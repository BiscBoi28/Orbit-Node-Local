"""Tests for Phase 3 — ActionCard lifecycle state machine."""
import pytest
from ingest_host import ingest_host
from ingest_actioncard import ingest_actioncard
from actioncard_lifecycle import (
    get_actioncard_status, assign_to_analyst, approve_action,
    reject_action, begin_execution, record_execution_result,
)
from exceptions import InvalidStateTransitionError


def _setup_pending_ac(driver, action_id="LC-001"):
    """Create a host + ActionCard auto-validated to 'pending'."""
    ingest_host(driver, {
        "host_id": "LC-HOST", "hostname": "lc", "ip": "10.0.0.1",
        "os": "Ubuntu", "agent_version": "1", "source": "test",
    })
    ingest_actioncard(driver, {
        "action_id": action_id, "origin": "core", "action_type": "patch",
        "summary": "test", "confidence": 0.9,
        "affected": {"hosts": ["LC-HOST"], "assets": [], "services": []},
    })
    return action_id


class TestHappyPath:
    def test_full_happy_path(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "HAPPY-001")

        assert get_actioncard_status(driver, aid) == "pending"

        assign_to_analyst(driver, aid, "A-001")
        assert get_actioncard_status(driver, aid) == "pending"

        approve_action(driver, aid, "A-001", comment="ok")
        assert get_actioncard_status(driver, aid) == "approved"

        begin_execution(driver, aid)
        assert get_actioncard_status(driver, aid) == "executing"

        record_execution_result(driver, aid, "EXEC-1", "success", "done")
        assert get_actioncard_status(driver, aid) == "completed"


class TestRejectionPath:
    def test_rejection_path(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "REJ-001")
        assign_to_analyst(driver, aid, "A-001")
        reject_action(driver, aid, "A-001", reason="too risky")
        assert get_actioncard_status(driver, aid) == "rejected"
        # Terminal — no further transitions should work
        with pytest.raises(InvalidStateTransitionError):
            approve_action(driver, aid, "A-001")


class TestRelationships:
    def test_assign_to_analyst_creates_relationship(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "REL-001")
        assign_to_analyst(driver, aid, "A-001", comment="reviewing")
        with driver.session() as s:
            r = s.run(
                "MATCH (ac:ActionCard {action_id:$aid})-[:ASSIGNED_TO]->(an:Analyst) "
                "RETURN an.analyst_id AS aid", {"aid": aid}
            ).single()
        assert r["aid"] == "A-001"

    def test_approval_creates_approved_by_relationship(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "REL-002")
        approve_action(driver, aid, "A-002", comment="approved")
        with driver.session() as s:
            r = s.run(
                "MATCH (ac:ActionCard {action_id:$aid})-[r:APPROVED_BY]->(an:Analyst) "
                "RETURN an.analyst_id AS aid, r.ts AS ts", {"aid": aid}
            ).single()
        assert r["aid"] == "A-002"
        assert r["ts"] is not None

    def test_execution_event_node_created(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "REL-003")
        approve_action(driver, aid, "A-003")
        begin_execution(driver, aid)
        record_execution_result(driver, aid, "EX-001", "success", "patched")
        with driver.session() as s:
            r = s.run(
                "MATCH (ac:ActionCard {action_id:$aid})-[:EXECUTED]->(ev:ExecutionEvent) "
                "RETURN ev.exec_id AS eid, ev.outcome AS outcome", {"aid": aid}
            ).single()
        assert r["eid"] == "EX-001"
        assert r["outcome"] == "success"


class TestInvalidTransitions:
    def test_invalid_transition_pending_to_executing(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "INV-001")
        with pytest.raises(InvalidStateTransitionError, match="pending.*executing"):
            begin_execution(driver, aid)

    def test_invalid_transition_completed_to_approved(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "INV-002")
        approve_action(driver, aid, "A-001")
        begin_execution(driver, aid)
        record_execution_result(driver, aid, "EX-001", "success", "done")
        with pytest.raises(InvalidStateTransitionError, match="completed.*approved"):
            approve_action(driver, aid, "A-001")

    def test_terminal_state_rejected_blocks_all_transitions(self, clean_graph):
        driver = clean_graph
        aid = _setup_pending_ac(driver, "INV-003")
        reject_action(driver, aid, "A-001", reason="no")
        with pytest.raises(InvalidStateTransitionError):
            begin_execution(driver, aid)
        with pytest.raises(InvalidStateTransitionError):
            approve_action(driver, aid, "A-001")
