# Manual installation steps – Machine 3 (NS-03) – corp-ad-01

**Role:** Active Directory, Jump Host  
**OS:** Windows Server 2022  
**Software (from CSV):** putty, winscp, nodejs, npm

Connect as **Administrator** (RDP). Run PowerShell or Command Prompt as Administrator where noted.

---

## 1. Install Chocolatey (if not already installed)

In **PowerShell (Run as Administrator)**:

```powershell
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
```

Close and reopen PowerShell as Administrator after install.

---

## 2. Install software via Chocolatey

In **PowerShell (Run as Administrator)**:

```powershell
choco install putty winscp nodejs npm -y
```

---

## 3. Install Wazuh agent (optional – for central monitoring)

Replace `WAZUH_MANAGER_IP` with your Wazuh server (e.g. 44.194.78.195).

**Option A – Download and install via MSI (silent):**

```powershell
# Create temp dir if needed
New-Item -ItemType Directory -Force -Path C:\Temp | Out-Null

# Download
Invoke-WebRequest -Uri "https://packages.wazuh.com/4.x/windows/wazuh-agent-4.7.2-1.msi" -OutFile C:\Temp\wazuh-agent.msi -UseBasicParsing

# Install (replace WAZUH_MANAGER_IP with actual IP)
Start-Process msiexec.exe -ArgumentList '/q', 'WAZUH_MANAGER=WAZUH_MANAGER_IP', '/i', 'C:\Temp\wazuh-agent.msi' -Wait
```

**Option B – GUI:** Run the downloaded MSI and set the manager address when prompted.

---

## 4. Set Wazuh service to start automatically and start it

In **PowerShell (Run as Administrator)**:

```powershell
Set-Service -Name WazuhSvc -StartupType Automatic
Start-Service -Name WazuhSvc
```

---

## 5. Verify Wazuh service

```powershell
Get-Service WazuhSvc
```

Status should be **Running** and StartType **Automatic**.

---

## 6. Create AMI

After all software is installed and Wazuh (if used) is set to Automatic and running:

1. In AWS Console: EC2 → Instances → select this instance → Actions → Image and templates → **Create image**.
2. Name the AMI (e.g. `corp-ad-01-configured`).
3. New instances launched from this AMI will have the same software; WazuhSvc will start at boot if set to Automatic.

---

## Notes

- **Putty / WinSCP / Node.js:** These are applications; they do not run as Windows services. They will be present on instances launched from the AMI.
- **WazuhSvc** is the only service in this list that must be set to **Automatic** so it starts when the machine boots.
