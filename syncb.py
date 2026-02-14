# syncb.py (Versi V3: Manual Connect + Strict Port)
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
WEB_PORT = 8080
SYNC_PORT = 7002
SYNC_CMD_DELETE = "SYNC_DELETE"

# --- HELPER: CEK PORT ---
def is_port_free(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except OSError:
        return False

def ask_valid_sync_port(start_port):
    port = start_port
    while True:
        ws_port = port + 100
        main_free = is_port_free(port)
        ws_free = is_port_free(ws_port)

        if main_free and ws_free:
            return port
        
        print(f"\n[!] GANGGUAN PORT TERDETEKSI:")
        if not main_free: print(f"    - TCP {port} SIBUK")
        if not ws_free: print(f"    - WS {ws_port} SIBUK")
            
        try:
            suggestion = port + 1
            new_input = input(f"    >>> Masukkan Port Baru (rekomendasi: {suggestion}): ")
            port = int(new_input) if new_input.strip() else suggestion
        except ValueError:
            pass

def ask_valid_web_port(start_port):
    port = start_port
    while True:
        if is_port_free(port): return port
        try:
            suggestion = port + 1
            new_input = input(f"    >>> Port Web {port} Sibuk. Port baru (rec: {suggestion}): ")
            port = int(new_input) if new_input.strip() else suggestion
        except ValueError:
            pass

# --- STATE MANAGEMENT ---
class AppState:
    def __init__(self):
        self.device_name = "SyncNode"
        self.folder_path = ""
        self.peers = {} 
        self.logs = []   
        self.history = [] 
        self.config = {'auto_sync': True, 'allow_delete': True}
        self.lock = threading.Lock()
        self.app_instance = None # Reference to BProtoSync instance

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
                'action': action, 'file': filename, 'details': details
            })
            if len(self.history) > 20: self.history.pop()

    def add_peer(self, ip, name, port):
        with self.lock:
            key = f"{ip}:{port}" # Use IP:Port as key to allow local simulation
            self.peers[key] = {
                'ip': ip, 'port': port, 'name': name,
                'last_seen': datetime.now().strftime("%H:%M:%S")
            }

STATE = AppState()

