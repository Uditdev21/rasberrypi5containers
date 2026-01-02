FROM ghcr.io/linuxserver/ffmpeg:version-6.1-cli

# 🔥 Disable ffmpeg entrypoint
ENTRYPOINT []

# Install Python (ARM-safe)
RUN apt-get update && \
    apt-get install -y python3 python3-pip && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
RUN pip3 install --no-cache-dir requests

CMD ["python3", "/app/stream.py"]
