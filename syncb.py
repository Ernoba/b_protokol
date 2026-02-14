# syncb.py (Versi V5: FIX PORT & WEB UI)
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
    sys.exit(1)

# Import BProto
try:
    from bproto import BProto, PacketType
except ImportError:
    print("Error: Folder 'bproto' tidak ditemukan.")
    sys.exit(1)

# --- KONFIGURASI GLOBAL ---
WEB_PORT = 8080
# [FIX 1] Ganti Port Default ke 7003 agar tidak bentrok dengan Photobooth (7002)
SYNC_PORT = 7003 
SYNC_CMD_DELETE = "SYNC_DELETE"

# --- RAHASIA (SECRET) KHUSUS ---
# Pastikan ini BEDA dengan server.py ("ernoba-root")
SYNC_SECRET_KEY = "folder-sync-private-key-v1" 

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
        if not main_free: print(f"    - TCP {port} SIBUK (Mungkin dipakai Server Photobooth?)")
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
        self.app_instance = None 

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
            key = f"{ip}:{port}" 
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
        if not peer_rows: peer_rows = "<tr><td colspan='3' style='text-align:center'>Belum ada peer. Gunakan Manual Connect.</td></tr>"

        history_rows = ""
        for h in STATE.history:
            color = "blue" if "Kirim" in h['action'] else "green" if "Terima" in h['action'] else "red"
            history_rows += f"<tr><td>{h['time']}</td><td style='color:{color}'><b>{h['action']}</b></td><td>{h['file']}</td><td>{h['details']}</td></tr>"

        log_rows = "\n".join(STATE.logs[-10:])

        # [FIX 2] Menggunakan JavaScript untuk Refresh (Smart Reload)
        # Halaman hanya akan refresh jika user TIDAK sedang mengetik di input box.
        html = f"""
        <html>
        <head>
            <title>BProto Sync</title>
            <style>
                body {{ font-family: monospace; max-width: 800px; margin: 0 auto; padding: 20px; background: #f4f4f4; }}
                h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                .card {{ background: white; padding: 15px; border: 1px solid #ccc; margin-bottom: 20px; border-radius: 5px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #eee; }}
                button {{ padding: 8px 15px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 3px; }}
                button:hover {{ background: #0056b3; }}
                input {{ padding: 5px; }}
                .status-ok {{ color: green; font-weight: bold; }}
                .status-warn {{ color: orange; font-weight: bold; }}
            </style>
            <script>
                // Script Anti-Gangguan Input
                setInterval(function() {{
                    // Cek apakah user sedang fokus di input text/number
                    var active = document.activeElement;
                    if (active.tagName !== "INPUT") {{
                        location.reload(); 
                    }} else {{
                        console.log("User sedang mengetik, skip refresh...");
                    }}
                }}, 5000); // Refresh setiap 5 detik
            </script>
        </head>
        <body>
            <h1>⚡ BProto Sync Node</h1>
            
            <div class="card" style="background: #e8f4ff; border-color: #b6d4fe;">
                <h3>🛡️ Isolasi Jaringan</h3>
                <p>Node ini berjalan di Port <b>{SYNC_PORT}</b> dengan kunci rahasia berbeda.
                <br>Aman dijalankan bersamaan dengan Server Photobooth (Port 7002).</p>
            </div>

            <div class="card">
                <h3>➕ Manual Connect</h3>
                <form method="POST">
                    <input type="hidden" name="action" value="manual_add_peer">
                    IP Lawan: <input type="text" name="target_ip" value="127.0.0.1" size="15" placeholder="192.168.x.x">
                    Port Lawan: <input type="number" name="target_port" value="7003" size="10">
                    <button type="submit">HUBUNGKAN</button>
                </form>
            </div>

            <div class="card">
                <h3>Status Node</h3>
                <table>
                    <tr><td width="30%">Device Name</td><td><b>{STATE.device_name}</b></td></tr>
                    <tr><td>Folder Path</td><td>{STATE.folder_path}</td></tr>
                    <tr><td>PORT (TCP/WS)</td><td><b>{SYNC_PORT}</b> / {SYNC_PORT+100}</td></tr>
                    <tr><td>Auto Sync</td><td>{'✅ ON' if STATE.config['auto_sync'] else '❌ OFF'}</td></tr>
                </table>
                <br>
                <form method="POST">
                    <button type="submit" name="action" value="toggle_sync">On/Off Auto Sync</button>
                    <button type="submit" name="action" value="toggle_delete" style="background:#dc3545">On/Off Remote Delete</button>
                </form>
            </div>

            <div class="card">
                <h3>👥 Peers (Terhubung)</h3>
                <table>
                    <tr><th>Nama</th><th>Address</th><th>Last Seen</th></tr>
                    {peer_rows}
                </table>
            </div>

            <div class="card">
                <h3>📂 History & Logs</h3>
                <table>
                    <tr><th>Jam</th><th>Aksi</th><th>File</th><th>Detail</th></tr>
                    {history_rows}
                </table>
                <br>
                <pre style="background: #222; color: #0f0; padding: 10px; height: 150px; overflow-y: scroll;">{log_rows}</pre>
            </div>
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
        
        # --- PERBAIKAN UTAMA: ISOLASI NETWORK ---
        self.bp = BProto(
            save_dir=self.folder_path, 
            port=port,
            device_name=f"SyncNode-{port}",
            secret=SYNC_SECRET_KEY,
            app_id="sync-net-v1"
        )
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

    def manual_add_peer(self, ip, port):
        self.bp.discovery.peers[ip] = {'name': 'ManualPeer', 'port': port}
        self._on_peer_found(ip, 'ManualPeer', port)
        STATE.add_log(f"System: Peer {ip}:{port} ditambahkan manual.")

    def start(self):
        threading.Thread(target=run_web_server, daemon=True).start()
        print(f"[INFO] Web Dashboard: http://localhost:{WEB_PORT}")
        print(f"[INFO] Secret Key: {SYNC_SECRET_KEY} (Aman dari PhotoBooth)")

        self.bp.start()
        
        observer = Observer()
        observer.schedule(SyncHandler(self), self.folder_path, recursive=False)
        observer.start()

        print(f"[INFO] Node Berjalan TCP:{SYNC_PORT}, WS:{SYNC_PORT+100}")
        try:
            while True:
                self.bp.scan() 
                time.sleep(5)
        except KeyboardInterrupt:
            observer.stop()
            self.bp.stop()
            observer.join()

    def _on_peer_found(self, ip, name, port=None):
        if port is None and ip in self.bp.discovery.peers:
            port = self.bp.discovery.peers[ip]['port']
        
        key = f"{ip}:{port}"
        if key not in STATE.peers:
            STATE.add_log(f"Network: Peer Ditemukan -> {name} ({ip}:{port})")
            STATE.add_peer(ip, name, port)

    def _on_error(self, msg):
        if "UDP Bind failed" in msg: return 
        if "Authentication Failed" in msg or "Handshake GAGAL" in msg:
            STATE.add_log(f"Security: Menolak koneksi asing (Salah Kunci).")
            return
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
        for info in STATE.peers.values():
            peer_ip = info['ip']
            STATE.add_log(f"Action: Mengirim {filename} ke {peer_ip}:{info['port']}")
            STATE.add_history("Kirim File", filename, f"to {peer_ip}")
            self.bp.send_file(peer_ip, filepath)

    def sync_delete(self, filename):
        payload = json.dumps({"cmd": SYNC_CMD_DELETE, "file": filename})
        for info in STATE.peers.values():
            self.bp.send_message(info['ip'], payload)

if __name__ == "__main__":
    folder_arg = "SyncFolder"
    # [FIX] Default port sekarang 7003
    port_arg = 7003 
    if len(sys.argv) > 1: folder_arg = sys.argv[1]
    if len(sys.argv) > 2: port_arg = int(sys.argv[2])

    print("--- KONFIGURASI ---")
    SYNC_PORT = ask_valid_sync_port(port_arg)
    WEB_PORT = ask_valid_web_port(8080)
    print("-------------------")

    app = BProtoSync(folder_arg, SYNC_PORT)
    app.start()