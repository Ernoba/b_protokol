# bproto/websocket.py
import asyncio
import websockets
import json
import threading
import os
from .protocol import PacketType

class WebSocketManager:
    def __init__(self, port, security, events, transfer):
        self.port = port + 100
        self.security = security
        self.events = events
        self.transfer = transfer
        self.loop = None

    def start(self):
        """Jalankan WS server di thread terpisah"""
        t = threading.Thread(target=self._run_async_server, daemon=True)
        t.start()

    def _run_async_server(self):
        # 1. Setup Loop Baru untuk Thread ini
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # 2. Definisikan Coroutine Utama
        async def runner():
            self.events.log(f"WebSocket Server running on port {self.port}")
            # Gunakan Context Manager untuk menjaga server tetap hidup
            # Catatan: Handler di websockets v11+ hanya menerima 1 argumen (websocket)
            async with websockets.serve(self._handle_client, "0.0.0.0", self.port):
                await asyncio.Future() # Run forever (tunggu selamanya)

        # 3. Jalankan Loop
        try:
            self.loop.run_until_complete(runner())
        except Exception as e:
            self.events.error(f"WebSocket Server Crash: {e}")
        finally:
            self.loop.close()

    async def _handle_client(self, websocket):
        # Websockets terbaru tidak lagi mengirim 'path' sebagai argumen kedua
        client_ip = websocket.remote_address[0]
        self.events.log(f"New WS Connection from {client_ip}")

        try:
            async for message in websocket:
                if isinstance(message, str):
                    # --- HANDLE JSON COMMANDS ---
                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        continue

                    msg_type = data.get('type')

                    # AUTH HANDLER
                    if msg_type == 'AUTH':
                        client_proof = data.get('proof')
                        # Validasi Proof (SHA256 dari secret kosong atau logic lain)
                        expected = self.security.create_proof("") 
                        
                        if client_proof == expected:
                            token = self.security.create_session_for(client_ip)
                            await websocket.send(json.dumps({"type": "AUTH_OK", "token": token}))
                        else:
                            await websocket.send(json.dumps({"type": "AUTH_FAIL"}))
                            return

                    # CHAT / COMMANDS
                    elif msg_type == PacketType.MESSAGE:
                        self.events.emit("message", client_ip, data.get('content'))
                        await websocket.send(json.dumps({"status": "RECEIVED"}))
                    
                    elif msg_type == PacketType.CLIPBOARD:
                        self.events.emit("clipboard", data.get('content'))
                    
                    # PREPARE FILE TRANSFER
                    elif msg_type == PacketType.FILE_INIT:
                         websocket.file_meta = data.get('file')
                         await websocket.send(json.dumps({"status": "READY_FOR_STREAM"}))

                elif isinstance(message, bytes):
                    # --- HANDLE BINARY (FILE) ---
                    if hasattr(websocket, 'file_meta'):
                        meta = websocket.file_meta
                        save_path = os.path.join(self.transfer.save_dir, meta['name'])
                        
                        # Tulis langsung (Append binary)
                        with open(save_path, "ab") as f:
                            f.write(message)
                        
                        # Simple progress update (langsung 100% karena WS streaming beda logic)
                        self.events.progress(meta['name'], 100, 0)
                        self.events.log(f"File received via WS: {meta['name']}")
                        
                        # Bersihkan meta setelah selesai
                        del websocket.file_meta
                        await websocket.send(json.dumps({"status": "FILE_SAVED"}))

        except websockets.exceptions.ConnectionClosed:
            pass # Koneksi putus wajar
        except Exception as e:
            self.events.error(f"WS Handler Error: {e}")