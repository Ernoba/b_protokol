import os
import time
import threading
import uuid
import socket
from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename

# Import library bproto Anda
from bproto import BProto

# Konfigurasi Flask
app = Flask(__name__, template_folder='templates') # Pastikan folder templates ada

# Konfigurasi Folder
UPLOAD_FOLDER = 'temp_uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# State Global
STATE = {
    "client": None,
    "target_ip": None,
    "logs": []
}

# --- BPROTO INIT ---
# Inisialisasi BProto
STATE["client"] = BProto(device_name="Ernoba-Photobooth")
STATE["client"].start()

def add_log(msg, type="info"):
    t = time.strftime("%H:%M:%S")
    entry = {"time": t, "msg": msg, "type": type}
    STATE["logs"].insert(0, entry)
    if len(STATE["logs"]) > 50: STATE["logs"].pop()
    print(f"[{type.upper()}] {msg}")

def process_and_send(filepath, filename):
    """
    Fungsi background: Kirim file ke Server BProto lalu hapus.
    Dijalankan di thread terpisah.
    """
    target = STATE["target_ip"]
    if not target:
        add_log(f"Tertunda: {filename} (Pilih Server!)", "error")
        return

    # Beri jeda sedikit agar UI terasa responsif dulu
    time.sleep(0.5)
    
    add_log(f"Mengirim: {filename} -> {target}...", "info")
    try:
        # Kirim menggunakan BProto
        STATE["client"].send_file(target, filepath)
        add_log(f"✅ Terkirim: {filename}", "success")
        
        # Hapus file temporary setelah terkirim untuk hemat storage
        try:
            os.remove(filepath)
        except: pass
        
    except Exception as e:
        add_log(f"❌ Gagal: {filename} - {str(e)}", "error")

# --- ROUTES ---

@app.route('/')
def index():
    # Pastikan file index.html ada di dalam folder 'templates/'
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    STATE["client"].scan()
    # Tunggu respons UDP broadcast
    time.sleep(1.0) 
    return jsonify(STATE["client"].peers)

@app.route('/api/set_server', methods=['POST'])
def api_set_server():
    data = request.json
    ip = data.get('ip')
    STATE["target_ip"] = ip
    add_log(f"Target Server diset ke: {ip}", "success")
    return jsonify({"status": "ok", "target": ip})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    files = request.files.getlist('file')
    if not STATE["target_ip"]:
        return jsonify({"error": "⚠️ Server Tujuan Belum Dipilih!"}), 400

    count = 0
    for file in files:
        if file.filename == '': continue
        
        # Generate nama unik agar tidak bentrok saat foto beruntun
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        unique_name = f"photo_{uuid.uuid4().hex[:8]}.{ext}"
        filename = secure_filename(unique_name)
        
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        # Jalankan pengiriman di background thread
        threading.Thread(target=process_and_send, args=(save_path, filename)).start()
        count += 1
        
    return jsonify({"status": "ok", "count": count})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": STATE["logs"]})

if __name__ == "__main__":
    try:
        # Mendapatkan IP Lokal untuk ditampilkan di Terminal
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        my_ip = s.getsockname()[0]
        s.close()
        
        print(f"==========================================")
        print(f" 📸 ERNOBA PHOTOBOOTH SYSTEM STARTED")
        print(f" 🔗 Akses UI di: http://{my_ip}:5000")
        print(f"==========================================")
        
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        print("\nStopping Service...")
        STATE["client"].stop()