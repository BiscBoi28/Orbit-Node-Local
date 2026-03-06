#!/usr/bin/env bash
# Run EC2 CloudFormation (03-ec2) - deploys instances from ORBIT_simulated_bank.csv
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_SCRIPT="$ROOT_DIR/03-ec2/deploy.sh"

if [ ! -x "$DEPLOY_SCRIPT" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] Not found or not executable: $DEPLOY_SCRIPT"
  exit 1
fi

exec "$DEPLOY_SCRIPT" "$@"
