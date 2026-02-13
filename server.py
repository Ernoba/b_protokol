import time
import socket
import os
import sys

# Pastikan library bproto bisa diimport
try:
    from bproto import BProto
except ImportError:
    # Hack jika dijalankan langsung tanpa install package
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

def get_local_ip():
    """Mendapatkan IP Address asli (bukan localhost 127.0.0.1)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Tidak perlu terkoneksi beneran, cuma pancingan untuk dapat IP
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def on_server_log(msg):
    # Callback untuk mempercantik log server
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")

def main():
    # 1. Tentukan Folder Penyimpanan
    save_path = os.path.join(os.getcwd(), "Server_Storage")
    if not os.path.exists(save_path):
        os.makedirs(save_path)

    # 2. Ambil IP Lokal untuk Info
    my_ip = get_local_ip()

    print("="*40)
    print(f"   ERNOBA SERVER (BProto V1)   ")
    print("="*40)
    print(f"[*] IP Address Server : {my_ip}")
    print(f"[*] Penyimpanan       : {save_path}")
    print(f"[*] Status            : MENUNGGU KONEKSI...")
    print("-" * 40)
    print("TIPS: Jika client tidak menemukan server,")
    print("      pastikan FIREWALL dimatikan atau")
    print("      izinkan Python di Windows Firewall.")
    print("-" * 40)

    # 3. Jalankan Server
    # device_name diganti jadi nama komputer agar mudah dikenali
    server = BProto(
        device_name=f"Server-{socket.gethostname()}", 
        secret="ernoba-root", 
        save_dir=save_path
    )
    
    # Override log agar tampil di layar
    server.events["log"] = on_server_log
    server.events["error"] = lambda e: print(f"[ERROR] {e}")
    
    server.start()
    
    try:
        while True:
            # Server standby (Keep Alive)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Mematikan Server...")
        server.stop()
        print("[!] Server Berhenti.")

if __name__ == "__main__":
    main()