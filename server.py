import time
import socket
import os
import sys

# Pastikan library bproto bisa diimport
try:
    from bproto import BProto
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

def get_local_ip():
    """Mendapatkan IP Address asli (bukan localhost 127.0.0.1)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def on_server_log(msg):
    # Log dengan warna/format supaya enak dilihat saat event
    print(f"[{time.strftime('%H:%M:%S')}] ➤ {msg}")

def main():
    # 1. Tentukan Folder Penyimpanan (Di Desktop atau folder script)
    save_path = os.path.join(os.getcwd(), "Hasil_Foto_Photobooth")
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # 2. Ambil IP Lokal untuk Info
    my_ip = get_local_ip()

    print("\n" + "="*50)
    print(f"       📸 SERVER PHOTOBOOTH (ERNOBA LINK)       ")
    print("="*50)
    print(f"[*] IP SERVER   : {my_ip}")
    print(f"[*] FOLDER FOTO : {save_path}")
    print(f"[*] STATUS      : SIAP MENERIMA FOTO...")
    print("-" * 50)
    print("CATATAN: Pastikan Laptop Client & Server di Wi-Fi yang sama.")
    print("-" * 50 + "\n")

    # 3. Jalankan Server
    server = BProto(
        device_name=f"Server-Utama", # Nama ini akan muncul di HP/Client saat Scan
        secret="ernoba-root", 
        save_dir=save_path
    )
    
    # Override log
    server.events["log"] = on_server_log
    server.events["error"] = lambda e: print(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR: {e}")
    server.events["progress"] = lambda name, pct, speed: print(f"\r ↳ Menerima {name}: {pct:.1f}% ({speed:.1f} MB/s)", end="") if pct < 100 else print(f"\r ↳ Selesai: {name}                ")

    server.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Mematikan Server...")
        server.stop()
        print("[!] Server Berhenti.")

if __name__ == "__main__":
    main()