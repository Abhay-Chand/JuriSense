"""
SAULGPT — FASTAPI SERVER (v2)
================================
All endpoints:

POST /api/chat              — Main 6-layer pipeline + interview intercept
POST /api/upload            — Contract evaluation (PDF/DOCX/TXT)
GET  /api/draft/state/{id}  — Check interview progress
DEL  /api/draft/state/{id}  — Cancel interview
GET  /api/history/{id}      — Conversation history
DEL  /api/history/{id}      — Clear history + interview state
GET  /                      — Health check

Run:
    python api_server.py
"""

import sys
# Windows cp1252 terminal can't print emoji/Unicode arrows → crashes with 500 error
# Force UTF-8 with errors='replace' so unprintable chars become '?' instead of crashing
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Load .env from project root before any imports that need GROQ_API_KEY
from dotenv import load_dotenv
import os, re
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

from fastapi import FastAPI, HTTPException, UploadFile, File, Header, Depends, Request
from typing import Annotated
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import traceback
import uvicorn

from pipeline_orchestrator import run_saulgpt_pipeline, get_session_history, get_history_with_summary, save_turn_to_memory
import time
from layer5_external import start_auto_updater
from layer6_evaluator import evaluate_contract, format_evaluation_response
from interview_state import (
    get_interview_state,
    DOCUMENT_SCHEMAS,
    generate_field_questions,
    generate_document_spec,
    detect_document_type,
    map_doc_type_to_family,
)
from scrutiny_agent import scrutinize
from document_generator import generate_docx, validate_document_spec
from database import init_db, create_user, get_user_by_email, get_user_by_id
from database import create_conversation, get_conversations, get_conversation
from database import delete_conversation, update_conversation_title
from database import add_message, get_messages, get_last_turn, touch_conversation, bulk_import_messages
from auth import hash_password, verify_password, create_token, decode_token

# In-memory storage for generated .docx files (session_id → bytes)
SESSION_DOCUMENTS: dict[str, bytes] = {}

# Track active conversation per user session (user_id → conv_id or session_id → conv_id)
ACTIVE_CONVERSATIONS: dict[str, int] = {}

# NEW: Agents import (for testing)
try:
    from agents.manager import manager
    from agents.triage import TriageAgent
    AGENTS_AVAILABLE = True
    TRIAGE_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Agents not available: {e}")
    AGENTS_AVAILABLE = False
    TRIAGE_AVAILABLE = False

try:
    from triage_state import get_triage_state, reset_triage_state, enrich_query_with_triage, MAX_INTAKE_QUESTIONS
    TRIAGE_STATE_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Triage state not available: {e}")

try:
    from agents.llm_client import get_binary_gate_llm
    from langchain_core.prompts import PromptTemplate
    from prompts.binary_gate import BINARY_GATE_PROMPT
    BINARY_GATE_AVAILABLE = True
    _BINARY_GATE_TEMPLATE = PromptTemplate(
        template=BINARY_GATE_PROMPT,
        input_variables=["user_query"]
    )
except Exception as e:
    print(f"[WARNING] Binary gate not available: {e}")
    BINARY_GATE_AVAILABLE = False
    TRIAGE_STATE_AVAILABLE = False

try:
    from discovery_agent import DiscoveryAgent
    from strategy_agent import StrategyAgent
    DISCOVERY_AVAILABLE = True
    STRATEGY_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] Discovery/Strategy agent not available: {e}")
    DISCOVERY_AVAILABLE = False
    STRATEGY_AVAILABLE = False

try:
    from irac_agent import IRACAgent
    IRAC_AVAILABLE = True
except Exception as e:
    print(f"[WARNING] IRAC agent not available: {e}")
    IRAC_AVAILABLE = False

# Pre-initialize triage agent
_triage_agent = TriageAgent() if TRIAGE_AVAILABLE else None

# ─────────────────────────────────────────────────────────────
# APP INIT
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title       = "SaulGPT Legal API",
    description = "6-Layer AI pipeline + Contract Evaluation + Interactive Drafter",
    version     = "2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# ─────────────────────────────────────────────────────────────
# REQUEST MODELS
# ─────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query:       str
    session_id:  str           = "web_session_1"
    mode:        Optional[str] = None
    conv_id:     Optional[int] = None


class AuthRequest(BaseModel):
    email:    str
    password: str
    username: Optional[str] = None


class AuthResponse(BaseModel):
    token:    str
    user_id:  int
    email:    str
    username: str


# ─────────────────────────────────────────────────────────────
# LIFECYCLE
# ─────────────────────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    print("🚀 SaulGPT API v2 starting...")
    init_db()
    print("✅ Database initialized.")
    start_auto_updater()
    print("✅ Ready on port 8000.")


# ─────────────────────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────────────────────

@app.get("/")
async def health_check():
    return {
        "status":   "SaulGPT API is Online ⚖️",
        "version":  "2.0.0",
        "features": ["6-layer RAG", "Contract Evaluation", "Interactive Drafter"]
    }


# ─────────────────────────────────────────────────────────────
# AGENT RESPONSE NORMALIZER
# ─────────────────────────────────────────────────────────────

def _populate_frontend_widgets(
    result: dict,
    session_id: str = None
):
    """
    Populate meta fields for frontend widgets (UrgencyBanner,
    JurisdictionBadge, VetoCard) from triage state + scrutiny result.
    """
    try:
        from triage_state import get_triage_state
        ts = get_triage_state(session_id)
        intake = ts.get("intake_fields", {})

        # ── JurisdictionBadge from triage jurisdiction_note + intake ──
        if not result.get("jurisdiction_mapped"):
            jn = ts.get("jurisdiction_note") or result.get("jurisdiction_note", "")
            court_level = None
            if "Small Claims" in jn:
                court_level = "Magistrate"
            elif "District Court" in jn or "Commercial Court" in jn:
                court_level = "District Court"
            elif "High Court" in jn:
                court_level = "High Court"
            if court_level:
                result["jurisdiction_mapped"] = {
                    "court_level": court_level,
                    "jurisdiction_type": "Civil",
                    "territorial": f"At {intake.get('location', 'appropriate jurisdiction')}",
                    "pecuniary": intake.get("amount", "As applicable"),
                }

        # ── UrgencyBanner from triage limitation_warning + intake ──
        if not result.get("urgency_flags"):
            lw = ts.get("limitation_warning") or result.get("limitation_warning", "")
            if "LIMITATION ALERT" in lw or "LIMITATION WARNING" in lw:
                # Parse remaining months from text like "Only **3 month(s)** remain"
                import re
                m = re.search(r"(\d+)\s*month", lw)
                if m:
                    days = int(m.group(1)) * 30
                    result["limitation_days"] = days
                result["urgency_flags"] = ["notice_period_expiring"]
                result["urgency_reason"] = lw
            elif "time-barred" in lw or "may be time-barred" in lw:
                result["urgency_flags"] = ["immediate_filing_required"]
                result["urgency_reason"] = lw

        # ── BNS CorrectionNotice from response text + citations ──
        # Wire remapped_laws for ALL responses (not just document drafting)
        if not result.get("remapped_laws"):
            response_text = result.get("response", "")
            citations = result.get("citations", [])
            # Check citations for repealed acts
            repealed_acts_in_result = set()
            for c in citations:
                name = (c.get("act_name") or "").lower()
                if "ipc" in name or "indian penal code" in name:
                    repealed_acts_in_result.add("IPC")
                if "crpc" in name or "code of criminal procedure" in name:
                    repealed_acts_in_result.add("CrPC")
                if "iea" in name or "indian evidence act" in name:
                    repealed_acts_in_result.add("Indian Evidence Act")
            # Check response text for old law mentions
            if "IPC" in response_text or "Indian Penal Code" in response_text or " ipc " in response_text.lower():
                repealed_acts_in_result.add("IPC")
            if "CrPC" in response_text or "Code of Criminal Procedure" in response_text:
                repealed_acts_in_result.add("CrPC")
            if "IEA" in response_text or "Indian Evidence Act" in response_text:
                repealed_acts_in_result.add("Indian Evidence Act")
            # Build remapped_laws
            LAW_REMAP = {
                "IPC": "BNS (Bharatiya Nyaya Sanhita, 2023)",
                "Indian Penal Code": "BNS (Bharatiya Nyaya Sanhita, 2023)",
                "CrPC": "BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023)",
                "Code of Criminal Procedure": "BNSS (Bharatiya Nagarik Suraksha Sanhita, 2023)",
                "Indian Evidence Act": "BSA (Bharatiya Sakshya Adhiniyam, 2023)",
                "IEA": "BSA (Bharatiya Sakshya Adhiniyam, 2023)",
            }
            remapped = {}
            for act in repealed_acts_in_result:
                if act in LAW_REMAP:
                    remapped[act] = LAW_REMAP[act]
            if remapped:
                result["remapped_laws"] = remapped
                # Also set inside meta for frontend widgets
                if "meta" not in result:
                    result["meta"] = {}
                if isinstance(result["meta"], dict):
                    result["meta"]["remapped_laws"] = remapped

    except Exception:
        pass  # Widget population is best-effort


