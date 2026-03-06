#!/bin/bash
# Deploy secrets CloudFormation stack
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/secrets.yaml"
PARAMS_FILE="${SCRIPT_DIR}/config/parameters.json"
STACK_NAME="iiith-orbit-node-secrets-dev"

if [ ! -f "$PARAMS_FILE" ]; then
  echo "Error: config/parameters.json not found"
  exit 1
fi

echo "=========================================="
echo "Deploying Secrets Stack"
echo "=========================================="
echo ""

# Create stack
aws cloudformation create-stack \
  --stack-name "$STACK_NAME" \
  --template-body "file://$TEMPLATE" \
  --parameters "file://$PARAMS_FILE"

echo "Waiting for stack creation..."
aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"

echo ""
echo "✓ Secrets stack deployed successfully"
echo ""

# Show outputs
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' --output table
