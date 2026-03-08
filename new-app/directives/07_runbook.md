# Directive 07 – Operations Runbook

## What This Is

Your team's reference for everyday operations: checking status, reading logs, restarting services, debugging issues, and updating the system.

Keep this open whenever you're working with the running system.

---

## Quick Reference

| Task | How |
|------|-----|
| Check if everything is running | SSH in → `docker compose ps` |
| Read logs | SSH in → `docker compose logs orc` |
| Restart a crashed container | SSH in → `docker compose restart orc` |
| Deploy a new version | `rsync` from laptop (or `git pull` on server when GitHub is up) |
| Force a full redeploy | SSH in → `git pull && docker compose up -d --build` |
| Re-seed the database | SSH in → `docker compose exec -T orc python -m app.seed` |
| Something is broken | See: **Debugging Checklist** |

---

## Connect to the Server

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
```

Then `cd ~/orbit` — all commands below assume you're in that directory on the server.

---

## Check System Status

### Are all containers running and healthy?

```bash
cd ~/orbit
docker compose ps --format table
```

Expected: four rows — neo4j, presidio, orc, juiceshop — all showing `running (healthy)`.

| Container      | Port(s)        | Expected Status     |
|----------------|----------------|---------------------|
| orbit-neo4j    | 7474, 7687     | running (healthy)   |
| orbit-presidio | 5001           | running (healthy)   |
| orbit-orc      | 8000           | running (healthy)   |
| orbit-juiceshop| 3000           | running             |

### Is the ORC API responding?

```bash
curl -s http://localhost:8000/health
```

### Is Presidio responding?

```bash
curl -s http://localhost:5001/health
```

### How much disk space is left?

```bash
df -h / && docker system df
```

---

## Reading Logs

### ORC logs (most useful for debugging)

```bash
docker compose logs --tail=50 orc
```

### Follow ORC logs live (watch in real-time)

```bash
docker compose logs -f orc
# Press Ctrl+C to stop
```

### Neo4j logs

```bash
docker compose logs --tail=50 neo4j
```

### Presidio logs

```bash
docker compose logs --tail=50 presidio
```

---

## Restarting Services

### Restart only ORC (leaves Neo4j and Presidio running — data preserved)

```bash
docker compose restart orc
```

### Restart all services (data preserved — volumes are not deleted)

```bash
docker compose restart
```

### Stop everything

```bash
docker compose down
```

### Start everything again (after a stop or server reboot)

```bash
cd ~/orbit
docker compose up -d
```

---

## Deploying Updated Code

### When GitHub is available

```bash
# On the server:
cd ~/orbit
git pull origin main
docker compose up -d --build --no-deps orc
# --build rebuilds the ORC image with new code
# --no-deps leaves neo4j and presidio untouched
```

### When GitHub is down (deploy from your laptop directly)

Run this **on your laptop**:

```bash
rsync -avz \
  --exclude '.venv' \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  --exclude '.tmp' \
  --exclude '.git' \
  --exclude '.env' \
  -e "ssh -i ~/.ssh/iiith-orbit-key.pem" \
  ~/path/to/your/new-app/ \
  ubuntu@16.58.158.189:~/orbit/
```

Then SSH in and rebuild:

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
cd ~/orbit
docker compose up -d --build --no-deps orc
```

---

## Full Redeploy (Pull Everything Fresh)

Use this when you want to rebuild from scratch.
**Neo4j data is preserved** (named volumes are not deleted).

```bash
cd ~/orbit
git pull origin main          # or rsync from laptop if no GitHub
docker compose build orc      # rebuild ORC image
docker compose up -d          # restart everything
sleep 30
docker compose ps             # confirm all healthy
```

---

## Re-seeding the Database

Safe to re-run — uses MERGE so no duplicates are created.

```bash
cd ~/orbit
docker compose exec -T orc python -m app.seed
```

### Full wipe and re-seed (nuclear option — deletes all graph data)

⚠️ Only do this intentionally. All Neo4j data will be permanently deleted.

```bash
cd ~/orbit
docker compose down -v        # -v removes volumes (deletes all graph data)
docker compose up -d
echo "Waiting for Neo4j to initialize..."
sleep 90
docker compose exec -T orc python -m app.seed
```

---

## What to Do When the Server Reboots

All containers have `restart: unless-stopped` so they should come back automatically.
If they don't:

```bash
cd ~/orbit
docker compose up -d
```

If the `.env` file was lost (unlikely but possible):
```bash
# Re-write .env (see Directive 02 for full values)
cat > ~/orbit/.env << 'EOF'
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA
PRESIDIO_URL=http://presidio:5001
CROWN_JEWEL_THRESHOLD=0.75
ROLE_BONUS_DB=0.2
ROLE_BONUS_WEB=0.1
BREADTH_BONUS_MAX=0.2
EOF
docker compose up -d
```

---

## Debugging Checklist

When something isn't working, go through this in order:

**1. Are all containers running?**
```bash
docker compose ps
```
→ If not: check logs for the unhealthy one.

**2. What do the ORC logs say?**
```bash
docker compose logs --tail=100 orc
```
→ Look for `ERROR`, `Exception`, `ConnectionRefused`, `ModuleNotFound`.

**3. Can ORC reach Neo4j?**
```bash
curl -s http://localhost:8000/health
```
→ `/health` checks Neo4j connectivity. If it fails, Neo4j is the problem.

**4. Can ORC reach Presidio?**
```bash
curl -s http://localhost:5001/health
```
→ If Presidio is down, data-change calls silently return 0 sensitivity. Always check this explicitly.

**5. Is the .env file present?**
```bash
cat ~/orbit/.env | grep -v PASSWORD
```
→ Should show 7 non-password variables. If missing, re-write it (see Directive 02).

**6. Does the database have data?**
```bash
docker exec orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA \
  "MATCH (h:Host) RETURN count(h);"
```
→ Should return 3. If 0, re-run the seed.

---

## Useful Neo4j Queries

Run these in the Neo4j Browser at `http://16.58.158.189:7474`
(login: neo4j / T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA)

Or run from the terminal:
```bash
docker exec -it orbit-neo4j cypher-shell \
  -u neo4j \
  -p T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA
```

```cypher
// Count everything in the graph
MATCH (n) RETURN labels(n), count(n) ORDER BY count(n) DESC;

// See all hosts
MATCH (h:Host) RETURN h.host_id, h.os, h.role;

// See all DataAssets and their sensitivity scores
MATCH (d:DataAsset)-[:RESIDES_ON]->(h:Host)
RETURN h.host_id, d.sensitivity_score, d.crown_jewel, d.pii_types
ORDER BY d.sensitivity_score DESC;

// See all ActionCards and their status
MATCH (a:ActionCard) RETURN a.action_id, a.status, a.priority ORDER BY a.priority;

// Crown jewel assets only
MATCH (d:DataAsset {crown_jewel: true})-[:RESIDES_ON]->(h:Host)
RETURN h.host_id, d.sensitivity_score;
```

---

## Team Notes

- **Deployments:** `git pull` on server + `docker compose up -d --build --no-deps orc`. Or rsync from laptop if GitHub is down.
- **Never edit `.env` on the server directly** without also updating Directive 02. Keep them in sync.
- **Never commit `.env`** to the repo — it contains the Neo4j password.
- **The Neo4j Browser** at `http://16.58.158.189:7474` is a great way to visually inspect the graph without writing code.
