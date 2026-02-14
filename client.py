import os
import time
import uuid
import socket
from flask import Flask, render_template, jsonify, request
from werkzeug.utils import secure_filename

# Import library bproto
try:
    from bproto import BProto
except ImportError:
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

app = Flask(__name__, template_folder='templates')

# Konfigurasi Folder Temp
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

# --- INIT BPROTO ---
# PENTING: Kita set port=7003 untuk Client.
# Alasannya: Server.py menggunakan port 7002. Jika dijalankan di satu laptop
# yang sama, port akan bentrok. Client menggunakan port berbeda untuk
# mendengarkan (listening), tapi tetap bisa mengirim ke port 7002 milik server.
STATE["client"] = BProto(
    device_name="Ernoba-Client-Sender", 
    secret="ernoba-root",
    port=7003 
)
STATE["client"].start()

def add_log(msg, type="info"):
    t = time.strftime("%H:%M:%S")
    entry = {"time": t, "msg": msg, "type": type}
    STATE["logs"].insert(0, entry)
    if len(STATE["logs"]) > 50: STATE["logs"].pop()
    print(f"[{type.upper()}] {msg}")

# --- FUNGSI PENGIRIM (Sinkronus) ---
def send_sync(filepath, filename):
    target = STATE["target_ip"]
    if not target:
        add_log(f"Gagal: {filename} (Server belum diset!)", "error")
        return False

    add_log(f"Mengirim (Encrypted): {filename} -> {target}...", "info")
    
    # Proses Kirim (Otomatis dikompres & dienkripsi oleh library baru)
    try:
        sukses = STATE["client"].send_file(target, filepath)
        
        if sukses:
            add_log(f"✅ Terkirim: {filename}", "success")
            try: os.remove(filepath)
            except: pass
            return True
        else:
            add_log(f"❌ Gagal mengirim: {filename}", "error")
            return False
    except Exception as e:
        add_log(f"❌ Error System: {e}", "error")
        return False

# --- ROUTES FLASK ---
@app.route('/')
def index():
    # Pastikan Anda punya folder 'templates/index.html'
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    # Trigger scan UDP
    STATE["client"].scan()
    time.sleep(1.0) # Tunggu balasan
    return jsonify(STATE["client"].peers)

@app.route('/api/set_server', methods=['POST'])
def api_set_server():
    data = request.json
    ip = data.get('ip')
    
    if not ip or len(ip.split('.')) != 4:
        return jsonify({"status": "error", "message": "Format IP Salah"}), 400
        
    STATE["target_ip"] = ip
    
    # Inject Manual Peer (Port Default Server adalah 7002)
    # Jika server dikonfigurasi custom port, ini perlu disesuaikan
    STATE["client"].peers[ip] = {"name": "Manual-Server", "port": 7002} 
    
    add_log(f"🔗 Target Server di-lock: {ip}", "success")
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
        # Generate nama unik aman
        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        unique_name = f"photo_{uuid.uuid4().hex[:8]}.{ext}"
        filename = secure_filename(unique_name)
        
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        
        # Kirim
        if send_sync(save_path, filename):
            success_count += 1
        else:
            errors.append(filename)

    if len(errors) > 0:
        return jsonify({
            "status": "error", 
            "message": f"Gagal mengirim {len(errors)} file.",
            "failed_files": errors
        }), 500
        
    return jsonify({"status": "ok", "count": success_count})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": STATE["logs"]})

# Shutdown cleanup
import atexit
def cleanup():
    print("[Client] Stopping BProto...")
    STATE["client"].stop()

atexit.register(cleanup)

if __name__ == "__main__":
    try:
        # Cek IP Lokal untuk info
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        my_ip = s.getsockname()[0]
        s.close()
        
        print(f"\n🚀 ERNOBA CLIENT WEB: http://{my_ip}:5000")
        print(f"🚀 INTERNAL BPROTO   : Port 7003 (Agar tidak bentrok dengan server)")
        
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        print(f"Error: {e}")