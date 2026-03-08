# Directive 04 – Prepare a Clean Deploy Folder and Copy to orbit-dev

## Goal

1. Create a clean folder on your laptop containing only what's needed to run on the server
2. Copy it to orbit-dev via rsync
3. Start all containers

---

## Prerequisites

- [ ] Directive 01 complete — SSH works, server is running
- [ ] Directive 02 complete — `.env` written at `~/orbit/.env` on the server
- [ ] Directive 03 complete — `Dockerfile` patched, new `docker-compose.yml` ready

---

## What the repo currently contains

```
new-app/                          ← your project root
├── app/                          ← ORC application code  ✅ needed
│   ├── main.py
│   ├── seed.py
│   ├── graph.py
│   ├── config.py
│   ├── presidio_bank.py
│   ├── presidio_client.py
│   ├── priority.py
│   └── stubs/
├── fixtures/                     ← seed data            ✅ needed
│   ├── bank/ORBIT_simulated_bank.csv
│   └── wazuh/hosts.json + vulnerabilities.json
├── docker-compose.yml            ← updated in Dir 03    ✅ needed
├── requirements.txt                                      ✅ needed
├── Dockerfile                    ← patched in Dir 03    ✅ needed
├── .env.example                  ← reference only       ⛔ not needed on server
└── Neo4j/                        ← old standalone scripts ⛔ not needed on server
    └── execution/...
```

The `Neo4j/` folder contains scripts that were used during early development to
manage the graph directly. The ORC app handles all of that now through `app/seed.py`.
Do not copy it to the server.

---

## Step 1 – Create a Clean Deploy Folder on Your Laptop

In WSL, run these commands. They create a new folder called `orbit-deploy` and
copy only the necessary files into it — nothing else.

```bash
# From inside the new-app directory (where Claude Code is already running):
mkdir -p ~/orbit-deploy

cp -r ./app                  ~/orbit-deploy/
cp -r ./fixtures             ~/orbit-deploy/
cp    ./requirements.txt     ~/orbit-deploy/
cp    ./Dockerfile           ~/orbit-deploy/
cp    ./docker-compose.yml   ~/orbit-deploy/
```

### Verify the clean folder looks right

```bash
find ~/orbit-deploy -not -path '*/__pycache__/*' -not -name '*.pyc' | sort
```

Expected output:
```
/home/yourname/orbit-deploy
/home/yourname/orbit-deploy/Dockerfile
/home/yourname/orbit-deploy/app
/home/yourname/orbit-deploy/app/__init__.py
/home/yourname/orbit-deploy/app/config.py
/home/yourname/orbit-deploy/app/graph.py
/home/yourname/orbit-deploy/app/main.py
/home/yourname/orbit-deploy/app/presidio_bank.py
/home/yourname/orbit-deploy/app/presidio_client.py
/home/yourname/orbit-deploy/app/priority.py
/home/yourname/orbit-deploy/app/seed.py
/home/yourname/orbit-deploy/app/stubs
/home/yourname/orbit-deploy/app/stubs/__init__.py
/home/yourname/orbit-deploy/app/stubs/core_source.py
/home/yourname/orbit-deploy/app/stubs/wazuh_source.py
/home/yourname/orbit-deploy/docker-compose.yml
/home/yourname/orbit-deploy/fixtures
/home/yourname/orbit-deploy/fixtures/bank
/home/yourname/orbit-deploy/fixtures/bank/ORBIT_simulated_bank.csv
/home/yourname/orbit-deploy/fixtures/wazuh
/home/yourname/orbit-deploy/fixtures/wazuh/hosts.json
/home/yourname/orbit-deploy/fixtures/wazuh/vulnerabilities.json
/home/yourname/orbit-deploy/requirements.txt
```

No `Neo4j/`, no `.env`, no `.env.example`. Clean.

---

## Step 2 – Copy to orbit-dev via rsync

Run this from WSL on your laptop. It copies everything from `orbit-deploy/`
to `~/orbit/` on the server.

```bash
rsync -avz \
  --exclude '__pycache__' \
  --exclude '*.pyc' \
  -e "ssh -i ~/.ssh/iiith-orbit-key.pem" \
  ~/orbit-deploy/ \
  ubuntu@16.58.158.189:~/orbit/
```

You should see a list of files being transferred. It should finish in under a minute.

### Verify the files arrived on the server

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189 \
  "ls ~/orbit/ && echo --- && ls ~/orbit/app/"
