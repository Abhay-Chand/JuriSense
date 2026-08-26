"""
SAULSGPT — LAYER 3: REASONING ENGINE
=======================================
Techniques:
1. Chain of Thought (CoT) Prompting
   Forces step by step legal reasoning
   Facts → Issues → Law → Outcome

2. Mode Specific Output Formats
   Knowledge  → plain explanation
   Analysis   → structured case analysis
   Document   → formal document draft
   Pathfinder → numbered step by step

3. Ambiguity Handler
   If Layer 1 flagged query as ambiguous
   returns clarifying question instead

4. Repealed Law Warning
   Checks is_repealed flag from Layer 2
   Forces LLM to warn user prominently

5. Knowledge Graph Context  ← NEW
   Reads graph_context from layer1_payload
   Appended as SYSTEM RULES block in prompt
   Tells LLM about law replacements and
   relationships before it generates answer

6. Groq API inference (replaces local Ollama)
   800+ tokens/second vs 3 minutes locally

7. Graceful Fallback
   If LLM fails returns retrieval summary
   Never crashes pipeline

Input:  layer1_payload dict + layer2_results list
Output: final validated legal response string

Run standalone to test:
    python layer3_reasoning.py

When used by pipeline_orchestrator.py:
    from layer3_reasoning import generate_legal_response
    response = generate_legal_response(layer1_payload, layer2_results)
"""

from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

LLM_MODEL   = "llama-3.1-8b-instant"
TEMPERATURE = 0.1

# ─────────────────────────────────────────────────────────────
# ABBREVIATION MAP — Fixes "Keyword Trapped" hallucinations
# Expands _from_db abbreviations to full act names before
# the LLM ever sees them, so it never sees "IEA_from_db"
# and hallucinates "Indian Easements Act" instead of
# "Indian Evidence Act"
# ─────────────────────────────────────────────────────────────

ACT_NAME_MAP = {
    "IEA_from_db":    "Indian Evidence Act, 1872",
    "IPC_from_db":    "Indian Penal Code, 1860 (replaced by BNS 2023)",
    "CRPC_from_db":   "Code of Criminal Procedure, 1973 (replaced by BNSS 2023)",
    "CPC_from_db":    "Code of Civil Procedure, 1908",
    "NIA_from_db":    "Negotiable Instruments Act, 1881",
    "HMA_from_db":    "Hindu Marriage Act, 1955",
    "MVA_from_db":    "Motor Vehicles Act, 1988",
    "IDA_from_db":    "Indian Divorce Act, 1869",
    "indian_penal_code": "Bharatiya Nyaya Sanhita, 2023 (BNS)",
    "indian_constitution": "Constitution of India",
}


def expand_act_name(raw_name: str) -> str:
    """Expand abbreviated act name to full human-readable name."""
    if not raw_name:
        return "Unknown Act"
    clean = raw_name.strip().replace(".json", "")
    return ACT_NAME_MAP.get(clean, raw_name)

import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

print(f"Connecting to Groq API ({LLM_MODEL})...")
llm = ChatGroq(
    model_name=LLM_MODEL,
    api_key=GROQ_API_KEY,
    temperature=TEMPERATURE
)
print("Groq LLM connected.\n")


# ─────────────────────────────────────────────────────────────
# PROMPT TEMPLATES — ONE PER MODE
# ─────────────────────────────────────────────────────────────

