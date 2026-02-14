# bproto/server.py
import socket
import threading
import struct
import json
import uuid
from .protocol import PacketType
from .utils import SystemUtils

class ServerManager:
    def __init__(self, port, security, transfer, events):
        self.port = port
        self.security = security
        self.transfer = transfer
        self.events = events
        self.running = False

    def start(self):
        self.running = True
        t = threading.Thread(target=self._accept_loop, daemon=True)
        t.start()
        return t

    def stop(self):
        self.running = False

    def _accept_loop(self):
        serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            serv.bind(('0.0.0.0', self.port))
            serv.listen(5)
            while self.running:
                try:
                    conn, addr = serv.accept()
                    threading.Thread(target=self._handle_client, args=(conn, addr)).start()
                except OSError: break
        except Exception as e:
            self.events.error(f"TCP Server Error: {e}")
        finally:
            serv.close()

    def _handle_client(self, conn, addr):
        client_ip = addr[0]
        try:
            # Baca Header Length (4 bytes big-endian)
            raw_len = conn.recv(4)
            if not raw_len: return
            header_len = struct.unpack("!I", raw_len)[0]
            
            # Baca Header JSON
            header_data = conn.recv(header_len).decode()
            header = json.loads(header_data)
            
            # 1. AUTENTIKASI
            auth_data = header.get('auth', {})
            authorized = False

            if auth_data.get('auth_mode') == "TOKEN":
                if self.security.verify_token(client_ip, auth_data.get('data')):
                    authorized = True
                    # Kirim OK + Resume Offset
                    self._send_json(conn, {"status": "OK", "resume_offset": self._get_local_offset(header)})

            if not authorized:
                # Challenge-Response
                nonce = uuid.uuid4().hex[:8]
                self._send_json(conn, {"status": "CHALLENGE", "nonce": nonce})
                
                client_proof = conn.recv(64).decode() # Terima SHA256
                
                if self.security.verify_handshake(nonce, client_proof):
                    new_token = self.security.create_session_for(client_ip)
                    self._send_json(conn, {
                        "status": "OK", 
                        "token": new_token, 
                        "resume_offset": self._get_local_offset(header)
                    })
                else:
                    self._send_json(conn, {"status": "FAIL"})
                    return

            # 2. ROUTING TIPE PAKET
            msg_type = header.get('type')
            
            if msg_type == PacketType.FILE_INIT:
                self.transfer.receive_stream(conn, header['file'])
                
            elif msg_type == PacketType.MESSAGE:
                # Fitur Baru: Chat
                content = header.get('content')
                self.events.log(f"Message from {client_ip}: {content}")
                self.events.emit("message", client_ip, content)
                
            elif msg_type == PacketType.CLIPBOARD:
                # Fitur Baru: Clipboard
                content = header.get('content')
                success = SystemUtils.copy_to_clipboard(content)
                status = "Copied" if success else "Failed"
                self.events.log(f"Clipboard received from {client_ip}: {status}")
                self.events.emit("clipboard", content)

        except Exception as e:
            self.events.error(f"Client Handle Error: {e}")
        finally:
            conn.close()

    def _send_json(self, sock, data):
        js = json.dumps(data).encode()
        sock.sendall(struct.pack("!I", len(js)))
        sock.sendall(js)

    def _get_local_offset(self, header):
        if header.get('type') != PacketType.FILE_INIT: return 0
        
        # Logic yang benar: Cek ukuran file yang sudah ada
        fname = header['file']['name']
        fpath = os.path.join(self.transfer.save_dir, fname)
        
        # Jika file ada, return ukurannya (int). Jika tidak, return 0.
        return os.path.getsize(fpath) if os.path.exists(fpath) else 0