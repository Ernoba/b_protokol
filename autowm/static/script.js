/* --- GLOBAL STATE --- */
let state = {
    explorerMode: '',
    currentPath: '',
    selectedPos: 'se',
    scale: 1,
    panning: false,
    pointX: 0,
    pointY: 0,
    startX: 0,
    startY: 0,
    monitorInterval: null, // Untuk menyimpan timer monitoring
    lastFolderHash: ''     // Untuk menyimpan sidik jari folder
};

let debounceTimer;

/* --- DOM ELEMENTS --- */
const els = {
    mainArea: document.getElementById('mainArea'),
    imgWrapper: document.getElementById('imageWrapper'),
    previewImg: document.getElementById('preview-img'),
    zoomLevel: document.getElementById('zoom-level'),
    inputPath: document.getElementById('inputPath'),
    outputPath: document.getElementById('outputPath'),
    emptyState: document.getElementById('emptyState')
};

// Initialization
document.addEventListener('DOMContentLoaded', () => {
    refreshWmList();
    setupEventListeners();
});

function setupEventListeners() {
    // Parameter Inputs
    document.querySelectorAll('.param').forEach(el => {
        el.addEventListener('input', (e) => {
            const label = document.getElementById('val_' + e.target.id);
            if(label) label.innerText = e.target.value;
            triggerPreview();
        });
    });

    // Checkboxes
    document.querySelectorAll('.param-check').forEach(el => {
        el.addEventListener('change', triggerPreview);
    });

    // Mouse Events for Pan/Zoom
    els.mainArea.addEventListener('wheel', handleZoom);
    els.mainArea.addEventListener('mousedown', startPan);
    window.addEventListener('mouseup', endPan);
    window.addEventListener('mousemove', handlePan);
}

/* --- PREVIEW LOGIC --- */
function triggerPreview() {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
        if(!els.previewImg.src || els.previewImg.style.display === 'none') return;
        
        const config = getConfig();
        try {
            const res = await fetch('/preview-live', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'}, 
                body: JSON.stringify(config)
            });
            if(res.ok) {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                els.previewImg.onload = () => URL.revokeObjectURL(els.previewImg.src); // cleanup memory
                els.previewImg.src = url;
            }
        } catch(e) { console.error("Preview failed", e); }
    }, 100); 
}

function getConfig() {
    const config = { 
        wm_position: state.selectedPos,
        wm_filename: document.getElementById('wm_filename').value 
    };
    document.querySelectorAll('.param').forEach(el => config[el.id] = el.value);
    document.querySelectorAll('.param-check').forEach(el => config[el.id] = el.checked ? 'true' : 'false');
    return config;
}

function resetParams() {
    // Set default values
    const defaults = {
        exposure: 0, contrast: 1.0, saturation: 1.0, temperature: 0
    };
    
    for (const [key, val] of Object.entries(defaults)) {
        const el = document.getElementById(key);
        if(el) {
            el.value = val;
            const label = document.getElementById('val_' + key);
            if(label) label.innerText = val;
        }
    }
    triggerPreview();
}

/* --- ZOOM & PAN LOGIC (Improved) --- */
function updateTransform() {
    els.imgWrapper.style.transform = `translate(${state.pointX}px, ${state.pointY}px) scale(${state.scale})`;
    els.zoomLevel.innerText = Math.round(state.scale * 100) + "%";
}

function handleZoom(e) {
    e.preventDefault();
    if(els.previewImg.style.display === 'none') return;

    const rect = els.mainArea.getBoundingClientRect();
    const xs = (e.clientX - rect.left - state.pointX) / state.scale;
    const ys = (e.clientY - rect.top - state.pointY) / state.scale;
    const delta = -e.deltaY;

    const oldScale = state.scale;
    state.scale *= (delta > 0) ? 1.1 : 0.9;
    
    // Limits
    if(state.scale < 0.1) state.scale = 0.1;
    if(state.scale > 8) state.scale = 8;

    state.pointX = e.clientX - rect.left - xs * state.scale;
    state.pointY = e.clientY - rect.top - ys * state.scale;

    updateTransform();
}

function startPan(e) {
    e.preventDefault();
    state.startX = e.clientX - state.pointX;
    state.startY = e.clientY - state.pointY;
    state.panning = true;
    els.mainArea.style.cursor = "grabbing";
}

function endPan() {
    state.panning = false;
    els.mainArea.style.cursor = "default";
}

function handlePan(e) {
    if (!state.panning) return;
    e.preventDefault();
    state.pointX = e.clientX - state.startX;
    state.pointY = e.clientY - state.startY;
    updateTransform();
}

function resetView() {
    state.scale = 1;
    state.pointX = 0;
    state.pointY = 0;
    updateTransform();
}

function zoomIn() {
    state.scale *= 1.2;
    updateTransform();
}

function zoomOut() {
    state.scale /= 1.2;
    updateTransform();
}

/* --- FILE EXPLORER & GALLERY --- */
function openExplorer(mode) {
    state.explorerMode = mode;
    document.getElementById('explorer-modal').style.display = 'flex';
    loadDir(state.currentPath || '');
}

