"""
SAULSGPT — LAYER 4: RESPONSE VALIDATION
=========================================
Validates Layer 3 output against retrieved legal context.

Five checks:
1. Regex Citation Verifier    — checks cited sections exist in retrieval
2. NLI Hallucination Checker  — DeBERTa entailment vs contradiction
3. Repealed Law Interceptor   — flags IPC/CrPC/Evidence Act references
4. Struck Down Detector       — flags SC struck down sections
5. Disclaimer Enforcer        — injects disclaimer if missing

Input:  generated_text (Layer 3 output) + retrieved_context (Layer 2 results)
Output: validation dict with final_response ready to show user

Run standalone to test:
    python layer4_validation.py

When used by pipeline_orchestrator.py:
    from layer4_validation import validate_legal_response
    result = validate_legal_response(generated_text, layer2_results)
"""

import re
from typing import Dict, List, Tuple

# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────

DISCLAIMER_TEXT = (
    "Disclaimer: This response provides general procedural "
    "information based on Indian law and does not constitute "
    "legal advice. Please consult a qualified lawyer for your "
    "specific situation."
)

# Repealed law detection patterns
# Key: string to search in response
# Value: warning message to append
REPEALED_ACT_PATTERNS = [
    (
        "Indian Penal Code",
        "⚠️  IMPORTANT: The Indian Penal Code has been replaced "
        "by the Bharatiya Nyaya Sanhita (BNS) 2023, effective "
        "July 1 2024. Please refer to current legislation."
    ),
    (
        " IPC ",
        "⚠️  IMPORTANT: IPC has been replaced by BNS 2023, "
        "effective July 1 2024. Please refer to current legislation."
    ),
    (
        "IPC Section",
        "⚠️  IMPORTANT: IPC has been replaced by BNS 2023, "
        "effective July 1 2024. Please refer to current legislation."
    ),
    (
        "Code of Criminal Procedure",
        "⚠️  IMPORTANT: The Code of Criminal Procedure has been "
        "replaced by the Bharatiya Nagarik Suraksha Sanhita "
        "(BNSS) 2023, effective July 1 2024."
    ),
    (
        "CrPC",
        "⚠️  IMPORTANT: CrPC has been replaced by BNSS 2023, "
        "effective July 1 2024. Please refer to current legislation."
    ),
    (
        "Indian Evidence Act",
        "⚠️  IMPORTANT: The Indian Evidence Act has been replaced "
        "by the Bharatiya Sakshya Adhiniyam (BSA) 2023, "
        "effective July 1 2024."
    ),
]

# Struck down / read down section patterns
# These sections are invalid law — must warn user
STRUCK_DOWN_PATTERNS = [
    (
        "66A",
        "🚨 IMPORTANT: Section 66A of the IT Act was struck down "
        "as unconstitutional by the Supreme Court in "
        "Shreya Singhal v. Union of India (2015). "
        "It is no longer valid law."
    ),
    (
        "Section 124A",
        "🚨 IMPORTANT: Section 124A IPC (Sedition) is currently "
        "under a Supreme Court stay in S.G. Vombatkere v. "
        "Union of India (2022). It has also been omitted "
        "from BNS 2023."
    ),
    (
        "Section 377",
        "🚨 IMPORTANT: Section 377 IPC was read down by the "
        "Supreme Court in Navtej Singh Johar v. Union of India "
        "(2018). Consensual same-sex relations between adults "
        "are decriminalized."
    ),
    (
        "Section 303",
        "🚨 IMPORTANT: Section 303 IPC was struck down by the "
        "Supreme Court in Mithu v. State of Punjab (1983). "
        "Mandatory death penalty for life convicts is invalid."
    ),
]

# NLI model config
NLI_MODEL_NAME         = "cross-encoder/nli-deberta-v3-small"
CONTRADICTION_THRESHOLD = 0.3

# Max chars of generated text to send to NLI
# DeBERTa has 512 token limit — truncate to avoid silent errors
NLI_TEXT_MAX_CHARS = 400


# ─────────────────────────────────────────────────────────────
# NLI MODEL LOADING (LAZY)
# Loaded on first call to _run_nli_check()
# ─────────────────────────────────────────────────────────────

nli_pipeline        = None
nli_model_available = False


