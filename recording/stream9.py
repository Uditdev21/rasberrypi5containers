import time
import subprocess
import threading
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================= CONFIG =================
RTSP_URL = "rtsp://192.168.1.83:554/live/0/MAIN"
CHUNK_DURATION = 60  # seconds
BASE_DIR = "chunks"
LOG_DIR = "logs"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

UPLOAD_INTERVAL = 5
MAX_UPLOAD_WORKERS = 4

# Heuristic: < 1 MB usually means < 1 min or broken
MIN_VALID_FILE_SIZE = 1 * 1024 * 1024  # 1MB
# ==========================================

STREAM_NAME = Path(__file__).stem

Path(BASE_DIR).mkdir(exist_ok=True)
Path(LOG_DIR).mkdir(exist_ok=True)

STREAM_DIR = Path(BASE_DIR) / STREAM_NAME
STREAM_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = Path(LOG_DIR) / f"{STREAM_NAME}.log"

# ================= LOGGING =================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(STREAM_NAME)


# ================= RECORDING =================
def record_stream():
    logger.info(f"🎥 Recording started: {STREAM_NAME}")

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

        logger.info(f"[REC] → {final_file.name}")

        result = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        if result.returncode == 0 and temp_file.exists():
            size = temp_file.stat().st_size
            temp_file.rename(final_file)

            if size < MIN_VALID_FILE_SIZE:
                logger.warning(
                    f"[SHORT FILE] {final_file.name} | size={size/1024:.1f} KB "
                    f"(likely < {CHUNK_DURATION}s)"
                )
            else:
                logger.info(f"[OK] Saved {final_file.name} | size={size/1024/1024:.2f} MB")

        else:
            if temp_file.exists():
                temp_file.unlink()
            logger.error(f"[ERR] FFmpeg failed for chunk {ts}")

        time.sleep(1)


# ================= UPLOAD SINGLE FILE =================
def upload_file(file: Path):
    try:
        logger.info(f"[UP] {file.name}")

        with open(file, "rb") as f:
            headers = {"X-API-Key": API_KEY}
            r = requests.post(
                UPLOAD_URL,
                files={"file": f},
                data={"camera_id": STREAM_NAME},
                headers=headers,
                timeout=(10, 180)
            )

        if r.status_code == 200:
            file.unlink()
            logger.info(f"[OK] Uploaded & deleted {file.name}")
            return True
        else:
            logger.warning(
                f"[UPLOAD FAIL] {file.name} | status={r.status_code} | response={r.text[:200]}"
            )
            return False

    except Exception as e:
        logger.error(f"[UPLOAD ERROR] {file.name} | {e}")
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

                if len(futures) >= MAX_UPLOAD_WORKERS:
                    for f in as_completed(futures):
                        f.result()
                    futures.clear()

            for f in as_completed(futures):
                f.result()

            time.sleep(UPLOAD_INTERVAL)


# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=record_stream, daemon=True).start()
    threading.Thread(target=uploader, daemon=True).start()

    logger.info("✅ Recording + FAST Parallel Uploading started")

    while True:
        time.sleep(60)