async function loadDir(path) {
    state.currentPath = path;
    const list = document.getElementById('file-list');
    list.innerHTML = '<div style="padding:10px;">Loading...</div>';
    
    try {
        const res = await fetch('/api/list-dirs', {
            method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({path})
        });
        const data = await res.json();
        
        list.innerHTML = '';
        
        // Up Button
        if(data.parent !== '') {
            const row = document.createElement('div');
            row.className = 'file-row';
            row.innerHTML = '<span>⬆️ ..</span>';
            row.onclick = () => loadDir(data.parent);
            list.appendChild(row);
        }

        data.items.forEach(d => {
            const row = document.createElement('div');
            row.className = 'file-row folder';
            row.innerHTML = `<span>📁</span> <span>${d}</span>`;
            let next = path ? (path.endsWith('\\') || path.endsWith('/') ? path + d : path + '\\' + d) : d;
            row.onclick = () => loadDir(next);
            list.appendChild(row);
        });
    } catch(e) {
        list.innerHTML = '<div style="color:red; padding:10px;">Error reading folder</div>';
    }
}

function selectFolder() {
    if(state.explorerMode === 'input') {
        els.inputPath.value = state.currentPath;
        loadGallery(state.currentPath);
    } else {
        els.outputPath.value = state.currentPath;
    }
    closeModal('explorer-modal');
}

async function loadGallery(path) {
    if(!path) return;
    
    // --- TAMBAHAN: Mulai memantau folder ini ---
    startMonitoring(path); 
    // ------------------------------------------

    const grid = document.getElementById('gallery-list');
    grid.innerHTML = '<p style="padding:10px; color:#888;">Scanning...</p>';
    
    const res = await fetch('/api/scan-images', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({path})
    });
    const data = await res.json();
    
    grid.innerHTML = '';
    // Update jumlah file
    document.getElementById('file-count').innerText = data.files ? data.files.length : 0; // Pastikan Anda punya elemen dengan ID 'file-count' di HTML, atau hapus baris ini jika error.

    if(data.status === 'error' || !data.files || data.files.length === 0) {
        grid.innerHTML = '<p style="padding:10px; color:#888;">No images found.</p>';
        showEmptyState(true);
        return;
    }
    
    showEmptyState(false);
    data.files.forEach((f, idx) => {
        const thumb = document.createElement('div');
        thumb.className = 'thumb';
        // Hapus class 'active' default di sini, kita handle nanti
        thumb.innerHTML = `<img src="/api/get-thumbnail?file=${encodeURIComponent(f)}" loading="lazy">`;
        thumb.onclick = () => changeActiveImage(f, thumb);
        
        // Simpan nama file di atribut data agar mudah dicari nanti
        thumb.dataset.filename = f; 
        
        grid.appendChild(thumb);
    });
    
    // Auto load first image (Standard behavior)
    if(grid.children.length > 0) {
        changeActiveImage(data.files[0], grid.children[0]);
    }
}

function showEmptyState(show) {
    if(show) {
        els.emptyState.classList.add('visible');
        els.imgWrapper.style.display = 'none';
    } else {
        els.emptyState.classList.remove('visible');
        els.imgWrapper.style.display = 'flex';
    }
}

async function changeActiveImage(filename, el) {
    document.querySelectorAll('.thumb').forEach(t => t.classList.remove('active'));
    if(el) el.classList.add('active');
    
    await fetch('/api/set-current', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({filename})
    });
    
    resetView(); // Reset zoom
    triggerPreview();
}

/* --- WATERMARK --- */
async function refreshWmList() {
    const res = await fetch('/api/wm-list');
    const files = await res.json();
    const container = document.getElementById('wm-list-container');
    container.innerHTML = '';
    
    files.forEach((f, idx) => {
        const div = document.createElement('div');
        div.className = 'wm-item';
        div.onclick = () => selectWm(f, div);
        div.innerHTML = `<img src="/api/wm-image/${f}">`;
        container.appendChild(div);
        
        // Auto select first if none selected
        if(idx === 0 && !document.getElementById('wm_filename').value) selectWm(f, div);
    });
}

function selectWm(filename, el) {
    document.getElementById('wm_filename').value = filename;
    document.querySelectorAll('.wm-item').forEach(d => d.classList.remove('active'));
    el.classList.add('active');
    triggerPreview();
}

async function uploadWm() {
    const fileInput = document.getElementById('wmFile');
    if(fileInput.files.length === 0) return;
    
    const formData = new FormData();
    formData.append('watermark', fileInput.files[0]);
    
    const res = await fetch('/api/wm-upload', { method: 'POST', body: formData });
    const data = await res.json();
    
    if(data.status === 'ok') {
        await refreshWmList();
    } else {
        alert('Upload failed');
    }
}

function setPos(pos, el) {
    document.querySelectorAll('.pos-cell').forEach(c => c.classList.remove('active'));
    el.classList.add('active');
    state.selectedPos = pos;
    triggerPreview();
}

