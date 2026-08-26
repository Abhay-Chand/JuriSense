"""
SAULGPT — DYNAMIC DRAFTER (Generative Scoping Agent)
======================================================
Moves from "Static Form" to "Reasoning Agent."

Instead of picking from a hardcoded template list,
the AI reads the user's problem and generates EXACTLY
the right questions for that specific case.

Examples:
  "My neighbor's dog bit me"
  → Asks: Date of incident, Dog owner name, Medical expenses,
          Vaccination status, Witness names

  "My landlord cut electricity without notice"
  → Asks: Landlord name, Property address, Date of cutoff,
          Lease agreement existence, Advance paid

  NOT a generic "Amount / Date / Name" form.

Architecture:
  Static schemas  → fast path for known doc types
  Dynamic scoping → intelligent path for unknown problems
  Hybrid routing  → api_server picks which to use

Caching:
  Results cached per session to avoid repeated LLM calls
  Same problem doesn't generate a second Groq call

Quality checks:
  JSON validated before use
  Field count capped at 7 (user fatigue)
  Fallback to static legal_notice schema if AI fails

Used by:
  api_server.py → detect_and_scope_document()
"""

import os
import re
import json
import hashlib
import traceback
from typing import Optional

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set in environment or .env file")
SCOPING_MODEL = "llama-3.1-8b-instant"   # fast — this is a routing call

scoping_llm = ChatGroq(
    model       = SCOPING_MODEL,
    api_key     = GROQ_API_KEY,
    temperature = 0.1    # analytical — we want consistent JSON
)

# ─────────────────────────────────────────────────────────────
# SCOPING PROMPT
# ─────────────────────────────────────────────────────────────

SCOPING_PROMPT = PromptTemplate(
    input_variables=["user_problem"],
    template="""You are a Senior Indian Legal Analyst specializing in drafting legal notices.

A client has described this problem:
"{user_problem}"

Your task: Identify EXACTLY 5 to 6 specific pieces of information needed to
draft a formal legal notice for THIS SPECIFIC situation.

RULES:
- Questions must be specific to THIS problem, not generic
- Focus on: Names, Dates, Amounts, Specific facts, Incident details
- If the problem involves money: ask for exact amount
- If the problem involves a date: ask for exact date
- If the problem involves a person: ask for their full name
- DO NOT ask generic questions like "What is your problem?"
- DO NOT ask for information already provided in the problem description
- Provide a helpful, realistic example for each field

Return a JSON object with this EXACT structure:
{{
  "document_name": "Type of legal notice (e.g. Demand Notice for Dog Bite Compensation)",
  "fields": [
    {{
      "key": "snake_case_key",
      "label": "Clear question label for the user",
      "example": "A realistic example answer"
    }}
  ]
}}

Output ONLY the JSON object. No explanation. No preamble.
"""
)

# ─────────────────────────────────────────────────────────────
# RESPONSE CACHE
# Prevents repeated LLM calls for same problem
# ─────────────────────────────────────────────────────────────

_SCOPE_CACHE: dict[str, dict] = {}

def _cache_key(problem: str) -> str:
    """Creates a short cache key from the problem text."""
    return hashlib.md5(problem.lower().strip().encode()).hexdigest()[:12]


# ─────────────────────────────────────────────────────────────
# JSON CLEANER
# ─────────────────────────────────────────────────────────────

def _clean_json(raw: str) -> str:
    """
    Strips markdown code fences and extracts JSON from LLM output.
    Handles: ```json ... ```, raw JSON, extra text around JSON.
    """
    raw = raw.strip()
    # Strip code fences
    raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$',          '', raw, flags=re.MULTILINE)
    # Extract JSON object if surrounded by text
    match = re.search(r'\{[\s\S]*\}', raw)
    return match.group(0) if match else raw


# ─────────────────────────────────────────────────────────────
# FIELD VALIDATOR
# ─────────────────────────────────────────────────────────────

def _validate_fields(fields: list) -> list:
    """
    Validates and sanitises the AI-generated field list.

    - Ensures each field has key, label, example
    - Caps at 7 fields (user fatigue threshold)
    - Removes fields with empty labels
    - Sanitizes keys to snake_case

    Args:
        fields: raw list from AI JSON

    Returns:
        validated and cleaned field list
    """
    validated = []
    seen_keys = set()

    for f in fields:
        if not isinstance(f, dict):
            continue

        key     = str(f.get("key", "")).strip().lower()
        label   = str(f.get("label", "")).strip()
        example = str(f.get("example", "")).strip()

        if not key or not label:
            continue

        # Sanitize key to snake_case
        key = re.sub(r'[^a-z0-9_]', '_', key)
        key = re.sub(r'_+', '_', key).strip('_')

        if key in seen_keys:
            continue

        seen_keys.add(key)
        validated.append({
            "key":     key,
            "label":   label,
            "example": example or "Please provide this information"
        })

        if len(validated) >= 7:  # cap at 7
            break

    return validated


