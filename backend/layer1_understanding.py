"""
SAULSGPT — LAYER 1: QUERY UNDERSTANDING
=========================================
Techniques implemented:
1. Language Detection       — langdetect
2. Intent Classification    — LLM-as-a-Judge via Groq (replaces bart-large-mnli)
3. Named Entity Recognition — spaCy en_core_web_sm
4. Legal Citation Extractor — custom regex
5. Ambiguity Detector       — confidence gap scoring
6. Query Reformulator       — llama3-8b via Groq API

Input:  raw user query (Hindi / English / mixed)
Output: structured UnderstandingResult payload
        consumed by Layer 2 Retrieval

Run standalone to test:
    python layer1_understanding.py

When used by pipeline_orchestrator.py:
    from layer1_understanding import analyze_query
    result = analyze_query(user_query)
"""

import re

# Groq LLM — replaces Ollama + bart-large-mnli
# Get free API key at: console.groq.com → API Keys
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# ─────────────────────────────────────────────────────────────
# LAZY LOADING — heavy models (spaCy ~5s, langchain ~6s, langdetect)
# loaded on first call to analyze_query() instead of at import time
# ─────────────────────────────────────────────────────────────

_nlp = None
_detect = None


def _ensure_nlp():
    global _nlp
    if _nlp is not None:
        return _nlp
    print("Loading spaCy model...")
    import spacy
    _nlp = spacy.load("en_core_web_sm")
    return _nlp


_reformulate_llm = None
_prompt_template = None


def _ensure_llm():
    """LLM for reformulation/condensation (NOT binary gate)."""
    global _reformulate_llm, _prompt_template
    if _reformulate_llm is not None:
        return _reformulate_llm, _prompt_template
    from langchain_groq import ChatGroq
    from langchain_core.prompts import PromptTemplate
    _reformulate_llm = ChatGroq(
        model_name="llama-3.1-8b-instant",
        api_key=GROQ_API_KEY,
        temperature=0.1
    )
    _prompt_template = PromptTemplate
    return _reformulate_llm, _prompt_template


def _ensure_detect():
    global _detect
    if _detect is not None:
        return _detect
    from langdetect import detect
    _detect = detect
    return _detect


# ─────────────────────────────────────────────────────────────
# TECHNIQUE 1 — LEGAL CITATION EXTRACTOR
# Regex pattern catches all Indian law section formats:
# "Section 302", "IPC 41", "BNS 103", "Article 21" etc.
# ─────────────────────────────────────────────────────────────

def extract_legal_citations(text: str) -> list:
    """
    Extracts explicit law section references from query text.
    Handles all common Indian law citation formats.

    Args:
        text: raw user query string

    Returns:
        list of citation strings e.g. ["SECTION 15", "IPC 302"]

    Example:
        extract_legal_citations("under Section 15 of PWA")
        → ["SECTION 15"]
    """
    citations = []
    pattern = r'(?i)(section|sec|article|ipc|bns|crpc|bnss|bsa|hma|pwа)\s*\.?\s*(\d+[a-z]?)'
    matches = re.finditer(pattern, text)
    for match in matches:
        citations.append(match.group(0).upper().strip())
    return citations


# ─────────────────────────────────────────────────────────────
# TECHNIQUE 2 — QUERY REFORMULATOR
# Converts colloquial Hindi/English mixed queries into
# formal legal English optimised for ChromaDB vector search
# ─────────────────────────────────────────────────────────────

def _is_vague_query(query: str) -> bool:
    """Detect short, conversational, or vague queries — HyDE candidates."""
    query_lower = query.strip().lower()
    word_count = len(query_lower.split())
    has_section = bool(re.search(r'(section|sec|article|s\.|art\.)\s*\d+', query_lower))
    has_number = bool(re.search(r'\d+', query_lower))
    is_conversational = any(
        p in query_lower for p in ["what is", "tell me", "explain", "define",
                                    "what's", "how to", "what are", "i want to know"]
    )
    return (word_count < 5 and not has_section) or (is_conversational and not has_number)


