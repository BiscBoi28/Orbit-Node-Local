# Directive: ORBIT Visualization Layer Integration

**Component:** Naveen's Visualization Layer (NeoDash + Neo4j Bloom + Cypher Queries)  
**Source location:** `Neo4j/visualization/` (must be moved to project root `visualization/`)  
**Builds on:** Wazuh integration (complete)  
**Goal:** Move, fix, and verify the visualization layer works against the live ORBIT Neo4j instance

---

## What This Component Is

The visualization layer is NOT a running service. It is a set of configuration and query files:
- `dashboards/*.json` — NeoDash dashboard configs, imported into https://neodash.graphapp.io
- `bloom/*.json` — Neo4j Bloom perspective configs, imported into Bloom UI
- `queries/**/*.cypher` — Reusable Cypher query libraries for analysts
- `setup/*.py` — Helper scripts for seeding and verifying data

No new Docker container is needed. NeoDash connects directly to your existing Neo4j instance via bolt://localhost:7687.

---

## Step 0 — Move Files to Correct Location

The files currently live at `Neo4j/visualization/`. They must be moved to `visualization/` at the project root so they are a first-class part of the Wazuh_Implementation project.

```bash
mv Neo4j/visualization/ visualization/
```

Verify:
```bash
ls visualization/
# Must show: README.md bloom/ dashboards/ queries/ setup/ test_data.py
```

Do NOT delete the `Neo4j/` directory if it contains other files. Only move the `visualization/` subdirectory out.

---

## Step 1 — Fix Hardcoded Credentials

Two scripts have hardcoded credentials that do not match your `.env`:

**Files affected:**
- `visualization/test_data.py` — hardcodes `neo4j/orbit_secure_pass`
- `visualization/setup/verify-neodash.py` — hardcodes `neo4j/orbit_secure_pass`
- `visualization/setup/install-neodash.md` — documents `orbit_secure_pass` as default

**Fix for Python files:** Replace hardcoded credentials with `.env` loading:

```python
# Replace hardcoded connection block with:
import os
from dotenv import load_dotenv
load_dotenv()  # loads from .env in current directory

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# IMPORTANT: NEO4J_URI in .env is bolt://neo4j:7687 (Docker internal)
# Scripts run on the host, so override to localhost:
NEO4J_URI = "bolt://localhost:7687"
```

**Fix for install-neodash.md:** Update the documented password to say:
"Use the password from your `.env` file (`NEO4J_PASSWORD` variable)"

**Files also affected:**
- `visualization/setup/sample-data-generator.py` — imports from `../neo4j-local` path which does not exist
- `visualization/test_data.py` — also prepends `../neo4j-local` to sys.path

**Fix:** Remove all `sys.path` manipulation referencing `neo4j-local`. These scripts must be self-contained.

---

## Step 2 — Fix Broken Import Paths

`sample-data-generator.py` tries to import execution helpers from a sibling `neo4j-local` directory that does not exist in this project. The advanced scenario methods (`enterprise`, `demo`) that depend on these imports are not usable.

**Fix:** 
1. Remove the `sys.path.insert` lines referencing `../neo4j-local`
2. Comment out any import lines that fail (execution helpers, lifecycle imports)
3. The `basic` scenario does NOT depend on these imports and must remain working
4. Add a comment: `# Advanced scenarios (enterprise/demo) require neo4j-local integration — not available in this deployment`

---

## Step 3 — Fix Schema Mismatches

The visualization files were written against a reference schema. Your actual Neo4j schema differs in these specific ways. Apply all fixes to the visualization files — do NOT modify ORC code.

### Mismatch 1 — `v.published_date` vs `v.published`
Your Vulnerability nodes store `v.published` not `v.published_date`.

Fix in all `.cypher` files and dashboard JSON:
```
v.published_date  →  v.published
```

### Mismatch 2 — `h.os` vs `h.os_name`  
Your Host nodes store `h.os_name` and `h.os_version` separately.

Fix in all `.cypher` files and dashboard JSON:
```cypher
-- Replace:
h.os AS operating_system
-- With:
coalesce(h.os_name + ' ' + h.os_version, h.os_name, 'Unknown') AS operating_system
```

### Mismatch 3 — `Analyst` nodes vs `ac.analyst_id` property
Your ActionCards store `ac.analyst_id` as a string property. There are no `Analyst` nodes.

Fix analyst workload queries:
```cypher
-- Replace:
MATCH (an:Analyst)<-[:ASSIGNED_TO]-(ac:ActionCard)
WITH an, count(ac) AS assigned_cards, collect(DISTINCT ac.status) AS card_statuses
RETURN an.analyst_id AS analyst, assigned_cards, card_statuses

-- With:
MATCH (ac:ActionCard)
WHERE ac.analyst_id IS NOT NULL
WITH ac.analyst_id AS analyst_id, count(ac) AS assigned_cards, collect(DISTINCT ac.status) AS card_statuses
RETURN analyst_id AS analyst, assigned_cards, card_statuses
ORDER BY assigned_cards DESC
```

### Mismatch 4 — `ac.metadata.priority` vs `ac.priority`
Your ActionCards store `ac.priority` directly as a top-level property.

Fix in all files:
```
ac.metadata IS NOT NULL AND ac.metadata.priority IS NOT NULL  →  ac.priority IS NOT NULL
ac.metadata.priority  →  ac.priority
```

