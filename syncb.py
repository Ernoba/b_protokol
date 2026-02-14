# syncb.py (Versi Final: Interaktif & Web GUI)
import sys
import os
import time
import json
import socket
import threading
import http.server
import socketserver
import urllib.parse
from datetime import datetime
from threading import Timer

# Cek library watchdog
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("Error: Library 'watchdog' belum terinstall.")
    print("Silahkan jalankan: pip install watchdog")
    sys.exit(1)

# Import BProto
try:
    from bproto import BProto, PacketType
except ImportError:
    print("Error: Folder 'bproto' tidak ditemukan.")
    sys.exit(1)

# --- KONFIGURASI GLOBAL ---
# Default Port (Akan divalidasi saat runtime)
WEB_PORT = 8080
SYNC_PORT = 7002
SYNC_CMD_DELETE = "SYNC_DELETE"

# --- HELPER: CEK PORT INTERAKTIF ---
def ask_valid_port(port, label):
    """
    Mengecek apakah port bisa digunakan. 
    Jika tidak, meminta user menginputkan port baru.
    """
    while True:
        try:
            # Coba bind port dummy untuk tes ketersediaan
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SO_REUSEADDR agar tidak perlu menunggu TIME_WAIT
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port # Jika berhasil bind dan close, berarti port aman
        except OSError:
            print(f"\n[!] Port {label} ({port}) sedang SIBUK/TERPAKAI.")
            try:
                new_input = input(f"    >>> Masukkan Port {label} baru (contoh: {port+1}): ")
                if not new_input.strip(): continue # Cegah input kosong
                port = int(new_input)
            except ValueError:
                print("    [!] Harap masukkan angka yang valid.")