def reformulate_query(query: str) -> dict:
    """
    Dual-output query reformulator.
    Returns separate formats for semantic search (ChromaDB) and keyword search (BM25).

    For vague/short queries: generates a HyDE paragraph (semantic) + clean keywords (BM25).
    For specific queries: returns original query as hyde_paragraph + expanded keywords.

    Args:
        query: original user query (any language)

    Returns:
        dict with:
          - hyde_paragraph: str — full sentence(s) for ChromaDB embedding
          - keyword_synonyms: str — clean keywords for BM25 tokenization
    """
    is_vague = _is_vague_query(query)

    if is_vague:
        template = """You are a legal search query optimizer. Output ONLY valid JSON with two fields.

Analyze this user query about Indian law.

If the query is vague or short, generate:
{{
  "hyde_paragraph": "Write one or two plausible textbook sentences that a legal database might contain, answering the user's implied question. Be factual and generic.",
  "keyword_synonyms": "Extract 5-8 key legal search terms from your paragraph, space-separated. No stop words."
}}

CRITICAL:
- hyde_paragraph must read like a real legal textbook excerpt, not a question.
- keyword_synonyms must contain NO stop words (is, a, the, what, of, in, to, etc).
- Keyword order does not matter.

User Query: {query}
JSON:"""
    else:
        template = """You are a legal search query optimizer. Output ONLY valid JSON with two fields.

Rewrite this legal query. For hyde_paragraph, output the original query as-is (no change).
For keyword_synonyms, add legal synonyms alongside the original words, never replace them.

{{
  "hyde_paragraph": "Original query text — no changes.",
  "keyword_synonyms": "original words plus legal synonyms, space-separated"
}}

CRITICAL:
- hyde_paragraph must be the EXACT original query, no changes.
- keyword_synonyms: add legal synonyms alongside, never replace. e.g. "cheque" stays "cheque", not "negotiable instrument". "car" stays "car", not "motor vehicle".
- Remove possessive 's from names before output.
- No stop words in keyword_synonyms.

User Query: {query}
JSON:"""

    llm, PT = _ensure_llm()
    prompt = PT(template=template, input_variables=["query"])
    try:
        raw = llm.invoke(prompt.format(query=query)).content.strip()
        import json
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            parsed = json.loads(m.group(0))
            hyde = parsed.get("hyde_paragraph", "").strip()
            keywords = parsed.get("keyword_synonyms", "").strip()
            return {
                "hyde_paragraph": hyde if hyde else query,
                "keyword_synonyms": keywords if keywords else re.sub(r'[^\w\s]', '', query),
            }
    except Exception:
        pass

    # Fallback — return original query for both
    return {
        "hyde_paragraph": query,
        "keyword_synonyms": re.sub(r'[^\w\s]', '', query),
    }


# ─────────────────────────────────────────────────────────────
# TECHNIQUE 3 — QUERY CONDENSER (True Memory)
# Industry-standard RAG technique
# When conversation history exists, does invisible LLM call
# to rewrite follow-up into complete standalone question
# ─────────────────────────────────────────────────────────────

def condense_with_history(user_query: str, conversation_history: list) -> str:
    """
    Condenses follow-up query with conversation history
    into a single standalone question.

    This is the industry-standard RAG memory technique.
    Works 100% regardless of word count or missing keywords.

    Args:
        user_query           : current raw user input
        conversation_history : list of previous turn dicts
                               each with 'query' and 'response' keys

    Returns:
        standalone condensed question ready for ChromaDB search

    Example:
        Turn 1: "My employer hasn't paid me 3 months"
        Turn 2: "I want to drag them to court"
        → "What is the legal procedure to file a court case
           against an employer for 3 months of unpaid wages?"

    If no history or first turn → returns original query unchanged
    """
    if not conversation_history:
        return user_query

    # Build conversation summary for LLM
    # Only use last 3 turns to keep prompt short
    recent = conversation_history[-3:]
    history_text = ""
    for turn in recent:
        history_text += f"User: {turn.get('query', '')}\n"
        history_text += f"AI: {turn.get('response', '')[:200]}...\n\n"

    condense_template = """Given the following conversation history and a follow-up question,
rewrite the follow-up question to be a complete standalone question
that captures the full context needed to search a legal database.

RULES:
- Preserve exact nouns, numbers, and key phrases from both history and follow-up.
- DO NOT replace everyday words with legal jargon.
- Output ONLY the rewritten standalone question. Nothing else.
- If the follow-up is already standalone and unrelated to history, return it unchanged.

Conversation History:
{history}
Follow-up Question: {question}
Standalone Question:"""

    try:
        llm, PT = _ensure_llm()
        prompt = PT(
            template=condense_template,
            input_variables=["history", "question"]
        )
        condensed = llm.invoke(
            prompt.format(history=history_text, question=user_query)
        ).content.strip()
        print(f"[Layer 1] 🧠 Query condensed: {condensed[:80]}...")
        return condensed
    except Exception as e:
        print(f"[Layer 1] Condenser failed: {e} — using original query")
        return user_query


# ─────────────────────────────────────────────────────────────
# MAIN FUNCTION — analyze_query
# Runs all 6 techniques in sequence
# Returns structured payload for Layer 2
# ─────────────────────────────────────────────────────────────

