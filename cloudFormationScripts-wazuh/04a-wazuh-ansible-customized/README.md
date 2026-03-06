# Wazuh Customized Deployment via Ansible

Deploys Wazuh using official Docker images with customizations for EBS storage and memory settings.

## Customizations

1. **EBS Storage**: All Wazuh data stored on `/data` EBS volume instead of Docker named volumes
2. **Memory Settings**: Indexer configured with 2GB heap and 3GB memory limit

## Prerequisites

- EC2 instance with Docker installed (from step 03)
- EBS volume mounted at `/data` (from step 01)
- SSH access configured

## Usage

```bash
chmod +x run-ec2.sh
./run-ec2.sh
```

## What It Does

1. Stops any existing Wazuh containers
2. Clones official Wazuh Docker repository
3. Generates certificates using Wazuh's method
4. Modifies docker-compose.yml to:
   - Use bind mounts to `/data` instead of named volumes
   - Set indexer heap to 2GB
   - Set indexer memory limit to 3GB
5. Creates required directories on EBS volume
6. Deploys the stack

## Verify Data Location

After deployment:
```bash
ssh ubuntu@44.194.78.195 'df -h /data && du -sh /data/wazuh*'
```

## Access

- Dashboard: https://44.194.78.195
- Username: admin
- Password: SecretPassword
