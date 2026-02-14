# Simpan sebagai cek_koneksi.py
import socket

SERVER_IP = "192.168.100.39"  # Ganti dengan IP Server Anda
PORT = 7002                   # Port default config.py

print(f"Mencoba menghubungi {SERVER_IP}:{PORT}...")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5) # Waktu tunggu 5 detik

try:
    sock.connect((SERVER_IP, PORT))
    print("✅ BERHASIL: Koneksi TCP Terbuka! Masalah ada di Auth/File.")
    sock.close()
except socket.timeout:
    print("❌ GAGAL: Time Out. (Firewall Server Aktif atau IP Salah)")
except ConnectionRefusedError:
    print("❌ GAGAL: Connection Refused. (Server.py belum dijalankan)")
except Exception as e:
    print(f"❌ ERROR LAIN: {e}")