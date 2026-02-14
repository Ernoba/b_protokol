function renderGallery() {
    const grid = document.getElementById('galleryGrid');
    grid.innerHTML = '';
    document.getElementById('photoCount').innerText = `${APP.photos.length} Foto`;
    
    APP.photos.slice().reverse().forEach(p => {
        const div = document.createElement('div');
        div.className = 'photo-card';
        div.innerHTML = `
            <img src="${p.url}" onclick="openPreview('${p.url}')">
            <div class="del-badge" onclick="deletePhoto(${p.id}, event)">✕</div>
        `;
        grid.appendChild(div);
    });
}

function deletePhoto(id, e) {
    e.stopPropagation();
    if(confirm('Hapus foto ini?')) {
        APP.photos = APP.photos.filter(p => p.id !== id);
        renderGallery();
    }
}

function openPreview(url) {
    document.getElementById('previewImg').src = url;
    document.getElementById('previewModal').style.display = 'flex';
}

function closePreview() {
    document.getElementById('previewModal').style.display = 'none';
}

// --- LOGIKA UPLOAD YANG AMAN ---
async function uploadAllPhotos() {
    if(APP.photos.length === 0) return showToast('Galeri kosong', 'error');
    if(!APP.serverIp) {
        slide(1); // Balik ke kamera
        setTimeout(() => document.getElementById('settingsModal').style.display = 'flex', 500);
        return showToast('Setting IP Server dulu!', 'error');
    }

    const btn = document.getElementById('uploadBtn');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Mengirim...';
    btn.disabled = true;

    // Kita kirim satu per satu agar bisa handle error per file
    // Atau kirim bulk (seperti sekarang) tapi handle response dengan teliti
    
    const formData = new FormData();
    APP.photos.forEach(p => formData.append('file', p.blob, `foto_${p.id}.jpg`));

    try {
        const res = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await res.json();

        if(res.ok && data.status === 'ok') {
            showToast(`Sukses! ${data.count} foto terkirim.`, 'success');
            APP.photos = []; // BARU DIHAPUS SETELAH SUKSES
            renderGallery();
            slide(1);
        } else {
            // Jika server error (misal 500 atau 400), JANGAN HAPUS FOTO
            throw new Error(data.error || 'Server menolak file');
        }
    } catch(e) {
        console.error(e);
        showToast(`Gagal: ${e.message}`, 'error');
        // Foto tetap ada di galeri, user bisa coba lagi
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}