KNOWLEDGE_PROMPT = """
You are SaulGPT, an Indian Legal Knowledge Assistant.
Your job is to explain the law clearly based ONLY on the retrieved sections below.

USER QUERY: {user_query}

RETRIEVED LEGAL SECTIONS:
{context}

CHAIN OF THOUGHT — think through these steps before answering:
Step 1: What legal concept is the user asking about?
Step 2: Which retrieved section best explains this concept?
Step 3: What does that section say in simple terms?
Step 4: Are there any important exceptions or conditions?

<strict_rules>
- CRITICAL DIRECTIVE — FACT FIRST: SOURCE blocks are provided. You MUST list the statutory requirements, sections, or facts from the text BEFORE showing empathy or asking follow-up questions. Never summarize away the legal elements. Start with the legal position, then add context. Example: Good — "Under Section 138, you must send a demand notice within 30 days." Bad — "That sounds frustrating. Can you tell me more about what happened?"
- Answer ONLY using the retrieved sections above.
- AMBIGUOUS SECTION RULE: If the same section number (e.g., Section 10) appears from DIFFERENT Acts (e.g., Contract Act AND CPC), and the user did not specify which Act, acknowledge the ambiguity: "Section 10 appears in multiple Acts. Without specifying the Act, here are all relevant provisions:" then list each with its Act name.
- SOURCE PRIORITY RULE: SOURCE blocks from "Live Web Search" have a SOURCE_TYPE field. "primary" = official/code (IndiaCode, IndianKanoon) — authoritative. "commentary" = legal news/blogs (Livelaw, Barandbench) — secondary context. Always cite primary sources first and flag when information comes from secondary commentary.
- If the answer is not in the sections, start by saying: "I do not have enough specific legal context to answer this fully." Then add a friendly note: "Could you share more details about your legal situation? I'm here to help with Indian law questions — just describe what happened and I'll do my best to guide you."
- If any section has STATUS: WARNING REPEALED you MUST say at the very start: "WARNING: This law has been replaced. Please refer to the updated legislation."
- Use plain simple English.
- Cite Act name and Section number for every claim.
- Do NOT give personal legal advice.
- Do NOT use phrases like "you should" or "you must".
- Use procedural language: "the law provides", "under Section X", "the Act states".
- End with: "Disclaimer: This response provides general procedural information based on Indian law and does not constitute legal advice. Please consult a qualified lawyer for your specific situation."
</strict_rules>

SEMANTIC VERIFICATION GATE — Mandatory before you output any section:
1. Read the user's scenario carefully. Identify who the parties are (e.g., landlord-tenant, employer-employee, buyer-seller, neutral stakeholder vs claimant).
2. For EACH retrieved section, check: does the legal relationship described in this statute EXACTLY match the relationship in the user's scenario?
3. If the relationship does NOT match (e.g., the user is a freelancer demanding unpaid wages but the section is about interpleader for neutral third parties holding money), DISCARD that section. Do NOT mention it.
4. If ALL sections are discarded, say: "The retrieved legal sections do not directly apply to your specific situation. Here is general guidance based on legal principles:"
5. If confused between Indian Easements Act and Indian Evidence Act: verify the actual ACT name carefully. "IEA" means "Indian Evidence Act, 1872", NOT "Indian Easements Act".

CRITICAL: DO NOT print, echo, or acknowledge the <strict_rules> or SEMANTIC VERIFICATION GATE or CONTENT VERDICT in your final output. Begin your response immediately with the legal explanation.

═══════════════════════════════
CONTENT VERDICT — Output this JSON on the very first line of your response.
Then write your answer below it, on a new line.
═══════════════════════════════
{
  "context_sufficient": true | false,
  "chunks_are_on_point": true | false,
  "reasoning": "<one sentence: do the chunks contain the specific answer to the user's query?>"
}

context_sufficient: false if the chunks are empty, generic, or lack the specific provisions needed.
chunks_are_on_point: false if the chunks talk about a different topic or legal relationship.
Set BOTH to true only if the chunks directly and specifically answer the user's query.

Example:
{"context_sufficient": true, "chunks_are_on_point": false, "reasoning": "Chunks describe Section 138 procedure but user asks about cheque bounce limitation period which is covered."}

Then write your answer on the next line.
═══════════════════════════════

YOUR EXPLANATION:
"""