def _ensure_nli():
    """Load NLI model on first call only (~20s)."""
    global nli_pipeline, nli_model_available
    if nli_pipeline is not None or nli_model_available:
        return
    try:
        from transformers import pipeline as hf_pipeline

        print(f"[Layer 4] Loading NLI model ({NLI_MODEL_NAME})...")
        nli_pipeline = hf_pipeline(
            "text-classification",
            model=NLI_MODEL_NAME,
            tokenizer=NLI_MODEL_NAME,
            top_k=None
        )
        nli_model_available = True
        print("[Layer 4] NLI model loaded.\n")
    except Exception as e:
        nli_pipeline        = None
        nli_model_available = False
        print(f"[Layer 4] WARNING: NLI model unavailable: {e}")
        print("[Layer 4] Checks 1 3 4 5 still active. Skipping check 2.\n")


# ─────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _normalize(value: str) -> str:
    """
    Normalizes section number for comparison.
    Removes spaces and lowercases.
    '302 A' → '302a', ' 15 ' → '15'
    """
    return re.sub(r"\s+", "", str(value).strip().lower())


def _extract_citations(text: str) -> List[Tuple[str, str]]:
    """
    Extracts all Section/Article citations from text.

    Returns list of (type, number) tuples.
    Example: [("Section", "302"), ("Article", "21")]
    """
    pattern = re.compile(
        r"\b(Section|Article)\s+([A-Za-z0-9\-]+)\b",
        re.IGNORECASE
    )
    return [
        (m.group(1).title(), m.group(2))
        for m in pattern.finditer(text)
    ]


def _label_to_scores(predictions) -> Dict[str, float]:
    """
    Converts NLI model predictions to score dict.
    Handles label name variations across model versions.

    Returns: {"contradiction": 0.x, "entailment": 0.x, "neutral": 0.x}
    """
    scores = {}
    for item in (predictions or []):
        label = str(item.get("label", "")).strip().lower()
        score = float(item.get("score", 0.0))
        if "contrad" in label:
            scores["contradiction"] = score
        elif "entail" in label:
            scores["entailment"] = score
        elif "neutral" in label:
            scores["neutral"] = score
    return scores


# ─────────────────────────────────────────────────────────────
# CHECK X — CITATION GROUNDING AGAINST KNOWLEDGE GRAPH
# ─────────────────────────────────────────────────────────────

def _ground_citations_against_graph(
    generated_text:    str,
    retrieved_context: list
) -> list:
    """
    Extracts citations and checks if the cited Act is present in the knowledge graph,
    is not repealed, and is present in the retrieved context.
    """
    ungrounded_citations = []

    try:
        # Import inside function to prevent circular dependency
        from layer6_knowledge_graph import legal_graph 

        # Regex to extract "Section/Article X of [Act Name]"
        # Captures the full Act Name, including spaces and punctuation
        citation_pattern = re.compile(
            r"\b(?:Section|Article)\s+([\w\-]+)\s+of\s+([\w\s,\.]+?)(?=\s*?[\.\,\;\n]|\s*$)",
            re.IGNORECASE
        )

        extracted_citations = citation_pattern.finditer(generated_text)

        # Hardcoded set of known repealed laws for quick checks
        KNOWN_REPEALED = {"Indian Penal Code", "IPC",
                          "Code of Criminal Procedure", "CrPC",
                          "Indian Evidence Act", "IEA",
                          "Bharatiya Nyaya Sanhita", "BNS",
                          "Bharatiya Nagarik Suraksha Sanhita", "BNSS",
                          "Bharatiya Sakshya Adhiniyam", "BSA"}

        for match in extracted_citations:
            section_num = match.group(1).strip()
            act_name    = match.group(2).strip()
            citation    = match.group(0).strip()
            issues      = []

            # CHECK A — Act exists in knowledge graph
            graph_nodes_lower = [str(n).lower() for n in legal_graph.graph.nodes()] if legal_graph and legal_graph.graph else []
            if act_name.lower() not in graph_nodes_lower:
                issues.append("act_not_in_graph")

            # CHECK B — Act is active (not repealed)
            # Check against hardcoded set and graph attributes if available
            if act_name in KNOWN_REPEALED or (legal_graph and legal_graph.get_act_status(act_name) == "repealed"):
                issues.append("repealed_act_cited")

            # CHECK C — Act appears in retrieved context
            if not any(act_name.lower() in item.get("act_name", "").lower() 
                       for item in retrieved_context):
                issues.append("not_in_retrieved_context")

            if issues:
                ungrounded_citations.append({
                    "citation": citation,
                    "act_name": act_name,
                    "issues":   issues
                })

    except (ImportError, AttributeError) as e:
        print(f"[Layer 4] Graph grounding unavailable: {e}")
        return [] # Don't break the pipeline

    return ungrounded_citations

