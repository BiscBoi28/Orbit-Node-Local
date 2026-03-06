#!/bin/bash
# Setup SSH access to EC2 instance

set -e

# Get instance ID
INSTANCE_ID=$(aws ec2 describe-instances --filters "Name=tag:Name,Values=orbit-node-poc" "Name=instance-state-name,Values=running" --region us-east-1 --query 'Reservations[0].Instances[0].InstanceId' --output text)

if [ "$INSTANCE_ID" == "None" ] || [ -z "$INSTANCE_ID" ]; then
    echo "Error: No running EC2 instance found with tag Name=orbit-node-poc"
    exit 1
fi

echo "Found instance: $INSTANCE_ID"
echo "Adding your SSH public key..."

# Get your public key
if [ -f ~/.ssh/id_ed25519.pub ]; then
    PUB_KEY=$(cat ~/.ssh/id_ed25519.pub)
elif [ -f ~/.ssh/id_rsa.pub ]; then
    PUB_KEY=$(cat ~/.ssh/id_rsa.pub)
else
    echo "Error: No SSH public key found"
    echo "Generate one with: ssh-keygen -t ed25519"
    exit 1
fi

# Add key using SSM
echo "Connecting via AWS Systems Manager..."
aws ssm send-command \
    --instance-ids "$INSTANCE_ID" \
    --document-name "AWS-RunShellScript" \
    --parameters "commands=[\"echo '$PUB_KEY' >> /home/ubuntu/.ssh/authorized_keys\",\"chmod 600 /home/ubuntu/.ssh/authorized_keys\",\"chown ubuntu:ubuntu /home/ubuntu/.ssh/authorized_keys\"]" \
    --region us-east-1 \
    --output text

echo ""
echo "SSH key added successfully!"
echo "You can now run: ./run-ec2.sh"
