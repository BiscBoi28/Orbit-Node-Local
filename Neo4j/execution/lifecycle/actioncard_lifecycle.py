"""
ActionCard Lifecycle Management (D4 §8)
=========================================
Implements every status transition as a named function.  Each function
asserts the ActionCard is in the correct predecessor state before
applying the transition.

State machine:
  received  → pending | failed
  pending   → approved | rejected
  approved  → executing | rejected
  executing → completed | failed
  completed → (terminal)
  rejected  → (terminal)
  failed    → (terminal)
"""

import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from exceptions import InvalidStateTransitionError

from neo4j import Driver

logger = logging.getLogger(__name__)

# ── State machine definition ────────────────────────────────────────────────
VALID_TRANSITIONS: dict[str, list[str]] = {
    "received":  ["pending", "failed"],
    "pending":   ["approved", "rejected"],
    "approved":  ["executing", "rejected"],
    "executing": ["completed", "failed"],
    # Terminal states — no transitions out
    "completed": [],
    "rejected":  [],
    "failed":    [],
}


def _assert_transition(current: str, target: str) -> None:
    """Raise InvalidStateTransitionError if the transition is not valid."""
    allowed = VALID_TRANSITIONS.get(current, [])
    if target not in allowed:
        raise InvalidStateTransitionError(
            f"Cannot transition ActionCard from '{current}' to '{target}'. "
            f"Allowed transitions from '{current}': {allowed}"
        )


def _get_current_status(session, action_id: str) -> str:
    """Return current status of an ActionCard, or raise ValueError if not found."""
    result = session.run(
        "MATCH (ac:ActionCard {action_id: $action_id}) RETURN ac.status AS status",
        {"action_id": action_id},
    )
    record = result.single()
    if record is None:
        raise ValueError(f"ActionCard '{action_id}' not found")
    return record["status"]


# ── Public API ───────────────────────────────────────────────────────────────

def get_actioncard_status(driver: Driver, action_id: str) -> str:
    """Simple read — returns the current status string."""
    with driver.session() as session:
        return _get_current_status(session, action_id)


def validate_and_transition(driver: Driver, action_id: str) -> str:
    """Transition from 'received' → 'pending' if valid, or → 'failed'.

    Called automatically by ingest_actioncard after persisting.
    Returns the new status.
    """
    with driver.session() as session:
        current = _get_current_status(session, action_id)
        if current != "received":
            return current

        # Basic validation: origin and action_type must be set
        result = session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "RETURN ac.origin AS origin, ac.action_type AS atype",
            {"action_id": action_id},
        )
        record = result.single()
        errors = []
        if not record["origin"]:
            errors.append("missing origin")
        if not record["atype"]:
            errors.append("missing action_type")

        if errors:
            reason = "; ".join(errors)
            _assert_transition(current, "failed")
            session.run(
                "MATCH (ac:ActionCard {action_id: $action_id}) "
                "SET ac.status = 'failed', ac.failure_reason = $reason, "
                "    ac.last_updated = datetime()",
                {"action_id": action_id, "reason": reason},
            )
            logger.warning("ActionCard validation failed",
                           extra={"action_id": action_id, "reason": reason})
            return "failed"

        _assert_transition(current, "pending")
        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "SET ac.status = 'pending', ac.last_updated = datetime()",
            {"action_id": action_id},
        )
        logger.info("ActionCard validated → pending",
                     extra={"action_id": action_id})
        return "pending"


