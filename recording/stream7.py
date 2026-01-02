import time
import subprocess
import threading
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONFIG =================
RTSP_URL = "rtsp://192.168.1.160:554/live/0/MAIN"
CHUNK_DURATION = 60
BASE_DIR = "chunks"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

UPLOAD_INTERVAL = 5
MAX_UPLOAD_WORKERS = 4    # 🔥 increase to 6–8 if bandwidth allows
# ==========================================

# Stream name = file name
STREAM_NAME = Path(__file__).stem

Path(BASE_DIR).mkdir(exist_ok=True)
STREAM_DIR = Path(BASE_DIR) / STREAM_NAME
STREAM_DIR.mkdir(parents=True, exist_ok=True)


# ================= RECORDING =================
def record_stream():
    print(f"🎥 Recording started: {STREAM_NAME}")

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
            print(f"[OK] Saved {final_file.name}")
        else:
            if temp_file.exists():
                temp_file.unlink()
            print("[ERR] Recording failed")

        time.sleep(1)


# ================= UPLOAD SINGLE FILE =================
def upload_file(file: Path):
    try:
        print(f"[UP] {file.name}")

        with open(file, "rb") as f:
            headers = {"X-API-Key": API_KEY}
            r = requests.post(
                UPLOAD_URL,
                files={"file": f},
                data={"camera_id": STREAM_NAME},
                headers=headers,
                timeout=20
            )

        if r.status_code == 200:
            file.unlink()
            print(f"[OK] Uploaded & deleted {file.name}")
            return True
        else:
            print(f"[WARN] Upload failed ({r.status_code}) {file.name}")
            return False

    except Exception as e:
        print(f"[ERR] Upload error {file.name}: {e}")
        return False


# ================= PARALLEL UPLOADER =================
def uploader():
    with ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS) as executor:
        while True:
            files = sorted(STREAM_DIR.glob("*.mp4"))

            if not files:
                time.sleep(UPLOAD_INTERVAL)
                continue

            futures = []

            for file in files:
                futures.append(executor.submit(upload_file, file))

                # Flush in batches
                if len(futures) >= MAX_UPLOAD_WORKERS:
                    for f in as_completed(futures):
                        f.result()
                    futures.clear()

            # Remaining uploads
            for f in as_completed(futures):
                f.result()

            time.sleep(UPLOAD_INTERVAL)


# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=record_stream, daemon=True).start()
    threading.Thread(target=uploader, daemon=True).start()

    print("✅ Recording + FAST Parallel Uploading started")
    while True:
        time.sleep(60)
