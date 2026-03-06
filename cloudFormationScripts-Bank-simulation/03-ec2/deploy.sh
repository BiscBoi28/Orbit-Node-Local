#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG="$ROOT_DIR/config/deployment.env"
CSV_FILE="${CSV_FILE:-$ROOT_DIR/ORBIT_simulated_bank.csv}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"; }

if [ ! -f "$CONFIG" ]; then
  log "ERROR" "Config not found: $CONFIG"
  exit 1
fi
# shellcheck source=../config/deployment.env
source "$CONFIG"
export AWS_REGION AWS_PROFILE
# Resolve CSV path: if relative or missing, use project root
if [[ "$CSV_FILE" != /* ]]; then
  CSV_FILE="$ROOT_DIR/ORBIT_simulated_bank.csv"
fi
if [ ! -f "$CSV_FILE" ]; then
  log "ERROR" "CSV not found: $CSV_FILE"
  exit 1
fi

if [ -z "${LOG_FILE:-}" ]; then
  LOG_DIR="$ROOT_DIR/logs"
  mkdir -p "$LOG_DIR"
  LOG_FILE="$LOG_DIR/ec2_$(date +%Y%m%d_%H%M%S).log"
  export LOG_FILE
  exec > >(tee "$LOG_FILE") 2>&1
  log "INFO" "Log file: $LOG_FILE"
fi

get_output() {
  aws cloudformation describe-stacks --stack-name "$PRE_REQ_STACK" --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text 2>/dev/null || echo ""
}

get_sg_list() {
  local role="$1"
  local sgs=""
  case "$role" in
    *Database*Server*)  sgs="${sgs:+$sgs,}$(get_output 'SGDatabase')"; ;;
    *Application*Server*) sgs="${sgs:+$sgs,}$(get_output 'SGAppServer')"; ;;
    *Web*Server*)       sgs="${sgs:+$sgs,}$(get_output 'SGWebServer')"; ;;
    *Active*Directory*) sgs="${sgs:+$sgs,}$(get_output 'SGActiveDirectory')"; ;;
    *Jump*Host*)        sgs="${sgs:+$sgs,}$(get_output 'SGJumpHost')"; ;;
  esac
  echo "$sgs" | sed 's/^,//'
}

roles_to_sgs() {
  local IFS=,
  local list=""
  for r in $1; do
    r=$(echo "$r" | xargs)
    [ -z "$r" ] && continue
    case "$r" in
      *Database*Server*)  list="${list:+$list,}$(get_output 'SGDatabase')"; ;;
      *Application*Server*) list="${list:+$list,}$(get_output 'SGAppServer')"; ;;
      *Web*Server*)       list="${list:+$list,}$(get_output 'SGWebServer')"; ;;
      *Active*Directory*) list="${list:+$list,}$(get_output 'SGActiveDirectory')"; ;;
      *Jump*Host*)        list="${list:+$list,}$(get_output 'SGJumpHost')"; ;;
    esac
  done
  echo "$list" | sed 's/^,//;s/,,*/,/g'
}

os_to_template() {
  case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
    *rhel*8*|*linux*rhel*) echo "linux"; ;;
    *ubuntu*22*|*linux*ubuntu*) echo "linux"; ;;
    *windows*2022*|*windows*server*) echo "windows"; ;;
    *) echo "linux"; ;;
  esac
}

os_to_param() {
  case "$(echo "$1" | tr '[:upper:]' '[:lower:]')" in
    *rhel*8*|*linux*rhel*) echo "RHEL8"; ;;
    *ubuntu*22*|*linux*ubuntu*) echo "Ubuntu2204"; ;;
    *windows*2022*|*windows*server*) echo "WindowsServer2022"; ;;
    *) echo "RHEL8"; ;;
  esac
}

asset_id_lower() {
  echo "$1" | tr '[:upper:]' '[:lower:]'
}

parse_csv() {
  python3 << 'PY'
import csv, sys, os
path = os.environ.get("CSV_PATH", "")
if not path or not os.path.isfile(path):
    sys.exit(1)
with open(path) as f:
    for r in csv.DictReader(f):
        aid = (r.get("Asset_ID") or "").strip()
        if not aid: continue
        print("\t".join([
            aid,
            (r.get("Hostname") or "").strip(),
            (r.get("Operating_System") or "").strip(),
            (r.get("Instance_Size") or "t3.micro").strip(),
            (r.get("Technical_Role") or "").strip().strip('"'),
            (r.get("OpenSource_Software_To_Install") or "").strip().strip('"'),
        ]))
PY
}

