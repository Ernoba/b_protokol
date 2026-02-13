import time
import os
import threading
from flask import Flask, render_template, jsonify, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import library BProto buatanmu
from bproto import BProto

app = Flask(__name__)

# --- GLOBAL STATE ---
# Menyimpan state aplikasi agar bisa diakses Flask dan Watchdog
STATE = {
    "bproto": None,
    "observer": None,
    "target_ip": None,
    "folder_path": None,
    "logs": []
}

# Inisialisasi BProto Client
client = BProto(device_name="Ernoba-WebClient", secret="ernoba-root")
client.start()
STATE["bproto"] = client

# --- LOGGING HELPER ---
def add_log(msg):
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {msg}"
    STATE["logs"].insert(0, entry) # Log terbaru di atas
    if len(STATE["logs"]) > 50: STATE["logs"].pop() # Batasi 50 log
    print(entry)

# --- WATCHDOG HANDLER (Inti Pemindahan File) ---
class AutoMoveHandler(FileSystemEventHandler):
    """Menangani event saat file baru dibuat"""
    
    def on_created(self, event):
        if event.is_directory: return

        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        # 1. Filter hanya file gambar (bisa disesuaikan)
        valid_ext = ('.jpg', '.jpeg', '.png', '.mp4', '.avi')
        if not filename.lower().endswith(valid_ext):
            add_log(f"Mengabaikan file non-media: {filename}")
            return

        # 2. Tunggu sebentar (File kamera seringkali butuh waktu milliseconds untuk selesai ditulis)
        time.sleep(1) 
        
        target_ip = STATE["target_ip"]
        if not target_ip: return

        add_log(f"📸 Terdeteksi: {filename}. Mengirim...")

        try:
            # 3. KIRIM FILE MENGGUNAKAN BPROTO
            # Kita modifikasi sedikit agar send_file melempar error jika gagal
            # (Asumsi library BProto kamu sudah aman, kita panggil langsung)
            client.send_file(target_ip, filepath)
            
            # 4. HAPUS FILE JIKA SUKSES (MOVE MECHANISM)
            add_log(f"✅ Terkirim: {filename}")
            try:
                os.remove(filepath)
                add_log(f"🗑️ File lokal dihapus (Folder bersih kembali).")
            except Exception as e:
                add_log(f"⚠️ Gagal menghapus file lokal: {e}")

        except Exception as e:
            add_log(f"❌ Gagal mengirim {filename}: {e}")

# --- FLASK ROUTES (API untuk HTML) ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    client.scan()
    time.sleep(1) # Tunggu hasil scan UDP
    return jsonify(client.peers)

@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.json
    folder = data.get('folder')
    ip = data.get('target_ip')

    if not os.path.exists(folder):
        return jsonify({"status": "error", "message": "Folder tidak ditemukan!"})

    # Simpan Config
    STATE["target_ip"] = ip
    STATE["folder_path"] = folder

    # Stop observer lama jika ada
    if STATE["observer"]:
        STATE["observer"].stop()
        STATE["observer"].join()

    # Mulai Watchdog Baru
    event_handler = AutoMoveHandler()
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=False)
    observer.start()
    
    STATE["observer"] = observer
    add_log(f"MONITORING AKTIF di: {folder} -> Server: {ip}")
    return jsonify({"status": "ok"})

@app.route('/api/stop')
def api_stop():
    if STATE["observer"]:
        STATE["observer"].stop()
        STATE["observer"].join()
        STATE["observer"] = None
        add_log("Monitoring dihentikan.")
    return jsonify({"status": "ok"})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": STATE["logs"]})

if __name__ == "__main__":
    try:
        # Jalankan Flask di port 5000
        print("Membuka Interface Web Client...")
        print("Buka browser di: http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=False) # Debug False agar thread aman
    except KeyboardInterrupt:
        client.stop()
        if STATE["observer"]: STATE["observer"].stop()