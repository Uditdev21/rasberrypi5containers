import time
import subprocess
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from test_up import UPLOAD_INTERVAL

# ================= CONFIG =================
CAMERAS = {
    "cam7": "rtsp://192.168.1.160:554/live/0/MAIN",
    "cam8": "rtsp://192.168.1.134:554/live/0/MAIN",
    "cam9": "rtsp://192.168.1.83:554/live/0/MAIN",
    "cam10": "rtsp://192.168.1.147:554/live/0/MAIN",
}

CHUNK_DURATION = 60          # seconds
BASE_DIR = "chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"
UPLOAD_INTERVAL = 5  # seconds

MAX_UPLOAD_WORKERS = 4       # 🔥 PARALLEL UPLOADS
MAX_QUEUE_SIZE = 8           # safety limit
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= RECORDING =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    while True:
        ts = int(time.time())
        temp_file = cam_dir / f"{cam_id}_{ts}.mp4.part"
        final_file = cam_dir / f"{cam_id}_{ts}.mp4"

        if cam_id == "cam1":
            # Re-encode HEVC + PCM → H.264 + AAC
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-fflags", "+genpts",
                "-i", rtsp_url,
                "-t", str(CHUNK_DURATION),

                "-c:v", "libx264",
                "-preset", "veryfast",
                "-profile:v", "baseline",
                "-pix_fmt", "yuv420p",

                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "1",
                "-b:a", "64k",

                "-movflags", "+faststart",
                "-f", "mp4",
                "-y",
                str(temp_file)
            ]
        else:
            # Stream copy
            cmd = [
                "ffmpeg",
                "-rtsp_transport", "tcp",
                "-fflags", "+genpts",
                "-i", rtsp_url,
                "-t", str(CHUNK_DURATION),
                "-c:v", "copy",
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

# ================= UPLOADER =================
def upload_file(file, cam_id):
    try:
        print(f"[UP] {file.name}")

        with open(file, "rb") as f:
            headers = {"X-API-Key": API_KEY}
            r = requests.post(
                UPLOAD_URL,
                files={"file": f},
                data={"camera_id": cam_id},
                headers=headers,
                timeout=20
            )

        if r.status_code == 200:
            file.unlink()
            print(f"[OK] Uploaded & deleted {file.name}")
            return True
        else:
            print(f"[WARN] Upload failed ({r.status_code})")
            return False

    except Exception as e:
        print(f"[ERR] Upload error: {e}")
        return False


def uploader():
    executor = ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS)

    while True:
        futures = []

        for cam_id in CAMERAS.keys():
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            files = sorted(cam_dir.glob("*.mp4"))

            for file in files:
                futures.append(
                    executor.submit(upload_file, file, cam_id)
                )

                # prevent RAM / thread explosion
                if len(futures) >= MAX_QUEUE_SIZE:
                    break

        for f in futures:
            f.result()   # wait for uploads to finish

        time.sleep(UPLOAD_INTERVAL)

# ================= MAIN =================
def main():
    # Start recorder threads
    for cam_id, url in CAMERAS.items():
        threading.Thread(
            target=record_camera,
            args=(cam_id, url),
            daemon=True
        ).start()

    # Start uploader thread
    threading.Thread(
        target=uploader,
        daemon=True
    ).start()

    print("✅ Recording + Parallel Uploading started (4 uploads max)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
