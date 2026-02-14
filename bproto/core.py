# bproto/core.py
import socket
import struct
import json
import os
import threading
import time
import hashlib
import zipfile
import uuid

# Import dari module tetangga
from .config import *
from .utils import SystemUtils

class BProto:
    def __init__(self, device_name=None, secret=DEFAULT_SECRET, save_dir=DEFAULT_SAVE_DIR):
        self.name = device_name if device_name else socket.gethostname()
        self.secret = secret
        self.save_dir = os.path.abspath(save_dir)
        
        # GANTI INI: Gunakan port tetap dari config
        try:
            self.tcp_port = TCP_PORT 
        except NameError:
            self.tcp_port = 7002 # Fallback jika config belum update
        
        self.running = False
        
        # Peer Discovery Data
        self.peers = {} 
        
        # SESSION MANAGEMENT
        self.authorized_sessions = {} 
        self.client_tokens = {}       

        # Default Callbacks (bisa di-override user)
        self.events = {
            "log": lambda m: print(f"[BPROTO LOG] {m}"),
            "error": lambda m: print(f"[BPROTO ERR] {m}"),
            "progress": lambda n, p, s: None
        }

        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)

    def start(self):
        self.running = True
        threading.Thread(target=self._udp_listener, daemon=True).start()
        threading.Thread(target=self._tcp_server, daemon=True).start()
        self.events["log"](f"Service Active on TCP Port: {self.tcp_port}")

    def stop(self):
        self.running = False

    # --- DISCOVERY ---
    def scan(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = json.dumps({
            "t": "PING", "n": self.name, "p": self.tcp_port
        }).encode()
        try:
            sock.sendto(PROTOCOL_ID + payload, ('<broadcast>', DISCOVERY_PORT))
        except Exception as e:
            self.events["error"](f"Scan failed: {e}")
        finally: 
            sock.close()

    def _udp_listener(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('', DISCOVERY_PORT))
        except: return

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                if not data.startswith(PROTOCOL_ID): continue
                msg = json.loads(data[len(PROTOCOL_ID):])
                
                if msg['n'] == self.name and msg['p'] == self.tcp_port: continue

                ip = addr[0]
                self.peers[ip] = {'name': msg['n'], 'port': msg['p']}
                
                if msg['t'] == "PING":
                    resp = json.dumps({"t": "PONG", "n": self.name, "p": self.tcp_port}).encode()
                    sock.sendto(PROTOCOL_ID + resp, addr)
            except: pass

    # --- AUTH LOGIC ---
    def _get_auth_header(self, target_ip):
        now = time.time()
        if target_ip in self.client_tokens:
            session = self.client_tokens[target_ip]
            if now < session['expires']:
                return {"auth_mode": "TOKEN", "data": session['token']}
        return {"auth_mode": "NEW_HANDSHAKE", "data": None}

    def _verify_session_token(self, ip, token):
        if ip in self.authorized_sessions:
            sess = self.authorized_sessions[ip]
            if sess['token'] == token and time.time() < sess['expires']:
                return True
        return False

    def _create_session(self, ip):
        token = uuid.uuid4().hex
        self.authorized_sessions[ip] = {
            'token': token, 'expires': time.time() + SESSION_TIMEOUT
        }
        return token

    # --- TRANSFER ENGINE ---
    def send_file(self, target_ip, filepath):
        if target_ip not in self.peers: 
            self.events["error"]("Target IP not found in peers list")
            return False  # <--- Return False

        is_zip = False
        final_path = filepath
        if os.path.isdir(filepath):
            final_path = f"{filepath}.zip"
            self._zip_folder(filepath, final_path)
            is_zip = True
        
        filename = os.path.basename(final_path)
        
        try:
            filesize = os.path.getsize(final_path)
        except FileNotFoundError:
            self.events["error"]("File not found")
            return False # <--- Return False

        target_port = self.peers[target_ip]['port']

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(10)
            s.connect((target_ip, target_port))
            
            # Init Header
            auth_info = self._get_auth_header(target_ip)
            header = {
                "type": "FILE_INIT",
                "auth": auth_info,
                "file": {"name": filename, "size": filesize}
            }
            self._send_json(s, header)

            # Auth Response
            resp = json.loads(s.recv(1024).decode())
            start_byte = 0

            if resp['status'] == "CHALLENGE":
                # Handshake
                nonce = resp['nonce']
                proof = hashlib.sha256((self.secret + nonce).encode()).hexdigest()
                s.sendall(proof.encode())
                
                auth_resp = json.loads(s.recv(1024).decode())
                if auth_resp['status'] == "OK":
                    self.client_tokens[target_ip] = {
                        'token': auth_resp['token'],
                        'expires': time.time() + SESSION_TIMEOUT
                    }
                    start_byte = auth_resp.get('resume_offset', 0)
                else:
                    self.events["error"]("Authentication Failed (Wrong Secret?)")
                    return
            elif resp['status'] == "OK":
                start_byte = resp.get('resume_offset', 0)
            else:
                return

            # Streaming
            with open(final_path, 'rb') as f:
                f.seek(start_byte)
                sent = start_byte
                start_time = time.time()
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk: break
                    s.sendall(chunk)
                    sent += len(chunk)
                    elapsed = time.time() - start_time
                    mbps = (sent - start_byte) / (1024*1024) / (elapsed if elapsed > 0 else 1)
                    self.events["progress"](filename, (sent/filesize)*100, mbps)
            
            self.events["log"](f"Transfer Complete: {filename}")
            return True # <--- TAMBAHKAN INI (Sukses)

        except Exception as e:
            self.events["error"](f"Send Error: {e}")
            return False # <--- TAMBAHKAN INI (Gagal)
        finally:
            s.close()
            if is_zip and os.path.exists(final_path): os.remove(final_path)

    def _tcp_server(self):
        serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        serv.bind(('0.0.0.0', self.tcp_port))
        serv.listen(5)
        while self.running:
            try:
                conn, addr = serv.accept()
                threading.Thread(target=self._handle_client, args=(conn, addr)).start()
            except: break

    def _handle_client(self, conn, addr):
        client_ip = addr[0]
        try:
            header_len = struct.unpack("!I", conn.recv(4))[0]
            header = json.loads(conn.recv(header_len).decode())
            
            auth_data = header['auth']
            authorized = False

            # Verify Token
            if auth_data['auth_mode'] == "TOKEN":
                if self._verify_session_token(client_ip, auth_data['data']):
                    authorized = True
                    conn.sendall(json.dumps({"status": "OK", "resume_offset": self._get_file_size(header)}).encode())

            # Verify Handshake
            if not authorized:
                nonce = uuid.uuid4().hex[:8]
                conn.sendall(json.dumps({"status": "CHALLENGE", "nonce": nonce}).encode())
                
                client_proof = conn.recv(64).decode()
                expected_proof = hashlib.sha256((self.secret + nonce).encode()).hexdigest()
                
                if client_proof == expected_proof:
                    new_token = self._create_session(client_ip)
                    conn.sendall(json.dumps({
                        "status": "OK", "token": new_token, "resume_offset": self._get_file_size(header)
                    }).encode())
                else:
                    conn.sendall(json.dumps({"status": "FAIL"}).encode())
                    return

            if header['type'] == "FILE_INIT":
                self._receive_file_stream(conn, header['file'])

        except Exception as e:
            self.events["error"](f"Receive Error from {client_ip}: {e}")
        finally:
            conn.close()

    def _receive_file_stream(self, conn, meta):
        path = os.path.join(self.save_dir, meta['name'])
        curr_size = os.path.getsize(path) if os.path.exists(path) else 0
        mode = 'ab' if curr_size > 0 else 'wb'
        
        with open(path, mode) as f:
            while True:
                chunk = conn.recv(CHUNK_SIZE)
                if not chunk: break
                f.write(chunk)
        self.events["log"](f"File Received: {meta['name']} saved to {self.save_dir}")

    def _send_json(self, sock, data):
        js = json.dumps(data).encode()
        sock.sendall(struct.pack("!I", len(js)))
        sock.sendall(js)

    def _get_file_size(self, header):
        fpath = os.path.join(self.save_dir, header['file']['name'])
        return os.path.getsize(fpath) if os.path.exists(fpath) else 0

    def _zip_folder(self, path, zip_name):
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(path):
                for file in files:
                    z.write(os.path.join(root, file), 
                            os.path.relpath(os.path.join(root, file), os.path.dirname(path)))