import os
import io
import string
import shutil
import time
from flask import Flask, render_template, request, jsonify, send_file
from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ImageDraw

app = Flask(__name__)

# --- KONFIGURASI ---
CACHE = {
    "input_folder": "",
    "current_file": None,
    "files_in_folder": []
}

WM_FOLDER = 'watermarks'
if not os.path.exists(WM_FOLDER):
    os.makedirs(WM_FOLDER)

# --- IMAGE LOGIC ---
def apply_adjustments(img, config):
    img = img.convert("RGBA")
    
    # 1. ROTATION (Putar dulu sebelum crop/color)
    rotate = float(config.get('rotate', 0))
    if rotate != 0:
        # expand=False agar ukuran canvas tetap (crop bagian luar)
        # resample=Image.BICUBIC agar hasil putar halus
        img = img.rotate(-rotate, resample=Image.BICUBIC, expand=False)

    # 2. BLACK & WHITE
    if config.get('bw', 'false') == 'true':
        img = ImageOps.grayscale(img).convert("RGBA")

    # 3. EXPOSURE
    exposure = float(config.get('exposure', 0))
    if exposure != 0:
        factor = 2 ** exposure
        img = ImageEnhance.Brightness(img).enhance(factor)

    # 4. CONTRAST
    contrast = float(config.get('contrast', 1.0))
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)

    # 5. SATURATION
    saturation = float(config.get('saturation', 1.0))
    if saturation != 1.0:
        img = ImageEnhance.Color(img).enhance(saturation)

    # 6. GAMMA
    gamma = float(config.get('gamma', 1.0))
    if gamma != 1.0 and gamma > 0:
        invGamma = 1.0 / gamma
        table = [int(((i / 255.0) ** invGamma) * 255) for i in range(256)] * 3
        r, g, b, a = img.split()
        r = r.point(table[:256])
        g = g.point(table[:256])
        b = b.point(table[:256])
        img = Image.merge("RGBA", (r, g, b, a))

    # 7. TEMPERATURE / TINT
    temp = float(config.get('temperature', 0))
    tint = float(config.get('tint', 0))
    if temp != 0 or tint != 0:
        r, g, b, a = img.split()
        r = r.point(lambda i: i + temp)
        b = b.point(lambda i: i - temp)
        g = g.point(lambda i: i + tint)
        img = Image.merge("RGBA", (r, g, b, a))

    # 8. SHARPNESS (Ketajaman)
    sharpness = float(config.get('sharpness', 1.0))
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)

    # 9. BLUR (Buram/Soft)
    blur = float(config.get('blur', 0))
    if blur > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur))

    # 10. VIGNETTE (Sisi Gelap)
    vignette_strength = float(config.get('vignette', 0))
    if vignette_strength > 0:
        # Buat layer hitam
        black = Image.new("RGBA", img.size, (0, 0, 0, 255))
        
        # Buat mask gradient radial
        # Logika: Putih di tengah (transparan), Hitam di pinggir (gelap)
        # Kita pakai 'L' mode untuk mask
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        
        # Gambar lingkaran putih di tengah
        w, h = img.size
        # Scaling ellipse agar oval mengikuti bentuk foto
        draw.ellipse((int(-w*0.2), int(-h*0.2), int(w*1.2), int(h*1.2)), fill=255)
        
        # Blur mask-nya agar gradasi halus (semakin besar strength, semakin blur 'masuk' ke dalam)
        # Rumus radius blur disesuaikan dengan resolusi gambar
        blur_radius = (w + h) / 2 * (0.1 + (vignette_strength/200.0)) 
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        
        # Gabungkan: Tempel layer hitam ke gambar asli menggunakan mask (inverted)
        # Karena mask putih = transparan (di logika paste), kita perlu invert atau sesuaikan
        # Pillow composite: image1, image2, mask. 
        # Kita ingin mempertahankan 'img' di area putih mask, dan 'black' di area hitam mask?
        # Logic composite: output = image2 * (1 - mask) + image1 * mask
        img = Image.composite(img, black, mask)

    return img

def scan_folder_content(folder_path):
    """Fungsi helper untuk scan real-time"""
    if not folder_path or not os.path.exists(folder_path):
        return []
    
    exts = ('.jpg', '.jpeg', '.png', '.webp', '.bmp')
    # Scan file secara real-time
    try:
        files = [f.name for f in os.scandir(folder_path) if f.is_file() and f.name.lower().endswith(exts)]
        files.sort()
        return files
    except Exception as e:
        print(f"Error scanning: {e}")
        return []

