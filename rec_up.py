import time
import subprocess
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

# ================= CONFIG =================
CAMERAS = {
    "cam7": "rtsp://192.168.1.160:554/live/0/MAIN",
    "cam8": "rtsp://192.168.1.134:554/live/0/MAIN",
    "cam9": "rtsp://192.168.1.83:554/live/0/MAIN",
    "cam10": "rtsp://192.168.1.147:554/live/0/MAIN",
}

CHUNK_DURATION = 60          # seconds (reduce to 30 if network weak)
BASE_DIR = "chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

UPLOAD_INTERVAL = 5
MAX_UPLOAD_WORKERS = 2       # SAFE FOR RPI
MAX_FILES_PER_CAMERA = 200   # DISK SAFETY
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= GLOBAL UPLOAD CONTROL =================
UPLOAD_SEMAPHORE = threading.Semaphore(MAX_UPLOAD_WORKERS)
UPLOADING = set()
UPLOADING_LOCK = threading.Lock()

# ================= RECORDING =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    while True:
        ts = int(time.time())
        temp_file = cam_dir / f"{cam_id}_{ts}.mp4.part"
        final_file = cam_dir / f"{cam_id}_{ts}.mp4"

        # Disk safety
        if len(list(cam_dir.glob("*.mp4"))) > MAX_FILES_PER_CAMERA:
            print(f"[DROP] Disk limit reached for {cam_id}")
            time.sleep(5)
            continue

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-fflags", "+genpts",
            "-i", rtsp_url,
            "-t", str(CHUNK_DURATION),

            # 🔥 Re-encode HEVC → H264 (stable uploads)
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-tune", "zerolatency",
            "-pix_fmt", "yuv420p",

            "-c:a", "aac",
            "-movflags", "+faststart",
            "-f", "mp4",
            "-y",
            str(temp_file)
        ]

        print(f"[REC] {cam_id} → {final_file.name}")

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0 and temp_file.exists():
            temp_file.rename(final_file)
        else:
            if temp_file.exists():
                temp_file.unlink()

        time.sleep(1)

# ================= UPLOAD FUNCTION =================
def upload_one(file: Path, cam_id: str):
    with UPLOAD_SEMAPHORE:
        try:
            size_mb = file.stat().st_size / 1024 / 1024
            print(f"[UP] {file.name} ({size_mb:.1f} MB)")

            for attempt in range(3):
                try:
                    with open(file, "rb") as f:
                        r = requests.post(
                            UPLOAD_URL,
                            files={"file": f},
                            data={"camera_id": cam_id},
                            headers={"X-API-Key": API_KEY},
                            timeout=(10, 300)   # 🔥 FIXED TIMEOUT
                        )

                    if r.status_code == 200:
                        file.unlink()
                        print(f"[OK] Uploaded & deleted {file.name}")
                        return

                    else:
                        print(f"[WARN] HTTP {r.status_code} for {file.name}")

                except requests.exceptions.Timeout:
                    print(f"[RETRY] Timeout {file.name} attempt {attempt+1}")
                    time.sleep(5)

        except Exception as e:
            print(f"[ERR] Upload error {file.name}: {e}")

        finally:
            with UPLOADING_LOCK:
                UPLOADING.discard(file)

# ================= UPLOADER THREAD =================
def uploader():
    executor = ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS)

    while True:
        jobs = []

        for cam_id in CAMERAS:
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            for file in cam_dir.glob("*.mp4"):
                with UPLOADING_LOCK:
                    if file in UPLOADING:
                        continue
                    UPLOADING.add(file)

                jobs.append((file.stat().st_mtime, file, cam_id))

        # Upload oldest files first
        jobs.sort(key=lambda x: x[0])

        for _, file, cam_id in jobs:
            executor.submit(upload_one, file, cam_id)

        time.sleep(UPLOAD_INTERVAL)

# ================= MAIN =================
def main():
    for cam_id, url in CAMERAS.items():
        threading.Thread(
            target=record_camera,
            args=(cam_id, url),
            daemon=True
        ).start()

    threading.Thread(
        target=uploader,
        daemon=True
    ).start()

    print("✅ Camera recording & uploading started (STABLE MODE)")

    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
