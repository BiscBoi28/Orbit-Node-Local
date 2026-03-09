# Directive: ORBIT.CyberGraph-Node — Wazuh v4 Integration

**Builds on:** `directives/neo4j_implementation.md` (complete)  
**Wazuh version:** 4.x (OSS stack — Manager + Indexer + Dashboard)  
**Integration model:** Push — Wazuh custom integration script → ORC webhook  
**Active Response:** Simulated — script logs action, ORC updates ActionCard lifecycle  
**Testing:** Fixture JSON seeds + one containerised Wazuh agent  
**Future migration:** All code must be parameterised so bank simulation agents slot in without modification

---

## Theoretical Grounding — Read Before Coding

### How Wazuh v4 custom integrations work
Wazuh has a built-in integration framework at `/var/ossec/integrations/`. When a rule fires that has `<integration>` configured in `ossec.conf`, Wazuh calls the integration script and passes it the alert JSON. This is the push mechanism. The script receives a path to a temp file containing the alert, reads it, and POSTs to the ORC webhook. This is more reliable than polling for event-driven data (FIM events, vulnerability findings, new agent registration) because it fires immediately when the event occurs.

### Why push for events but the agent container still auto-registers
The containerised agent registers itself with the Manager on startup via the enrollment protocol (port 1515). This registration creates an agent entry in the Manager — which is then visible via the Wazuh REST API. The ORC can query the Wazuh API at startup (or on demand) to pull the current agent inventory and seed Neo4j. Ongoing changes (new vulnerabilities, FIM alerts) arrive via push. This hybrid is natural: inventory is pull-on-demand, events are push.

### Why Active Response must be simulated now but structured for real scripts later
Wazuh Active Response works by the Manager sending a command to the agent over the agent connection (port 1514). The agent runs the pre-registered script from `/var/ossec/active-response/bin/`. For our purposes: the script exists on the agent container, it receives the ActionCard metadata, logs "ORBIT: [action] triggered on [host]", and exits 0. The ORC monitors for completion via the Wazuh API alerts stream (the AR result appears as a Wazuh alert with rule 601). When it sees the completion alert, it calls `record_execution_result()`. The script is designed so a real isolation command can be inserted in one place later.

### Why the fixture format must match real agent output
When the bank simulation (CloudFormation) deploys real EC2 hosts with Wazuh agents, those agents will produce the same JSON schema as our fixture files — because the fixtures are modelled on real Wazuh API responses. If fixtures use a different schema, the ingestion code will break when real agents connect. Always model fixtures on actual Wazuh v4 API response shapes.

