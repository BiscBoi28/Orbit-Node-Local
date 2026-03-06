# Runbook – Bank Simulation

How to run the scripts, what to configure, and how the asset CSV drives the deployment.

---

## 1. Prerequisites

- **AWS CLI** configured (`aws sts get-caller-identity` works).
- **Ansible** (with collections: `community.aws`, `ansible.windows`, `chocolatey.chocolatey`).
- **Python 3** (for inventory/validation scripts).

Install Ansible collections if needed:

```bash
ansible-galaxy collection install community.aws community.windows ansible.windows chocolatey.chocolatey
```

---

## 2. Configuration: `config/deployment.env`

All scripts source **`config/deployment.env`**. Set these before running anything.

| Variable | Required | Description |
|----------|----------|-------------|
| `AWS_REGION` | Yes | e.g. `us-east-1` |
| `AWS_PROFILE` | No | AWS CLI profile (default: `default`) |
| `USE_SSM` | Yes | `true` = Ansible over SSM (no SSH key). Use when instances have no key pair. |
| `SSM_BUCKET_NAME` | If USE_SSM=true | S3 bucket for SSM (same account/region). Can be left empty if pre-requirements stack provides it. |
| `SSH_PRIVATE_KEY_FILE` | If USE_SSM=false | Path to `.pem` for Ansible SSH. |
| `KEY_PAIR_NAME` | No | EC2 key pair name if you attach one. |
| `PRE_REQ_STACK` | Yes | Pre-requirements CloudFormation stack name (e.g. `njsecure-prod-pre-requirements`). |
| `SECRETS_STACK` | Yes | Secrets stack name (e.g. `njsecure-prod-secrets`). |
| `EC2_STACK_PREFIX` | Yes | Prefix for EC2 stacks (e.g. `njsecure-prod-ec2` → stacks `njsecure-prod-ec2-ns-01`, etc.). |
| `WAZUH_SERVER_IP` | For agents | Wazuh manager IP for agent registration. |
| `WAZUH_SERVER_PORT` | No | Default `1514`. |
| `CSV_FILE` | No | Full path to asset CSV. Default: `../ORBIT_simulated_bank.csv` from config dir. |

Example (minimal):

```bash
# config/deployment.env
AWS_REGION=us-east-1
AWS_PROFILE=default
USE_SSM=true
SSM_BUCKET_NAME=your-ssm-bucket-name
PRE_REQ_STACK=njsecure-prod-pre-requirements
SECRETS_STACK=njsecure-prod-secrets
EC2_STACK_PREFIX=njsecure-prod-ec2
WAZUH_SERVER_IP=1.2.3.4
WAZUH_SERVER_PORT=1514
```

---

## 3. Asset CSV: `ORBIT_simulated_bank.csv`

The CSV is the **source of truth** for which machines exist and what runs on them.

### Location

- Default path: **`cloudFormationScripts-Bank-simulation/ORBIT_simulated_bank.csv`** (or set `CSV_FILE` in `config/deployment.env`).

### Columns

| Column | Purpose |
|--------|--------|
| `Asset_ID` | Short id (e.g. `NS-01`). Used for stack names: `{EC2_STACK_PREFIX}-ns-01`. |
| `Hostname` | Instance hostname (e.g. `corebank-db-01`). Set on the VM and used in Ansible inventory. |
| `AWS_Resource_Type` | e.g. `EC2`. |
| `Operating_System` | Drives template and params. Values like: `Linux (RHEL 8)`, `Linux (Ubuntu 22.04)`, `Windows Server 2022`. |
| `Instance_Size` | e.g. `t3.micro`. |
| `Technical_Role` | Role(s) used to pick security groups (e.g. `Database Server,Application Server`, `Web Server`, `Active Directory,Jump Host`). |
| `OpenSource_Software_To_Install` | Comma-separated list of packages to install (RHEL/Ubuntu: yum/apt; Windows: Chocolatey). |

### Example rows

```csv
Asset_ID,Hostname,AWS_Resource_Type,Operating_System,Instance_Size,Technical_Role,OpenSource_Software_To_Install
NS-01,corebank-db-01,EC2,Linux (RHEL 8),t3.micro,"Database Server,Application Server","postgresql15,postgresql15-server,java-11-openjdk,tomcat,nodejs,npm"
NS-02,corebank-web-01,EC2,Linux (Ubuntu 22.04),t3.micro,Web Server,"nginx,php8.1,nodejs,npm"
NS-03,corp-ad-01,EC2,Windows Server 2022,t3.micro,"Active Directory,Jump Host","putty,winscp,nodejs,npm"
```

### How it’s used

