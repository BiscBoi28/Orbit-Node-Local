# Directive 03 – Dockerfile and Unified docker-compose.yml

## Goal

Make two changes to files in your `new-app` repo on your laptop:

1. **Dockerfile** — review and patch the one that already exists (small fixes only)
2. **docker-compose.yml** — replace the existing one with a new version that includes ORC as a container

After this, the entire ORBIT stack starts with one command:
```bash
docker compose up -d
```

---

## Step 1 – Review the Existing Dockerfile

Open the `Dockerfile` in your `new-app` folder and check these 8 things.
Only fix what's missing — don't replace anything that's already correct.

| # | What to look for | What to do if missing |
|---|------------------|-----------------------|
| 1 | `FROM python:3.11-slim` (or any python version) | Leave it — any Python 3.x base is fine |
| 2 | `WORKDIR /app` | Add this near the top |
| 3 | `COPY requirements.txt .` + `RUN pip install` | Add these two lines |
| 4 | `COPY app/ ./app/` | Add this line |
| 5 | `COPY fixtures/ ./fixtures/` | **Add this** — the seed script needs the CSV files |
| 6 | `EXPOSE 8000` | Add this line |
| 7 | `HEALTHCHECK` block (see below) | **Add this** — docker-compose needs it to know ORC is ready |
| 8 | `CMD` line contains `--host 0.0.0.0` | **Fix this if it says 127.0.0.1** — otherwise ORC won't be reachable |

**The two things most likely to be missing are #5 (fixtures) and #7 (HEALTHCHECK).**

Add the HEALTHCHECK block like this, just before the CMD line:
```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1
```

The `curl` command also needs to be installed in the container for this to work.
If your Dockerfile doesn't already have a `RUN apt-get install` line, add:
```dockerfile
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
```

**Complete reference** (only use this to fill in missing pieces, not to replace your whole file):
```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY fixtures/ ./fixtures/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Step 2 – Replace docker-compose.yml

The existing `docker-compose.yml` only starts Neo4j and Presidio.
We need to replace it with one that also starts ORC.

First, back up the old one (in case you need to refer to it):
```bash
cp docker-compose.yml docker-compose.yml.bak
```

Then replace `docker-compose.yml` with this content:

```yaml
# docker-compose.yml
# Starts all ORBIT Node services: Neo4j, Presidio, and ORC

services:

  neo4j:
    image: neo4j:5.18-community
    container_name: orbit-neo4j
    restart: unless-stopped
    ports:
      - "7474:7474"   # Neo4j Browser (open in web browser to view graph)
      - "7687:7687"   # Bolt connection (used by ORC app internally)
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}
      - NEO4J_PLUGINS=["apoc"]
      - NEO4J_dbms_security_procedures_unrestricted=apoc.*
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:7474"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 60s
    networks:
      - orbit-net

  presidio:
    image: mcr.microsoft.com/presidio-analyzer:latest
    container_name: orbit-presidio
    restart: unless-stopped
    ports:
      - "5001:3000"   # Presidio API (3000 inside container, exposed as 5001)
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:3000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
    networks:
      - orbit-net

  orc:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: orbit-orc
    restart: unless-stopped
    ports:
      - "8000:8000"   # ORC API
    env_file:
      - .env
    depends_on:
      neo4j:
        condition: service_healthy
      presidio:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 90s
    networks:
      - orbit-net

volumes:
  neo4j_data:
  neo4j_logs:

networks:
  orbit-net:
    driver: bridge
```

**What the important lines mean in plain English:**
- `depends_on` with `service_healthy` — ORC waits for Neo4j and Presidio to be ready before starting. Prevents crashes on startup.
- `env_file: .env` — ORC reads its passwords and config from the `.env` file (written in Directive 02).
- `restart: unless-stopped` — if the server reboots, all containers start back up automatically.
- `volumes: neo4j_data` — the database contents survive container restarts. Nothing is lost if you restart ORC.
- `orbit-net` — all three containers are on a private internal network and can talk to each other by name (e.g. ORC reaches Neo4j at `neo4j:7687`).

---

## Step 3 – Create .dockerignore (if it doesn't exist)

This tells Docker what to ignore when building the ORC image.
Create a file called `.dockerignore` in the repo root:

```
.env
.env.*
.venv/
__pycache__/
*.pyc
.git/
.tmp/
docker-compose*.yml
```

---

## Step 4 – Test Locally Before Deploying

If Docker is installed on your laptop, test it here first before copying to the server.

```bash
# Build and start everything
docker compose up -d

# Wait 60-90 seconds for Neo4j to start, then check status
docker compose ps

# All three should show (healthy). Then test the API:
curl http://localhost:8000/health

# Shut down when done
docker compose down
```

If you don't have Docker on your laptop, skip this step and go straight to Directive 04.

---

## Step 5 – Save the Changes

```bash
git add Dockerfile .dockerignore docker-compose.yml
git commit -m "feat: add ORC to docker-compose, fix Dockerfile"
git push
```

If GitHub is down, just save the files locally — you'll copy them to the server in Directive 04.

---

## Done When

- [ ] `Dockerfile` has all 8 required elements (especially HEALTHCHECK and fixtures copy)
- [ ] `docker-compose.yml` includes neo4j, presidio, and orc services
- [ ] `.dockerignore` exists
- [ ] Files saved (committed if GitHub is available)
- [ ] Optional local test: all three containers reach `healthy` status

---

## Troubleshooting

**ORC container starts but immediately exits:**
- Check logs: `docker compose logs orc`
- Usually means a Python import error or missing `.env` value

**Neo4j never becomes healthy (stuck at "starting"):**
- Give it up to 2 minutes — Neo4j is genuinely slow to start the first time
- Check its logs: `docker compose logs neo4j`

**`curl: not found` inside the container during healthcheck:**
- The `RUN apt-get install -y curl` line is missing from the Dockerfile
- Add it and rebuild: `docker compose build orc`
