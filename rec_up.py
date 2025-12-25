import time
import subprocess
import threading
import requests
from pathlib import Path

# ================= CONFIG =================
CAMERAS = {
    "cam4": "rtsp://192.168.1.212:554/live/0/MAIN",
    "cam5": "rtsp://192.168.1.144:554/live/0/MAIN",
    "cam6": "rtsp://192.168.1.211:554/live/0/MAIN",
}

CHUNK_DURATION = 60  # seconds
BASE_DIR = "chunks"

UPLOAD_URL = "https://test.dreams.codes/upload"   # <-- change this
UPLOAD_INTERVAL = 5  # seconds
API_KEY = "testkey"  # <-- change this to match web.py
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

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-fflags", "+genpts",
            "-i", rtsp_url,
            "-t", str(CHUNK_DURATION),
            "-c:v", "copy",
            "-c:a", "aac",
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

        # Atomic rename → uploader will see ONLY completed files
        if result.returncode == 0 and temp_file.exists():
            temp_file.rename(final_file)
        else:
            if temp_file.exists():
                temp_file.unlink()

        time.sleep(1)

# ================= UPLOADER =================
def uploader():
    while True:
        for cam_id in CAMERAS.keys():
            cam_dir = Path(BASE_DIR) / cam_id
            if not cam_dir.exists():
                continue

            # Only finalized files (never .part)
            files = sorted(cam_dir.glob("*.mp4"))

            for file in files:
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
                    else:
                        print(f"[WARN] Upload failed ({r.status_code})")
                        break  # retry later

                except Exception as e:
                    print(f"[ERR] Upload error: {e}")
                    break  # retry later

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

    print("Recording + Uploading started. Press Ctrl+C to stop.")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
