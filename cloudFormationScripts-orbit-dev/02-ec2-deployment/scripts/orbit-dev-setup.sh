#!/bin/bash
# orbit-dev-setup.sh
# Runs on orbit-dev EC2 (via UserData, after Docker + EBS are ready).
# Brings up: Neo4j, Presidio Analyzer, OWASP Juice Shop, ORC placeholder.
# Installs and registers the Wazuh agent against wazuh-dev.
#
# Environment variables injected by UserData:
#   DATA_MOUNT_PATH   - EBS mount path (default /data)
#   WAZUH_MANAGER_IP  - Elastic IP of wazuh-dev EC2 (default 18.116.159.176)
#   AWS_DEFAULT_REGION

set -e

exec > >(tee -a /var/log/orbit-dev-setup.log) 2>&1

DATA_MOUNT_PATH="${DATA_MOUNT_PATH:-/data}"
WAZUH_MANAGER_IP="${WAZUH_MANAGER_IP:-18.116.159.176}"
COMPOSE_DIR="$DATA_MOUNT_PATH/orbit-dev"

echo ""
echo "=========================================="
echo "orbit-dev Setup  -  $(date)"
echo "=========================================="
echo "DATA_MOUNT_PATH:  $DATA_MOUNT_PATH"
echo "WAZUH_MANAGER_IP: $WAZUH_MANAGER_IP"
echo "COMPOSE_DIR:      $COMPOSE_DIR"
echo ""

# ==========================================================
# 1. Directories
# ==========================================================
echo "--- [1/5] Creating data directories ---"
mkdir -p "$COMPOSE_DIR"
mkdir -p "$DATA_MOUNT_PATH/neo4j/data"
mkdir -p "$DATA_MOUNT_PATH/neo4j/logs"
mkdir -p "$DATA_MOUNT_PATH/neo4j/import"
mkdir -p "$DATA_MOUNT_PATH/neo4j/plugins"
mkdir -p "$DATA_MOUNT_PATH/presidio"
mkdir -p "$DATA_MOUNT_PATH/orc/html"
chown -R ubuntu:ubuntu "$DATA_MOUNT_PATH"
echo "✓ Directories created"

# ==========================================================
# 2. Credentials from Secrets Manager
# ==========================================================
echo ""
echo "--- [2/5] Fetching credentials ---"

NEO4J_LOCAL_PASSWORD="orbit-dev-2024!"   # default for local Neo4j container

if command -v aws &>/dev/null && aws secretsmanager get-secret-value \
    --secret-id orbit/node/neo4j-credentials \
    --region "${AWS_DEFAULT_REGION:-us-east-2}" \
    --query SecretString --output text &>/dev/null 2>&1; then
  # Use the stored Neo4j password as the local password too (keeps ORC config consistent)
  SECRET=$(aws secretsmanager get-secret-value \
    --secret-id orbit/node/neo4j-credentials \
    --region "${AWS_DEFAULT_REGION:-us-east-2}" \
    --query SecretString --output text)
  SM_PASSWORD=$(echo "$SECRET" | jq -r '.Neo4jPassword // empty')
  [ -n "$SM_PASSWORD" ] && NEO4J_LOCAL_PASSWORD="$SM_PASSWORD"
  echo "✓ Neo4j password fetched from Secrets Manager"
else
  echo "! Secrets Manager unavailable - using default local password"
fi

# ==========================================================
# 3. .env file (keeps credentials out of docker-compose.yml)
# ==========================================================
cat > "$COMPOSE_DIR/.env" << ENV_EOF
NEO4J_PASSWORD=${NEO4J_LOCAL_PASSWORD}
DATA_MOUNT=${DATA_MOUNT_PATH}
ENV_EOF
chmod 600 "$COMPOSE_DIR/.env"
echo "✓ .env written"

# ==========================================================
# 4. docker-compose.yml
# ==========================================================
echo ""
echo "--- [3/5] Writing docker-compose.yml ---"

# Note: compose variable syntax ${VAR} is resolved from the .env file at runtime.
# Shell variables (used below during file creation) are prefixed with $SHELL_VAR
# and interpolated now; compose env vars are left as ${COMPOSE_VAR}.
cat > "$COMPOSE_DIR/docker-compose.yml" << 'COMPOSE_EOF'
# orbit-dev Docker Compose
# Services: Neo4j, Presidio Analyzer, OWASP Juice Shop, ORC placeholder
# Credentials and paths are sourced from .env (auto-loaded by docker compose)

