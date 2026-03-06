#!/bin/bash
# Automated Wazuh Agent Registration
# Supports: macOS, Ubuntu/Debian, CentOS/RHEL, Amazon Linux

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/config.sh"

# Load configuration
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.sh not found"
    echo "Please create config.sh with WAZUH_MANAGER setting"
    exit 1
fi

source "$CONFIG_FILE"

# Validate configuration
if [ -z "$WAZUH_MANAGER" ]; then
    echo "Error: WAZUH_MANAGER not set in config.sh"
    exit 1
fi

# Set agent name to hostname if not specified
if [ -z "$AGENT_NAME" ]; then
    AGENT_NAME=$(hostname)
fi

echo "=========================================="
echo "Wazuh Agent Registration"
echo "=========================================="
echo ""
echo "Manager: $WAZUH_MANAGER"
echo "Agent Name: $AGENT_NAME"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    AGENT_PATH="/Library/Ossec"
    WAZUH_VERSION="4.14.2-1"
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        PACKAGE_URL="https://packages.wazuh.com/4.x/macos/wazuh-agent-${WAZUH_VERSION}.arm64.pkg"
    else
        PACKAGE_URL="https://packages.wazuh.com/4.x/macos/wazuh-agent-${WAZUH_VERSION}.intel64.pkg"
    fi
elif [ -f /etc/os-release ]; then
    . /etc/os-release
    case "$ID" in
        ubuntu|debian)
            OS="debian"
            AGENT_PATH="/var/ossec"
            ;;
        centos|rhel|fedora)
            OS="rhel"
            AGENT_PATH="/var/ossec"
            ;;
        amzn)
            OS="amazon"
            AGENT_PATH="/var/ossec"
            ;;
        *)
            echo "Error: Unsupported Linux distribution: $ID"
            exit 1
            ;;
    esac
else
    echo "Error: Unsupported operating system"
    exit 1
fi

echo "Detected OS: $OS"
echo ""

# Check if agent is already installed
if [ -d "$AGENT_PATH" ]; then
    echo "Wazuh agent is already installed"
    INSTALL_AGENT=false
else
    echo "Wazuh agent not found. Installing..."
    INSTALL_AGENT=true
fi

# Install agent if needed
if [ "$INSTALL_AGENT" = true ]; then
    case "$OS" in
        macos)
            echo "Downloading Wazuh agent for macOS..."
            curl -so /tmp/wazuh-agent.pkg "$PACKAGE_URL"
            echo "Installing agent..."
            sudo installer -pkg /tmp/wazuh-agent.pkg -target /
            rm -f /tmp/wazuh-agent.pkg
            ;;
        debian)
            echo "Installing Wazuh agent for Debian/Ubuntu..."
            curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
            sudo chmod 644 /usr/share/keyrings/wazuh.gpg
            echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | sudo tee /etc/apt/sources.list.d/wazuh.list
            sudo apt-get update
            sudo WAZUH_MANAGER="$WAZUH_MANAGER" apt-get install -y wazuh-agent
            ;;
        rhel|amazon)
            echo "Installing Wazuh agent for RHEL/CentOS/Amazon Linux..."
            sudo rpm --import https://packages.wazuh.com/key/GPG-KEY-WAZUH
            cat | sudo tee /etc/yum.repos.d/wazuh.repo << EOF
[wazuh]
gpgcheck=1
gpgkey=https://packages.wazuh.com/key/GPG-KEY-WAZUH
enabled=1
name=EL-\$releasever - Wazuh
baseurl=https://packages.wazuh.com/4.x/yum/
protect=1
EOF
            sudo WAZUH_MANAGER="$WAZUH_MANAGER" yum install -y wazuh-agent
            ;;
    esac
    echo "✓ Agent installed"
fi

# Update agent configuration
echo ""
echo "Configuring agent..."
if [ "$OS" = "macos" ]; then
    sudo sed -i.bak "s|<address>.*</address>|<address>$WAZUH_MANAGER</address>|" "$AGENT_PATH/etc/ossec.conf"
else
    sudo sed -i.bak "s|<address>.*</address>|<address>$WAZUH_MANAGER</address>|" "$AGENT_PATH/etc/ossec.conf"
fi
echo "✓ Configuration updated"

# Register agent with manager
echo ""
echo "Registering agent with manager..."
if [ "$OS" = "macos" ]; then
    sudo "$AGENT_PATH/bin/agent-auth" -m "$WAZUH_MANAGER" -A "$AGENT_NAME" ${AGENT_GROUPS:+-G "$AGENT_GROUPS"}
else
    sudo "$AGENT_PATH/bin/agent-auth" -m "$WAZUH_MANAGER" -A "$AGENT_NAME" ${AGENT_GROUPS:+-G "$AGENT_GROUPS"}
fi
echo "✓ Agent registered"

# Start/restart agent
echo ""
echo "Starting agent..."
if [ "$OS" = "macos" ]; then
    sudo "$AGENT_PATH/bin/wazuh-control" restart
else
    sudo systemctl daemon-reload
    sudo systemctl enable wazuh-agent
    sudo systemctl restart wazuh-agent
fi
echo "✓ Agent started"

# Verify
echo ""
echo "Verifying agent status..."
sleep 5

if [ "$OS" = "macos" ]; then
    STATUS=$(sudo "$AGENT_PATH/bin/wazuh-control" status 2>/dev/null | grep "wazuh-agentd is running" || echo "")
else
    STATUS=$(sudo systemctl is-active wazuh-agent 2>/dev/null || echo "")
fi

if [ -n "$STATUS" ]; then
    echo "✓ Agent is running"
else
    echo "⚠ Agent may not be running. Check logs:"
    if [ "$OS" = "macos" ]; then
        echo "  sudo tail -f $AGENT_PATH/logs/ossec.log"
    else
        echo "  sudo journalctl -u wazuh-agent -f"
    fi
fi

echo ""
echo "=========================================="
echo "Registration Complete!"
echo "=========================================="
echo ""
echo "Manager: $WAZUH_MANAGER"
echo "Agent Name: $AGENT_NAME"
echo ""
echo "Check agent status in Wazuh dashboard:"
echo "  https://$WAZUH_MANAGER"
echo "  Login: admin / SecretPassword"
echo ""
echo "Agent logs:"
if [ "$OS" = "macos" ]; then
    echo "  sudo tail -f $AGENT_PATH/logs/ossec.log"
else
    echo "  sudo journalctl -u wazuh-agent -f"
fi
echo ""
