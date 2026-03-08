# ORBIT Node – Deployment Directives Overview

## What This Is

Step-by-step directives for deploying the ORBIT Node prototype to AWS.
Follow them in order. Each one has a "Done When" checklist — don't move on until it's complete.

---

## Your Environment

| Thing | Value |
|-------|-------|
| Server name | `orbit-dev` |
| Server public IP | `16.58.158.189` (may change after stop/start) |
| AWS Region | `us-east-2` |
| SSH key | `iiith-orbit-key.pem` |
| SSH user | `ubuntu` |
| SSH command | `ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189` |
| Neo4j password | `T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA` |

---

## Architecture: What Runs Where

Everything runs on **orbit-dev** as Docker containers, managed by one `docker-compose.yml`:

```
orbit-dev (16.58.158.189)
│
└── docker-compose.yml
        ├── neo4j      → ports 7474 (browser), 7687 (bolt)
        ├── presidio   → port 5001
        ├── orc        → port 8000  ← this is what we're deploying
        └── juiceshop  → port 3000  (already running)
```

**Current server state (confirmed):** All containers are stopped. Clean slate — no conflicts.

---

## How to Access the Server

**SSH (main method):**
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
```

**If the server is offline**, start it via AWS CLI:
```bash
aws ec2 start-instances --region us-east-2 --instance-ids <instance-id>
```
See Directive 01 for the full process.

**No GitHub temporarily?** No problem. Use `scp` or `rsync` to copy files directly
from your laptop to the server. Directive 04 covers both paths.

---

## Directive Index

| File | What it covers |
|------|----------------|
| `01_access_and_server_start.md` | SSH setup, starting the EC2 if offline, checking what's running |
| `02_inspect_and_env_setup.md`   | Explore server state, write the .env file |
| `03_dockerfile_and_compose.md`  | Review Dockerfile, create unified docker-compose.yml |
| `04_deploy_new_app.md`          | Copy new-app to server (GitHub or direct SCP), handle existing containers |
| `05_seed_and_verify.md`         | Run seed script, verify Neo4j graph, run smoke tests |
| `06_cicd_pipeline.md`           | GitHub Actions auto-deploy on push (set up when GitHub is back) |
| `07_runbook.md`                 | Day-to-day: logs, restarts, debugging, Neo4j queries |

---

## Execution Scripts (put these in `execution/` in your repo)

| Script | What it does |
|--------|-------------|
| `execution/smoke_test.sh` | Runs 5 API tests against the live server |
| `execution/bootstrap_ec2.sh` | Full bootstrap in one shot (for a fresh server) |

---

## Ground Rules

1. **Never commit `.env`** to the repo — it contains the Neo4j password.
2. **Always check the "Done When" list** before moving to the next directive.
3. **When something breaks:** read the full error, fix it, test again, note what you learned.
4. **GitHub down?** Use `scp`/`rsync` to deploy directly. CI/CD can be set up later.
5. **IP may change** after an EC2 stop/start — always check with `aws ec2 describe-instances` first.

---

## Prerequisites (Before Starting Directive 01)

On your laptop:
- [ ] AWS CLI installed (`aws --version`)
- [ ] AWS CLI configured for the right account (`aws configure` — region: `us-east-2`)
- [ ] `.pem` key saved at `~/.ssh/iiith-orbit-key.pem`
- [ ] Key permissions set: `chmod 400 ~/.ssh/iiith-orbit-key.pem`
- [ ] `new-app` code on your laptop and confirmed working locally
