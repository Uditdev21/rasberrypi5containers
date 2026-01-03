#!/bin/bash
set -e

echo "🛑 Stopping containers..."
docker compose down

echo "🧱 Building image once..."
docker build -t camera-recorder:latest .

echo "🚀 Starting containers..."
docker compose up -d

echo "✅ Active containers:"
docker compose ps
