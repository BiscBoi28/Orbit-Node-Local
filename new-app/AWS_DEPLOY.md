# AWS Deployment – Push Local Build to orbit-dev

## Context

Local build is confirmed working. All 6 smoke tests passed locally.
We are now pushing the exact same working state to the AWS server.

## Rules

- Do NOT modify any file inside `app/` for any reason
- Do NOT modify `graph.py` under any circumstances
- If anything fails, show me the full raw error and wait for my instruction
- Never print or commit the `.env` file
- Run all commands in WSL, not PowerShell

---

## Pre-flight Check

Confirm you are in WSL:
```bash
uname -a
```
Must say Linux. If not, switch to WSL terminal before continuing.

Confirm SSH key is in place:
```bash
ls -la ~/.ssh/iiith-orbit-key.pem
```
Must show `-r--------`. If permissions are wrong, fix with:
```bash
chmod 400 ~/.ssh/iiith-orbit-key.pem
```

---

## Step 1 – Check Server State

Get the current server IP (it may have changed since last time):
```bash
aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].{State:State.Name,IP:PublicIpAddress}" \
  --output table
```

If State shows `stopped`, start it:
```bash
INSTANCE_ID=$(aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

aws ec2 start-instances --region us-east-2 --instance-ids $INSTANCE_ID
aws ec2 wait instance-running --region us-east-2 --instance-ids $INSTANCE_ID
echo "Server is running"
```

Get the new IP after start:
```bash
SERVER_IP=$(aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text)
echo "Server IP: $SERVER_IP"
```

Use this IP for all subsequent commands. Do not assume it is still 16.58.158.189.

Test SSH works:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP "echo SSH OK"
```

---

## Step 2 – Clean Up Old Containers on Server

Stop and remove any old containers that conflict with the new deployment.
This does NOT delete Neo4j data volumes.

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "docker stop \$(docker ps -q) 2>/dev/null || true && \
   docker rm \$(docker ps -aq) 2>/dev/null || true && \
   echo Containers cleared"
```

---

## Step 3 – Create Working Directory on Server

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "mkdir -p ~/orbit && echo Directory ready"
```

---

## Step 4 – Write .env on Server

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP 'cat > ~/orbit/.env << EOF
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA
PRESIDIO_URL=http://presidio:3000
CROWN_JEWEL_THRESHOLD=0.75
ROLE_BONUS_DB=0.2
ROLE_BONUS_WEB=0.1
BREADTH_BONUS_MAX=0.2
EOF
chmod 600 ~/orbit/.env
echo .env written'
```

Note: `PRESIDIO_URL` uses port `3000` — that is Presidio's internal Docker port.
Port `5001` is only the external host port. Using `5001` here would break PII detection.

Verify it was written:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cat ~/orbit/.env | grep -v PASSWORD"
```

---

## Step 5 – Copy Files to Server

Copy the exact local build that passed all smoke tests.
Run this from the `new-app` directory:

```bash
rsync -avz \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.venv' \
  --exclude '.git' \
  --exclude 'directives/' \
  --exclude 'execution/' \
  -e "ssh -i ~/.ssh/iiith-orbit-key.pem" \
  ./ \
  ubuntu@$SERVER_IP:~/orbit/
```

Verify files arrived:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "ls ~/orbit/ && echo --- && ls ~/orbit/app/"
```

Expected: `app  fixtures  Neo4j  docker-compose.yml  Dockerfile  requirements.txt`

Confirm `.env` is still present and not overwritten:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "ls -la ~/orbit/.env"
```

---

## Step 6 – Build and Start Containers on Server

SSH in and build:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose pull neo4j presidio"

ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose build orc"

ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose up -d"
```

---

## Step 7 – Wait and Confirm All Three Healthy

Wait 90 seconds for Neo4j to initialise, then check:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose ps"
```

All three must show `(healthy)`:
- orbit-neo4j
- orbit-presidio
- orbit-orc

If any show `(unhealthy)` after 2 minutes, check logs:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose logs --tail=40 orc"
```

Do NOT proceed until all three are healthy.

---

## Step 8 – Run Smoke Tests on Server

```bash
# Test 1 – Health
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "curl -s http://localhost:8000/health"
```
Expected: `{"status":"healthy","neo4j":"connected"}`

```bash
# Test 2 – Seed
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "cd ~/orbit && docker compose exec -T orc python -m app.seed"
```
Expected: 3 hosts loaded, no errors

```bash
# Test 3 – PII Detection
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "curl -s -X POST http://localhost:8000/ingest/data-change \
  -H 'Content-Type: application/json' \
  -d '{\"asset_id\": \"corebank-db-01\", \"content_items\": [\"John Doe SSN 123-45-6789 email john@example.com card 4111111111111111\"]}'"
```
Expected: sensitivity_score > 0, crown_jewel: true

```bash
# Test 4 – ActionCard
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "curl -s -X POST http://localhost:8000/ingest/core-alert \
  -H 'Content-Type: application/json' \
  -d '{\"alert_id\": \"SMOKE-001\", \"summary\": \"Critical PostgreSQL vulnerability\", \"confidence\": 0.95, \"affected\": {\"hosts\": [\"corebank-db-01\"]}, \"metadata\": {\"base_severity\": \"CRITICAL\", \"cve_id\": \"CVE-2024-99999\"}}'"
```
Expected: priority CRITICAL or HIGH, status: pending

```bash
# Test 5 – Crown Jewels
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@$SERVER_IP \
  "curl -s http://localhost:8000/query/crown-jewels"
```
Expected: list containing corebank-db-01

---

## Done When

Show me this summary table and wait for my confirmation before closing:

```
Step 1 – Server running:     ✅ IP=X.X.X.X
Step 2 – Old containers cleared: ✅
Step 3 – Directory ready:    ✅
Step 4 – .env written:       ✅
Step 5 – Files rsynced:      ✅
Step 6 – Images built:       ✅
Step 7 – All 3 healthy:      ✅
Test 1 – Health:             ✅
Test 2 – Seed:               ✅
Test 3 – PII Detection:      ✅
Test 4 – ActionCard:         ✅
Test 5 – Crown Jewels:       ✅
```

## If Anything Fails

1. Show me the complete raw output
2. Do NOT modify anything in `app/` or `graph.py`
3. Wait for my instruction
