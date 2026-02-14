import os
import json
from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
DATA_FILE = 'data.json'

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Pastikan folder uploads ada
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- FUNGSI BANTUAN JSON ---
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

# --- ROUTES ---

# 1. HALAMAN TAMU (Input Data)
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        nama = request.form['nama']
        alamat = request.form['alamat']
        
        data = load_data()
        # Tambah data baru dengan status pending
        new_entry = {
            "id": len(data) + 1,
            "nama": nama,
            "alamat": alamat,
            "status": "pending",
            "folder": ""
        }
        data.append(new_entry)
        save_data(data)
        
        return "Data terkirim! Silakan tunggu Admin."
    return render_template('index.html')

# 2. HALAMAN ADMIN (Cek & ACC)
@app.route('/admin')
def admin():
    data = load_data()
    # Hanya tampilkan yang pending
    pending_list = [d for d in data if d['status'] == 'pending']
    return render_template('admin.html', tamu=pending_list)

# Logic ACC (Buat Folder Asli)
@app.route('/approve/<int:id>')
def approve(id):
    data = load_data()
    for d in data:
        if d['id'] == id:
            d['status'] = 'approved'
            # Buat nama folder KAPITAL (ganti spasi dengan underscore)
            folder_name = d['nama'].upper().replace(" ", "_")
            d['folder'] = folder_name
            
            # Buat Folder Fisik di Server
            path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
            if not os.path.exists(path):
                os.makedirs(path)
            break
            
    save_data(data)
    return redirect(url_for('admin'))

# 3. HALAMAN UPLOAD (Drag & Drop Admin)
@app.route('/upload_page')
def upload_page():
    # Ambil daftar folder asli yang ada di static/uploads
    folders = [f for f in os.listdir(app.config['UPLOAD_FOLDER']) if os.path.isdir(os.path.join(app.config['UPLOAD_FOLDER'], f))]
    return render_template('upload.html', folders=folders)

# Logic Terima File Upload
@app.route('/upload_process/<folder_name>', methods=['POST'])
def upload_process(folder_name):
    if 'files[]' not in request.files:
        return jsonify({'msg': 'No file'})
    
    files = request.files.getlist('files[]')
    save_path = os.path.join(app.config['UPLOAD_FOLDER'], folder_name)
    
    for file in files:
        if file.filename != '':
            file.save(os.path.join(save_path, file.filename))
            
    return jsonify({'msg': 'Berhasil Upload'})

# 4. HALAMAN GALLERY (User Cari Foto)
@app.route('/gallery')
def gallery():
    query = request.args.get('cari', '').upper().replace(" ", "_")
    folder_found = None
    files = []

    if query:
        # Cek apakah folder fisik ada
        folder_path = os.path.join(app.config['UPLOAD_FOLDER'], query)
        if os.path.exists(folder_path):
            folder_found = query
            # List semua file gambar di folder itu
            files = os.listdir(folder_path)

    return render_template('gallery.html', folder=folder_found, files=files)

if __name__ == '__main__':
    app.run(debug=True)