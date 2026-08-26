"""
SAULSGPT — PIPELINE ORCHESTRATOR
===================================
Central controller connecting all 6 layers.

Layer execution order:
Step 0: Memory enrichment (BEFORE Layer 1)
Step 1: Layer 1 — Query Understanding
Step 2: Layer 2 — Hybrid Retrieval
Step 2b: Layer 6 — Knowledge Graph expansion
Step 3: Layer 3 — LLM Reasoning (streaming)
Step 4: Layer 4 — Validation
Step 4b: Layer 5 — External case law (appended after)

New in v2:
→ Interactive Drafter: api_server.py intercepts document
  requests, runs interview_state.py, then calls this
  pipeline with fully-formed query + mode="document"
→ Contract Evaluator: handled entirely in layer6_evaluator.py
  This pipeline is NOT called for /api/upload requests

Run to chat with SaulGPT:
    python legal_pipeline/pipeline_orchestrator.py
"""

import time
import sys

# Import all layers
from layer1_understanding import analyze_query
from layer2_retrieval import retrieve_with_hybrid_logic
from layer3_reasoning import generate_legal_response
from layer4_validation import validate_legal_response, enforce_legal_terminology
from layer5_external import fetch_case_law, fallback_web_search
from layer6_knowledge_graph import legal_graph


# ─────────────────────────────────────────────────────────────
# MULTI-TURN CONVERSATION MEMORY
# ─────────────────────────────────────────────────────────────

CONVERSATION_MEMORY = {}

# Sliding window settings
MAX_VERBATIM_TURNS = 6     # keep this many recent turns verbatim
COLLAPSE_AT_TURNS  = 9     # when history hits this, collapse oldest
SESSION_SUMMARIES  = {}    # per-session running summaries


def get_session_history(session_id: str) -> list:
    """Returns conversation history for a session."""
    if session_id not in CONVERSATION_MEMORY:
        CONVERSATION_MEMORY[session_id] = []
    return CONVERSATION_MEMORY[session_id]


def _extract_facts(text: str) -> list:
    """Extract key facts (dates, amounts, places, names) from text."""
    import re
    facts = []
    # Dates: 1st Jan 2024, Jan 1 2024, 01/01/2024, June 1st, 2026
    date_patterns = [
        r"\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}",
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}",
        r"\d{1,2}/\d{1,2}/\d{4}",
        r"\d{4}-\d{2}-\d{2}",
    ]
    for pat in date_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            facts.append(f"[DATE: {m.group()}]")
    # Amounts: ₹5,00,000, Rs. 50000, INR 1000
    amount_patterns = [
        r"[₹R]s?\.?\s*[\d,]+(?:,\d{3})*(?:\.\d{2})?",
        r"INR\s*[\d,]+(?:,\d{3})*(?:\.\d{2})?",
        r"Rupees?\s+[\d,]+(?:,\d{3})*(?:\.\d{2})?",
    ]
    for pat in amount_patterns:
        for m in re.finditer(pat, text, re.IGNORECASE):
            facts.append(f"[AMOUNT: {m.group()}]")
    # Places: "in X", "at X", "near X" capitalized words
    place_matches = re.findall(r"(?:in|at|near)\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)", text)
    for p in place_matches[:3]:
        facts.append(f"[PLACE: {p}]")
    # Section numbers
    sec_matches = re.findall(r"(?:Section|S\.|Sec\.)\s*\d+[A-Z]?", text, re.IGNORECASE)
    for s in sec_matches[:5]:
        facts.append(f"[LAW: {s}]")
    return list(set(facts))


def _build_summary(history: list) -> str:
    """Build a concise fact-extracting summary of older conversation turns."""
    parts = []
    all_text = ""
    for turn in history[:-MAX_VERBATIM_TURNS]:
        q = turn.get("query", "")
        r = turn.get("response", "")[:200]
        all_text += q + " " + r
        parts.append(f"Q: {q}")
        if r:
            parts.append(f"A: {r}")
    # Extract facts from all older turns combined
    facts = _extract_facts(all_text)
    fact_block = " | ".join(facts) if facts else ""
    if fact_block:
        return f"[FACTS: {fact_block}] | " + " | ".join(parts)
    return " | ".join(parts) if parts else ""


