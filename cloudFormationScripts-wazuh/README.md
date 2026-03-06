# ORBIT Node - AWS CloudFormation Deployment

Production-grade AWS infrastructure deployment for ORBIT Node with Wazuh SIEM.

## Quick Start

```bash
# 1. Deploy pre-deployment stack (VPC, IAM, EBS, Elastic IP)
cd 01-pre-deployment
bash create-pre-deployment-stack.sh

# 2. Deploy secrets stack (Wazuh credentials)
cd ../02-secrets
bash create-secrets-stack.sh

# 3. Deploy EC2 stack (Instance with Docker)
cd ../03-ec2-deployment
bash deploy-ec2-stack.sh

# 4. Deploy Wazuh via Ansible (with EBS storage and memory settings)
cd ../04a-wazuh-ansible-customized
bash run-ec2.sh

# 5. Register agents
cd ../05-agent-registration
# Edit config.sh with your Elastic IP
bash register-agent.sh
```

## Documentation

- **[Deployment Runbook](RUNBOOK_DEPLOY.md)** - Complete deployment guide with troubleshooting
- **[Configuration Guide](CONFIGURATION.md)** - All configuration options (mandatory/optional)

## Repository Structure

```
.
├── 01-pre-deployment/          # VPC, networking, IAM, EBS, Elastic IP
│   ├── config/
│   │   └── parameters.json     # Stack parameters
│   ├── pre-deployment.yaml     # CloudFormation template
│   └── create-pre-deployment-stack.sh
│
├── 02-secrets/                 # AWS Secrets Manager
│   ├── config/
│   │   └── parameters.json     # Stack parameters
│   ├── secrets.yaml            # CloudFormation template
│   └── create-secrets-stack.sh
│
├── 03-ec2-deployment/          # EC2 instance with Docker
│   ├── config/
│   │   └── parameters-base.json # Stack parameters
│   ├── ec2-basic.yaml          # CloudFormation template
│   └── deploy-ec2-stack.sh     # Deployment script
│
├── 04a-wazuh-ansible-customized/ # Wazuh deployment via Ansible
│   ├── inventory/
│   │   └── ec2.yml             # Ansible inventory
│   ├── install-wazuh-customized.yml # Ansible playbook
│   ├── run-ec2.sh              # Deployment script
│   └── README.md               # Ansible documentation
│
├── 05-agent-registration/      # Wazuh agent registration
│   ├── config.sh               # Agent configuration
│   ├── register-agent.sh       # Registration script
│   └── README.md               # Agent documentation
│
├── RUNBOOK_DEPLOY.md           # Deployment guide
├── QUICK_REFERENCE.md          # Quick reference
├── CONFIGURATION.md            # Configuration reference
└── README.md                   # This file
```

## Prerequisites

- AWS CLI configured with appropriate credentials
- Bash shell (macOS/Linux)
- jq (JSON processor)
- Appropriate AWS permissions (see [RUNBOOK_DEPLOY.md](RUNBOOK_DEPLOY.md))

## Key Features

- **Persistent Elastic IP**: Survives EC2 stack deletions
- **Automated Deployment**: Single-script deployment per stack
- **Production-Ready**: Proper tagging, IAM roles, security groups
- **Wazuh SIEM**: Fully automated installation and configuration
- **Agent Registration**: Simple script-based agent enrollment
- **Session Manager**: SSH-less access to EC2 instances

## Configuration Before Deployment

### MANDATORY Changes

1. **Update Tags** in all CloudFormation templates:
   - `project`: Your project name
   - `created_by`: Your identifier (NOT "rkp")
   - `resource_type`: Your environment (dev/staging/prod)

2. **Update Stack Names** if deploying multiple environments:
   - `01-pre-deployment/create-pre-deployment-stack.sh`
   - `02-secrets/create-secrets-stack.sh`
   - `03-ec2-deployment/deploy-ec2-stack.sh`

3. **Update S3 Bucket** name:
   - `03-ec2-deployment/deploy-ec2-stack.sh`

See [CONFIGURATION.md](CONFIGURATION.md) for complete configuration guide.

## Deployment Time

- Pre-deployment stack: ~3-5 minutes
- Secrets stack: ~1-2 minutes
- EC2 stack: ~5-7 minutes
- Wazuh deployment (Ansible): ~5-10 minutes
- Agent registration: ~1-2 minutes
- **Total**: ~20-30 minutes

## Access

After deployment:

- **Wazuh Dashboard**: `https://<ELASTIC_IP>`
- **Username**: `admin`
- **Password**: `SecretPassword`

## Support

For detailed instructions, troubleshooting, and configuration options:

- [Deployment Runbook](RUNBOOK_DEPLOY.md)
- [Configuration Guide](CONFIGURATION.md)
- [Agent Registration Guide](04-agent-registration/README.md)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AWS Cloud (us-east-1)                │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  VPC (10.0.0.0/16)                             │    │
│  │                                                 │    │
│  │  ┌──────────────────────────────────────────┐  │    │
│  │  │  Public Subnet (10.0.1.0/24)             │  │    │
│  │  │                                           │  │    │
│  │  │  ┌─────────────────────────────────┐     │  │    │
│  │  │  │  EC2 Instance (t3.medium)       │     │  │    │
│  │  │  │  - Elastic IP (persistent)      │     │  │    │
│  │  │  │  - EBS Volume (/data)           │     │  │    │
│  │  │  │                                  │     │  │    │
│  │  │  │  Docker Containers:             │     │  │    │
│  │  │  │  ├─ wazuh.manager               │     │  │    │
│  │  │  │  ├─ wazuh.indexer               │     │  │    │
│  │  │  │  └─ wazuh.dashboard             │     │  │    │
│  │  │  │                                  │     │  │    │
│  │  │  │  Nginx (reverse proxy)          │     │  │    │
│  │  │  └─────────────────────────────────┘     │  │    │
│  │  │                                           │  │    │
│  │  └──────────────────────────────────────────┘  │    │
│  │                                                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  AWS Secrets Manager                           │    │
│  │  ├─ orbit/node/wazuh-indexer-credentials      │    │
│  │  └─ orbit/node/wazuh-api-credentials          │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │  S3 Bucket (orbit-node-config-*)               │    │
│  │  └─ cloudformation_configs/                    │    │
│  │     └─ wazhu_setup_config/                     │    │
│  │        └─ full-wazuh-setup.sh                  │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## License

Internal use only.
