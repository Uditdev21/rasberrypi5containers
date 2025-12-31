import time
import subprocess
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONFIG =================
CAMERAS = {
    "cam7": "rtsp://192.168.1.160:554/live/0/MAIN",
    "cam8": "rtsp://192.168.1.134:554/live/0/MAIN",
    "cam9": "rtsp://192.168.1.83:554/live/0/MAIN",
    "cam10": "rtsp://192.168.1.147:554/live/0/MAIN",
}

CHUNK_DURATION = 60        # ⏱ time-based only
BASE_DIR = "test_chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
UPLOAD_INTERVAL = 5
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

MAX_UPLOAD_WORKERS = 4
FILE_STABLE_SECONDS = 10
# =========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= RECORDING =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    restart_delay = 2

    while True:
        ts = int(time.time())
        start_time = time.time()

        temp_file = cam_dir / f"{cam_id}_{ts}.mp4.part"
        final_file = cam_dir / f"{cam_id}_{ts}.mp4"

        # 🔥 ENHANCED WITH RECONNECTION LOGIC & TIMEOUTS
        cmd = [
            "ffmpeg",

            # RTSP stability
            "-rtsp_transport", "tcp",
            "-rtbufsize", "256M",
            "-fflags", "+genpts+discardcorrupt",
            "-use_wallclock_as_timestamps", "1",

            "-i", rtsp_url,

            # Time-based chunk
            "-t", str(CHUNK_DURATION),

            # Encoding (same as working RTMP)
            "-c:v", "copy",
            "-c:a", "aac",
            "-ar", "44100",
            "-b:a", "128k",

            # Output
            "-movflags", "+faststart",
            "-f", "mp4",
            "-y",
            str(temp_file)
        ]

        print(f"[REC] {cam_id} → {final_file.name}")

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        elapsed = time.time() - start_time

        if result.returncode == 0 and temp_file.exists():
            temp_file.rename(final_file)
            print(f"[OK] {cam_id} recorded {elapsed:.1f}s")
        else:
            if temp_file.exists():
                temp_file.unlink()
            # Log FFmpeg errors for debugging
            if result.stderr:
                error_lines = result.stderr.split('\n')[-5:]  # Last 5 lines
                print(f"[ERR] {cam_id} FFmpeg error (code {result.returncode}): {' | '.join(error_lines)}")

            # If camera reports session issues, cool down longer to avoid hammering it
            if result.stderr and "Session Not Found" in result.stderr:
                cooldown = max(restart_delay, 10)
                print(f"[WARN] {cam_id} RTSP session missing; cooling down {cooldown}s before retry")
                time.sleep(cooldown)
                restart_delay = min(cooldown * 2, 30)
                continue

        # Backoff if FFmpeg exits too early
        if elapsed < 5:
            print(f"[WARN] {cam_id} FFmpeg exited early ({elapsed:.1f}s), retrying in {restart_delay}s")
            time.sleep(restart_delay)
            restart_delay = min(restart_delay * 2, 30)
        else:
            restart_delay = 2

        time.sleep(1)

# ================= UPLOAD WORKER =================
def upload_file(file: Path, cam_id: str):
    try:
        size_mb = file.stat().st_size / (1024 * 1024)
        print(f"[UP] {file.name} | size={size_mb:.2f} MB")

        with open(file, "rb") as f:
            headers = {"X-API-Key": API_KEY}
            r = requests.post(
                UPLOAD_URL,
                files={"file": f},
                data={"camera_id": cam_id},
                headers=headers,
                timeout=30
            )

        if r.status_code == 200:
            file.unlink()
            print(f"[OK] Uploaded & deleted {file.name}")
        else:
            print(f"[WARN] Upload failed ({r.status_code}) | {file.name}")

    except Exception as e:
        print(f"[ERR] Upload error {file.name}: {e}")

# ================= PARALLEL UPLOADER =================
def uploader():
    executor = ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS)

    while True:
        tasks = []
        now = time.time()

        for cam_id in CAMERAS.keys():
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            files = [
                f for f in cam_dir.glob("*.mp4")
                if now - f.stat().st_mtime >= FILE_STABLE_SECONDS
            ]

            for file in sorted(files):
                tasks.append(
                    executor.submit(upload_file, file, cam_id)
                )

        for future in as_completed(tasks):
            future.result()

        time.sleep(UPLOAD_INTERVAL)

# ================= MAIN =================
def main():
    for cam_id, url in CAMERAS.items():
        threading.Thread(
            target=record_camera,
            args=(cam_id, url),
            daemon=True
        ).start()

        # Stagger RTSP connection attempts so cameras are not hit at the same moment
        time.sleep(3)

    threading.Thread(
        target=uploader,
        daemon=True
    ).start()

    print(f"✅ Time-based Recording + Parallel Uploading started ({MAX_UPLOAD_WORKERS} workers)")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
