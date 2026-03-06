# ORBIT Node Deployment Runbook

## Overview

This runbook provides step-by-step instructions for deploying the ORBIT Node infrastructure on AWS using CloudFormation. The deployment consists of three stacks that must be deployed in order.

## Current Deployment Information

- **Elastic IP**: 44.194.78.195 (persistent across EC2 stack deletions)
- **Wazuh Dashboard**: https://44.194.78.195
- **Login**: admin / SecretPassword
- **Region**: us-east-1
- **S3 Bucket**: orbit-node-config-1770558079

---

## Prerequisites

### Required Tools
- AWS CLI configured with appropriate credentials
- Bash shell (macOS/Linux)
- jq (JSON processor)

### Required Permissions
- CloudFormation: Full access
- EC2: Full access
- IAM: Create/manage roles and instance profiles
- Secrets Manager: Create/read secrets
- S3: Read/write access to deployment bucket
- Systems Manager: Session Manager access (for troubleshooting)

---

## Deployment Architecture

The deployment is split into three CloudFormation stacks:

1. **Pre-Deployment Stack** (`orbit-node-pre-deployment`)
   - VPC, Subnet, Internet Gateway, Route Tables
   - Security Group
   - IAM Role and Instance Profile
   - EBS Volume for persistent data
   - Elastic IP (persists across EC2 deletions)

2. **Secrets Stack** (`orbit-node-secrets`)
   - Wazuh indexer credentials
   - Wazuh API credentials
   - Stored in AWS Secrets Manager

3. **EC2 Stack** (`orbit-node-ec2`)
   - EC2 instance (On-Demand or Spot)
   - EBS volume attachment
   - Elastic IP association
   - Automated Wazuh installation via UserData

---

## Configuration

Before deploying, review and update configuration files as needed. See [CONFIGURATION.md](CONFIGURATION.md) for detailed configuration options.

### Quick Configuration Checklist

1. **Tags** (MANDATORY): Update in all CloudFormation templates
   - `project`: Your project name
   - `created_by`: Your identifier
   - `resource_type`: Environment (dev/staging/prod)

2. **Stack Names** (MANDATORY): Update if deploying multiple environments
   - Pre-deployment: `orbit-node-pre-deployment`
   - Secrets: `orbit-node-secrets`
   - EC2: `orbit-node-ec2`

3. **S3 Bucket** (MANDATORY): Update in deployment scripts
   - Default: `orbit-node-config-1770558079`
   - Update in: `03-ec2-deployment/deploy-ec2-stack.sh`

4. **Region** (MANDATORY): Ensure consistency across all resources
   - Default: `us-east-1`

---

## Deployment Steps

### Step 1: Deploy Pre-Deployment Stack

This creates the foundational infrastructure including VPC, security groups, IAM roles, EBS volume, and Elastic IP.

```bash
cd 01-pre-deployment
bash create-pre-deployment-stack.sh
```

**Expected Output:**
- Stack creation takes ~3-5 minutes
- Outputs: VPC ID, Subnet ID, Security Group ID, IAM Profile ARN, EBS Volume ID, Elastic IP, Elastic IP Allocation ID

**Verify:**
```bash
aws cloudformation describe-stacks --stack-name orbit-node-pre-deployment --query 'Stacks[0].Outputs'
```

---

### Step 2: Deploy Secrets Stack

This creates the secrets in AWS Secrets Manager for Wazuh authentication.

```bash
cd 02-secrets
bash create-secrets-stack.sh
```

**Expected Output:**
- Stack creation takes ~1-2 minutes
- Creates two secrets:
  - `orbit/node/wazuh-indexer-credentials`
  - `orbit/node/wazuh-api-credentials`

**Verify:**
```bash
aws cloudformation describe-stacks --stack-name orbit-node-secrets --query 'Stacks[0].StackStatus'
```

---

### Step 3: Deploy EC2 Stack

This deploys the EC2 instance with Docker installed and EBS volume mounted at `/data`.

```bash
cd 03-ec2-deployment
bash deploy-ec2-stack.sh
```

**What This Script Does:**
1. Fetches outputs from pre-deployment stack
2. Generates deployment parameters
3. Deploys CloudFormation stack with EC2 instance
4. Installs Docker and mounts EBS volume

