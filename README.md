# ORBIT Node – Infrastructure

ORBIT (Orchestrated Resilience-Based Intelligence & Telemetry) is a prototype cyber-graph platform that correlates security signals, sensitivity scores, and graph relationships to generate actionable remediation cards.

This repository contains the AWS CloudFormation scripts and setup automation to provision the two-EC2 sandbox environment described in the ORBIT Node Design Document.

---

## Architecture

```
┌─────────────────────── AWS VPC (10.0.0.0/16) ─────────────────────────┐
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  Public Subnet (10.0.1.0/24)                                     │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────┐   ┌────────────────────────────┐   │  │
│  │  │  wazuh-dev EC2          │   │  orbit-dev EC2             │   │  │
│  │  │  (t3.large)             │   │  (t3.large)                │   │  │
│  │  │                         │   │                            │   │  │
│  │  │  Docker:                │   │  Docker:                   │   │  │
│  │  │  ├─ wazuh.manager       │◄──┤  ├─ orbit-neo4j            │   │  │
│  │  │  ├─ wazuh.indexer       │   │  ├─ orbit-presidio         │   │  │
│  │  │  └─ wazuh.dashboard     │   │  ├─ orbit-juice-shop       │   │  │
│  │  │                         │   │  └─ orbit-orc              │   │  │
│  │  │  Nginx (reverse proxy)  │   │                            │   │  │
│  │  │  EBS: /data (100 GB)    │   │  Wazuh agent → wazuh-dev  │   │  │
│  │  │                         │   │  EBS: /data  (80 GB)      │   │  │
│  │  └─────────────────────────┘   └────────────────────────────┘   │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  AWS Secrets Manager: orbit/node/*                                      │
│  S3: iiith-orbit-wazuh-scripts  (setup scripts)                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Dataflow

```
Assets (Wazuh agent on orbit-dev) → Wazuh (wazuh-dev) → ORC
ORC → Presidio → ORC
ORC → Neo4j
ORC → Core → ORC
ORC → Wazuh HITL UI → ORC
Bloom/NeoDash → Neo4j (read-only)
```

---

## Repository Structure

```
.
├── cloudFormationScripts-wazuh/        # wazuh-dev EC2 (Wazuh manager stack)
│   ├── 01-pre-deployment/              # VPC, SG, IAM, EBS (100 GB), EIP
│   ├── 02-secrets/                     # AWS Secrets Manager (Wazuh + Neo4j creds)
│   ├── 03-ec2-deployment/              # EC2 + wazuh-setup.sh via S3 (+ scripts/health-check.sh)
│   ├── 04a-wazuh-ansible-customized/   # Ansible alternative for Wazuh install
│   ├── 05-agent-registration/          # Register external agents with Wazuh
│   ├── README.md
│   ├── RUNBOOK_DEPLOY.md
│   ├── CONFIGURATION.md
│   └── QUICK_REFERENCE.md
│
└── cloudFormationScripts-orbit-dev/    # orbit-dev EC2 (app services stack)
    ├── 01-pre-deployment/              # SG, IAM, EBS (80 GB), EIP (shares wazuh VPC)
    └── 02-ec2-deployment/              # EC2 + orbit-dev-setup.sh via S3
        └── scripts/
            ├── orbit-dev-setup.sh     # Starts Neo4j, Presidio, Juice Shop, ORC + Wazuh agent
            ├── health-check.sh        # Per-service health check (containers + endpoints)
            └── start-services.sh     # Manually start Docker stack (e.g. after first boot)
```

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| AWS CLI | Deploying CloudFormation stacks |
| `jq` | JSON parsing in deploy scripts |
| Bash | Running deploy scripts (macOS / Linux) |
| AWS key pair `iiith-orbit-key` | SSH access to EC2 instances |

Required AWS permissions: CloudFormation, EC2, IAM, Secrets Manager, S3, SSM.

---

## Deployment

Deploy **wazuh-dev first** — orbit-dev shares its VPC and points its Wazuh agent at wazuh-dev's Elastic IP.

### wazuh-dev (Wazuh manager + dashboard)

```bash
# 1. One-time: VPC, security group, IAM, EBS, Elastic IP
cd cloudFormationScripts-wazuh/01-pre-deployment
bash create-pre-deployment-stack.sh          # ~3-5 min

# 2. One-time: credentials in Secrets Manager
cd ../02-secrets
bash create-secrets-stack.sh                 # ~1-2 min

# 3. EC2 + Wazuh via Ansible
cd ../03-ec2-deployment
bash deploy-ec2-stack.sh                     # ~5-7 min (EC2 up)

