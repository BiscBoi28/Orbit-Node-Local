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
LOG_FILE="$LOG_DIR/validation_$(date +%Y%m%d_%H%M%S).log"
export LOG_FILE
exec > >(tee "$LOG_FILE") 2>&1
log "INFO" "Log file: $LOG_FILE"
log "INFO" "Validation (vs ORBIT_simulated_bank.csv) started"

CF_DIR="$ROOT_DIR/04-configuration"
INV="$CF_DIR/inventory/hosts.ini"
VARS="$CF_DIR/inventory/host_software.yml"
CSV_FILE="${CSV_FILE:-$ROOT_DIR/ORBIT_simulated_bank.csv}"
[ ! -f "$CSV_FILE" ] && log "ERROR" "CSV not found: $CSV_FILE" && exit 1

log "INFO" "Generate inventory"
bash "$CF_DIR/inventory/generate_inventory.sh"

[ ! -f "$INV" ] && log "ERROR" "Inventory not generated. Deploy EC2 stacks first." && exit 1

export ROOT_DIR CSV_FILE
EXPECTED_FILE="$SCRIPT_DIR/expected_installation.yml"
export OUT_FILE="$EXPECTED_FILE"
python3 "$SCRIPT_DIR/generate_expected_from_csv.py"
[ ! -f "$EXPECTED_FILE" ] && log "ERROR" "Expected file not generated" && exit 1
log "INFO" "Expected (from CSV): $EXPECTED_FILE"

EXTRA_VARS="-e @$EXPECTED_FILE"
[ -f "$VARS" ] && EXTRA_VARS="$EXTRA_VARS -e @$VARS"
[ -n "${SSH_PRIVATE_KEY_FILE:-}" ] && [ -f "${SSH_PRIVATE_KEY_FILE:-}" ] && EXTRA_VARS="$EXTRA_VARS -e ansible_ssh_private_key_file=$SSH_PRIVATE_KEY_FILE"

export ANSIBLE_HOST_KEY_CHECKING=False
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

log "INFO" "Run validation playbook"
if ansible-playbook -i "$INV" $EXTRA_VARS "$SCRIPT_DIR/playbooks/validate_installation.yaml"; then
  log "INFO" "Validation finished OK. Full log: $LOG_FILE"
else
  log "WARN" "Validation finished with errors. Full log: $LOG_FILE"
  exit 1
fi
