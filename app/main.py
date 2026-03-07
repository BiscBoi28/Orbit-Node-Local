"""
ORBIT ORC — FastAPI Application
=================================
The central orchestrator service.  Exposes endpoints for:
  - Data-change events (→ Presidio scan → sensitivity → Neo4j)
  - Core vulnerability alerts (→ context lookup → ActionCard)
  - Wazuh inventory ingestion
  - Graph queries (crown jewels, high-sensitivity assets)
  - Delta computation and export
  - ActionCard lifecycle transitions
  - Health check
"""

import hashlib
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.config import LOG_LEVEL
from app.graph import (
    get_driver,
    close_driver,
    ingest_host,
    ingest_vulnerability,
    ingest_dataasset,
    ingest_actioncard,
    lookup_host,
    lookup_dataassets_for_host,
    get_crown_jewels,
    get_high_sensitivity_assets,
    compute_delta,
    export_delta,
    acknowledge_delta,
    assign_to_analyst,
    approve_action,
    reject_action,
    begin_execution,
    record_execution_result,
    get_actioncard_status,
)
from app.presidio_bank import scan_bank_content
from app.priority import (
    compute_sensitivity_score,
    compute_importance_score,
    is_crown_jewel,
    compute_action_priority,
)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Pydantic models ─────────────────────────────────────────────────────────

class DataChangeEvent(BaseModel):
    event_type: str = "data_change"
    asset_id: str
    content_items: list[str] = Field(default_factory=list)


class CoreAlert(BaseModel):
    alert_id: str
    origin: str = "orbit-core"
    action_type: str = "patch_vulnerability"
    summary: str = ""
    confidence: float = 0.5
    recommended_ts: str = ""
    affected: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)


