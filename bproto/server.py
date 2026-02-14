# bproto/server.py
import socket
import threading
import struct
import json
import uuid
import os
import time
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
        # Fix: Allow reuse address agar tidak error "Address already in use" saat restart cepat
        serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
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
        # [DEBUG] Tampilkan siapa yang connect
        print(f"[DEBUG] Koneksi masuk dari: {client_ip}")

        try:
            # Baca Header Length
            raw_len = conn.recv(4)
            if not raw_len: return
            header_len = struct.unpack("!I", raw_len)[0]
            
            # Baca Header JSON
            header_data = conn.recv(header_len).decode()
            header = json.loads(header_data)
            
            # 1. AUTENTIKASI
            auth_data = header.get('auth', {})
            authorized = False

            # Cek Token Lama
            if auth_data.get('auth_mode') == "TOKEN":
                if self.security.verify_token(client_ip, auth_data.get('data')):
                    authorized = True
                    # Kirim OK
                    print(f"[DEBUG] {client_ip} Login via TOKEN sukses.")
                    self._send_json(conn, {"status": "OK", "resume_offset": self._get_local_offset(header)})

            # Jika Token Gagal, Lakukan Handshake Baru
            if not authorized:
                print(f"[DEBUG] {client_ip} Meminta Handshake Baru...")
                nonce = uuid.uuid4().hex[:8]
                self._send_json(conn, {"status": "CHALLENGE", "nonce": nonce})
                
                # FIX: Baca proof dengan buffer aman (bukan fix 64 byte yg bisa macet)
                client_proof = conn.recv(1024).decode().strip()
                
                if self.security.verify_handshake(nonce, client_proof):
                    print(f"[DEBUG] {client_ip} Handshake BERHASIL.")
                    new_token = self.security.create_session_for(client_ip)
                    self._send_json(conn, {
                        "status": "OK", 
                        "token": new_token, 
                        "resume_offset": self._get_local_offset(header)
                    })
                else:
                    print(f"[DEBUG] {client_ip} Handshake GAGAL (Wrong Secret).")
                    self._send_json(conn, {"status": "FAIL"})
                    return

            # 2. PROSES TIPE PAKET
            msg_type = header.get('type')
            
            if msg_type == PacketType.FILE_INIT:
                fname = header['file']['name']
                print(f"[DEBUG] Menerima file: {fname}")
                self.transfer.receive_stream(conn, header['file'])
                
            elif msg_type == PacketType.MESSAGE:
                content = header.get('content')
                self.events.log(f"Chat dari {client_ip}: {content}")
                self.events.emit("message", client_ip, content)
                
            elif msg_type == PacketType.CLIPBOARD:
                content = header.get('content')
                success = SystemUtils.copy_to_clipboard(content)
                self.events.log(f"Clipboard dari {client_ip}: {'Sukses' if success else 'Gagal'}")

        except Exception as e:
            self.events.error(f"Client Handle Error: {e}")
            import traceback
            traceback.print_exc() # Print error detail ke terminal server
        finally:
            conn.close()

    def _send_json(self, sock, data):
        js = json.dumps(data).encode()
        sock.sendall(struct.pack("!I", len(js)))
        sock.sendall(js)

    def _get_local_offset(self, header):
        # FIX FINAL: Logic sederhana & aman
        if header.get('type') != PacketType.FILE_INIT: return 0
        
        try:
            fname = header['file']['name']
            fpath = os.path.join(self.transfer.save_dir, fname)
            
            if os.path.exists(fpath):
                size = os.path.getsize(fpath)
                print(f"[DEBUG] File ada, resume dari: {size}")
                return size
            else:
                return 0
        except Exception as e:
            print(f"[DEBUG] Error cek offset: {e}")
            return 0