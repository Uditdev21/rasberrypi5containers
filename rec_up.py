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

CHUNK_DURATION = 60
BASE_DIR = "test_chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

MAX_UPLOAD_WORKERS = 10
UPLOAD_INTERVAL = 5
MIN_FILE_SIZE_MB = 4   # safety filter
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= RECORDING (SEGMENT MODE) =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = cam_dir / f"{cam_id}_%Y%m%d_%H%M%S.mp4"

    cmd = [
        "ffmpeg",
        "-rtsp_transport", "tcp",
        "-fflags", "+genpts",
        "-i", rtsp_url,

        # video (stable + low latency)
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",

        "-c:a", "aac",
        "-movflags", "+faststart",

        # 🔥 SEGMENT MODE (REAL FIX)
        "-f", "segment",
        "-segment_time", str(CHUNK_DURATION),
        "-reset_timestamps", "1",
        "-strftime", "1",

        str(output_pattern)
    ]

    print(f"🎥 [{cam_id}] Segment recorder started")

    while True:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        proc.wait()
        print(f"⚠ [{cam_id}] FFmpeg exited — restarting in 3s")
        time.sleep(3)

# ================= UPLOADER =================
def upload_one(file, cam_id):
    try:
        size_mb = file.stat().st_size / (1024 * 1024)
        if size_mb < MIN_FILE_SIZE_MB:
            file.unlink()
            print(f"[DROP] {file.name} ({size_mb:.1f} MB)")
            return

        print(f"[UP] {file.name} ({size_mb:.1f} MB)")

        with open(file, "rb") as f:
            r = requests.post(
                UPLOAD_URL,
                files={"file": f},
                data={"camera_id": cam_id},
                headers={"X-API-Key": API_KEY},
                timeout=180
            )

        if r.status_code == 200:
            file.unlink()
            print(f"[OK] Uploaded {file.name}")
        else:
            print(f"[WARN] Upload failed {file.name}")

    except Exception as e:
        print(f"[ERR] Upload error {file.name}: {e}")

def uploader():
    executor = ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS)

    while True:
        jobs = []

        for cam_id in CAMERAS:
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            for file in cam_dir.glob("*.mp4"):
                jobs.append((file.stat().st_mtime, file, cam_id))

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

    threading.Thread(target=uploader, daemon=True).start()

    print("✅ Camera recording & uploading started (SEGMENT MODE)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
