#!/bin/bash
# wazuh-dev health-check.sh
# Run on wazuh-dev EC2 (e.g. after SSM/SSH). Checks each Wazuh service with a clear pass/fail.
# Usage: sudo bash health-check.sh   OR   bash health-check.sh
#
# Optional: set INDEXER_USERNAME, INDEXER_PASSWORD for indexer API check (default: admin / SecretPassword).

set -e

INDEXER_USER="${INDEXER_USERNAME:-admin}"
INDEXER_PASS="${INDEXER_PASSWORD:-SecretPassword}"
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
echo "wazuh-dev service health check"
echo "=========================================="
echo ""

# --- Docker containers ---
echo "Containers:"
check "wazuh.manager running"   "docker inspect -f '{{.State.Running}}' wazuh.manager 2>/dev/null | grep -q true"
check "wazuh.indexer running"  "docker inspect -f '{{.State.Running}}' wazuh.indexer 2>/dev/null | grep -q true"
check "wazuh.dashboard running" "docker inspect -f '{{.State.Running}}' wazuh.dashboard 2>/dev/null | grep -q true"
echo ""

# --- Manager: agent port (1514) ---
echo "Endpoints:"
check "Wazuh manager port 1514 (agents)" "timeout 2 bash -c 'echo >/dev/tcp/127.0.0.1/1514' 2>/dev/null"
check "Wazuh indexer API (9200)" "curl -sk --connect-timeout 5 -u \"$INDEXER_USER:$INDEXER_PASS\" https://127.0.0.1:9200 2>/dev/null | grep -q cluster_name"
check "Wazuh dashboard (5601)" "curl -sk --connect-timeout 5 -o /dev/null -w '%{http_code}' https://127.0.0.1:5601 2>/dev/null | grep -qE '^[23][0-9][0-9]$'"
echo ""

# --- Nginx (if used as reverse proxy) ---
echo "Proxy:"
if systemctl is-active --quiet nginx 2>/dev/null; then
  echo "  ✓ nginx (active)"
  PASS=$((PASS + 1))
else
  echo "  - nginx (not running or not installed; optional)"
fi
echo ""

# --- Summary ---
echo "=========================================="
echo "Summary: $PASS passed, $FAIL failed"
echo "=========================================="
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "Troubleshooting:"
  echo "  docker ps --filter name=wazuh"
  echo "  docker compose -f /opt/wazuh-docker/docker-compose.yml logs -f"
  echo "  systemctl status nginx"
  exit 1
fi
exit 0
