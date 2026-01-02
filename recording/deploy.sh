#!/bin/bash
set -e

echo "🛑 Stopping containers..."
docker compose down

echo "🧹 Cleaning old images..."
docker image prune -f

echo "🚀 Building & starting containers..."
docker compose up -d --build

echo "✅ Active containers:"
docker compose ps
