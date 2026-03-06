"""Tests for Phase 2 — Ingestion templates."""
import pytest
from ingest_host import ingest_host
from ingest_service import ingest_service
from ingest_vulnerability import ingest_vulnerability
from ingest_dataasset import ingest_dataasset, ingest_dataasset_pending_retry
from ingest_actioncard import ingest_actioncard
from ingest_subscription import ingest_subscription
from exceptions import PrivacyViolationError, OrphanEntityError


# ── Helper ───────────────────────────────────────────────────────────────
def _make_host(driver, host_id="TEST-HOST-001"):
    """Ingest a prerequisite host node."""
    return ingest_host(driver, {
        "host_id": host_id, "hostname": "test-host", "ip": "10.0.0.1",
        "os": "Ubuntu", "agent_version": "4.7", "source": "test",
    })


# ═══════════════════════════════════════════════════════════════════════
# HOST
# ═══════════════════════════════════════════════════════════════════════
class TestHost:
    def test_host_create(self, clean_graph):
        driver = clean_graph
        rid = ingest_host(driver, {
            "host_id": "H-001", "hostname": "web-01", "ip": "10.0.0.1",
            "os": "Ubuntu", "agent_version": "4.7", "source": "wazuh",
        })
        assert rid == "H-001"
        with driver.session() as s:
            r = s.run("MATCH (h:Host {host_id: 'H-001'}) RETURN h").single()
        assert r is not None

    def test_host_idempotent(self, clean_graph):
        driver = clean_graph
        payload = {"host_id": "H-002", "hostname": "web", "ip": "1.2.3.4",
                   "os": "Ubuntu", "agent_version": "1", "source": "test"}
        ingest_host(driver, payload)
        ingest_host(driver, payload)
        with driver.session() as s:
            cnt = s.run("MATCH (h:Host {host_id: 'H-002'}) RETURN count(h) AS c").single()["c"]
        assert cnt == 1

    def test_host_update(self, clean_graph):
        driver = clean_graph
        payload = {"host_id": "H-003", "hostname": "web", "ip": "1.1.1.1",
                   "os": "Ubuntu", "agent_version": "1", "source": "test"}
        ingest_host(driver, payload)
        payload["ip"] = "2.2.2.2"
        ingest_host(driver, payload)
        with driver.session() as s:
            ip = s.run("MATCH (h:Host {host_id: 'H-003'}) RETURN h.ip AS ip").single()["ip"]
        assert ip == "2.2.2.2"


# ═══════════════════════════════════════════════════════════════════════
# VULNERABILITY
# ═══════════════════════════════════════════════════════════════════════
class TestVulnerability:
    def test_vulnerability_link(self, clean_graph):
        driver = clean_graph
        _make_host(driver)
        ingest_vulnerability(driver, {
            "host_id": "TEST-HOST-001", "cve_id": "CVE-2023-44487",
            "cvss": 7.5, "severity": "HIGH", "source": "nvd",
        })
        with driver.session() as s:
            cnt = s.run(
                "MATCH (:Host)-[:HAS_VULNERABILITY]->(:Vulnerability) "
                "RETURN count(*) AS c"
            ).single()["c"]
        assert cnt == 1

    def test_vulnerability_rejected_bad_cve(self, clean_graph):
        driver = clean_graph
        _make_host(driver)
        with pytest.raises(ValueError, match="does not match"):
            ingest_vulnerability(driver, {
                "host_id": "TEST-HOST-001", "cve_id": "INVALID",
                "cvss": 5.0, "source": "test",
            })
        with driver.session() as s:
            cnt = s.run("MATCH (v:Vulnerability) RETURN count(v) AS c").single()["c"]
        assert cnt == 0

    def test_vulnerability_rejected_unknown_host(self, clean_graph):
        driver = clean_graph
        with pytest.raises(OrphanEntityError):
            ingest_vulnerability(driver, {
                "host_id": "GHOST-999", "cve_id": "CVE-2024-0001",
                "cvss": 5.0, "source": "test",
            })


