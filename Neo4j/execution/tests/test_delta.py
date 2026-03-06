"""Tests for Phase 4 — Delta computation, export, acknowledgement, soft-delete."""
import json
import os
import time
import pytest
from ingest_host import ingest_host
from ingest_dataasset import ingest_dataasset
from compute_delta import compute_delta, export_delta, acknowledge_delta, soft_delete


def _setup_data(driver):
    """Create a Host + DataAsset for delta tests.  Returns (T1, T2)."""
    with driver.session() as s:
        t1 = s.run("RETURN toString(datetime()) AS ts").single()["ts"]
    time.sleep(0.3)

    ingest_host(driver, {
        "host_id": "DT-HOST", "hostname": "dt", "ip": "10.0.0.1",
        "os": "Ubuntu", "agent_version": "1", "source": "test",
    })
    ingest_dataasset(driver, {
        "asset_hash": "DT-ASSET", "location_pseudonym": "loc_dt",
        "sensitivity_score": 0.8, "pii_types": [],
        "host_id": "DT-HOST", "scan_ts": "2024-01-01T00:00:00Z",
        "source": "presidio",
    })

    time.sleep(0.3)
    with driver.session() as s:
        t2 = s.run("RETURN toString(datetime()) AS ts").single()["ts"]
    return t1, t2


class TestDeltaComputation:
    def test_delta_includes_updated_nodes(self, clean_graph):
        driver = clean_graph
        t1, _ = _setup_data(driver)
        delta = compute_delta(driver, t1)
        ids = [c["entity_id"] for c in delta["changes"]]
        assert "DT-HOST" in ids
        assert "DT-ASSET" in ids

    def test_delta_excludes_unchanged_nodes(self, clean_graph):
        driver = clean_graph
        _, t2 = _setup_data(driver)
        delta = compute_delta(driver, t2)
        assert len(delta["changes"]) == 0


class TestDeltaExport:
    def test_delta_event_created_on_export(self, clean_graph):
        driver = clean_graph
        t1, _ = _setup_data(driver)
        delta = compute_delta(driver, t1)
        did = export_delta(driver, delta)
        with driver.session() as s:
            r = s.run(
                "MATCH (de:DeltaEvent {delta_id: $did}) RETURN de.sent_status AS ss",
                {"did": did},
            ).single()
        assert r["ss"] == "pending"

    def test_included_in_relationships_created(self, clean_graph):
        driver = clean_graph
        t1, _ = _setup_data(driver)
        delta = compute_delta(driver, t1)
        did = export_delta(driver, delta)
        with driver.session() as s:
            cnt = s.run(
                "MATCH ()-[:INCLUDED_IN]->(de:DeltaEvent {delta_id: $did}) "
                "RETURN count(*) AS c", {"did": did}
            ).single()["c"]
        assert cnt >= 2

    def test_delta_ack_marks_sent(self, clean_graph):
        driver = clean_graph
        t1, _ = _setup_data(driver)
        delta = compute_delta(driver, t1)
        did = export_delta(driver, delta)
        acknowledge_delta(driver, did)
        with driver.session() as s:
            ss = s.run(
                "MATCH (de:DeltaEvent {delta_id: $did}) RETURN de.sent_status AS ss",
                {"did": did},
            ).single()["ss"]
        assert ss == "sent"


class TestSoftDelete:
    def test_soft_delete_appears_as_delete_operation(self, clean_graph):
        driver = clean_graph
        _, t2 = _setup_data(driver)
        soft_delete(driver, "Host", "host_id", "DT-HOST")

        # Node must still exist
        with driver.session() as s:
            r = s.run("MATCH (h:Host {host_id:'DT-HOST'}) RETURN h.deleted AS d").single()
        assert r["d"] is True

        # Must appear in delta with operation='delete'
        delta = compute_delta(driver, t2)
        host_changes = [c for c in delta["changes"] if c["entity_id"] == "DT-HOST"]
        assert len(host_changes) == 1
        assert host_changes[0]["operation"] == "delete"


class TestDeltaPrivacy:
    def test_delta_json_no_raw_pii(self, clean_graph):
        driver = clean_graph
        t1, _ = _setup_data(driver)
        delta = compute_delta(driver, t1)
        did = export_delta(driver, delta)

        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        json_path = os.path.join(project_root, ".tmp", "deltas", f"delta_{did}.json")
        assert os.path.exists(json_path), f"Delta JSON not found: {json_path}"

        with open(json_path) as f:
            data = json.load(f)

        for change in data.get("changes", []):
            for key, val in change.get("properties", {}).items():
                if isinstance(val, str):
                    assert "@" not in val, (
                        f"Raw PII (@) found in {change['entity_id']}.{key}: {val}"
                    )
