# ORBIT Node Configuration Guide

## Overview

This document describes all configuration options for the ORBIT Node deployment. Each configuration item is marked as MANDATORY or OPTIONAL.

---

## Configuration Priority

1. **MANDATORY** - Must be customized before deployment
2. **RECOMMENDED** - Should be reviewed and customized for production
3. **OPTIONAL** - Can be left as default or customized as needed

---

## 1. Pre-Deployment Stack Configuration

**File:** `01-pre-deployment/config/parameters.json`

### Resource Tags (MANDATORY)

All resources are tagged for organization and cost tracking. Update these before deployment:

```json
{
  "project": "ORBIT",        // MANDATORY: Your project name
  "created_by": "rkp",       // MANDATORY: Your identifier (NOT the original creator)
  "resource_type": "prod"    // MANDATORY: Environment (dev/staging/prod)
}
```

**Where to Update:**
- `01-pre-deployment/pre-deployment.yaml` - Search for "Tags:" sections
- `02-secrets/secrets.yaml` - Search for "Tags:" sections  
- `03-ec2-deployment/ec2-deployment-s3.yaml` - Search for "Tags:" sections

**Example:**
```yaml
Tags:
  - Key: project
    Value: MyProject          # Change from "ORBIT"
  - Key: created_by
    Value: john.doe           # Change from "rkp"
  - Key: resource_type
    Value: dev                # Change from "prod"
```

### Stack Name (MANDATORY)

**Default:** `orbit-node-pre-deployment`

**Where to Update:**
- `01-pre-deployment/create-pre-deployment-stack.sh` - Line with `STACK_NAME=`
- `03-ec2-deployment/deploy-ec2-stack.sh` - Line with `PRE_DEPLOYMENT_STACK=`

**Example:**
```bash
STACK_NAME="mycompany-wazuh-pre-deployment"
```

### VPC Configuration (OPTIONAL)

**Parameters:**
- `VpcId`: Leave empty to create new VPC, or provide existing VPC ID
- `SubnetId`: Leave empty to create new subnet, or provide existing subnet ID

**File:** `01-pre-deployment/config/parameters.json`

```json
[
  {
    "ParameterKey": "VpcId",
    "ParameterValue": ""              // Empty = create new, or "vpc-xxxxx"
  },
  {
    "ParameterKey": "SubnetId",
    "ParameterValue": ""              // Empty = create new, or "subnet-xxxxx"
  }
]
```

### Admin Access (RECOMMENDED)

**Parameter:** `AdminIpCidr`

**Default:** `0.0.0.0/0` (allows SSH from anywhere - POC only)

**Recommended:** Restrict to your IP or corporate network

```json
{
  "ParameterKey": "AdminIpCidr",
  "ParameterValue": "203.0.113.0/24"  // Your IP range
}
```

### EBS Volume (OPTIONAL)

**Parameters:**
- `EbsVolumeSize`: Size in GB (default: 100)
- `EbsDeviceName`: Device name (default: /dev/sdf)
- `DataMountPath`: Mount path (default: /data)

```json
[
  {
    "ParameterKey": "EbsVolumeSize",
    "ParameterValue": "200"           // Increase for more storage
  },
  {
    "ParameterKey": "EbsDeviceName",
    "ParameterValue": "/dev/sdf"      // Usually no need to change
  },
  {
    "ParameterKey": "DataMountPath",
    "ParameterValue": "/data"         // Usually no need to change
  }
]
```

---

## 2. Secrets Stack Configuration

**File:** `02-secrets/config/parameters.json`

### Stack Name (MANDATORY)

**Default:** `orbit-node-secrets`

**Where to Update:**
- `02-secrets/create-secrets-stack.sh` - Line with `STACK_NAME=`

### Wazuh Credentials (RECOMMENDED)

**File:** `02-secrets/secrets.yaml`