def _collapse_history(session_id: str):
    """
    Collapse oldest turns into a summary entry.
    Preserves the last MAX_VERBATIM_TURNS verbatim.
    """
    history = CONVERSATION_MEMORY.get(session_id, [])
    if len(history) < COLLAPSE_AT_TURNS:
        return

    # Build summary from turns that will be collapsed
    summary_text = _build_summary(history)

    # Merge with any existing summary
    existing = SESSION_SUMMARIES.get(session_id, "")
    if existing:
        summary_text = existing + " | " + summary_text
    SESSION_SUMMARIES[session_id] = summary_text

    # Keep only the last N verbatim turns
    CONVERSATION_MEMORY[session_id] = history[-MAX_VERBATIM_TURNS:]


def get_conversation_context(session_id: str) -> str:
    """
    Returns a combined context: summary (if any) + recent turn list.
    Used by layer1_understanding to inject into the prompt.
    """
    summary = SESSION_SUMMARIES.get(session_id, "")
    history = CONVERSATION_MEMORY.get(session_id, [])
    parts = []
    if summary:
        parts.append(f"[Previous conversation summary: {summary}]")
    for turn in history:
        parts.append(f"[Turn {turn.get('turn', '?')}] User: {turn.get('query', '')} | Assistant: {turn.get('response', '')[:300]}")
    return "\n".join(parts)


def get_history_with_summary(session_id: str) -> list:
    """
    Returns conversation history list with a synthetic summary entry
    prepended (if summary exists), so downstream functions like
    condense_with_history can reference older context.
    """
    history = CONVERSATION_MEMORY.get(session_id, [])
    summary = SESSION_SUMMARIES.get(session_id, "")
    if summary:
        history = [{"turn": 0, "query": "", "response": f"[Summary of earlier turns: {summary}]"}] + history
    return history


def save_turn_to_memory(
    session_id: str,
    user_query: str,
    domain: str,
    mode: str,
    response: str,
    laws_cited: list
):
    """
    Saves completed turn to memory with sliding window summarization.
    When history exceeds COLLAPSE_AT_TURNS, oldest turns are
    collapsed into a running summary, preserving recent context.
    """
    history = get_session_history(session_id)
    history.append({
        "turn":       len(history) + 1,
        "query":      user_query,
        "domain":     domain,
        "mode":       mode,
        "response":   response[:500],
        "laws_cited": laws_cited,
        "timestamp":  time.time()
    })

    # Collapse old turns into summary when history gets long
    if len(history) >= COLLAPSE_AT_TURNS:
        _collapse_history(session_id)
    else:
        CONVERSATION_MEMORY[session_id] = history


# ─────────────────────────────────────────────────────────────
# JSON CoT VERDICT HELPERS
# ─────────────────────────────────────────────────────────────

