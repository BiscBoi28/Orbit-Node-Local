#!/bin/bash
# Deploy Wazuh to EC2 instance

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

# Check if we can connect with default key
echo "Checking SSH connection..."
if ! ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$EC2_IP "echo 'SSH OK'" 2>/dev/null; then
    echo ""
    echo "ERROR: Cannot connect to EC2 instance via SSH"
    echo "Please ensure:"
    echo "1. Your SSH public key is added to the EC2 instance"
    echo "2. Or update inventory/ec2.yml with the correct SSH key path"
    echo ""
    echo "To add your public key to EC2, run:"
    echo "  aws ec2-instance-connect send-ssh-public-key --instance-id <INSTANCE_ID> --instance-os-user ubuntu --ssh-public-key file://~/.ssh/id_ed25519.pub --region us-east-1"
    echo ""
    echo "Or use AWS Systems Manager Session Manager to add your key:"
    echo "  aws ssm start-session --target <INSTANCE_ID>"
    echo "  Then run: echo '$(cat ~/.ssh/id_ed25519.pub)' >> ~/.ssh/authorized_keys"
    exit 1
fi

echo "Testing connection to EC2..."
ANSIBLE_HOST_KEY_CHECKING=False ansible -i inventory/ec2.yml wazuh_server -m ping

echo "Running Wazuh installation playbook (EC2)..."
ANSIBLE_HOST_KEY_CHECKING=False ansible-playbook -i inventory/ec2.yml install-wazuh.yml

echo ""
echo "Installation complete!"
echo "Dashboard: https://$EC2_IP"
echo "Username: admin"
echo "Password: SecretPassword"
