// --- Global State ---
window.APP = {
    viewIndex: 1,
    serverIp: localStorage.getItem('ernoba_ip') || '',
    photos: [] // {id, blob, url}
};

document.addEventListener('DOMContentLoaded', () => {
    // Init Slide
    slide(1); 
    
    // Auto-connect if IP exists
    if(APP.serverIp) updateServerIp(APP.serverIp, true);

    // Gestures
    let touchX = 0;
    document.body.addEventListener('touchstart', e => touchX = e.changedTouches[0].screenX);
    document.body.addEventListener('touchend', e => {
        const diff = touchX - e.changedTouches[0].screenX;
        if(Math.abs(diff) > 60) {
            if(diff > 0 && APP.viewIndex < 2) slide(APP.viewIndex + 1);
            if(diff < 0 && APP.viewIndex > 0) slide(APP.viewIndex - 1);
        }
    });
});

function slide(idx) {
    APP.viewIndex = idx;
    document.getElementById('mainContainer').style.transform = `translateX(-${idx * 33.33}%)`;
}

function showToast(msg, type='info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    const icon = type === 'success' ? 'fa-check-circle' : (type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle');
    const color = type === 'success' ? '#2ecc71' : (type === 'error' ? '#ff4757' : '#4A90E2');
    
    el.innerHTML = `
        <i class="fas ${icon}" style="color:${color}"></i>
        <span style="font-size:0.9rem; font-weight:500;">${msg}</span>
    `;
    container.appendChild(el);
    setTimeout(() => { el.style.opacity='0'; setTimeout(()=>el.remove(), 300); }, 3000);
}

async function updateServerIp(ip, silent=false) {
    try {
        const res = await fetch('/api/set_server', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip })
        });
        const data = await res.json();
        
        if(data.status === 'ok') {
            APP.serverIp = ip;
            localStorage.setItem('ernoba_ip', ip);
            document.getElementById('connIcon').style.background = '#2ecc71';
            if(!silent) showToast(`Terhubung ke ${ip}`, 'success');
        } else {
            throw new Error(data.message);
        }
    } catch(e) {
        if(!silent) showToast('Gagal set IP: ' + e.message, 'error');
        document.getElementById('connIcon').style.background = '#ff4757';
    }
}