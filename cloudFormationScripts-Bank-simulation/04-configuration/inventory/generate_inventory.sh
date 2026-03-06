#!/usr/bin/env bash
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
CONFIG="$ROOT_DIR/config/deployment.env"
OUT_FILE="$SCRIPT_DIR/hosts.ini"
CSV_FILE="${CSV_FILE:-$ROOT_DIR/ORBIT_simulated_bank.csv}"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$1] $2"; }

if [ ! -f "$CONFIG" ]; then
  log "ERROR" "Config not found: $CONFIG"
  exit 1
fi
# shellcheck source=../../config/deployment.env
source "$CONFIG"
export AWS_REGION AWS_PROFILE

# Resolve CSV path: if relative, make it relative to project root
[[ "$CSV_FILE" != /* ]] && CSV_FILE="$ROOT_DIR/ORBIT_simulated_bank.csv"
[ ! -f "$CSV_FILE" ] && log "ERROR" "CSV not found: $CSV_FILE" && exit 1

get_output() {
  aws cloudformation describe-stacks --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text 2>/dev/null || echo ""
}

stacks=$(aws cloudformation list-stacks --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE \
  --query "StackSummaries[?starts_with(StackName,'$EC2_STACK_PREFIX-')].StackName" --output text 2>/dev/null)

: > "$OUT_FILE"
echo "[linux_rhel]" >> "$OUT_FILE"
echo "[linux_ubuntu]" >> "$OUT_FILE"
echo "[windows]" >> "$OUT_FILE"

export CSV_PATH="$CSV_FILE"
csv_os() {
  local aid="$1"
  python3 -c "
import csv, os, sys
path = os.environ.get('CSV_PATH','')
aid = sys.argv[1] if len(sys.argv) > 1 else ''
if not path or not aid: sys.exit(1)
with open(path) as f:
  for r in csv.DictReader(f):
    row_aid = (r.get('Asset_ID') or '').strip()
    if row_aid and row_aid.lower() == aid.lower():
      os = (r.get('Operating_System') or '').lower()
      if 'rhel' in os or 'red hat' in os: print('rhel')
      elif 'ubuntu' in os: print('ubuntu')
      elif 'windows' in os: print('windows')
      else: print('rhel')
      break
" "$aid" 2>/dev/null
}

use_ssm="${USE_SSM:-false}"
ssm_bucket="${SSM_BUCKET_NAME:-$(get_output "$PRE_REQ_STACK" SSMBucketName)}"
tmp=$(mktemp)
echo "[linux_rhel]" > "$tmp"
for stack in $stacks; do
  [ -z "$stack" ] && continue
  asset_id=$(echo "$stack" | sed "s/^${EC2_STACK_PREFIX}-//")
  os_type=$(csv_os "$asset_id")
  [ "$os_type" != "rhel" ] && continue
  pub_ip=$(get_output "$stack" PublicIp)
  hostname=$(get_output "$stack" Hostname)
  instance_id=$(get_output "$stack" InstanceId)
  if [ "$use_ssm" = "true" ] && [ -n "$instance_id" ]; then
    line="${hostname:-$asset_id} ansible_host=$instance_id ansible_connection=community.aws.aws_ssm ansible_user=ec2-user ansible_aws_ssm_region=${AWS_REGION:-us-east-1} ansible_remote_tmp=/tmp/.ansible_tmp"
    [ -n "$ssm_bucket" ] && line="$line ansible_aws_ssm_bucket_name=$ssm_bucket"
    echo "$line" >> "$tmp"
  else
    [ -z "$pub_ip" ] && continue
    echo "${hostname:-$asset_id} ansible_host=$pub_ip ansible_user=ec2-user" >> "$tmp"
  fi
done
echo "[linux_ubuntu]" >> "$tmp"
for stack in $stacks; do
  [ -z "$stack" ] && continue
  asset_id=$(echo "$stack" | sed "s/^${EC2_STACK_PREFIX}-//")
  os_type=$(csv_os "$asset_id")
  [ "$os_type" != "ubuntu" ] && continue
  pub_ip=$(get_output "$stack" PublicIp)
  hostname=$(get_output "$stack" Hostname)
  instance_id=$(get_output "$stack" InstanceId)
  if [ "$use_ssm" = "true" ] && [ -n "$instance_id" ]; then
    line="${hostname:-$asset_id} ansible_host=$instance_id ansible_connection=community.aws.aws_ssm ansible_user=ubuntu ansible_aws_ssm_region=${AWS_REGION:-us-east-1} ansible_remote_tmp=/tmp/.ansible_tmp"
    [ -n "$ssm_bucket" ] && line="$line ansible_aws_ssm_bucket_name=$ssm_bucket"
    echo "$line" >> "$tmp"
  else
    [ -z "$pub_ip" ] && continue
    echo "${hostname:-$asset_id} ansible_host=$pub_ip ansible_user=ubuntu" >> "$tmp"
  fi
done
echo "[windows]" >> "$tmp"
for stack in $stacks; do
  [ -z "$stack" ] && continue
  asset_id=$(echo "$stack" | sed "s/^${EC2_STACK_PREFIX}-//")
  os_type=$(csv_os "$asset_id")
  [ "$os_type" != "windows" ] && continue
  pub_ip=$(get_output "$stack" PublicIp)
  hostname=$(get_output "$stack" Hostname)
  instance_id=$(get_output "$stack" InstanceId)
  if [ "$use_ssm" = "true" ] && [ -n "$instance_id" ]; then
    line="${hostname:-$asset_id} ansible_host=$instance_id ansible_connection=community.aws.aws_ssm ansible_user=Administrator ansible_aws_ssm_region=${AWS_REGION:-us-east-1} ansible_remote_tmp=C:\\Windows\\Temp\\.ansible_tmp"
    [ -n "$ssm_bucket" ] && line="$line ansible_aws_ssm_bucket_name=$ssm_bucket"
    echo "$line" >> "$tmp"
  else
    [ -z "$pub_ip" ] && continue
    echo "${hostname:-$asset_id} ansible_host=$pub_ip ansible_user=Administrator ansible_connection=winrm ansible_winrm_transport=ntlm" >> "$tmp"
  fi
done
mv "$tmp" "$OUT_FILE"

# Generate host software vars from CSV for Ansible
SOFTWARE_VARS="$SCRIPT_DIR/host_software.yml"
export CSV_PATH="$CSV_FILE" SOFTWARE_VARS="$SOFTWARE_VARS"
python3 << 'PY'
import csv, os
path = os.environ.get("CSV_PATH", "")
out = os.environ.get("SOFTWARE_VARS", "")
if not path or not out:
    exit(0)
with open(path) as f:
    rdr = csv.DictReader(f)
    data = {}
    for r in rdr:
        host = (r.get("Hostname") or "").strip()
        sw = (r.get("OpenSource_Software_To_Install") or "").strip().strip('"')
        if host:
            data[host] = sw
with open(out, "w") as w:
    w.write("---\nhost_software:\n")
    for h, s in data.items():
        w.write("  %s: \"%s\"\n" % (h, s.replace('"', '\\"')))
PY
[ -f "$SOFTWARE_VARS" ] && log "INFO" "Generated $SOFTWARE_VARS"

log "INFO" "Generated $OUT_FILE"
