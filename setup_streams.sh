#!/bin/bash
# ==========================================================
# setup_streams.sh - Auto Setup for RTSP → RTMP Streaming
# ==========================================================
# Author: Udit Kumar
# Description:
#   - Installs Docker & Docker Compose (if not present)
#   - Starts containers defined in docker-compose.yml
#   - Ensures auto-start on reboot and reconnection
# ==========================================================

set -e

# ----------------------------
# CONFIGURATION
# ----------------------------
PROJECT_DIR="/home/rtsp_streams"   # Change if needed
COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"

# ----------------------------
# FUNCTIONS
# ----------------------------

install_docker() {
  echo "🔹 Checking Docker installation..."
  if ! command -v docker &> /dev/null; then
    echo "🚀 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
  else
    echo "✅ Docker already installed."
  fi

  echo "🔹 Checking Docker Compose plugin..."
  if ! docker compose version &> /dev/null; then
    echo "🚀 Installing Docker Compose plugin..."
    sudo apt-get install -y docker-compose-plugin
  else
    echo "✅ Docker Compose already installed."
  fi
}

check_compose_file() {
  echo "🔍 Checking for docker-compose.yml..."
  if [ ! -f "$COMPOSE_FILE" ]; then
    echo "❌ ERROR: docker-compose.yml not found in $PROJECT_DIR"
    echo "➡️ Please place your docker-compose.yml there before running this script."
    exit 1
  else
    echo "✅ docker-compose.yml found."
  fi
}

start_docker_service() {
  echo "🔁 Enabling and starting Docker service..."
  sudo systemctl enable docker
  sudo systemctl start docker
}

start_containers() {
  echo "🚀 Starting containers..."
  cd "$PROJECT_DIR"
  docker compose up -d
  echo "✅ Containers launched successfully!"
}

show_summary() {
  echo
  echo "=========================================================="
  echo " ✅ Setup complete!"
  echo "=========================================================="
  echo "📂 Project directory: $PROJECT_DIR"
  echo "📜 Compose file: $COMPOSE_FILE"
  echo
  echo "📺 Running containers:"
  docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
  echo
  echo "🪵 To view logs:       docker logs -f stream1"
  echo "🔁 To restart streams: docker compose restart"
  echo "⛔ To stop streams:    docker compose down"
  echo "=========================================================="
}

# ----------------------------
# EXECUTION FLOW
# ----------------------------

echo "=========================================================="
echo "🛠  Setting up RTSP → RTMP streaming services..."
echo "=========================================================="

install_docker
check_compose_file
start_docker_service
start_containers
show_summary
