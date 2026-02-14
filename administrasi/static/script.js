// --- ANIMASI KAMERA ---
function playCameraAnimation() {
    const shutter = document.getElementById('camera-shutter');
    shutter.style.display = 'flex'; // Tampilkan overlay
    
    // Suara shutter (opsional, perlu file mp3)
    // const audio = new Audio('/static/shutter.mp3');
    // audio.play();

    // Tunggu animasi selesai (1.2 detik sesuai CSS)
    setTimeout(() => {
        // Redirect atau Refresh
        window.location.href = "/?status=success"; 
    }, 1200);
}

// Cek URL params untuk pesan sukses setelah redirect
const urlParams = new URLSearchParams(window.location.search);
if (urlParams.get('status') === 'success') {
    // Tampilkan pesan "Silakan ambil foto"
    setTimeout(() => {
        alert("Data Tersimpan! Silakan bersiap untuk AMBIL FOTO! 📸");
    }, 500);
}


// --- TOAST & DRAG DROP ---
document.addEventListener('DOMContentLoaded', () => {
    if (!document.getElementById('toast-container')) {
        const container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
});

function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = 'toast';
    const icon = type === 'success' ? '<i class="fas fa-check-circle"></i>' : '<i class="fas fa-exclamation-circle"></i>';
    toast.innerHTML = `${icon} <span>${message}</span>`;
    toast.style.borderLeftColor = type === 'success' ? '#00f260' : '#ff0080';
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function dragOverHandler(ev) {
    ev.preventDefault();
    ev.currentTarget.classList.add('dragover');
}

function dragLeaveHandler(ev) {
    ev.currentTarget.classList.remove('dragover');
}

function dropHandler(ev, folderName) {
    ev.preventDefault();
    ev.currentTarget.classList.remove('dragover');
    
    const originalContent = ev.currentTarget.innerHTML;
    ev.currentTarget.innerHTML = '<i class="fas fa-spinner fa-spin"></i><p>Mengupload...</p>';

    var files = ev.dataTransfer.files;
    var formData = new FormData();
    
    for (var i = 0; i < files.length; i++) {
        formData.append('files[]', files[i]);
    }

    fetch('/upload_process/' + folderName, {
        method: 'POST',
        body: formData
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // PERBAIKAN: Cek isi pesan dari server
        showToast(`Berhasil upload ${data.count} foto!`, 'success');
        ev.currentTarget.innerHTML = '<i class="fas fa-check" style="color:#00f260"></i><p>Selesai!</p>';
        setTimeout(() => ev.currentTarget.innerHTML = originalContent, 2000);
    })
    .catch(error => {
        console.error('Error:', error);
        showToast('Gagal mengupload foto. Coba lagi.', 'error');
        ev.currentTarget.innerHTML = originalContent;
    });
}