def _normalize_agent_response(result: dict, query: str = "", mode: str = None, session_id: str = None) -> dict:
    """
    Normalizes agent response to match frontend expectations
    (same shape as old pipeline response).
    """
    defaults = {
        "original_query":       query,
        "status":               "success",
        "mode_used":            result.get("mode_used", mode or "knowledge"),
        "domain":               result.get("domain", "general"),
        "laws_retrieved":       result.get("laws_retrieved", 0),
        "citations":            result.get("citations", []),
        "graph_insights":       result.get("graph_insights", []),
        "case_law_found":       result.get("case_law_found", False),
        "is_hallucinating":     result.get("is_hallucinating", False),
        "confidence_score":     result.get("confidence_score", 0.85),
        "flagged_citations":    result.get("flagged_citations", []),
        "repealed_warnings":    result.get("repealed_warnings", []),
        "struck_down_warnings": result.get("struck_down_warnings", []),
        "elapsed_seconds":      result.get("elapsed_seconds", 0),
    }
    defaults.update(result)
    defaults["response"] = result.get("response", "No response generated.")

    # Populate frontend widget fields from triage state
    if session_id:
        _populate_frontend_widgets(defaults, session_id)

    return defaults


# ─────────────────────────────────────────────────────────────
# MAIN CHAT ENDPOINT
# ─────────────────────────────────────────────────────────────

def _build_triage_response(triage_result: dict, session_id: str = None) -> dict:
    """Build a frontend-friendly triage response with SWOT + options."""
    has_options = bool(triage_result.get("options"))
    is_intake = triage_result.get("is_intake_needed", False)

    resp_text = triage_result.get("clarifying_question") or (
        "I've analyzed your situation. Here are your strategic options:"
    )

    triage_payload = {
        "swot_analysis":        triage_result.get("swot_analysis"),
        "options":              triage_result.get("options", []),
        "allow_explanation":    triage_result.get("allow_explanation_trigger", True),
        "allow_advocate":       triage_result.get("allow_advocate_mode", True),
        "is_explanation":       triage_result.get("_is_explanation", False),
        "is_intake_needed":     is_intake,
        "limitation_warning":   triage_result.get("limitation_warning"),
        "jurisdiction_note":    triage_result.get("jurisdiction_note"),
        "extracted_fields":     triage_result.get("extracted_fields", {}),
    }

    return {
        "status":           "triage",
        "mode_used":        "triage",
        "response":         resp_text,
        "triage":           triage_payload,
        "session_id":       session_id or "",
        "interview_active": False,
        "limitation_warning": triage_result.get("limitation_warning"),
        "jurisdiction_note":  triage_result.get("jurisdiction_note"),
    }


# ── Direct legal query patterns (bypass Discovery, go straight to Knowledge) ──
_DIRECT_LEGAL_PATTERNS = [
    # Section/Article references
    r"(section|sec|article|s\.|art\.)\s*\d+",
    # Specific Indian acts
    r"(negotiable instruments|industrial disputes|hindu marriage|motor vehicles|"
    r"indian penal|code of criminal|code of civil|indian evidence|"
    r"bharatiya nyaya|bharatiya nagarik|bharatiya sakshya|"
    r"constitution of india|transfer of property|specific relief|"
    r"limitation act|contract act|partnership act|companies act)",
    # Legal procedure questions
    r"can i (file|sue|put them in|get|claim|apply|register)",
    r"(is it|is this) (legal|illegal|valid|allowed|permitted)",
    r"what (is the|are the) (punishment|penalty|ingredients|procedure|grounds|difference)",
    r"how (many|long|much) (days|months|years|notice|time)",
    r"under (section|article|which|what) (law|act|section)",
    r"does .* violate (article|section|law|right|act)",
    r"right to (file|sue|claim|appeal|apply)",
    r"legal (under|according to|as per)",
]

_SITUATIONAL_LEGAL_ANCHORS = [
    # Employment
    r"(unpaid|salary|wages|firing|termination|notice period|pf|provident fund|gratuity|workplace harassment|constructive dismissal)",
    # Tenancy
    r"(landlord|eviction|deposit refund|illegal lockout|tenancy|rent agreement|lease)",
    # Family
    r"(divorce|maintenance|custody|dowry|domestic violence|inheritance|will|succession|adoption|guardianship)",
    # Money/Fraud
    r"(unpaid loan|cheque bounce|business partner fraud|investment scam|non.?refund|embezzlement)",
    # Property
    r"(ownership dispute|encroachment|sale deed|illegal construction|property dispute|boundary dispute)",
    # Digital
    r"(account ban|online fraud|defamation|data breach|internet restriction|cyber crime|phishing)",
    # Criminal
    r"(threats|assault|stalking|extortion|trespass|blackmail|kidnapping|robbery|theft|dacoity)",
    # Corporate
    r"(company registration|LLP|MCA|GST registration|partnership deed|director liability|msme|startup registration)",
    # Consumer
    r"(product defect|insurance rejection|medical negligence|service failure|deficient service|flawed product)",
    # Constitutional
    r"(fundamental rights|right to life|freedom of speech|right to equality|right to education|writ petition|habeas corpus)",
]

_NON_INDIAN_JURISDICTIONS = [
    r"\bcalifornia\b", r"\bnew york\b", r"\btexas\b", r"\bflorida\b",
    r"\bunited states\b", r"\bu\.?s\.?a?\b", r"\bUK\b", r"\bengland\b",
    r"\blondon\b", r"\bcanada\b", r"\baustralia\b", r"\beuropean union\b",
    r"\bEU\b", r"\bsingapore\b", r"\bmalaysia\b",
]

# ── Crisis / emergency patterns (checked before triage) ──
_CRISIS_RESPONSES = {
    "self_harm": (
        "I hear you, and your wellbeing comes first, before any legal matter.\n\n"
        "**Please reach out for immediate support:**\n"
        "• **AASRA** (24x7 suicide prevention): **+91-9820466726**\n"
        "• **iCall** (mental health helpline): **+91-9152987821** (Mon-Sat 10am-8pm)\n"
        "• **Vandrevala Foundation**: **1860-266-2345** (24x7)\n"
        "• **Emergency**: **112** (National Emergency Number)\n\n"
        "Please talk to someone you trust or visit the nearest hospital. "
        "Your legal issue can wait — your safety cannot."
    ),
    "active_violence": (
        "This sounds like an **emergency situation** that needs immediate action.\n\n"
        "**Please contact emergency services now:**\n"
        "• **Police**: **100**\n"
        "• **National Emergency**: **112**\n"
        "• **Women's Helpline**: **1091**\n"
        "• **Child Helpline**: **1098**\n\n"
        "Go to a safe location if you can. I can help you with legal options "
        "once you're out of immediate danger."
    ),
    "confinement": (
        "This sounds like an **emergency situation** involving unlawful confinement.\n\n"
        "**Please contact emergency services now:**\n"
        "• **Police**: **100**\n"
        "• **National Emergency**: **112**\n"
        "• **Women's Helpline**: **1091**\n\n"
        "If you can, inform a trusted person about your location. "
        "I can assist with legal recourse once you are in a safe environment."
    ),
}

_CRISIS_PATTERNS = {
    "self_harm": [
        r"(kill|end|take) my (own )?(life|self)",
        r"suicide",
        r"(hurt|harm|cut) myself",
        r"i (want|am going) to (die|end it)",
        r"no (point|reason) (to )?(live|living)",
        r"(suicide )?(note|letter)",
        r"i (can'?t|cannot) (do this|take it) (anymore|any longer)",
    ],
    "active_violence": [
        r"(beating|hitting|attacking|choking|strangling) me (right now|currently|at this moment)",
        r"(weapon|knife|gun|blade|stick) .*(right now|in front|here|currently)",
        r"help me.*(bleeding|hurt|injured|in danger|attack)",
        r"(trying to|about to) (kill|hurt|attack|harm) me",
    ],
    "confinement": [
        r"(locked|trapped|held) (in|inside|against my will)",
        r"(can'?t|cannot) (leave|escape|get out)",
        r"(took|confiscated|stole) my (passport|phone|id|documents)",
        r"(holding|keeping) me (hostage|captive)",
        r"padlock(ed)?",
    ],
}


def _detect_crisis(query: str) -> str | None:
    """Detect if query signals an emergency. Returns crisis type or None."""
    query_lower = query.strip().lower()
    for crisis_type, patterns in _CRISIS_PATTERNS.items():
        if any(re.search(p, query_lower) for p in patterns):
            return crisis_type
    return None