- **03-ec2/deploy.sh** reads the CSV and creates one CloudFormation stack per row (Hostname, OS, size, role, software, etc.).
- **04-configuration/inventory/generate_inventory.sh** uses the same CSV and stack outputs to build `hosts.ini` and `host_software.yml`.
- **07-validation_installation** uses the CSV to generate expected OS and packages and validate installed software and services.

To add or remove a machine: edit the CSV, then run the EC2 deploy (for that asset or all) and regenerate inventory.

---

## 4. Run order (high level)

1. **Pre-requirements** → **Secrets** → **EC2** (one or more machines).
2. **Inventory** (generated from stacks + CSV).
3. **Configure** (install software + Wazuh agents).
4. **Validation** (optional; checks OS, packages, services vs CSV).

---

## 5. Scripts and how to run them

All from repo root: **`cloudFormationScripts-Bank-simulation/`**.

### One-shot: deploy and configure everything

Uses CSV to deploy all EC2 stacks, then runs inventory and configuration for all hosts:

```bash
./06-orchestrator/deploy_all.sh
```

This runs:

1. `01-pre-requirements/deploy.sh` create  
2. `02-secrets/deploy.sh` create  
3. `03-ec2/deploy.sh` create (all rows in CSV)  
4. `04-configuration/inventory/generate_inventory.sh`  
5. `04-configuration/run.sh` all (install software + register Wazuh)

Logs go to `logs/deploy_<timestamp>.log`.

---

### Per-machine deploy (EC2 only)

Deploy a single machine by asset id (must exist in CSV):

```bash
./06-orchestrator/deploy_machine_1.sh   # NS-01  → corebank-db-01   (Linux RHEL)
./06-orchestrator/deploy_machine_2.sh   # NS-02  → corebank-web-01 (Linux Ubuntu)
./06-orchestrator/deploy_machine_3.sh   # NS-03  → corp-ad-01      (Windows)
```

Each script:

- Calls `03-ec2/deploy.sh` with the matching asset (e.g. `ns-01`, `ns-02`, `ns-03`).
- Waits for that stack to be created/updated.

---

### Per-machine configure (software + Wazuh)

After the EC2 instance for a machine exists and (for SSM) is connected, run:

```bash
./06-orchestrator/configure_machine_1.sh   # corebank-db-01   (Linux: packages + Wazuh)
./06-orchestrator/configure_machine_2.sh   # corebank-web-01 (Linux: packages + Wazuh)
./06-orchestrator/configure_machine_3.sh   # corp-ad-01      (Windows: Chocolatey + Wazuh)
```

Each script:

1. Resolves hostname from the stack (e.g. `ns-01` → `corebank-db-01`).
2. Runs `04-configuration/inventory/generate_inventory.sh`.
3. Runs the right install playbook (`install_software_linux.yaml` or `install_software_windows.yaml`) with `--limit <hostname>`.
4. Runs `register_wazuh_agent.yaml` with `--limit <hostname>`.

Logs: `logs/configure_machine_<n>_<timestamp>.log`.

---

### Tear-down (all EC2 + optional pre-req/secrets)

```bash
./06-orchestrator/destroy_all.sh
```

Destroys EC2 stacks (from CSV / `EC2_STACK_PREFIX`), then optionally secrets and pre-requirements. Confirm when prompted.

---

### Validation (vs CSV)

After deployment and configuration, check that OS, packages, and services match the CSV:

```bash
./07-validation_installation/run_validation.sh
```

This:

1. Regenerates inventory.
2. Builds `07-validation_installation/expected_installation.yml` from the CSV.
3. Runs `07-validation_installation/playbooks/validate_installation.yaml` (OS, package list, and service stop/start where applicable).

Log: `logs/validation_<timestamp>.log`.

---

## 6. Other useful commands

- **Regenerate inventory only** (after stacks exist):

  ```bash
  bash 04-configuration/inventory/generate_inventory.sh
  ```

- **Configure all hosts** (install software + Wazuh) without redeploying:

  ```bash
  # Ensure inventory is up to date first
  bash 04-configuration/inventory/generate_inventory.sh
  04-configuration/run.sh all
  ```

- **Only install software** (no Wazuh):

  ```bash
  04-configuration/run.sh install-software
  ```

- **Only register Wazuh agents**:

  ```bash
  04-configuration/run.sh register-wazuh
  ```

---

## 7. Summary table

| Goal | Script / command |
|------|-------------------|
| Set config | Edit `config/deployment.env` |
| Define machines | Edit `ORBIT_simulated_bank.csv` |
| Deploy + configure everything | `./06-orchestrator/deploy_all.sh` |
| Deploy one machine | `./06-orchestrator/deploy_machine_1.sh` (or 2 or 3) |
| Configure one machine | `./06-orchestrator/configure_machine_1.sh` (or 2 or 3) |
| Validate vs CSV | `./07-validation_installation/run_validation.sh` |
| Destroy all | `./06-orchestrator/destroy_all.sh` |