# --- WEB SERVER HANDLER ---
class SyncWebHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args): pass 

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
                STATE.add_log(f"Config: Auto Sync -> {STATE.config['auto_sync']}")
            elif action == 'toggle_delete':
                STATE.config['allow_delete'] = not STATE.config['allow_delete']
                STATE.add_log(f"Config: Allow Delete -> {STATE.config['allow_delete']}")
            elif action == 'manual_add_peer':
                try:
                    target_ip = params['target_ip'][0].strip()
                    target_port = int(params['target_port'][0].strip())
                    if target_ip and target_port:
                        STATE.add_log(f"Manual Add: Menambahkan {target_ip}:{target_port}...")
                        # Panggil fungsi di App Instance
                        if STATE.app_instance:
                            STATE.app_instance.manual_add_peer(target_ip, target_port)
                except Exception as e:
                    STATE.add_log(f"Error Manual Add: {e}")

        self.send_response(303)
        self.send_header('Location', '/')
        self.end_headers()

    def get_html_content(self):
        peer_rows = ""
        for key, info in STATE.peers.items():
            peer_rows += f"<tr><td>{info['name']}</td><td>{info['ip']}:{info['port']}</td><td>{info['last_seen']}</td></tr>"
        if not peer_rows: peer_rows = "<tr><td colspan='3' style='text-align:center'>Belum ada peer (Gunakan Manual Connect)</td></tr>"

        history_rows = ""
        for h in STATE.history:
            color = "blue" if "Kirim" in h['action'] else "green" if "Terima" in h['action'] else "red"
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
            
            <div style="background:#eee; padding:10px; border:1px solid #999; margin-bottom:20px;">
                <h3>➕ Manual Connect (Wajib untuk Simulasi 1 Laptop)</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="manual_add_peer">
                    IP Lawan: <input type="text" name="target_ip" value="127.0.0.1" size="15">
                    Port Lawan: <input type="number" name="target_port" placeholder="Contoh: 7002" size="10">
                    <button type="submit" style="cursor:pointer; font-weight:bold;">TAMBAHKAN PEER</button>
                </form>
                <small>Jika Port Anda 7003, masukkan Port teman (misal 7002) di sini.</small>
            </div>

            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr><td width="30%">Device Name</td><td><b>{STATE.device_name}</b></td></tr>
                <tr><td>Folder Path</td><td>{STATE.folder_path}</td></tr>
                <tr><td>YOUR PORT</td><td><b>TCP {SYNC_PORT}</b> / WS {SYNC_PORT+100}</td></tr>
                <tr><td>Auto Sync</td><td>{'✅ ON' if STATE.config['auto_sync'] else '❌ OFF'}</td></tr>
            </table>

            <br>
            <h3>👥 Peers (Terhubung)</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #ddd;"><th>Nama</th><th>Address</th><th>Last Seen</th></tr>
                {peer_rows}
            </table>

            <h3>📂 History</h3>
            <table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">
                <tr style="background-color: #ddd;"><th>Jam</th><th>Aksi</th><th>File</th><th>Detail</th></tr>
                {history_rows}
            </table>

            <h3>📜 Logs</h3>
            <pre style="background-color: #f0f0f0; padding: 10px; height: 150px; overflow-y: scroll;">{log_rows}</pre>
        </body>
        </html>
        """
        return html

def run_web_server():
    try:
        socketserver.TCPServer.allow_reuse_address = True
        server = socketserver.TCPServer(("", WEB_PORT), SyncWebHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[WEB ERROR] {e}")

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
    def __init__(self, app): self.app = app
    def _process_event(self, event):
        if event.is_directory: return None
        filename = os.path.basename(event.src_path)
        if filename.startswith('.') or filename.endswith('.tmp'): return None
        if not STATE.config['auto_sync']: return None
        if self.app.loop_preventer.should_ignore(filename): return None
        return filename

    def on_created(self, event):
        if fname := self._process_event(event):
            STATE.add_log(f"FS: File Dibuat -> {fname}")
            self.app.sync_file(event.src_path)
            self.app.loop_preventer.update_signature(event.src_path)

    def on_modified(self, event):
        if fname := self._process_event(event):
            STATE.add_log(f"FS: File Diubah -> {fname}")
            self.app.sync_file(event.src_path)
            self.app.loop_preventer.update_signature(event.src_path)

    def on_deleted(self, event):
        fname = os.path.basename(event.src_path)
        if not self.app.loop_preventer.should_ignore(fname) and not event.is_directory:
            STATE.add_log(f"FS: File Dihapus -> {fname}")
            self.app.sync_delete(fname)

class BProtoSync:
    def __init__(self, folder_path, port):
        self.folder_path = os.path.abspath(folder_path)
        if not os.path.exists(self.folder_path): os.makedirs(self.folder_path)
        STATE.folder_path = self.folder_path
        STATE.app_instance = self
        
        self.loop_preventer = LoopPreventer()
        STATE.add_log(f"Core: BProto init di {self.folder_path}")
        
        self.bp = BProto(save_dir=self.folder_path, port=port)
        STATE.device_name = self.bp.name
        
        # Hook Events
        self.bp.events.on("peer_found", self._on_peer_found)
        self.bp.events.on("message", self._on_message_received)
        self.bp.events.on("progress", self._on_transfer_progress)
        self.bp.events.on("error", self._on_error)
        self._build_index()

    def _build_index(self):
        for f in os.listdir(self.folder_path):
            fp = os.path.join(self.folder_path, f)
            if os.path.isfile(fp): self.loop_preventer.update_signature(fp)

    def manual_add_peer(self, ip, port):
        """Memaksa menambahkan peer secara manual (Bypass UDP Discovery)"""
        # Inject ke internal BProto discovery peers
        self.bp.discovery.peers[ip] = {'name': 'ManualPeer', 'port': port}
        # Trigger event lokal untuk update UI STATE
        self._on_peer_found(ip, 'ManualPeer', port)
        STATE.add_log(f"System: Peer {ip}:{port} ditambahkan manual.")

    def start(self):
        threading.Thread(target=run_web_server, daemon=True).start()
        print(f"[INFO] Web Dashboard: http://localhost:{WEB_PORT}")

        self.bp.start()
        
        observer = Observer()
        observer.schedule(SyncHandler(self), self.folder_path, recursive=False)
        observer.start()

        print(f"[INFO] Node Berjalan TCP:{SYNC_PORT}, WS:{SYNC_PORT+100}")
        try:
            while True:
                self.bp.scan() # Tetap scan UDP siapa tahu ada device lain
                time.sleep(5)
        except KeyboardInterrupt:
            observer.stop()
            self.bp.stop()
            observer.join()

    def _on_peer_found(self, ip, name, port=None):
        # Ambil port dari discovery jika tidak disediakan
        if port is None and ip in self.bp.discovery.peers:
            port = self.bp.discovery.peers[ip]['port']
        
        # Logic update state
        # Kita pakai key unik ip:port agar simulasi localhost bisa jalan (127.0.0.1:7002 vs 127.0.0.1:7003)
        key = f"{ip}:{port}"
        if key not in STATE.peers:
            STATE.add_log(f"Network: Peer Ditemukan -> {name} ({ip}:{port})")
            STATE.add_peer(ip, name, port)

    def _on_error(self, msg):
        if "UDP Bind failed" in msg: return 
        STATE.add_log(f"Error: {msg}")

    def _on_message_received(self, ip, content):
        try:
            data = json.loads(content)
            if data.get('cmd') == SYNC_CMD_DELETE:
                fname = data.get('file')
                if STATE.config['allow_delete']:
                    target = os.path.join(self.folder_path, fname)
                    if os.path.exists(target):
                        STATE.add_log(f"Network: Hapus {fname} dari {ip}")
                        self.loop_preventer.add(fname)
                        os.remove(target)
                        STATE.add_history("Hapus (Remote)", fname, f"by {ip}")
        except: pass 

    def _on_transfer_progress(self, filename, percent, speed):
        self.loop_preventer.add(filename)
        if percent >= 100:
            STATE.add_log(f"Transfer: Selesai -> {filename}")
            STATE.add_history("Terima File", filename, "Sukses")
            time.sleep(0.5)
            self.loop_preventer.update_signature(os.path.join(self.folder_path, filename))

    def sync_file(self, filepath):
        filename = os.path.basename(filepath)
        # Iterate over STATE.peers values
        for info in STATE.peers.values():
            peer_ip = info['ip']
            # BProto aslinya hanya support IP di discovery, 
            # tapi karena kita simulasi manual, kita harus pastikan port benar.
            # BProto._connect_and_send_header mengambil port dari discovery.peers[ip]['port']
            # Jadi pastikan Manual Add sudah mengisi discovery.peers
            
            STATE.add_log(f"Action: Mengirim {filename} ke {peer_ip}:{info['port']}")
            STATE.add_history("Kirim File", filename, f"to {peer_ip}")
            
            # PENTING: BProto send_file mengambil port dari self.discovery.peers[ip]
            # Jadi fungsi manual_add_peer di atas sudah menangani logic ini.
            self.bp.send_file(peer_ip, filepath)

    def sync_delete(self, filename):
        payload = json.dumps({"cmd": SYNC_CMD_DELETE, "file": filename})
        for info in STATE.peers.values():
            self.bp.send_message(info['ip'], payload)

if __name__ == "__main__":
    folder_arg = "SyncFolder"
    port_arg = 7002
    if len(sys.argv) > 1: folder_arg = sys.argv[1]
    if len(sys.argv) > 2: port_arg = int(sys.argv[2])

    print("--- KONFIGURASI ---")
    SYNC_PORT = ask_valid_sync_port(port_arg)
    WEB_PORT = ask_valid_web_port(8080)
    print("-------------------")

    app = BProtoSync(folder_arg, SYNC_PORT)
    app.start()