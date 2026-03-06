# Manual installation steps – Machine 1 (NS-01) – corebank-db-01

**Role:** Database Server, Application Server  
**OS:** Linux (RHEL 8) / Amazon Linux 2023  
**Software (from CSV):** postgresql15, postgresql15-server, java-11-openjdk, tomcat, nodejs, npm

Connect as `ec2-user` (or root). All commands below assume `sudo` if not root.

---

## 1. Install packages

### RHEL 8 / Amazon Linux 2

```bash
# PostgreSQL 15 (enable module if available, then install)
sudo dnf module enable postgresql:15 -y 2>/dev/null || true
sudo dnf install -y postgresql15 postgresql15-server

# Java 11 and Tomcat
sudo dnf install -y java-11-openjdk java-11-openjdk-devel
sudo dnf install -y tomcat tomcat-admin-webapps tomcat-webapps 2>/dev/null || true
# If tomcat not in repos, use: sudo dnf install -y tomcat9 tomcat9-admin-webapps 2>/dev/null || true

# Node.js and npm
sudo dnf install -y nodejs npm
```

### Amazon Linux 2023

```bash
sudo dnf install -y postgresql15 postgresql15-server
sudo dnf install -y java-11-openjdk java-11-openjdk-devel
sudo dnf install -y tomcat nodejs npm 2>/dev/null || true
# If tomcat not in default repos, install from Apache or use tomcat9 package if available
```

---

## 2. Initialize and configure PostgreSQL (run once)

```bash
sudo postgresql-setup --initdb 2>/dev/null || sudo /usr/bin/postgresql-15-setup initdb 2>/dev/null || true
```

---

## 3. Install Wazuh agent (optional – for central monitoring)

Replace `WAZUH_MANAGER_IP` with your Wazuh server (e.g. from config: 44.194.78.195).

```bash
sudo dnf install -y https://packages.wazuh.com/4.x/yum/wazuh-agent-4.7.2-1.x86_64.rpm
```

Edit manager address:

```bash
sudo sed -i 's|^<address>.*</address>|  <address>WAZUH_MANAGER_IP</address>|' /var/ossec/etc/ossec.conf
```

---

## 4. Enable and start system services (so they start at boot)

Run these so every service is enabled (start on boot) and started now:

```bash
# PostgreSQL
sudo systemctl enable postgresql-15 2>/dev/null || sudo systemctl enable postgresql
sudo systemctl start postgresql-15 2>/dev/null || sudo systemctl start postgresql

# Tomcat
sudo systemctl enable tomcat 2>/dev/null || sudo systemctl enable tomcat9 2>/dev/null || true
sudo systemctl start tomcat 2>/dev/null || sudo systemctl start tomcat9 2>/dev/null || true

# Wazuh agent (if installed)
sudo systemctl enable wazuh-agent
sudo systemctl start wazuh-agent
```

---

## 5. Verify services

```bash
sudo systemctl is-active postgresql-15 postgresql tomcat tomcat9 wazuh-agent 2>/dev/null
sudo systemctl is-enabled postgresql-15 postgresql tomcat tomcat9 wazuh-agent 2>/dev/null
```

---

## 6. Create AMI

After all software is installed and all services are enabled and running:

1. In AWS Console: EC2 → Instances → select this instance → Actions → Image and templates → Create image.
2. Name the AMI (e.g. `corebank-db-01-configured`).
3. New instances launched from this AMI will have the same software and services set to start at boot.
