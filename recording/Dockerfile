FROM python:3.12-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
RUN pip install --no-cache-dir requests

# DO NOT COPY any stream file
# Script will be mounted at runtime

CMD ["python", "/app/stream.py"]
