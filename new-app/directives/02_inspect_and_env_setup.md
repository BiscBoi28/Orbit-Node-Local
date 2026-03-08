# Directive 02 – Inspect the Server and Write the .env File

## Goal

1. Understand what's already on the server (code, containers, directory layout)
2. Write the correct `.env` file so docker-compose can start all services

No SSM Parameter Store needed. We write the `.env` directly because this is a prototype
with a small trusted team and the credentials are already known.

---

## Prerequisites

- [ ] Directive 01 complete — SSH access works, instance is running

---

## Step 1 – Explore What's Already on the Server

SSH in, then run these commands to understand the current state:

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
```

Once inside:

```bash
# What's in the home directory?
ls -la ~

# Is there already a project directory?
ls -la ~/orbit* 2>/dev/null || echo "No orbit directory found"

# Is Docker installed?
docker --version
docker compose version

# What containers are running right now?
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"

# Is there already a docker-compose.yml somewhere?
find ~ -name "docker-compose.yml" 2>/dev/null
find /opt -name "docker-compose.yml" 2>/dev/null

# Is there already a .env file somewhere?
find ~ -name ".env" 2>/dev/null
```

Write down what you find. This determines what you need to do in the next directives.

---

## Step 2 – Create the Working Directory

All ORBIT files will live at `/home/ubuntu/orbit/`. If it already exists, skip the `mkdir` line.

```bash
mkdir -p ~/orbit
cd ~/orbit
```

---

## Step 3 – Write the .env File

This file contains all configuration the ORC app and docker-compose need.
The values come from the credentials file you were given.

```bash
cat > ~/orbit/.env << 'EOF'
# Neo4j
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA

# Presidio (internal Docker network hostname)
PRESIDIO_URL=http://presidio:5001

# ORBIT scoring config
CROWN_JEWEL_THRESHOLD=0.75
ROLE_BONUS_DB=0.2
ROLE_BONUS_WEB=0.1
BREADTH_BONUS_MAX=0.2
EOF
```

Verify it was written correctly:
```bash
cat ~/orbit/.env
```

Restrict the file permissions so only you can read it:
```bash
chmod 600 ~/orbit/.env
```

### Why `bolt://neo4j:7687` and not the public IP?

Because all services run on the same Docker network (`orbit-net`), they reach each other
by **container name**, not by IP address. `neo4j` is the container name we give Neo4j
in docker-compose. ORC connects to it at `neo4j:7687` — this only works inside Docker.

From outside Docker (e.g. Neo4j Browser in your web browser), you use the public IP:
`bolt://16.58.158.189:7687`.

---

## Step 4 – Add .env to .gitignore

Make sure the `.env` file is never accidentally committed to the repo:

```bash
cd ~/orbit
# If .gitignore exists, check if .env is already listed
cat .gitignore 2>/dev/null | grep -q "^\.env" && echo ".env already ignored" || echo ".env NOT in .gitignore"

# If it's not there, add it:
echo ".env" >> .gitignore
```

---

## Verification

- [ ] `~/orbit/` directory exists on the server
- [ ] `~/orbit/.env` contains all 8 variables with correct values
- [ ] File permissions on `.env` are `600` (only owner can read)
- [ ] `.env` is listed in `.gitignore`

---

## Troubleshooting

**Wrong password / authentication errors in ORC logs later:**
- The Neo4j password in the credentials file is the one set when the container was first created.
- If Neo4j was restarted with a different password at some point, the stored data and the password are mismatched.
- Fix: see "Full wipe and re-seed" in Directive 07 (Runbook).

**`.env` file has Windows line endings (if edited on Windows):**
- This can cause subtle failures. Fix with: `sed -i 's/\r//' ~/orbit/.env`
