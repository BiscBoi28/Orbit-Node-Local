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
LOG_FILE="$LOG_DIR/destroy_$(date +%Y%m%d_%H%M%S).log"
export LOG_FILE
exec > >(tee "$LOG_FILE") 2>&1
log "INFO" "Log file: $LOG_FILE"

# 1. EC2 stacks
log "INFO" "Step 01: EC2 stacks (started)"
"$ROOT_DIR/03-ec2/deploy.sh" delete
for stack in $(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE ROLLBACK_COMPLETE --query "StackSummaries[?starts_with(StackName,'$EC2_STACK_PREFIX-')].StackName" --output text 2>/dev/null); do
  [ -z "$stack" ] && continue
  aws cloudformation wait stack-delete-complete --stack-name "$stack" 2>/dev/null || true
done
log "INFO" "Step 01: EC2 stacks (completed)"

# 2. Secrets
log "INFO" "Step 02: Secrets (started)"
"$ROOT_DIR/02-secrets/deploy.sh" delete
log "INFO" "Step 02: Secrets (completed)"

# 3. Pre-requirements
log "INFO" "Step 03: Pre-requirements (started)"
"$ROOT_DIR/01-pre-requirements/deploy.sh" delete
log "INFO" "Step 03: Pre-requirements (completed)"

log "INFO" "Teardown complete"