**Expected Output:**
- Stack creation takes ~5-7 minutes
- Outputs: Instance ID, Public IP, SSH command

**Verify:**
```bash
aws cloudformation describe-stacks --stack-name orbit-node-ec2 --query 'Stacks[0].Outputs'
```

---

### Step 4: Deploy Wazuh via Ansible

This installs Wazuh using official Docker images with customizations for EBS storage and memory settings.

```bash
cd 04a-wazuh-ansible-customized
bash run-ec2.sh
```

**What This Script Does:**
1. Sets up Python virtual environment with Ansible
2. Stops any existing Wazuh containers
3. Clones official Wazuh Docker repository
4. Customizes docker-compose.yml to use EBS storage at `/data`
5. Sets indexer memory to 2GB heap with 3GB limit
6. Deploys Wazuh stack

**Expected Output:**
- Ansible playbook execution takes ~5-10 minutes
- All Wazuh containers start successfully
- Dashboard becomes accessible

**Verify Wazuh is Running:**
```bash
# Check containers
ssh ubuntu@<ELASTIC_IP> "docker ps --filter name=wazuh"

# Check data on EBS volume
ssh ubuntu@<ELASTIC_IP> "df -h /data && du -sh /data/wazuh*"

# Check alerts index
ssh ubuntu@<ELASTIC_IP> "curl -sk -u admin:SecretPassword https://localhost:9200/_cat/indices?v | grep alert"
```

---

### Step 5: Access Wazuh Dashboard

Once deployment is complete:

1. **Get Public IP:**
   ```bash
   aws cloudformation describe-stacks --stack-name orbit-node-ec2 \
     --query 'Stacks[0].Outputs[?OutputKey==`NodePublicIp`].OutputValue' --output text
   ```

2. **Access Dashboard:**
   - URL: `https://<PUBLIC_IP>`
   - Username: `admin`
   - Password: `SecretPassword`

3. **Accept Self-Signed Certificate:**
   - Browser will show security warning (expected)
   - Proceed to site (safe for POC environments)

---

### Step 6: Register Agents

To register endpoints as Wazuh agents:

1. **Update Configuration:**
   ```bash
   cd 05-agent-registration
   # Edit config.sh and set WAZUH_MANAGER to your Elastic IP
   nano config.sh
   ```

2. **Run Registration Script:**
   ```bash
   bash register-agent.sh
   ```

3. **Verify in Dashboard:**
   - Login to Wazuh dashboard
   - Navigate to Agents section
   - Confirm agent appears with "Active" status

---

## Deployment with Assumed Role

If deploying with an assumed IAM role:

```bash
# Assume role
aws sts assume-role \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME \
  --role-session-name deployment-session \
  --output json > /tmp/credentials.json

# Export credentials
export AWS_ACCESS_KEY_ID=$(jq -r .Credentials.AccessKeyId /tmp/credentials.json)
export AWS_SECRET_ACCESS_KEY=$(jq -r .Credentials.SecretAccessKey /tmp/credentials.json)
export AWS_SESSION_TOKEN=$(jq -r .Credentials.SessionToken /tmp/credentials.json)

# Proceed with deployment steps
cd 01-pre-deployment
bash create-pre-deployment-stack.sh
# ... continue with remaining steps
```

---

## Stack Management

### Update Existing Stack

To update an existing stack with configuration changes:

```bash
# Pre-deployment stack
cd 01-pre-deployment
bash create-pre-deployment-stack.sh  # Script handles update automatically

# Secrets stack
cd 02-secrets
bash create-secrets-stack.sh  # Script handles update automatically

# EC2 stack
cd 03-ec2-deployment
bash deploy-ec2-stack.sh  # Script handles update automatically
```

### Delete Stacks

Delete in reverse order to avoid dependency issues:

```bash
# Delete EC2 stack (Elastic IP persists)
aws cloudformation delete-stack --stack-name orbit-node-ec2
aws cloudformation wait stack-delete-complete --stack-name orbit-node-ec2

# Delete secrets stack
aws cloudformation delete-stack --stack-name orbit-node-secrets
aws cloudformation wait stack-delete-complete --stack-name orbit-node-secrets

# Delete pre-deployment stack (includes Elastic IP)
aws cloudformation delete-stack --stack-name orbit-node-pre-deployment
aws cloudformation wait stack-delete-complete --stack-name orbit-node-pre-deployment
```