### The MCP Server's role
The MCP Server is not another REST API — it is a server implementing the Model Context Protocol that exposes Wazuh data as typed tools a Claude/GPT agent can call by name. The Node Agent (LLM brain, Naveen's component) calls `get_agents()`, `get_vulnerabilities(agent_id)`, `get_active_alerts()`, `trigger_active_response(agent_id, command)` as structured tool calls rather than constructing raw HTTP requests. This is the correct abstraction boundary: the MCP Server handles all Wazuh API authentication and response normalisation; the LLM agent just calls tools.

---

## Phase 0 — Docker Compose Extension

**Goal:** Add Wazuh full stack (Manager + Indexer + Dashboard + Agent) to the existing `docker-compose.yml` alongside ORC, Neo4j, Presidio.

**Create:** `docker-compose.yml` (extend existing — do NOT replace)

### Services to add

```yaml
# Wazuh Indexer (OpenSearch)
wazuh.indexer:
  image: wazuh/wazuh-indexer:4.7.0
  container_name: wazuh-indexer
  hostname: wazuh.indexer
  restart: unless-stopped
  ports:
    - "9200:9200"
  environment:
    - "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m"
  volumes:
    - wazuh-indexer-data:/var/lib/wazuh-indexer
    - ./wazuh/config/wazuh_indexer.yml:/usr/share/wazuh-indexer/opensearch.yml
    - ./wazuh/config/certs/:/usr/share/wazuh-indexer/certs/
  healthcheck:
    test: ["CMD-SHELL", "curl -sk https://localhost:9200 -u admin:admin | grep -q 'cluster_name'"]
    interval: 30s
    timeout: 10s
    retries: 10
    start_period: 90s

# Wazuh Manager
wazuh.manager:
  image: wazuh/wazuh-manager:4.7.0
  container_name: wazuh-manager
  hostname: wazuh.manager
  restart: unless-stopped
  ports:
    - "1514:1514/udp"    # Agent events
    - "1515:1515"         # Agent enrollment
    - "514:514/udp"       # Syslog
    - "55000:55000"       # Wazuh API
  environment:
    - INDEXER_URL=https://wazuh.indexer:9200
    - INDEXER_USERNAME=admin
    - INDEXER_PASSWORD=admin
    - FILEBEAT_SSL_VERIFICATION_MODE=full
  volumes:
    - wazuh-manager-data:/var/ossec/data
    - wazuh-manager-logs:/var/ossec/logs
    - wazuh-manager-queue:/var/ossec/queue
    - ./wazuh/config/ossec.conf:/wazuh-config-mount/etc/ossec.conf
    - ./wazuh/integrations/:/var/ossec/integrations/
    - ./wazuh/active-response/:/var/ossec/active-response/bin/
    - ./wazuh/config/certs/:/etc/ssl/wazuh/
  depends_on:
    wazuh.indexer:
      condition: service_healthy
  healthcheck:
    test: ["CMD-SHELL", "curl -sk -u wazuh-wui:wazuh-wui https://localhost:55000/ | grep -q 'title'"]
    interval: 30s
    timeout: 10s
    retries: 10
    start_period: 120s

# Wazuh Dashboard (Kibana-based)
wazuh.dashboard:
  image: wazuh/wazuh-dashboard:4.7.0
  container_name: wazuh-dashboard
  hostname: wazuh.dashboard
  restart: unless-stopped
  ports:
    - "5601:5601"
  environment:
    - INDEXER_USERNAME=admin
    - INDEXER_PASSWORD=admin
    - WAZUH_API_URL=https://wazuh.manager
    - DASHBOARD_USERNAME=kibanaserver
    - DASHBOARD_PASSWORD=kibanaserver
  volumes:
    - ./wazuh/config/wazuh_dashboard.yml:/usr/share/wazuh-dashboard/config/opensearch_dashboards.yml
    - ./wazuh/config/certs/:/usr/share/wazuh-dashboard/certs/
  depends_on:
    wazuh.indexer:
      condition: service_healthy
    wazuh.manager:
      condition: service_healthy

# Wazuh Agent (containerised bank host simulation)
wazuh.agent:
  build:
    context: ./wazuh/agent
    dockerfile: Dockerfile.agent
  container_name: wazuh-agent
  hostname: simulated-bank-host-01
  restart: unless-stopped
  environment:
    - WAZUH_MANAGER=wazuh.manager
    - WAZUH_AGENT_NAME=simulated-bank-host-01
    - WAZUH_AGENT_GROUP=bank-hosts
  volumes:
    - ./wazuh/agent/ossec.conf:/var/ossec/etc/ossec.conf
    - ./wazuh/active-response/:/var/ossec/active-response/bin/
  depends_on:
    wazuh.manager:
      condition: service_healthy
  cap_add:
    - NET_ADMIN       # needed for simulated iptables AR
  networks:
    - orbit-network

volumes:
  wazuh-indexer-data:
  wazuh-manager-data:
  wazuh-manager-logs:
  wazuh-manager-queue:

networks:
  orbit-network:
    driver: bridge
```

**Create:** `wazuh/agent/Dockerfile.agent`

```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y curl wget gnupg2 lsb-release sudo iproute2

# Install Wazuh agent 4.7.0
RUN curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --dearmor -o /usr/share/keyrings/wazuh.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" \
    > /etc/apt/sources.list.d/wazuh.list && \
    apt-get update && apt-get install -y wazuh-agent=4.7.0-1

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
```

**Create:** `wazuh/agent/entrypoint.sh`

```bash
#!/bin/bash
# Configure and start the Wazuh agent
sed -i "s|MANAGER_IP|${WAZUH_MANAGER}|g" /var/ossec/etc/ossec.conf
/var/ossec/bin/wazuh-agentd -d
# Keep container alive and agent running
tail -f /var/ossec/logs/ossec.log
```

**Create:** `wazuh/config/ossec.conf` (Manager config — the most critical config file)

This must include:
- `<global>` block with jsonout_output enabled
- `<integration>` blocks for the ORBIT push integration (triggers on relevant rule groups)
- `<active-response>` block registering the ORBIT AR script
- `<vulnerability-detector>` enabled
- `<syscheck>` (FIM) enabled with bank-relevant directories

Key integration block:
```xml
<integration>
  <name>orbit-orc</name>
  <hook_url>http://orc:8000/webhook/wazuh-event</hook_url>
  <rule_id>550,554,657,18107,23502</rule_id>
  <group>vulnerability-detector,syscheck,authentication_failed,web,</group>
  <alert_format>json</alert_format>
</integration>
```

Key active-response block:
```xml
<active-response>
  <command>orbit-action</command>
  <location>local</location>
  <timeout>60</timeout>
</active-response>

<command>
  <name>orbit-action</name>
  <executable>orbit_action.sh</executable>
  <timeout_allowed>yes</timeout_allowed>
</command>
```

**Verify Phase 0:**
```bash
docker compose up -d
docker compose ps
# All 7 containers should be Up (healthy)
# Wazuh startup takes 3-5 minutes — wait for healthy before proceeding
```

---

## Phase 1 — Wazuh Fixture Data & Seeding

**Goal:** Seed Wazuh with fixture data that matches real Wazuh v4 API response shapes. The containerised agent auto-registers; fixtures add a second simulated host for multi-host testing.

**Create:** `wazuh/fixtures/agents.json`

Model this on the real Wazuh API `GET /agents` response shape:
```json
{
  "data": {
    "affected_items": [
      {
        "id": "001",
        "name": "simulated-bank-host-01",
        "ip": "172.20.0.10",
        "os": {"name": "Ubuntu", "version": "22.04", "platform": "ubuntu"},
        "version": "Wazuh v4.7.0",
        "status": "active",
        "group": ["bank-hosts"],
        "registerIP": "172.20.0.10",
        "dateAdd": "2024-01-15T08:00:00Z",
        "lastKeepAlive": "2024-01-15T10:00:00Z"
      },
      {
        "id": "002",
        "name": "simulated-bank-db-01",
        "ip": "172.20.0.11",
        "os": {"name": "Ubuntu", "version": "20.04", "platform": "ubuntu"},
        "version": "Wazuh v4.7.0",
        "status": "active",
        "group": ["bank-hosts", "databases"],
        "registerIP": "172.20.0.11",
        "dateAdd": "2024-01-15T08:00:00Z",
        "lastKeepAlive": "2024-01-15T10:00:00Z"
      }
    ],
    "total_affected_items": 2
  }
}
```

**Create:** `wazuh/fixtures/vulnerabilities.json`

Model on real Wazuh API `GET /vulnerability/{agent_id}` response:
```json
{
  "agent_id": "001",
  "data": {
    "affected_items": [
      {
        "cve": "CVE-2023-44487",
        "name": "nginx",
        "version": "1.18.0",
        "severity": "High",
        "cvss2_score": 7.5,
        "cvss3_score": 7.5,
        "published": "2023-10-10",
        "title": "HTTP/2 Rapid Reset Attack",
        "condition": "Package less than 1.25.3",
        "package": {"name": "nginx", "version": "1.18.0", "architecture": "amd64"}
      },
      {
        "cve": "CVE-2024-3094",
        "name": "xz-utils",
        "version": "5.6.0",
        "severity": "Critical",
        "cvss3_score": 10.0,
        "published": "2024-03-29",
        "title": "XZ Utils backdoor in liblzma",
        "package": {"name": "xz-utils", "version": "5.6.0", "architecture": "amd64"}
      }
    ],
    "total_affected_items": 2
  }
}
```

**Create:** `wazuh/fixtures/packages.json`

Model on real Wazuh API `GET /syscollector/{agent_id}/packages`:
```json
{
  "agent_id": "001",
  "data": {
    "affected_items": [
      {"name": "nginx", "version": "1.18.0", "vendor": "Ubuntu", "architecture": "amd64", "install_time": "2024-01-10"},
      {"name": "postgresql-14", "version": "14.10", "vendor": "Ubuntu", "architecture": "amd64", "install_time": "2024-01-10"},
      {"name": "openssl", "version": "3.0.2", "vendor": "Ubuntu", "architecture": "amd64", "install_time": "2024-01-10"}
    ]
  }
}
```

**Create:** `wazuh/fixtures/ports.json`

Model on real Wazuh API `GET /syscollector/{agent_id}/ports`:
```json
{
  "agent_id": "001",
  "data": {
    "affected_items": [
      {"local_port": 443, "protocol": "tcp", "process": "nginx", "state": "listening"},
      {"local_port": 80, "protocol": "tcp", "process": "nginx", "state": "listening"},
      {"local_port": 5432, "protocol": "tcp", "process": "postgres", "state": "listening"}
    ]
  }
}
```

**Create:** `wazuh/fixtures/fim_event.json` (sample FIM alert — for integration test)

Model on real Wazuh alert JSON pushed by integration:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "rule": {"id": "550", "description": "Integrity checksum changed", "level": 7, "groups": ["syscheck"]},
  "agent": {"id": "001", "name": "simulated-bank-host-01", "ip": "172.20.0.10"},
  "manager": {"name": "wazuh-manager"},
  "full_log": "File '/etc/passwd' modified. Size changed from '1823' to '1890'",
  "syscheck": {
    "path": "/etc/passwd",
    "event": "modified",
    "changed_attributes": ["size", "md5", "sha1"],
    "size_before": "1823", "size_after": "1890",
    "md5_before": "abc123", "md5_after": "def456"
  }
}
```

**Create:** `wazuh/seed_wazuh.py`

This script runs after Wazuh Manager is healthy:
1. Authenticates with Wazuh API (`POST /security/user/authenticate`)
2. Creates agent group `bank-hosts` if not exists (`POST /groups`)
3. Waits for the containerised agent to auto-register, then assigns it to group
4. Injects the fixture vulnerability data by calling the ORC endpoints that will trigger graph ingestion (not directly into Wazuh — Wazuh's vulnerability data comes from its own scanner; we pre-populate Neo4j via ORC for the non-auto-registered host)
5. Triggers a test FIM event by writing a test file that Syscheck monitors
6. Prints a summary of what was seeded

This script must be idempotent — safe to run multiple times.

---

## Phase 2 — ORC Webhook Endpoint (Push Receiver)

**Goal:** ORC receives Wazuh alert pushes and routes them to the correct ingestion function.

**Create:** `app/wazuh/webhook.py`

```python
POST /webhook/wazuh-event
```

This endpoint:
1. Receives the Wazuh alert JSON (the shape defined in `fim_event.json` above)
2. Extracts: `rule.id`, `rule.groups`, `agent.id`, `agent.name`, `agent.ip`
3. Routes to the correct handler based on rule group:
   - `syscheck` → `handle_fim_event(alert)` → updates Host node, logs change
   - `vulnerability-detector` → `handle_vulnerability_event(alert)` → calls `ingest_vulnerability()`
   - `authentication_failed` → `handle_auth_failure(alert)` → logs to graph as SecurityEvent
   - `web` → `handle_web_event(alert)` → logs to graph
4. Returns `{"status": "processed", "rule_id": ..., "agent_id": ...}`
5. On any exception: returns 200 (never 500 — Wazuh retries on non-200 which causes loops) but logs the error

Key design: **always return 200**. Wazuh's integration framework retries on failure and has no backoff — a non-200 response creates an alert storm. Log errors internally, never fail the webhook.

**Create:** `app/wazuh/handlers.py`

Handler functions:

```python
def handle_fim_event(alert: dict) -> None
```
- Extracts agent info → ensures Host exists in Neo4j (calls `ingest_host` if needed)
- Creates a `SecurityEvent` property update on the Host node
- Sets `last_fim_alert = datetime`, `last_alert_rule = rule description`
- Logs at INFO level: "FIM event on {agent_name}: {path} {event_type}"

```python  
def handle_vulnerability_event(alert: dict) -> None
```
- Extracts CVE, CVSS, package info from `alert.data.vulnerability`
- Calls `ingest_vulnerability(driver, payload)` — payload shaped from alert fields
- Links to correct Host via agent_id → host_id mapping

```python
def handle_auth_failure(alert: dict) -> None
```
- Logs to structured log only (no graph write needed for MVP)
- Increment a counter on Host node: `auth_failures_24h`

**Important — agent_id to host_id mapping:**
Wazuh uses `agent.id` (e.g., "001") as its identifier. Neo4j uses `host_id`. Create a mapping layer:

```python
# app/wazuh/agent_registry.py
def get_or_create_host_from_agent(driver, agent: dict) -> str:
    """
    Maps Wazuh agent dict to Neo4j host_id.
    host_id = f"wazuh-agent-{agent['id']}"  # deterministic, reversible
    Creates Host node if not exists.
    Returns host_id.
    """
