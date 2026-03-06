#!/bin/bash
# Deploy EC2 stack with simplified Wazuh setup script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config/parameters-base.json"

# Check if config exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Read parameters
STACK_NAME=$(jq -r '.[] | select(.ParameterKey=="StackName") | .ParameterValue' "$CONFIG_FILE")
ENV=$(jq -r '.[] | select(.ParameterKey=="Environment") | .ParameterValue' "$CONFIG_FILE")
ENV=${ENV:-dev}
S3_BUCKET=$(jq -r '.[] | select(.ParameterKey=="S3Bucket") | .ParameterValue' "$CONFIG_FILE")
S3_KEY=$(jq -r '.[] | select(.ParameterKey=="S3ScriptKey") | .ParameterValue' "$CONFIG_FILE")
REGION=$(jq -r '.[] | select(.ParameterKey=="Region") | .ParameterValue' "$CONFIG_FILE")
KEY_NAME=$(jq -r '.[] | select(.ParameterKey=="KeyName") | .ParameterValue' "$CONFIG_FILE")

echo "=== Deploying Wazuh EC2 Stack ==="
echo "Stack: $STACK_NAME"
echo "S3 Bucket: $S3_BUCKET"
echo "S3 Key: $S3_KEY"
echo "Region: $REGION"
echo ""

# Upload setup and health-check scripts to S3
echo "[1/3] Uploading scripts to S3..."
aws s3 cp "$SCRIPT_DIR/scripts/wazuh-setup.sh" "s3://$S3_BUCKET/$S3_KEY" --region "$REGION"
aws s3 cp "$SCRIPT_DIR/scripts/health-check.sh" "s3://$S3_BUCKET/health-check-wazuh.sh" --region "$REGION"
echo "✓ Scripts uploaded"

# Get pre-deployment outputs
echo "[2/3] Getting pre-deployment stack outputs..."
PRE_STACK="${STACK_NAME}-pre-deployment-${ENV}"

VPC_ID=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' --output text)
SUBNET_ID=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`SubnetId`].OutputValue' --output text)
SG_ID=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`SecurityGroupId`].OutputValue' --output text)
INSTANCE_PROFILE=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`InstanceProfileArn`].OutputValue' --output text)
VOLUME_ID=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`DataVolumeId`].OutputValue' --output text)
EIP_ALLOC=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`ElasticIPAllocationId`].OutputValue' --output text)
EIP=$(aws cloudformation describe-stacks --stack-name "$PRE_STACK" --region "$REGION" --query 'Stacks[0].Outputs[?OutputKey==`ElasticIP`].OutputValue' --output text)

# Create parameters file
cat > "$SCRIPT_DIR/config/parameters.json" << EOF
[
  {"ParameterKey": "VpcId", "ParameterValue": "$VPC_ID"},
  {"ParameterKey": "SubnetId", "ParameterValue": "$SUBNET_ID"},
  {"ParameterKey": "SecurityGroupId", "ParameterValue": "$SG_ID"},
  {"ParameterKey": "InstanceProfileArn", "ParameterValue": "$INSTANCE_PROFILE"},
  {"ParameterKey": "DataVolumeId", "ParameterValue": "$VOLUME_ID"},
  {"ParameterKey": "ElasticIPAllocationId", "ParameterValue": "$EIP_ALLOC"},
  {"ParameterKey": "ElasticIP", "ParameterValue": "$EIP"},
  {"ParameterKey": "SetupScriptS3Url", "ParameterValue": "https://$S3_BUCKET.s3.$REGION.amazonaws.com/$S3_KEY"},
  {"ParameterKey": "KeyName", "ParameterValue": "$KEY_NAME"}
]
EOF

# Deploy stack
echo "[3/3] Deploying EC2 stack..."
EC2_STACK="${STACK_NAME}-ec2"

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/ec2-deployment-s3.yaml" \
  --stack-name "$EC2_STACK" \
  --parameter-overrides file://"$SCRIPT_DIR/config/parameters.json" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM

echo ""
echo "=== Deployment Complete ==="
echo "Stack: $EC2_STACK"
echo "Dashboard URL: https://$EIP"
echo ""
echo "Wait 5-10 minutes for Wazuh to fully initialize"
echo "Default credentials: admin / SecretPassword"
