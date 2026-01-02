import time
import subprocess
import threading
from pathlib import Path

# ================= CONFIG =================
CAMERAS = {
    "cam7": "rtsp://192.168.1.160:554/live/0/MAIN",
    # "cam8": "rtsp://192.168.1.134:554/live/0/MAIN",
    # "cam9": "rtsp://192.168.1.83:554/live/0/MAIN",
    # "cam10": "rtsp://192.168.1.147:554/live/0/MAIN",
}

CHUNK_DURATION = 60   # seconds
BASE_DIR = "chunks"
# ==========================================

Path(BASE_DIR).mkdir(exist_ok=True)

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

        if result.returncode == 0 and temp_file.exists():
            temp_file.rename(final_file)
            print(f"[OK] Saved {final_file}")
        else:
            if temp_file.exists():
                temp_file.unlink()
            print(f"[ERR] Recording failed {cam_id}")

        time.sleep(1)

def main():
    for cam_id, url in CAMERAS.items():
        threading.Thread(
            target=record_camera,
            args=(cam_id, url),
            daemon=True
        ).start()

    print("🎥 Recording ONLY started")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    main()
