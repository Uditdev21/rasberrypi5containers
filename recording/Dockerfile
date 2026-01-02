FROM python:3.12-slim

# Install ffmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
RUN pip install --no-cache-dir requests

# Copy script (will be overridden per container)
COPY stream.py /app/stream.py

CMD ["python", "/app/stream.py"]