services:

  # ------------------------------------------------------------------
  # Neo4j Community 5.x - graph store for ORBIT
  # Browser:  http://<ip>:7474  (user: neo4j / see .env)
  # Bolt:     bolt://<ip>:7687
  # ------------------------------------------------------------------
  neo4j:
    image: neo4j:5.23-community
    container_name: orbit-neo4j
    ports:
      - "7474:7474"   # HTTP browser UI
      - "7473:7473"   # HTTPS browser UI
      - "7687:7687"   # Bolt
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_server_memory_heap_initial__size=512m
      - NEO4J_server_memory_heap_max__size=2G
      - NEO4J_server_memory_pagecache_size=1G
      - NEO4J_dbms_security_allow__csv__import__from__file__urls=true
    volumes:
      - ${DATA_MOUNT}/neo4j/data:/data
      - ${DATA_MOUNT}/neo4j/logs:/logs
      - ${DATA_MOUNT}/neo4j/import:/var/lib/neo4j/import
      - ${DATA_MOUNT}/neo4j/plugins:/plugins
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:7474"]
      interval: 30s
      timeout: 10s
      retries: 12
      start_period: 60s

  # ------------------------------------------------------------------
  # Microsoft Presidio Analyzer - PII / sensitivity engine
  # API:  http://<ip>:5001
  # Docs: https://microsoft.github.io/presidio/
  # ------------------------------------------------------------------
  presidio-analyzer:
    image: mcr.microsoft.com/presidio-analyzer:latest
    container_name: orbit-presidio-analyzer
    ports:
      - "5001:3000"   # external:internal
    environment:
      - NLP_ENGINE_NAME=spacy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 12
      start_period: 120s   # spaCy model download on first start

  # ------------------------------------------------------------------
  # OWASP Juice Shop - representative "customer-facing app" for the demo
  # App:  http://<ip>:3000
  # ------------------------------------------------------------------
  juice-shop:
    image: bkimminich/juice-shop:latest
    container_name: orbit-juice-shop
    ports:
      - "3000:3000"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:3000"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s

  # ------------------------------------------------------------------
  # ORC placeholder (nginx) - replace with real ORC Python service
  # API:  http://<ip>:8000
  # ------------------------------------------------------------------
  orc:
    image: nginx:alpine
    container_name: orbit-orc
    ports:
      - "8000:80"
    volumes:
      - ${DATA_MOUNT}/orc/html:/usr/share/nginx/html:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "wget", "--quiet", "--tries=1", "--spider", "http://localhost:80/health"]
      interval: 15s
      timeout: 5s
      retries: 3

COMPOSE_EOF

echo "✓ docker-compose.yml written"

# ==========================================================
# ORC placeholder content
# ==========================================================
cat > "$DATA_MOUNT_PATH/orc/html/index.html" << 'HTML_EOF'
<!DOCTYPE html>
<html>
<head><title>ORBIT ORC - Placeholder</title></head>
<body>
  <h1>ORBIT Orchestrator (ORC)</h1>
  <p>Status: <strong>Placeholder (nginx)</strong></p>
  <p>Replace this container with the real ORC Python service when ready.</p>
</body>
</html>
HTML_EOF

# /health endpoint for health checks
printf '{"status":"ok","service":"orc-placeholder"}' \
  > "$DATA_MOUNT_PATH/orc/html/health"

# ==========================================================
# 5. Start Docker services
# ==========================================================
echo ""
echo "--- [4/5] Starting Docker services ---"

# Ensure Docker daemon is ready (handles race when run right after install)
for i in $(seq 1 30); do
  if docker info >/dev/null 2>&1; then
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "ERROR: Docker not available. Check: systemctl status docker"
    exit 1
  fi
  echo "Waiting for Docker... ($i/30)"
  sleep 2
done

cd "$COMPOSE_DIR"

echo "Pulling images (this may take a few minutes)..."
docker compose pull

echo "Starting services..."
docker compose up -d

echo "✓ Services started"

# Wait for Neo4j (it takes 30-60 s to initialise)
echo "Waiting for Neo4j to be ready..."
for i in $(seq 1 36); do
  if docker exec orbit-neo4j wget --quiet --tries=1 --spider http://localhost:7474 2>/dev/null; then
    echo "✓ Neo4j is ready (attempt $i)"
    break
  fi
  if [ "$i" -eq 36 ]; then
    echo "! Neo4j not ready after 3 min - check: docker logs orbit-neo4j"
  fi
  sleep 5
done

# ==========================================================
# 6. Install Wazuh agent and register with wazuh-dev
# ==========================================================
echo ""
echo "--- [5/5] Installing Wazuh agent ---"

# Add Wazuh 4.x APT repository
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH \
  | gpg --no-default-keyring \
        --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg \
        --import 2>/dev/null
chmod 644 /usr/share/keyrings/wazuh.gpg

echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] \
  https://packages.wazuh.com/4.x/apt/ stable main" \
  | tee /etc/apt/sources.list.d/wazuh.list > /dev/null

apt-get update -qq

# Install + auto-register agent (env vars are read by the postinstall script)
WAZUH_MANAGER="$WAZUH_MANAGER_IP" \
WAZUH_AGENT_NAME="orbit-dev" \
  apt-get install -y wazuh-agent

systemctl daemon-reload
systemctl enable wazuh-agent
systemctl start wazuh-agent

echo "✓ Wazuh agent installed (manager: $WAZUH_MANAGER_IP)"

# ==========================================================
# Summary
# ==========================================================
INSTANCE_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<elastic-ip>")

echo ""
echo "=========================================="
echo "orbit-dev Setup Complete  -  $(date)"
echo "=========================================="
echo ""
echo "Service endpoints:"
printf "  %-26s http://%s:7474  (user: neo4j)\n" "Neo4j Browser:" "$INSTANCE_IP"
printf "  %-26s bolt://%s:7687\n"                "Neo4j Bolt:"   "$INSTANCE_IP"
printf "  %-26s http://%s:5001\n"                "Presidio:"     "$INSTANCE_IP"
printf "  %-26s http://%s:3000\n"                "Juice Shop:"   "$INSTANCE_IP"
printf "  %-26s http://%s:8000\n"                "ORC:"          "$INSTANCE_IP"
echo ""
echo "Useful commands (SSH in first):"
echo "  docker compose -f $COMPOSE_DIR/docker-compose.yml ps"
echo "  docker compose -f $COMPOSE_DIR/docker-compose.yml logs -f"
echo "  systemctl status wazuh-agent"
echo "  /var/ossec/bin/wazuh-control status"
echo ""
echo "Neo4j password: stored in $COMPOSE_DIR/.env"
