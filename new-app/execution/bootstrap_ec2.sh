#!/bin/bash
# execution/bootstrap_ec2.sh
# Bootstraps orbit-dev via SSH when starting from a clean server.
#
# Usage: ORBIT_REPO_URL=https://github.com/yourteam/repo.git bash execution/bootstrap_ec2.sh
#
# Prerequisites:
#   - iiith-orbit-key.pem accessible (default: ~/.ssh/iiith-orbit-key.pem)
#   - Directives 01-03 complete
#   - new-app code on this laptop OR a GitHub repo URL

set -e

SERVER="ubuntu@16.58.158.189"
KEY="${PEM_KEY:-$HOME/.ssh/iiith-orbit-key.pem}"
REPO_URL="${ORBIT_REPO_URL:-}"
REMOTE_DIR="/home/ubuntu/orbit"

SSH="ssh -i $KEY -o StrictHostKeyChecking=no $SERVER"
SCP="scp -i $KEY"

# ── Validate ──────────────────────────────────────────────────────────────────

if [ ! -f "$KEY" ]; then
  echo "ERROR: PEM key not found at $KEY"
  echo "Set PEM_KEY=/path/to/iiith-orbit-key.pem or place the key at ~/.ssh/iiith-orbit-key.pem"
  exit 1
fi

chmod 400 "$KEY"

echo "Testing SSH connection to $SERVER..."
$SSH "echo SSH connection OK" || { echo "ERROR: Cannot SSH to server. Check IP and key."; exit 1; }

# ── Helper ────────────────────────────────────────────────────────────────────

remote() {
  echo "→ $1"
  $SSH "$1"
}

# ── Steps ─────────────────────────────────────────────────────────────────────

echo ""
echo "════ Step 1: Install Docker (if needed) ════"
remote "docker --version 2>/dev/null || (
  apt-get update -y &&
  apt-get install -y ca-certificates curl gnupg &&
  install -m 0755 -d /etc/apt/keyrings &&
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg &&
  chmod a+r /etc/apt/keyrings/docker.gpg &&
  echo \"deb [arch=\$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \$(. /etc/os-release && echo \$VERSION_CODENAME) stable\" | tee /etc/apt/sources.list.d/docker.list > /dev/null &&
  apt-get update -y &&
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin &&
  systemctl enable docker && systemctl start docker
)"

echo ""
echo "════ Step 2: Create working directory ════"
remote "mkdir -p $REMOTE_DIR"

echo ""
echo "════ Step 3: Deploy code ════"
if [ -n "$ORBIT_REPO_URL" ]; then
  echo "Cloning from GitHub: $ORBIT_REPO_URL"
  remote "cd $REMOTE_DIR && git clone $ORBIT_REPO_URL . 2>/dev/null || git pull origin main"
else
  echo "No ORBIT_REPO_URL set — using rsync from current directory"
  echo "Make sure you're running this from inside your new-app directory."
  rsync -avz \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.tmp' \
    --exclude '.git' \
    --exclude '.env' \
    -e "ssh -i $KEY" \
    ./ $SERVER:$REMOTE_DIR/
fi

echo ""
echo "════ Step 4: Write .env ════"
$SSH "cat > $REMOTE_DIR/.env << 'EOF'
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA
PRESIDIO_URL=http://presidio:5001
CROWN_JEWEL_THRESHOLD=0.75
ROLE_BONUS_DB=0.2
ROLE_BONUS_WEB=0.1
BREADTH_BONUS_MAX=0.2
EOF
chmod 600 $REMOTE_DIR/.env"

echo ""
echo "════ Step 5: Start containers ════"
remote "cd $REMOTE_DIR && docker compose pull neo4j presidio 2>/dev/null; docker compose build orc && docker compose up -d"

echo ""
echo "Waiting 90 seconds for Neo4j to initialize..."
sleep 90

echo ""
echo "════ Step 6: Check status ════"
remote "cd $REMOTE_DIR && docker compose ps"

echo ""
echo "════ Step 7: Seed database ════"
remote "cd $REMOTE_DIR && docker compose exec -T orc python -m app.seed"

echo ""
echo "════ Step 8: Smoke tests ════"
remote "cd $REMOTE_DIR && bash execution/smoke_test.sh http://localhost:8000"

echo ""
echo "════════════════════════════════════════"
echo "✅ Bootstrap complete!"
echo "   ORC API running on $SERVER port 8000"
echo "   Neo4j Browser: http://16.58.158.189:7474"
echo "════════════════════════════════════════"