def analyze_query(user_query: str, conversation_history: list = None) -> dict:
    """
    Master function for Layer 1 Query Understanding.
    Runs all 6 techniques and returns structured payload.

    Args:
        user_query: raw input from user (any language)

    Returns:
        dict with all understanding fields consumed by Layer 2

    Example:
        analyze_query("Mere malik ne salary nahi di Section 15")
        → {
            original_query: "...",
            language: "hi",
            domain: "labour",
            is_ambiguous: False,
            ambiguity_reason: "",
            named_entities: [...],
            explicit_citations: ["SECTION 15"],
            search_optimized_query: "Employer withheld wages..."
          }
    """

    # ── Step 0: Query Condensing (if history provided) ──
    # Runs BEFORE language detection
    # Rewrites follow-up into complete standalone question
    # Fixes "give me in simple words" style follow-up failures
    if conversation_history:
        print("[0/5] Condensing query with conversation history...")
        user_query = condense_with_history(user_query, conversation_history)

    # ── Step 1: Language Detection ──
    print("[1/5] Detecting language...")
    try:
        lang = detect(user_query)
    except Exception:
        # langdetect fails on very short queries
        # default to unknown and continue
        lang = "unknown"

    # ── Step 2a: Fast keyword-based non-legal pre-check ──
    # Catches obvious non-legal queries without waiting for LLM
    query_lower = user_query.strip().lower()
    NON_LEGAL_PATTERNS = [
        "weather", "cook", "recipe", "sport", "cricket", "football",
        "hello", "hi ", "hey", "how are you", "what's up", "good morning",
        "good evening", "good night", "thank you", "thanks", "bye",
        "tell me a joke", "joke", "sing", "dance", "movie", "song",
        "game", "play", "eat", "food", "drink", "music", "art",
        "how old", "how tall", "capital of", "population",
    ]
    is_non_legal_keyword = any(p in query_lower for p in NON_LEGAL_PATTERNS)

    # ── Step 2b: Classification ──
    # Non-legal queries are caught in api_server.py (binary gate) before
    # reaching the pipeline. By the time we get here, it's always legal.
    # Hardcoded values — no LLM call needed.
    print("[2/5] Classification: hardcoded legal (gate handled upstream)")

    is_non_legal = True if is_non_legal_keyword else False
    web_fallback_recommended = False

    # BOUNCER PERMANENTLY DISABLED
    # is_ambiguous always False — Layer 3 + 5 handle unclear queries
    is_ambiguous = False
    ambiguity_reason = "" 

    # ── Step 3: Named Entity Recognition ──
    print("[3/5] Extracting named entities...")
    import spacy
    nlp = _ensure_nlp()
    doc = nlp(user_query)
    named_entities = [
        {
            "text": ent.text,
            "label": ent.label_,
            "description": spacy.explain(ent.label_)
        }
        for ent in doc.ents
    ]

    # ── Step 4: Legal Citation Extraction ──
    print("[4/5] Extracting legal citations...")
    explicit_citations = extract_legal_citations(user_query)

    # ── Step 5: Query Reformulation (dual-output: HyDE + Keywords) ──
    print("[5/5] Reformulating query for vector search...")
    reformulated = reformulate_query(user_query)
    hyde_paragraph = reformulated.get("hyde_paragraph", user_query)
    keyword_synonyms = reformulated.get("keyword_synonyms", user_query)
    # search_optimized_query kept for backward compat — uses hyde_paragraph
    search_optimized_query = hyde_paragraph

    # ── Return Structured Payload ──
    # This dict is the INPUT to Layer 2 Retrieval
    return {
        "original_query":         user_query,
        "language":               lang,
        "domain":                 "legal",
        "is_ambiguous":           is_ambiguous,
        "ambiguity_reason":       ambiguity_reason,
        "is_non_legal":           is_non_legal,
        "web_fallback_recommended": web_fallback_recommended,
        "named_entities":         named_entities,
        "explicit_citations":     explicit_citations,
        "search_optimized_query": search_optimized_query,
        "hyde_paragraph":         hyde_paragraph,
        "keyword_synonyms":       keyword_synonyms,
    }


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# This block only runs when file is executed directly:
#   python layer1_understanding.py
#
# When imported by pipeline_orchestrator.py
# this block is SKIPPED automatically
# Only analyze_query() function is used
#
# The test query is hardcoded intentionally —
# it covers Hindi + English mixed language,
# an explicit section citation (Section 15),
# and a real Indian labour law scenario
# which tests all 6 techniques at once
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    test_query = (
        "Mere malik ne 2 mahine se salary nahi di, "
        "what should I do under Section 15 of "
        "Payment of Wages Act?"
    )

    print(f"User Input: '{test_query}'\n")

    analysis = analyze_query(test_query)

    print("\n" + "=" * 50)
    print("LAYER 1 — FINAL UNDERSTANDING PAYLOAD")
    print("=" * 50)
    for key, value in analysis.items():
        print(f"{key.upper()}: {value}")
    print("=" * 50)
    print("\nLayer 1 complete. Payload ready for Layer 2.\n")