def _is_direct_legal_query(query: str) -> bool:
    """Check if query is a direct legal question that should skip Discovery."""
    query_lower = query.strip().lower()
    # Tier 1: Explicit legal patterns (acts, sections, procedures)
    if any(re.search(p, query_lower) for p in _DIRECT_LEGAL_PATTERNS):
        return True
    # Tier 2: Situational anchors (landlord, eviction, dowry, etc.)
    if any(re.search(p, query_lower) for p in _SITUATIONAL_LEGAL_ANCHORS):
        return True
    return False


def _extract_gate_json(raw: str) -> dict:
    """4-layer JSON extraction for binary gate output (same pattern as layer1)._"""
    import json
    raw = raw.strip()
    if raw.startswith("{"):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    m = __import__("re").search(r'```(?:json)?\s*\n(.*?)\n```', raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    result = {}
    for line in raw.split("\n"):
        line = line.strip().lower()
        if 'classification' in line:
            if 'legal' in line and 'non' not in line:
                result["classification"] = "LEGAL"
            elif 'non' in line:
                result["classification"] = "NON-LEGAL"
        if 'web_fallback' in line:
            result["web_fallback_recommended"] = 'true' in line
        if 'is_non_legal' in line:
            result["is_non_legal"] = 'true' in line
    if result.get("classification"):
        result.setdefault("is_non_legal", result["classification"] == "NON-LEGAL")
        result.setdefault("web_fallback_recommended", False)
        return result
    return {"classification": "LEGAL", "is_non_legal": False, "web_fallback_recommended": False}


def _detect_non_indian_jurisdiction(query: str) -> str | None:
    """Detect if query refers to a non-Indian jurisdiction. Returns the jurisdiction name or None."""
    query_lower = query.strip().lower()
    for pattern in _NON_INDIAN_JURISDICTIONS:
        m = re.search(pattern, query_lower)
        if m:
            return m.group(0)
    return None


# Phrases that indicate user rejects all shown options
_REJECTION_PATTERNS = [
    "none of these", "other option", "not satisfied", "different way",
    "alternate", "anything else", "not helpful", "tell me other",
    "not what i need", "something else", "another way"
]


def _get_route_to(choice: str, options: list) -> str:
    """Read route_to from the chosen option. Never returns 'analysis' (killed fallback)."""
    for opt in options:
        if opt.get("id") == choice:
            return opt.get("route_to", "pathfinder")
    return "pathfinder"  # safe default for unrecognized IDs


def _is_rejection(query: str) -> bool:
    """Check if user is rejecting the shown triage options."""
    q = query.strip().lower()
    return any(p in q for p in _REJECTION_PATTERNS)


def _resolve_triage_choice(query: str, options: list) -> str:
    """
    Check if user's query matches a triage option label or id.
    Returns the option id if matched, None otherwise.
    """
    q = query.strip().lower()
    for opt in options:
        opt_id = opt.get("id", "").lower()
        opt_label = opt.get("label", "").lower()
        if q == opt_id or q == opt_label or q in opt_label:
            return opt.get("id")
    return None


def _maybe_offer_voluntary_intake(resp: dict, triage_state: dict, triage_result: dict) -> dict:
    """If there are still fields to gather, append a voluntary prompt."""
    if not triage_state or not triage_result:
        return resp
    intake_fields = triage_state.get("intake_fields", {})
    has_missing = triage_result.get("is_intake_needed") or any(
        not intake_fields.get(f) for f in ["amount", "incident_date", "location"]
    )
    if has_missing:
        triage_state["voluntary_intake_open"] = True
        resp["response"] += "\n\n---\n✨ **Would you like to provide any additional details to strengthen your case?** (Yes/No)"
        if "triage" in resp:
            resp["triage"]["voluntary_intake_offered"] = True
    return resp


def _interview_response(state, response_text):
    """Helper — builds standard response dict for interview turns."""
    return {
        "status":               "interviewing",
        "interview_complete":   False,
        "response":             response_text,
        "interview_active":     True,
        "progress_pct":         state.progress_pct,
        "domain":               "civil",
        "mode_used":            "document",
        "laws_retrieved":       0,
        "citations":            [],
        "graph_insights":       [],
        "case_law_found":       False,
        "is_hallucinating":     False,
        "confidence_score":     1.0,
        "flagged_citations":    [],
        "repealed_warnings":    [],
        "struck_down_warnings": [],
        "elapsed_seconds":      0,
    }


# ── Confirmation detection patterns ──
_CONFIRMATION_PATTERNS = [
    "yes", "yeah", "yep", "sure", "ok", "okay", "proceed",
    "go ahead", "do it", "generate", "draft", "create",
    "please do", "sounds good", "go for it", "fine"
]


def _is_confirmation(query: str) -> bool:
    """Check if user is confirming document generation."""
    q = query.strip().lower().rstrip(".!?")
    return any(p == q or q.startswith(p) for p in _CONFIRMATION_PATTERNS)


def _generate_document_docx(session_id: str, state) -> dict:
    """
    Generate .docx from interview state, store in memory,
    reset interview state, return response with download_url.
    """
    draft_context = state.get_draft_context()
    scrutiny_res = state.scrutiny_result
    display_name = draft_context["display_name"]
    filled_fields = draft_context["filled_fields"]
    doc_type_key = draft_context.get("doc_type")
    doc_family = draft_context.get("doc_family")

    # ── Generate structured document spec (new path) ──
    spec = generate_document_spec(
        doc_family=doc_family or "letter",
        doc_type=doc_type_key or "legal_document",
        display_name=display_name,
        problem_description=getattr(state, 'problem_description', ""),
        filled_fields=filled_fields,
    )

    if spec:
        # Validate spec against guardrails
        validation = validate_document_spec(spec, filled_fields)
        if not validation["valid"]:
            # If validation fails, log warnings and try to proceed with spec anyway
            # (the spec is still legally informative even if structure is imperfect)
            print(f"[Generator] Spec validation warnings: {validation['errors']}")
            if validation.get("warnings"):
                print(f"[Generator] Spec validation warnings: {validation['warnings']}")

        docx_bytes = generate_docx(
            display_name=display_name,
            filled_fields=filled_fields,
            doc_spec=spec,
        )
    else:
        # ── Legacy fallback if spec generation fails ──
        docx_bytes = generate_docx(
            display_name=display_name,
            filled_fields=filled_fields,
            doc_type=doc_type_key,
            is_dynamic=False,
            problem_description=getattr(state, 'problem_description', ""),
        )

    SESSION_DOCUMENTS[session_id] = docx_bytes

    response_text = (
        f"**{display_name}** has been drafted successfully.\n\n"
        f"[Download your document](http://localhost:8000/api/document/{session_id})\n\n"
        "Please review it carefully and consult a qualified advocate before use."
    )

    meta = {
        "scrutiny": {
            "is_valid": getattr(scrutiny_res, "is_valid", True) if scrutiny_res else True,
            "warnings": getattr(scrutiny_res, "warnings", []) if scrutiny_res else [],
            "veto_message": getattr(scrutiny_res, "veto_message", "") if scrutiny_res else "",
            "can_proceed": True,
            "remapped_laws": getattr(scrutiny_res, "remapped_laws", {}) if scrutiny_res else {},
            "limitation_info": getattr(scrutiny_res, "limitation_info", "") if scrutiny_res else "",
            "severity": "warning",
        },
        "remapped_laws": getattr(scrutiny_res, "remapped_laws", {}) if scrutiny_res else {},
        "jurisdiction_mapped": getattr(scrutiny_res, "jurisdiction", None) if scrutiny_res else None,
        "urgency_flags": getattr(scrutiny_res, "urgency_flags", []) if scrutiny_res else [],
        "limitation_days": getattr(scrutiny_res, "limitation_days", None) if scrutiny_res else None,
        "limitation_expiry": getattr(scrutiny_res, "limitation_expiry", None) if scrutiny_res else None,
        "urgency_reason": getattr(scrutiny_res, "urgency_reason", None) if scrutiny_res else None,
        "document_ready": True,
        "document_url": f"/api/document/{session_id}",
    }

    state.reset()
    if TRIAGE_STATE_AVAILABLE:
        reset_triage_state(session_id)
    return {
        "interview_active": False,
        "interview_complete": True,
        "response": response_text,
        "meta": meta,
        "mode_used": "document",
    }


# ── Helper: save chat turn to DB for authenticated users ──
def _save_to_db(user_id: int, conv_id: int, query: str, result: dict):
    import json
    turn = get_last_turn(conv_id) + 1
    add_message(conv_id, "user", query, turn=turn)
    meta_json = json.dumps({k: v for k, v in result.items() if k != "response"}, default=str)
    add_message(conv_id, "assistant", result.get("response", ""), meta=meta_json, turn=turn + 1)
    touch_conversation(conv_id)
    # Auto-set title from first user query (max 60 chars)
    if turn == 1:
        title = query.strip()[:60]
        if len(query) > 60:
            title += "..."
        update_conversation_title(conv_id, title)


def _save_assistant_response(conv_id: int, result: dict):
    """Save only the assistant response to DB (user message already saved)."""
    import json
    turn = get_last_turn(conv_id) + 1
    meta_json = json.dumps({k: v for k, v in result.items() if k != "response"}, default=str)
    add_message(conv_id, "assistant", result.get("response", ""), meta=meta_json, turn=turn)
    touch_conversation(conv_id)


def _save_and_return(result: dict, user_id, conv_id):
    """Save assistant response to DB if authenticated, then return result."""
    if user_id and conv_id and isinstance(result, dict):
        _save_assistant_response(conv_id, result)
        result["conv_id"] = conv_id  # inject conv_id so frontend persists it to localStorage
    return result


# ─────────────────────────────────────────────────────────────
# INTERRUPTION HANDLING (State Stack)
# ─────────────────────────────────────────────────────────────

_INTERRUPT_CLARIFICATION = [
    "why", "what is", "explain", "how is", "can you tell",
    "what does", "why is", "reason", "purpose", "how does",
    "meaning", "define",
]

_INTERRUPT_HYPOTHETICAL = [
    "what if", "suppose", "imagine", "hypothetically",
    "what happens if",
]

_INTERRUPT_PUSHBACK = [
    "i think", "i disagree", "that's not right", "that's wrong",
    "actually,", "but what about", "let's ask for", "why not",
    "too low", "too high", "i want", "let's put", "make it",
]


def _classify_interruption(query: str, state=None) -> Optional[str]:
    """Classify a mid-interview interruption by intent.
    
    Two-layer approach:
    1. Fast path — keyword patterns (zero LLM cost, covers ~80% of cases)
    2. Fallback — LLM classification (covers semantic variants at ~50 tokens/call)
    """
    q = query.lower().strip()

    # ── Fast path: keywords ──
    # Short queries (< 5 chars) that aren't yes/no/ok are likely clarification
    if len(q) < 5 and q not in ("yes", "no", "ok", "sure", "y", "n", "1", "2"):
        return "clarification"

    if any(q.startswith(s) for s in _INTERRUPT_PUSHBACK):
        return "pushback"

    if any(s in q for s in _INTERRUPT_HYPOTHETICAL):
        return "hypothetical"

    if any(q.startswith(s) for s in _INTERRUPT_CLARIFICATION):
        return "clarification"

    # ── Fallback: LLM classification for queries that look non-answer ──
    # Skip if it looks like a straightforward field value (contains number or is very short)
    _LOOKS_LIKE_ANSWER = r"^(?:\d{1,4}[-/.]?\w*|\d+\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)|rs\.?\s*\d+|₹\d+)"
    if not re.match(_LOOKS_LIKE_ANSWER, q, re.IGNORECASE) and len(q) > 5:
        try:
            from interview_state import _ensure_field_llm
            llm = _ensure_field_llm()
            field_label = ""
            if state and hasattr(state, 'current_field') and state.current_field:
                idx = state._field_index
                if idx < len(state._pending_fields):
                    field_label = state._pending_fields[idx].get("label", state.current_field)
            prompt = (
                f"Field: '{field_label}'\n"
                f"User: '{query}'\n\n"
                f"Classify intent as ONE word:\n"
                f"- answer (providing the requested information)\n"
                f"- clarification (asking why, what, how about the field)\n"
                f"- hypothetical (what-if scenario, alternative course)\n"
                f"- pushback (disagreeing, suggesting different value)\n"
                f"Intent:"
            )
            resp = llm.invoke(prompt, max_tokens=5, temperature=0)
            intent = resp.content.strip().lower().rstrip(".")
            if intent in ("clarification", "hypothetical", "pushback"):
                return intent
        except Exception:
            pass

    return None


def _resume_after_interruption(state) -> str:
    """Re-ask the appropriate question based on the resumed state.
    If we popped back to a pushback, re-prompt the pushback confirmation.
    Otherwise re-ask the current field."""
    if state.state == "interruption:pushback":
        ctx = state.interruption_context
        suggested = ctx.get("suggested_value", "your suggestion")
        return f"**Regarding your suggestion:** Do you want to proceed with **{suggested}**? (Yes / No)"
    return state._ask_next() if state._field_index < len(state._pending_fields) else state._summarize()


def _handle_clarification(state, query: str) -> dict:
    """Explain why the current field matters, then re-ask."""
    from interview_state import _ensure_field_llm
    llm = _ensure_field_llm()
    field_key = state.current_field
    idx = state._field_index
    field_label = state._pending_fields[idx].get("label", field_key) if idx < len(state._pending_fields) else field_key

    prompt = (
        f"The user is drafting a legal document ({state.display_name}). "
        f"They were asked: '{field_label}'. Their response: '{query}'.\n\n"
        f"Explain in 2-3 clear sentences why this information is legally necessary. "
        f"Be specific (limitation period, court rules, evidence requirements, etc.). "
        f"Be practical and reassuring. If they don't know the exact answer, suggest a reasonable approximation."
    )
    try:
        resp = llm.invoke(prompt)
        explanation = resp.content.strip()
    except Exception:
        explanation = "This information helps us ensure the document is legally accurate and meets court requirements."

    state.pop_state()
    next_q = _resume_after_interruption(state)
    return {
        "response": f"{explanation}\n\n{next_q}",
        "interview_active": True,
        "state_stack_resumed": True,
    }


def _handle_hypothetical(state, query: str) -> dict:
    """Warn about the risks of the hypothetical, then re-ask."""
    from interview_state import _ensure_field_llm
    llm = _ensure_field_llm()
    prompt = (
        f"The user is drafting a legal document about: {state.problem_description}\n\n"
        f"They asked: '{query}'\n\n"
        f"Warn them about the legal risks of this alternative course of action in 3-4 sentences. "
        f"Be specific about Indian law sections where relevant (e.g., Defamation S.356 BNS, "
        f"Contempt of Court, etc.). End with: 'I strongly advise sticking to the formal legal route.'"
    )
    try:
        resp = llm.invoke(prompt)
        warning = resp.content.strip()
    except Exception:
        warning = "That alternative could expose you to legal liability. I strongly advise sticking to the formal legal route."

    state.pop_state()
    next_q = _resume_after_interruption(state)
    return {
        "response": f"{warning}\n\n{next_q}",
        "interview_active": True,
        "state_stack_resumed": True,
    }


def _handle_pushback(state, query: str) -> dict:
    """Evaluate the user's alternative suggestion and ask for confirmation."""
    from interview_state import _ensure_field_llm
    llm = _ensure_field_llm()
    field_key = state.current_field
    idx = state._field_index
    field_label = state._pending_fields[idx].get("label", field_key) if idx < len(state._pending_fields) else field_key
    current_value = state.collected.get(field_key, "not yet set")

    prompt = (
        f"The user is drafting: {state.display_name}\n"
        f"Field asked: '{field_label}'\n"
        f"Their current value: '{current_value}'\n"
        f"Their suggestion: '{query}'\n\n"
        f"Evaluate their suggestion against legal reality in 3-4 sentences:\n"
        f"1. Is their suggestion legally viable?\n"
        f"2. What are the practical consequences (court fees, evidence, limitation)?\n"
        f"3. Are there any risks they should know?\n"
        f"End by asking: 'Do you want to proceed with this? (Yes / No)'"
    )
    try:
        resp = llm.invoke(prompt)
        evaluation = resp.content.strip()
    except Exception:
        evaluation = (
            f"Your suggestion has been noted. However, you should be aware that the amount/value "
            f"you specify may affect court fees, jurisdiction, and legal strategy. "
            f"Do you want to proceed with this? (Yes / No)"
        )

    state.push_state("interruption:pushback", {
        "question": field_key,
        "label": field_label,
        "suggested_value": query,
    })
    return {
        "response": evaluation,
        "interview_active": True,
        "confirmation_needed": True,
        "interruption_type": "pushback",
    }


def _handle_pushback_confirmation(state, query: str) -> dict:
    """User responded to a pushback — yes/no on the suggested value."""
    ctx = state.interruption_context
    suggested = ctx.get("suggested_value", query)
    field_key = ctx.get("question", state.current_field)

    if _is_confirmation(query):
        state.collected[field_key] = suggested
        state.pop_state()
        state._field_index += 1
        next_q = state._ask_next()
        return {
            "response": f"Updated. {next_q}",
            "interview_active": True,
        }
    else:
        state.pop_state()
        next_q = state._ask_next()
        return {
            "response": f"No changes made. {next_q}",
            "interview_active": True,
        }
        
@app.post("/api/chat")
async def chat_endpoint(
    request: QueryRequest,
    fastapi_request: Request,
):
    """
    Main chat endpoint. Checks interview state first,
    then routes to normal pipeline or interview flow.
    For authenticated users, persists conversations to SQLite.
    """
    try:
        session_id = request.session_id
        query      = request.query.strip()

        # ── Extract authenticated user (optional) ──
        authorization = fastapi_request.headers.get("authorization", "")
        user_id = _get_user_id(authorization)
        conv_id = request.conv_id

        # ── For authenticated users: resolve conversation ──
        if user_id:
            if conv_id:
                conv = get_conversation(conv_id, user_id)
                if not conv:
                    raise HTTPException(404, "Conversation not found")
            else:
                if session_id in ACTIVE_CONVERSATIONS:
                    conv_id = ACTIVE_CONVERSATIONS[session_id]
                    conv = get_conversation(conv_id, user_id)
                    if not conv:
                        conv_id = create_conversation(user_id)
                        ACTIVE_CONVERSATIONS[session_id] = conv_id
                else:
                    conv_id = create_conversation(user_id)
                    ACTIVE_CONVERSATIONS[session_id] = conv_id

        # ── Persist user query to DB immediately ──
        if user_id and conv_id:
            _turn = get_last_turn(conv_id) + 1
            add_message(conv_id, "user", query, turn=_turn)
            if _turn == 1:
                _title = query.strip()[:60]
                if len(query) > 60:
                    _title += "..."
                update_conversation_title(conv_id, _title)

        # ── Active interview: accept answer ──
        state = get_interview_state(session_id)

        # ── LAYER 0: INTERRUPTION GUARD (runs BEFORE all state routing) ──
        # If we're in an active interview with an unanswered field, check for
        # interruptions FIRST before the query reaches any field extractor.
        if state.state in ("interviewing", "interruption:clarification",
                           "interruption:hypothetical", "interruption:pushback"):
            field_unanswered = (
                state.current_field
                and state._field_index < len(state._pending_fields)
                and state.collected.get(state.current_field) is None
            )
            if state.state == "interruption:pushback":
                # Nested check: even while awaiting pushback confirmation, the user
                # may throw another interruption ("actually what if 60 instead")
                nested_intent = _classify_interruption(query, state)
                if nested_intent:
                    state.push_state(f"interruption:{nested_intent}")
                    if nested_intent == "clarification":
                        return _save_and_return(_handle_clarification(state, query), user_id, conv_id)
                    elif nested_intent == "hypothetical":
                        return _save_and_return(_handle_hypothetical(state, query), user_id, conv_id)
                    elif nested_intent == "pushback":
                        return _save_and_return(_handle_pushback(state, query), user_id, conv_id)
                # Otherwise fall through to normal pushback confirmation below
            elif field_unanswered and state.state == "interviewing":
                intent = _classify_interruption(query, state)
                if intent == "clarification":
                    return _save_and_return(_handle_clarification(state, query), user_id, conv_id)
                elif intent == "hypothetical":
                    return _save_and_return(_handle_hypothetical(state, query), user_id, conv_id)
                elif intent == "pushback":
                    return _save_and_return(_handle_pushback(state, query), user_id, conv_id)
            # else: no interruption — fall through to state routing

        # ── Pending generation confirmation: user is saying yes/no to .docx ──
        if state.state == "pending_generation" and state.confirm_generation:
            if _is_confirmation(query):
                return _save_and_return(_generate_document_docx(session_id, state), user_id, conv_id)
            else:
                doc_name = state.display_name
                state.reset()
                if TRIAGE_STATE_AVAILABLE:
                    reset_triage_state(session_id)
                return _save_and_return({
                    "interview_active": False,
                    "interview_complete": True,
                    "response": f"Alright, I won't draft the **{doc_name}**. "
                                "If you change your mind, just let me know."
                }, user_id, conv_id)

        # ── Interrupted interview (legacy path, fallback) ──
        if state.state == "interrupted":
            if query.lower().strip() in ("cancel", "2", "stop", "never mind", "2️⃣"):
                doc_name = state.display_name
                state.reset()
                if TRIAGE_STATE_AVAILABLE:
                    reset_triage_state(session_id)
                return _save_and_return({
                    "interview_active": False,
                    "response": f"Alright, I've cancelled the **{doc_name}** draft. How can I help you?",
                }, user_id, conv_id)
            else:
                state.state = "interviewing"
                state.pop_state()
                next_q = state.record_answer(query)
                if next_q:
                    return _save_and_return(_interview_response(state, next_q), user_id, conv_id)

        # ── Pushback confirmation (second turn of pushback flow) ──
        if state.state == "interruption:pushback":
            return _save_and_return(_handle_pushback_confirmation(state, query), user_id, conv_id)

        # ── Interviewing: answer the current field ──
        if state.state == "interviewing":
            # Defense-in-depth: re-check interruptions before recording answer.
            # Catches any cases LAYER 0 missed due to state routing subtleties.
            if state.current_field and state._field_index < len(state._pending_fields):
                intent = _classify_interruption(query, state)
                if intent == "clarification":
                    return _save_and_return(_handle_clarification(state, query), user_id, conv_id)
                elif intent == "hypothetical":
                    return _save_and_return(_handle_hypothetical(state, query), user_id, conv_id)
                elif intent == "pushback":
                    return _save_and_return(_handle_pushback(state, query), user_id, conv_id)
            next_q = state.record_answer(query)

            if next_q:
                return _save_and_return(_interview_response(state, next_q), user_id, conv_id)

            # All fields collected — run pre-flight scrutiny
            draft_context = state.get_draft_context()
            prob_desc = getattr(state, 'problem_description', query)
            filled_f  = draft_context.get("filled_fields", {})

            scrutiny_res = scrutinize(prob_desc, filled_f)

            # VETO CHECK: If the agent says STOP, we stop.
            if getattr(scrutiny_res, 'can_proceed', True) is False:
                state.reset()
                if TRIAGE_STATE_AVAILABLE:
                    reset_triage_state(session_id)
                return _save_and_return({
                    "status": "vetoed",
                    "response": "Legal scrutiny has identified critical issues with this matter.",
                    "interview_active": False,
                    "interview_complete": True,
                    "meta": {
                        "scrutiny": {
                            "is_valid": False,
                            "warnings": scrutiny_res.warnings,
                            "veto_message": scrutiny_res.veto_message,
                            "can_proceed": False,
                            "remapped_laws": getattr(scrutiny_res, 'remapped_laws', {}),
                            "severity": "serious"
                        }
                    }
                }, user_id, conv_id)

            # Ask user for explicit confirmation before generating
            state.confirm_generation = True
            state.state = "pending_generation"
            state.scrutiny_result = scrutiny_res

            summary_lines = [
                f"**{state.display_name}** — I have all the information needed.",
                "",
                "Here's what you've provided:"
            ]
            for key, val in state.collected.items():
                label = state.doc_schema["fields"][key]["label"]
                summary_lines.append(f"  **{label}:** {val}")

            # Include scrutiny warnings if any
            warnings = getattr(scrutiny_res, 'warnings', [])
            if warnings:
                summary_lines.append("")
                summary_lines.append("**Note:** " + " ".join(warnings[:2]))

            summary_lines.append("")
            summary_lines.append("**Shall I proceed to draft this document?** (Yes / No)")

            return _save_and_return({
                "interview_active": True,
                "interview_complete": False,
                "response": "\n".join(summary_lines),
                "confirmation_needed": True
            }, user_id, conv_id)

        # ── MANUAL MODE OVERRIDE: mode="document" bypasses triage entirely ──
        if request.mode == "document":
            # Detect doc_family and doc_type directly from query, skip triage
            doc_type = detect_document_type(query)
            doc_family = map_doc_type_to_family(doc_type) if doc_type else None
            if doc_type or doc_family:
                fields = generate_field_questions(
                    doc_family or "letter", doc_type or "legal_document", query
                )
                display_name = DOCUMENT_SCHEMAS.get(doc_type, {}).get("display_name",
                               doc_type.replace("_", " ").title() if doc_type else "Legal Document")
                if not fields:
                    fields = [{"key": "details", "label": "Describe your situation", "example": ""}]
                question = state.start_interview(
                    doc_type or "legal_document",
                    problem_description=query,
                    doc_family=doc_family or "letter",
                    dynamic_fields=fields
                )
                total = len(fields)
                intro = (
                    f"I'll draft a **{display_name}** for you.\n\n"
                    f"I need **{total} pieces of information**. "
                    f"Let's go through them one at a time.\n\n"
                    f"{question}"
                )
                return _save_and_return(_interview_response(state, intro), user_id, conv_id)
            # If no doc type detected, fall through to triage below

        # ── 3-PHASE "VIRTUAL COUNSEL" PIPELINE ──
        # Replaces old triage layer with Discovery (Phase 1) → Strategy (Phase 2) → Drafting (Phase 3)
        if TRIAGE_AVAILABLE and TRIAGE_STATE_AVAILABLE and DISCOVERY_AVAILABLE:
            triage_state = get_triage_state(session_id)
            current_mode = triage_state.get("current_mode", "idle")

            # Universal pre-check: crisis overrides any mode
            crisis_type = _detect_crisis(query)
            if crisis_type:
                resp = {
                    "response": _CRISIS_RESPONSES[crisis_type],
                    "mode_used": "crisis",
                    "domain": "general",
                    "interview_active": False,
                    "laws_retrieved": 0,
                    "citations": [],
                    "confidence_score": 0.0,
                    "crisis_help_shown": True,
                }
                _populate_frontend_widgets(resp, session_id)
                # Reset triage state so user can start fresh after crisis
                triage_state["current_mode"] = "idle"
                triage_state["discovery_turn_count"] = 0
                triage_state["discovery_profile"] = {}
                return _save_and_return(resp, user_id, conv_id)

            # ═══════════════════════════════════════════════
            # PHASE 0: INITIAL CLASSIFICATION (idle)
            # ═══════════════════════════════════════════════
            if current_mode == "idle":
                # Pre-check 1: Non-Indian jurisdiction → gate immediately
                non_indian_jur = _detect_non_indian_jurisdiction(query)
                if non_indian_jur:
                    resp = {
                        "response": (
                            f"Your question refers to **{non_indian_jur}** law, "
                            f"but my legal database is limited to **Indian law** "
                            f"(Constitution of India, IPC/BNS, CrPC/BNSS, CPC, "
                            f"Negotiable Instruments Act, Industrial Disputes Act, etc.).\n\n"
                            f"I cannot provide legal guidance for {non_indian_jur}. "
                            f"Please consult a qualified attorney licensed in that jurisdiction."
                        ),
                        "mode_used": "knowledge",
                        "domain": "general",
                        "interview_active": False,
                        "laws_retrieved": 0,
                        "citations": [],
                        "confidence_score": 0.0,
                    }
                    _populate_frontend_widgets(resp, session_id)
                    return _save_and_return(resp, user_id, conv_id)

                # Pre-check 2: Direct legal question — force knowledge even if triage says otherwise
                is_direct_legal = _is_direct_legal_query(query)

                # Pre-check 3: Binary gate for non-direct-legal queries
                # Catches off-topic queries before reaching triage LLM
                if not is_direct_legal and BINARY_GATE_AVAILABLE:
                    try:
                        gate_llm = get_binary_gate_llm()
                        gate_prompt = _BINARY_GATE_TEMPLATE.format(user_query=query)
                        gate_raw = gate_llm.invoke(gate_prompt).content.strip()
                        gate_result = _extract_gate_json(gate_raw)
                        if gate_result.get("classification") == "NON-LEGAL":
                            resp = {
                                "response": (
                                    "I'm designed to answer questions about **Indian law** "
                                    "(Constitution, IPC/BNS, CrPC/BNSS, CPC, Family Law, etc.). "
                                    "Your query doesn't appear to be a legal question. "
                                    "Could you rephrase or ask a law-related question?"
                                ),
                                "mode_used": "knowledge",
                                "domain": "legal",
                                "laws_retrieved": 0,
                                "citations": [],
                                "confidence_score": 0.0,
                            }
                            _populate_frontend_widgets(resp, session_id)
                            return _save_and_return(resp, user_id, conv_id)
                    except Exception as e:
                        print(f"[Binary Gate] Gate failed: {e}")

                triage_result = await _triage_agent.analyze(query, triage_state)

                # Override: if it's a direct legal question, force pass_through regardless of triage
                if is_direct_legal:
                    triage_result["pass_through"] = True
                    triage_result["suggested_mode"] = "knowledge"
                    triage_result["swot_analysis"] = None
                    triage_result["options"] = None
                    triage_result["role"] = None

                extracted = triage_result.get("extracted_fields", {})
                for k, v in extracted.items():
                    if v:
                        triage_state["intake_fields"][k] = v

                # Store classification fields regardless of pass_through
                if triage_result.get("doc_family"):
                    triage_state["doc_family"] = triage_result["doc_family"]
                if triage_result.get("doc_type"):
                    triage_state["doc_type"] = triage_result["doc_type"]
                if triage_result.get("suggested_mode"):
                    triage_state["goal"] = triage_result["suggested_mode"]
                if triage_result.get("role"):
                    triage_state["role"] = triage_result["role"]

                if triage_result.get("pass_through", True):
                    # Knowledge / off-topic / document — skip Discovery, route directly
                    triage_state["is_triaged"] = True
                    query = enrich_query_with_triage(query, triage_state)
                else:
                    # Personal grievance — enter Discovery (Phase 1)
                    triage_state["original_query"] = query
                    triage_state["current_mode"] = "discovery"
                    triage_state["discovery_profile"] = {}
                    triage_state["discovery_turn_count"] = 0

                    discovery_agent = DiscoveryAgent()
                    discovery_result = await discovery_agent.run(query)

                    triage_state["discovery_profile"] = discovery_result.get("discovery_profile", {})
                    triage_state["discovery_turn_count"] = 1

                    e_fields = discovery_result.get("extracted_fields", {})
                    for k, v in e_fields.items():
                        if v:
                            triage_state["intake_fields"][k] = v

                    resp = {
                        "response": discovery_result.get("response", "Tell me more about your situation."),
                        "mode_used": "discovery",
                        "domain": "civil",
                        "discovery_active": True,
                        "interview_active": False,
                        "laws_retrieved": 0,
                        "citations": [],
                        "graph_insights": [],
                        "case_law_found": False,
                        "is_hallucinating": False,
                        "confidence_score": 0.85,
                        "flagged_citations": [],
                        "repealed_warnings": [],
                        "struck_down_warnings": [],
                        "elapsed_seconds": 0,
                    }
                    _populate_frontend_widgets(resp, session_id)
                    return _save_and_return(resp, user_id, conv_id)

            # ═══════════════════════════════════════════════
            # PHASE 1: DISCOVERY (max 3 turns)
            # ═══════════════════════════════════════════════
            elif current_mode == "discovery":
                discovery_agent = DiscoveryAgent()
                existing_profile = triage_state.get("discovery_profile", {})
                discovery_turn = triage_state.get("discovery_turn_count", 0)

                discovery_result = await discovery_agent.run(query, existing_profile, discovery_turn)

                triage_state["discovery_profile"] = discovery_result.get("discovery_profile", {})
                triage_state["discovery_turn_count"] = discovery_turn + 1

                e_fields = discovery_result.get("extracted_fields", {})
                for k, v in e_fields.items():
                    if v:
                        triage_state["intake_fields"][k] = v

                if discovery_result.get("discovery_complete") or discovery_turn >= 2:
                    # Force transition to Strategy (Phase 2)
                    triage_state["current_mode"] = "strategy"

                    strategy_agent = StrategyAgent()
                    strategy_result = await strategy_agent.run(
                        triage_state.get("original_query", query),
                        triage_state["discovery_profile"]
                    )

                    triage_state["swot_analysis"] = strategy_result.get("swot_analysis")
                    triage_state["options_shown"] = strategy_result.get("options", [])
                    triage_state["allow_explain"] = strategy_result.get("allow_explanation_trigger", True)

                    resp = _build_triage_response(strategy_result, session_id)
                    return _save_and_return(resp, user_id, conv_id)
                else:
                    resp = {
                        "response": discovery_result.get("response", "Tell me more."),
                        "mode_used": "discovery",
                        "domain": "civil",
                        "discovery_active": True,
                        "interview_active": False,
                        "laws_retrieved": 0,
                        "citations": [],
                        "graph_insights": [],
                        "case_law_found": False,
                        "is_hallucinating": False,
                        "confidence_score": 0.85,
                        "flagged_citations": [],
                        "repealed_warnings": [],
                        "struck_down_warnings": [],
                        "elapsed_seconds": 0,
                    }
                    _populate_frontend_widgets(resp, session_id)
                    return _save_and_return(resp, user_id, conv_id)

            # ═══════════════════════════════════════════════
            # PHASE 2: STRATEGY (user picks option)
            # ═══════════════════════════════════════════════
            elif current_mode == "strategy":
                choice = _resolve_triage_choice(query, triage_state.get("options_shown", []))

                # "none of these work" — ADR fallback
                if not choice and _is_rejection(query):
                    rejection_prompt = (
                        "The user has rejected the primary legal/formal routes previously shown. "
                        "Provide alternative dispute resolution (ADR), community-based, or "
                        "non-litigious strategic paths only."
                    )
                    triage_result = await _triage_agent.analyze(
                        triage_state.get("original_query", query) + "\n\n" + rejection_prompt,
                        triage_state
                    )
                    if triage_result.get("options"):
                        triage_state["options_shown"] = triage_result.get("options", [])
                        triage_state["swot_analysis"] = triage_result.get("swot_analysis")
                        resp = _build_triage_response(triage_result, session_id)
                        return _save_and_return(resp, user_id, conv_id)

                # "advocate" / IRAC mode — intentional deep legal analysis
                if not choice:
                    user_lower = query.strip().lower()
                    is_advocate_request = any(kw in user_lower for kw in
                        ["advocate", "irac", "deep legal analysis", "advocate mode", "deep legal"])
                    # Exact match for "advocate" (button click frontend sends this)
                    if user_lower.strip() == "advocate":
                        is_advocate_request = True
                    if is_advocate_request and IRAC_AVAILABLE:
                        irac_agent = IRACAgent()
                        irac_result = await irac_agent.run(
                            triage_state.get("original_query", query),
                            triage_state.get("discovery_profile"),
                            triage_state.get("options_shown", [])
                        )
                        triage_state["current_mode"] = "idle"
                        _populate_frontend_widgets(irac_result, session_id)
                        return _save_and_return(irac_result, user_id, conv_id)
                    elif is_advocate_request:
                        resp_show = {
                            "response": "Deep legal analysis (IRAC Advocate Mode) is not available right now. Please try the standard options above.",
                            "mode_used": "strategy",
                            "triage": {
                                "swot_analysis": triage_state.get("swot_analysis"),
                                "options": triage_state.get("options_shown", []),
                                "allow_explanation": triage_state.get("allow_explain", True),
                                "is_explanation": False,
                            },
                            "interview_active": False,
                        }
                        _populate_frontend_widgets(resp_show, session_id)
                        return _save_and_return(resp_show, user_id, conv_id)

                if choice:
                    triage_state["chosen_path"] = choice
                    triage_state["is_triaged"] = True
                    mode = _get_route_to(choice, triage_state.get("options_shown", []))
                    request.mode = mode

                    if mode == "document":
                        # Route directly to document drafting interview
                        doc_type = detect_document_type(triage_state.get("original_query", query))
                        doc_family = map_doc_type_to_family(doc_type) if doc_type else None
                        if doc_type or doc_family:
                            fields = generate_field_questions(
                                doc_family or "letter", doc_type or "legal_document",
                                triage_state.get("original_query", query)
                            )
                            display_name = DOCUMENT_SCHEMAS.get(doc_type, {}).get("display_name",
                                           doc_type.replace("_", " ").title() if doc_type else "Legal Document")
                            if not fields:
                                fields = [{"key": "details", "label": "Describe your situation", "example": ""}]

                            question = state.start_interview(
                                doc_type or "legal_document",
                                problem_description=triage_state.get("original_query", query),
                                doc_family=doc_family or "letter",
                                dynamic_fields=fields
                            )
                            total = len(fields)
                            intro = (
                                f"I'll draft a **{display_name}** for you.\n\n"
                                f"I need **{total} pieces of information**. "
                                f"Let's go through them one at a time.\n\n"
                                f"{question}"
                            )
                            return _save_and_return(_interview_response(state, intro), user_id, conv_id)

                        # No doc type detected — treat as pathfinder instead
                        # Add preamble so pathfinder knows it's a fallback
                        mode = "pathfinder"
                        request.mode = "pathfinder"
                        triage_state["_fallback_note"] = "document_to_pathfinder"

                    if mode == "pathfinder":
                        original = triage_state.get("original_query", query)
                        enriched = enrich_query_with_triage(original, triage_state)
                        preamble = ""
                        if triage_state.get("_fallback_note") == "document_to_pathfinder":
                            preamble = "I couldn't map that to a specific document type, so here are the general legal steps:\n\n"
                        query = preamble + enriched + "\n[Request: Show step-by-step legal procedure for this option.]"
                else:
                    # User didn't pick an option — could be asking for explanation
                    triage_result = await _triage_agent.analyze(query, triage_state)
                    if triage_result.get("_is_explanation"):
                        return _save_and_return(_build_triage_response(triage_result, session_id), user_id, conv_id)

                    # Re-show options
                    resp_show = {
                        "response": "Please let me know which option you'd like to pursue.",
                        "mode_used": "strategy",
                        "triage": {
                            "swot_analysis": triage_state.get("swot_analysis"),
                            "options": triage_state.get("options_shown", []),
                            "allow_explanation": triage_state.get("allow_explain", True),
                            "is_explanation": False,
                        },
                        "interview_active": False,
                    }
                    _populate_frontend_widgets(resp_show, session_id)
                    return _save_and_return(resp_show, user_id, conv_id)

        # ── Use LLM-decided mode from triage (if available) ──
        # When triage returned pass_through=true, the LLM already inferred
        # the correct mode. Use it instead of keyword fallback detection.
        llm_mode = None
        if TRIAGE_STATE_AVAILABLE and not request.mode:
            ts = get_triage_state(session_id)
            if ts.get("goal"):
                llm_mode = request.mode = ts["goal"]

        # ── Document routing via doc_family from triage ──
        # If triage set suggested_mode="document", it also set doc_family + doc_type.
        # Only trust LLM-decided classification from triage, not keyword fallback.
        doc_family = None
        doc_type = None
        if TRIAGE_STATE_AVAILABLE:
            ts = get_triage_state(session_id)
            if ts.get("goal") == "document":
                doc_family = ts.get("doc_family")
                doc_type = ts.get("doc_type")

        if doc_family or doc_type:
            # ── SPEC-BASED INTERVIEW ──
            # Generate field questions via LLM or fallback to legacy schemas
            fields = generate_field_questions(
                doc_family or "letter",
                doc_type or "legal_document",
                query
            )
            display_name = DOCUMENT_SCHEMAS.get(doc_type, {}).get("display_name",
                           doc_type.replace("_", " ").title() if doc_type else "Legal Document")

            if not fields:
                # Should not happen — fallback fields always return something
                fields = [{"key": "details", "label": "Describe your situation", "example": ""}]

            question = state.start_interview(
                doc_type or "legal_document",
                problem_description=query,
                doc_family=doc_family or "letter",
                dynamic_fields=fields
            )
            total = len(fields)

            intro = (
                f"I'll draft a **{display_name}** for you.\n\n"
                f"I need **{total} pieces of information**. "
                f"Let's go through them one at a time.\n\n"
                f"{question}"
            )
            return _save_and_return(_interview_response(state, intro), user_id, conv_id)

        # ── Build triage_context from triage state ──
        triage_context = None
        if TRIAGE_STATE_AVAILABLE:
            ts = get_triage_state(session_id)
            if ts.get("is_triaged") or ts.get("role"):
                triage_context = {
                    "role": ts.get("role"),
                    "goal": ts.get("goal"),
                    "chosen_path": ts.get("chosen_path"),
                    "intake_fields": ts.get("intake_fields", {}),
                }

        # ── Agent Manager (new) or Pipeline fallback ──
        if AGENTS_AVAILABLE:
            result = await manager.run(
                query=query,
                mode=request.mode,
                session_id=session_id,
                conversation_history=get_history_with_summary(session_id),
                triage_context=triage_context
            )
            result = _normalize_agent_response(result, query, request.mode, session_id=session_id)
            # Save turn to conversation memory for sliding window
            save_turn_to_memory(
                session_id=session_id,
                user_query=query,
                domain=result.get("domain", "general"),
                mode=result.get("mode_used", request.mode or "knowledge"),
                response=result.get("response", ""),
                laws_cited=result.get("citations", []),
            )
        else:
            result = run_saulgpt_pipeline(
                user_query=query,
                session_id=session_id,
                mode=request.mode
            )
            if session_id:
                _populate_frontend_widgets(result, session_id)
        result["interview_active"] = False

        # ── Persist to SQLite for authenticated users ──
        if user_id and conv_id:
            result["conv_id"] = conv_id

        return _save_and_return(result, user_id, conv_id)

    except Exception as e:
        traceback.print_exc()
        print(f"[API] Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────────────────────────
# CONTRACT EVALUATOR ENDPOINT
# ─────────────────────────────────────────────────────────────

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_MB   = 50


@app.post("/api/upload")
async def upload_and_evaluate(file: UploadFile = File(...)):
    """
    Accepts PDF, DOCX, or TXT.
    Returns structured Red Pen evaluation report.
    """
    try:
        ext = os.path.splitext(file.filename.lower())[1]
        if ext not in ALLOWED_EXTENSIONS:
            return {
                "response": (
                    f"🚨 Unsupported file type: **{ext}**\n\n"
                    f"Accepted formats: PDF, DOCX, TXT"
                ),
                "meta": None
            }

        file_bytes = await file.read()
        size_mb    = len(file_bytes) / (1024 * 1024)

        if size_mb > MAX_FILE_SIZE_MB:
            return {
                "response": (
                    f"🚨 File too large: **{size_mb:.1f}MB** "
                    f"(max {MAX_FILE_SIZE_MB}MB)"
                ),
                "meta": None
            }

        print(f"[API] Evaluating: {file.filename} ({size_mb:.2f}MB)")
        evaluation = evaluate_contract(file_bytes, file.filename)
        response   = format_evaluation_response(evaluation)

        return {
            "response":        response,
            "evaluation_data": evaluation,
            "meta": {
                "mode_used":            "evaluate",
                "domain":               "civil",
                "is_hallucinating":     False,
                "confidence_score":     0.92,
                "laws_retrieved":       0,
                "citations":            [],
                "graph_insights":       [],
                "case_law_found":       False,
                "flagged_citations":    [],
                "repealed_warnings":    evaluation.get("repealed_laws_cited", []),
                "struck_down_warnings": [],
                "elapsed_seconds":      0,
            }
        }

    except ImportError as e:
        return {
            "response": (
                f"🚨 Missing dependency: {str(e)}\n\n"
                "Run: `pip install PyMuPDF python-docx python-multipart`"
            ),
            "meta": None
        }
    except ValueError as e:
        return {"response": f"🚨 {str(e)}", "meta": None}
    except Exception as e:
        print(f"[API] Upload error: {e}")
        return {"response": f"🚨 Evaluation failed: {str(e)}", "meta": None}


# ─────────────────────────────────────────────────────────────
# INTERVIEW STATE ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/api/draft/state/{session_id}")
async def get_draft_state(session_id: str):
    state = get_interview_state(session_id)
    return {
        "state":          state.state,
        "doc_type":       state.doc_type,
        "progress_pct":   state.progress_pct,
        "missing_fields": state.missing_fields,
        "is_active":      state.is_active,
    }


@app.delete("/api/draft/state/{session_id}")
async def cancel_draft(session_id: str):
    state = get_interview_state(session_id)
    state.reset()
    if TRIAGE_STATE_AVAILABLE:
        reset_triage_state(session_id)
    return {"status": "cancelled", "session_id": session_id}


# ─────────────────────────────────────────────────────────────
# HISTORY ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/api/history/{session_id}")
async def get_history_endpoint(session_id: str):
    history = get_session_history(session_id)
    return {"session_id": session_id, "turns": len(history), "history": history}


@app.delete("/api/history/{session_id}")
async def clear_history_endpoint(session_id: str):
    from pipeline_orchestrator import CONVERSATION_MEMORY
    from interview_state import INTERVIEW_STATES
    if session_id in CONVERSATION_MEMORY:
        CONVERSATION_MEMORY[session_id] = []
    if session_id in INTERVIEW_STATES:
        INTERVIEW_STATES[session_id].reset()
    if TRIAGE_STATE_AVAILABLE:
        reset_triage_state(session_id)
    SESSION_DOCUMENTS.pop(session_id, None)
    return {"status": "cleared", "session_id": session_id}


# ─────────────────────────────────────────────────────────────
# DOCUMENT DOWNLOAD ENDPOINT
# ─────────────────────────────────────────────────────────────

from fastapi.responses import Response

@app.get("/api/document/{session_id}")
async def download_document(session_id: str):
    """Download a previously generated .docx document."""
    docx_bytes = SESSION_DOCUMENTS.get(session_id)
    if docx_bytes is None:
        raise HTTPException(status_code=404, detail="No document found for this session. Generate one first via /api/chat.")
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="legal_document_{session_id}.docx"'
        }
    )


