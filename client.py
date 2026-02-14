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
# --- PERBAIKAN DI SINI ---
# Gabungkan parameter device_name dan secret dalam satu pemanggilan
STATE["client"] = BProto(
    device_name="Ernoba-Photobooth-Client", 
    secret="ernoba-root"
)
STATE["client"].start()

def add_log(msg, type="info"):
    t = time.strftime("%H:%M:%S")
    entry = {"time": t, "msg": msg, "type": type}
    STATE["logs"].insert(0, entry)
    if len(STATE["logs"]) > 50: STATE["logs"].pop()
    print(f"[{type.upper()}] {msg}")

# --- FUNGSI PENGIRIM (DIPERBARUI) ---
def send_sync(filepath, filename):
    """
    Mengirim file secara langsung dan mengembalikan True/False.
    Tidak ada Threading di sini.
    """
    target = STATE["target_ip"]
    if not target:
        add_log(f"Gagal: {filename} (Server belum diset!)", "error")
        return False

    add_log(f"Mengirim: {filename} -> {target}...", "info")
    
    # Proses Kirim (Program akan menunggu di sini sampai selesai/gagal)
    sukses = STATE["client"].send_file(target, filepath)
    
    if sukses:
        add_log(f"✅ Terkirim: {filename}", "success")
        try: os.remove(filepath)
        except: pass
        return True
    else:
        # Error detail sudah dicetak oleh bproto ke console
        add_log(f"❌ Gagal mengirim: {filename} (Cek koneksi/Firewall)", "error")
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