def apply_watermark(img, config):
    wm_filename = config.get('wm_filename')
    if not wm_filename: return img
    
    wm_path = os.path.join(WM_FOLDER, wm_filename)
    if not os.path.exists(wm_path): return img
    
    wm = Image.open(wm_path).convert("RGBA")
    
    opacity = int(config.get('wm_opacity', 100))
    if opacity < 100:
        alpha = wm.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity / 100.0)
        wm.putalpha(alpha)

    # Scale 100%
    scale = int(config.get('wm_scale', 20)) / 100.0
    target_w = int(img.width * scale)
    if target_w < 10: target_w = 10
    
    aspect = wm.width / wm.height
    target_h = int(target_w / aspect)
    wm = wm.resize((target_w, target_h), Image.Resampling.LANCZOS)

    pos = config.get('wm_position', 'se')
    
    # Offset Calculation
    off_x_val = int(config.get('wm_off_x', 0))
    off_y_val = int(config.get('wm_off_y', 0))
    
    margin_x = int(img.width * (off_x_val / 1000.0))
    margin_y = int(img.height * (off_y_val / 1000.0))

    iw, ih = img.size
    ww, wh = wm.size
    x, y = 0, 0

    if 'w' in pos: x = 0
    elif 'e' in pos: x = iw - ww
    else: x = (iw - ww) // 2

    if 'n' in pos: y = 0
    elif 's' in pos: y = ih - wh
    else: y = (ih - wh) // 2

    if 'w' in pos: x += margin_x
    elif 'e' in pos: x -= margin_x
    else: x += margin_x 

    if 'n' in pos: y += margin_y
    elif 's' in pos: y -= margin_y
    else: y += margin_y

    dest = img.copy()
    dest.paste(wm, (int(x), int(y)), wm)
    return dest

# --- ROUTES SAMA SEPERTI SEBELUMNYA ---
# (Pastikan copy semua route dari code sebelumnya di sini)
# Agar aman, saya tulis ulang route utamanya:

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/list-dirs', methods=['POST'])
def list_dirs():
    path = request.json.get('path', '')
    if not path:
        drives = [f"{d}:\\" for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]
        return jsonify({'items': drives, 'type': 'drives'})
    try:
        items = [d.name for d in os.scandir(path) if d.is_dir()]
        return jsonify({'items': sorted(items), 'parent': os.path.dirname(path), 'current': path})
    except:
        return jsonify({'items': [], 'parent': '', 'error': True})

@app.route('/api/scan-images', methods=['POST'])
def scan_images():
    req_path = request.json.get('path')
    # Prioritas: Path dari Client > Path di Cache
    target_path = req_path if req_path else CACHE.get('input_folder')

    if target_path and os.path.isdir(target_path):
        CACHE['input_folder'] = target_path
        files = scan_folder_content(target_path)
        CACHE['files_in_folder'] = files
        
        # Logika seleksi file yang lebih pintar
        if files:
            # Jika current_file kosong atau tidak ada di list baru, pilih yang pertama
            if not CACHE['current_file'] or CACHE['current_file'] not in files:
                CACHE['current_file'] = files[0]
        else:
            CACHE['current_file'] = None

        return jsonify({
            'status': 'success', 
            'files': files, 
            'current_folder': target_path,
            'current_file': CACHE['current_file']
        })
    
    return jsonify({'status': 'error', 'msg': 'Folder not found'})

@app.route('/api/set-current', methods=['POST'])
def set_current():
    filename = request.json.get('filename')
    # Validasi sederhana, izinkan set meskipun file baru masuk belum ter-cache sempurna
    if filename:
        CACHE['current_file'] = filename
        return jsonify({'status': 'ok'})
    return jsonify({'status': 'fail'})

@app.route('/api/get-thumbnail')
def get_thumbnail():
    filename = request.args.get('file')
    if CACHE['input_folder'] and filename:
        path = os.path.join(CACHE['input_folder'], filename)
        if os.path.exists(path):
            return send_file(path)
    return "", 404

