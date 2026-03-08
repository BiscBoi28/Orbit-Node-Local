"""
Ingestion template — DataAsset
================================
MERGE on asset_hash.  crown_jewel is ALWAYS derived from sensitivity_score
>= CROWN_JEWEL_THRESHOLD (.env, default 0.7).  Never accepted as input.

Privacy enforcement runs BEFORE any Cypher — if triggered, zero nodes created.

Separate function ingest_dataasset_pending_retry() handles the Presidio-
offline path (sets scan_status='pending_retry' only).
"""

import logging
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from exceptions import PrivacyViolationError, OrphanEntityError

from dotenv import load_dotenv
from neo4j import Driver

load_dotenv()

logger = logging.getLogger(__name__)

# ── Privacy patterns ─────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"@")
_DIGIT_SEQ_RE = re.compile(r"\d{9,}")
_RAW_PATH_RE = re.compile(r"(/home/|C:\\\\Users\\\\|C:\\Users\\)", re.IGNORECASE)

INGEST_CYPHER = """
MERGE (d:DataAsset {asset_hash: $asset_hash})
SET d.location_pseudonym = $location_pseudonym,
    d.sensitivity_score  = $sensitivity_score,
    d.pii_types          = $pii_types,
    d.crown_jewel        = $crown_jewel,
    d.scan_status        = 'scanned',
    d.scan_ts            = datetime($scan_ts),
    d.source             = $source,
    d.last_updated       = datetime()
WITH d
MATCH (h:Host {host_id: $host_id})
MERGE (d)-[r:RESIDES_ON]->(h)
ON CREATE SET r.first_seen = datetime()
SET r.last_updated = datetime()
RETURN d.asset_hash AS asset_hash
"""

HOST_EXISTS_CHECK = """
MATCH (h:Host {host_id: $host_id}) RETURN h.host_id AS hid
"""

PENDING_RETRY_CYPHER = """
MERGE (d:DataAsset {asset_hash: $asset_hash})
ON CREATE SET d.crown_jewel       = false,
              d.sensitivity_score = 0.0,
              d.scan_status       = 'pending_retry',
              d.last_updated      = datetime()
ON MATCH  SET d.scan_status       = 'pending_retry',
              d.last_updated      = datetime()
RETURN d.asset_hash AS asset_hash
"""


def _check_privacy(field_name: str, value: str) -> None:
    """Raise PrivacyViolationError if value contains raw PII patterns."""
    if not isinstance(value, str):
        return
    if _EMAIL_RE.search(value):
        raise PrivacyViolationError(
            f"Raw PII detected in '{field_name}': contains email address (@)"
        )
    if _DIGIT_SEQ_RE.search(value):
        raise PrivacyViolationError(
            f"Raw PII detected in '{field_name}': contains 9+ digit sequence (SSN/phone)"
        )
    if _RAW_PATH_RE.search(value):
        raise PrivacyViolationError(
            f"Raw PII detected in '{field_name}': contains raw filesystem path"
        )


def ingest_dataasset(driver: Driver, payload: dict) -> str:
    """Ingest a single DataAsset node.  Returns the asset_hash.

    crown_jewel is ALWAYS computed locally — never from payload.
    Privacy check runs BEFORE any Cypher executes.
    """

    asset_hash = payload.get("asset_hash")
    if not asset_hash:
        raise ValueError("asset_hash is required")

    host_id = payload.get("host_id")
    if not host_id:
        raise ValueError("host_id is required")

    location_pseudonym = payload.get("location_pseudonym", "")

    # ── Privacy enforcement (BEFORE any Cypher) ──────────────────────────
    _check_privacy("location_pseudonym", location_pseudonym)

    # ── Strip & warn if crown_jewel was passed ───────────────────────────
    if "crown_jewel" in payload:
        logger.warning(
            "Stripping 'crown_jewel' from payload — always computed locally",
            extra={"asset_hash": asset_hash},
        )

    # ── Compute crown_jewel ──────────────────────────────────────────────
    sensitivity_score = float(payload.get("sensitivity_score", 0.0))
    threshold = float(os.getenv("CROWN_JEWEL_THRESHOLD", "0.7"))
    crown_jewel = sensitivity_score >= threshold

    with driver.session() as session:
        # Check host exists
        check = session.run(HOST_EXISTS_CHECK, {"host_id": host_id})
        if check.single() is None:
            raise OrphanEntityError(
                f"Host {host_id} not found — ingest host first"
            )

        params = {
            "asset_hash":         asset_hash,
            "location_pseudonym": location_pseudonym,
            "sensitivity_score":  sensitivity_score,
            "pii_types":          payload.get("pii_types", []),
            "crown_jewel":        crown_jewel,
            "scan_ts":            payload.get("scan_ts", ""),
            "source":             payload.get("source", "unknown"),
            "host_id":            host_id,
        }

        result = session.run(INGEST_CYPHER, params)
        record = result.single()
        logger.info(
            "Ingested dataasset",
            extra={
                "asset_hash": asset_hash,
                "crown_jewel": crown_jewel,
                "action": "merge",
            },
        )
        return record["asset_hash"]


def ingest_dataasset_pending_retry(driver: Driver, asset_hash: str) -> None:
    """Set scan_status='pending_retry' on an existing or new stub DataAsset.

    Called by the Node Agent when Presidio is unreachable.  If the node
    does not exist yet, creates a stub with crown_jewel=False and
    sensitivity_score=0.0.
    """
    if not asset_hash:
        raise ValueError("asset_hash is required")

    with driver.session() as session:
        session.run(PENDING_RETRY_CYPHER, {"asset_hash": asset_hash})
        logger.info(
            "DataAsset marked pending_retry",
            extra={"asset_hash": asset_hash, "action": "pending_retry"},
        )
