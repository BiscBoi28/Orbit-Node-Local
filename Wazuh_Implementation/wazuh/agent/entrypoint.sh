#!/bin/bash
set -euo pipefail

OSSEC_CONF=/var/ossec/etc/ossec.conf
MANAGER_HOST="${WAZUH_MANAGER:-wazuh.manager}"
AGENT_NAME="${WAZUH_AGENT_NAME:-$(hostname)}"
AGENT_GROUP="${WAZUH_AGENT_GROUP:-default}"

TMP_CONF="$(mktemp)"
sed "s|MANAGER_IP|${MANAGER_HOST}|g; s|AGENT_NAME|${AGENT_NAME}|g" "${OSSEC_CONF}" > "${TMP_CONF}"
cat "${TMP_CONF}" > "${OSSEC_CONF}"
rm -f "${TMP_CONF}"

if [ -f /var/ossec/active-response/bin/orbit_action.sh ]; then
  chmod +x /var/ossec/active-response/bin/orbit_action.sh
fi

for _ in $(seq 1 60); do
  if bash -c ">/dev/tcp/${MANAGER_HOST}/1515" 2>/dev/null; then
    break
  fi
  sleep 5
done

if [ ! -s /var/ossec/etc/client.keys ]; then
  enrolled=0
  for _ in $(seq 1 30); do
    if /var/ossec/bin/agent-auth -m "${MANAGER_HOST}" -A "${AGENT_NAME}" -G "${AGENT_GROUP}"; then
      enrolled=1
      break
    fi
    sleep 5
  done

  if [ "${enrolled}" -ne 1 ]; then
    echo "Failed to enroll Wazuh agent with manager ${MANAGER_HOST}" >&2
    exit 1
  fi
fi

/var/ossec/bin/wazuh-control start

tail -F /var/ossec/logs/ossec.log