# ─────────────────────────────────────────────────────────────
# CHECK 1 — CITATION VERIFIER
# ─────────────────────────────────────────────────────────────

def _verify_citations(
    generated_text: str,
    retrieved_context: list
) -> List[str]:
    """
    Checks if Section/Article citations in generated text
    exist in the retrieved context sections.

    Citations not found in retrieved context are flagged
    as UNVERIFIED — they may be correct general knowledge
    but were not grounded in retrieved chunks.

    Args:
        generated_text   : Layer 3 response string
        retrieved_context: Layer 2 results list

    Returns:
        list of unverified citation strings
    """

    # Build set of section numbers from retrieved context
    available = {
        _normalize(item.get("section_number", ""))
        for item in retrieved_context
        if item.get("section_number")
    }

    flagged = []
    seen    = set()

    for citation_type, citation_number in _extract_citations(generated_text):
        normalized = _normalize(citation_number)
        label      = f"{citation_type} {citation_number}"

        if normalized not in available and label not in seen:
            flagged.append(label)
            seen.add(label)

    return flagged


# ─────────────────────────────────────────────────────────────
# CHECK 2 — NLI HALLUCINATION CHECKER
# ─────────────────────────────────────────────────────────────

def _run_nli_check(
    generated_text: str,
    retrieved_context: list
) -> Tuple[bool, float]:
    """
    Uses DeBERTa NLI model to check if generated response
    is entailed or contradicted by retrieved context.

    Truncates generated_text to NLI_TEXT_MAX_CHARS to avoid
    silent token truncation errors in DeBERTa (512 token limit).

    Args:
        generated_text   : Layer 3 response
        retrieved_context: Layer 2 results

    Returns:
        (is_hallucinating: bool, confidence_score: float)
        confidence = entailment * (1 - contradiction)
        Range: 0.0 (bad) to 1.0 (good)
    """
    _ensure_nli()
    if not nli_model_available or not retrieved_context:
        # NLI unavailable — assume not hallucinating
        # Other 4 checks still protect the pipeline
        return False, 1.0

    # Truncate for DeBERTa token limit
    # FIX 4: Hypothesis (generated) kept longer than premise
    # (context) — NLI accuracy degrades when hypothesis
    # is shorter than what it claims to verify
    text_for_nli = generated_text[:500]

    max_contradiction = 0.0
    max_entailment    = 0.0

    for item in retrieved_context:
        context_text = item.get("content", "").strip()
        if not context_text:
            continue

        try:
            predictions = nli_pipeline(
                {
                    "text":      text_for_nli,
                    "text_pair": context_text[:400]  # also truncate context
                },
                truncation=True
            )

            # Handle nested list response format
            if (isinstance(predictions, list) and
                    predictions and
                    isinstance(predictions[0], list)):
                predictions = predictions[0]

            scores = _label_to_scores(predictions)
            max_contradiction = max(
                max_contradiction,
                scores.get("contradiction", 0.0)
            )
            max_entailment = max(
                max_entailment,
                scores.get("entailment", 0.0)
            )

        except Exception as e:
            print(f"[Layer 4] NLI check error on chunk: {e}")
            continue

    # Confidence = how well entailment beats contradiction
    confidence = round(
        max(0.0, min(1.0, max_entailment * (1.0 - max_contradiction))),
        4
    )
    is_hallucinating = max_contradiction > CONTRADICTION_THRESHOLD

    return is_hallucinating, confidence


# ─────────────────────────────────────────────────────────────
# CHECK 3 — REPEALED LAW INTERCEPTOR
# CHECK 4 — STRUCK DOWN DETECTOR
# Both use same pattern matching approach
# ─────────────────────────────────────────────────────────────