# ─────────────────────────────────────────────────────────────
# AUTH ENDPOINTS
# ─────────────────────────────────────────────────────────────

def _get_user_id(authorization: str = "") -> Optional[int]:
    """Extract user_id from Bearer token."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return decode_token(token)


@app.post("/api/auth/signup")
async def signup(req: AuthRequest):
    if not req.email or not req.password:
        raise HTTPException(400, "Email and password required")
    if not req.username:
        req.username = req.email.split("@")[0]
    existing = get_user_by_email(req.email)
    if existing:
        raise HTTPException(409, "Email already registered")
    hashed = hash_password(req.password)
    user_id = create_user(req.email, req.username, hashed)
    if not user_id:
        raise HTTPException(500, "Failed to create user")
    token = create_token(user_id)
    return AuthResponse(token=token, user_id=user_id, email=req.email, username=req.username)


@app.post("/api/auth/login")
async def login(req: AuthRequest):
    user = get_user_by_email(req.email)
    if not user or not verify_password(req.password, user["password"]):
        raise HTTPException(401, "Invalid email or password")
    token = create_token(user["id"])
    return AuthResponse(token=token, user_id=user["id"], email=user["email"], username=user["username"])


@app.get("/api/auth/me")
async def get_me(fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Invalid or missing token")
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return {"user_id": user["id"], "email": user["email"], "username": user["username"]}


# ─────────────────────────────────────────────────────────────
# CONVERSATION ENDPOINTS
# ─────────────────────────────────────────────────────────────

@app.get("/api/conversations")
async def list_conversations(fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        return {"conversations": [], "total": 0}
    limit = int(fastapi_request.query_params.get("limit", 50))
    offset = int(fastapi_request.query_params.get("offset", 0))
    result = get_conversations(user_id, limit=min(limit, 100), offset=offset)
    return {
        "conversations": [{"id": c["id"], "title": c["title"], "updated_at": c["updated_at"]} for c in result["conversations"]],
        "total": result["total"],
    }


@app.post("/api/conversations")
async def new_conversation(fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    conv_id = create_conversation(user_id, "New Chat")
    return {"conv_id": conv_id}


@app.get("/api/conversations/{conv_id}")
async def get_conversation_endpoint(conv_id: int, fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    conv = get_conversation(conv_id, user_id)
    if not conv:
        raise HTTPException(404, "Conversation not found")
    messages = get_messages(conv_id)
    return {"conversation": conv, "messages": messages}


@app.delete("/api/conversations/{conv_id}")
async def delete_conversation_endpoint(conv_id: int, fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if not delete_conversation(conv_id, user_id):
        raise HTTPException(404, "Conversation not found")
    return {"status": "deleted"}


class MigrateRequest(BaseModel):
    turns: list
    title: Optional[str] = None


@app.post("/api/conversations/migrate")
async def migrate_conversation(req: MigrateRequest, fastapi_request: Request):
    authorization = fastapi_request.headers.get("authorization", "")
    user_id = _get_user_id(authorization)
    if not user_id:
        raise HTTPException(401, "Authentication required")
    if not req.turns:
        raise HTTPException(400, "No turns provided")
    title = (req.title or req.turns[0].get("content", "Migrated Chat")[:60]).strip()
    conv_id = create_conversation(user_id, title)
    if not bulk_import_messages(conv_id, req.turns):
        delete_conversation(conv_id, user_id)
        raise HTTPException(500, "Failed to import messages")
    return {"conv_id": conv_id}


# ─────────────────────────────────────────────────────────────
# TEST ENDPOINTS - New Multi-Agent Architecture
# ─────────────────────────────────────────────────────────────

@app.get("/api/test/agents")
async def test_agents_available():
    """Check if new agents are available"""
    return {
        "agents_available": AGENTS_AVAILABLE,
        "available_modes": ["knowledge", "analysis", "pathfinder", "document", "interviewing", "evaluate", "scrutiny"] if AGENTS_AVAILABLE else []
    }


@app.post("/api/test/researcher")
async def test_researcher_agent(query: str, mode: str = "knowledge"):
    """Test the Researcher Agent"""
    if not AGENTS_AVAILABLE:
        return {"error": "Agents not available", "legacy_fallback": "Use /api/chat instead"}
    
    try:
        result = await manager.run(query, mode=mode)
        return {"agent": "Researcher", "mode": mode, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/test/drafter")
async def test_drafter_agent(query: str, mode: str = "document"):
    """Test the Drafter Agent"""
    if not AGENTS_AVAILABLE:
        return {"error": "Agents not available", "legacy_fallback": "Use /api/chat instead"}
    
    try:
        result = await manager.run(query, mode=mode)
        return {"agent": "Drafter", "mode": mode, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/test/reviewer")
async def test_reviewer_agent(query: str, mode: str = "scrutiny"):
    """Test the Reviewer Agent"""
    if not AGENTS_AVAILABLE:
        return {"error": "Agents not available", "legacy_fallback": "Use /api/upload instead"}
    
    try:
        result = await manager.run(query, mode=mode)
        return {"agent": "Reviewer", "mode": mode, "result": result}
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/test/{mode}")
async def quick_test(mode: str, q: str = "What is Section 138 of NIA?"):
    """Quick test endpoint - /api/test/knowledge?q=Your question"""
    if not AGENTS_AVAILABLE:
        return {"error": "Agents not loaded"}
    
    try:
        result = await manager.run(q, mode=mode)
        return {
            "mode": mode,
            "query": q,
            "response": result.get("response", str(result))
        }
    except Exception as e:
        return {"error": str(e)}


# ─────────────────────────────────────────────────────────────
# RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("⚖️  SaulGPT API v2 — Port 8000")
    print("   /api/chat  /api/upload  /api/draft  /api/history  /api/document/<id>")
    print("=" * 55 + "\n")
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)