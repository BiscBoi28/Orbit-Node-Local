#!/bin/bash
# Create orbit-dev pre-deployment stack.
# Imports VPC + Subnet from the existing wazuh pre-deployment stack so both EC2s
# share the same VPC.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REGION="us-east-2"
STACK_NAME="iiith-orbit-dev-pre-deployment-dev"
WAZUH_PRE_STACK="iiith-orbit-node-pre-deployment-dev"  # source of shared VPC/Subnet

echo "=== Creating orbit-dev Pre-Deployment Stack ==="
echo "Stack:  $STACK_NAME"
echo "Region: $REGION"
echo ""

# ------------------------------------------------------------------
# 1. Pull VPC + Subnet from the existing wazuh pre-deployment stack
# ------------------------------------------------------------------
echo "[1/2] Fetching VPC/Subnet from $WAZUH_PRE_STACK..."

VPC_ID=$(aws cloudformation describe-stacks \
  --stack-name "$WAZUH_PRE_STACK" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`VpcId`].OutputValue' \
  --output text)

SUBNET_ID=$(aws cloudformation describe-stacks \
  --stack-name "$WAZUH_PRE_STACK" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[?OutputKey==`SubnetId`].OutputValue' \
  --output text)

if [ -z "$VPC_ID" ] || [ "$VPC_ID" = "None" ]; then
  echo "ERROR: Could not get VpcId from $WAZUH_PRE_STACK."
  echo "       Deploy the wazuh pre-deployment stack first."
  exit 1
fi

echo "VPC ID:    $VPC_ID"
echo "Subnet ID: $SUBNET_ID"

# Write parameters file (overwritten each deploy so values stay in sync)
mkdir -p "$SCRIPT_DIR/config"
cat > "$SCRIPT_DIR/config/parameters.json" << EOF
[
  {"ParameterKey": "VpcId",          "ParameterValue": "$VPC_ID"},
  {"ParameterKey": "SubnetId",       "ParameterValue": "$SUBNET_ID"},
  {"ParameterKey": "AdminIpCidr",    "ParameterValue": "0.0.0.0/0"},
  {"ParameterKey": "EbsVolumeSize",  "ParameterValue": "80"},
  {"ParameterKey": "EbsDeviceName",  "ParameterValue": "/dev/sdf"},
  {"ParameterKey": "DataMountPath",  "ParameterValue": "/data"}
]
EOF

# ------------------------------------------------------------------
# 2. Deploy the CloudFormation stack
# ------------------------------------------------------------------
echo ""
echo "[2/2] Deploying pre-deployment stack..."

aws cloudformation deploy \
  --template-file "$SCRIPT_DIR/pre-deployment.yaml" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides file://"$SCRIPT_DIR/config/parameters.json" \
  --region "$REGION" \
  --capabilities CAPABILITY_NAMED_IAM

echo ""
echo "=== Pre-Deployment Stack Ready ==="
echo ""
echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --region "$REGION" \
  --query 'Stacks[0].Outputs[*].[OutputKey,OutputValue]' \
  --output table