do_create() {
  local target="${2:-}"
  local vpc sub profile
  vpc=$(get_output VpcId)
  sub=$(get_output PublicSubnetId)
  profile=$(get_output EC2InstanceProfileArn)
  if [ -z "$vpc" ] || [ -z "$sub" ] || [ -z "$profile" ]; then
    log "ERROR" "Pre-requirements stack outputs not found. Run 01-pre-requirements/deploy.sh create first."
    exit 1
  fi

  export CSV_PATH="$CSV_FILE"
  while IFS=$'\t' read -r asset_id hostname os size role software; do
    [ -z "$asset_id" ] && continue
    if [ -n "$target" ] && [ "$(asset_id_lower "$asset_id")" != "$(asset_id_lower "$target")" ]; then
      continue
    fi
    stack_name="${EC2_STACK_PREFIX}-$(asset_id_lower "$asset_id")"
    tmpl=$(os_to_template "$os")
    os_param=$(os_to_param "$os")
    sgs=$(roles_to_sgs "$role")
    if [ -z "$sgs" ]; then
      sgs=$(get_output 'SGJumpHost')
    fi
    [ -z "$sgs" ] && sgs=$(get_output 'SGWebServer')
    log "INFO" "Deploying $stack_name ($tmpl)"
    params=(
      "AssetID=$asset_id"
      "Hostname=$hostname"
      "TechnicalRole=$role"
      "OperatingSystem=$os_param"
      "InstanceType=${size:-t3.micro}"
      "SoftwarePackages=$software"
      "VpcId=$vpc"
      "SubnetId=$sub"
      "InstanceProfileArn=$profile"
      "KeyPairName=$KEY_PAIR_NAME"
      "WazuhServerIP=${WAZUH_SERVER_IP:-}"
      "WazuhPort=${WAZUH_SERVER_PORT:-1514}"
      "SecurityGroupIds=$sgs"
    )
    if [ "$tmpl" = "windows" ]; then
      admin_pass=$(aws secretsmanager get-secret-value --secret-id njsecure-prod/windows/admin --query SecretString --output text 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('password',''))" 2>/dev/null || true)
      params+=("AdminPassword=${admin_pass:-}")
    fi
    aws cloudformation deploy \
      --template-file "$SCRIPT_DIR/templates/${tmpl}.yaml" \
      --stack-name "$stack_name" \
      --parameter-overrides "${params[@]}" \
      --capabilities CAPABILITY_NAMED_IAM \
      --no-fail-on-empty-changeset &
  done < <(parse_csv)
  wait
  for s in $(parse_csv | cut -f1); do
    [ -z "$s" ] && continue
    if [ -n "$target" ] && [ "$(asset_id_lower "$s")" != "$(asset_id_lower "$target")" ]; then continue; fi
    stack_name="${EC2_STACK_PREFIX}-$(asset_id_lower "$s")"
    aws cloudformation wait stack-create-complete --stack-name "$stack_name" 2>/dev/null || true
  done
  log "INFO" "EC2 create finished"
}

do_delete() {
  local target="${2:-}"
  local stacks
  if [ -n "$target" ]; then
    stacks="${EC2_STACK_PREFIX}-$(asset_id_lower "$target")"
  else
    stacks=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query "StackSummaries[?starts_with(StackName,'$EC2_STACK_PREFIX-')].StackName" --output text 2>/dev/null || true)
  fi
  for s in $stacks; do
    [ -z "$s" ] && continue
    log "INFO" "Deleting stack $s"
    aws cloudformation delete-stack --stack-name "$s" &
  done
  wait
  for s in $stacks; do
    [ -z "$s" ] && continue
    aws cloudformation wait stack-delete-complete --stack-name "$s" 2>/dev/null || true
  done
  log "INFO" "EC2 delete finished"
}

do_start() {
  local target="${2:-}"
  local ids
  if [ -n "$target" ]; then
    out=$(aws cloudformation describe-stacks --stack-name "${EC2_STACK_PREFIX}-$(asset_id_lower "$target")" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text 2>/dev/null)
    ids=$out
  else
    ids=$(aws ec2 describe-instances --filters "Name=tag:Project,Values=ORBIT" "Name=instance-state-name,Values=stopped" --query "Reservations[].Instances[].InstanceId" --output text 2>/dev/null)
  fi
  for id in $ids; do
    [ -z "$id" ] && continue
    aws ec2 start-instances --instance-ids "$id"
    log "INFO" "Started $id"
  done
}

do_stop() {
  local target="${2:-}"
  local ids
  if [ -n "$target" ]; then
    out=$(aws cloudformation describe-stacks --stack-name "${EC2_STACK_PREFIX}-$(asset_id_lower "$target")" --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text 2>/dev/null)
    ids=$out
  else
    ids=$(aws ec2 describe-instances --filters "Name=tag:Project,Values=ORBIT" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text 2>/dev/null)
  fi
  for id in $ids; do
    [ -z "$id" ] && continue
    aws ec2 stop-instances --instance-ids "$id"
    log "INFO" "Stopped $id"
  done
}

do_status() {
  aws ec2 describe-instances --filters "Name=tag:Project,Values=ORBIT" \
    --query "Reservations[].Instances[].[Tags[?Key=='Name']|[0].Value,InstanceId,State.Name,PublicIpAddress,PrivateIpAddress]" \
    --output table 2>/dev/null || log "WARN" "No instances found"
}

CMD="${1:-}"
case "$CMD" in
  create)  do_create "$@" ;;
  delete)  do_delete "$@" ;;
  start)   do_start "$@" ;;
  stop)    do_stop "$@" ;;
  restart) do_stop "$@"; sleep 10; do_start "$@" ;;
  status)  do_status ;;
  *)
    log "ERROR" "Usage: $0 create [asset_id] | delete [asset_id] | start | stop | restart | status"
    exit 1
    ;;
esac
