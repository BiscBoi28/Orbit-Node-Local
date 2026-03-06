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
LOG_FILE="$LOG_DIR/deploy_machine_2_$(date +%Y%m%d_%H%M%S).log"
export LOG_FILE
exec > >(tee "$LOG_FILE") 2>&1
log "INFO" "Log file: $LOG_FILE"

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  log "ERROR" "AWS credentials invalid"
  exit 1
fi

log "INFO" "Machine 2 (NS-02): EC2 ns-02 (started)"
"$ROOT_DIR/03-ec2/deploy.sh" create ns-02
aws cloudformation wait stack-create-complete --stack-name "${EC2_STACK_PREFIX}-ns-02" 2>/dev/null || true
log "INFO" "Machine 2 (NS-02): EC2 ns-02 (completed)"

log "INFO" "Machine 2 deploy finished. Log: $LOG_FILE"