### Mismatch 5 — `Threat` nodes (currently empty)
Your graph has no `Threat` nodes yet. Queries referencing `(t:Threat)` or `[:EXPLOITED_BY]` will return empty results. This is acceptable — do NOT remove these queries. Add this comment above them:
```
-- NOTE: Threat nodes not yet seeded in this deployment.
-- These queries return empty until threat intelligence is ingested.
-- Widgets will display "No data" which is correct behaviour.
```

### Mismatch 6 — `action_type = 'patch'` vs `'patch_vulnerability'`
Your ActionCards use `action_type = 'patch_vulnerability'`.

Fix in all files:
```
ac.action_type = 'patch'
→
ac.action_type IN ['patch', 'patch_vulnerability']
```

### Mismatch 7 — `HOSTS` vs `RESIDES_ON` relationship
`sample-data-generator.py` uses `[:HOSTS]` in its basic scenario. Your schema uses `[:RESIDES_ON]`.

Fix in `sample-data-generator.py`:
```
[:HOSTS]  →  [:RESIDES_ON]
```

---

## Step 4 — Seed Visualization Test Data

After fixing the scripts, seed the Neo4j instance with visualization test data using the self-contained generator (NOT sample-data-generator.py):

```bash
cd Wazuh_Implementation/
source .venv/bin/activate
python3 visualization/setup/neodash-test-generator.py
```

This script:
- Creates hosts, vulnerabilities, data assets, threats, ActionCards
- Is fully self-contained (no external imports)
- Uses the `medium` preset by default
- Prints stats after completion

**Expected output includes:**
```
Hosts: X
Vulnerabilities: X  
DataAssets: X
ActionCards: X
```

All counts must be > 0.

**IMPORTANT:** This generator may use `MERGE` or `CREATE` which could conflict with existing Wazuh-seeded data. Run it and check — if it creates duplicate nodes, add `--cleanup` flag first, then re-run your Wazuh seed:
```bash
python3 visualization/setup/neodash-test-generator.py --cleanup
python3 wazuh/seed_wazuh.py
curl -X POST http://localhost:8000/admin/sync
```

---

## Step 5 — Verify Queries Against Live Neo4j

Run these core queries to confirm the fixed files work against your actual data:

```bash
NEO4J_PASS=$(grep NEO4J_PASSWORD .env | cut -d= -f2)

# Core counts
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host) RETURN count(h) AS hosts"

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (v:Vulnerability) RETURN count(v) AS vulns"

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (d:DataAsset) RETURN count(d) AS assets"

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard) RETURN ac.status, count(*) AS n ORDER BY n DESC"

# Fixed schema queries
docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (h:Host)-[:HAS_VULNERABILITY]->(v:Vulnerability) WITH h, count(v) AS n RETURN h.hostname, n ORDER BY n DESC LIMIT 5"

docker exec orbit-neo4j cypher-shell -u neo4j -p $NEO4J_PASS \
  "MATCH (ac:ActionCard) WHERE ac.priority IS NOT NULL RETURN ac.priority, count(*) AS n"
```

All must return data without errors. Empty results for Threat queries are acceptable.

---

## Step 6 — Create Integration Test Script

Create `visualization/setup/test_queries.py`:

Requirements:
- Reads `NEO4J_PASSWORD` from `.env` in project root
- Connects to `bolt://localhost:7687` (host-side, not Docker internal)
- Parses every `.cypher` file in `visualization/queries/dashboard/`
- Splits on semicolons to get individual queries
- Skips empty strings and comment-only blocks
- Runs each query
- Prints `PASS` for successful execution (even if 0 rows returned)
- Prints `FAIL: <error>` for any query that throws an exception
- Exits with code 0 if all pass, code 1 if any fail

---

## Step 7 — Update Project README

Add a `## Visualization` section to the main `README.md`:

```markdown
## Visualization

NeoDash dashboards and Neo4j Bloom configurations for the ORBIT security graph.

### Quick Start — NeoDash
1. Open https://neodash.graphapp.io in your browser
2. Click "New Dashboard" → "Connect to Neo4j"
3. URL: bolt://localhost:7687
4. Username: neo4j
5. Password: (value of NEO4J_PASSWORD in your .env file)
6. Click "Open" → navigate to "Load Dashboard"
7. Import: visualization/dashboards/orbit-security-dashboard.json

### Available Dashboards
| File | Description |
|---|---|
| orbit-security-dashboard.json | Main SOC view — hosts, vulns, ActionCards |
| asset-intelligence.json | PII and crown jewel analysis |
| threat-analysis.json | Attack paths (requires Threat nodes) |

### Seed Visualization Data
python3 visualization/setup/neodash-test-generator.py

### Run Query Tests
python3 visualization/setup/test_queries.py

### Neo4j Browser Direct Access
Open http://localhost:7474 — login with neo4j / (NEO4J_PASSWORD from .env)
```

---

## What Does NOT Change

- ORC API — no changes
- docker-compose.yml — no new containers  
- Wazuh integration — no changes
- Neo4j schema — no structural changes, only data seeding

The visualization layer is read-only against Neo4j. It queries, never writes (except the seed scripts which are run manually).

---

## Known Limitations

| Issue | Impact | Acceptable? |
|---|---|---|
| No `Threat` nodes | Threat Analysis dashboard shows "No data" | Yes — expected |
| Crown jewels may be 0 | Crown jewel widgets show 0 | Yes if no assets seeded |
| Bloom requires Neo4j Desktop | Bloom perspective import unavailable in Docker-only setup | Yes — focus on NeoDash |
| `sample-data-generator.py` advanced scenarios broken | Only `basic` scenario works | Yes — neodash-test-generator.py covers testing needs |