**Indexer Credentials:**
```yaml
IndexerUsername:
  Type: String
  Default: 'admin'                    // OPTIONAL: Change if needed
  NoEcho: true

IndexerPassword:
  Type: String
  Default: 'SecretPassword'           // RECOMMENDED: Change for production
  NoEcho: true
```

**API Credentials:**
```yaml
ApiUsername:
  Type: String
  Default: 'wazuh-wui'                // DO NOT CHANGE (hardcoded in setup)
  NoEcho: true

ApiPassword:
  Type: String
  Default: 'Wazuh@2024Pass'           // DO NOT CHANGE (hardcoded in setup)
  NoEcho: true
```

**IMPORTANT:** The API credentials are hardcoded in the Wazuh setup script. If you change them here, you must also update:
- `03-ec2-deployment/scripts/full-wazuh-setup.sh` - Lines with `API_USERNAME` and `API_PASSWORD`

---

## 3. EC2 Stack Configuration

**File:** `03-ec2-deployment/config/parameters-base.json`

### Stack Name (MANDATORY)

**Default:** `orbit-node-ec2`

**Where to Update:**
- `03-ec2-deployment/deploy-ec2-stack.sh` - Line with `STACK_NAME=`

### Instance Type (RECOMMENDED)

**Parameter:** `InstanceType`

**Default:** `t3.medium`

**Options:**
- `t3.small` - 2 vCPU, 2 GB RAM (minimum for testing)
- `t3.medium` - 2 vCPU, 4 GB RAM (recommended for POC)
- `t3.large` - 2 vCPU, 8 GB RAM (recommended for production)
- `t3.xlarge` - 4 vCPU, 16 GB RAM (high load)

```json
{
  "ParameterKey": "InstanceType",
  "ParameterValue": "t3.large"        // Upgrade for production
}
```

### Spot vs On-Demand (RECOMMENDED)

**Parameter:** `UseSpotInstance`

**Default:** `false` (On-Demand)

**Options:**
- `false` - On-Demand instance (stable, higher cost)
- `true` - Spot instance (cheaper, may be interrupted)

```json
{
  "ParameterKey": "UseSpotInstance",
  "ParameterValue": "false"           // Use "true" for cost savings
}
```

**Spot Price (if using Spot):**
```json
{
  "ParameterKey": "MaxSpotPrice",
  "ParameterValue": "0.04"            // Max price per hour in USD
}
```

### Pre-Deployment Outputs (AUTO-POPULATED)

These parameters are automatically populated from the pre-deployment stack. Do not manually edit:

```json
[
  {
    "ParameterKey": "VpcId",
    "ParameterValue": "vpc-xxxxx"     // Auto-populated
  },
  {
    "ParameterKey": "SubnetId",
    "ParameterValue": "subnet-xxxxx"  // Auto-populated
  },
  {
    "ParameterKey": "SecurityGroupId",
    "ParameterValue": "sg-xxxxx"      // Auto-populated
  },
  {
    "ParameterKey": "InstanceProfileArn",
    "ParameterValue": "arn:aws:..."   // Auto-populated
  },
  {
    "ParameterKey": "DataVolumeId",
    "ParameterValue": "vol-xxxxx"     // Auto-populated
  },
  {
    "ParameterKey": "ElasticIPAllocationId",
    "ParameterValue": "eipalloc-xxx"  // Auto-populated
  },
  {
    "ParameterKey": "ElasticIP",
    "ParameterValue": "x.x.x.x"       // Auto-populated
  }
]
```

---

## 4. Wazuh Ansible Configuration

**Directory:** `04a-wazuh-ansible-customized/`

### Inventory Configuration (AUTO-POPULATED)

**File:** `04a-wazuh-ansible-customized/inventory/ec2.yml`

The EC2 IP is automatically set from the CloudFormation stack output. No manual changes needed.

```yaml
all:
  children:
    wazuh_server:
      hosts:
        wazuh-node:
          ansible_host: x.x.x.x           # Auto-populated from stack
          ansible_user: ubuntu
          ansible_ssh_private_key_file: ~/.ssh/id_ed25519
          ansible_python_interpreter: /usr/bin/python3
```

