#!/bin/bash
# Deploy Wazuh with EBS storage and custom memory settings

set -e

if [ ! -f inventory/ec2.yml ]; then
    echo "Error: inventory/ec2.yml not found"
    exit 1
fi

# SSH key: env, then inventory, then common key paths (must match EC2 key pair)
SSH_KEY="${SSH_PRIVATE_KEY_FILE:-}"
if [ -z "$SSH_KEY" ]; then
    INV_KEY=$(grep ansible_ssh_private_key_file inventory/ec2.yml | sed 's/.*: *//;s/^ *//;s#~#'"$HOME"'#' | sed "s/^['\"]//;s/['\"]$//" | tr -d '\n\r')
    if [ -n "$INV_KEY" ] && [ -f "$INV_KEY" ]; then
        SSH_KEY="$INV_KEY"
    fi
fi
if [ -z "$SSH_KEY" ]; then
    for k in "$HOME/.ssh/id_ed25519" "$HOME/.ssh/id_rsa"; do
        if [ -f "$k" ]; then
            SSH_KEY="$k"
            break
        fi
    done
fi
if [ -z "$SSH_KEY" ] || [ ! -f "$SSH_KEY" ]; then
    echo "Error: No SSH private key found. Use the key pair you used when launching the EC2 instance."
    echo "  Put your .pem key in ~/.ssh/ and set: export SSH_PRIVATE_KEY_FILE=~/.ssh/iiith-orbit-key.pem"
    echo "  Or set ansible_ssh_private_key_file in inventory/ec2.yml to the key path."
    echo "  Or add: ~/.ssh/id_ed25519 or ~/.ssh/id_rsa"
    if [ -n "$INV_KEY" ] && [ -z "$SSH_KEY" ]; then
        echo "  (Inventory points to: $INV_KEY — file not found)"
    fi
    exit 1
fi
echo "Using SSH key: $SSH_KEY"

# Get EC2 IP from inventory
EC2_IP=$(grep ansible_host inventory/ec2.yml | awk '{print $2}')

echo "Installing uv (Python package manager)..."
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
# Ensure uv is on PATH (installer may have just added it to ~/.local/bin)
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

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

echo "Running Wazuh installation playbook (Customized with EBS + Memory)..."
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory/ec2.yml install-wazuh-customized.yml -e "ansible_ssh_private_key_file=$SSH_KEY"

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo "Dashboard: https://$EC2_IP"
echo "Username: admin"
echo "Password: SecretPassword"
echo ""
echo "Customizations:"
echo "- Data stored on EBS volume: /data"
echo "- Indexer heap size: 2GB"
echo "- Indexer memory limit: 3GB"
echo ""
echo "Verify data location:"
echo "  ssh ubuntu@$EC2_IP 'df -h /data && du -sh /data/wazuh*'"
