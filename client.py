import time
import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, jsonify, request
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Import library BProto
try:
    from bproto import BProto
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

app = Flask(__name__)

# --- GLOBAL STATE ---
STATE = {
    "bproto": None,
    "observer": None,
    "target_ip": None,
    "folder_path": None,
    "logs": []
}

# Inisialisasi BProto Client
client = BProto(device_name="Ernoba-Creative-Client", secret="ernoba-root")
client.start()
STATE["bproto"] = client

# --- LOGGING HELPER ---
def add_log(msg, type="info"):
    timestamp = time.strftime("%H:%M:%S")
    # Tipe: info, success, error, warning
    entry = {"time": timestamp, "msg": msg, "type": type}
    STATE["logs"].insert(0, entry)
    if len(STATE["logs"]) > 50: STATE["logs"].pop()
    print(f"[{timestamp}] {msg}")

# --- WATCHDOG HANDLER ---
class AutoMoveHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory: return

        filepath = event.src_path
        filename = os.path.basename(filepath)
        
        valid_ext = ('.jpg', '.jpeg', '.png', '.mp4', '.avi', '.mov', '.raw')
        if not filename.lower().endswith(valid_ext):
            return

        time.sleep(1) # Buffer write time
        
        target_ip = STATE["target_ip"]
        if not target_ip: return

        add_log(f"Mendeteksi file baru: {filename}...", "info")

        try:
            client.send_file(target_ip, filepath)
            add_log(f"Berhasil dikirim: {filename}", "success")
            try:
                os.remove(filepath)
                add_log(f"File lokal dibersihkan.", "warning")
            except Exception as e:
                add_log(f"Gagal hapus lokal: {e}", "error")

        except Exception as e:
            add_log(f"Gagal kirim {filename}: {e}", "error")

# --- FLASK ROUTES ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/scan')
def api_scan():
    client.scan()
    time.sleep(1)
    return jsonify(client.peers)

@app.route('/api/browse')
def api_browse():
    """Membuka Dialog Pilih Folder Native OS"""
    try:
        root = tk.Tk()
        root.withdraw() # Sembunyikan window utama tkinter
        root.attributes('-topmost', True) # Agar popup muncul di paling depan
        folder_selected = filedialog.askdirectory()
        root.destroy()
        return jsonify({"path": folder_selected})
    except Exception as e:
        return jsonify({"path": "", "error": str(e)})

@app.route('/api/start', methods=['POST'])
def api_start():
    data = request.json
    folder = data.get('folder')
    ip = data.get('target_ip')

    if not os.path.exists(folder):
        return jsonify({"status": "error", "message": "Folder tidak valid!"})

    STATE["target_ip"] = ip
    STATE["folder_path"] = folder

    if STATE["observer"]:
        STATE["observer"].stop()
        STATE["observer"].join()

    event_handler = AutoMoveHandler()
    observer = Observer()
    observer.schedule(event_handler, folder, recursive=False)
    observer.start()
    
    STATE["observer"] = observer
    add_log(f"Layanan dimulai pada folder: {os.path.basename(folder)}", "success")
    return jsonify({"status": "ok"})

@app.route('/api/stop')
def api_stop():
    if STATE["observer"]:
        STATE["observer"].stop()
        STATE["observer"].join()
        STATE["observer"] = None
        add_log("Layanan dihentikan.", "warning")
    return jsonify({"status": "ok"})

@app.route('/api/logs')
def api_logs():
    return jsonify({"logs": STATE["logs"]})

if __name__ == "__main__":
    try:
        print("Ernoba Creative Client Running on http://localhost:5000")
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        client.stop()
        if STATE["observer"]: STATE["observer"].stop()