**Note:** Deleting the pre-deployment stack will delete the Elastic IP. If you want to preserve the IP, do not delete the pre-deployment stack.

---

## Troubleshooting

### Stack Creation Failed

1. **Check CloudFormation Events:**
   ```bash
   aws cloudformation describe-stack-events --stack-name STACK_NAME \
     --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' --output table
   ```

2. **Common Issues:**
   - **Parameter not found**: Pre-deployment stack outputs not available
   - **Resource limit**: Check AWS service quotas
   - **Permission denied**: Verify IAM permissions

### Wazuh Not Accessible

1. **Check Container Status:**
   ```bash
   aws ssm start-session --target INSTANCE_ID
   sudo docker ps --filter name=wazuh
   ```

2. **Check Setup Logs:**
   ```bash
   sudo tail -100 /var/log/wazuh-setup.log
   ```

3. **Check Nginx Status:**
   ```bash
   sudo systemctl status nginx
   sudo nginx -t
   ```

4. **Verify Security Group:**
   - Port 443 should be open to 0.0.0.0/0
   - Port 1514-1515 should be open for agents

### Agent Not Connecting

1. **Verify Manager IP:**
   - Check `04-agent-registration/config.sh` has correct IP
   - Verify Elastic IP is associated with instance

2. **Check Firewall:**
   - Security group allows ports 1514-1515
   - Local firewall not blocking outbound connections

3. **Check Agent Status:**
   ```bash
   # macOS
   sudo /Library/Ossec/bin/wazuh-control status
   
   # Linux
   sudo systemctl status wazuh-agent
   ```

### Session Manager Connection Failed

1. **Verify SSM Agent:**
   ```bash
   # Check instance has SSM agent running
   aws ssm describe-instance-information --filters "Key=InstanceIds,Values=INSTANCE_ID"
   ```

2. **Verify IAM Role:**
   - Instance profile includes `AmazonSSMManagedInstanceCore` policy

3. **Install Session Manager Plugin:**
   - macOS: `brew install --cask session-manager-plugin`
   - Linux: Follow AWS documentation

---

## Post-Deployment Checklist

- [ ] All three stacks deployed successfully
- [ ] Wazuh dashboard accessible via HTTPS
- [ ] All three Wazuh containers running
- [ ] Login successful with admin credentials
- [ ] Test agent registered and showing as "Active"
- [ ] Elastic IP documented for future reference
- [ ] Backup configuration files
- [ ] Update DNS records (if applicable)

---

## Support and Maintenance

### Regular Maintenance Tasks

1. **Monitor Disk Usage:**
   ```bash
   aws ssm start-session --target INSTANCE_ID
   df -h /data
   ```

2. **Check Container Health:**
   ```bash
   sudo docker ps --filter name=wazuh
   sudo docker stats --no-stream
   ```

3. **Review Logs:**
   ```bash
   sudo tail -f /var/log/wazuh-setup.log
   sudo docker logs wazuh-docker-wazuh.manager-1
   ```

### Backup and Recovery

1. **EBS Volume Snapshots:**
   ```bash
   VOLUME_ID=$(aws cloudformation describe-stacks --stack-name orbit-node-pre-deployment \
     --query 'Stacks[0].Outputs[?OutputKey==`DataVolumeId`].OutputValue' --output text)
   
   aws ec2 create-snapshot --volume-id $VOLUME_ID \
     --description "ORBIT Node backup $(date +%Y-%m-%d)"
   ```

2. **Configuration Backup:**
   - Keep copies of all `config/*.json` files
   - Document any manual configuration changes
   - Store Elastic IP for reference

---

## Additional Resources

- [Configuration Guide](CONFIGURATION.md) - Detailed configuration options
- [AWS CloudFormation Documentation](https://docs.aws.amazon.com/cloudformation/)
- [Wazuh Documentation](https://documentation.wazuh.com/)
- [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)