def assign_to_analyst(
    driver: Driver,
    action_id: str,
    analyst_id: str,
    comment: str | None = None,
) -> None:
    """Create :ASSIGNED_TO relationship.  ActionCard must be 'pending'.

    This is the 'PendingAction' pattern from UC-06:
    ActionCard(status='pending') + [:ASSIGNED_TO] → Analyst.
    """
    with driver.session() as session:
        current = _get_current_status(session, action_id)
        if current != "pending":
            raise InvalidStateTransitionError(
                f"Cannot assign ActionCard '{action_id}' to analyst: "
                f"current status is '{current}', must be 'pending'"
            )

        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "MERGE (an:Analyst {analyst_id: $analyst_id}) "
            "  ON CREATE SET an.last_updated = datetime() "
            "MERGE (ac)-[r:ASSIGNED_TO]->(an) "
            "  ON CREATE SET r.assigned_ts = datetime(), r.comment = $comment "
            "SET ac.assigned_analyst_id = $analyst_id, "
            "    ac.last_updated = datetime(), "
            "    an.last_updated = datetime()",
            {"action_id": action_id, "analyst_id": analyst_id,
             "comment": comment or ""},
        )
        logger.info("ActionCard assigned to analyst",
                     extra={"action_id": action_id, "analyst_id": analyst_id})


def approve_action(
    driver: Driver,
    action_id: str,
    analyst_id: str,
    comment: str | None = None,
) -> None:
    """Transition: pending → approved.  Creates :APPROVED_BY relationship."""
    with driver.session() as session:
        current = _get_current_status(session, action_id)
        _assert_transition(current, "approved")

        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "MERGE (an:Analyst {analyst_id: $analyst_id}) "
            "  ON CREATE SET an.last_updated = datetime() "
            "MERGE (ac)-[r:APPROVED_BY]->(an) "
            "SET r.ts = datetime(), r.comment = $comment, "
            "    ac.status = 'approved', ac.approved_ts = datetime(), "
            "    ac.last_updated = datetime(), an.last_updated = datetime()",
            {"action_id": action_id, "analyst_id": analyst_id,
             "comment": comment or ""},
        )
        logger.info("ActionCard approved",
                     extra={"action_id": action_id, "analyst_id": analyst_id})


def reject_action(
    driver: Driver,
    action_id: str,
    analyst_id: str,
    reason: str,
) -> None:
    """Transition: pending|approved → rejected.  Records reason."""
    with driver.session() as session:
        current = _get_current_status(session, action_id)
        _assert_transition(current, "rejected")

        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "SET ac.status = 'rejected', ac.rejected_ts = datetime(), "
            "    ac.reject_reason = $reason, ac.last_updated = datetime()",
            {"action_id": action_id, "reason": reason},
        )
        logger.info("ActionCard rejected",
                     extra={"action_id": action_id, "reason": reason})


def begin_execution(driver: Driver, action_id: str) -> None:
    """Transition: approved → executing.  Records execution_started_ts."""
    with driver.session() as session:
        current = _get_current_status(session, action_id)
        _assert_transition(current, "executing")

        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "SET ac.status = 'executing', "
            "    ac.execution_started_ts = datetime(), "
            "    ac.last_updated = datetime()",
            {"action_id": action_id},
        )
        logger.info("ActionCard execution started",
                     extra={"action_id": action_id})


def record_execution_result(
    driver: Driver,
    action_id: str,
    exec_id: str,
    outcome: str,
    details: str,
) -> None:
    """Create ExecutionEvent and transition: executing → completed|failed.

    outcome='success' → status='completed'.
    Any other outcome  → status='failed'.
    """
    new_status = "completed" if outcome == "success" else "failed"

    with driver.session() as session:
        current = _get_current_status(session, action_id)
        _assert_transition(current, new_status)

        session.run(
            "MATCH (ac:ActionCard {action_id: $action_id}) "
            "CREATE (ev:ExecutionEvent { "
            "  exec_id: $exec_id, "
            "  ts: datetime(), "
            "  outcome: $outcome, "
            "  details: $details, "
            "  last_updated: datetime() "
            "}) "
            "MERGE (ac)-[:EXECUTED]->(ev) "
            "SET ac.status = $new_status, "
            "    ac.last_execution_ts = datetime(), "
            "    ac.last_updated = datetime()",
            {"action_id": action_id, "exec_id": exec_id,
             "outcome": outcome, "details": details,
             "new_status": new_status},
        )
        logger.info("ActionCard execution result recorded",
                     extra={"action_id": action_id, "outcome": outcome,
                            "new_status": new_status})
