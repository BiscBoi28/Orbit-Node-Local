#!/bin/bash
# orbit-dev health-check.sh
# Run on orbit-dev EC2 (e.g. after SSM/SSH). Checks each service with a clear pass/fail.
# Usage: sudo bash health-check.sh   OR   bash health-check.sh

set -e

COMPOSE_DIR="${DATA_MOUNT_PATH:-/data}/orbit-dev"
PASS=0
FAIL=0

check() {
  local name="$1"
  local cmd="$2"
  if eval "$cmd" >/dev/null 2>&1; then
    echo "  ✓ $name"
    PASS=$((PASS + 1))
    return 0
  else
    echo "  ✗ $name"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

echo ""
echo "=========================================="
echo "orbit-dev service health check"
echo "=========================================="
echo ""

# --- Docker containers (must be running) ---
echo "Containers:"
check "orbit-neo4j running"           "docker inspect -f '{{.State.Running}}' orbit-neo4j 2>/dev/null | grep -q true"
check "orbit-presidio-analyzer running" "docker inspect -f '{{.State.Running}}' orbit-presidio-analyzer 2>/dev/null | grep -q true"
check "orbit-juice-shop running"      "docker inspect -f '{{.State.Running}}' orbit-juice-shop 2>/dev/null | grep -q true"
check "orbit-orc running"             "docker inspect -f '{{.State.Running}}' orbit-orc 2>/dev/null | grep -q true"
echo ""

# --- HTTP/API health ---
echo "Endpoints:"
check "Neo4j (7474)"                  "wget --quiet --tries=1 --spider --timeout=5 http://127.0.0.1:7474 2>/dev/null"
check "Presidio /health (5001)"       "curl -sf --connect-timeout 5 http://127.0.0.1:5001/health >/dev/null"
check "Juice Shop (3000)"             "wget --quiet --tries=1 --spider --timeout=5 http://127.0.0.1:3000 2>/dev/null"
check "ORC /health (8000)"            "curl -sf --connect-timeout 5 http://127.0.0.1:8000/health >/dev/null"
echo ""

# --- Wazuh agent (optional) ---
echo "Agent:"
if systemctl is-active --quiet wazuh-agent 2>/dev/null; then
  echo "  ✓ wazuh-agent (active)"
  PASS=$((PASS + 1))
else
  echo "  ✗ wazuh-agent (inactive or not installed)"
  FAIL=$((FAIL + 1))
fi
echo ""

# --- Summary ---
echo "=========================================="
echo "Summary: $PASS passed, $FAIL failed"
echo "=========================================="
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "Troubleshooting:"
  echo "  docker compose -f $COMPOSE_DIR/docker-compose.yml ps"
  echo "  docker compose -f $COMPOSE_DIR/docker-compose.yml logs -f <service>"
  echo "  systemctl status wazuh-agent"
  exit 1
fi
exit 0