```

Expected: `app  fixtures  docker-compose.yml  Dockerfile  requirements.txt` in the
first section, and the Python files in the second.

---

## Step 3 – Confirm .env is Still in Place on the Server

The `.env` was written in Directive 02. The rsync above deliberately excludes it
(so it never accidentally gets overwritten). Confirm it's still there:

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189 \
  "ls -la ~/orbit/.env"
```

Expected: `-rw------- ... ~/orbit/.env`

If it's missing, go back to Directive 02 and re-write it.

---

## Step 4 – Confirm docker-compose.yml Includes ORC

```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189 \
  "grep 'container_name' ~/orbit/docker-compose.yml"
```

Expected output — all three container names:
```
container_name: orbit-neo4j
container_name: orbit-presidio
container_name: orbit-orc
```

If `orbit-orc` is missing, the updated docker-compose.yml from Directive 03
wasn't copied correctly. Re-run Step 2.

---

## Step 5 – Build and Start All Containers

SSH into the server:
```bash
ssh -i ~/.ssh/iiith-orbit-key.pem ubuntu@16.58.158.189
cd ~/orbit
```

Pull the Neo4j and Presidio images from Docker Hub (2–3 minutes, first time only):
```bash
docker compose pull neo4j presidio
```

Build the ORC image from your Dockerfile (1–2 minutes):
```bash
docker compose build orc
```

Start everything in the background:
```bash
docker compose up -d
```

---

## Step 6 – Wait and Confirm All Three Are Healthy

Neo4j takes 60–90 seconds to fully initialise on first boot. Check status:

```bash
watch -n 10 'docker compose ps --format table'
# Press Ctrl+C when all three show (healthy)
```

Or check manually every 30 seconds:
```bash
docker compose ps --format table
```

Target state — all three must show `running (healthy)` before moving on:
```
NAME              STATUS
orbit-neo4j       running (healthy)
orbit-presidio    running (healthy)
orbit-orc         running (healthy)
```

If ORC shows `(health: starting)` — it's waiting for Neo4j. Give it another 60 seconds.
If ORC shows `(unhealthy)` — check logs: `docker compose logs --tail=50 orc`

---

## Verification

```bash
# ORC API responds
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health
# Expected: 200

# Presidio responds
curl -s http://localhost:5001/health
# Expected: {"status":"ok"} or similar

# Neo4j browser — open this in your laptop's web browser
# http://16.58.158.189:7474
# Login: neo4j / T1pOzBraJrNcFE5nJiA_vQkbCkeeV1xNMN9TJwKpZFA
```

---

## Done When

- [ ] `~/orbit-deploy/` exists on your laptop with exactly the files listed in Step 1
- [ ] rsync completes without errors
- [ ] `~/orbit/` on the server contains `app/`, `fixtures/`, `docker-compose.yml`, `Dockerfile`, `requirements.txt`
- [ ] `~/orbit/.env` is present on the server
- [ ] `docker-compose.yml` shows all three container names
- [ ] `docker compose build orc` completes without errors
- [ ] All three containers show `running (healthy)`
- [ ] `curl http://localhost:8000/health` returns `200`

---

## Troubleshooting

**rsync fails with `Permission denied`:**
- The SSH key isn't set up correctly. Go back to Directive 01 Part B.
- Check: `ls -la ~/.ssh/iiith-orbit-key.pem` — should show `-r--------`

**`docker compose build orc` fails:**
```bash
docker compose logs orc
```
- Most common cause: a Python package in `requirements.txt` can't be installed.
- Fix the package name/version and re-run `docker compose build orc`.

**ORC container keeps restarting:**
```bash
docker compose logs --tail=50 orc
```
- Almost always a wrong or missing `.env` value, or Neo4j not ready yet.
- If error says `authentication failed`: password in `.env` doesn't match Neo4j.
  Fix: `docker compose down -v && docker compose up -d` (wipes and reinitialises
  Neo4j with the current `.env` password — fine since database is empty).

**Neo4j stuck at `(health: starting)` for more than 3 minutes:**
```bash
docker compose logs --tail=50 neo4j
```
- Usually a memory issue. Check: `free -h` — Neo4j needs at least 1GB free.

**Port already in use:**
```bash
sudo lsof -i :8000   # or :7474, :7687, :5001
```
- Something else grabbed the port. Kill it or change the port in docker-compose.yml.
