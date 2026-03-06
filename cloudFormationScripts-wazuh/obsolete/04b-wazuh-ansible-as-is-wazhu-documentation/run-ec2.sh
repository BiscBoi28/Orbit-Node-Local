#!/bin/bash
# Deploy Wazuh using official documentation method

set -e

if [ ! -f inventory/ec2.yml ]; then
    echo "Error: inventory/ec2.yml not found"
    exit 1
fi

# Get EC2 IP from inventory
EC2_IP=$(grep ansible_host inventory/ec2.yml | awk '{print $2}')

echo "Installing uv (Python package manager)..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "Setting up Python virtual environment..."
if [ ! -d .venv ]; then
    uv venv .venv
    source .venv/bin/activate
    uv pip install ansible-core requests docker
else
    source .venv/bin/activate
fi

echo "Installing Ansible collections..."
ansible-galaxy collection install community.docker

echo "Removing old SSH host key for $EC2_IP..."
ssh-keygen -R $EC2_IP 2>/dev/null || true

echo "Running Wazuh installation playbook (Official Method)..."
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory/ec2.yml install-wazuh-official.yml

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo "Dashboard: https://$EC2_IP"
echo "Username: admin"
echo "Password: SecretPassword"
echo ""
echo "This installation follows:"
echo "https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html#single-node-stack"
