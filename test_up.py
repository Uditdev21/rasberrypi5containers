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
MIN_FILE_SIZE_MB = 2.0
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= RECORDING (UDP + CLOCK SEGMENT MODE) =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    output_pattern = cam_dir / f"{cam_id}_%Y%m%d_%H%M%S.mp4"

    cmd = [
        "ffmpeg",

        # 🔥 RTSP over UDP (MOST STABLE FOR IP CAMERAS)
        "-rtsp_transport", "udp",

        # Timestamp & corruption handling
        "-use_wallclock_as_timestamps", "1",
        "-fflags", "+genpts+discardcorrupt",
        "-avoid_negative_ts", "make_zero",

        "-i", rtsp_url,

        # Video
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",

        "-c:a", "aac",
        "-movflags", "+faststart",

        # 🔥 CLOCK-BASED SEGMENTATION
        "-f", "segment",
        "-segment_time", str(CHUNK_DURATION),
        "-segment_atclocktime", "1",
        "-segment_time_delta", "0.1",
        "-strftime", "1",

        str(output_pattern)
    ]

    print(f"🎥 [{cam_id}] Segment recorder started (UDP + CLOCK MODE)")

    while True:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        proc.wait()

        # Camera closed stream → wait before retry
        print(f"⚠ [{cam_id}] FFmpeg exited — restarting in 10s")
        time.sleep(10)

# ================= UPLOADER =================
def upload_one(file: Path, cam_id: str):
    try:
        size_mb = file.stat().st_size / (1024 * 1024)

        # Drop junk segments
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
            print(f"[OK] Uploaded & deleted {file.name}")
        else:
            print(f"[WARN] Upload failed {file.name} ({r.status_code})")

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

        # Oldest first
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

    print("✅ Camera recording & uploading started (UDP + CLOCK STABLE)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
