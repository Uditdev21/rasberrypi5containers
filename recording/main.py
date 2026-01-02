import subprocess
import time
import sys
from pathlib import Path

# ================= CONFIG =================
STREAM_SCRIPTS = [
    "stream7.py",
    "stream8.py",
    "stream9.py",
    "stream10.py"
    # "cam7.py",
    # "office_gate.py",
]

RESTART_DELAY = 5  # seconds
# ==========================================


def start_process(script):
    print(f"🚀 Starting {script}")
    return subprocess.Popen(
        [sys.executable, script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )


def main():
    processes = {}

    for script in STREAM_SCRIPTS:
        if not Path(script).exists():
            print(f"❌ Script not found: {script}")
            continue
        processes[script] = start_process(script)

    print("✅ All streams launched\n")

    while True:
        time.sleep(2)

        for script, proc in list(processes.items()):
            if proc.poll() is not None:  # process exited
                print(f"⚠️ {script} stopped. Restarting in {RESTART_DELAY}s...")
                time.sleep(RESTART_DELAY)
                processes[script] = start_process(script)


if __name__ == "__main__":
    main()