### Memory Settings (OPTIONAL)

**File:** `04a-wazuh-ansible-customized/install-wazuh-customized.yml`

**Default Settings:**
- Indexer heap size: 2GB
- Indexer memory limit: 3GB

**To Customize:**
```yaml
vars:
  data_path: /data
  indexer_heap_size: 4g              # Increase for production
  indexer_memory_limit: 5g           # Increase for production
```

**Recommendations by Instance Type:**

| Instance Type | RAM | Indexer Heap | Indexer Limit |
|---------------|-----|--------------|---------------|
| t3.small | 2 GB | 512m | 1g |
| t3.medium | 4 GB | 1g | 2g |
| t3.large | 8 GB | 2g | 3g |
| t3.xlarge | 16 GB | 4g | 6g |

### Data Storage Path (OPTIONAL)

**Default:** `/data` (EBS volume)

All Wazuh data is stored on the EBS volume:
- `/data/wazuh-indexer/` - Indexer data
- `/data/wazuh/` - Manager data, logs, configurations

**To Change:**
```yaml
vars:
  data_path: /custom/path           # Change if needed
```

---

## 5. Agent Registration Configuration

**File:** `05-agent-registration/config.sh`

### Wazuh Manager IP (MANDATORY)

**Parameter:** `WAZUH_MANAGER`

**Default:** `44.194.78.195` (current deployment)

**Update:** Set to your Elastic IP from pre-deployment stack

```bash
WAZUH_MANAGER="x.x.x.x"              // MANDATORY: Your Elastic IP
```

### Agent Name (OPTIONAL)

**Parameter:** `AGENT_NAME`

**Default:** Empty (uses hostname)

**Options:**
- Leave empty to use system hostname
- Set custom name for easier identification

```bash
AGENT_NAME="web-server-01"           // OPTIONAL: Custom agent name
```

### Agent Groups (OPTIONAL)

**Parameter:** `AGENT_GROUPS`

**Default:** Empty (no groups)

**Options:**
- Leave empty for no groups
- Comma-separated list of groups

```bash
AGENT_GROUPS="web,production"        // OPTIONAL: Agent groups
```

---

## 5. Agent Registration Configuration

**File:** `05-agent-registration/config.sh`

### Wazuh Manager IP (MANDATORY)

**Parameter:** `WAZUH_MANAGER`

**Default:** `44.194.78.195` (current deployment)

**Update:** Set to your Elastic IP from pre-deployment stack

```bash
WAZUH_MANAGER="x.x.x.x"              // MANDATORY: Your Elastic IP
```

### Agent Name (OPTIONAL)

**Parameter:** `AGENT_NAME`

**Default:** Empty (uses hostname)

**Options:**
- Leave empty to use system hostname
- Set custom name for easier identification

```bash
AGENT_NAME="web-server-01"           // OPTIONAL: Custom agent name
```

### Agent Groups (OPTIONAL)

**Parameter:** `AGENT_GROUPS`

**Default:** Empty (no groups)

**Options:**
- Leave empty for no groups
- Comma-separated list of groups

```bash
AGENT_GROUPS="web,production"        // OPTIONAL: Agent groups
```

---

## 6. AWS Region Configuration (MANDATORY)

**Default:** `us-east-1`

All resources must be in the same region. Update in:

1. **AWS CLI Profile:**
   ```bash
   aws configure set region us-west-2
   ```

2. **Deployment Scripts:**
   - `03-ec2-deployment/deploy-ec2-stack.sh` - Update S3 URL region
   ```bash
   S3_URL="https://${BUCKET_NAME}.s3.us-west-2.amazonaws.com/${S3_KEY}"
   ```

3. **IAM Role Policy:**
   - `01-pre-deployment/pre-deployment.yaml` - Update S3 bucket ARN if needed

---

## 6. Security Configuration

### Security Group Rules (RECOMMENDED)

