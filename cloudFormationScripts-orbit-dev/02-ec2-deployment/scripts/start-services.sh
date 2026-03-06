#!/bin/bash
# Manually start orbit-dev Docker services (Neo4j, Presidio, Juice Shop, ORC).
# Run on orbit-dev EC2 after SSM/SSH:  sudo bash /data/scripts/start-services.sh

set -e

DATA_MOUNT_PATH="${DATA_MOUNT_PATH:-/data}"
COMPOSE_DIR="$DATA_MOUNT_PATH/orbit-dev"

echo "Starting Docker if needed..."
systemctl start docker 2>/dev/null || true

echo "Waiting for Docker..."
for i in $(seq 1 15); do
  docker info >/dev/null 2>&1 && break
  [ "$i" -eq 15 ] && { echo "Docker not ready."; exit 1; }
  sleep 2
done

echo "Starting orbit-dev services..."
cd "$COMPOSE_DIR"
docker compose -f docker-compose.yml up -d

echo ""
echo "Status:"
docker compose -f docker-compose.yml ps
