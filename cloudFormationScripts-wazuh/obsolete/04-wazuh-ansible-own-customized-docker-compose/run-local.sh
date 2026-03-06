#!/bin/bash
# Test Wazuh installation locally

set -e

echo "Installing uv (Python package manager)..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "Installing Ansible via uv..."
uv tool install ansible-core

echo "Installing Ansible collections..."
uv tool run --from ansible-core ansible-galaxy collection install community.docker

echo "Running Wazuh installation playbook (local)..."
echo "Note: You will be prompted for your sudo password"
uv tool run --from ansible-core ansible-playbook -i inventory/local.yml install-wazuh.yml --ask-become-pass

echo ""
echo "Installation complete!"
echo "Access Wazuh at: https://localhost"
echo "Username: admin"
echo "Password: SecretPassword"
