import time
import socket
import os
import sys

# Import Library
try:
    from bproto import BProto
except ImportError:
    # Fallback jika dijalankan langsung dari folder project
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
    # Tampilan progress bar sederhana
    bar_len = 20
    filled_len = int(bar_len * pct // 100)
    bar = '█' * filled_len + '-' * (bar_len - filled_len)
    
    if pct < 100:
        print(f"\r ↳ Menerima: |{bar}| {pct:.1f}% ({speed:.1f} MB/s)", end="")
    else:
        print(f"\r ↳ Selesai:  |{bar}| 100%                 ")

def on_message(ip, content):
    # Menampilkan pesan chat dari Python Client maupun Web Client (JS)
    print(f"\n[{time.strftime('%H:%M:%S')}] 💬 CHAT dari {ip}: {content}")

def on_clipboard(content):
    print(f"\n[{time.strftime('%H:%M:%S')}] 📋 CLIPBOARD DITERIMA: {content}")

def main():
    # Folder penyimpanan
    save_path = os.path.join(os.getcwd(), "Hasil_Foto_Photobooth")
    if not os.path.exists(save_path): os.makedirs(save_path)

    my_ip = get_local_ip()

    # Init BProto (Otomatis mengaktifkan Enkripsi & WebSocket)
    # Default TCP Port: 7002
    # Default WS Port : 7102 (7002 + 100)
    server = BProto(
        device_name="Server-Utama",
        secret="ernoba-root", 
        save_dir=save_path,
        port=7002 # Pastikan server menggunakan port standar
    )
    
    # Register Event Listeners
    server.events.on("log", on_server_log)
    server.events.on("error", on_server_error)
    server.events.on("progress", on_progress)
    server.events.on("message", on_message)
    server.events.on("clipboard", on_clipboard) # Listener baru

    print("\n" + "="*55)
    print(f"    📸 SERVER PHOTOBOOTH (BPROTO V2.5 - CRYPTO+WS)    ")
    print("="*55)
    print(f"[*] IP SERVER      : {my_ip}")
    print(f"[*] FOLDER FOTO    : {save_path}")
    print(f"[*] TCP PORT       : 7002 (Python Client)")
    print(f"[*] WEBSOCKET URL  : ws://{my_ip}:7102 (Web/JS Client)")
    print(f"[*] ENKRIPSI       : AKTIF (AES-GCM)")
    print("-" * 55 + "\n")

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