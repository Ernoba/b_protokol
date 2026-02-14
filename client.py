import os
import time
import uuid
import socket
from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename

# Import library bproto Anda
from bproto import BProto

app = Flask(__name__, template_folder='templates')

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

# Init BProto
# Init BProto
# Kita paksa secret sama dengan server ("ernoba-root")
STATE["client"] = BProto(
    device_name="Ernoba-Photobooth-Client", 
    secret="ernoba-root",
    app_id="photobooth-v1"# <--- TAMBAHKAN INI
)

STATE["client"].start()

def add_log(msg, type="info"):
    t = time.strftime("%H:%M:%S")
    entry = {"time": t, "msg": msg, "type": type}
    STATE["logs"].insert(0, entry)
    if len(STATE["logs"]) > 50: STATE["logs"].pop()
    print(f"[{type.upper()}] {msg}")

# --- FUNGSI PENGIRIM (DIPERBARUI) ---
# Di file client.py

def send_sync(filepath, filename):
    target = STATE["target_ip"]
    if not target:
        add_log(f"Gagal: {filename} (Server belum diset!)", "error")
        return False

    add_log(f"Mengirim: {filename} -> {target}...", "info")
    
    # --- UBAH BAGIAN INI ---
    try:
        # Panggil fungsi internal bproto untuk melihat error aslinya
        sukses = STATE["client"].send_file(target, filepath)
        
        if sukses:
            add_log(f"✅ Terkirim: {filename}", "success")
            try: os.remove(filepath)
            except: pass
            return True
        else:
            # Ini akan muncul jika bproto menangkap error tapi me-return False
            add_log(f"❌ Ditolak Server: {filename}", "error")
            return False
            
    except Exception as e:
        # INI YANG PENTING: Menampilkan error spesifik (misal: TypeError)
        add_log(f"CRASH: {str(e)}", "error")
        print(f"DEBUG ERROR DETAIL: {e}") # Cek terminal
        return False
    
# --- ROUTES ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    STATE["client"].scan()
    time.sleep(1.0) 
    return jsonify(STATE["client"].peers)

@app.route('/api/set_server', methods=['POST'])
def api_set_server():
    data = request.json
    ip = data.get('ip')
    
    if not ip or len(ip.split('.')) != 4:
        return jsonify({"status": "error", "message": "Format IP Salah"}), 400
        
    STATE["target_ip"] = ip
    # Inject Manual Peer (Port Default 7002)
    STATE["client"].peers[ip] = {"name": "Manual-Server", "port": 7002} 
    
    add_log(f"🔗 Target Server manual: {ip} (Port 7002)", "success")
    return jsonify({"status": "ok", "target": ip})

@app.route('/api/upload', methods=['POST'])
def api_upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    files = request.files.getlist('file')
    if not STATE["target_ip"]:
        return jsonify({"error": "⚠️ Server Tujuan Belum Dipilih!"}), 400

    success_count = 0
    errors = []

    for file in files:
        if file.filename == '': continue
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        unique_name = f"photo_{uuid.uuid4().hex[:8]}.{ext}"
        filename = secure_filename(unique_name)
        
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        # --- PERUBAHAN UTAMA DI SINI ---
        # Kita panggil langsung (tanpa Threading) dan cek hasilnya
        if send_sync(save_path, filename):
            success_count += 1
        else:
            errors.append(filename)
            # Jika gagal, file temp mungkin perlu dihapus atau dibiarkan untuk debug
            # try: os.remove(save_path) 
            # except: pass

    # Logika Response ke Web
    if len(errors) > 0:
        # Jika ada yang gagal, kirim status Error (500) supaya JS menampilkan notif MERAH
        return jsonify({
            "status": "error", 
            "message": f"Gagal mengirim {len(errors)} file. Cek Server!",
            "failed_files": errors
        }), 500
        
    return jsonify({"status": "ok", "count": success_count})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": STATE["logs"]})

if __name__ == "__main__":
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        my_ip = s.getsockname()[0]
        s.close()
        print(f"\n🚀 ERNOBA PHOTOBOOTH WEB: http://{my_ip}:5000\n")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except:
        STATE["client"].stop()