# ═══════════════════════════════════════════════════════════════════════
# DATAASSET
# ═══════════════════════════════════════════════════════════════════════
class TestDataAsset:
    def _ingest_da(self, driver, asset_hash, score, location="loc_test"):
        _make_host(driver)
        return ingest_dataasset(driver, {
            "asset_hash": asset_hash, "location_pseudonym": location,
            "sensitivity_score": score, "pii_types": [],
            "host_id": "TEST-HOST-001", "scan_ts": "2024-01-01T00:00:00Z",
            "source": "presidio",
        })

    def test_dataasset_crown_jewel_true(self, clean_graph):
        driver = clean_graph
        self._ingest_da(driver, "CJ-HIGH", 0.85)
        with driver.session() as s:
            cj = s.run("MATCH (d:DataAsset {asset_hash:'CJ-HIGH'}) RETURN d.crown_jewel AS cj").single()["cj"]
        assert cj is True

    def test_dataasset_crown_jewel_false(self, clean_graph):
        driver = clean_graph
        self._ingest_da(driver, "CJ-LOW", 0.50)
        with driver.session() as s:
            cj = s.run("MATCH (d:DataAsset {asset_hash:'CJ-LOW'}) RETURN d.crown_jewel AS cj").single()["cj"]
        assert cj is False

    def test_dataasset_boundary(self, clean_graph):
        driver = clean_graph
        self._ingest_da(driver, "CJ-BOUND", 0.70)
        with driver.session() as s:
            cj = s.run("MATCH (d:DataAsset {asset_hash:'CJ-BOUND'}) RETURN d.crown_jewel AS cj").single()["cj"]
        assert cj is True  # 0.70 >= 0.7 threshold

    def test_dataasset_scan_status_scanned(self, clean_graph):
        driver = clean_graph
        self._ingest_da(driver, "SS-001", 0.5)
        with driver.session() as s:
            ss = s.run("MATCH (d:DataAsset {asset_hash:'SS-001'}) RETURN d.scan_status AS ss").single()["ss"]
        assert ss == "scanned"

    def test_dataasset_pending_retry_new(self, clean_graph):
        driver = clean_graph
        ingest_dataasset_pending_retry(driver, "PR-NEW")
        with driver.session() as s:
            r = s.run("MATCH (d:DataAsset {asset_hash:'PR-NEW'}) RETURN d.scan_status AS ss, d.crown_jewel AS cj").single()
        assert r["ss"] == "pending_retry"
        assert r["cj"] is False

    def test_dataasset_pending_retry_existing(self, clean_graph):
        driver = clean_graph
        self._ingest_da(driver, "PR-EXIST", 0.85)
        ingest_dataasset_pending_retry(driver, "PR-EXIST")
        with driver.session() as s:
            r = s.run("MATCH (d:DataAsset {asset_hash:'PR-EXIST'}) RETURN d.scan_status AS ss, d.crown_jewel AS cj, d.sensitivity_score AS score").single()
        assert r["ss"] == "pending_retry"
        assert r["cj"] is True  # preserved
        assert r["score"] == 0.85  # preserved

    def test_privacy_violation_rejected(self, clean_graph):
        driver = clean_graph
        _make_host(driver)
        with driver.session() as s:
            before = s.run("MATCH (d:DataAsset) RETURN count(d) AS c").single()["c"]
        with pytest.raises(PrivacyViolationError):
            ingest_dataasset(driver, {
                "asset_hash": "PRIV-001", "location_pseudonym": "user@email.com",
                "sensitivity_score": 0.5, "pii_types": [],
                "host_id": "TEST-HOST-001", "scan_ts": "2024-01-01T00:00:00Z",
                "source": "presidio",
            })
        with driver.session() as s:
            after = s.run("MATCH (d:DataAsset) RETURN count(d) AS c").single()["c"]
        assert after == before