```

The `host_id` format `wazuh-agent-{agent_id}` is deterministic — given an agent_id you always get the same host_id. This is the key that connects Wazuh data to the rest of the graph. When bank simulation agents connect, they will use the same format — their real agent IDs will generate real host_ids.

---

## Phase 3 — Wazuh Inventory Sync (Pull on Demand)

**Goal:** ORC can pull full agent inventory from Wazuh API and sync the entire current state into Neo4j. Called at startup and on `/admin/refresh`.

**Create:** `app/wazuh/wazuh_client.py`

A thin wrapper around the Wazuh REST API:

```python
class WazuhClient:
    def __init__(self, base_url, username, password):
        # base_url = https://wazuh.manager:55000
        # Authenticate and cache JWT token
        # Refresh token before expiry (Wazuh tokens expire after 900s)
    
    def get_agents(self) -> list[dict]
    # GET /agents?status=active&limit=500
    
    def get_agent_packages(self, agent_id: str) -> list[dict]
    # GET /syscollector/{agent_id}/packages?limit=1000
    
    def get_agent_ports(self, agent_id: str) -> list[dict]
    # GET /syscollector/{agent_id}/ports
    
    def get_agent_vulnerabilities(self, agent_id: str) -> list[dict]
    # GET /vulnerability/{agent_id}?limit=1000
    
    def get_recent_alerts(self, limit: int = 100) -> list[dict]
    # GET /alerts?limit={limit}&sort=-timestamp
    
    def trigger_active_response(self, agent_id: str, command: str, 
                                 custom_args: list[str]) -> dict
    # PUT /active-response?agents_list={agent_id}
    # Body: {"command": command, "custom": custom_args, "alert": {...}}
    
    def get_ar_results(self, agent_id: str, after_ts: str) -> list[dict]
    # GET /alerts?q=rule.groups=active_response&agent.id={agent_id}
    # Filters alerts after after_ts — AR completion appears as rule 601/602
