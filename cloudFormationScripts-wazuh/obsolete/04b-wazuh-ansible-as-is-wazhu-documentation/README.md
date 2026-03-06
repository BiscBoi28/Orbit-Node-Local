# Wazuh Official Docker Deployment via Ansible

This follows the official Wazuh documentation:
https://documentation.wazuh.com/current/deployment-options/docker/wazuh-container.html#single-node-stack

## What This Does

1. Clones the official Wazuh Docker repository
2. Uses Wazuh's official docker-compose files
3. Generates certificates using Wazuh's method
4. Deploys the single-node stack

## Prerequisites

- EC2 instance with Docker installed
- SSH access configured

## Usage

```bash
chmod +x run-ec2.sh
./run-ec2.sh
```

## Access

After deployment:
- Dashboard: https://YOUR_EC2_IP
- Username: admin
- Password: SecretPassword

## Differences from 04-wazuh-ansible

- Uses Wazuh's official repository and configs
- No custom templates or modifications
- Follows documentation exactly
- Should work out of the box with proper Filebeat configuration