class LifecycleAction(BaseModel):
    analyst_id: str = ""
    comment: str = ""
    reason: str = ""
    exec_id: str = ""
    outcome: str = ""
    details: str = ""


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: connect Neo4j driver.  Shutdown: close it."""
    get_driver()
    logger.info("ORC started — Neo4j driver connected")
    yield
    close_driver()
    logger.info("ORC shutdown — Neo4j driver closed")


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ORBIT ORC — Orchestrator",
    description="Central decision engine for the ORBIT CyberGraph Node",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        driver = get_driver()
        with driver.session() as s:
            s.run("RETURN 1").consume()
        return {"status": "healthy", "neo4j": "connected"}
    except Exception as e:
        raise HTTPException(502, detail=f"Neo4j unreachable: {e}")


# ── Data-Change Pipeline ───────────────────────────────────────────────────

@app.post("/ingest/data-change")
def ingest_data_change(event: DataChangeEvent):
    """Full ORC pipeline: Presidio scan → compute sensitivity → update Neo4j.

    1. Scan content_items via Presidio (bank adapter)
    2. Compute sensitivity_score from chunk scores
    3. Compute importance_score using host role
    4. Derive crown_jewel
    5. Ingest DataAsset into Neo4j
    """
    driver = get_driver()
    asset_id = event.asset_id

    # Check host exists
    host = lookup_host(asset_id)
    if not host:
        raise HTTPException(404, detail=f"Host '{asset_id}' not found in Neo4j. Seed it first.")

    # 1. Scan with Presidio
    scan_result = scan_bank_content(event.content_items)

    # 2. Compute sensitivity
    sensitivity = compute_sensitivity_score(scan_result["chunk_scores"])

    # 3. Compute importance
    technical_roles = host.get("os", "") + " " + str(host.get("source", ""))
    # Try to get role from host properties (set during seed)
    # The bank CSV role isn't stored on Host node directly, but we can infer from hostname
    role_hint = ""
    if "db" in asset_id.lower():
        role_hint = "Database Server"
    elif "web" in asset_id.lower():
        role_hint = "Web Server"
    elif "ad" in asset_id.lower():
        role_hint = "Active Directory"

    pii_types = set(scan_result["detected_pii_types"])
    importance = compute_importance_score(sensitivity, role_hint, pii_types)
    crown_jewel = is_crown_jewel(importance)

    # 4. Generate asset_hash for DataAsset key
    content_hash = hashlib.sha256(
        json.dumps(event.content_items, sort_keys=True).encode()
    ).hexdigest()[:16]
    asset_hash = f"{asset_id}::{content_hash}"

    # 5. Ingest DataAsset
    location_pseudonym = f"host:{asset_id}"  # safe pseudonym, no raw PII
    scan_ts = datetime.now(timezone.utc).isoformat()

    try:
        ingest_dataasset(driver, {
            "asset_hash": asset_hash,
            "location_pseudonym": location_pseudonym,
            "sensitivity_score": sensitivity,
            "pii_types": scan_result["detected_pii_types"],
            "host_id": asset_id,
            "scan_ts": scan_ts,
            "source": "orc-pipeline",
        })
    except Exception as e:
        raise HTTPException(500, detail=f"DataAsset ingestion failed: {e}")

    result = {
        "asset_id": asset_id,
        "asset_hash": asset_hash,
        "current_sensitivity_score": sensitivity,
        "asset_importance_score": importance,
        "crown_jewel": crown_jewel,
        "detected_pii_types": scan_result["detected_pii_types"],
        "pii_counts_summary": scan_result["pii_counts_summary"],
        "risk_analysis": scan_result["risk_analysis"],
    }
    logger.info("Data-change processed for %s: sensitivity=%.4f importance=%.4f crown_jewel=%s",
                asset_id, sensitivity, importance, crown_jewel)
    return result


# ── Core Alert Handling ─────────────────────────────────────────────────────

@app.post("/ingest/core-alert")
def ingest_core_alert(alert: CoreAlert):
    """Ingest Core alert → look up asset context → generate ActionCard.

    1. Ingest ActionCard into Neo4j (triggers received→pending)
    2. Look up affected host's sensitivity/importance
    3. Compute final priority
    4. Return the enriched action card
    """
    driver = get_driver()

    # 1. Build ActionCard payload — translate Core's alert_id → Neo4j's action_id
    ac_payload = {
        "action_id":      alert.alert_id,
        "origin":         alert.origin,
        "action_type":    alert.action_type,
        "summary":        alert.summary,
        "confidence":     alert.confidence,
        "recommended_ts": alert.recommended_ts,
        "affected":       alert.affected,
        "metadata":       alert.metadata,
    }

    try:
        action_id = ingest_actioncard(driver, ac_payload)
    except Exception as e:
        raise HTTPException(500, detail=f"ActionCard ingestion failed: {e}")

    # 2. Look up affected host context
    host_ids = alert.affected.get("hosts", [])
    meta = alert.metadata

    # Enrich with priority if we have host context
    priority = "MEDIUM"
    enrichment = {}

    for host_id in host_ids:
        host = lookup_host(host_id)
        data_assets = lookup_dataassets_for_host(host_id)

        if host and data_assets:
            # Use the highest sensitivity DataAsset
            top_da = data_assets[0]
            sensitivity = top_da.get("sensitivity_score", 0.0) or 0.0
            crown = top_da.get("crown_jewel", False) or False

            # Compute importance
            role_hint = ""
            if "db" in host_id.lower():
                role_hint = "Database Server"
            elif "web" in host_id.lower():
                role_hint = "Web Server"

            pii_types_raw = top_da.get("pii_types", [])
            pii_set = set(pii_types_raw) if isinstance(pii_types_raw, list) else set()
            importance = compute_importance_score(sensitivity, role_hint, pii_set)

            base_severity = meta.get("base_severity", "MEDIUM")
            priority = compute_action_priority(base_severity, importance, crown)

            enrichment = {
                "host_id": host_id,
                "sensitivity_score": sensitivity,
                "importance_score": importance,
                "crown_jewel": crown,
                "computed_priority": priority,
            }

    result = {
        "action_id": alert.alert_id,
        "status": get_actioncard_status(driver, alert.alert_id),
        "priority": priority,
        "summary": alert.summary,
        "enrichment": enrichment,
    }
    logger.info("Core alert processed: %s → priority=%s", alert.alert_id, priority)
    return result


# ── Wazuh Inventory Ingestion ───────────────────────────────────────────────

@app.post("/ingest/wazuh-host")
def ingest_wazuh_host(payload: dict):
    """Ingest a single Wazuh host inventory payload."""
    driver = get_driver()
    try:
        host_id = ingest_host(driver, payload)
        return {"host_id": host_id, "status": "ingested"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/ingest/wazuh-vulnerability")
def ingest_wazuh_vuln(payload: dict):
    """Ingest a single Wazuh vulnerability finding."""
    driver = get_driver()
    try:
        cve_id = ingest_vulnerability(driver, payload)
        return {"cve_id": cve_id, "status": "ingested"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


# ── Query Endpoints ─────────────────────────────────────────────────────────

@app.get("/query/crown-jewels")
def query_crown_jewels():
    return {"crown_jewels": get_crown_jewels()}


@app.get("/query/high-sensitivity")
def query_high_sensitivity(threshold: float = 0.5):
    return {"assets": get_high_sensitivity_assets(threshold)}


# ── Delta ───────────────────────────────────────────────────────────────────

@app.post("/delta/compute")
def delta_compute(last_synced_ts: str = "2000-01-01T00:00:00Z"):
    """Compute and export delta since last_synced_ts."""
    driver = get_driver()
    try:
        payload = compute_delta(driver, last_synced_ts)
        delta_id = export_delta(driver, payload)
        return {"delta_id": delta_id, "changes_count": len(payload["changes"])}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@app.post("/delta/acknowledge/{delta_id}")
def delta_ack(delta_id: str):
    """Acknowledge a delta after Core confirms receipt."""
    driver = get_driver()
    try:
        acknowledge_delta(driver, delta_id)
        return {"delta_id": delta_id, "status": "acknowledged"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


# ── ActionCard Lifecycle ────────────────────────────────────────────────────

@app.get("/lifecycle/{action_id}/status")
def lifecycle_status(action_id: str):
    driver = get_driver()
    try:
        status = get_actioncard_status(driver, action_id)
        return {"action_id": action_id, "status": status}
    except Exception as e:
        raise HTTPException(404, detail=str(e))


@app.post("/lifecycle/{action_id}/assign")
def lifecycle_assign(action_id: str, body: LifecycleAction):
    driver = get_driver()
    try:
        assign_to_analyst(driver, action_id, body.analyst_id, body.comment)
        return {"action_id": action_id, "status": "assigned", "analyst_id": body.analyst_id}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/lifecycle/{action_id}/approve")
def lifecycle_approve(action_id: str, body: LifecycleAction):
    driver = get_driver()
    try:
        approve_action(driver, action_id, body.analyst_id, body.comment)
        return {"action_id": action_id, "status": "approved"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/lifecycle/{action_id}/reject")
def lifecycle_reject(action_id: str, body: LifecycleAction):
    driver = get_driver()
    try:
        reject_action(driver, action_id, body.analyst_id, body.reason)
        return {"action_id": action_id, "status": "rejected"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/lifecycle/{action_id}/execute")
def lifecycle_begin_execution(action_id: str):
    driver = get_driver()
    try:
        begin_execution(driver, action_id)
        return {"action_id": action_id, "status": "executing"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))


@app.post("/lifecycle/{action_id}/complete")
def lifecycle_complete(action_id: str, body: LifecycleAction):
    driver = get_driver()
    try:
        record_execution_result(
            driver, action_id,
            body.exec_id or f"exec-{uuid.uuid4().hex[:8]}",
            body.outcome, body.details,
        )
        return {"action_id": action_id, "status": "completed" if body.outcome == "success" else "failed"}
    except Exception as e:
        raise HTTPException(400, detail=str(e))