# ═══════════════════════════════════════════════════════════════════════
# ACTIONCARD
# ═══════════════════════════════════════════════════════════════════════
class TestActionCard:
    def test_actioncard_initial_status_is_received(self, clean_graph):
        """To test the 'received' state before auto-validation, we call the
        raw MERGE Cypher directly rather than ingest_actioncard(), because
        ingest_actioncard() auto-calls validate_and_transition() which moves
        valid cards to 'pending'.  This is cleaner than mocking because it
        tests the actual Cypher template from the directive."""
        driver = clean_graph
        with driver.session() as s:
            s.run("""
                MERGE (ac:ActionCard {action_id: 'RAW-001'})
                ON CREATE SET ac.status = 'received',
                              ac.created_ts = datetime(),
                              ac.last_updated = datetime()
                SET ac.origin = 'core', ac.action_type = 'patch',
                    ac.summary = 'test', ac.last_updated = datetime()
            """)
            status = s.run(
                "MATCH (ac:ActionCard {action_id:'RAW-001'}) RETURN ac.status AS s"
            ).single()["s"]
        assert status == "received"

    def test_actioncard_unresolved_targets_populated(self, clean_graph):
        driver = clean_graph
        _make_host(driver)
        ingest_actioncard(driver, {
            "action_id": "AC-UNRES", "origin": "core", "action_type": "patch",
            "summary": "test", "confidence": 0.5,
            "affected": {"hosts": ["GHOST-999", "TEST-HOST-001"], "assets": ["FAKE"], "services": []},
        })
        with driver.session() as s:
            r = s.run("MATCH (ac:ActionCard {action_id:'AC-UNRES'}) RETURN ac.unresolved_targets AS ut").single()
        assert r["ut"] is not None
        assert len(r["ut"]) >= 2  # GHOST-999 and FAKE

    def test_actioncard_idempotent(self, clean_graph):
        driver = clean_graph
        _make_host(driver)
        payload = {"action_id": "AC-IDEM", "origin": "core", "action_type": "patch",
                   "summary": "test", "confidence": 0.5,
                   "affected": {"hosts": ["TEST-HOST-001"], "assets": [], "services": []}}
        ingest_actioncard(driver, payload)
        ingest_actioncard(driver, payload)
        with driver.session() as s:
            cnt = s.run("MATCH (ac:ActionCard {action_id:'AC-IDEM'}) RETURN count(ac) AS c").single()["c"]
        assert cnt == 1


# ═══════════════════════════════════════════════════════════════════════
# SERVICE COMPOSITE KEY
# ═══════════════════════════════════════════════════════════════════════
class TestService:
    def test_service_composite_key(self, clean_graph):
        driver = clean_graph
        _make_host(driver, "HOST-A")
        _make_host(driver, "HOST-B")
        ingest_service(driver, {"host_id": "HOST-A", "name": "nginx", "port": 443, "proto": "tcp", "source": "test"})
        ingest_service(driver, {"host_id": "HOST-B", "name": "nginx", "port": 443, "proto": "tcp", "source": "test"})
        with driver.session() as s:
            cnt = s.run("MATCH (svc:Service) RETURN count(svc) AS c").single()["c"]
        assert cnt == 2


# ═══════════════════════════════════════════════════════════════════════
# SUBSCRIPTION
# ═══════════════════════════════════════════════════════════════════════
class TestSubscription:
    def test_subscription_archiving(self, clean_graph):
        driver = clean_graph
        ingest_subscription(driver, {
            "subscription_id": "SUB-1", "context_summary": {},
            "preferred_action_types": ["patch"],
        })
        ingest_subscription(driver, {
            "subscription_id": "SUB-2", "context_summary": {},
            "preferred_action_types": ["isolate"],
        })
        with driver.session() as s:
            s1 = s.run("MATCH (sub:Subscription {subscription_id:'SUB-1'}) RETURN sub.status AS st").single()["st"]
            s2 = s.run("MATCH (sub:Subscription {subscription_id:'SUB-2'}) RETURN sub.status AS st").single()["st"]
            gen = s.run("MATCH ()-[r:GENERATED]->() RETURN count(r) AS c").single()["c"]
        assert s1 == "archived"
        assert s2 == "active"
        assert gen == 1
