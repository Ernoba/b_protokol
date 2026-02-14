# bproto/core.py
import socket
import struct
import json
import os
import time

# Import Modul Baru
from .config import *
from .protocol import PacketType
from .events import EventManager
from .security import SecurityManager
from .discovery import DiscoveryManager
from .transfer import TransferManager
from .server import ServerManager
from .websocket import WebSocketManager

class BProto:
    def __init__(self, device_name=None, secret=DEFAULT_SECRET, save_dir=DEFAULT_SAVE_DIR, port=None):
        self.name = device_name if device_name else socket.gethostname()
        self.save_dir = os.path.abspath(save_dir)
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)

        # Port Logic
        try:
            self.tcp_port = port if port else TCP_PORT
        except NameError:
            self.tcp_port = 7002

        # 1. Inisialisasi Sub-Sistem
        self.events = EventManager()
        self.security = SecurityManager(secret)
        # Pass security ke transfer untuk enkripsi file
        self.transfer = TransferManager(self.save_dir, self.events, self.security) 
        
        # 2. Network Managers
        self.discovery = DiscoveryManager(self.name, self.tcp_port, self.events)
        self.server = ServerManager(self.tcp_port, self.security, self.transfer, self.events)
        
        # 3. WebSocket Manager (Baru)
        self.ws_server = WebSocketManager(self.tcp_port, self.security, self.events, self.transfer)
        
        self.peers = self.discovery.peers 

    def start(self):
        self.events.log(f"BProto V2.5 (Crypto+WS) Starting...")
        self.server.start()
        self.discovery.start_listener()
        self.ws_server.start() # Start WebSocket
        self.events.log(f"TCP: {self.tcp_port}, WS: {self.tcp_port + 100}")
        self.events.log("Service Active.")

    def stop(self):
        self.discovery.stop()
        self.server.stop()
        self.events.log("Service Stopped.")

    def scan(self):
        self.discovery.scan()

    # --- CLIENT ACTIONS ---
    
    def _connect_and_send_header(self, target_ip, packet_type, payload):
        """Helper internal untuk koneksi TCP dengan penanganan header 4-byte"""
        if target_ip not in self.discovery.peers:
            self.events.error("Target IP unknown (Scan first?)")
            return None

        target_port = self.discovery.peers[target_ip]['port']
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECTION_TIMEOUT)
        
        try:
            sock.connect((target_ip, target_port))
            
            # 1. Kirim Header ke Server
            auth_info = self.security.get_outgoing_auth(target_ip)
            header = {
                "type": packet_type,
                "auth": auth_info
            }
            header.update(payload) 
            
            js = json.dumps(header).encode()
            sock.sendall(struct.pack("!I", len(js)))
            sock.sendall(js)
            
            # 2. Baca Respon Awal (Challenge/OK) - FIX: Pakai Header 4 Byte
            raw_len = sock.recv(4)
            if not raw_len: return None
            header_len = struct.unpack("!I", raw_len)[0]
            
            resp_data = sock.recv(header_len).decode()
            if not resp_data: return None
            resp = json.loads(resp_data)
            
            # 3. Handle Handshake jika diminta
            if resp['status'] == "CHALLENGE":
                nonce = resp['nonce']
                proof = self.security.create_proof(nonce)
                # Sesuai server.py, proof dikirim mentah (bukan _send_json)
                sock.sendall(proof.encode())
                
                # Baca Respon Akhir Handshake - FIX: Pakai Header 4 Byte
                raw_len_final = sock.recv(4)
                if not raw_len_final: return None
                header_len_final = struct.unpack("!I", raw_len_final)[0]
                
                auth_resp_data = sock.recv(header_len_final).decode()
                auth_resp = json.loads(auth_resp_data)
                
                if auth_resp['status'] == "OK":
                    self.security.save_client_token(target_ip, auth_resp['token'])
                    return sock, auth_resp 
                else:
                    self.events.error("Authentication Failed")
                    sock.close()
                    return None
                    
            elif resp['status'] == "OK":
                return sock, resp
            
            sock.close()
            return None
        except Exception as e:
            self.events.error(f"Connection Error: {e}")
            if sock: sock.close()
            return None

    def send_file(self, target_ip, filepath):
        try:
            file_meta = self.transfer.prepare_file(filepath)
        except Exception as e:
            self.events.error(str(e))
            return False

        result = self._connect_and_send_header(target_ip, PacketType.FILE_INIT, {"file": file_meta})
        
        if result:
            sock, resp = result
            try:
                # Ambil offset jika server mendukung resume
                start_byte = resp.get('resume_offset', 0)
                self.transfer.stream_file(sock, file_meta['path'], start_byte, file_meta['size'])
                self.events.log(f"Transfer Complete: {file_meta['name']}")
                return True
            except Exception as e:
                self.events.error(f"Stream Error: {e}")
            finally:
                sock.close()
                if file_meta['is_zip'] and os.path.exists(file_meta['path']):
                    os.remove(file_meta['path'])
        return False

    def send_message(self, target_ip, message):
        """Fitur Baru: Kirim Chat"""
        result = self._connect_and_send_header(target_ip, PacketType.MESSAGE, {"content": message})
        if result:
            sock, _ = result
            sock.close()
            self.events.log(f"Message sent to {target_ip}")
            return True
        return False

    def send_clipboard(self, target_ip, text):
        """Fitur Baru: Kirim ke Clipboard Remote"""
        result = self._connect_and_send_header(target_ip, PacketType.CLIPBOARD, {"content": text})
        if result:
            sock, _ = result
            sock.close()
            self.events.log(f"Clipboard data sent to {target_ip}")
            return True
        return False