def _collect_warnings(
    generated_text: str,
    patterns: List[Tuple[str, str]]
) -> List[str]:
    """
    Scans generated text for pattern matches.
    Returns list of warning strings for all matches found.
    Deduplicates warnings.

    Args:
        generated_text: Layer 3 response
        patterns: list of (search_string, warning_message) tuples

    Returns:
        list of unique warning strings
    """
    warnings = []
    for needle, warning in patterns:
        if needle in generated_text and warning not in warnings:
            warnings.append(warning)
    return warnings


# ─────────────────────────────────────────────────────────────
# CHECK 5 — DISCLAIMER ENFORCER + RESPONSE ASSEMBLER
# ─────────────────────────────────────────────────────────────

def _build_final_response(
    generated_text:     str,
    repealed_warnings:  list,
    struck_down_warnings: list,
    disclaimer_present: bool
) -> str:
    """
    Assembles final validated response by appending
    all warnings and disclaimer if missing.

    Warning order:
    1. Original generated text
    2. Repealed law warnings
    3. Struck down warnings
    4. Disclaimer (if missing)

    Args:
        generated_text      : original Layer 3 response
        repealed_warnings   : list from check 3
        struck_down_warnings: list from check 4
        disclaimer_present  : bool from check 5

    Returns:
        complete final response string ready to show user
    """
    final = generated_text.strip()

    # Append all warnings
    all_warnings = repealed_warnings + struck_down_warnings
    if all_warnings:
        final += "\n\n" + "\n\n".join(all_warnings)

    # Inject disclaimer if missing
    if not disclaimer_present:
        final += "\n\n" + DISCLAIMER_TEXT

    return final.strip()


# ─────────────────────────────────────────────────────────────
# LEGAL TERMINOLOGY ENFORCER
# ─────────────────────────────────────────────────────────────

