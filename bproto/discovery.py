# bproto/discovery.py
import socket
import json
import threading
from .config import PROTOCOL_ID, DISCOVERY_PORT
from .protocol import PacketType

class DiscoveryManager:
# 1. Tambahkan parameter app_id di __init__
    def __init__(self, device_name, tcp_port, events, app_id="bproto-default"):
        self.device_name = device_name
        self.tcp_port = tcp_port
        self.events = events
        self.app_id = app_id  # <--- Simpan App ID
        self.peers = {} 
        self.running = False

    def start_listener(self):
        self.running = True
        threading.Thread(target=self._listen_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def scan(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        payload = json.dumps({
            "t": PacketType.PING, 
            "n": self.device_name, 
            "p": self.tcp_port,
            "a": self.app_id  # <--- Kirim App ID (key 'a')
        }).encode()
        try:
            sock.sendto(PROTOCOL_ID + payload, ('<broadcast>', DISCOVERY_PORT))
            self.events.log("Scanning for peers...")
        except Exception as e:
            self.events.error(f"Scan failed: {e}")
        finally:
            sock.close()

    def _listen_loop(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(('', DISCOVERY_PORT))
        except Exception as e:
            self.events.error(f"UDP Bind failed: {e}")
            return

        while self.running:
            try:
                data, addr = sock.recvfrom(4096)
                if not data.startswith(PROTOCOL_ID): continue
                
                msg = json.loads(data[len(PROTOCOL_ID):])
                
                # --- FILTER BARU DI SINI ---
                # Jika App ID paket tidak sama dengan App ID saya, abaikan!
                remote_app = msg.get('a', 'bproto-default')
                if remote_app != self.app_id:
                    continue

                ip = addr[0]
                # Jika peer baru atau info update
                if ip not in self.peers or self.peers[ip]['port'] != msg['p']:
                    self.peers[ip] = {'name': msg['n'], 'port': msg['p']}
                    self.events.emit("peer_found", ip, msg['n'])
                    self.events.log(f"Peer Found: {msg['n']} @ {ip}")

                # Auto reply PING dengan PONG
                if msg['t'] == PacketType.PING:
                    resp = json.dumps({
                        "t": PacketType.PONG, 
                        "n": self.device_name, 
                        "p": self.tcp_port,
                        "a": self.app_id # <--- Balas dengan App ID juga
                    }).encode()
                    sock.sendto(PROTOCOL_ID + resp, addr)
            except Exception: pass
        sock.close()