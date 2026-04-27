"""
State machine helpers for clinical workflow statuses.
Enforces valid state transitions and rejects illegal ones.
"""

from rest_framework import status
from rest_framework.response import Response


class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


# Referral status transitions
# Maps current status -> list of allowed next statuses
REFERRAL_TRANSITIONS = {
    'PENDING': ['ACCEPTED', 'REJECTED'],
    'ACCEPTED': ['COMPLETED', 'CANCELLED'],
    'REJECTED': [],  # Terminal state
    'COMPLETED': [],  # Terminal state
    'CANCELLED': [],  # Terminal state
}

# Lab order status transitions
LAB_ORDER_TRANSITIONS = {
    'ordered': ['collected', 'cancelled'],
    'collected': ['in_progress', 'cancelled'],
    'in_progress': ['resulted', 'cancelled'],
    'resulted': ['verified'],
    'verified': [],  # Terminal state
    'cancelled': [],  # Terminal state
}

# Encounter visit_status transitions
VISIT_STATUS_TRANSITIONS = {
    'registered': ['waiting_triage', 'waiting_doctor', 'discharged'],
    'waiting_triage': ['waiting_doctor', 'sent_to_lab', 'admitted', 'discharged'],
    'waiting_doctor': ['in_consultation', 'sent_to_lab', 'admitted', 'discharged'],
    'in_consultation': ['sent_to_lab', 'admitted', 'discharged'],
    'sent_to_lab': ['in_consultation', 'waiting_doctor', 'waiting_triage', 'discharged'],
    'admitted': ['discharged'],
    'discharged': [],  # Terminal state
}


def validate_transition(current_status: str, new_status: str, transitions: dict, entity_name: str) -> None:
    """
    Validate a status transition against allowed transitions.
    Raises StateMachineError if transition is invalid.
    
    Args:
        current_status: Current state value
        new_status: Desired new state value
        transitions: Dictionary mapping current -> list of allowed next states
        entity_name: Human-readable name for error messages
    
    Raises:
        StateMachineError: If the transition is not allowed
    """
    if current_status == new_status:
        return  # No change is always valid
    
    allowed = transitions.get(current_status, [])
    if new_status not in allowed:
        raise StateMachineError(
            f"Invalid {entity_name} status transition: '{current_status}' → '{new_status}'. "
            f"Allowed transitions from '{current_status}': {allowed or 'none (terminal state)'}"
        )


def validate_referral_transition(current: str, new: str) -> None:
    """Validate referral status transition."""
    validate_transition(current, new, REFERRAL_TRANSITIONS, "referral")


def validate_lab_order_transition(current: str, new: str) -> None:
    """Validate lab order status transition."""
    validate_transition(current, new, LAB_ORDER_TRANSITIONS, "lab order")


def validate_visit_status_transition(current: str, new: str) -> None:
    """Validate encounter visit_status transition."""
    validate_transition(current, new, VISIT_STATUS_TRANSITIONS, "visit status")