/* --- MODALS & PROCESS --- */
function closeModal(id) { document.getElementById(id).style.display = 'none'; }
function showProcessModal() {
    if(!els.inputPath.value || !els.outputPath.value) return alert('Please select Input and Output folders first!');
    document.getElementById('process-modal').style.display = 'flex';
}

async function startProcess() {
    const btn = document.getElementById('btn-start-process');
    const originalText = btn.innerText;
    btn.innerText = 'Processing...'; 
    btn.disabled = true;
    
    const config = getConfig();
    const mode = document.querySelector('input[name="proc_mode"]:checked').value;
    const deleteSource = document.getElementById('chk_delete').checked;
    const payload = {
        output_folder: els.outputPath.value,
        config: config,
        mode: mode,
        delete_source: deleteSource,
        format: document.getElementById('export_fmt').value,
        quality: document.getElementById('export_qual').value,
        resize_w: document.getElementById('export_resize').value
    };

    try {
        const res = await fetch('/process-batch', {
            method: 'POST', headers: {'Content-Type':'application/json'},
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        alert(`Process Complete!\n\n✅ Success: ${data.processed}\n❌ Errors: ${data.errors}`);
        closeModal('process-modal');
        if(deleteSource) loadGallery(els.inputPath.value);
    } catch(e) { 
        alert('Error communicating with server'); 
    } finally { 
        btn.innerText = originalText; 
        btn.disabled = false; 
    }
}

/* --- REAL-TIME FOLDER MONITORING --- */

function startMonitoring(path) {
    // 1. Hentikan interval lama jika ada (supaya tidak numpuk)
    if (state.monitorInterval) {
        clearInterval(state.monitorInterval);
    }

    // 2. Reset hash awal
    state.lastFolderHash = '';

    // 3. Cek status awal (First Run) untuk simpan hash saat ini
    fetch('/api/check-updates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: path }) // Kirim path folder aktif (ubah backend jika perlu support body)
        // CATAAN: Di backend python sebelumnya kita pakai CACHE['input_folder'], 
        // jadi tidak kirim body pun tidak apa-apa jika backend mengambil dari CACHE.
        // Tapi agar aman, pastikan backend Anda konsisten.
    })
    .then(r => r.json())
    .then(data => {
        if(data.status === 'ok') state.lastFolderHash = data.hash;
    });

    // 4. Mulai Interval setiap 2 detik
    state.monitorInterval = setInterval(() => {
        checkForUpdates(path);
    }, 2000);
}

async function checkForUpdates(path) {
    try {
        // Panggil API check-updates (Pastikan route ini sudah ada di Python)
        const res = await fetch('/api/check-updates', { method: 'POST' });
        const data = await res.json();

        if (data.status === 'ok') {
            // Jika hash server beda dengan hash terakhir di browser
            if (state.lastFolderHash && data.hash !== state.lastFolderHash) {
                console.log("New content detected!");
                state.lastFolderHash = data.hash; // Update hash
                await refreshGalleryAndSelectNewest(path); // Reload UI
            }
        }
    } catch (e) {
        console.error("Monitoring skipped:", e);
    }
}

async function refreshGalleryAndSelectNewest(path) {
    // 1. Scan ulang folder
    const res = await fetch('/api/scan-images', {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({path})
    });
    const data = await res.json();

    if(data.status !== 'success' || !data.files) return;

    const grid = document.getElementById('gallery-list');
    
    // Simpan file yang sedang aktif sekarang
    const currentActiveFile = state.currentPath ? state.currentPath.split(/[\\/]/).pop() : null;

    // 2. Render ulang Grid (Sama seperti loadGallery tapi tanpa loading text agar smooth)
    grid.innerHTML = '';
    // Update count jika ada elemennya
    if(document.getElementById('file-count')) document.getElementById('file-count').innerText = data.files.length;

    data.files.forEach((f) => {
        const thumb = document.createElement('div');
        thumb.className = 'thumb';
        thumb.dataset.filename = f;
        thumb.innerHTML = `<img src="/api/get-thumbnail?file=${encodeURIComponent(f)}" loading="lazy">`;
        thumb.onclick = () => changeActiveImage(f, thumb);
        grid.appendChild(thumb);
    });

    // 3. LOGIKA SELECT FILE BARU
    // Kita asumsikan file baru ada di urutan TERAKHIR (karena append) atau berdasarkan nama.
    // Biasanya sistem file sort by name. Jika kamera tethering memberi nama berurut (DSC_001, DSC_002),
    // maka file baru ada di index terakhir array `data.files`.
    
    const newestFile = data.files[data.files.length - 1];

    // Cari elemen thumbnail untuk file terbaru
    const newThumb = grid.querySelector(`div[data-filename="${newestFile}"]`);
    
    if (newThumb) {
        // Klik otomatis thumbnail tersebut
        changeActiveImage(newestFile, newThumb);
        // Scroll thumbnail agar terlihat
        newThumb.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        
        // Opsional: Mainkan suara notifikasi
        // const audio = new Audio('notify.mp3'); audio.play();
    }
}