ANALYSIS_PROMPT = """
You are SaulGPT, an Indian Legal Case Analyst.
Analyze the user's situation using ONLY the retrieved legal sections below.

USER QUERY: {user_query}
LEGAL DOMAIN: {domain}

RETRIEVED LEGAL SECTIONS:
{context}

CHAIN OF THOUGHT — work through these steps:
Step 1: What are the key facts presented by the user?
Step 2: What legal issues do these facts raise?
Step 3: Which retrieved sections directly apply to these issues?
Step 4: What procedural options or outcomes do those sections describe?
Step 5: What is the realistic procedural outcome?

FORMAT YOUR RESPONSE EXACTLY LIKE THIS:

FACTS:
[Extract the key facts from the user's query]

LEGAL ISSUES:
[List the legal issues these facts raise]

APPLICABLE LAW:
[Cite each relevant section with Act name and Section number]
[Quote the relevant part of each section]

PROCEDURAL OUTCOME:
[Explain what the law says happens in this situation]
[Use procedural language only — no personal advice]

<strict_rules>
- Answer ONLY using the retrieved sections.
- If answer is not in sections, start by saying: "I do not have enough specific legal context to answer this fully." Then add: "Could you share more details about your legal situation? I'm here to help with Indian law questions."
- If any section has STATUS: WARNING REPEALED start with a prominent warning.
- Never say "you should" or "you must do X".
- Always say "the procedure provides" or "under Section X the law states".
- Cite Act and Section for every claim.
- End with: "Disclaimer: This response provides general procedural information based on Indian law and does not constitute legal advice. Please consult a qualified lawyer for your specific situation."
</strict_rules>

SEMANTIC VERIFICATION GATE — Mandatory before you output any section:
1. Read the user's scenario carefully. Identify who the parties are and the legal relationship involved.
2. For EACH retrieved section, check: does the legal relationship described in this statute EXACTLY match the user's scenario?
3. If the relationship does NOT match (e.g., interpleader statute about neutral stakeholders when user is a freelancer demanding their own wages), DISCARD that section. Do NOT mention it.
4. If ALL sections are discarded, say: "The retrieved legal sections do not directly apply to your specific situation. Here is general guidance based on legal principles:"
5. "IEA" is "Indian Evidence Act, 1872", NOT "Indian Easements Act". Verify act names carefully.

CRITICAL: DO NOT print, echo, or acknowledge the <strict_rules> or SEMANTIC VERIFICATION GATE or CONTENT VERDICT in your final output. Begin your response immediately with FACTS:

═══════════════════════════════
CONTENT VERDICT — Output this JSON on the very first line of your response.
Then write your analysis below it, on a new line.
═══════════════════════════════
{
  "context_sufficient": true | false,
  "chunks_are_on_point": true | false,
  "reasoning": "<one sentence>"
}
═══════════════════════════════

YOUR ANALYSIS:
"""

DOCUMENT_PROMPT = """
You are SaulGPT, an Indian Legal Document Drafting Assistant.
Draft a formal legal document based ONLY on the retrieved sections and user details below.

USER REQUEST: {user_query}
LEGAL DOMAIN: {domain}

RETRIEVED LEGAL SECTIONS:
{context}

CHAIN OF THOUGHT:
Step 1: What type of document does the user need?
Step 2: Which retrieved sections govern this type of document?
Step 3: What is the correct format and required elements?
Step 4: Draft the document with correct legal language

FORMAT YOUR RESPONSE AS A FORMAL DOCUMENT:

[DOCUMENT TYPE]
Date: [Date]
To: [Recipient Authority]
From: [Sender — user to fill in]
Subject: [Clear subject line]

[BODY — formal legal language citing relevant sections]

[CLOSING]
[Signature block — user to fill in]

<strict_rules>
- Use formal legal language throughout.
- Cite specific Act and Section numbers in the body.
- Mark all blanks clearly with [brackets] for user to fill.
- If any retrieved law is REPEALED warn before the document.
- Never give personal legal advice in the document body.
- End with: "Disclaimer: This is a draft template only. Please verify all legal citations with a qualified lawyer before submission. This does not constitute legal advice."
</strict_rules>

SEMANTIC VERIFICATION GATE — Mandatory before you draft:
1. Verify the legal relationship in each retrieved section matches the document the user needs.
2. If a section does not match the document type, discard it.
3. "IEA" is "Indian Evidence Act, 1872", NOT "Indian Easements Act". Verify act names carefully.

CRITICAL: DO NOT print, echo, or acknowledge the <strict_rules> or SEMANTIC VERIFICATION GATE or CONTENT VERDICT in your final output. Begin your response immediately with the document.

═══════════════════════════════
CONTENT VERDICT — Output this JSON on the very first line of your response.
Then write your document below it, on a new line.
═══════════════════════════════
{
  "context_sufficient": true | false,
  "chunks_are_on_point": true | false,
  "reasoning": "<one sentence>"
}
═══════════════════════════════

YOUR DOCUMENT DRAFT:
"""

