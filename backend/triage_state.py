"""
SAULGPT — TRIAGE STATE
=======================
Per-session state for the TriageAgent.

Stores:
  - role: detected user role (tenant, landlord, consumer, etc.)
  - goal: clarified user goal after triage
  - swot_analysis: SWOT bullets for display
  - options_shown: the strategic paths presented
  - chosen_path: which option the user selected
  - is_triaged: whether triage is complete for this session
  - session_context: enriched query combining original + triage data
  - intake_fields: collected missing variables (amount, date, location)
  - intake_complete: whether all required fields are gathered
  - intake_question_asked: the question currently awaiting an answer

TRIAGE_STATES: dict[str, dict]
  Keyed by session_id. Same pattern as INTERVIEW_STATES.
"""

INTASK_REQUIRED_FIELDS = ["amount", "incident_date", "location"]

TRIAGE_STATES: dict[str, dict] = {}

MAX_INTAKE_QUESTIONS = 3


def get_triage_state(session_id: str) -> dict:
    """Get or create triage state for a session."""
    if session_id not in TRIAGE_STATES:
        TRIAGE_STATES[session_id] = {
            "role": None,
            "goal": None,
            "swot_analysis": None,
            "options_shown": [],
            "chosen_path": None,
            "is_triaged": False,
            "session_context": None,
            "intake_fields": {},
            "intake_complete": True,
            "intake_question_asked": None,
            "doc_family": None,
            "doc_type": None,
            "intake_question_count": 0,
            "voluntary_intake_open": False,
            "current_mode": "idle",
            "discovery_profile": {},
            "discovery_turn_count": 0,
        }
    return TRIAGE_STATES[session_id]


def reset_triage_state(session_id: str):
    """Reset triage state for a session."""
    if session_id in TRIAGE_STATES:
        del TRIAGE_STATES[session_id]


def enrich_query_with_triage(original_query: str, state: dict) -> str:
    """
    Build enriched query by appending triage context.
    Passed to downstream agents so they know role + goal.
    """
    if not state.get("is_triaged"):
        return original_query

    parts = [original_query]
    if state.get("role"):
        parts.append(f"\n[User Role: {state['role']}]")
    if state.get("goal"):
        parts.append(f"[User Goal: {state['goal']}]")
    if state.get("chosen_path"):
        parts.append(f"[Chosen Strategy: {state['chosen_path']}]")

    intake = state.get("intake_fields", {})
    if intake.get("amount"):
        parts.append(f"[Claim Amount: {intake['amount']}]")
    if intake.get("incident_date"):
        parts.append(f"[Incident Date: {intake['incident_date']}]")
    if intake.get("location"):
        parts.append(f"[Location: {intake['location']}]")

    return "\n".join(parts)
