function renderGallery() {
    const grid = document.getElementById('galleryGrid');
    grid.innerHTML = '';
    
    // Update UI jumlah foto
    const count = APP.photos.length;
    document.getElementById('photoCount').innerText = `${count} Foto`;
    
    // Tampilkan pesan jika kosong
    if (count === 0) {
        grid.innerHTML = `
            <div style="grid-column: span 2; text-align:center; padding:40px; color:#aaa;">
                <i class="fas fa-camera" style="font-size:3rem; margin-bottom:10px;"></i><br>
                Belum ada foto
            </div>`;
        return;
    }

    // Render Loop
    APP.photos.slice().reverse().forEach(p => {
        const div = document.createElement('div');
        div.className = 'photo-card';
        // Tambahkan tombol Download dan Hapus
        div.innerHTML = `
            <img src="${p.url}" onclick="openPreview('${p.url}')">
            <div class="download-badge" onclick="downloadSingle(${p.id}, event)">
                <i class="fas fa-arrow-down"></i>
            </div>
            <div class="del-badge" onclick="deletePhoto(${p.id}, event)">
                <i class="fas fa-trash"></i>
            </div>
        `;
        grid.appendChild(div);
    });
}

// --- FITUR HAPUS ---
function deletePhoto(id, e) {
    if(e) e.stopPropagation();
    if(confirm('Hapus foto ini permanen?')) {
        // Hapus dari array
        APP.photos = APP.photos.filter(p => p.id !== id);
        renderGallery();
        showToast('Foto dihapus', 'info');
    }
}

function deleteAllPhotos() {
    if(APP.photos.length === 0) return;
    if(confirm(`Yakin hapus SEMUA (${APP.photos.length}) foto?`)) {
        APP.photos = [];
        renderGallery();
        showToast('Galeri dibersihkan', 'success');
    }
}

// --- FITUR DOWNLOAD KE HP ---
function downloadSingle(id, e) {
    if(e) e.stopPropagation();
    const photo = APP.photos.find(p => p.id === id);
    if (photo) {
        const a = document.createElement('a');
        a.href = photo.url;
        a.download = `ErnobaCam_${id}.jpg`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        showToast('Menyimpan ke galeri HP...', 'success');
    }
}

// Preview Modal Logic
function openPreview(url) {
    const modal = document.getElementById('previewModal');
    document.getElementById('previewImg').src = url;
    modal.style.display = 'flex';
}

function closePreview() {
    document.getElementById('previewModal').style.display = 'none';
}

// Upload Logic (Tetap sama, dirapikan)
async function uploadAllPhotos() {
    if(APP.photos.length === 0) return showToast('Galeri kosong', 'error');
    if(!APP.serverIp) {
        slide(1); 
        setTimeout(() => document.getElementById('settingsModal').style.display = 'flex', 500);
        return showToast('Setting IP Server dulu!', 'error');
    }

    const btn = document.getElementById('uploadBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mengirim...';
    btn.disabled = true;

    const formData = new FormData();
    APP.photos.forEach(p => formData.append('file', p.blob, `foto_${p.id}.jpg`));

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if(res.ok && data.status === 'ok') {
            showToast(`Sukses! ${data.count} foto terkirim.`, 'success');
            APP.photos = []; 
            renderGallery();
            slide(1);
        } else {
            throw new Error(data.error || 'Server menolak file');
        }
    } catch(e) {
        console.error(e);
        showToast(`Gagal: ${e.message}`, 'error');
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}