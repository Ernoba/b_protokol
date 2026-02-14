import time
import socket
import os
import sys

# Import Library
try:
    from bproto import BProto
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

def get_local_ip():
    """Mendapatkan IP Address asli"""
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
    print(f"[{time.strftime('%H:%M:%S')}] ➤ {msg}")

def on_server_error(msg):
    print(f"[{time.strftime('%H:%M:%S')}] ❌ ERROR: {msg}")

def on_progress(name, pct, speed):
    if pct < 100:
        print(f"\r ↳ Menerima {name}: {pct:.1f}% ({speed:.1f} MB/s)", end="")
    else:
        print(f"\r ↳ Selesai: {name}                ")

def on_message(ip, content):
    # Fitur Baru: Menampilkan pesan chat jika ada client yang kirim
    print(f"\n[{time.strftime('%H:%M:%S')}] 💬 CHAT dari {ip}: {content}")

def main():
    save_path = os.path.join(os.getcwd(), "Hasil_Foto_Photobooth")
    if not os.path.exists(save_path): os.makedirs(save_path)

    my_ip = get_local_ip()

    print("\n" + "="*50)
    print(f"       📸 SERVER PHOTOBOOTH (MODULAR V2)       ")
    print("="*50)
    print(f"[*] IP SERVER   : {my_ip}")
    print(f"[*] FOLDER FOTO : {save_path}")
    print(f"[*] STATUS      : SIAP (Event System V2 Active)")
    print("-" * 50 + "\n")

    # Init BProto (Struktur baru otomatis menangani init modules)
    server = BProto(
        device_name="Server-Utama",
        secret="ernoba-root",
        app_id="photobooth-v1", 
        save_dir=save_path
    )
    
    # --- BAGIAN INI YANG BERUBAH ---
    # Menggunakan .on() karena sekarang pakai EventManager class
    server.events.on("log", on_server_log)
    server.events.on("error", on_server_error)
    server.events.on("progress", on_progress)
    server.events.on("message", on_message) # Extra listener untuk fitur chat baru
    # -------------------------------

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