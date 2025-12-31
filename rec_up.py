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

CHUNK_DURATION = 60  # seconds
BASE_DIR = "chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

UPLOAD_INTERVAL = 60       # ✅ check every 60 sec
MAX_UPLOAD_WORKERS = 4     # parallel uploads
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

# ================= UTILS =================
def is_full_chunk(file: Path, expected_sec: int) -> bool:
    """Verify recorded duration using ffprobe"""
    try:
        out = subprocess.check_output(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(file)
            ],
            stderr=subprocess.DEVNULL
        )
        duration = float(out.strip())
        return duration >= expected_sec - 1  # 1s tolerance
    except Exception:
        return False

# ================= RECORDING =================
def record_camera(cam_id, rtsp_url):
    cam_dir = Path(BASE_DIR) / cam_id
    cam_dir.mkdir(parents=True, exist_ok=True)

    while True:
        ts = time.strftime("%Y%m%d_%H%M%S")
        part_file = cam_dir / f"{cam_id}_{ts}.mp4.part"
        final_file = cam_dir / f"{cam_id}_{ts}.mp4"

        print(f"[REC] {cam_id} → {final_file.name}")

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-fflags", "+genpts",
            "-i", rtsp_url,
            "-t", str(CHUNK_DURATION),
            "-c:v", "copy",
            "-c:a", "aac",
            "-movflags", "+faststart",
            "-y",
            str(part_file)
        ]

        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # ✅ Promote only if FULL 60s recorded
        if part_file.exists() and is_full_chunk(part_file, CHUNK_DURATION):
            part_file.rename(final_file)
        else:
            if part_file.exists():
                part_file.unlink()  # ❌ discard partial

        # No sleep → next chunk starts immediately

# ================= UPLOAD =================
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
                timeout=60
            )

        if r.status_code == 200:
            file.unlink()
            print(f"[OK] Uploaded & deleted {file.name}")
            return True
        else:
            print(f"[WARN] Upload failed ({r.status_code}) | {file.name}")
            return False

    except Exception as e:
        print(f"[ERR] Upload error {file.name}: {e}")
        return False

# ================= PARALLEL UPLOADER =================
def uploader():
    executor = ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS)

    while True:
        tasks = []

        for cam_id in CAMERAS.keys():
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            # ✅ only finalized files
            for file in sorted(cam_dir.glob("*.mp4")):
                tasks.append(executor.submit(upload_file, file, cam_id))

        for future in as_completed(tasks):
            future.result()

        time.sleep(UPLOAD_INTERVAL)

# ================= MAIN =================
def main():
    # Start recorders
    for cam_id, url in CAMERAS.items():
        threading.Thread(
            target=record_camera,
            args=(cam_id, url),
            daemon=True
        ).start()

    # Start uploader
    threading.Thread(
        target=uploader,
        daemon=True
    ).start()

    print("✅ Recording (.part) → promote on 60s → parallel upload started")

    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