cd ../04a-wazuh-ansible-customized
bash run-ec2.sh                              # ~5-10 min (Wazuh install)
```

Access: `https://<WAZUH_ELASTIC_IP>` — user `admin` / `SecretPassword`

---

### orbit-dev (Neo4j · Presidio · Juice Shop · ORC · Wazuh agent)

> The deploy script automatically reads the wazuh pre-deployment stack for the shared VPC/Subnet.

```bash
# 1. One-time: security group, IAM, EBS, Elastic IP
cd cloudFormationScripts-orbit-dev/01-pre-deployment
bash create-pre-deployment-stack.sh          # ~3-5 min

# 2. EC2 + all services
cd ../02-ec2-deployment
bash deploy-ec2-stack.sh                     # ~5-7 min (EC2 up)
                                             # ~8-10 min (services healthy)
```

Monitor the setup inside the instance:

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
tail -f /var/log/orbit-dev-setup.log
```

---

## Service Endpoints

### wazuh-dev

| Service | URL / Port | Credentials |
|---------|-----------|-------------|
| Wazuh Dashboard | `https://<WAZUH_IP>` | admin / SecretPassword |
| Wazuh API | `https://<WAZUH_IP>:55000` | wazuh-wui / Wazuh@2024Pass |
| Agent enrollment | TCP 1514–1515 | — |

### orbit-dev

| Service | URL / Port | Notes |
|---------|-----------|-------|
| Neo4j Browser | `http://16.58.158.189:7474` | user `neo4j`; password in `/data/orbit-dev/.env` |
| Neo4j Bolt | `bolt://16.58.158.189:7687` | For driver / ORC connections |
| Presidio Analyzer | `http://16.58.158.189:5001` | `POST /analyze` REST API |
| OWASP Juice Shop | `http://16.58.158.189:3000` | Prototype "customer-facing app" |
| ORC | `http://16.58.158.189:8000` | nginx placeholder; replace with real service |

---

## Secrets

All credentials are stored in AWS Secrets Manager under `orbit/node/*`.

| Secret | Contents |
|--------|---------|
| `orbit/node/wazuh-indexer-credentials` | Wazuh indexer admin password |
| `orbit/node/wazuh-api-credentials` | Wazuh API credentials |
| `orbit/node/neo4j-credentials` | Neo4j Aura URI + credentials (also used as local Neo4j password) |
| `orbit/node/orbit-core-api-token` | ORBIT Core API token (set to `CHANGE_ME` until Core is live) |

---

## Useful Commands

### Check stack outputs

```bash
REGION=us-east-2

# wazuh-dev Elastic IP
aws cloudformation describe-stacks \
  --stack-name iiith-orbit-node-pre-deployment-dev \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ElasticIP`].OutputValue' \
  --output text

# orbit-dev Elastic IP
aws cloudformation describe-stacks \
  --stack-name iiith-orbit-dev-pre-deployment-dev \
  --region $REGION \
  --query 'Stacks[0].Outputs[?OutputKey==`ElasticIP`].OutputValue' \
  --output text
```

### SSM session (no SSH key required)

```bash
INSTANCE_ID=$(aws cloudformation describe-stacks \
  --stack-name iiith-orbit-dev-ec2 --region us-east-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`InstanceId`].OutputValue' \
  --output text)
aws ssm start-session --target "$INSTANCE_ID" --region us-east-2
```

### orbit-dev service health

```bash
# One-command health check (containers + Neo4j, Presidio, Juice Shop, ORC, Wazuh agent)
# On instance after deploy (script is downloaded to /data/scripts/):
sudo bash /data/scripts/health-check.sh
# Or copy from cloudFormationScripts-orbit-dev/02-ec2-deployment/scripts/ and run: sudo bash health-check.sh

# All containers
docker compose -f /data/orbit-dev/docker-compose.yml ps

# Live logs
docker compose -f /data/orbit-dev/docker-compose.yml logs -f

# Wazuh agent
systemctl status wazuh-agent
/var/ossec/bin/wazuh-control status
```

Health check verifies: **orbit-neo4j**, **orbit-presidio-analyzer**, **orbit-juice-shop**, **orbit-orc** (running + HTTP), and **wazuh-agent** (active).

### wazuh-dev container health

```bash
# One-command health check (manager, indexer, dashboard + nginx)
# On instance after deploy (script is downloaded to /data/scripts/):
sudo bash /data/scripts/health-check.sh

docker ps --filter name=wazuh
docker stats --no-stream --format \
  'table {{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}' | grep wazuh
