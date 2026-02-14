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

class BProto:
    def __init__(self, device_name=None, secret=DEFAULT_SECRET, save_dir=DEFAULT_SAVE_DIR, port=None):
        self.name = device_name if device_name else socket.gethostname()
        self.save_dir = os.path.abspath(save_dir)
        if not os.path.exists(self.save_dir): os.makedirs(self.save_dir)

        # 1. Inisialisasi Sub-Sistem
        self.events = EventManager()
        self.security = SecurityManager(secret)
        self.transfer = TransferManager(self.save_dir, self.events)
        
        # Setup Port
        try:
            self.tcp_port = port if port else TCP_PORT
        except NameError:
            self.tcp_port = 7002

        # 2. Network Managers
        self.discovery = DiscoveryManager(self.name, self.tcp_port, self.events)
        self.server = ServerManager(self.tcp_port, self.security, self.transfer, self.events)
        
        # Backward compatibility property
        self.peers = self.discovery.peers 

    def start(self):
        self.events.log(f"BProto V2 Starting on Port {self.tcp_port}...")
        self.server.start()
        self.discovery.start_listener()
        self.events.log("Service Active.")

    def stop(self):
        self.discovery.stop()
        self.server.stop()
        self.events.log("Service Stopped.")

    def scan(self):
        self.discovery.scan()

    # --- CLIENT ACTIONS ---
    
    def _connect_and_send_header(self, target_ip, packet_type, payload):
        """Helper internal untuk koneksi TCP"""
        if target_ip not in self.discovery.peers:
            self.events.error("Target IP unknown (Scan first?)")
            return None

        target_port = self.discovery.peers[target_ip]['port']
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(CONNECTION_TIMEOUT)
        
        try:
            sock.connect((target_ip, target_port))
            
            # Auth Header
            auth_info = self.security.get_outgoing_auth(target_ip)
            header = {
                "type": packet_type,
                "auth": auth_info
            }
            header.update(payload) # Merge payload (file info / chat content)
            
            # Send Header
            js = json.dumps(header).encode()
            sock.sendall(struct.pack("!I", len(js)))
            sock.sendall(js)
            
            # Handle Auth Response
            resp_data = sock.recv(1024).decode()
            if not resp_data: return None
            resp = json.loads(resp_data)
            
            if resp['status'] == "CHALLENGE":
                nonce = resp['nonce']
                proof = self.security.create_proof(nonce)
                sock.sendall(proof.encode())
                
                auth_resp = json.loads(sock.recv(1024).decode())
                if auth_resp['status'] == "OK":
                    self.security.save_client_token(target_ip, auth_resp['token'])
                    return sock, auth_resp # Return socket aktif & respon akhir
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