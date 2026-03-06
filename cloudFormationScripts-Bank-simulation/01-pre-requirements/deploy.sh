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

if [ -z "${LOG_FILE:-}" ]; then
  LOG_DIR="$ROOT_DIR/logs"
  mkdir -p "$LOG_DIR"
  LOG_FILE="$LOG_DIR/pre-requirements_$(date +%Y%m%d_%H%M%S).log"
  export LOG_FILE
  exec > >(tee "$LOG_FILE") 2>&1
  log "INFO" "Log file: $LOG_FILE"
fi

CMD="${1:-}"
case "$CMD" in
  create)
    log "INFO" "Creating stack $PRE_REQ_STACK"
    aws cloudformation deploy \
      --template-file "$SCRIPT_DIR/pre-requirements.yaml" \
      --stack-name "$PRE_REQ_STACK" \
      --parameter-overrides \
        "AdminCIDR=$ADMIN_CIDR" \
        "WazuhServerIp=${WAZUH_SERVER_IP:-}" \
      --capabilities CAPABILITY_NAMED_IAM \
      --no-fail-on-empty-changeset
    aws cloudformation wait stack-create-complete --stack-name "$PRE_REQ_STACK"
    log "INFO" "Stack $PRE_REQ_STACK CREATE_COMPLETE"
    ;;
  delete)
    log "INFO" "Deleting stack $PRE_REQ_STACK"
    aws cloudformation delete-stack --stack-name "$PRE_REQ_STACK"
    aws cloudformation wait stack-delete-complete --stack-name "$PRE_REQ_STACK"
    log "INFO" "Stack $PRE_REQ_STACK deleted"
    ;;
  status)
    aws cloudformation describe-stacks --stack-name "$PRE_REQ_STACK" \
      --query 'Stacks[0].{Status:StackStatus,Outputs:Outputs}' --output table 2>/dev/null || log "WARN" "Stack $PRE_REQ_STACK not found"
    ;;
  start|stop|restart)
    log "INFO" "Command $CMD not applicable for pre-requirements stack"
    ;;
  *)
    log "ERROR" "Usage: $0 create | delete | status"
    exit 1
    ;;
esac