PATHFINDER_PROMPT = """
You are SaulGPT, an Indian Legal Path Finder.
Give clear step by step procedural guidance based ONLY on the retrieved sections below.

USER QUERY: {user_query}
LEGAL DOMAIN: {domain}

RETRIEVED LEGAL SECTIONS:
{context}

CHAIN OF THOUGHT:
Step 1: What legal process is the user asking about?
Step 2: Which retrieved sections describe this process?
Step 3: What is the correct sequence of steps?
Step 4: What documents, timelines, and authorities are involved?

FORMAT YOUR RESPONSE AS NUMBERED STEPS:

LEGAL PROCESS: [Name of the process]

Step 1: [Action to take]
→ Where: [Which office or authority]
→ What to carry: [Documents needed]
→ Timeline: [How long this step takes]

Step 2: [Next action]
→ Where: [Which office or authority]
→ What to carry: [Documents needed]
→ Timeline: [How long this step takes]

[Continue for all steps until process is complete]

IMPORTANT NOTES:
[Any exceptions, limitations, or critical things to know]

<strict_rules>
- Base steps ONLY on retrieved sections.
- Cite the Section number that authorizes each step.
- If any retrieved law is REPEALED warn prominently before steps.
- Use procedural language only — no personal advice.
- If process varies by state note this clearly.
- End with: "Disclaimer: This response provides general procedural information based on Indian law and does not constitute legal advice. Please consult a qualified lawyer for your specific situation."
</strict_rules>

SEMANTIC VERIFICATION GATE — Mandatory before you output steps:
1. Verify the procedure described in each retrieved section matches the process the user asked about.
2. If a section describes a different process (e.g., interpleader vs unpaid wages), discard it.
3. "IEA" is "Indian Evidence Act, 1872", NOT "Indian Easements Act". Verify act names carefully.

CRITICAL: DO NOT print, echo, or acknowledge the <strict_rules> or SEMANTIC VERIFICATION GATE or CONTENT VERDICT in your final output. Begin your response immediately with LEGAL PROCESS:

═══════════════════════════════
CONTENT VERDICT — Output this JSON on the very first line of your response.
Then write your guide below it, on a new line.
═══════════════════════════════
{
  "context_sufficient": true | false,
  "chunks_are_on_point": true | false,
  "reasoning": "<one sentence>"
}
═══════════════════════════════

YOUR STEP BY STEP GUIDE:
"""

MODE_PROMPTS = {
    "knowledge":  KNOWLEDGE_PROMPT,
    "analysis":   ANALYSIS_PROMPT,
    "document":   DOCUMENT_PROMPT,
    "pathfinder": PATHFINDER_PROMPT,
}

DEFAULT_MODE = "analysis"


# ─────────────────────────────────────────────────────────────
# CONTEXT FORMATTER
# ─────────────────────────────────────────────────────────────
# CHANGE FROM ORIGINAL:
# Added layer1_payload parameter
# Reads graph_context from it
# Appends as SYSTEM RULES block after retrieved sections
# This is the only change from the original file
# Everything else is identical
# ─────────────────────────────────────────────────────────────

