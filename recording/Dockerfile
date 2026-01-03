FROM ghcr.io/linuxserver/ffmpeg:version-6.1-cli

# Disable ffmpeg entrypoint
ENTRYPOINT []

WORKDIR /app

# Minimal Python only
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3-minimal \
        python3-pip \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Only dependency you need
RUN pip3 install --no-cache-dir requests

CMD ["python3", "/app/stream.py"]