**File:** `01-pre-deployment/pre-deployment.yaml`

**Current Rules:**
- Port 80 (HTTP): 0.0.0.0/0 - Redirects to HTTPS
- Port 443 (HTTPS): 0.0.0.0/0 - Wazuh dashboard access
- Port 3110 (API): 0.0.0.0/0 - ORBIT API (if used)
- Port 3111 (UI): 0.0.0.0/0 - ORBIT UI (if used)
- Port 22 (SSH): AdminIpCidr - SSH access
- Port 1514-1515 (TCP): 0.0.0.0/0 - Wazuh agent communication
- Port 514 (UDP): 0.0.0.0/0 - Wazuh syslog (optional)

**Production Recommendations:**
1. Restrict HTTPS (443) to known IP ranges
2. Restrict API/UI ports to internal network
3. Keep agent ports (1514-1515) open to agent networks only
4. Restrict SSH to bastion host or VPN

### IAM Permissions (RECOMMENDED)

**File:** `01-pre-deployment/pre-deployment.yaml`

**Current Permissions:**
- Secrets Manager: Read access to `orbit/*` secrets
- S3: Read/write access to config bucket
- SSM: Managed instance core (for Session Manager)

**Production Recommendations:**
1. Use least privilege principle
2. Restrict S3 access to specific paths
3. Use separate IAM roles for different environments

---

## 7. Wazuh Configuration

### Memory Limits (OPTIONAL)

**File:** `03-ec2-deployment/scripts/full-wazuh-setup.sh`

**Current:** No memory limits (uses Docker defaults)

**To Add Limits:**
Edit the docker-compose.yml generation section:

```yaml
services:
  wazuh.indexer:
    environment:
      - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"  # Adjust as needed
    deploy:
      resources:
        limits:
          memory: 1G                                # Adjust as needed
```

### Nginx SSL Certificate (OPTIONAL)

**Current:** Self-signed certificate (auto-generated)

**For Production:** Use proper SSL certificate

**File:** `03-ec2-deployment/scripts/full-wazuh-setup.sh`

Replace the self-signed cert generation with:
```bash
# Copy your certificates
cp /path/to/your/cert.crt /etc/nginx/ssl/nginx.crt
cp /path/to/your/key.key /etc/nginx/ssl/nginx.key
```

---

## 8. Cleanup Configuration

### EBS Volume Deletion Policy (IMPORTANT)

**File:** `01-pre-deployment/pre-deployment.yaml`

**Current:** `DeletionPolicy: Snapshot`

**Options:**
- `Snapshot` - Creates snapshot before deletion (RECOMMENDED)
- `Retain` - Keeps volume after stack deletion
- `Delete` - Deletes volume immediately (NOT RECOMMENDED)

```yaml
OrbitNodeDataVolume:
  Type: AWS::EC2::Volume
  DeletionPolicy: Snapshot              # Change if needed
```

---

## Configuration Validation Checklist

Before deployment, verify:

- [ ] All tags updated with your information (NOT original creator)
- [ ] Stack names are unique to your deployment
- [ ] S3 bucket name updated and bucket exists
- [ ] AWS region consistent across all configurations
- [ ] Admin IP CIDR restricted appropriately
- [ ] Instance type appropriate for workload
- [ ] Wazuh credentials changed for production
- [ ] Security group rules reviewed
- [ ] IAM permissions follow least privilege
- [ ] Backup/snapshot policies configured

---

## Configuration Examples

### Example 1: Development Environment

```json
// Tags
{
  "project": "MyProject",
  "created_by": "dev.team",
  "resource_type": "dev"
}

// Instance
{
  "InstanceType": "t3.small",
  "UseSpotInstance": "true",
  "MaxSpotPrice": "0.02"
}

// Access
{
  "AdminIpCidr": "10.0.0.0/8"  // Internal network only
}
```

### Example 2: Production Environment