@app.route('/api/wm-list')
def wm_list():
    if not os.path.exists(WM_FOLDER): return jsonify([])
    files = [f for f in os.listdir(WM_FOLDER) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    return jsonify(sorted(files))

@app.route('/api/wm-upload', methods=['POST'])
def wm_upload():
    if 'watermark' in request.files:
        f = request.files['watermark']
        if f.filename:
            save_path = os.path.join(WM_FOLDER, f.filename)
            f.save(save_path)
            return jsonify({'status': 'ok', 'filename': f.filename})
    return jsonify({'status': 'error'})

@app.route('/api/wm-image/<path:filename>')
def wm_serve(filename):
    return send_file(os.path.join(WM_FOLDER, filename))

@app.route('/preview-live', methods=['POST'])
def preview_live():
    config = request.json
    filename = CACHE.get('current_file')
    
    # Fail-safe: Jika tidak ada file terpilih tapi folder ada isinya, pilih satu
    if not filename and CACHE['files_in_folder']:
        filename = CACHE['files_in_folder'][0]
        CACHE['current_file'] = filename

    if not filename: return "No Image", 404
    
    try:
        path = os.path.join(CACHE['input_folder'], filename)
        if not os.path.exists(path): return "File missing", 404

        # PERBAIKAN: Gunakan 'with' agar file langsung ditutup setelah dibaca
        with Image.open(path) as img:
            img.thumbnail((1000, 1000)) 
            img = apply_adjustments(img, config)
            img = apply_watermark(img, config)
            img = img.convert("RGB")
            
            img_io = io.BytesIO()
            img.save(img_io, 'JPEG', quality=85)
            img_io.seek(0)
            
        return send_file(img_io, mimetype='image/jpeg')
    except Exception as e:
        print(f"Preview Error: {e}")
        return str(e), 500

@app.route('/api/check-updates', methods=['POST'])
def check_updates():
    path = CACHE.get('input_folder')
    
    # Jika path kosong (server restart), coba minta client kirim ulang (opsional)
    # Tapi di sini kita return false agar client tidak error
    if not path or not os.path.isdir(path):
        return jsonify({'status': 'ok', 'files': [], 'changed': False})
    
    current_files = scan_folder_content(path)
    cached_files = CACHE.get('files_in_folder', [])
    
    if current_files != cached_files:
        CACHE['files_in_folder'] = current_files
        
        # Auto-switch logika
        if CACHE['current_file'] not in current_files:
            CACHE['current_file'] = current_files[0] if current_files else None
            
        return jsonify({
            'status': 'ok', 
            'changed': True, 
            'files': current_files,
            'current_file': CACHE['current_file']
        })
    
    return jsonify({'status': 'ok', 'changed': False})

@app.route('/process-batch', methods=['POST'])
def process_batch():
    data = request.json
    out_folder = data.get('output_folder')
    config = data.get('config')
    mode = data.get('mode', 'all')
    delete_source = data.get('delete_source', False)
    fmt = data.get('format', 'JPEG')
    quality = int(data.get('quality', 90))
    resize_w = int(data.get('resize_w', 0))
    
    if not CACHE['input_folder']: return jsonify({'status': 'error', 'msg': 'No input folder'})
    if not os.path.exists(out_folder): os.makedirs(out_folder)
    
    target_files = [CACHE['current_file']] if mode == 'current' and CACHE['current_file'] else CACHE['files_in_folder']
    
    success = 0
    errors = 0
    
    for fname in target_files:
        try:
            in_path = os.path.join(CACHE['input_folder'], fname)
            name_part = os.path.splitext(fname)[0]
            ext_map = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp'}
            out_fname = name_part + ext_map.get(fmt, '.jpg')
            out_path = os.path.join(out_folder, out_fname)
            
            # PERBAIKAN: Gunakan 'with' agar file aman dihapus di Windows
            with Image.open(in_path) as img:
                if resize_w > 0 and img.width > resize_w:
                    ratio = resize_w / float(img.width)
                    h = int(img.height * ratio)
                    img = img.resize((resize_w, h), Image.Resampling.LANCZOS)
                    
                img = apply_adjustments(img, config)
                img = apply_watermark(img, config)
                
                if fmt == 'JPEG':
                    img = img.convert("RGB")
                    img.save(out_path, quality=quality, subsampling=0)
                elif fmt == 'PNG':
                    img.save(out_path, compress_level=int((100-quality)/10) if quality < 100 else 0) 
                elif fmt == 'WEBP':
                    img.save(out_path, quality=quality, method=6)
            
            # File sudah ditutup di sini, aman untuk dihapus
            success += 1
            if delete_source and os.path.abspath(in_path) != os.path.abspath(out_path):
                os.remove(in_path)

        except Exception as e:
            print(f"Error {fname}: {e}")
            errors += 1
            
    if delete_source:
        path = CACHE.get('input_folder')
        remaining_files = scan_folder_content(path)
        CACHE['files_in_folder'] = remaining_files
        
        if not remaining_files:
            CACHE['current_file'] = None
        elif CACHE['current_file'] not in remaining_files:
            CACHE['current_file'] = remaining_files[0]

    return jsonify({
        'status': 'success', 
        'processed': success, 
        'errors': errors,
        'remaining_files': CACHE['files_in_folder']
    })

if __name__ == '__main__':
    # TAMBAHAN: use_reloader=False mencegah server restart saat file berubah
    app.run(debug=True, use_reloader=False, port=3300)