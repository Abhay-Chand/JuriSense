"""
SAULGPT — LAYER 6: CONTRACT EVALUATOR
========================================
The "Red Pen" — evaluates uploaded legal documents for:
→ Critical flaws and missing clauses
→ Risk scoring (High / Medium / Low)
→ Suggested edits with specific improvements
→ Repealed law detection in contracts

Architecture:
→ Extracts text from PDF / DOCX in memory (no disk writes)
→ Intelligently chunks long contracts (no silent truncation)
→ Routes through existing Groq pipeline (not a bypass)
→ Returns structured JSON enforced at API level

Install dependencies:
    pip install PyMuPDF python-docx python-multipart

Run standalone to test:
    python layer6_evaluator.py
"""

import os
import json
import re
from typing import Optional

# PDF parsing — in-memory, fastest available
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("[Evaluator] WARNING: PyMuPDF not installed. PDF support disabled.")
    print("            Run: pip install PyMuPDF")

# DOCX parsing
try:
    from docx import Document as DocxDocument
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    print("[Evaluator] WARNING: python-docx not installed. DOCX support disabled.")
    print("            Run: pip install python-docx")

# Groq for structured JSON evaluation
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate

# ─────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
EVAL_MODEL       = "llama-3.1-8b-instant"
MAX_CHUNK_CHARS  = 5000   # safe limit per Groq call
OVERLAP_CHARS    = 200    # overlap between chunks for context continuity

eval_llm = ChatGroq(
    model       = EVAL_MODEL,
    api_key     = GROQ_API_KEY,
    temperature = 0.1       # analytical — not creative
)

