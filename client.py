import time
import sys
from bproto import BProto

def progress_bar(filename, percent, speed):
    # Membuat bar loading sederhana
    bar_len = 30
    filled = int(bar_len * percent / 100)
    bar = '█' * filled + '-' * (bar_len - filled)
    sys.stdout.write(f"\r🚀 Mengirim {filename}: [{bar}] {percent:.1f}% | {speed:.1f} MB/s")
    sys.stdout.flush()
    if percent >= 100: print() # New line saat selesai

def main():
    client = BProto(device_name="Ernoba-Client", secret="rahasia123")
    
    # Pasang callback progress
    client.events["progress"] = progress_bar
    
    client.start()
    print("Mencari server di jaringan lokal...", end="", flush=True)
    
    # Scanning awal
    client.scan()
    time.sleep(2) # Beri waktu untuk discovery
    print(" Selesai.")

    while True:
        print("\n--- MENU CLIENT ---")
        if not client.peers:
            print("⚠️ Belum ada peer ditemukan. Coba Scan lagi.")
        else:
            print(f"Ditemukan {len(client.peers)} Peer:")
            peers_list = list(client.peers.items())
            for idx, (ip, data) in enumerate(peers_list):
                print(f"[{idx+1}] {data['name']} ({ip})")

        cmd = input("\n[S]can Ulang | [K]irim File | [Q]uit: ").lower()

        if cmd == 's':
            client.scan()
            time.sleep(1)
            
        elif cmd == 'k' and client.peers:
            try:
                choice = int(input("Pilih nomor peer tujuan: ")) - 1
                if 0 <= choice < len(peers_list):
                    target_ip = peers_list[choice][0]
                    filepath = input("Masukkan path file: ").replace('"', '').strip()
                    print("Memulai transfer...")
                    client.send_file(target_ip, filepath)
                else:
                    print("Pilihan salah.")
            except ValueError:
                print("Input tidak valid.")
                
        elif cmd == 'q':
            break

    client.stop()

if __name__ == "__main__":
    main()