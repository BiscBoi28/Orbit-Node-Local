#!/bin/sh
set -eu

ACTION="${1:-unknown}"
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOSTNAME="$(hostname)"
LOG_FILE="/var/ossec/logs/active-responses.log"

cat >/dev/null 2>&1 || true
printf '%s ORBIT: %s triggered on %s\n' "${STAMP}" "${ACTION}" "${HOSTNAME}" >> "${LOG_FILE}"

exit 0