# --- STATE MANAGEMENT (Untuk Web UI) ---
class AppState:
    def __init__(self):
        self.device_name = "SyncNode"
        self.folder_path = ""
        self.peers = {} 
        self.logs = []   
        self.history = [] 
        self.config = {
            'auto_sync': True,
            'allow_delete': True
        }
        self.lock = threading.Lock()

    def add_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.lock:
            self.logs.append(f"[{timestamp}] {msg}")
            if len(self.logs) > 50: self.logs.pop(0)
            print(f"[{timestamp}] {msg}")

    def add_history(self, action, filename, details=""):
        with self.lock:
            self.history.insert(0, {
                'time': datetime.now().strftime("%H:%M:%S"),
                'action': action,
                'file': filename,
                'details': details
            })
            if len(self.history) > 20: self.history.pop()

    def add_peer(self, ip, name):
        with self.lock:
            self.peers[ip] = {
                'name': name,
                'last_seen': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

STATE = AppState()

# --- WEB SERVER HANDLER ---
class SyncWebHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass # Matikan log request HTTP di terminal agar tidak berisik

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(self.get_html_content().encode())
        else:
            self.send_error(404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode()
        params = urllib.parse.parse_qs(body)

        if 'action' in params:
            action = params['action'][0]
            if action == 'toggle_sync':
                STATE.config['auto_sync'] = not STATE.config['auto_sync']
                STATE.add_log(f"Config: Auto Sync set to {STATE.config['auto_sync']}")
            elif action == 'toggle_delete':
                STATE.config['allow_delete'] = not STATE.config['allow_delete']
                STATE.add_log(f"Config: Allow Delete set to {STATE.config['allow_delete']}")
            elif action == 'trigger_scan':
                STATE.add_log("Manual Scan triggered...")

        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def get_html_content(self):
        peer_rows = ""
        for ip, info in STATE.peers.items():
            peer_rows += f"<tr><td>{info['name']}</td><td>{ip}</td><td>{info['last_seen']}</td></tr>"
        if not peer_rows: peer_rows = "<tr><td colspan='3'>Belum ada peer ditemukan</td></tr>"

        history_rows = ""
        for h in STATE.history:
            color = "black"
            if "Kirim" in h['action']: color = "blue"
            elif "Terima" in h['action']: color = "green"
            elif "Hapus" in h['action']: color = "red"
            history_rows += f"<tr><td>{h['time']}</td><td style='color:{color}'><b>{h['action']}</b></td><td>{h['file']}</td><td>{h['details']}</td></tr>"

        log_rows = "\n".join(STATE.logs[-10:])

        html = f"""
        <html>
        <head>
            <title>BProto Sync Manager</title>
            <meta http-equiv="refresh" content="5">
        </head>
        <body style="font-family: monospace; max-width: 800px; margin: 0 auto; padding: 20px;">
            <h1>⚡ BProto Sync Manager</h1>
            <hr>
            
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr><td width="30%">Device Name</td><td><b>{STATE.device_name}</b></td></tr>
                <tr><td>Folder Path</td><td>{STATE.folder_path}</td></tr>
                <tr><td>Sync Port</td><td>TCP {SYNC_PORT}</td></tr>
                <tr><td>Auto Sync</td><td>{'✅ ON' if STATE.config['auto_sync'] else '❌ OFF'}</td></tr>
                <tr><td>Allow Remote Delete</td><td>{'✅ ON' if STATE.config['allow_delete'] else '❌ OFF'}</td></tr>
            </table>

            <h3>Kontrol</h3>
            <form method="POST">
                <button type="submit" name="action" value="toggle_sync">On/Off Auto Sync</button>
                <button type="submit" name="action" value="toggle_delete">On/Off Remote Delete</button>
            </form>

            <hr>
            <h3>👥 Peers (Perangkat Terhubung)</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #ddd;"><th>Nama</th><th>IP Address</th><th>Terakhir Terlihat</th></tr>
                {peer_rows}
            </table>

            <hr>
            <h3>📂 Riwayat Transfer</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #ddd;"><th>Jam</th><th>Aksi</th><th>File</th><th>Keterangan</th></tr>
                {history_rows}
            </table>

            <h3>📜 System Logs</h3>
            <pre style="background-color: #f0f0f0; padding: 10px; border: 1px solid #ccc; height: 150px; overflow-y: scroll;">{log_rows}</pre>
        </body>
        </html>
        """
        return html

def run_web_server():
    # Menggunakan port yang sudah divalidasi di main
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("", WEB_PORT), SyncWebHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[WEB ERROR] Gagal menjalankan web server: {e}")

# --- LOGIC UTAMA ---

class LoopPreventer:
    def __init__(self):
        self.ignoring = set()
        self.signatures = {}

    def add(self, filename):
        self.ignoring.add(filename)
        Timer(10.0, lambda: self.ignoring.discard(filename)).start()

    def should_ignore(self, filename):
        return filename in self.ignoring
    
    def update_signature(self, filepath):
        try:
            stats = os.stat(filepath)
            self.signatures[os.path.basename(filepath)] = (stats.st_size, stats.st_mtime)
        except FileNotFoundError: pass

class SyncHandler(FileSystemEventHandler):
    def __init__(self, app):
        self.app = app

    def _process_event(self, event):
        if event.is_directory: return None
        filename = os.path.basename(event.src_path)
        if filename.startswith('.') or filename.endswith('.tmp') or filename.endswith('.crdownload'): return None
        if not STATE.config['auto_sync']: return None
        if self.app.loop_preventer.should_ignore(filename): return None
        return filename

    def on_created(self, event):
        filename = self._process_event(event)
        if filename:
            STATE.add_log(f"FS: File Dibuat -> {filename}")
            self.app.sync_file(event.src_path)
            self.app.loop_preventer.update_signature(event.src_path)

    def on_modified(self, event):
        filename = self._process_event(event)
        if filename:
            STATE.add_log(f"FS: File Diubah -> {filename}")
            self.app.sync_file(event.src_path)
            self.app.loop_preventer.update_signature(event.src_path)

    def on_deleted(self, event):
        if event.is_directory: return
        filename = os.path.basename(event.src_path)
        if self.app.loop_preventer.should_ignore(filename): return
        STATE.add_log(f"FS: File Dihapus -> {filename}")
        self.app.sync_delete(filename)

class BProtoSync:
    def __init__(self, folder_path, port):
        self.folder_path = os.path.abspath(folder_path)
        if not os.path.exists(self.folder_path):
            os.makedirs(self.folder_path)

        STATE.folder_path = self.folder_path
        self.loop_preventer = LoopPreventer()

        STATE.add_log(f"Core: BProto init di {self.folder_path}")
        self.bp = BProto(save_dir=self.folder_path, port=port)
        STATE.device_name = self.bp.name
        
        self.bp.events.on("peer_found", self._on_peer_found)
        self.bp.events.on("message", self._on_message_received)
        self.bp.events.on("progress", self._on_transfer_progress)
        self.bp.events.on("error", self._on_error)
        
        self._build_index()

    def _build_index(self):
        for f in os.listdir(self.folder_path):
            fp = os.path.join(self.folder_path, f)
            if os.path.isfile(fp): self.loop_preventer.update_signature(fp)

    def start(self):
        # Jalankan Web Server
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        print(f"[INFO] Web Dashboard aktif di: http://localhost:{WEB_PORT}")

        # Jalankan BProto
        self.bp.start()
        
        # Jalankan Watchdog
        event_handler = SyncHandler(self)
        observer = Observer()
        observer.schedule(event_handler, self.folder_path, recursive=False)
        observer.start()

        print(f"[INFO] SyncNode Berjalan di Port {SYNC_PORT}.")
        print(f"[INFO] Tekan Ctrl+C untuk berhenti.\n")

        try:
            while True:
                self.bp.scan()
                time.sleep(5)
        except KeyboardInterrupt:
            observer.stop()
            self.bp.stop()
            observer.join()

    def _on_peer_found(self, ip, name):
        if ip not in STATE.peers:
            STATE.add_log(f"Network: Peer Baru -> {name} ({ip})")
            STATE.add_peer(ip, name)

    def _on_error(self, msg):
        # Filter error bind UDP yang wajar di satu mesin
        if "UDP Bind failed" in msg: return 
        STATE.add_log(f"Error: {msg}")

    def _on_message_received(self, ip, content):
        try:
            data = json.loads(content)
            if data.get('cmd') == SYNC_CMD_DELETE:
                filename = data.get('file')
                if not STATE.config['allow_delete']: return
                target_path = os.path.join(self.folder_path, filename)
                if os.path.exists(target_path):
                    STATE.add_log(f"Network: Hapus {filename} dari {ip}")
                    self.loop_preventer.add(filename)
                    try:
                        os.remove(target_path)
                        STATE.add_history("Hapus (Remote)", filename, f"by {ip}")
                    except: pass
        except: pass 

    def _on_transfer_progress(self, filename, percent, speed):
        self.loop_preventer.add(filename)
        if percent >= 100:
            STATE.add_log(f"Transfer: File Selesai -> {filename}")
            STATE.add_history("Terima File", filename, "Sukses")
            time.sleep(0.5)
            self.loop_preventer.update_signature(os.path.join(self.folder_path, filename))

    def sync_file(self, filepath):
        filename = os.path.basename(filepath)
        for peer_ip in STATE.peers:
            STATE.add_log(f"Action: Mengirim {filename} ke {peer_ip}")
            STATE.add_history("Kirim File", filename, f"to {peer_ip}")
            self.bp.send_file(peer_ip, filepath)

    def sync_delete(self, filename):
        payload = json.dumps({"cmd": SYNC_CMD_DELETE, "file": filename})
        for peer_ip in STATE.peers:
            STATE.add_log(f"Action: Broadcast Delete {filename} ke {peer_ip}")
            STATE.add_history("Kirim Hapus", filename, f"to {peer_ip}")
            self.bp.send_message(peer_ip, payload)

if __name__ == "__main__":
    folder_arg = "SyncFolder"
    port_arg = 7002
    
    if len(sys.argv) > 1:
        folder_arg = sys.argv[1]
    if len(sys.argv) > 2:
        port_arg = int(sys.argv[2])

    print("--- KONFIGURASI PORT ---")
    
    # 1. Validasi Port Sync (BProto) - INTERAKTIF
    SYNC_PORT = ask_valid_port(port_arg, "SYNC (TCP)")
    
    # 2. Validasi Port Web - INTERAKTIF
    WEB_PORT = ask_valid_port(8080, "WEB DASHBOARD")
    
    print("------------------------")

    app = BProtoSync(folder_arg, SYNC_PORT)
    app.start()