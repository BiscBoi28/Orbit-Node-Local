# Wazuh Agent Registration

Automated script to register agents with the Wazuh manager.

## Supported Platforms

- macOS (Intel & Apple Silicon)
- Ubuntu/Debian
- CentOS/RHEL
- Amazon Linux

## Quick Start

1. Edit `config.sh` and set the Wazuh manager IP:
   ```bash
   WAZUH_MANAGER="54.163.6.185"
   ```

2. Run the registration script:
   ```bash
   ./register-agent.sh
   ```

## Configuration

Edit `config.sh` before running:

```bash
# Wazuh Manager IP or hostname (REQUIRED)
WAZUH_MANAGER="54.163.6.185"

# Agent name (optional - defaults to hostname)
AGENT_NAME=""

# Agent groups (optional - comma-separated)
AGENT_GROUPS=""
```

## What the Script Does

1. Detects your operating system
2. Downloads and installs the Wazuh agent (if not already installed)
3. Configures the agent to connect to your Wazuh manager
4. Registers the agent with the manager
5. Starts the agent service
6. Verifies the agent is running

## Manual Steps (if script fails)

### macOS

```bash
# Download agent
curl -so wazuh-agent.pkg https://packages.wazuh.com/4.x/macos/wazuh-agent-4.14.2-1.arm64.pkg

# Install
sudo installer -pkg ./wazuh-agent.pkg -target /

# Configure
sudo sed -i.bak 's|<address>.*</address>|<address>54.163.6.185</address>|' /Library/Ossec/etc/ossec.conf

# Register
sudo /Library/Ossec/bin/agent-auth -m 54.163.6.185

# Start
sudo /Library/Ossec/bin/wazuh-control start
```

### Ubuntu/Debian

```bash
# Add repository
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | sudo gpg --no-default-keyring --keyring gnupg-ring:/usr/share/keyrings/wazuh.gpg --import
sudo chmod 644 /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" | sudo tee /etc/apt/sources.list.d/wazuh.list

# Install
sudo apt-get update
sudo WAZUH_MANAGER="54.163.6.185" apt-get install -y wazuh-agent

# Register
sudo /var/ossec/bin/agent-auth -m 54.163.6.185

# Start
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

### CentOS/RHEL/Amazon Linux

```bash
# Add repository
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

# Install
sudo WAZUH_MANAGER="54.163.6.185" yum install -y wazuh-agent

# Register
sudo /var/ossec/bin/agent-auth -m 54.163.6.185

# Start
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

## Troubleshooting

### Check agent status

**macOS:**
```bash
sudo /Library/Ossec/bin/wazuh-control status
sudo tail -f /Library/Ossec/logs/ossec.log
```

**Linux:**
```bash
sudo systemctl status wazuh-agent
sudo journalctl -u wazuh-agent -f
```

### Agent not connecting

1. Verify manager IP is correct in config.sh
2. Check firewall allows ports 1514, 1515 (TCP) and 514 (UDP)
3. Verify agent is registered in Wazuh dashboard
4. Check agent logs for connection errors

### Re-register agent

If you need to re-register (e.g., manager IP changed):

1. Update `config.sh` with new manager IP
2. Run `./register-agent.sh` again

## Wazuh Dashboard

Access the dashboard to see your registered agents:

- URL: https://54.163.6.185
- Username: admin
- Password: SecretPassword

Navigate to "Agents" in the left menu to see all registered agents.
