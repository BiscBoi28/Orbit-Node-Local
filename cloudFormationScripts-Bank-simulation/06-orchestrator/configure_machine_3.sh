#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$ROOT_DIR/config/deployment.env"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"; }

if [ ! -f "$CONFIG" ]; then
  log "ERROR" "Config not found: $CONFIG"
  exit 1
fi
# shellcheck source=../config/deployment.env
source "$CONFIG"
export AWS_REGION AWS_PROFILE

LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/configure_machine_3_$(date +%Y%m%d_%H%M%S).log"
export LOG_FILE
exec > >(tee "$LOG_FILE") 2>&1
log "INFO" "Log file: $LOG_FILE"
log "INFO" "Configure machine 3 (NS-03) started"

CF_DIR="$ROOT_DIR/04-configuration"
INV="$CF_DIR/inventory/hosts.ini"
VARS="$CF_DIR/inventory/host_software.yml"

# Resolve machine_3 hostname from stack (NS-03)
HOST_MACHINE_3=$(aws cloudformation describe-stacks --stack-name "${EC2_STACK_PREFIX}-ns-03" \
  --query "Stacks[0].Outputs[?OutputKey=='Hostname'].OutputValue" --output text 2>/dev/null)
[ -z "$HOST_MACHINE_3" ] && HOST_MACHINE_3="corp-ad-01"
log "INFO" "Machine 3 host: $HOST_MACHINE_3"

log "INFO" "Machine 3: Generate inventory (started)"
bash "$CF_DIR/inventory/generate_inventory.sh"
log "INFO" "Machine 3: Generate inventory (completed)"

[ ! -f "$INV" ] && log "ERROR" "Inventory not generated. Run deploy_machine_3.sh first." && exit 1
log "INFO" "Inventory: $INV"
[ "${USE_SSM:-false}" = "true" ] && log "INFO" "Using AWS SSM for Ansible (no SSH key)"

EXTRA_VARS="-e wazuh_server_ip=${WAZUH_SERVER_IP:-} -e wazuh_port=${WAZUH_SERVER_PORT:-1514}"
[ -f "$VARS" ] && EXTRA_VARS="$EXTRA_VARS -e @$VARS" && log "INFO" "Using host_software: $VARS"
[ -n "${SSH_PRIVATE_KEY_FILE:-}" ] && [ -f "${SSH_PRIVATE_KEY_FILE:-}" ] && EXTRA_VARS="$EXTRA_VARS -e ansible_ssh_private_key_file=$SSH_PRIVATE_KEY_FILE" && log "INFO" "Using SSH key: $SSH_PRIVATE_KEY_FILE"

export ANSIBLE_HOST_KEY_CHECKING=False
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

log "INFO" "Machine 3: Install software (started) -- playbook install_software_windows.yaml --limit $HOST_MACHINE_3"
if ansible-playbook -i "$INV" $EXTRA_VARS "$CF_DIR/playbooks/install_software_windows.yaml" --limit "$HOST_MACHINE_3"; then
  log "INFO" "Machine 3: Install software (completed OK)"
else
  log "WARN" "Machine 3: Install software (completed with errors, check Ansible output above)"
fi

log "INFO" "Machine 3: Register Wazuh agent (started) -- playbook register_wazuh_agent.yaml --limit $HOST_MACHINE_3"
if ansible-playbook -i "$INV" $EXTRA_VARS "$CF_DIR/playbooks/register_wazuh_agent.yaml" --limit "$HOST_MACHINE_3"; then
  log "INFO" "Machine 3: Register Wazuh agent (completed OK)"
else
  log "WARN" "Machine 3: Register Wazuh agent (completed with errors, check Ansible output above)"
fi

log "INFO" "Configure machine 3 finished. Full log: $LOG_FILE"
