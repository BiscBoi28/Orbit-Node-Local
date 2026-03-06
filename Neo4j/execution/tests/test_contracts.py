"""Tests for D3 contract compliance (Phase 6)."""
import pytest
from ingest_host import ingest_host
from ingest_dataasset import ingest_dataasset
from ingest_actioncard import ingest_actioncard
from ingest_subscription import ingest_subscription
from compute_delta import compute_delta
import time


def _make_host(driver, host_id="CTR-HOST"):
    ingest_host(driver, {
        "host_id": host_id, "hostname": "ctr", "ip": "10.0.0.1",
        "os": "Ubuntu", "agent_version": "1", "source": "test",
    })


class TestActionCardContract:
    def test_actioncard_contract_field_mapping(self, clean_graph):
        """Ingest a full D3 Contract A payload and verify every field
        lands in the correct graph property."""
        driver = clean_graph
        _make_host(driver)
        ingest_dataasset(driver, {
            "asset_hash": "CTR-ASSET", "location_pseudonym": "loc_ctr",
            "sensitivity_score": 0.6, "pii_types": [],
            "host_id": "CTR-HOST", "scan_ts": "2024-01-01T00:00:00Z",
            "source": "presidio",
        })
        payload = {
            "action_id": "CTR-AC-001",
            "origin": "core",
            "action_type": "patch",
            "summary": "Patch critical vuln",
            "confidence": 0.95,
            "recommended_ts": "2024-02-01T12:00:00Z",
            "affected": {
                "hosts": ["CTR-HOST"],
                "assets": ["CTR-ASSET"],
                "services": [],
            },
            "metadata": {"priority": "high"},
        }
        ingest_actioncard(driver, payload)

        with driver.session() as s:
            r = s.run(
                "MATCH (ac:ActionCard {action_id: 'CTR-AC-001'}) "
                "RETURN ac.origin AS origin, ac.action_type AS atype, "
                "ac.summary AS summary, ac.confidence AS conf"
            ).single()
        assert r["origin"] == "core"
        assert r["atype"] == "patch"
        assert r["summary"] == "Patch critical vuln"
        assert r["conf"] == 0.95

        # Verify AFFECTS relationships
        with driver.session() as s:
            targets = s.run(
                "MATCH (ac:ActionCard {action_id:'CTR-AC-001'})-[:AFFECTS]->(t) "
                "RETURN labels(t) AS labels"
            ).data()
        label_set = {tuple(t["labels"]) for t in targets}
        assert any("Host" in l for l in label_set)
        assert any("DataAsset" in l for l in label_set)


class TestDeltaContract:
    def test_delta_contract_schema(self, clean_graph):
        """Generate delta, verify output dict has required top-level keys."""
        driver = clean_graph
        _make_host(driver)
        with driver.session() as s:
            t1 = s.run("RETURN toString(datetime()) AS ts").single()["ts"]
        time.sleep(0.2)
        _make_host(driver, "CTR-HOST-2")

        delta = compute_delta(driver, t1)

        required_keys = {"contract_version", "delta_id", "generated_ts", "changes"}
        assert required_keys.issubset(delta.keys()), (
            f"Missing keys: {required_keys - delta.keys()}"
        )
        assert delta["contract_version"] == "1.1"
        assert isinstance(delta["changes"], list)
        assert delta["delta_id"].startswith("delta-")


class TestSubscriptionContract:
    def test_subscription_contract_schema(self, clean_graph):
        """Generate subscription, verify output maps correctly."""
        driver = clean_graph
        payload = {
            "subscription_id": "SUB-CTR-001",
            "context_summary": {
                "crown_jewel_count": 2,
                "active_vulnerability_count": 5,
                "top_pii_types": ["EMAIL_ADDRESS"],
                "host_count": 10,
            },
            "preferred_action_types": ["patch", "isolate"],
        }
        sid = ingest_subscription(driver, payload)
        assert sid == "SUB-CTR-001"

        with driver.session() as s:
            r = s.run(
                "MATCH (sub:Subscription {subscription_id: 'SUB-CTR-001'}) "
                "RETURN sub.subscription_id AS sid, sub.status AS status, "
                "sub.generated_ts AS gts, sub.context_summary AS ctx, "
                "sub.preferred_action_types AS pat"
            ).single()
        assert r["sid"] == "SUB-CTR-001"
        assert r["status"] == "active"
        assert r["gts"] is not None
        assert r["ctx"] is not None
        assert "patch" in r["pat"]
        assert "isolate" in r["pat"]
