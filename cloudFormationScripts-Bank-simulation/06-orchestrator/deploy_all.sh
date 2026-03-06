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
LOG_FILE="$LOG_DIR/deploy_$(date +%Y%m%d_%H%M%S).log"
export LOG_FILE
exec > >(tee "$LOG_FILE") 2>&1
log "INFO" "Log file: $LOG_FILE"

# 1. Validate config
if [ -z "${WAZUH_SERVER_IP:-}" ]; then
  log "WARN" "WAZUH_SERVER_IP not set in config/deployment.env"
fi
if ! aws sts get-caller-identity >/dev/null 2>&1; then
  log "ERROR" "AWS credentials invalid"
  exit 1
fi

# 2. Pre-requirements
log "INFO" "Step 01: Pre-requirements (started)"
"$ROOT_DIR/01-pre-requirements/deploy.sh" create
aws cloudformation wait stack-create-complete --stack-name "$PRE_REQ_STACK"
log "INFO" "Step 01: Pre-requirements (completed)"

# 3. Secrets
log "INFO" "Step 02: Secrets (started)"
"$ROOT_DIR/02-secrets/deploy.sh" create
aws cloudformation wait stack-create-complete --stack-name "$SECRETS_STACK"
log "INFO" "Step 02: Secrets (completed)"

# 4. EC2
log "INFO" "Step 03: EC2 (started)"
"$ROOT_DIR/03-ec2/deploy.sh" create
for stack in $(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?starts_with(StackName,'$EC2_STACK_PREFIX-')].StackName" --output text 2>/dev/null); do
  [ -z "$stack" ] && continue
  aws cloudformation wait stack-create-complete --stack-name "$stack" 2>/dev/null || true
done
log "INFO" "Step 03: EC2 (completed)"

# 5. Inventory
log "INFO" "Step 04: Generate inventory (started)"
bash "$ROOT_DIR/04-configuration/inventory/generate_inventory.sh"
log "INFO" "Step 04: Generate inventory (completed)"

# 6. Configuration (install software + Wazuh)
log "INFO" "Step 04: Configuration (started)"
"$ROOT_DIR/04-configuration/run.sh" all
log "INFO" "Step 04: Configuration (completed)"

# 7. Deployment summary
DEPLOY_INFO="$ROOT_DIR/deployment-info.txt"
{
  echo "ORBIT Bank Simulation - Deployment Summary"
  echo "=========================================="
  echo "Generated: $(date)"
  echo ""
  for stack in $(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?starts_with(StackName,'$EC2_STACK_PREFIX-')].StackName" --output text 2>/dev/null); do
    [ -z "$stack" ] && continue
    hn=$(aws cloudformation describe-stacks --stack-name "$stack" --query "Stacks[0].Outputs[?OutputKey=='Hostname'].OutputValue" --output text 2>/dev/null)
    pub=$(aws cloudformation describe-stacks --stack-name "$stack" --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text 2>/dev/null)
    priv=$(aws cloudformation describe-stacks --stack-name "$stack" --query "Stacks[0].Outputs[?OutputKey=='PrivateIp'].OutputValue" --output text 2>/dev/null)
    echo "Asset: $stack | Hostname: $hn | Public: $pub | Private: $priv"
    echo "  SSH: ssh -i <key> ec2-user@$pub  (or ubuntu@$pub for Ubuntu)"
    echo ""
  done
  echo "Wazuh dashboard: https://${WAZUH_SERVER_IP:-<WAZUH_SERVER_IP>}"
} > "$DEPLOY_INFO"
log "INFO" "Deployment summary: $DEPLOY_INFO"
log "INFO" "Deployment run finished. Full log: $LOG_FILE"
