# Wazuh Manual Testing Guide

## 1. Prerequisites

- Start the full stack with `docker compose up -d`.
- Confirm Neo4j, ORC, Presidio, Wazuh Manager, Indexer, Dashboard, Agent, and `wazuh-mcp` are running.
- Ensure `.env` contains the Neo4j and Wazuh credentials used by the app.
- Keep the project root as the current working directory for every command below.

## 2. Verifying Wazuh Components

- Run `docker compose ps` and confirm the Wazuh services are healthy.
- Check the manager and indexer logs with `docker compose logs wazuh.manager wazuh.indexer`.
- Verify the Wazuh API is reachable:

```bash
curl -sk -u wazuh-wui:wazuh-wui https://localhost:55000/ | python3 -m json.tool
```

- Verify the dashboard is reachable at `https://localhost:5601`.

## 3. Testing the Push Pipeline

- Send a FIM event into ORC:

```bash
curl -s -X POST http://localhost:8000/webhook/wazuh-event \
  -H "Content-Type: application/json" \
  -d @wazuh/fixtures/fim_event.json | python3 -m json.tool
```

- Send a vulnerability event into ORC:

```bash
curl -s -X POST http://localhost:8000/webhook/wazuh-event \
  -H "Content-Type: application/json" \
  -d @wazuh/fixtures/vuln_alert.json | python3 -m json.tool
```

- Confirm both calls return HTTP 200 and `{"status": "processed"}`.

## 4. Testing ActionCard Injection

- Ingest a Core alert:

```bash
curl -s -X POST http://localhost:8000/ingest/core-alert \
  -H "Content-Type: application/json" \
  -d @fixtures/alerts/core_alert_001.json | python3 -m json.tool
```

- Inspect the shared alert log:

```bash
cat wazuh/orbit_alerts/orbit_alerts.log
```

- Confirm the newest JSON line contains `orbit_action_id`, `priority`, `affected_host`, and `wazuh_alert_ref`.
- Check manager logs for the custom ORBIT rule firing:

```bash
docker compose logs wazuh.manager | grep ORBIT
```

## 5. Testing Active Response

- Assign and approve the injected ActionCard:

```bash
curl -s -X POST http://localhost:8000/lifecycle/ORBIT-AC-008/assign \
  -H "Content-Type: application/json" \
  -d '{"analyst_id":"analyst-test","comment":"Assigned"}'

curl -s -X POST http://localhost:8000/lifecycle/ORBIT-AC-008/approve \
  -H "Content-Type: application/json" \
  -d '{"analyst_id":"analyst-test","comment":"Approved"}'
```

- Wait 10 to 15 seconds, then check status:

```bash
curl http://localhost:8000/lifecycle/ORBIT-AC-008/status | python3 -m json.tool
```

- Inspect the agent-side active response log:

```bash
docker exec wazuh-agent cat /var/ossec/logs/orbit_ar.log
```

- Confirm the matching `action_card_id` shows `status=executed`.

## 6. Testing MCP Tools

- Confirm the MCP container is up and the server is listening:

```bash
docker compose logs wazuh-mcp
```

- Exercise the direct Python tool entrypoints:

```bash
python3 - << 'EOF'
import asyncio, sys
sys.path.insert(0, '.')
from wazuh_mcp.tools import (
    get_agents, get_vulnerabilities, get_crown_jewels,
    get_active_alerts, get_pending_actioncards, get_risk_context
)

async def test():
    print(await get_agents())
    print(await get_vulnerabilities("001"))
    print(await get_crown_jewels())
    print(await get_active_alerts(limit=5))
    print(await get_pending_actioncards())
    print(await get_risk_context("wazuh-agent-001"))

asyncio.run(test())
EOF
```

- Confirm each call returns a populated Pydantic model instance.

## 7. Testing the Completion Feedback Loop

- After an Active Response finishes, inspect Neo4j:

```cypher
MATCH (ac:ActionCard)
OPTIONAL MATCH (ac)-[:EXECUTED]->(ev:ExecutionEvent)
RETURN ac.action_id, ac.status, ev.outcome, ev.exec_id
ORDER BY ac.action_id
```

- Confirm approved Wazuh-managed cards move from `approved` to `executing` to `completed`.
- Confirm failed trigger attempts are recorded as `failed` with an `ExecutionEvent`.

## 8. Wazuh Dashboard Quick Reference

- Dashboard URL: `https://localhost:5601`
- API URL: `https://localhost:55000`
- Default API user: `wazuh-wui`
- Wazuh Manager service name: `wazuh.manager`
- Shared ORBIT alert log: `wazuh/orbit_alerts/orbit_alerts.log`
- Agent Active Response log: `/var/ossec/logs/orbit_ar.log`
- MCP endpoint: `http://localhost:8001/mcp`