# ─────────────────────────────────────────────────────────────
# FALLBACK SCHEMA
# Used when AI fails to generate valid fields
# ─────────────────────────────────────────────────────────────

FALLBACK_SCHEMA = {
    "document_name": "Legal Notice",
    "fields": [
        {"key": "sender_name",    "label": "Your Full Name",              "example": "Ravi Kumar"},
        {"key": "recipient_name", "label": "Recipient's Full Name",       "example": "Mohan Sharma"},
        {"key": "incident_date",  "label": "Date of Incident",            "example": "15 January 2025"},
        {"key": "issue",          "label": "Nature of the Problem",       "example": "Unpaid dues of ₹50,000"},
        {"key": "relief_sought",  "label": "What you are demanding",      "example": "Payment within 15 days"},
    ]
}


# ─────────────────────────────────────────────────────────────
# MAIN SCOPING FUNCTION
# ─────────────────────────────────────────────────────────────

def identify_required_fields(user_problem: str) -> dict:
    """
    Generative Scoping Agent.

    Reads the user's problem and generates a custom list of
    exactly the right questions for THAT specific situation.

    Args:
        user_problem: the user's original query string

    Returns:
        dict with keys:
          document_name : human-readable document type name
          fields        : list of {key, label, example} dicts

    The AI generates contextually appropriate questions:
      "My tenant hasn't paid rent" →
        tenant_name, property_address, unpaid_months,
        monthly_rent, lease_date, advance_paid

      "My employer didn't give me a relieving letter" →
        employee_name, employer_name, last_working_day,
        letter_requested_on, position_held

    NOT generic Name/Date/Amount fields for everything.
    """
    cache_key = _cache_key(user_problem)
    if cache_key in _SCOPE_CACHE:
        print(f"[Scoper] Cache hit for problem: {user_problem[:50]}...")
        return _SCOPE_CACHE[cache_key]

    print(f"[Scoper] 🔍 Analyzing problem to generate custom fields...")

    try:
        response = scoping_llm.invoke(
            SCOPING_PROMPT.format(user_problem=user_problem)
        )
        raw      = response.content.strip()
        cleaned  = _clean_json(raw)
        data     = json.loads(cleaned)

        # Handle both {fields: [...]} and raw [...] formats
        if isinstance(data, list):
            fields       = data
            doc_name     = "Custom Legal Notice"
        elif isinstance(data, dict):
            fields       = data.get("fields", [])
            doc_name     = data.get("document_name", "Custom Legal Notice")
        else:
            raise ValueError("Unexpected JSON structure from scoping LLM")

        # Validate and sanitize
        validated_fields = _validate_fields(fields)

        if len(validated_fields) < 3:
            print(f"[Scoper] Too few valid fields ({len(validated_fields)}). Using fallback.")
            return FALLBACK_SCHEMA

        result = {
            "document_name": doc_name,
            "fields":        validated_fields
        }

        # Cache the result
        _SCOPE_CACHE[cache_key] = result
        print(f"[Scoper] ✅ Generated {len(validated_fields)} custom fields for: {doc_name}")
        return result

    except json.JSONDecodeError as e:
        print(f"[Scoper] JSON parse error: {e}. Using fallback schema.")
        return FALLBACK_SCHEMA

    except Exception as e:
        print(f"[Scoper] Scoping failed: {e}. Using fallback schema.")
        return FALLBACK_SCHEMA


# ─────────────────────────────────────────────────────────────
# PROBLEM CLASSIFIER
# Decides: use static schema OR dynamic scoping
# ─────────────────────────────────────────────────────────────

# Problems that map to known static schemas
# Order matters — first match wins.
# legal_notice must come before rental_agreement because
# "lease agreement expired" should not match rental_agreement
# when the user's intent is a legal notice for eviction.
STATIC_TRIGGERS = {
    "eviction_notice":  [
        "eviction", "evict tenant", "notice for eviction",
        "eviction notice", "tenant not paying rent",
        "tenant has not paid", "tenant hasn't paid",
        "lease agreement expired", "lease expired",
        "tenancy expired", "notice to tenant"
    ],
    "legal_notice":     [
        "legal notice", "send a notice", "formal notice",
        "legal notice for", "notice to recover",
        "demand notice"
    ],
    "cheque_bounce":    [
        "cheque bounce", "cheque returned", "dishonoured cheque",
        "section 138", "insufficient funds", "bounced cheque",
        "cheque was rejected"
    ],
    "fir_complaint":    [
        "fir", "police complaint", "file a complaint to police",
        "lodge a complaint"
    ],
    "rental_agreement": [
        "rental agreement", "lease agreement", "rent agreement",
        "tenancy agreement", "rent deed"
    ],
}

