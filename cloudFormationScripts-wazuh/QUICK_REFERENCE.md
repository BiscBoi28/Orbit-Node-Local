# ORBIT Node - Quick Reference

## Deployment Commands

```bash
# Full deployment (run in order)
cd 01-pre-deployment && bash create-pre-deployment-stack.sh
cd ../02-secrets && bash create-secrets-stack.sh
cd ../03-ec2-deployment && bash deploy-ec2-stack.sh
cd ../04a-wazuh-ansible-customized && bash run-ec2.sh
cd ../05-agent-registration && bash register-agent.sh
```

## Stack Information

| Stack | Name | Purpose | Deploy Time |
|-------|------|---------|-------------|
| 1 | `orbit-node-pre-deployment` | VPC, IAM, EBS, Elastic IP | 3-5 min |
| 2 | `orbit-node-secrets` | Wazuh credentials | 1-2 min |
| 3 | `orbit-node-ec2` | EC2 with Docker | 5-7 min |
| 4 | Ansible | Wazuh installation (EBS + memory) | 5-10 min |
| 5 | Agent | Agent registration | 1-2 min |

## Configuration Files

| File | Purpose | Required Changes |
|------|---------|------------------|
| `01-pre-deployment/config/parameters.json` | VPC, EBS settings | Tags (MANDATORY) |
| `01-pre-deployment/pre-deployment.yaml` | Infrastructure template | Tags (MANDATORY) |
| `02-secrets/config/parameters.json` | Secrets parameters | Tags (MANDATORY) |
| `02-secrets/secrets.yaml` | Secrets template | Tags, passwords (RECOMMENDED) |
| `03-ec2-deployment/config/parameters-base.json` | Instance settings | Auto-populated |
| `03-ec2-deployment/ec2-basic.yaml` | EC2 template | Tags (MANDATORY) |
| `03-ec2-deployment/deploy-ec2-stack.sh` | Deployment script | Stack names |
| `04a-wazuh-ansible-customized/inventory/ec2.yml` | Ansible inventory | EC2 IP (auto-set) |
| `04a-wazuh-ansible-customized/install-wazuh-customized.yml` | Wazuh playbook | Memory settings (OPTIONAL) |
| `05-agent-registration/config.sh` | Agent config | Elastic IP (MANDATORY) |

## AWS CLI Commands

### Check Stack Status
```bash
aws cloudformation describe-stacks --stack-name STACK_NAME \
  --query 'Stacks[0].StackStatus' --output text
```

### Get Stack Outputs
```bash
aws cloudformation describe-stacks --stack-name STACK_NAME \
  --query 'Stacks[0].Outputs' --output table
```

### Get Elastic IP
```bash
aws cloudformation describe-stacks --stack-name orbit-node-pre-deployment \
  --query 'Stacks[0].Outputs[?OutputKey==`ElasticIP`].OutputValue' --output text
```

### Get Instance ID
```bash
aws cloudformation describe-stacks --stack-name orbit-node-ec2 \
  --query 'Stacks[0].Outputs[?OutputKey==`NodeInstanceId`].OutputValue' --output text
```

### Connect to Instance
```bash
INSTANCE_ID=$(aws cloudformation describe-stacks --stack-name orbit-node-ec2 \
  --query 'Stacks[0].Outputs[?OutputKey==`NodeInstanceId`].OutputValue' --output text)
aws ssm start-session --target $INSTANCE_ID
```

### Delete Stacks (reverse order)
```bash
aws cloudformation delete-stack --stack-name orbit-node-ec2
aws cloudformation wait stack-delete-complete --stack-name orbit-node-ec2

aws cloudformation delete-stack --stack-name orbit-node-secrets
aws cloudformation wait stack-delete-complete --stack-name orbit-node-secrets

aws cloudformation delete-stack --stack-name orbit-node-pre-deployment
aws cloudformation wait stack-delete-complete --stack-name orbit-node-pre-deployment
```

## Wazuh Commands

### Check Container Status
```bash
ssh ubuntu@<ELASTIC_IP> "docker ps --filter name=wazuh"
```

### Check Data Storage Location
```bash
ssh ubuntu@<ELASTIC_IP> "df -h /data && du -sh /data/wazuh*"
```

### Check Alerts Index
```bash
ssh ubuntu@<ELASTIC_IP> "curl -sk -u admin:SecretPassword https://localhost:9200/_cat/indices?v | grep alert"
```

