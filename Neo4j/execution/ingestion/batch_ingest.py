"""
Batch Ingestion Utility
========================
General-purpose batch runner that processes records in chunks, handles
failures gracefully, and uses binary-search to isolate bad rows in
failed batches.
"""

import logging
import os
from typing import Callable

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def batch_ingest(
    driver,
    records: list[dict],
    ingest_fn: Callable,
    batch_size: int | None = None,
    fail_fast: bool = False,
) -> dict:
    """Process a list of records through an ingestion function in batches.

    Args:
        driver:     Neo4j driver instance.
        records:    List of payload dicts.
        ingest_fn:  A function(driver, payload) -> canonical_id.
        batch_size: Records per transaction batch (default from env INGEST_BATCH_SIZE or 200).
        fail_fast:  If True, abort on first batch failure.

    Returns:
        {"processed": int, "failed": int, "errors": [{"index": int, "error": str}]}
    """
    if batch_size is None:
        batch_size = int(os.getenv("INGEST_BATCH_SIZE", "200"))

    total = len(records)
    processed = 0
    failed = 0
    errors: list[dict] = []

    # ── Chunk records ────────────────────────────────────────────────────
    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch = records[batch_start:batch_end]

        try:
            for offset, record in enumerate(batch):
                idx = batch_start + offset
                try:
                    ingest_fn(driver, record)
                    processed += 1
                except Exception as exc:
                    failed += 1
                    errors.append({"index": idx, "error": str(exc)})
                    logger.error(
                        "Record %d failed: %s", idx, exc,
                    )
                    if fail_fast:
                        logger.error("fail_fast=True — aborting batch ingestion")
                        return {
                            "processed": processed,
                            "failed": failed,
                            "errors": errors,
                        }
        except Exception as batch_exc:
            # Whole-batch failure — binary-search to isolate bad rows
            logger.warning(
                "Batch [%d:%d] failed wholesale: %s — binary searching",
                batch_start, batch_end, batch_exc,
            )
            sub_results = _binary_search_failures(
                driver, ingest_fn, batch, batch_start
            )
            processed += sub_results["processed"]
            failed += sub_results["failed"]
            errors.extend(sub_results["errors"])

            if fail_fast:
                return {
                    "processed": processed,
                    "failed": failed,
                    "errors": errors,
                }

    logger.info(
        "Batch ingestion complete: %d processed, %d failed out of %d total",
        processed, failed, total,
    )

    return {"processed": processed, "failed": failed, "errors": errors}


def _binary_search_failures(
    driver,
    ingest_fn: Callable,
    batch: list[dict],
    global_offset: int,
) -> dict:
    """Recursively split a failed batch in half to isolate bad rows."""
    if len(batch) <= 1:
        # Single record — try it
        try:
            ingest_fn(driver, batch[0])
            return {"processed": 1, "failed": 0, "errors": []}
        except Exception as exc:
            return {
                "processed": 0,
                "failed": 1,
                "errors": [{"index": global_offset, "error": str(exc)}],
            }

    mid = len(batch) // 2
    left = batch[:mid]
    right = batch[mid:]

    left_result = _binary_search_failures(driver, ingest_fn, left, global_offset)
    right_result = _binary_search_failures(
        driver, ingest_fn, right, global_offset + mid
    )

    return {
        "processed": left_result["processed"] + right_result["processed"],
        "failed": left_result["failed"] + right_result["failed"],
        "errors": left_result["errors"] + right_result["errors"],
    }
