import time
import subprocess
import threading
import requests
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

# ================= CONFIG =================
RTSP_URL = "rtsp://192.168.1.160:554/live/0/MAIN"
CHUNK_DURATION = 60  # seconds

BASE_DIR = "chunks"
LOG_DIR = "logs"

UPLOAD_URL = "https://diseaseai.agrikheti.com/upload"
API_KEY = "6513d871943f3acaf3ef2dee663980bb2087ef2a0a1f9028367906c8d1ffe375"

UPLOAD_INTERVAL = 5
MAX_UPLOAD_WORKERS = 4
# =========================================

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
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(STREAM_NAME)

# ================= RECORDING (GUARANTEED MODE) =================
def record_stream():
    delay = random.uniform(2, 6)
    logger.info(f"⏳ Startup delay {delay:.1f}s to avoid sync storms")
    time.sleep(delay)

    logger.info(f"🎥 Recording started (GUARANTEED MODE): {STREAM_NAME}")

    output_pattern = STREAM_DIR / f"{STREAM_NAME}_%05d.mkv.part"

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",

        "-rtsp_transport", "tcp",
        "-use_wallclock_as_timestamps", "1",
        "-fflags", "+genpts",
        "-i", RTSP_URL,

        # VIDEO ONLY (audio removed to avoid codec issues)
        "-map", "0:v:0",
        "-c:v", "copy",

        # SEGMENTING — NO KEYFRAME WAITING
        "-f", "segment",
        "-segment_time", str(CHUNK_DURATION),
        "-segment_atclocktime", "1",
        "-break_non_keyframes", "1",
        "-segment_format", "matroska",

        "-y",
        str(output_pattern),
    ]

    while True:
        logger.info("▶️ FFmpeg launched (GUARANTEED)")
        proc = subprocess.Popen(cmd)
        ret = proc.wait()
        logger.error(f"❌ FFmpeg exited (code={ret}) — restarting safely")
        time.sleep(5)


# ================= FINALIZE SEGMENTS =================
def finalize_segments():
    """
    Rename *.mkv.part → *.mkv
    MKV is always valid even if short.
    """
    while True:
        for part in STREAM_DIR.glob("*.mkv.part"):
            final = part.with_suffix("")
            try:
                part.rename(final)
                logger.info(f"[OK] Finalized {final.name}")
            except Exception as e:
                logger.error(f"[RENAME ERROR] {part.name} | {e}")

        time.sleep(2)


# ================= UPLOAD =================
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
                timeout=(20, 500),
            )

        if r.status_code == 200:
            file.unlink()
            logger.info(f"[OK] Uploaded & deleted {file.name}")
            return True

        logger.warning(
            f"[UPLOAD FAIL] {file.name} | status={r.status_code} | {r.text[:200]}"
        )
        return False

    except Exception as e:
        logger.error(f"[UPLOAD ERROR] {file.name} | {e}")
        return False


def internet_available(timeout=3):
    try:
        requests.head("https://www.google.com", timeout=timeout)
        return True
    except requests.RequestException:
        return False


def uploader():
    with ThreadPoolExecutor(max_workers=MAX_UPLOAD_WORKERS) as executor:
        while True:
            if not internet_available():
                logger.warning("[NET] Internet unavailable, upload paused")
                time.sleep(10)
                continue

            files = sorted(STREAM_DIR.glob("*.mkv"))
            if not files:
                time.sleep(UPLOAD_INTERVAL)
                continue

            futures = [executor.submit(upload_file, f) for f in files]
            for f in as_completed(futures):
                f.result()

            time.sleep(UPLOAD_INTERVAL)


# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=record_stream, daemon=True).start()
    threading.Thread(target=finalize_segments, daemon=True).start()
    threading.Thread(target=uploader, daemon=True).start()

    logger.info("✅ GUARANTEED recorder + uploader started")

    while True:
        time.sleep(60)
