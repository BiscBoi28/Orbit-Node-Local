"""
Schema application as a callable function (used by conftest.py).
Wraps the logic from 01_apply_schema.py so tests can re-apply schema
without spawning a subprocess.
"""

import os
from dotenv import load_dotenv
load_dotenv()


UNIQUENESS_CONSTRAINTS = [
    ("Host",            "host_id",          "host_host_id_unique"),
    ("Vulnerability",   "cve_id",           "vulnerability_cve_id_unique"),
    ("DataAsset",       "asset_hash",       "dataasset_asset_hash_unique"),
    ("ActionCard",      "action_id",        "actioncard_action_id_unique"),
    ("Analyst",         "analyst_id",       "analyst_analyst_id_unique"),
    ("Threat",          "threat_id",        "threat_threat_id_unique"),
    ("Subscription",    "subscription_id",  "subscription_subscription_id_unique"),
    ("DeltaEvent",      "delta_id",         "deltaevent_delta_id_unique"),
    ("SchemaVersion",   "name",             "schemaversion_name_unique"),
    ("ExecutionEvent",  "exec_id",          "executionevent_exec_id_unique"),
]

INDEXES = [
    ("Host",         "hostname",          "idx_host_hostname"),
    ("Host",         "ip",                "idx_host_ip"),
    ("Service",      "name",              "idx_service_name"),
    ("DataAsset",    "sensitivity_score", "idx_dataasset_sensitivity_score"),
    ("DataAsset",    "crown_jewel",       "idx_dataasset_crown_jewel"),
    ("ActionCard",   "status",            "idx_actioncard_status"),
    ("Threat",       "severity",          "idx_threat_severity"),
    ("Subscription", "status",            "idx_subscription_status"),
    ("DeltaEvent",   "sent_status",       "idx_deltaevent_sent_status"),
]

SCHEMA_VERSION_CYPHER = """
MERGE (s:SchemaVersion {name: 'orbit-node'})
SET s.version = '1.1.0',
    s.updated = datetime(),
    s.notes   = 'Initial implementation: Subscription, DeltaEvent, crown_jewel, scan_status, 6-state ActionCard lifecycle, standardised last_updated'
"""


def apply_schema(driver) -> None:
    """Apply all constraints, indexes, and SchemaVersion.  Idempotent."""
    with driver.session() as session:
        for label, prop, name in UNIQUENESS_CONSTRAINTS:
            session.run(
                f"CREATE CONSTRAINT {name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            ).consume()

        for label, prop, name in INDEXES:
            session.run(
                f"CREATE INDEX {name} IF NOT EXISTS "
                f"FOR (n:{label}) ON (n.{prop})"
            ).consume()

        session.run(SCHEMA_VERSION_CYPHER).consume()