```json
// Tags
{
  "project": "MyProject",
  "created_by": "ops.team",
  "resource_type": "prod"
}

// Instance
{
  "InstanceType": "t3.large",
  "UseSpotInstance": "false"
}

// Storage
{
  "EbsVolumeSize": "500"
}

// Access
{
  "AdminIpCidr": "203.0.113.0/24"  // Specific IP range
}
```

---

## Getting Help

If you need assistance with configuration:

1. Review the [Deployment Runbook](RUNBOOK_DEPLOY.md)
2. Check AWS CloudFormation documentation
3. Review Wazuh documentation for application-specific settings
4. Validate JSON syntax using `jq` or online validators


---

## Deployment Architecture Summary

### Step 1-3: CloudFormation (Infrastructure)
- **01-pre-deployment**: VPC, IAM, EBS volume (100GB), Elastic IP
- **02-secrets**: AWS Secrets Manager credentials
- **03-ec2-deployment**: EC2 instance with Docker, EBS mounted at `/data`

### Step 4: Ansible (Wazuh Installation)
- **04a-wazuh-ansible-customized**: Deploys Wazuh using official Docker images
  - Clones official Wazuh repository (v4.14.2)
  - Customizes docker-compose.yml for EBS storage
  - Sets indexer memory: 2GB heap, 3GB limit
  - All data stored on `/data` EBS volume
  - Uses official certificate generation

### Step 5: Agent Registration
- **05-agent-registration**: Registers endpoints as Wazuh agents

### Key Features
1. **Separation of Concerns**: Infrastructure (CloudFormation) separate from application (Ansible)
2. **EBS Storage**: All Wazuh data on persistent EBS volume, survives container restarts
3. **Memory Optimization**: Configurable memory settings for indexer
4. **Official Images**: Uses Wazuh's official Docker images with minimal customization
5. **Alerts Index**: Working out-of-the-box with official Wazuh configuration

### Data Persistence
- **EBS Volume**: `/data` (100GB, mounted from CloudFormation)
- **Wazuh Indexer**: `/data/wazuh-indexer/`
- **Wazuh Manager**: `/data/wazuh/` (logs, configs, queues, etc.)
- **Docker Volumes**: Replaced with bind mounts to EBS

### Memory Configuration
- **Default**: 2GB heap, 3GB limit for indexer
- **Customizable**: Edit `04a-wazuh-ansible-customized/install-wazuh-customized.yml`
- **Recommendations**: Scale based on instance type (see table in section 4)

---

## Quick Configuration Checklist

Before deployment:

- [ ] Update tags in all CloudFormation templates (project, created_by, resource_type)
- [ ] Update stack names if deploying multiple environments
- [ ] Review instance type (t3.medium default, t3.large for production)
- [ ] Review EBS volume size (100GB default)
- [ ] Review security group rules (restrict as needed)
- [ ] Review Wazuh memory settings (2GB heap default)
- [ ] Set AWS region in CLI profile
- [ ] Update agent registration config with Elastic IP after deployment

---

## Post-Deployment Verification

After deployment, verify:

```bash
# 1. Check all containers running
ssh ubuntu@<ELASTIC_IP> "docker ps --filter name=wazuh"

# 2. Verify data on EBS volume
ssh ubuntu@<ELASTIC_IP> "df -h /data && du -sh /data/wazuh*"

# 3. Check alerts index exists
ssh ubuntu@<ELASTIC_IP> "curl -sk -u admin:SecretPassword https://localhost:9200/_cat/indices?v | grep alert"

# 4. Check memory settings
ssh ubuntu@<ELASTIC_IP> "docker stats --no-stream --format 'table {{.Name}}\t{{.MemUsage}}' | grep wazuh"

# 5. Access dashboard
open https://<ELASTIC_IP>
```

Expected results:
- 3 containers running (manager, indexer, dashboard)
- Data directories on /data with growing size
- wazuh-alerts-4.x-* index present
- Indexer using ~2GB memory
- Dashboard accessible with admin/SecretPassword

