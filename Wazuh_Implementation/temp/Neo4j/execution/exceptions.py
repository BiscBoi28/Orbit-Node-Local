"""
Custom exceptions for the ORBIT.CyberGraph-Node execution layer.
Each exception represents a distinct failure category so callers can
distinguish bad input from database errors from policy violations.
"""


class PrivacyViolationError(Exception):
    """Raised when a payload contains raw PII that must not enter Neo4j.

    Examples: email addresses in location fields, SSN-length digit
    sequences, raw filesystem paths containing user home directories.
    This is a hard stop — the ingestion must be aborted entirely.
    """
    pass


class InvalidStateTransitionError(Exception):
    """Raised when an ActionCard transition is not valid for the current status.

    For example, attempting to move an ActionCard from 'pending' directly
    to 'completed' without going through 'approved' → 'executing' first.
    The error message includes the current state and the attempted state.
    """
    pass


class OrphanEntityError(Exception):
    """Raised when an entity references a parent that doesn't exist in the graph.

    For example, ingesting a Vulnerability for a host_id that has not been
    ingested yet. Orphan entities are never created — the parent must
    exist first.
    """
    pass


class ContractValidationError(Exception):
    """Raised when an incoming payload fails D3 contract schema validation.

    This covers missing required fields, wrong types, or values outside
    the allowed ranges/enums defined by the integration contracts.
    """
    pass
