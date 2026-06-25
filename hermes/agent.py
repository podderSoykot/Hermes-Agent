"""Harmis agent core logic."""

from dataclasses import dataclass
from datetime import datetime, timezone

MAX_ACTION_LENGTH = 200


@dataclass
class HarmisState:
    """Tracks Harmis's latest activity."""

    last_action: str | None = None
    last_response: str | None = None
    updated_at: datetime | None = None
    action_count: int = 0


_state = HarmisState()


def harmis_agent(action: str) -> str:
    """Return Harmis's response for the given action."""
    cleaned = action.strip()
    if not cleaned:
        raise ValueError("Action cannot be empty.")
    if len(cleaned) > MAX_ACTION_LENGTH:
        raise ValueError(f"Action must be at most {MAX_ACTION_LENGTH} characters.")

    response = f"Harmis is aggressive and {cleaned}"
    _state.last_action = cleaned
    _state.last_response = response
    _state.updated_at = datetime.now(timezone.utc)
    _state.action_count += 1
    return response


def get_harmis_state() -> HarmisState:
    """Return a snapshot of Harmis's current state."""
    return _state
