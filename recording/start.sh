#!/bin/bash

set -e  # exit on error

SERVICES=(
  cam-recorder-1
  cam-recorder-2
  cam-recorder-3
  cam-recorder-4
)

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

for SERVICE in "${SERVICES[@]}"; do
  echo "🚀 Enabling $SERVICE"
  sudo systemctl enable "$SERVICE"

  echo "▶️ Starting $SERVICE"
  sudo systemctl start "$SERVICE"

  echo "✅ $SERVICE started"
  echo "-----------------------------"
done

echo "🎉 All camera recorder services deployed successfully"
