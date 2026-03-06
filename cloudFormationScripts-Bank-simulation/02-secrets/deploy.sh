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
  LOG_FILE="$LOG_DIR/secrets_$(date +%Y%m%d_%H%M%S).log"
  export LOG_FILE
  exec > >(tee "$LOG_FILE") 2>&1
  log "INFO" "Log file: $LOG_FILE"
fi

CMD="${1:-}"
case "$CMD" in
  create)
    log "INFO" "Creating stack $SECRETS_STACK"
    aws cloudformation deploy \
      --template-file "$SCRIPT_DIR/secrets.yaml" \
      --stack-name "$SECRETS_STACK" \
      --parameter-overrides \
        "WazuhServerIp=${WAZUH_SERVER_IP:-}" \
        "WazuhPort=${WAZUH_SERVER_PORT:-1514}" \
        "WazuhAgentGroup=${WAZUH_AGENT_GROUP:-bank-simulation}" \
        "KeyPairName=${KEY_PAIR_NAME:-}" \
      --no-fail-on-empty-changeset
    aws cloudformation wait stack-create-complete --stack-name "$SECRETS_STACK"
    log "INFO" "Stack $SECRETS_STACK CREATE_COMPLETE"
    ;;
  delete)
    log "INFO" "Deleting stack $SECRETS_STACK"
    aws cloudformation delete-stack --stack-name "$SECRETS_STACK"
    aws cloudformation wait stack-delete-complete --stack-name "$SECRETS_STACK"
    log "INFO" "Stack $SECRETS_STACK deleted"
    ;;
  status)
    if aws cloudformation describe-stacks --stack-name "$SECRETS_STACK" --query 'Stacks[0].Outputs' --output table 2>/dev/null; then
      log "INFO" "Secrets ARNs above (values not shown)"
    else
      log "WARN" "Stack $SECRETS_STACK not found"
    fi
    ;;
  start|stop|restart)
    log "INFO" "Command $CMD not applicable for secrets stack"
    ;;
  *)
    log "ERROR" "Usage: $0 create | delete | status"
    exit 1
    ;;
esac