### View Container Logs
```bash
ssh ubuntu@<ELASTIC_IP> "docker logs single-node-wazuh.manager-1"
ssh ubuntu@<ELASTIC_IP> "docker logs single-node-wazuh.indexer-1"
ssh ubuntu@<ELASTIC_IP> "docker logs single-node-wazuh.dashboard-1"
```

### Restart Containers
```bash
ssh ubuntu@<ELASTIC_IP> "cd /opt/wazuh-docker/single-node && docker compose restart"
```

### Check Memory Usage
```bash
ssh ubuntu@<ELASTIC_IP> "docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' | grep wazuh"
```

## Agent Commands

### macOS
```bash
# Status
sudo /Library/Ossec/bin/wazuh-control status

# Start
sudo /Library/Ossec/bin/wazuh-control start

# Stop
sudo /Library/Ossec/bin/wazuh-control stop

# Logs
sudo tail -f /Library/Ossec/logs/ossec.log
```

### Linux
```bash
# Status
sudo systemctl status wazuh-agent

# Start
sudo systemctl start wazuh-agent

# Stop
sudo systemctl stop wazuh-agent

# Logs
sudo tail -f /var/ossec/logs/ossec.log
```

## Troubleshooting

### Stack Creation Failed
```bash
# View failed events
aws cloudformation describe-stack-events --stack-name STACK_NAME \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' --output table
```

### Wazuh Not Accessible
```bash
# Check containers
sudo docker ps --filter name=wazuh

# Check setup log
sudo tail -100 /var/log/wazuh-setup.log

# Check nginx
sudo systemctl status nginx
curl -k -I https://localhost
```

### Agent Not Connecting
```bash
# Verify manager IP in config
cat 04-agent-registration/config.sh

# Check security group (ports 1514-1515 open)
aws ec2 describe-security-groups --group-ids sg-xxxxx

# Check agent status
sudo /Library/Ossec/bin/wazuh-control status  # macOS
sudo systemctl status wazuh-agent              # Linux
```

## Default Credentials

| Service | Username | Password |
|---------|----------|----------|
| Wazuh Dashboard | `admin` | `SecretPassword` |
| Wazuh Indexer | `admin` | `SecretPassword` |
| Wazuh API | `wazuh-wui` | `Wazuh@2024Pass` |

## Ports

| Port | Protocol | Purpose |
|------|----------|---------|
| 80 | TCP | HTTP (redirects to HTTPS) |
| 443 | TCP | HTTPS (Wazuh Dashboard) |
| 1514 | TCP | Wazuh agent registration |
| 1515 | TCP | Wazuh agent communication |
| 514 | UDP | Wazuh syslog (optional) |
| 3110 | TCP | ORBIT API (if used) |
| 3111 | TCP | ORBIT UI (if used) |
| 22 | TCP | SSH (restricted by AdminIpCidr) |

## Resource Tags

All resources should have these tags (update before deployment):

```yaml
Tags:
  - Key: project
    Value: YOUR_PROJECT_NAME      # MANDATORY: Change this
  - Key: created_by
    Value: YOUR_IDENTIFIER        # MANDATORY: Change this
  - Key: resource_type
    Value: YOUR_ENVIRONMENT       # MANDATORY: dev/staging/prod
```

## File Locations on EC2

| Path | Purpose |
|------|---------|
| `/opt/wazuh-docker/` | Wazuh Docker Compose files |
| `/opt/wazuh-docker/config/` | Wazuh configuration files |
| `/data/wazuh/` | Wazuh manager data (persistent) |
| `/data/wazuh-indexer/` | Wazuh indexer data (persistent) |
| `/var/log/wazuh-setup.log` | Wazuh setup log |
| `/etc/nginx/sites-available/orbit-node` | Nginx configuration |

## URLs

| Service | URL |
|---------|-----|
| Wazuh Dashboard | `https://<ELASTIC_IP>` |
| Wazuh API | `https://<ELASTIC_IP>:55000` (internal only) |

## Documentation

- **[README.md](README.md)** - Overview and quick start
- **[RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md)** - Complete deployment guide
- **[CONFIGURATION.md](CONFIGURATION.md)** - Configuration reference
- **[04-agent-registration/README.md](04-agent-registration/README.md)** - Agent registration guide

## Support Checklist

Before asking for help, verify:

- [ ] AWS CLI configured and working
- [ ] Correct region set (us-east-1 by default)
- [ ] All tags updated with your information
- [ ] S3 bucket exists and is accessible
- [ ] IAM permissions are sufficient
- [ ] Stack names are unique (if multiple deployments)
- [ ] CloudFormation events checked for errors
- [ ] Setup logs reviewed (`/var/log/wazuh-setup.log`)
