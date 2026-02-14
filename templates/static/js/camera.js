let stream = null;
let isFrontCamera = true;
let backCameraList = [];
let currentBackCameraIndex = 0;
let timerSeconds = 0;

// Init Camera saat load
document.addEventListener('DOMContentLoaded', async () => {
    await requestCameraPermission();
    await enumerateCameras();
    startCamera();
});

async function requestCameraPermission() {
    try {
        const s = await navigator.mediaDevices.getUserMedia({ video: true });
        s.getTracks().forEach(t => t.stop());
    } catch (e) { console.warn("Izin kamera belum ok"); }
}

async function enumerateCameras() {
    try {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoDevices = devices.filter(d => d.kind === 'videoinput');
        
        // Cari kamera belakang (environment)
        backCameraList = videoDevices.filter(d => 
            d.label.toLowerCase().includes('back') || 
            d.label.toLowerCase().includes('rear') ||
            d.label.toLowerCase().includes('environment')
        ).map(d => d.deviceId);

        // Fallback jika label tidak terdeteksi, ambil device terakhir
        if (backCameraList.length === 0 && videoDevices.length > 1) {
            backCameraList = [videoDevices[videoDevices.length - 1].deviceId];
        }
    } catch (e) { console.error(e); }
}

async function startCamera() {
    if (stream) stream.getTracks().forEach(track => track.stop());

    const video = document.getElementById('videoFeed');
    const lensBtn = document.getElementById('lensToggleBtn');
    let constraints = { audio: false };

    if (isFrontCamera) {
        constraints.video = { facingMode: 'user', width: { ideal: 1920 }, height: { ideal: 1080 } };
        lensBtn.style.display = 'none';
    } else {
        if (backCameraList.length > 0) {
            const camId = backCameraList[currentBackCameraIndex];
            constraints.video = { deviceId: { exact: camId }, width: { ideal: 1920 }, height: { ideal: 1080 } };
            lensBtn.style.display = 'block';
            lensBtn.innerHTML = `<i class="fas fa-circle-notch"></i> Lensa ${currentBackCameraIndex + 1}`;
        } else {
            constraints.video = { facingMode: 'environment' };
            lensBtn.style.display = 'none';
        }
    }

    try {
        stream = await navigator.mediaDevices.getUserMedia(constraints);
        video.srcObject = stream;
        video.style.transform = isFrontCamera ? "scaleX(-1)" : "none";
    } catch (err) {
        showToast("Gagal akses kamera: " + err.message, 'error');
    }
}

function toggleCameraMode() {
    isFrontCamera = !isFrontCamera;
    startCamera();
}

function cycleBackLens() {
    if (isFrontCamera || backCameraList.length <= 1) return;
    currentBackCameraIndex = (currentBackCameraIndex + 1) % backCameraList.length;
    startCamera();
}

function toggleTimer() {
    const times = [0, 3, 5, 10];
    const idx = times.indexOf(timerSeconds);
    timerSeconds = times[(idx + 1) % times.length];
    document.getElementById('timerBtn').innerText = timerSeconds === 0 ? 'OFF' : `${timerSeconds}s`;
    document.getElementById('timerBtn').style.color = timerSeconds === 0 ? 'white' : 'var(--primary)';
}

function startCaptureSequence() {
    if(timerSeconds > 0) {
        let count = timerSeconds;
        const disp = document.getElementById('countdownDisplay');
        disp.innerText = count; 
        disp.style.display = 'block';
        
        const interval = setInterval(() => {
            count--;
            if(count > 0) disp.innerText = count;
            else { 
                clearInterval(interval); 
                disp.style.display = 'none'; 
                takePicture(); 
            }
        }, 1000);
    } else { 
        takePicture(); 
    }
}

function takePicture() {
    // Flash Effect
    const flash = document.getElementById('flash');
    flash.style.opacity = 1; 
    setTimeout(() => flash.style.opacity = 0, 150);

    const video = document.getElementById('videoFeed');
    const canvas = document.getElementById('captureCanvas');
    const ctx = canvas.getContext('2d');

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    // Mirroring Fix
    if (isFrontCamera) {
        ctx.translate(canvas.width, 0);
        ctx.scale(-1, 1);
    }

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(blob => {
        const url = URL.createObjectURL(blob);
        const id = Date.now();
        
        // Simpan ke Global State APP (yang ada di app.js)
        if(window.APP) {
            window.APP.photos.push({ id, blob, url });
            // Panggil renderGallery (global dari gallery.js)
            if(typeof renderGallery === 'function') renderGallery();
            
            showToast("Foto tersimpan!", "success");
        }
    }, 'image/jpeg', 0.95);
}