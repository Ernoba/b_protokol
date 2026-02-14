import os
import json
import time
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, flash

app = Flask(__name__)
app.secret_key = 'rahasia_super_aman_ganti_ini' # Ganti dengan random string
UPLOAD_FOLDER = 'static/uploads'
DATA_FILE = 'data.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder uploads ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNGSI BANTUAN ---
def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        try:
            return json.load(f)
        except:
            return []

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- ROUTES AUTH ADMIN ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        # Simple hardcoded login
        if username == 'admin' and password == 'admin123':
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        else:
            flash('Username atau Password salah!', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

# --- ROUTES USER ---

# 1. HALAMAN TAMU & INSTRUKSI
# app.py

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        data_json = request.get_json()
        
        # Ambil nama dan bersihkan spasi di awal/akhir
        nama = data_json.get('nama', '').strip()
        alamat = data_json.get('alamat')
        kunci = data_json.get('kunci')
        
        db = load_data()

        # --- LOGIKA PENGECEKAN NAMA DUPLIKAT ---
        # Kita cek case-insensitive (huruf besar/kecil dianggap sama)
        # Contoh: "Budi" sama dengan "budi"
        nama_exists = any(user['nama'].lower() == nama.lower() for user in db)

        if nama_exists:
            return jsonify({
                "status": "error", 
                "msg": "Nama sudah terdaftar! Harap gunakan nama lain atau tambahkan inisial."
            })
        # ---------------------------------------

        new_entry = {
            "id": int(time.time()),
            "nama": nama,
            "alamat": alamat,
            "kunci": kunci, 
            "status": "pending",
            "folder": ""
        }
        db.append(new_entry)
        save_data(db)
        
        return jsonify({"status": "success", "msg": "Data tersimpan!"})
        
    return render_template('index.html')

@app.route('/help')
def help_page():
    return render_template('help.html')

# 2. HALAMAN ADMIN
@app.route('/admin')
def admin():
    if not session.get('admin_logged_in'):
        return redirect(url_for('login'))
        
    data = load_data()
    # Sortir: Pending di atas
    sorted_data = sorted(data, key=lambda x: x['status'] == 'approved')
    return render_template('admin.html', tamu=sorted_data)

# API untuk Auto Refresh Data di Admin
@app.route('/api/get_tamu')
def api_get_tamu():
    if not session.get('admin_logged_in'):
        return jsonify([])
    data = load_data()
    pending_only = [d for d in data if d['status'] == 'pending']
    return jsonify(pending_only)

@app.route('/approve/<int:id>')
def approve(id):
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    
    data = load_data()
    for d in data:
        if d['id'] == id:
            d['status'] = 'approved'
            folder_name = d['nama'].upper().replace(" ", "_")
            d['folder'] = folder_name
            
            path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
            if not os.path.exists(path):
                os.makedirs(path)
            break
            
    save_data(data)
    return redirect(url_for('admin'))

# 3. UPLOAD PAGE
@app.route('/upload_page')
def upload_page():
    if not session.get('admin_logged_in'): return redirect(url_for('login'))
    folders = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], f))]
    return render_template('upload.html', folders=folders)

@app.route('/upload_process/<folder_name>', methods=['POST'])
def upload_process(folder_name):
    if not session.get('admin_logged_in'): 
        return jsonify({'msg': 'Unauthorized'}), 401

    if 'files[]' not in request.files:
        return jsonify({'msg': 'No file part'}), 400
    
    files = request.files.getlist('files[]')
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    
    count = 0
    for file in files:
        if file.filename != '':
            file.save(os.path.join(save_path, file.filename))
            count += 1
            
    # Return JSON valid agar JS menganggap sukses
    return jsonify({'msg': 'Berhasil', 'count': count}), 200

# 4. GALLERY DENGAN KUNCI
@app.route('/gallery', methods=['GET', 'POST'])
def gallery():
    folder_found = None
    files = []
    locked = True
    error_msg = None
    
    # Ambil folder user
    search_name = request.args.get('cari', '').upper().replace(" ", "_")
    
    if search_name:
        # Cek apakah folder ada di database
        db = load_data()
        user_data = next((item for item in db if item["folder"] == search_name), None)
        
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], search_name)
        
        if user_data and os.path.exists(folder_path):
            folder_found = search_name
            
            # Cek Session (Apakah user sudah unlock folder ini?)
            session_key = f"unlocked_{search_name}"
            
            if session.get(session_key):
                locked = False
                files = os.listdir(folder_path)
            
            # Jika user submit password
            if request.method == 'POST':
                input_key = request.form.get('kunci_akses')
                if input_key == user_data['kunci']:
                    session[session_key] = True
                    locked = False
                    files = os.listdir(folder_path)
                else:
                    error_msg = "Kode akses salah!"

    return render_template('gallery.html', 
                           folder=folder_found, 
                           files=files, 
                           locked=locked, 
                           error=error_msg,
                           search_query=request.args.get('cari', ''))

if __name__ == '__main__':
    # host='0.0.0.0' artinya membuka akses ke semua IP publik di jaringan
    # port=5000 adalah port standar Flask (bisa diganti jika bentrok)
    app.run(host='0.0.0.0', port=5000, debug=True)