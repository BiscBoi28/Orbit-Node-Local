#!/usr/bin/env bash
# Run pre-requirements CloudFormation (01-pre-requirements)
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_SCRIPT="$ROOT_DIR/01-pre-requirements/deploy.sh"

if [ ! -x "$DEPLOY_SCRIPT" ]; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] Not found or not executable: $DEPLOY_SCRIPT"
  exit 1
fi

CMD="${1:-create}"
exec "$DEPLOY_SCRIPT" "$CMD"
