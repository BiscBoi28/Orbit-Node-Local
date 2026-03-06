"""Tests for Phase 1 — Schema constraints, indexes, and SchemaVersion."""
import pytest
from neo4j.exceptions import ConstraintError


EXPECTED_CONSTRAINT_NAMES = [
    "host_host_id_unique",
    "vulnerability_cve_id_unique",
    "dataasset_asset_hash_unique",
    "actioncard_action_id_unique",
    "analyst_analyst_id_unique",
    "threat_threat_id_unique",
    "subscription_subscription_id_unique",
    "deltaevent_delta_id_unique",
    "schemaversion_name_unique",
    "executionevent_exec_id_unique",
]

EXPECTED_INDEX_NAMES = [
    "idx_host_hostname",
    "idx_host_ip",
    "idx_service_name",
    "idx_dataasset_sensitivity_score",
    "idx_dataasset_crown_jewel",
    "idx_actioncard_status",
    "idx_threat_severity",
    "idx_subscription_status",
    "idx_deltaevent_sent_status",
]


def test_all_constraints_exist(neo4j_driver):
    with neo4j_driver.session() as s:
        result = s.run("SHOW CONSTRAINTS YIELD name RETURN name")
        existing = {r["name"] for r in result}
    for name in EXPECTED_CONSTRAINT_NAMES:
        assert name in existing, f"Constraint '{name}' missing"


def test_all_indexes_exist(neo4j_driver):
    with neo4j_driver.session() as s:
        result = s.run("SHOW INDEXES YIELD name RETURN name")
        existing = {r["name"] for r in result}
    for name in EXPECTED_INDEX_NAMES:
        assert name in existing, f"Index '{name}' missing"


def test_schema_version_is_1_1_0(neo4j_driver):
    with neo4j_driver.session() as s:
        rec = s.run(
            "MATCH (sv:SchemaVersion {name: 'orbit-node'}) RETURN sv.version AS v"
        ).single()
    assert rec is not None, "SchemaVersion node not found"
    assert rec["v"] == "1.1.0", f"Expected 1.1.0, got {rec['v']}"


def test_uniqueness_enforced_host(clean_graph):
    driver = clean_graph
    with driver.session() as s:
        s.run("CREATE (h:Host {host_id: 'DUP-001', hostname: 'a', last_updated: datetime()})")
        with pytest.raises(ConstraintError):
            s.run("CREATE (h:Host {host_id: 'DUP-001', hostname: 'b', last_updated: datetime()})")


def test_uniqueness_enforced_dataasset(clean_graph):
    driver = clean_graph
    with driver.session() as s:
        s.run("CREATE (d:DataAsset {asset_hash: 'DUP-HASH', last_updated: datetime()})")
        with pytest.raises(ConstraintError):
            s.run("CREATE (d:DataAsset {asset_hash: 'DUP-HASH', last_updated: datetime()})")
