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
STABLE_SECONDS = 3
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

# ================= RECORDING =================
def record_stream():
    delay = random.uniform(2, 6)
    logger.info(f"⏳ Startup delay {delay:.1f}s to avoid sync storms")
    time.sleep(delay)

    logger.info(f"🎥 Recording started (GUARANTEED MODE): {STREAM_NAME}")

    output_pattern = STREAM_DIR / f"{STREAM_NAME}_%05d.mkv"

    cmd = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel", "error",

    "-rtsp_transport", "tcp",
    "-fflags", "nobuffer",
    "-flags", "low_delay",
    "-i", RTSP_URL,

    # Video only
    "-map", "0:v:0",
    "-c:v", "copy",

    # PURE DURATION SEGMENTING (STABLE)
    "-f", "segment",
    "-segment_time", str(CHUNK_DURATION),
    "-break_non_keyframes", "1",
    "-segment_format", "matroska",

    "-y",
    str(output_pattern),
    ]

    while True:
        logger.info("▶️ FFmpeg launched")
        proc = subprocess.Popen(cmd)
        ret = proc.wait()
        logger.error(f"❌ FFmpeg exited (code={ret}) — restarting safely")
        time.sleep(5)

# ================= FILE STABILITY CHECK =================
def is_file_stable(path: Path, stable_seconds=STABLE_SECONDS):
    try:
        size1 = path.stat().st_size
        time.sleep(stable_seconds)
        size2 = path.stat().st_size
        return size1 == size2
    except FileNotFoundError:
        return False

# ================= VIDEO DURATION =================
def get_video_duration(path: Path):
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return None

# ================= UPLOAD =================
def upload_file(file: Path):
    try:
        size_bytes = file.stat().st_size
        size_mb = size_bytes / 1024 / 1024

        duration = get_video_duration(file)
        duration_str = f"{duration:.1f}s" if duration else "unknown"

        logger.info(
            f"[UP] {file.name} | size={size_mb:.2f} MB | duration={duration_str}"
        )

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
            ready = []

            for f in files:
                if is_file_stable(f):
                    ready.append(f)

            if not ready:
                time.sleep(UPLOAD_INTERVAL)
                continue

            futures = [executor.submit(upload_file, f) for f in ready]
            for f in as_completed(futures):
                f.result()

            time.sleep(UPLOAD_INTERVAL)

# ================= MAIN =================
if __name__ == "__main__":
    threading.Thread(target=record_stream, daemon=True).start()
    threading.Thread(target=uploader, daemon=True).start()

    logger.info("✅ GUARANTEED recorder + race-safe uploader started")

    while True:
        time.sleep(60)