```

Health check verifies: **wazuh.manager** (port 1514), **wazuh.indexer** (API 9200), **wazuh.dashboard** (5601), and optionally **nginx**.

---

## Registering Additional Agents

To register a laptop or server as a Wazuh agent against wazuh-dev:

```bash
cd cloudFormationScripts-wazuh/05-agent-registration
# Edit config.sh: set WAZUH_MANAGER to the wazuh-dev Elastic IP
bash register-agent.sh
```

Supports macOS (Intel + Apple Silicon), Ubuntu/Debian, CentOS/RHEL, Amazon Linux.

---

## Teardown

Delete stacks in reverse order to avoid dependency errors.

```bash
REGION=us-east-2

# orbit-dev
aws cloudformation delete-stack --stack-name iiith-orbit-dev-ec2             --region $REGION
aws cloudformation wait stack-delete-complete --stack-name iiith-orbit-dev-ec2 --region $REGION

aws cloudformation delete-stack --stack-name iiith-orbit-dev-pre-deployment-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name iiith-orbit-dev-pre-deployment-dev --region $REGION

# wazuh-dev
aws cloudformation delete-stack --stack-name iiith-orbit-node-ec2             --region $REGION
aws cloudformation wait stack-delete-complete --stack-name iiith-orbit-node-ec2 --region $REGION

aws cloudformation delete-stack --stack-name iiith-orbit-node-secrets-dev     --region $REGION
aws cloudformation wait stack-delete-complete --stack-name iiith-orbit-node-secrets-dev --region $REGION

aws cloudformation delete-stack --stack-name iiith-orbit-node-pre-deployment-dev --region $REGION
aws cloudformation wait stack-delete-complete --stack-name iiith-orbit-node-pre-deployment-dev --region $REGION
```

> The pre-deployment stacks hold the Elastic IPs. Deleting them releases the IPs permanently.
> Leave them in place if you plan to redeploy and want to keep the same IP addresses.

---

## Troubleshooting

### CloudFormation stack stuck / failed

```bash
aws cloudformation describe-stack-events \
  --stack-name <STACK_NAME> --region us-east-2 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]' \
  --output table
```

### orbit-dev service not starting / Docker containers not available

```bash
# SSH or SSM in, then:
# 1. Check Docker is running
sudo systemctl status docker
sudo docker info

# 2. Manually start the stack (script on instance after deploy)
sudo bash /data/scripts/start-services.sh

# Or run the commands directly:
cd /data/orbit-dev
sudo docker compose -f docker-compose.yml up -d
sudo docker compose -f docker-compose.yml ps

# 3. Inspect setup and container logs
tail -200 /var/log/orbit-dev-setup.log
tail -200 /var/log/user-data.log
sudo docker compose -f /data/orbit-dev/docker-compose.yml logs -f
```

Common causes:
- **Docker not ready at first boot** — bootstrap now waits for Docker; if you hit this on an older deploy, run `sudo docker compose -f /data/orbit-dev/docker-compose.yml up -d` after SSH in.
- **Neo4j slow to start** — first boot downloads APOC plugin; allow 2–3 min
- **Presidio slow to start** — downloads spaCy `en_core_web_lg` model on first pull; allow 3–5 min
- **EBS not mounted** — check `df -h /data`; if missing, re-run mount manually and re-run `orbit-dev-setup.sh`

### Wazuh agent on orbit-dev not connecting

```bash
systemctl status wazuh-agent
tail -50 /var/ossec/logs/ossec.log
```

Verify the wazuh-dev security group allows inbound TCP 1514–1515 from `0.0.0.0/0`.

### Wazuh dashboard not loading

```bash
# On wazuh-dev:
docker ps --filter name=wazuh
sudo tail -100 /var/log/wazuh-setup.log
sudo systemctl status nginx
```

---

## Configuration Reference

| File | What to change |
|------|---------------|
| `cloudFormationScripts-wazuh/03-ec2-deployment/config/parameters-base.json` | Instance type, key name, region |
| `cloudFormationScripts-wazuh/02-secrets/config/parameters.json` | Wazuh + Neo4j passwords |
| `cloudFormationScripts-orbit-dev/02-ec2-deployment/config/parameters-base.json` | Instance type, key name, wazuh-dev IP, region |
| `cloudFormationScripts-wazuh/04a-wazuh-ansible-customized/inventory/ec2.yml` | Ansible target IP (auto-set by deploy script) |
| `cloudFormationScripts-wazuh/05-agent-registration/config.sh` | Wazuh manager IP for external agents |
