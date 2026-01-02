import time
import subprocess
from pathlib import Path
import sys

# ================= CONFIG =================
RTSP_URL = "rtsp://192.168.1.160:554/live/0/MAIN"
CHUNK_DURATION = 60   # seconds
BASE_DIR = "chunks"
# ==========================================

# ---------- STREAM NAME FROM FILE ARG ----------
# Usage:
# python3 recorder_single.py cam7
if len(sys.argv) < 2:
    print("Usage: python3 recorder_single.py <stream_name>")
    sys.exit(1)

STREAM_NAME = sys.argv[1]

Path(BASE_DIR).mkdir(exist_ok=True)
STREAM_DIR = Path(BASE_DIR) / STREAM_NAME
STREAM_DIR.mkdir(parents=True, exist_ok=True)


def record_stream():
    print(f"🎥 Recording started for stream: {STREAM_NAME}")
    print(f"📂 Output directory: {STREAM_DIR}")

    while True:
        ts = int(time.time())
        temp_file = STREAM_DIR / f"{STREAM_NAME}_{ts}.mp4.part"
        final_file = STREAM_DIR / f"{STREAM_NAME}_{ts}.mp4"

        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-fflags", "+genpts",
            "-i", RTSP_URL,
            "-t", str(CHUNK_DURATION),
            "-c:v", "copy",
            "-c:a", "aac",
            "-f", "mp4",
            "-y",
            str(temp_file)
        ]

        print(f"[REC] → {final_file.name}")

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
            print(f"[ERR] Recording failed")

        time.sleep(1)


if __name__ == "__main__":
    record_stream()
