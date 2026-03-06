# Manual installation steps – Machine 2 (NS-02) – corebank-web-01

**Role:** Web Server  
**OS:** Linux (Ubuntu 22.04)  
**Software (from CSV):** nginx, php8.1, nodejs, npm

Connect as `ubuntu`. All commands below assume `sudo` if not root.

---

## 1. Update package list

```bash
sudo apt update
```

---

## 2. Install packages

```bash
# Nginx
sudo apt install -y nginx

# PHP 8.1 and common extensions
sudo apt install -y php8.1-fpm php8.1-cli php8.1-common php8.1-mysql php8.1-xml php8.1-curl php8.1-mbstring php8.1-zip

# Node.js and npm (from NodeSource or distro)
sudo apt install -y nodejs npm
# If Ubuntu's node is old, use: curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs
```

---

## 3. Install Wazuh agent (optional – for central monitoring)

Replace `WAZUH_MANAGER_IP` with your Wazuh server (e.g. 44.194.78.195).

```bash
curl -sO https://packages.wazuh.com/4.x/apt/pool/main/w/wazuh-agent/wazuh-agent_4.7.2-1_amd64.deb
sudo dpkg -i wazuh-agent_4.7.2-1_amd64.deb
sudo sed -i 's|^<address>.*</address>|  <address>WAZUH_MANAGER_IP</address>|' /var/ossec/etc/ossec.conf
```

---

## 4. Enable and start system services (so they start at boot)

```bash
# Nginx
sudo systemctl enable nginx
sudo systemctl start nginx

# PHP-FPM
sudo systemctl enable php8.1-fpm
sudo systemctl start php8.1-fpm

# Wazuh agent (if installed)
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

---

## 5. Verify services

```bash
sudo systemctl is-active nginx php8.1-fpm wazuh-agent 2>/dev/null
sudo systemctl is-enabled nginx php8.1-fpm wazuh-agent 2>/dev/null
```

---

## 6. Create AMI

After all software is installed and all services are enabled and running:

1. In AWS Console: EC2 → Instances → select this instance → Actions → Image and templates → **Create image**.
2. Name the AMI (e.g. `corebank-web-01-configured`).
3. New instances launched from this AMI will have the same software and services set to start at boot.
