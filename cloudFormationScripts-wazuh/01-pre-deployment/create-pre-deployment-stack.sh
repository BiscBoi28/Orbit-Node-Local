#!/bin/bash
# Deploy or update pre-deployment stack
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${SCRIPT_DIR}/pre-deployment.yaml"
PARAMS="${SCRIPT_DIR}/config/parameters.json"
STACK_NAME="iiith-orbit-node-pre-deployment-dev"

echo "=========================================="
echo "Pre-Deployment Stack"
echo "=========================================="
echo ""

# Check if stack exists
STACK_STATUS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].StackStatus' --output text 2>/dev/null) || STACK_STATUS="DOES_NOT_EXIST"

if [ "$STACK_STATUS" = "DOES_NOT_EXIST" ]; then
    echo "Creating stack $STACK_NAME..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE" \
        --parameters "file://$PARAMS" \
        --capabilities CAPABILITY_NAMED_IAM
    
    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
    echo "✓ Stack created successfully"
    
elif [ "$STACK_STATUS" = "ROLLBACK_COMPLETE" ]; then
    echo "Stack is in ROLLBACK_COMPLETE state. Deleting..."
    aws cloudformation delete-stack --stack-name "$STACK_NAME"
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
    echo "✓ Stack deleted"
    
    echo "Creating stack $STACK_NAME..."
    aws cloudformation create-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE" \
        --parameters "file://$PARAMS" \
        --capabilities CAPABILITY_NAMED_IAM
    
    echo "Waiting for stack creation..."
    aws cloudformation wait stack-create-complete --stack-name "$STACK_NAME"
    echo "✓ Stack created successfully"
    
else
    echo "Stack exists with status: $STACK_STATUS"
    echo "Updating stack $STACK_NAME..."
    UPDATE_OUTPUT=$(aws cloudformation update-stack \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE" \
        --parameters "file://$PARAMS" \
        --capabilities CAPABILITY_NAMED_IAM 2>&1) || {
            if echo "$UPDATE_OUTPUT" | grep -q "No updates"; then
                echo "✓ No updates needed"
            else
                echo "✗ Update failed: $UPDATE_OUTPUT"
                exit 1
            fi
        }
    
    if [ $? -eq 0 ] && ! echo "$UPDATE_OUTPUT" | grep -q "No updates"; then
        echo "Waiting for stack update..."
        aws cloudformation wait stack-update-complete --stack-name "$STACK_NAME"
        echo "✓ Stack updated successfully"
    fi
fi

echo ""
echo "=========================================="
echo "Stack Outputs"
echo "=========================================="
aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output table

echo ""
echo "Elastic IP has been created and will persist across EC2 stack deletions."
echo "Save this IP for agent configuration."
echo ""