def _extract_cot_verdict(response: str) -> dict:
    """Extract JSON CoT verdict from the first line of the LLM response."""
    import json
    import re

    first_line = response.split("\n")[0].strip()
    if not first_line:
        return {}

    # Layer 1: pure JSON
    if first_line.startswith("{"):
        try:
            return json.loads(first_line)
        except json.JSONDecodeError:
            pass

    # Layer 2: markdown code block
    m = re.search(r'```(?:json)?\s*(.*?)\s*```', first_line, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    return {}


def _strip_cot_header(response: str) -> str:
    """Remove the JSON CoT verdict first line from the response."""
    parts = response.split("\n", 1)
    if len(parts) > 1:
        first = parts[0].strip()
        if first.startswith("{"):
            return parts[1].strip()
    return response.strip()


# ─────────────────────────────────────────────────────────────
# AUTO MODE DETECTOR
# ─────────────────────────────────────────────────────────────

def detect_mode(layer1_payload: dict, session_id: str = None) -> str:
    """
    Auto detects correct mode from original query keywords.
    Uses original_query NOT enriched_query for mode detection.
    Falls back to previous turn's mode for follow-up questions.
    """
    query = layer1_payload.get("original_query", "").lower()

    DOCUMENT_SIGNALS = [
        "draft", "generate", "write", "create", "template",
        "complaint letter", "legal notice", "affidavit",
        "petition", "application", "banao", "likhna",
        "verified user information", "draft a complete",
        "cheque bounce notice", "employment grievance",
        "fir / police complaint", "rental agreement",
        "response deadline"
    ]
    PATHFINDER_SIGNALS = [
        "step by step", "procedure", "process", "how to file",
        "what steps", "kaise", "kya karna", "where to go",
        "which office", "timeline", "how long", "next step",
        "aage kya", "kya process", "when should", "when do",
    ]
    KNOWLEDGE_SIGNALS = [
        "what is", "define", "explain", "meaning", "kya hai",
        "matlab", "definition", "what does", "tell me about",
        "what are the conditions", "what does section",
        "in which cases", "when to avoid", "when to file",
        "shall one", "must one", "avoid it",
    ]

    if any(s in query for s in DOCUMENT_SIGNALS):
        return "document"
    if any(s in query for s in PATHFINDER_SIGNALS):
        return "pathfinder"
    if any(s in query for s in KNOWLEDGE_SIGNALS):
        return "knowledge"

    # Fallback: reuse previous turn's mode for follow-up questions
    if session_id:
        history = get_session_history(session_id)
        if history:
            prev_mode = history[-1].get("mode", "")
            # Inherit mode from last turn, but never inherit "document"
            if prev_mode and prev_mode != "document":
                print(f"      Inheriting mode from previous turn: {prev_mode}")
                return prev_mode

    return "analysis"


# ─────────────────────────────────────────────────────────────
# MAIN PIPELINE FUNCTION
# ─────────────────────────────────────────────────────────────

def run_saulgpt_pipeline(
    user_query: str,
    session_id: str = "default",
    mode: str = None
) -> dict:
    """
    Executes the complete SaulGPT pipeline end to end.

    Fixed order of operations:
    Step 0: Memory enrichment BEFORE Layer 1
    Step 1: Layer 1 — understand enriched query
    Step 2: Layer 2 — hybrid retrieval
    Step 2b: Layer 6 — knowledge graph expansion
    Step 3: Layer 3 — reasoning + streaming
    Step 4: Layer 4 — validation
    Step 4b: Layer 5 — case law appended to response

    Args:
        user_query : raw user input (Hindi/English/mixed)
        session_id : unique session for conversation memory
                     default = "default" for CLI testing
        mode       : force a specific mode if needed
                     if None auto detects from query

    Returns:
        dict with keys:
        - status               : success / clarification_needed /
                                 no_results / error
        - original_query       : raw user input
        - domain               : legal domain detected
        - mode_used            : which mode was used
        - laws_retrieved       : count of law sections found
        - citations            : list of act+section references
        - response             : final validated answer string
        - graph_insights       : knowledge graph relationships found
        - case_law_found       : bool whether case law was appended
        - is_hallucinating     : bool from Layer 4
        - confidence_score     : float from Layer 4
        - flagged_citations    : unverified citations list
        - repealed_warnings    : repealed law warnings list
        - struck_down_warnings : struck down section warnings
        - elapsed_seconds      : total pipeline time
    """

    print("\n" + "=" * 55)
    print("⚖️   SAULGPT PIPELINE ACTIVATED")
    print("=" * 55)

    start_time = time.time()

    try:

        # ─── STEP 1: LAYER 1 — QUERY UNDERSTANDING & MEMORY ───
        print("[1/5] 🤔 Understanding query (checking memory)...")

        # Pass conversation history directly to Layer 1
        # Layer 1's LLM Query Condenser handles memory intelligently
        # Rewrites follow-ups into complete standalone questions
        # No more word-counting hacks or keyword lists needed
        history = get_session_history(session_id)
        layer1_payload = analyze_query(user_query, conversation_history=history)

        # Restore original raw query for display and memory saving
        layer1_payload["original_query"] = user_query

        domain = layer1_payload.get("domain", "legal")
        web_fallback_hint = layer1_payload.get("web_fallback_recommended", False)
        print(f"      Domain: {domain} | web_fallback_hint: {web_fallback_hint}")

        # Early exit for ambiguous queries
        if layer1_payload.get("is_ambiguous"):
            print("⚠️  Query is ambiguous — requesting clarification")
            clarification = generate_legal_response(
                layer1_payload, [], "analysis",
                conversation_history=history
            )
            return {
                "status":          "clarification_needed",
                "original_query":  user_query,
                "domain":          domain,
                "mode_used":       "none",
                "laws_retrieved":  0,
                "citations":       [],
                "response":        clarification,
                "elapsed_seconds": round(time.time() - start_time, 2)
            }

        # ─── STEP 2: LAYER 2 — HYBRID RETRIEVAL ───

        # Stage 1 — LLM advisory flag
        # Binary gate hint: true if query is outside our 9 acts.
        # Advisory only — if false, threshold and JSON CoT gate still fire.
        if web_fallback_hint:
            print(f"[2/5] 📡 LLM flag: query outside DB scope. Skipping retrieval.")
            layer2_results = []
        else:
            print(f"[2/5] 📚 Searching legal database...")
            # Layer 1 search_optimized_query is now fully self-contained
            # includes condensed memory context from condense_with_history()
            # No need to manually append previous context here
            layer2_results = retrieve_with_hybrid_logic(layer1_payload)

        # ── RELATIVE RELEVANCE THRESHOLD ──
        # Uses score distribution to detect noise vs signal
        # Threshold adapts to query difficulty automatically
        if layer2_results:
            scores = [r.get("relevance_score", 0) for r in layer2_results]
            max_s = max(scores)
            min_s = min(scores)
            spread = max_s - min_s
            # If max is clearly relevant, keep results
            # If all scores are similar & low, it's noise
            if max_s < 0.5 and spread < 0.15:
                print(f"⚠️  DB results appear to be noise (max={max_s:.4f}, "
                      f"spread={spread:.4f}). Triggering web fallback.")
                layer2_results = []

        # ── LAYER 5 AGENTIC FALLBACK ──
        # Triggers when:
        # 1. DB returned zero results, OR
        # 2. DB results were below relevance threshold
        if not layer2_results:
            print("⚠️  No relevant laws found in local database.")
            print("     Triggering Layer 5 Web Fallback...")

            layer2_results = fallback_web_search(
                layer1_payload.get("search_optimized_query", user_query)
            )

            if not layer2_results:
                # Both local DB and web failed — give up gracefully
                return {
                    "status":          "no_results",
                    "original_query":  user_query,
                    "domain":          domain,
                    "mode_used":       "none",
                    "laws_retrieved":  0,
                    "citations":       [],
                    "response": (
                        "I could not find relevant information in my "
                        "local database or on the web for your query. "
                        "Please try rephrasing or consult a lawyer directly.\n\n"
                        "Disclaimer: This response provides general procedural "
                        "information based on Indian law and does not constitute "
                        "legal advice. Please consult a qualified lawyer for "
                        "your specific situation."
                    ),
                    "elapsed_seconds": round(time.time() - start_time, 2)
                }

            print(f"      Web fallback returned {len(layer2_results)} results")

        print(f"      Found {len(layer2_results)} relevant legal sections")

        # Build citations list
        citations = [
            {
                "act_name":       r.get("act_name", ""),
                "section_number": r.get("section_number", ""),
                "is_repealed":    r.get("is_repealed", False)
            }
            for r in layer2_results
        ]

        # ─── STEP 2b: LAYER 6 — KNOWLEDGE GRAPH EXPANSION ───
        # Traverses graph to find related laws
        # Adds insights as structured strings to context
        # Does NOT add fake document chunks (avoids Layer 4 issues)
        graph_insights = []
        if legal_graph is not None:
            print("[2b]  🕸️  Traversing Knowledge Graph...")
            graph_insights = legal_graph.expand_context(layer2_results)
            if graph_insights:
                print(f"      Graph found {len(graph_insights)} relationship(s)")
                for insight in graph_insights[:3]:  # print first 3
                    print(f"      → {insight[:80]}...")
                # Inject graph insights into Layer 1 payload
                # Layer 3 prompt receives this as additional context
                layer1_payload["graph_context"] = "\n".join(graph_insights)
            else:
                print("      No additional relationships found")

        # ─── AUTO MODE DETECTION ───
        selected_mode = mode if mode else detect_mode(layer1_payload, session_id)
        print(f"      Mode auto-detected: {selected_mode}")

        # ─── STEP 3: LAYER 3 — REASONING ───
        # Streams response word by word
        # Do NOT print result["response"] after — causes double print
        print("[3/5] ⚖️  Generating legal response...\n")
        final_answer = generate_legal_response(
            layer1_payload,
            layer2_results,
            selected_mode,
            conversation_history=history
        )

        # ── STAGE 3: JSON CoT VERDICT GATE ──
        # Replaces old phrase-matching defeat detection.
        # LLM outputs JSON on first line: context_sufficient + chunks_are_on_point.
        # If either is false, trigger web search and regenerate.
        cot_verdict = _extract_cot_verdict(final_answer)
        final_answer = _strip_cot_header(final_answer)
        context_fail = not cot_verdict.get("context_sufficient", True)
        on_point_fail = not cot_verdict.get("chunks_are_on_point", True)

        # Skip for non-legal queries — Layer 3 already returned a friendly off-topic response
        if not layer1_payload.get("is_non_legal"):
            already_web = any(
                r.get("act_name") == "Live Web Search"
                for r in layer2_results
            )

            if (context_fail or on_point_fail) and not already_web:
                reason = cot_verdict.get("reasoning", "context insufficient")
                print(f"\n[LLM] CoT verdict: context_sufficient={not context_fail}, "
                      f"chunks_are_on_point={not on_point_fail}")
                print(f"      Reason: {reason[:120]}")
                print("      Triggering Stage 3 Web Fallback...")
                web_results = fallback_web_search(
                    layer1_payload.get("search_optimized_query", user_query)
                )
                if web_results:
                    print("[LLM] 🔄 Regenerating with web context...\n")
                    layer2_results = web_results
                    final_answer = generate_legal_response(
                        layer1_payload,
                        web_results,
                        selected_mode,
                        conversation_history=history
                    )
                    # Parse verdict again on regenerated response
                    final_answer = _strip_cot_header(final_answer)
                    print("\n[LLM] ✅ Regenerated with web fallback results.")

        # ─── STEP 4: LAYER 4 — VALIDATION ───
        # Validates after streaming is complete
        # Appends repealed/struck down warnings + disclaimer
        print("[4/5] 🔍 Validating response...")
        validation = validate_legal_response(
            final_answer,
            layer2_results
        )
        final_answer = validation["final_response"]

        # Apply terminology enforcement as the absolute last step
        final_answer = enforce_legal_terminology(final_answer)

        # Print validation report
        print("\n⚖️  VALIDATION REPORT")
        print("━" * 45)
        hal_status = (
            "⚠️  WARNING — possible unsupported claims"
            if validation["is_hallucinating"]
            else "✅ PASSED"
        )
        print(f"Hallucination Check  : {hal_status}")
        print(f"Confidence Score     : {validation['confidence_score']}")
        cites = validation["flagged_citations"]
        print(f"Unverified Citations : {', '.join(cites) if cites else 'None'}")
        print(f"Repealed Laws        : {len(validation['repealed_warnings'])} warning(s)")
        print(f"Struck Down Laws     : {len(validation['struck_down_warnings'])} warning(s)")
        disc = "Present" if validation["disclaimer_present"] else "Auto-Injected"
        print(f"Disclaimer           : {disc}")
        print("━" * 45)

        # ─── STEP 4b: LAYER 5 — EXTERNAL CASE LAW ───
        # Only for Case Analysis mode
        # Appended AFTER validation — not used for reasoning
        # Avoids polluting LLM context with unverified web data
        case_law_found = False
        if selected_mode == "analysis" and layer2_results:
            print("[5/5] 🌐 Fetching relevant case law...")
            top_result = layer2_results[0]
            case_law = fetch_case_law(
                query       = layer1_payload.get("search_optimized_query", user_query),
                act_name    = top_result.get("act_name", ""),
                section_num = top_result.get("section_number", "")
            )
            if case_law:
                final_answer += case_law
                case_law_found = True
        else:
            print("[5/5] ⏭️  Case law fetch skipped (not analysis mode)")

        elapsed = round(time.time() - start_time, 2)
        print(f"\n⏱️  Pipeline completed in {elapsed}s")

        # Save RAW query to memory — not enriched version
        save_turn_to_memory(
            session_id = session_id,
            user_query = user_query,
            domain     = domain,
            mode       = selected_mode,
            response   = final_answer,
            laws_cited = citations
        )

        return {
            "status":               "success",
            "original_query":       user_query,
            "domain":               domain,
            "mode_used":            selected_mode,
            "laws_retrieved":       len(layer2_results),
            "citations":            citations,
            "response":             final_answer,
            "graph_insights":       graph_insights,
            "case_law_found":       case_law_found,
            "is_hallucinating":     validation["is_hallucinating"],
            "confidence_score":     validation["confidence_score"],
            "flagged_citations":    validation["flagged_citations"],
            "repealed_warnings":    validation["repealed_warnings"],
            "struck_down_warnings": validation["struck_down_warnings"],
            "elapsed_seconds":      elapsed
        }

    except Exception as e:
        elapsed = round(time.time() - start_time, 2)
        print(f"\n🚨 PIPELINE ERROR: {e}")
        return {
            "status":               "error",
            "original_query":       user_query,
            "domain":               "unknown",
            "mode_used":            "none",
            "laws_retrieved":       0,
            "citations":            [],
            "response": (
                "An internal error occurred while processing "
                "your legal query. Please try again.\n\n"
                "Disclaimer: This response provides general "
                "procedural information based on Indian law "
                "and does not constitute legal advice. Please "
                "consult a qualified lawyer for your situation."
            ),
            "graph_insights":       [],
            "case_law_found":       False,
            "is_hallucinating":     False,
            "confidence_score":     0.0,
            "flagged_citations":    [],
            "repealed_warnings":    [],
            "struck_down_warnings": [],
            "elapsed_seconds":      elapsed
        }


# ─────────────────────────────────────────────────────────────
# INTERACTIVE CLI LOOP
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    print("\n" + "#" * 60)
    print(" " * 15 + "⚖️   WELCOME TO SAULGPT ⚖️")
    print(" " * 10 + "Your Local AI Indian Legal Assistant")
    print(" " * 8 + "Powered by Gemma 3 + Indian Law Database")
    print("#" * 60)
    print("\nType your legal question in Hindi or English.")
    print("Type 'history' to see conversation history.")
    print("Type 'clear' to reset conversation memory.")
    print("Type 'exit' or 'quit' to close.\n")

    CLI_SESSION = "cli_session"

    while True:
        try:
            user_input = input("\n👤 YOU: ").strip()

            if user_input.lower() in ["exit", "quit", "q"]:
                print("\nCourt is adjourned. Goodbye! ⚖️")
                sys.exit(0)

            if not user_input:
                continue

            if user_input.lower() == "history":
                history = get_session_history(CLI_SESSION)
                if not history:
                    print("No conversation history yet.")
                else:
                    print("\n--- CONVERSATION HISTORY ---")
                    for turn in history:
                        print(f"Turn {turn['turn']}: {turn['query']}")
                        print(f"  Domain: {turn['domain']} | "
                              f"Mode: {turn['mode']}")
                continue

            if user_input.lower() == "clear":
                CONVERSATION_MEMORY[CLI_SESSION] = []
                print("Conversation memory cleared.")
                continue

            # Run full pipeline
            result = run_saulgpt_pipeline(
                user_query = user_input,
                session_id = CLI_SESSION
            )

            # Layer 3 already streamed response live
            # Layer 4 + 5 printed their own output
            # Only print metadata summary here
            print("\n" + "=" * 55)
            print(
                f"Domain: {result['domain']} | "
                f"Mode: {result['mode_used']} | "
                f"Laws: {result['laws_retrieved']} | "
                f"Graph: {len(result.get('graph_insights', []))} insights | "
                f"Case law: {'Yes' if result.get('case_law_found') else 'No'} | "
                f"Time: {result['elapsed_seconds']}s"
            )

        except KeyboardInterrupt:
            print("\n\nInterrupted. Type 'exit' to quit properly.")
            continue