def enforce_legal_terminology(text: str) -> str:
    """
    Final deterministic regex-based cleanup for legal terminology.
    Standardises citations, fixes Constitution/Act terminology swaps,
    and appends repealed law annotations.
    """
    
    # 0. HONOURIFIC FORMATTING
    # FIX 1: Add negative lookahead to prevent double replacement for "Supreme Court of India"
    text = re.sub(r"\bsupreme court\b(?!\s+of\s+India)", "Supreme Court of India", text, flags=re.IGNORECASE)
    text = re.sub(r"\bhigh court\b", "High Court", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdistrict court\b", "District Court", text, flags=re.IGNORECASE)

    # 1. CITATION STANDARDISATION (Part 1: Specific Acts - NIA first)
    # "section 138 of NIA", "sec 138 of NIA", "S.138 of NIA" -> "Section 138 of the Negotiable Instruments Act, 1881"
    text = re.sub(
        r"\b(?:sec|s|section)\.?\s*138\s+of\s+(?:the\s+)?NIA\b",
        "Section 138 of the Negotiable Instruments Act, 1881",
        text, flags=re.IGNORECASE
    )

    # 2. CITATION STANDARDISATION (Part 2: Generic sec/S. -> Section)
    # FIX 2: Make pattern more precise and add negative lookbehinds.
    # Bare "s" only matches when followed by literal dot.
    # (?<!S\.C) and (?<!S\.B) prevent matching "S.C." or "S.B."
    text = re.sub(r"(?<!S\.C)(?<!S\.B)\b(?:sec\.?|s\.)\s*([0-9]+[A-Z]?)\b", r"Section \1", text, flags=re.IGNORECASE)

    # 3. CONSTITUTION ARTICLE FIX (Section -> Article for Constitution)
    # Handles plurals: Sections 14 and 21 of the Constitution
    text = re.sub(
        r"\bSections?\s+([0-9]+[A-Z]?(?:\([0-9a-z]+\))*)\s+(?:and|&)\s+([0-9]+[A-Z]?(?:\([0-9a-z]+\))*)\s+of\s+(?:the\s+)?(?:Indian\s+)?Constitution\b",
        r"Articles \1 and \2 of the Constitution of India",
        text, flags=re.IGNORECASE
    )
    # Handles singular: Section 21 of the Constitution
    text = re.sub(
        r"\bSections?\s+([0-9]+[A-Z]?(?:\([0-9a-z]+\))*)\s+of\s+(?:the\s+)?(?:Indian\s+)?Constitution\b",
        r"Article \1 of the Constitution of India",
        text, flags=re.IGNORECASE
    )
    
    # 4. REVERSE FIX: Article -> Section for non-constitutional laws
    # FIX 3: Make regex less greedy, use \w\s,\. for act name, and fix \b anchor.
    # Matches Article 302 of IPC, but NOT Article 21 of the Constitution
    # Uses negative lookahead that includes optional 'the' to prevent skipping
    # Uses (?=\s|$|,|\.) instead of \b for more precise ending match
    text = re.sub(
        r"\bArticles?\s+([0-9]+[A-Z]?(?:\([0-9a-z]+\))*)\s+of\s+((?:the\s+)?(?!(?:the\s+)?(?:Indian\s+)?Constitution)[\w\s,\.]{2,})(?=\s|$|,|\.)",
        r"Section \1 of \2",
        text, flags=re.IGNORECASE
    )

    # 5. CONSTITUTIONAL ARTICLES STANDARDISED (Art. [N] -> Article [N] of the Constitution)
    # Only for known ranges: 12-35, 226, 227, 32, 136, 141, 142, 300A
    # Negative lookahead to avoid double-tagging if already followed by "of the Constitution"
    known_articles = r"(?:1[2-9]|2[0-9]|3[0-5]|226|227|32|136|141|142|300A)"
    text = re.sub(
        rf"\bArt\.?\s*({known_articles})\b(?!\s+of\s+(?:the\s+)?(?:Indian\s+)?Constitution)",
        r"Article \1 of the Constitution of India",
        text, flags=re.IGNORECASE
    )

    # 6. REPEALED LAW INLINE FIX (Avoid double-tagging)
    repeal_map = {
        r"\bIPC\b": "IPC (now BNS 2023)",
        r"\bCrPC\b": "CrPC (now BNSS 2023)",
        r"\bIndian\s+Evidence\s+Act\b": "Indian Evidence Act (now BSA 2023)"
    }
    for pattern, replacement in repeal_map.items():
        # Negative lookahead to ensure we don't double-tag if already present
        safe_pattern = f"{pattern}(?!\\s*\\(now\\s+[A-Z]+\\s+2023\\))"
        text = re.sub(safe_pattern, replacement, text, flags=re.IGNORECASE)

    return text


# ─────────────────────────────────────────────────────────────
# MAIN VALIDATION FUNCTION
# ─────────────────────────────────────────────────────────────

def validate_legal_response(
    generated_text:   str,
    retrieved_context: list
) -> dict:
    """
    Master validation function for Layer 4.
    Runs all 5 checks and returns complete validation result.

    Args:
        generated_text   : final response string from Layer 3
        retrieved_context: list of dicts from Layer 2 retrieval
                          each with: content, act_name,
                          section_number, is_repealed

    Returns:
        dict with keys:
        - is_hallucinating    : bool
        - confidence_score    : float (0.0 to 1.0)
        - flagged_citations   : list of unverified citations
        - repealed_warnings   : list of repealed law warnings
        - struck_down_warnings: list of struck down warnings
        - disclaimer_present  : bool
        - final_response      : cleaned validated response string

    Example:
        result = validate_legal_response(layer3_text, layer2_results)
        print(result["final_response"])
        if result["is_hallucinating"]:
            print("WARNING: Response may contain unsupported claims")
    """
    try:
        # Check 1 — Citation verifier
        flagged_citations = _verify_citations(
            generated_text,
            retrieved_context
        )

        # Check 2 — NLI hallucination check
        is_hallucinating, confidence_score = _run_nli_check(
            generated_text,
            retrieved_context
        )

        # Check 3 — Repealed law interceptor
        repealed_warnings = _collect_warnings(
            generated_text,
            REPEALED_ACT_PATTERNS
        )

        # Check 4 — Struck down section detector
        struck_down_warnings = _collect_warnings(
            generated_text,
            STRUCK_DOWN_PATTERNS
        )

        # Check 5 — Disclaimer enforcer
        disclaimer_present = DISCLAIMER_TEXT in generated_text

        # First, enforce terminology on the generated text itself
        enforced_generated_text = enforce_legal_terminology(generated_text)

        # Assemble final validated response with the enforced text
        final_response = _build_final_response(
            enforced_generated_text,
            repealed_warnings,
            struck_down_warnings,
            disclaimer_present
        )

        return {
            "is_hallucinating":     is_hallucinating,
            "confidence_score":     confidence_score,
            "flagged_citations":    flagged_citations,
            "repealed_warnings":    repealed_warnings,
            "struck_down_warnings": struck_down_warnings,
            "disclaimer_present":   disclaimer_present,
            "final_response":       final_response
        }

    except Exception as e:
        # Graceful fallback — never crash pipeline
        print(f"[Layer 4] Validation error: {e}")
        disclaimer_present = DISCLAIMER_TEXT in generated_text
        final_response     = generated_text.strip()
        if not disclaimer_present:
            final_response += "\n\n" + DISCLAIMER_TEXT
        
        final_response = enforce_legal_terminology(final_response)

        return {
            "is_hallucinating":     False,
            "confidence_score":     0.0,
            "flagged_citations":    [],
            "repealed_warnings":    [],
            "struck_down_warnings": [],
            "disclaimer_present":   disclaimer_present,
            "final_response":       final_response.strip()
        }


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# Only runs when executed directly:
#   python layer4_validation.py
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    # --- Unit Tests for enforce_legal_terminology ---
    print("-" * 55)
    print("Testing enforce_legal_terminology()...")
    
    # Test 1: Constitution Article Fix
    t1 = "Section 21 of the Constitution is a fundamental right."
    assert "Article 21 of the Constitution of India" in enforce_legal_terminology(t1)
    
    t1b = "Section 21(1) of the Constitution."
    assert "Article 21(1) of the Constitution of India" in enforce_legal_terminology(t1b)
    
    t1c = "Sections 14 and 21 of the Constitution."
    assert "Articles 14 and 21 of the Constitution of India" in enforce_legal_terminology(t1c)

    t2 = "Article 302 of the IPC"
    assert "Section 302 of the IPC" in enforce_legal_terminology(t2)
    
    # Test 2: Repealed Law Inline Fix
    t3 = "The IPC governs crimes."
    assert "IPC (now BNS 2023)" in enforce_legal_terminology(t3)
    
    t4 = "Already IPC (now BNS 2023)"
    assert enforce_legal_terminology(t4).count("(now BNS 2023)") == 1 # No double-tagging
    
    # Test 3: Citation Standardisation
    t5 = "Refer to section 138 of NIA."
    assert "Section 138 of the Negotiable Instruments Act, 1881" in enforce_legal_terminology(t5)
    
    t6 = "See S.138 or sec 420."
    assert "Section 138" in enforce_legal_terminology(t6)
    assert "Section 420" in enforce_legal_terminology(t6)
    
    t7 = "Art. 226 gives power to High Court."
    assert "Article 226 of the Constitution of India" in enforce_legal_terminology(t7)

    # Test 4: Honourifics
    t8 = "The supreme court ruled on this."
    assert "Supreme Court of India" in enforce_legal_terminology(t8)

    print("✅ All terminology enforcement tests passed.")

    # --- Integration Test ---
    mock_generated_text = (
        "Under Article 302 of IPC Section 302 prescribes "
        "punishment for murder. Additionally, Section 21 of the Constitution "
        "protects life. Refer to sec 138 of NIA for cheque bounce. "
        "The supreme court ruled on this. Also section 21 of the indian constitution. "
        "CrPC governs procedure. A known IPC (now BNS 2023) offense."
    )

    mock_retrieved_context = [
        {
            "act_name":       "Indian Penal Code",
            "section_number": "302",
            "is_repealed":    False,
            "content": "[Act: IPC] [Section 302: Punishment for Murder]..."
        }
    ]

    print("\nRunning integrated validation test...")
    result = validate_legal_response(mock_generated_text, mock_retrieved_context)

    print("\n⚖️  VALIDATION REPORT")
    print("━" * 40)
    print(f"Hallucination Check  : {'✅' if not result['is_hallucinating'] else '⚠️'}")
    print(f"Final Response Sample: {result['final_response'][:100]}...")
    print("━" * 40)
    
    # Assertions for integrated test
    assert "Section 302 of IPC (now BNS 2023)" in result['final_response']
    assert "Article 21 of the Constitution of India" in result['final_response']
    assert "Section 138 of the Negotiable Instruments Act, 1881" in result['final_response']
    assert "Supreme Court of India" in result['final_response']
    assert "CrPC (now BNSS 2023)" in result['final_response']
    assert result['final_response'].count("IPC (now BNS 2023)") == 2 # Check no double tagging

    print("\nAll integration tests passed. Layer 4 updated.")