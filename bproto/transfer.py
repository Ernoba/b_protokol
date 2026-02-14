# bproto/transfer.py
import os
import time
import socket
import zipfile
import hashlib
from .config import CHUNK_SIZE, VERIFY_INTEGRITY

class TransferManager:
    def __init__(self, save_dir, events):
        self.save_dir = save_dir
        self.events = events

    def calculate_checksum(self, filepath):
        """Fitur Baru: Hitung hash file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def prepare_file(self, filepath):
        """Menyiapkan file (zip jika folder)"""
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
            "checksum": checksum
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
                sock.sendall(chunk)
                sent += len(chunk)
                
                # Progress calc
                elapsed = time.time() - start_time
                mbps = (sent - start_byte) / (1024*1024) / (elapsed if elapsed > 0 else 1)
                self.events.progress(filename, (sent/total_size)*100, mbps)

    def receive_stream(self, sock, meta):
        path = os.path.join(self.save_dir, meta['name'])
        curr_size = os.path.getsize(path) if os.path.exists(path) else 0
        mode = 'ab' if curr_size > 0 else 'wb'
        
        received_total = curr_size
        total_expected = meta['size']
        start_time = time.time()

        with open(path, mode) as f:
            while received_total < total_expected:
                chunk = sock.recv(CHUNK_SIZE)
                if not chunk: break
                f.write(chunk)
                received_total += len(chunk)
                
                elapsed = time.time() - start_time
                mbps = (received_total - curr_size) / (1024*1024) / (elapsed if elapsed > 0 else 1)
                self.events.progress(meta['name'], (received_total/total_expected)*100, mbps)
        
        self.events.log(f"File Received: {meta['name']} saved to {self.save_dir}")
        
        # Verify Integrity
        if VERIFY_INTEGRITY and 'checksum' in meta and meta['checksum']:
            self.events.log("Verifying checksum...")
            local_hash = self.calculate_checksum(path)
            if local_hash == meta['checksum']:
                self.events.log("Integrity Check: PASSED (File Perfect)")
            else:
                self.events.error("Integrity Check: FAILED (File Corrupt!)")

    def _zip_folder(self, path, zip_name):
        self.events.log("Zipping folder...")
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(path):
                for file in files:
                    z.write(os.path.join(root, file), 
                            os.path.relpath(os.path.join(root, file), os.path.dirname(path)))