def classify_document_request(query: str) -> tuple[str, bool]:
    """
    Classifies a document request as static or dynamic.

    Returns:
        (doc_type_or_none, is_static)

    If is_static=True  → use DOCUMENT_SCHEMAS[doc_type]
    If is_static=False → use identify_required_fields(query)
    """
    query_lower = query.lower()

    # ── Exclude procedural / informational queries ──
    # If the user is asking "how to file", "procedure", "when do I need",
    # "what is", etc., do NOT treat as a draft request even if
    # a keyword like "fir" or "complaint" appears in the query.
    QUESTION_SIGNALS = [
        "how to", "how do i", "how can i", "procedure",
        "process for", "step by step", "what is", "tell me",
        "when do", "when should", "explain", "meaning",
        "guide me", "information about", "kya hai",
        "kaise", "kya process",
    ]
    is_question = any(s in query_lower for s in QUESTION_SIGNALS)

    if not is_question:
        # Check static triggers first — faster and more reliable
        for doc_type, triggers in STATIC_TRIGGERS.items():
            if any(t in query_lower for t in triggers):
                print(f"[Scoper] Static route → {doc_type}")
                return doc_type, True

    # If query matches both question signals and draft signals,
    # only treat as draft if draft signals outweigh question signals.
    # Check if it's clearly a drafting request
    DRAFT_SIGNALS = [
        "draft", "write a notice", "send a notice", "legal notice",
        "notice to", "complaint letter", "affidavit", "petition",
        "demand notice", "write a letter", "compose a notice",
        "notice for", "notice against"
    ]
    is_draft = any(s in query_lower for s in DRAFT_SIGNALS)

    if is_draft:
        print(f"[Scoper] Dynamic route → generative scoping")
        return None, False   # None = use dynamic scoping

    return None, None   # None, None = not a draft request at all


# ─────────────────────────────────────────────────────────────
# PROMPT INJECTION BUILDER (for dynamic drafts)
# ─────────────────────────────────────────────────────────────

def build_dynamic_injection(document_name: str, collected: dict, fields: list) -> str:
    """
    Builds the complete prompt injection string for Layer 3.
    More forceful than the static version — uses MANDATE language
    to ensure every field appears in the final document.

    Args:
        document_name: type of document being drafted
        collected:     dict of key → user's answer
        fields:        list of field dicts with key/label/example

    Returns:
        formatted injection string for Layer 3 document prompt
    """
    field_map = {f["key"]: f["label"] for f in fields}

    lines = [
        f"DOCUMENT TYPE: {document_name}",
        "",
        "MANDATORY VERIFIED INFORMATION — USE ALL OF THESE:",
        "(Every field below MUST appear explicitly in the final document)",
        "",
    ]

    for key, val in collected.items():
        label = field_map.get(key, key.replace("_", " ").title())
        lines.append(f"  ✓ {label}: {val}")

    lines += [
        "",
        "STRICT DRAFTING MANDATE:",
        "1. Use EVERY piece of information listed above in the document body.",
        "2. Do NOT use [brackets] for any field that has been provided above.",
        "3. The document must be ready to sign and send immediately.",
        "4. Use formal legal language throughout.",
        "5. Cite relevant Indian law sections where applicable.",
        "6. End with a clear demand and response deadline.",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("-" * 55)
    print("SaulGPT — Dynamic Drafter Test")
    print("-" * 55)

    test_problems = [
        "My neighbor's dog bit my child last week and they are refusing to pay medical bills",
        "My employer fired me without notice after 4 years and hasn't given me any settlement",
        "My landlord is threatening to evict me even though I paid all rent on time",
    ]

    for problem in test_problems:
        print(f"\nProblem: '{problem[:60]}...'")
        result = identify_required_fields(problem)
        print(f"Document: {result['document_name']}")
        print("Fields generated:")
        for f in result["fields"]:
            print(f"  [{f['key']}] {f['label']} (e.g. {f['example']})")

    print("\n" + "=" * 55)
    print("Dynamic Drafter test complete.")
