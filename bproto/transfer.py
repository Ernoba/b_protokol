# bproto/transfer.py
import os
import time
import socket
import zipfile
import hashlib
import zlib
from .config import CHUNK_SIZE, VERIFY_INTEGRITY, ENABLE_COMPRESSION, ENABLE_ENCRYPTION

class TransferManager:
    def __init__(self, save_dir, events, security_manager=None):
        self.save_dir = save_dir
        self.events = events
        self.security = security_manager # Referensi ke SecurityManager

    def calculate_checksum(self, filepath):
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def prepare_file(self, filepath):
        is_zip = False
        final_path = filepath
        
        if os.path.isdir(filepath):
            final_path = f"{filepath}.zip"
            self._zip_folder(filepath, final_path)
            is_zip = True
            
        if not os.path.exists(final_path):
            raise FileNotFoundError("File not found")
            
        filesize = os.path.getsize(final_path)
        filename = os.path.basename(final_path)
        
        checksum = None
        if VERIFY_INTEGRITY:
            self.events.log(f"Calculating checksum for {filename}...")
            checksum = self.calculate_checksum(final_path)
            
        return {
            "path": final_path,
            "name": filename,
            "size": filesize,
            "is_zip": is_zip,
            "checksum": checksum,
            "compressed": ENABLE_COMPRESSION,
            "encrypted": ENABLE_ENCRYPTION
        }

    def stream_file(self, sock, file_path, start_byte, total_size):
        with open(file_path, 'rb') as f:
            f.seek(start_byte)
            sent = start_byte
            start_time = time.time()
            filename = os.path.basename(file_path)
            
            while True:
                chunk = f.read(CHUNK_SIZE)
                if not chunk: break
                
                # 1. Kompresi
                if ENABLE_COMPRESSION:
                    chunk = zlib.compress(chunk)
                
                # 2. Enkripsi (Jika ada security manager dan enabled)
                if self.security and ENABLE_ENCRYPTION:
                    chunk = self.security.encrypt_data(chunk)

                # Kirim panjang chunk dulu (agar penerima tahu seberapa banyak baca)
                # Format: [4 byte length][data]
                sock.sendall(len(chunk).to_bytes(4, byteorder='big'))
                sock.sendall(chunk)
                
                sent += len(chunk) # Hitung bytes raw yang dikirim (bukan asli)
                
                # Progress calc (estimasi kasar karena kompresi mengubah ukuran)
                elapsed = time.time() - start_time
                mbps = (sent - start_byte) / (1024*1024) / (elapsed if elapsed > 0 else 1)
                self.events.progress(filename, min((sent/total_size)*100, 99), mbps)

        # Kirim terminator ukuran 0
        sock.sendall((0).to_bytes(4, byteorder='big'))

    def receive_stream(self, sock, meta):
        path = os.path.join(self.save_dir, meta['name'])
        
        # Deteksi fitur dari metadata pengirim
        use_compression = meta.get('compressed', False)
        use_encryption = meta.get('encrypted', False)

        received_total = 0
        total_expected = meta['size']
        start_time = time.time()

        with open(path, 'wb') as f:
            while True:
                # Baca panjang chunk berikutnya
                raw_len = sock.recv(4)
                if not raw_len: break
                chunk_len = int.from_bytes(raw_len, byteorder='big')
                if chunk_len == 0: break # End of stream

                # Baca chunk penuh
                chunk_data = b""
                while len(chunk_data) < chunk_len:
                    packet = sock.recv(chunk_len - len(chunk_data))
                    if not packet: break
                    chunk_data += packet
                
                # 1. Dekripsi
                if use_encryption and self.security:
                    try:
                        chunk_data = self.security.decrypt_data(chunk_data)
                    except Exception as e:
                        self.events.error("Decryption error during transfer")
                        break

                # 2. Dekompresi
                if use_compression:
                    try:
                        chunk_data = zlib.decompress(chunk_data)
                    except Exception:
                        self.events.error("Decompression error")
                        break
                
                f.write(chunk_data)
                received_total += len(chunk_data) # Ukuran asli
                
                elapsed = time.time() - start_time
                mbps = (received_total) / (1024*1024) / (elapsed if elapsed > 0 else 1)
                self.events.progress(meta['name'], (received_total/total_expected)*100, mbps)
        
        self.events.log(f"File Received: {meta['name']}")
        
        if VERIFY_INTEGRITY and 'checksum' in meta and meta['checksum']:
            self.events.log("Verifying checksum...")
            local_hash = self.calculate_checksum(path)
            if local_hash == meta['checksum']:
                self.events.log("Integrity Check: PASSED")
            else:
                self.events.error("Integrity Check: FAILED")

    def _zip_folder(self, path, zip_name):
        self.events.log("Zipping folder...")
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(path):
                for file in files:
                    z.write(os.path.join(root, file), 
                            os.path.relpath(os.path.join(root, file), os.path.dirname(path)))