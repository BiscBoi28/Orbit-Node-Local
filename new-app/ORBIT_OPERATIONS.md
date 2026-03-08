# ORBIT Node – You're Live on AWS 🎉

## What Just Happened

Your ORBIT Node security orchestration system is now running on AWS EC2.
Three services are live and talking to each other:

| Service | What it does | URL |
|---------|-------------|-----|
| ORC | The brain — FastAPI app, all endpoints | http://16.58.158.189:8000 |
| Neo4j | Graph database — stores hosts, assets, alerts | http://16.58.158.189:7474 |
| Presidio | PII scanner — finds SSNs, credit cards, emails | http://16.58.158.189:5001 |

---

## Daily Use

### Check if everything is running

SSH in and check:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
cd ~/orbit
docker compose ps
```

All three should show `(healthy)`:
```
orbit-neo4j      Up (healthy)
orbit-presidio   Up (healthy)
orbit-orc        Up (healthy)
```

Or just hit the health endpoint from your browser or terminal:
```bash
curl http://16.58.158.189:8000/health
```
Expected: `{"status":"healthy","neo4j":"connected"}`

### View the graph visually

Open in your browser: **http://16.58.158.189:7474**
- Username: `neo4j`
- Password: `T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA`

Useful queries to run in the browser:
```cypher
// See everything
MATCH (n) RETURN n LIMIT 50;

// All hosts
MATCH (h:Host) RETURN h.host_id, h.os, h.role;

// Crown jewel assets
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN h.host_id, d.sensitivity_score;

// All ActionCards
MATCH (a:ActionCard) RETURN a.action_id, a.priority, a.status;
```

---

## The 3 API Endpoints You'll Use

### 1. Ingest a data change (triggers PII scan)
```bash
curl -X POST http://16.58.158.189:8000/ingest/data-change \
  -H "Content-Type: application/json" \
  -d '{
    "asset_id": "corebank-db-01",
    "content_items": ["your text here containing possible PII"]
  }'
```

### 2. Ingest a security alert (creates ActionCard)
```bash
curl -X POST http://16.58.158.189:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d '{
    "alert_id": "ALERT-001",
    "summary": "Describe the alert here",
    "confidence": 0.9,
    "affected": {"hosts": ["corebank-db-01"]},
    "metadata": {"base_severity": "HIGH", "cve_id": "CVE-2024-XXXXX"}
  }'
```

### 3. Query crown jewels
```bash
curl http://16.58.158.189:8000/query/crown-jewels
```

---

## When the Server is Turned Off

AWS may assign a new IP when the server restarts. Always check first:
```bash
aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].{State:State.Name,IP:PublicIpAddress}" \
  --output table
```

If it's stopped, start it:
```bash
INSTANCE_ID=$(aws ec2 describe-instances \
  --region us-east-2 \
  --filters "Name=tag:Name,Values=orbit-dev" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text)

aws ec2 start-instances --region us-east-2 --instance-ids $INSTANCE_ID
aws ec2 wait instance-running --region us-east-2 --instance-ids $INSTANCE_ID
```

Then get the new IP and use that for all subsequent commands.

Containers start automatically after a reboot. If they don't:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@NEW_IP
cd ~/orbit
docker compose up -d
```

---

## Reading Logs

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189

# ORC logs (most useful)
cd ~/orbit && docker compose logs --tail=50 orc

# Follow live
cd ~/orbit && docker compose logs -f orc

# Neo4j logs
cd ~/orbit && docker compose logs --tail=50 neo4j
```

---

## Deploying Code Changes

When you update your code locally, push it to the server:

```bash
# From new-app directory in WSL:
rsync -avz \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.env' \
  --exclude '.git' \
  -e "ssh -i ~/.ssh/iiith-orbit-key.pem" \
  ./ \
  ubuntu@16.58.158.189:~/orbit/

# Then rebuild only ORC (leaves Neo4j data untouched):
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189 \
  "cd ~/orbit && docker compose build orc && docker compose up -d --no-deps orc"
```

---

## Re-seeding the Database

Safe to run any time — uses MERGE so no duplicates created:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189 \
  "cd ~/orbit && docker compose exec -T orc python -m app.seed"
```

---

## Something Broke — Debugging Steps

Go through in order:

**1. Are containers running?**
```bash
cd ~/orbit && docker compose ps
```

**2. What do ORC logs say?**
```bash
cd ~/orbit && docker compose logs --tail=50 orc
```
Look for `ERROR`, `ModuleNotFoundError`, `ConnectionRefused`.

**3. Is Neo4j reachable?**
```bash
curl http://localhost:8000/health
```
If `neo4j: disconnected` — Neo4j is the problem, check its logs.

**4. Is Presidio working?**
```bash
curl http://localhost:5001/health
```
If this fails, PII detection silently returns 0. Always check explicitly.

**5. Is .env present?**
```bash
ls -la ~/orbit/.env
```
If missing, re-create it (see Directive 02).

**6. Does the database have data?**
```bash
docker exec orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA \
  "MATCH (h:Host) RETURN count(h);"
```
Should return 3. If 0, re-run the seed.

---

## Nuclear Option (full wipe and restart)

⚠️ This deletes ALL graph data permanently. Only use intentionally.

```bash
cd ~/orbit
docker compose down -v
docker compose up -d
sleep 90
docker compose exec -T orc python -m app.seed
```

---

## What's Next (when GitHub is available)

- Set up Directive 06 (GitHub Actions auto-deploy) so code pushes deploy automatically

---

## Key Facts

| Thing | Value |
|-------|-------|
| Server | orbit-dev |
| Current IP | 16.58.158.189 (may change after restart) |
| Region | us-east-2 |
| SSH user | ubuntu |
| SSH key | ~/.ssh/iiith-orbit-key.pem |
| Neo4j password | T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA |
| ORC API | http://16.58.158.189:8000 |
| Neo4j Browser | http://16.58.158.189:7474 |
