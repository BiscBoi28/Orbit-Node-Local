#!/bin/bash
# Deploy the orbit-dev EC2 stack.
# Uploads orbit-dev-setup.sh to S3, pulls pre-deployment outputs, then deploys EC2.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config/parameters-base.json"

if [ ! -f "$CONFIG_FILE" ]; then
  echo "Error: $CONFIG_FILE not found"
  exit 1
fi

# Read base parameters
STACK_NAME=$(jq -r '.[] | select(.ParameterKey=="StackName")      | .ParameterValue' "$CONFIG_FILE")
ENV=$(jq -r       '.[] | select(.ParameterKey=="Environment")    | .ParameterValue' "$CONFIG_FILE")
S3_BUCKET=$(jq -r '.[] | select(.ParameterKey=="S3Bucket")       | .ParameterValue' "$CONFIG_FILE")
S3_KEY=$(jq -r    '.[] | select(.ParameterKey=="S3ScriptKey")    | .ParameterValue' "$CONFIG_FILE")
REGION=$(jq -r    '.[] | select(.ParameterKey=="Region")         | .ParameterValue' "$CONFIG_FILE")
KEY_NAME=$(jq -r  '.[] | select(.ParameterKey=="KeyName")        | .ParameterValue' "$CONFIG_FILE")
WAZUH_IP=$(jq -r  '.[] | select(.ParameterKey=="WazuhManagerIp") | .ParameterValue' "$CONFIG_FILE")
INSTANCE_TYPE=$(jq -r '.[] | select(.ParameterKey=="InstanceType") | .ParameterValue' "$CONFIG_FILE")
USE_SPOT=$(jq -r  '.[] | select(.ParameterKey=="UseSpotInstance")| .ParameterValue' "$CONFIG_FILE")
ENV=${ENV:-dev}

echo "=== Deploying orbit-dev EC2 Stack ==="
echo "Stack:        $STACK_NAME"
echo "Region:       $REGION"
echo "S3 Bucket:    $S3_BUCKET"
echo "Instance:     $INSTANCE_TYPE (Spot=$USE_SPOT)"
echo "Wazuh Mgr IP: $WAZUH_IP"
echo ""

# ------------------------------------------------------------------
# 1. Upload orbit-dev-setup.sh and health-check.sh to S3
# ------------------------------------------------------------------
echo "[1/3] Uploading scripts to S3..."
aws s3 cp "$SCRIPT_DIR/scripts/orbit-dev-setup.sh" \
  "s3://$S3_BUCKET/$S3_KEY" \
  --region "$REGION"
S3_KEY_HEALTH="${S3_KEY%/*}/health-check.sh"
S3_KEY_START="${S3_KEY%/*}/start-services.sh"
aws s3 cp "$SCRIPT_DIR/scripts/health-check.sh" "s3://$S3_BUCKET/$S3_KEY_HEALTH" --region "$REGION"
aws s3 cp "$SCRIPT_DIR/scripts/start-services.sh" "s3://$S3_BUCKET/$S3_KEY_START" --region "$REGION"
echo "✓ Uploaded s3://$S3_BUCKET/$S3_KEY, health-check.sh, start-services.sh"

# ------------------------------------------------------------------
# 2. Read outputs from orbit-dev pre-deployment stack
# ------------------------------------------------------------------
echo ""
echo "[2/3] Reading orbit-dev pre-deployment outputs..."
PRE_STACK="${STACK_NAME}-pre-deployment-${ENV}"

get_output() {
  aws cloudformation describe-stacks \
    --stack-name "$1" \
    --region "$REGION" \
    --query "Stacks[0].Outputs[?OutputKey==\`$2\`].OutputValue" \
    --output text
}

SG_ID=$(get_output "$PRE_STACK" SecurityGroupId)
INSTANCE_PROFILE=$(get_output "$PRE_STACK" InstanceProfileArn)
VOLUME_ID=$(get_output "$PRE_STACK" DataVolumeId)
EIP_ALLOC=$(get_output "$PRE_STACK" ElasticIPAllocationId)
EIP=$(get_output "$PRE_STACK" ElasticIP)

# VPC + Subnet come from the shared wazuh pre-deployment stack
WAZUH_PRE_STACK="iiith-orbit-node-pre-deployment-dev"
VPC_ID=$(get_output "$WAZUH_PRE_STACK" VpcId)
SUBNET_ID=$(get_output "$WAZUH_PRE_STACK" SubnetId)

if [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
  echo "ERROR: Could not get SecurityGroupId from $PRE_STACK"
  echo "       Run 01-pre-deployment/create-pre-deployment-stack.sh first."
  exit 1
fi

echo "  VPC:               $VPC_ID"
echo "  Subnet:            $SUBNET_ID"
echo "  Security Group:    $SG_ID"
echo "  Instance Profile:  $INSTANCE_PROFILE"
echo "  EBS Volume:        $VOLUME_ID"
echo "  Elastic IP:        $EIP"

# Write resolved parameters file
mkdir -p "$SCRIPT_DIR/config"
cat > "$SCRIPT_DIR/config/parameters.json" << EOF
[
  {"ParameterKey": "VpcId",                "ParameterValue": "$VPC_ID"},
  {"ParameterKey": "SubnetId",             "ParameterValue": "$SUBNET_ID"},
  {"ParameterKey": "SecurityGroupId",      "ParameterValue": "$SG_ID"},
  {"ParameterKey": "InstanceProfileArn",   "ParameterValue": "$INSTANCE_PROFILE"},
  {"ParameterKey": "DataVolumeId",         "ParameterValue": "$VOLUME_ID"},
  {"ParameterKey": "ElasticIPAllocationId","ParameterValue": "$EIP_ALLOC"},
  {"ParameterKey": "ElasticIP",            "ParameterValue": "$EIP"},
  {"ParameterKey": "SetupScriptS3Url",     "ParameterValue": "https://$S3_BUCKET.s3.$REGION.amazonaws.com/$S3_KEY"},
  {"ParameterKey": "KeyName",              "ParameterValue": "$KEY_NAME"},
  {"ParameterKey": "WazuhManagerIp",       "ParameterValue": "$WAZUH_IP"},
  {"ParameterKey": "InstanceType",         "ParameterValue": "$INSTANCE_TYPE"},
  {"ParameterKey": "UseSpotInstance",      "ParameterValue": "$USE_SPOT"}
]
EOF

# ------------------------------------------------------------------
# 3. Deploy EC2 CloudFormation stack
# ------------------------------------------------------------------
echo ""
echo "[3/3] Deploying EC2 stack..."
EC2_STACK="${STACK_NAME}-ec2"

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/ec2-orbit-dev.yaml" \
  --stack-name "$EC2_STACK" \
  --parameter-overrides file://"$SCRIPT_DIR/config/parameters.json" \
  --region "$REGION" \
  --capabilities CAPABILITY_IAM

echo ""
echo "=== Deployment Complete ==="
echo ""
echo "EC2 stack: $EC2_STACK"
echo ""
echo "Service endpoints (available after ~8-10 min for setup to finish):"
echo "  Neo4j Browser:      http://$EIP:7474   (user: neo4j)"
echo "  Presidio Analyzer:  http://$EIP:5001"
echo "  OWASP Juice Shop:   http://$EIP:3000"
echo "  ORC (placeholder):  http://$EIP:8000"
echo ""
echo "SSH access:"
echo "  ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$EIP"
echo ""
echo "Monitor setup progress:"
echo "  ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$EIP 'tail -f /var/log/orbit-dev-setup.log'"