def format_context(
    layer2_results: list,
    layer1_payload: dict = None   # ← NEW parameter
) -> str:
    """
    Formats Layer 2 retrieval results into readable prompt context.
    Also appends Knowledge Graph insights if available.

    Args:
        layer2_results : list of result dicts from layer2_retrieval
        layer1_payload : dict from Layer 1
                         may contain graph_context from Layer 6
                         if None graph context is simply skipped

    Returns:
        formatted string ready for LLM prompt injection
        includes SYSTEM RULES block if graph_context present

    Example output:
        --- SOURCE 1 ---
        ACT: Payment of Wages Act
        SECTION: 15
        STATUS: Active Law
        TEXT: ...

        --- KNOWLEDGE GRAPH SYSTEM RULES ---
        ⚠️ LAW UPDATE: IPC has been replaced by BNS 2023
        --- END SYSTEM RULES ---
    """
    if not layer2_results:
        return "No relevant legal sections were retrieved."

    # Format retrieved sections — same as original
    blocks = []
    for i, res in enumerate(layer2_results, 1):
        is_repealed = res.get("is_repealed", False)
        status = (
            "⚠️  WARNING: THIS LAW HAS BEEN REPEALED OR REPLACED. "
            "Refer to updated legislation."
            if is_repealed
            else "Active Law"
        )
        source_type = res.get("source_type", "")
        raw_act = res.get('act_name', 'Unknown Act')
        block = (
            f"--- SOURCE {i} ---\n"
            f"ACT: {expand_act_name(raw_act)}\n"
            f"SECTION: {res.get('section_number', 'Unknown')}\n"
            f"STATUS: {status}\n"
            + (f"SOURCE_TYPE: {source_type}\n" if source_type else "")
            + f"TEXT: {res.get('content', '')}\n"
        )
        blocks.append(block)

    formatted = "\n".join(blocks)

    # ── NEW: Append Knowledge Graph insights ──
    # graph_context is set by orchestrator from layer6_knowledge_graph
    # Appended as SYSTEM RULES so LLM treats as verified facts
    # NOT as retrieved legal sections (avoids Layer 4 citation issues)
    # If layer1_payload is None or graph_context is empty
    # this block is silently skipped — no error
    if layer1_payload:
        graph_context = layer1_payload.get("graph_context", "").strip()
        if graph_context:
            formatted += (
                "\n\n--- KNOWLEDGE GRAPH SYSTEM RULES ---\n"
                "The following are verified law relationships and updates.\n"
                "You MUST factor these into your response:\n\n"
                + graph_context
                + "\n--- END SYSTEM RULES ---"
            )
            print("[Layer 3] 🕸️  Knowledge Graph context injected.")

    return formatted


# ─────────────────────────────────────────────────────────────
# AMBIGUITY HANDLER
# ─────────────────────────────────────────────────────────────

def handle_non_legal_query(query: str) -> str:
    """
    Returns a friendly off-topic response when the query is non-legal.
    Encourages the user to ask legal questions within SaulGPT's domain.
    """
    return (
        "Thanks for reaching out! I'm SaulGPT, your Indian Legal Intelligence Assistant. "
        "I specialize in Indian law — criminal, civil, family, labour, "
        "constitutional, and your legal rights.\n\n"
        "Your question seems to be about something outside the legal domain, "
        "and I want to make sure you get the best help possible. "
        "If you have a legal matter you'd like help with — "
        "whether it's understanding a law, analysing a situation, "
        "drafting a document, or figuring out next steps — "
        "I'm here for you. Just tell me about your legal concern!"
    )

def handle_ambiguous_query(layer1_payload: dict) -> str:
    """
    Returns clarifying question when query is too ambiguous.
    Called before LLM reasoning if is_ambiguous is True.
    """
    return (
        "Your query could relate to multiple areas of law. "
        "Could you please clarify:\n\n"
        "→ Are you asking about a general legal concept "
        "(use Knowledge Mode)?\n"
        "→ Did something happen to you personally "
        "(use Case Analysis Mode)?\n"
        "→ Do you need a document drafted "
        "(use Document Generator Mode)?\n"
        "→ Do you need step by step procedure "
        "(use Path Finder Mode)?\n\n"
        "The more specific your question, the better "
        "SaulGPT can help you.\n\n"
        "Disclaimer: This response provides general procedural "
        "information based on Indian law and does not constitute "
        "legal advice. Please consult a qualified lawyer for "
        "your specific situation."
    )


