#!/bin/sh

ACTION="${1:-ADD}"
REQUEST_USER="${2:-orbit-orc}"
REQUEST_IP="${3:-127.0.0.1}"
CUSTOM_ARGS="${4:-::::}"
INPUT_JSON=""
IFS= read -r INPUT_JSON || INPUT_JSON=""
STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOSTNAME="$(hostname)"
RESULT_LOG="/var/ossec/logs/orbit_ar.log"
SHARED_RESULT_LOG="/var/ossec/active-response/bin/orbit_ar.log"

parse_custom_args() {
  ACTION_TYPE="${CUSTOM_ARGS%%::*}"
  REST="${CUSTOM_ARGS#*::}"

  if [ "${REST}" = "${CUSTOM_ARGS}" ]; then
    ACTION_CARD_ID=""
    HOST_ID=""
  else
    ACTION_CARD_ID="${REST%%::*}"
    HOST_ID="${REST#*::}"
    if [ "${HOST_ID}" = "${REST}" ]; then
      HOST_ID=""
    fi
  fi
}

json_escape() {
  printf '%s' "${1:-}" | sed 's/\\/\\\\/g; s/"/\\"/g'
}

if [ -n "${INPUT_JSON}" ]; then
  PARSED="$(
    INPUT_JSON_ENV="${INPUT_JSON}" python3 - "${ACTION}" "${REQUEST_USER}" "${REQUEST_IP}" "${CUSTOM_ARGS}" 2>/dev/null <<'PY'
import json
import os
import sys

action, user, ip, custom = sys.argv[1:5]
action_type = ""
action_card_id = ""
host_id = ""

raw = os.environ.get("INPUT_JSON_ENV", "").strip()
message = json.loads(raw)
command = str(message.get("command", "")).lower()
if command == "add":
    action = "ADD"
elif command == "delete":
    action = "DELETE"

params = message.get("parameters") or {}
extra_args = params.get("extra_args") or []
if len(extra_args) > 1 and extra_args[1]:
    user = str(extra_args[1])
if len(extra_args) > 2 and extra_args[2]:
    ip = str(extra_args[2])
if len(extra_args) > 3 and extra_args[3]:
    custom = str(extra_args[3])

alert = params.get("alert") or {}
alert_data = alert.get("data") if isinstance(alert, dict) else {}
if not isinstance(alert_data, dict):
    alert_data = {}

if custom:
    parts = custom.split("::", 2)
    if len(parts) > 0:
        action_type = parts[0]
    if len(parts) > 1:
        action_card_id = parts[1]
    if len(parts) > 2:
        host_id = parts[2]

if not action_type:
    action_type = str(alert_data.get("action_type", ""))
if not action_card_id:
    action_card_id = str(alert_data.get("action_id", ""))
if not host_id:
    host_id = str(alert_data.get("host_id", ""))

print(action)
print(user)
print(ip)
print(custom)
print(action_type)
print(action_card_id)
print(host_id)
PY
  )"

  if [ -n "${PARSED}" ]; then
    ACTION="$(printf '%s\n' "${PARSED}" | sed -n '1p')"
    REQUEST_USER="$(printf '%s\n' "${PARSED}" | sed -n '2p')"
    REQUEST_IP="$(printf '%s\n' "${PARSED}" | sed -n '3p')"
    CUSTOM_ARGS="$(printf '%s\n' "${PARSED}" | sed -n '4p')"
    ACTION_TYPE="$(printf '%s\n' "${PARSED}" | sed -n '5p')"
    ACTION_CARD_ID="$(printf '%s\n' "${PARSED}" | sed -n '6p')"
    HOST_ID="$(printf '%s\n' "${PARSED}" | sed -n '7p')"
  else
    parse_custom_args
  fi
else
  parse_custom_args
fi

PAYLOAD="$(printf '{"timestamp":"%s","status":"executed","action":"%s","user":"%s","ip":"%s","action_type":"%s","action_card_id":"%s","host_id":"%s","hostname":"%s"}' \
  "$(json_escape "${STAMP}")" \
  "$(json_escape "${ACTION}")" \
  "$(json_escape "${REQUEST_USER}")" \
  "$(json_escape "${REQUEST_IP}")" \
  "$(json_escape "${ACTION_TYPE}")" \
  "$(json_escape "${ACTION_CARD_ID}")" \
  "$(json_escape "${HOST_ID}")" \
  "$(json_escape "${HOSTNAME}")")"

# REPLACE THIS BLOCK FOR PRODUCTION
# Insert the real host isolation / remediation command here.
true

mkdir -p "$(dirname "${RESULT_LOG}")" >/dev/null 2>&1 || true
printf '%s\n' "${PAYLOAD}" >> "${RESULT_LOG}" 2>/dev/null || true
printf '%s\n' "${PAYLOAD}" >> "${SHARED_RESULT_LOG}" 2>/dev/null || true

logger -t orbit-action -- "ORBIT active response ${ACTION} ${ACTION_CARD_ID} ${HOST_ID}" >/dev/null 2>&1 || true

exit 0
