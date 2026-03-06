
## Prerequisites

1. AWS CLI installed and configured with your credentials
2. Bash shell (macOS/Linux)
3. `jq` installed (JSON processor)
4. AWS permissions: CloudFormation, EC2, IAM, Secrets Manager, S3, Systems Manager

---

## IMPORTANT: Configuration Before Deployment

**You MUST update these configurations with YOUR information (not mine):**

### 1. Update Resource Tags (MANDATORY)

Edit these files and replace the tags:
- `01-pre-deployment/pre-deployment.yaml`
- `02-secrets/secrets.yaml`
- `03-ec2-deployment/ec2-deployment-s3.yaml`

Search for "Tags:" and update:
```yaml
- Key: project
  Value: YOUR_PROJECT_NAME        # Change from "ORBIT"
- Key: created_by
  Value: YOUR_NAME                # Change from "rkp"
- Key: resource_type
  Value: YOUR_ENVIRONMENT         # dev/staging/prod
```

### 2. Update Stack Names (MANDATORY if deploying multiple environments)

Edit these files:
- `01-pre-deployment/create-pre-deployment-stack.sh` → Line: `STACK_NAME="your-project-pre-deployment"`
- `02-secrets/create-secrets-stack.sh` → Line: `STACK_NAME="your-project-secrets"`
- `03-ec2-deployment/deploy-ec2-stack.sh` → Lines: `STACK_NAME="your-project-ec2"` and `PRE_DEPLOYMENT_STACK="your-project-pre-deployment"`

### 3. Update S3 Bucket (MANDATORY)

Edit `03-ec2-deployment/deploy-ec2-stack.sh`:
- Line: `BUCKET_NAME="your-bucket-name"`
- Ensure the bucket exists in us-east-1 (or your region)

### 4. Verify AWS Region (MANDATORY)

All resources must be in the same region. Default is `us-east-1`.

To change region:
```bash
aws configure set region us-west-2
```

Then update S3 URL in `03-ec2-deployment/deploy-ec2-stack.sh`:
```bash
S3_URL="https://${BUCKET_NAME}.s3.YOUR-REGION.amazonaws.com/${S3_KEY}"
```

---

## Deployment Steps

### Step 1: Deploy Pre-Deployment Stack (3-5 minutes)
```bash
cd 01-pre-deployment
bash create-pre-deployment-stack.sh
```

This creates: VPC, Security Group, IAM Role, EBS Volume, Elastic IP

**Save the Elastic IP from the output** - you'll need it for agent registration.

---

### Step 2: Deploy Secrets Stack (1-2 minutes)
```bash
cd ../02-secrets
bash create-secrets-stack.sh
```

This creates Wazuh credentials in AWS Secrets Manager.

---

### Step 3: Deploy EC2 Stack (5-7 minutes)
```bash
cd ../03-ec2-deployment
bash deploy-ec2-stack.sh
```

This deploys the EC2 instance and automatically installs Wazuh.

**Wait 5-10 additional minutes** for Wazuh setup to complete in the background.

---

### Step 4: Verify Wazuh is Running

Get your Elastic IP from Step 1 output, then:

1. Open browser: `https://<YOUR_ELASTIC_IP>`
2. Accept the self-signed certificate warning
3. Login:
   - Username: `admin`
   - Password: `SecretPassword`

---

### Step 5: Register Agents (Optional)

To register your laptop or servers as Wazuh agents:

1. Edit `04-agent-registration/config.sh`:
   ```bash
   WAZUH_MANAGER="YOUR_ELASTIC_IP"    # Update with your Elastic IP
   ```

2. Run the registration script:
   ```bash
   cd ../04-agent-registration
   bash register-agent.sh
   ```

3. Verify in Wazuh dashboard → Agents section

---

## Troubleshooting

### Stack Creation Failed
```bash
aws cloudformation describe-stack-events --stack-name STACK_NAME \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' --output table
```

### Wazuh Not Accessible
Connect to instance and check logs:
```bash
# Get instance ID
INSTANCE_ID=$(aws cloudformation describe-stacks --stack-name your-project-ec2 \
  --query 'Stacks[0].Outputs[?OutputKey==`NodeInstanceId`].OutputValue' --output text)

# Connect via Session Manager
aws ssm start-session --target $INSTANCE_ID

# Check setup logs
sudo tail -f /var/log/wazuh-setup.log

# Check containers
sudo docker ps --filter name=wazuh
```

All three containers should be running:
- wazuh-docker-wazuh.manager-1
- wazuh-docker-wazuh.indexer-1
- wazuh-docker-wazuh.dashboard-1

---

## Documentation

Detailed documentation is available in the repository:

- **README.md** - Project overview and quick start
- **RUNBOOK_DEPLOY.md** - Complete deployment guide with troubleshooting
- **CONFIGURATION.md** - All configuration options (mandatory/optional)
- **QUICK_REFERENCE.md** - Command cheat sheet

---

## Cleanup (When Done Testing)

To delete all resources (in reverse order):

```bash
aws cloudformation delete-stack --stack-name your-project-ec2
aws cloudformation wait stack-delete-complete --stack-name your-project-ec2

aws cloudformation delete-stack --stack-name your-project-secrets
aws cloudformation wait stack-delete-complete --stack-name your-project-secrets

aws cloudformation delete-stack --stack-name your-project-pre-deployment
aws cloudformation wait stack-delete-complete --stack-name your-project-pre-deployment
```

**Note:** Deleting pre-deployment stack will delete the Elastic IP.

---

## Summary

1. Update tags, stack names, and S3 bucket (MANDATORY)
2. Run 3 deployment scripts in order
3. Wait for Wazuh setup to complete (~10 min total)
4. Access dashboard at `https://<ELASTIC_IP>`
5. Register agents (optional)

Total deployment time: ~15-25 minutes

---

If you encounter any issues, check RUNBOOK_DEPLOY.md for detailed troubleshooting steps.