# ─────────────────────────────────────────────────────────────
# MAIN REASONING FUNCTION
# ─────────────────────────────────────────────────────────────

def generate_legal_response(
    layer1_payload: dict,
    layer2_results: list,
    mode: str = None,
    triage_context: dict = None,
    conversation_history: list = None
) -> str:
    """
    Core Layer 3 function.
    Takes Layer 1 understanding + Layer 2 retrieval results
    and generates a structured legal response using local LLM.

    Args:
        layer1_payload: dict from layer1_understanding.analyze_query()
                        must contain: original_query, domain,
                        is_ambiguous, ambiguity_reason
                        may contain: graph_context (from Layer 6)
        layer2_results: list of dicts from layer2_retrieval
                        must contain: act_name, section_number,
                        is_repealed, content
        mode:           one of knowledge/analysis/document/pathfinder
                        if None defaults to analysis
        triage_context: optional dict from Triage Agent
                        contains role, goal, chosen_path, intake_fields
        conversation_history: optional list of previous turn dicts
                        each dict: {"role": str, "content": str, ...}

    Returns:
        final legal response string ready for Layer 4 validation
    """

    original_query = layer1_payload.get("original_query", "")
    domain         = layer1_payload.get("domain", "legal")
    is_ambiguous   = layer1_payload.get("is_ambiguous", False)

    # Handle non-legal queries with a friendly off-topic response
    # This bypasses LLM entirely — no tokens wasted
    if layer1_payload.get("is_non_legal"):
        print("[Layer 3] Non-legal query detected. Returning friendly off-topic response.")
        return handle_non_legal_query(original_query)

    # Handle ambiguous queries first
    if is_ambiguous:
        print("[Layer 3] Query flagged as ambiguous. Returning clarification.")
        return handle_ambiguous_query(layer1_payload)

    # Select correct prompt template
    selected_mode   = mode if mode in MODE_PROMPTS else DEFAULT_MODE
    prompt_template = MODE_PROMPTS[selected_mode]
    print(f"[Layer 3] Mode selected: {selected_mode}")

    # Format context — passes layer1_payload so graph_context
    # gets injected into prompt automatically
    print("[Layer 3] Formatting retrieved sections as context...")
    formatted_context = format_context(layer2_results, layer1_payload)

    # ── Inject Conversation History into prompt context ──
    if conversation_history:
        ch_lines = ["\n\n--- PREVIOUS CONVERSATION (for context) ---"]
        for turn in conversation_history:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            # Truncate long assistant responses to avoid bloat
            if role == "assistant" and len(content) > 500:
                content = content[:500] + "..."
            ch_lines.append(f"{role.title()}: {content}")
        ch_lines.append("--- END PREVIOUS CONVERSATION ---\n")
        formatted_context = "\n".join(ch_lines) + "\n" + formatted_context
        print(f"[Layer 3] Conversation history injected ({len(conversation_history)} turns).")

    # ── Inject Triage Context into prompt context ──
    if triage_context:
        tc_lines = ["\n\n--- USER CASE CONTEXT (from Triage) ---"]
        if triage_context.get("role"):
            tc_lines.append(f"User Role: {triage_context['role']}")
        if triage_context.get("goal"):
            tc_lines.append(f"Goal: {triage_context['goal']}")
        if triage_context.get("chosen_path"):
            tc_lines.append(f"Chosen Strategy: {triage_context['chosen_path']}")
        intake = triage_context.get("intake_fields", {})
        for k, v in intake.items():
            if v:
                label = k.replace("_", " ").title()
                tc_lines.append(f"{label}: {v}")
        tc_lines.append("--- END CASE CONTEXT ---\n")
        formatted_context = "\n".join(tc_lines) + "\n" + formatted_context
        print("[Layer 3] Triage context injected into prompt.")

    # Log repealed law warning
    repealed_laws = [
        r.get("act_name") for r in layer2_results
        if r.get("is_repealed", False)
    ]
    if repealed_laws:
        print(f"[Layer 3] WARNING: Repealed laws in context: {repealed_laws}")

    # Build and invoke LLM chain
    print(f"[Layer 3] Generating response with {LLM_MODEL}...")

    prompt = PromptTemplate(
        input_variables=["user_query", "domain", "context"],
        template=prompt_template
    )

    try:
        chain = prompt | llm

        print("\n" + "=" * 40)
        print("🧠 SAULGPT IS TYPING...")
        print("=" * 40 + "\n")

        final_answer = ""
        # .stream() outputs word by word to terminal
        for chunk in chain.stream({
            "user_query": original_query,
            "domain":     domain,
            "context":    formatted_context
        }):
            print(chunk.content, end="", flush=True)
            final_answer += chunk.content

        print("\n\n" + "=" * 40 + "\n")
        return final_answer.strip()

    except Exception as e:
        # Graceful fallback — never crash pipeline
        print(f"[Layer 3] LLM call failed: {e}")
        print("[Layer 3] Falling back to retrieval summary...")

        fallback_lines = [
            "SaulGPT was unable to generate a full response at this time.",
            "Based on retrieved legal sections, the following may be relevant:\n"
        ]
        for res in layer2_results[:3]:
            fallback_lines.append(
                f"• {res.get('act_name')} — "
                f"Section {res.get('section_number')}: "
                f"{res.get('content', '')[:150]}..."
            )
        fallback_lines.append(
            "\nDisclaimer: This response provides general procedural "
            "information based on Indian law and does not constitute "
            "legal advice. Please consult a qualified lawyer for "
            "your specific situation."
        )
        return "\n".join(fallback_lines)


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    mock_layer1 = {
        "original_query": (
            "What are the legal conditions for a valid marriage "
            "regarding age and living spouses under "
            "Section 5 of the Hindu Marriage Act?"
        ),
        "domain":           "family",
        "is_ambiguous":     False,
        "ambiguity_reason": "",
        # Simulated graph_context from layer6_knowledge_graph
        # In production set by orchestrator after Layer 6 runs
        "graph_context": (
            "📖 DEFINITION: Hindu Marriage Act Section 5 requires "
            "reading with Section 11 (void marriages) and "
            "Section 12 (voidable marriages) for complete understanding."
        ),
    }

    mock_layer2 = [
        {
            "act_name":       "Hindu Marriage Act, 1955",
            "section_number": "5",
            "is_repealed":    False,
            "content": (
                "[Act: Hindu Marriage Act, 1955] "
                "[Section 5: Conditions for a Hindu marriage]. "
                "A marriage may be solemnized between any two Hindus "
                "if the following conditions are fulfilled: "
                "(i) neither party has a spouse living at the time "
                "of the marriage; "
                "(iii) the bridegroom has completed the age of "
                "twenty-one years and the bride, the age of "
                "eighteen years at the time of the marriage."
            )
        },
        {
            "act_name":       "Hindu Marriage Act, 1955",
            "section_number": "18",
            "is_repealed":    False,
            "content": (
                "[Act: Hindu Marriage Act, 1955] "
                "[Section 18: Punishment for contravention]. "
                "Every person who procures a marriage in contravention "
                "of conditions in Section 5 shall be punishable with "
                "rigorous imprisonment which may extend to two years "
                "or with fine which may extend to one lakh rupees "
                "or with both."
            )
        }
    ]

    print("-" * 55)
    print("SaulGPT — Layer 3 Reasoning Test")
    print("-" * 55)

    print("\nTesting MODE: analysis (with Knowledge Graph context)")
    response = generate_legal_response(
        mock_layer1,
        mock_layer2,
        mode="analysis"
    )

    print("\n" + "=" * 55)
    print("LAYER 3 — FINAL RESPONSE (analysis mode)")
    print("=" * 55)
    print(response)
    print("=" * 55)
    print("\nLayer 3 complete. Response ready for Layer 4 validation.")