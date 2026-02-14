import os
import sys
import time
import socket
import logging
from flask import Flask, render_template

# Bisukan Log agar terminal bersih
log = logging.getLogger('werkzeug')
log.setLevel(logging.WARNING)

# Import Library BProto
try:
    from bproto import BProto
except ImportError:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from bproto import BProto

app = Flask(__name__, template_folder='templates', static_folder='static')

SAVE_DIR = os.path.join(os.getcwd(), "Hasil_Foto_Photobooth")
SECRET_KEY = "ernoba-root"
bproto_server = None

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def on_progress(name, pct, speed):
    if pct >= 100:
        print(f"\r[✔] Selesai: {name}                            ")
    elif int(pct) % 20 == 0:
        print(f"\r[...] Uploading {name}: {pct:.0f}%", end="")

def on_message(ip, content):
    print(f"\n[💬] {ip}: {content}")

def on_error(msg):
    # Abaikan error putus nyambung
    if "ConnectionClosed" not in str(msg):
        print(f"[X] {msg}")

@app.route('/')
def index():
    # Protokol kita kembalikan ke 'ws' (lebih ringan)
    return render_template('index.html', 
                           server_ip=get_local_ip(), 
                           ws_port=7102,
                           protocol='ws', 
                           secret_key=SECRET_KEY)

def main():
    global bproto_server
    if not os.path.exists(SAVE_DIR): os.makedirs(SAVE_DIR)
    
    my_ip = get_local_ip()
    print("\n" + "="*45)
    print(f"  🚀 ERNOBA SERVER (HTTP MODE - FAST)  ")
    print(f"  👉 URL HP: http://{my_ip}:5000")
    print("="*45 + "\n")

    # Jalankan BProto (Port 7002)
    bproto_server = BProto(device_name="Server", secret=SECRET_KEY, save_dir=SAVE_DIR, port=7002)
    bproto_server.events.on("error", on_error) 
    bproto_server.events.on("progress", on_progress)
    bproto_server.events.on("message", on_message)
    bproto_server.start()

    # Jalankan Flask HTTP Biasa
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        print("\n[!] Stopping...")
        bproto_server.stop()

if __name__ == "__main__":
    main()