```

**Token management:** Wazuh JWT tokens expire after 900 seconds. The client must track `token_expiry` and re-authenticate before any call that would fail. Wrap every API call in a `_with_auth_retry()` decorator that catches 401 and re-authenticates once.

**Create:** `app/wazuh/inventory_sync.py`

```python
def sync_full_inventory(driver, wazuh_client: WazuhClient) -> dict:
    """
    Pulls complete current state from Wazuh and syncs to Neo4j.
    Returns {"agents": n, "packages": n, "ports": n, "vulnerabilities": n}
    Idempotent — safe to call repeatedly.
    """
    # 1. Get all active agents
    # 2. For each agent: ingest_host()
    # 3. For each agent: ingest_application() for each package
    # 4. For each agent: ingest_service() for each listening port
    # 5. For each agent: ingest_vulnerability() for each CVE
    # Use batch_ingest() for packages — there can be 500+ per host
```

**Add ORC endpoints:**
```python
GET  /wazuh/agents          # list agents currently known to Wazuh
POST /admin/sync            # trigger full inventory sync
GET  /admin/sync/status     # last sync timestamp and counts
```

---

## Phase 4 — ActionCard Injection into Wazuh (UC-04)

**Goal:** When an ActionCard reaches `status=pending`, ORC injects it into Wazuh as a visible alert in the Security Events stream.

**Create:** `app/wazuh/alert_injector.py`

```python
def inject_actioncard_as_alert(wazuh_client: WazuhClient, 
                                actioncard: dict,
                                affected_host: dict) -> str:
    """
    Translates an ActionCard into a Wazuh alert and injects it.
    Returns the Wazuh alert ID (for later correlation).
    """
```

**How to inject into Wazuh v4:**
Wazuh v4 does not have a direct "create alert" endpoint. The cleanest approach is:
1. Write the alert JSON to a monitored log file on the Manager container: `/var/ossec/logs/orbit_alerts.log`
2. A custom Wazuh rule (`orbit_rules.xml`) matches entries in