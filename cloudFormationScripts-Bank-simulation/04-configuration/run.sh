#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$ROOT_DIR/config/deployment.env"
INV="$SCRIPT_DIR/inventory/hosts.ini"
VARS="$SCRIPT_DIR/inventory/host_software.yml"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"; }

if [ ! -f "$CONFIG" ]; then
  log "ERROR" "Config not found: $CONFIG"
  exit 1
fi
# shellcheck source=../config/deployment.env
source "$CONFIG"

CMD="${1:-}"
EXTRA_VARS="-e wazuh_server_ip=${WAZUH_SERVER_IP:-} -e wazuh_port=${WAZUH_SERVER_PORT:-1514}"
[ -f "$VARS" ] && EXTRA_VARS="$EXTRA_VARS -e @$VARS"

case "$CMD" in
  install-software)
    [ ! -f "$INV" ] && log "ERROR" "Run inventory/generate_inventory.sh first" && exit 1
    log "INFO" "Running install_software (Linux + Windows)"
    ansible-playbook -i "$INV" $EXTRA_VARS "$SCRIPT_DIR/playbooks/install_software_linux.yaml" 2>/dev/null || true
    ansible-playbook -i "$INV" $EXTRA_VARS "$SCRIPT_DIR/playbooks/install_software_windows.yaml" 2>/dev/null || true
    ;;
  register-wazuh)
    [ ! -f "$INV" ] && log "ERROR" "Run inventory/generate_inventory.sh first" && exit 1
    [ -z "$WAZUH_SERVER_IP" ] && log "WARN" "WAZUH_SERVER_IP not set in config"
    log "INFO" "Running register_wazuh_agent"
    ansible-playbook -i "$INV" $EXTRA_VARS "$SCRIPT_DIR/playbooks/register_wazuh_agent.yaml"
    ;;
  all)
    [ ! -f "$INV" ] && "$SCRIPT_DIR/inventory/generate_inventory.sh"
    "$SCRIPT_DIR/run.sh" install-software
    "$SCRIPT_DIR/run.sh" register-wazuh
    ;;
  status)
    [ ! -f "$INV" ] && log "WARN" "Inventory not generated" && exit 0
    ansible -i "$INV" all -m ping 2>/dev/null || log "WARN" "Ansible ping failed"
    ;;
  *)
    log "ERROR" "Usage: $0 install-software | register-wazuh | all | status"
    exit 1
    ;;
esac