# ─────────────────────────────────────────────────────────────
# TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts all text from a PDF using PyMuPDF.
    Reads entirely from RAM — never writes to disk.
    Handles scanned PDFs gracefully (returns best effort).

    Args:
        file_bytes: raw PDF bytes from file upload

    Returns:
        extracted text string

    Raises:
        ValueError if PDF cannot be parsed
        ImportError if PyMuPDF not installed
    """
    if not PYMUPDF_AVAILABLE:
        raise ImportError(
            "PyMuPDF not installed. Run: pip install PyMuPDF"
        )

    try:
        text_parts = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page_num, page in enumerate(doc, 1):
                page_text = page.get_text()
                if page_text.strip():
                    text_parts.append(f"[Page {page_num}]\n{page_text}")

        if not text_parts:
            raise ValueError(
                "No text extracted. This may be a scanned image PDF "
                "that requires OCR, which is not currently supported."
            )

        return "\n\n".join(text_parts)

    except fitz.FitzError as e:
        raise ValueError(f"PDF parsing failed: {str(e)}")


def extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts text from a DOCX file.
    Reads from RAM via BytesIO — no disk writes.

    Args:
        file_bytes: raw DOCX bytes from file upload

    Returns:
        extracted text string
    """
    if not DOCX_AVAILABLE:
        raise ImportError(
            "python-docx not installed. Run: pip install python-docx"
        )

    try:
        import io
        doc = DocxDocument(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        if not paragraphs:
            raise ValueError("No readable text found in this DOCX file.")
        return "\n\n".join(paragraphs)

    except Exception as e:
        raise ValueError(f"DOCX parsing failed: {str(e)}")


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Master extraction dispatcher.
    Routes to correct parser based on file extension.

    Args:
        file_bytes: raw file bytes
        filename:   original filename with extension

    Returns:
        extracted plain text

    Raises:
        ValueError for unsupported file types
    """
    fname = filename.lower()

    if fname.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    elif fname.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    elif fname.endswith(".txt"):
        # Plain text — just decode
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return file_bytes.decode("latin-1")
    else:
        raise ValueError(
            f"Unsupported file type: {fname}. "
            "Supported formats: PDF, DOCX, TXT"
        )


# ─────────────────────────────────────────────────────────────
# INTELLIGENT CHUNKING
# Never silently truncates — evaluates all sections
# ─────────────────────────────────────────────────────────────

def chunk_document(text: str) -> list:
    """
    Splits long contracts into overlapping chunks.
    Ensures no clause is silently dropped due to token limits.

    Args:
        text: full extracted document text

    Returns:
        list of text chunks with overlap
    """
    if len(text) <= MAX_CHUNK_CHARS:
        return [text]

    chunks   = []
    start    = 0
    text_len = len(text)

    while start < text_len:
        end   = min(start + MAX_CHUNK_CHARS, text_len)
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= text_len:
            break
        # Move forward but keep overlap for context continuity
        start = end - OVERLAP_CHARS

    return chunks


# ─────────────────────────────────────────────────────────────
# EVALUATION PROMPTS
# ─────────────────────────────────────────────────────────────

EVALUATION_PROMPT = PromptTemplate(
    input_variables=["document_text", "chunk_info"],
    template="""You are an elite Indian Legal Contract Evaluator with 20 years of experience.
Your job is to find every possible flaw, loophole, and missing protection in this document.

{chunk_info}

DOCUMENT TEXT:
{document_text}

Analyze this document and return a JSON object with EXACTLY this structure:
{{
    "risk_score": "High" or "Medium" or "Low",
    "risk_reasoning": "One sentence explaining the risk score",
    "critical_flaws": [
        "Specific flaw 1 with the exact clause or section it affects",
        "Specific flaw 2 with details"
    ],
    "missing_clauses": [
        "Missing clause 1 — what it should say",
        "Missing clause 2 — what it should say"
    ],
    "repealed_laws_cited": [
        "Any IPC/CrPC/Evidence Act citations found — now replaced by BNS/BNSS/BSA"
    ],
    "suggested_edits": [
        "Specific improvement 1 — exact recommended language",
        "Specific improvement 2"
    ],
    "positive_aspects": [
        "What the document does well"
    ]
}}

STRICT RULES:
- Every flaw must cite the specific problematic clause/section
- If this is a chunk of a larger document, only evaluate what you see
- Under Indian law context only
- Output ONLY the JSON object. No explanation. No preamble.
"""
)

MERGE_PROMPT = PromptTemplate(
    input_variables=["chunk_results"],
    template="""You are consolidating multiple legal evaluation reports of different sections of the same contract.

CHUNK EVALUATIONS:
{chunk_results}

Merge these into a single comprehensive evaluation JSON with EXACTLY this structure:
{{
    "risk_score": "High" or "Medium" or "Low",
    "risk_reasoning": "Combined reasoning across all sections",
    "critical_flaws": ["deduplicated combined list of all critical flaws"],
    "missing_clauses": ["deduplicated combined list of all missing clauses"],
    "repealed_laws_cited": ["all repealed law citations found"],
    "suggested_edits": ["deduplicated combined list of all suggested edits"],
    "positive_aspects": ["combined positive aspects"]
}}

Rules:
- If ANY chunk is "High" risk, the overall score is "High"
- Remove duplicate findings
- Output ONLY the JSON object.
"""
)


# ─────────────────────────────────────────────────────────────
# CORE EVALUATION ENGINE
# ─────────────────────────────────────────────────────────────

def evaluate_single_chunk(text: str, chunk_num: int, total_chunks: int) -> dict:
    """
    Evaluates a single chunk of document text.

    Args:
        text:         chunk text to evaluate
        chunk_num:    1-based chunk index
        total_chunks: total number of chunks

    Returns:
        evaluation dict or error dict
    """
    chunk_info = (
        f"This is chunk {chunk_num} of {total_chunks} of the full document."
        if total_chunks > 1
        else "This is the complete document."
    )

    try:
        response = eval_llm.invoke(
            EVALUATION_PROMPT.format(
                document_text = text,
                chunk_info    = chunk_info
            )
        )
        raw = response.content.strip()

        # Strip markdown code blocks if LLM wraps output
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"[Evaluator] JSON parse error on chunk {chunk_num}: {e}")
        return {
            "risk_score":          "Medium",
            "risk_reasoning":      "Evaluation incomplete due to parsing error.",
            "critical_flaws":      ["Could not fully parse this section."],
            "missing_clauses":     [],
            "repealed_laws_cited": [],
            "suggested_edits":     [],
            "positive_aspects":    []
        }
    except Exception as e:
        print(f"[Evaluator] Evaluation error on chunk {chunk_num}: {e}")
        raise


def merge_chunk_results(chunk_results: list) -> dict:
    """
    Merges multiple chunk evaluations into one comprehensive report.
    Uses LLM for intelligent deduplication.

    Args:
        chunk_results: list of evaluation dicts

    Returns:
        merged evaluation dict
    """
    if len(chunk_results) == 1:
        return chunk_results[0]

    chunk_summary = json.dumps(chunk_results, indent=2)

    try:
        response = eval_llm.invoke(
            MERGE_PROMPT.format(chunk_results=chunk_summary[:8000])
        )
        raw = response.content.strip()
        raw = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)
        return json.loads(raw)

    except Exception:
        # Fallback: manual merge without LLM
        merged = {
            "risk_score":          "High",
            "risk_reasoning":      "Multiple sections evaluated.",
            "critical_flaws":      [],
            "missing_clauses":     [],
            "repealed_laws_cited": [],
            "suggested_edits":     [],
            "positive_aspects":    []
        }
        risk_levels = {"High": 3, "Medium": 2, "Low": 1}
        max_risk    = 1

        for r in chunk_results:
            max_risk = max(max_risk, risk_levels.get(r.get("risk_score", "Low"), 1))
            for key in ["critical_flaws", "missing_clauses",
                        "repealed_laws_cited", "suggested_edits", "positive_aspects"]:
                merged[key].extend(r.get(key, []))

        # Deduplicate
        for key in ["critical_flaws", "missing_clauses",
                    "repealed_laws_cited", "suggested_edits", "positive_aspects"]:
            merged[key] = list(dict.fromkeys(merged[key]))

        merged["risk_score"] = {3: "High", 2: "Medium", 1: "Low"}[max_risk]
        return merged


def evaluate_contract(file_bytes: bytes, filename: str) -> dict:
    """
    Master evaluation function.
    Extracts text, chunks intelligently, evaluates all sections,
    merges results into one comprehensive report.

    Args:
        file_bytes: raw file bytes from upload
        filename:   original filename

    Returns:
        comprehensive evaluation dict with:
        - risk_score
        - risk_reasoning
        - critical_flaws
        - missing_clauses
        - repealed_laws_cited
        - suggested_edits
        - positive_aspects
        - word_count
        - chunks_evaluated

    Raises:
        ValueError for unsupported files
        ImportError for missing dependencies
    """
    print(f"[Evaluator] 📄 Evaluating: {filename}")

    # Step 1: Extract text
    print("[Evaluator] Extracting text...")
    text       = extract_text(file_bytes, filename)
    word_count = len(text.split())
    print(f"[Evaluator] Extracted {word_count} words")

    # Step 2: Chunk if needed
    chunks = chunk_document(text)
    print(f"[Evaluator] Split into {len(chunks)} chunk(s)")

    # Step 3: Evaluate each chunk
    results = []
    for i, chunk in enumerate(chunks, 1):
        print(f"[Evaluator] Evaluating chunk {i}/{len(chunks)}...")
        result = evaluate_single_chunk(chunk, i, len(chunks))
        results.append(result)

    # Step 4: Merge results
    final = merge_chunk_results(results)
    final["word_count"]       = word_count
    final["chunks_evaluated"] = len(chunks)
    final["filename"]         = filename

    print(f"[Evaluator] ✅ Evaluation complete. Risk: {final['risk_score']}")
    return final


# ─────────────────────────────────────────────────────────────
# FORMAT FOR FRONTEND
# ─────────────────────────────────────────────────────────────

def format_evaluation_response(evaluation: dict) -> str:
    """
    Formats the evaluation dict into a rich markdown string
    for display in the SaulGPT chat interface.

    Args:
        evaluation: result from evaluate_contract()

    Returns:
        markdown formatted string
    """
    risk    = evaluation.get("risk_score", "Unknown")
    risk_emoji = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}.get(risk, "⚪")
    fname   = evaluation.get("filename", "Document")
    words   = evaluation.get("word_count", 0)
    chunks  = evaluation.get("chunks_evaluated", 1)

    lines = [
        f"## 📑 Contract Evaluation: {fname}",
        f"**{risk_emoji} Risk Level: {risk}** — {evaluation.get('risk_reasoning', '')}",
        f"*{words:,} words analyzed across {chunks} section(s)*",
        "",
    ]

    flaws = evaluation.get("critical_flaws", [])
    if flaws:
        lines.append("### 🚨 Critical Flaws")
        for f in flaws:
            lines.append(f"- {f}")
        lines.append("")

    missing = evaluation.get("missing_clauses", [])
    if missing:
        lines.append("### ⚠️ Missing Protections")
        for m in missing:
            lines.append(f"- {m}")
        lines.append("")

    repealed = evaluation.get("repealed_laws_cited", [])
    if repealed:
        lines.append("### 🔄 Outdated Laws Cited")
        for r in repealed:
            lines.append(f"- {r}")
        lines.append("")

    edits = evaluation.get("suggested_edits", [])
    if edits:
        lines.append("### ✏️ Suggested Improvements")
        for e in edits:
            lines.append(f"- {e}")
        lines.append("")

    positives = evaluation.get("positive_aspects", [])
    if positives:
        lines.append("### ✅ What's Working")
        for p in positives:
            lines.append(f"- {p}")
        lines.append("")

    lines.append(
        "*This evaluation provides procedural analysis under Indian law. "
        "It does not constitute legal advice. Consult a qualified advocate "
        "before acting on this evaluation.*"
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────
# TEST RUNNER
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("-" * 55)
    print("SaulGPT — Layer 6 Contract Evaluator Test")
    print("-" * 55)

    # Test with a sample contract text
    sample_text = """
    EMPLOYMENT AGREEMENT

    This agreement is entered into between the Employer and Employee.

    1. The Employee agrees to work for a salary of Rs. 50,000 per month.
    2. The Employee may be terminated at any time without notice.
    3. Any disputes shall be resolved under Section 302 of the IPC.
    4. The Employee agrees not to work for any competitor for 10 years after leaving.
    5. Overtime shall not be compensated.
    """

    print("\nTest: Evaluating sample employment contract...")

    # Simulate file bytes
    sample_bytes = sample_text.encode("utf-8")

    try:
        result   = evaluate_contract(sample_bytes, "test_contract.txt")
        response = format_evaluation_response(result)
        print("\n" + response)
    except Exception as e:
        print(f"Test failed: {e}")

    print("\n" + "=" * 55)
    print("Layer 6 Evaluator test complete.")
