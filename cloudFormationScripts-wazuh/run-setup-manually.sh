#!/bin/bash
# Manually run Wazuh setup on EC2 instance

echo "Downloading and running Wazuh setup script..."

ssh ubuntu@44.194.78.195 << 'ENDSSH'
# Download script from S3
aws s3 cp s3://orbit-wazuh-scripts/wazuh-setup.sh /data/scripts/wazuh-setup.sh
chmod +x /data/scripts/wazuh-setup.sh

# Run setup
sudo bash /data/scripts/wazuh-setup.sh 2>&1 | tee /var/log/wazuh-setup.log
ENDSSH

echo "Setup complete. Check https://44.194.78.195"
