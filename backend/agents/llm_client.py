"""
LLM Client - Single source for all Language Models
===============================================
All agents import from here. No more repeated LLM initialization.
"""

from langchain_groq import ChatGroq
import os

# Load .env from project root (two levels up from agents/)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set. Create a .env file in the project root with GROQ_API_KEY=your_key")

# ============================================================
# AVAILABLE MODELS
# ============================================================

# Fast, good for Q&A and simple tasks
RESEARCHER_MODEL = "mixtral-8x7b-32768"

# Large context (128K), best for document creation
DRAFTER_MODEL = "llama-3.1-8b-instant"

# Fast + accurate for reviews and validation
REVIEWER_MODEL = "llama-3.1-8b-instant"

# Lightweight model for triage/strategy calls
TRIAGE_MODEL = "llama-3.1-8b-instant"

# ============================================================
# LLM INSTANCES
# ============================================================

def get_researcher_llm():
    """Researcher Agent - Legal Q&A, case analysis, procedures"""
    return ChatGroq(
        model=RESEARCHER_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.3,
        max_completion_tokens=4096
    )

def get_drafter_llm():
    """Drafter Agent - Legal documents, notices, FIRs"""
    return ChatGroq(
        model=DRAFTER_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.2,
        max_completion_tokens=8192
    )

def get_reviewer_llm():
    """Reviewer Agent - Contract review, validation, scrutiny"""
    return ChatGroq(
        model=REVIEWER_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.1,
        max_completion_tokens=4096
    )

def get_triage_llm():
    """Triage Agent - Strategic query analysis, SWOT generation"""
    return ChatGroq(
        model=TRIAGE_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.2,
        max_completion_tokens=2048
    )

def get_binary_gate_llm():
    """Binary Gatekeeper - LEGAL/NON-LEGAL classification only"""
    return ChatGroq(
        model=TRIAGE_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.0,
        top_p=0.1,
        max_completion_tokens=512
    )

def get_discovery_llm():
    """Discovery Agent - Empathetic investigation with structured turns"""
    return ChatGroq(
        model=TRIAGE_MODEL,
        api_key=GROQ_API_KEY,
        temperature=0.1,
        max_completion_tokens=2048
    )

# ============================================================
# EXPORTS - Import these in agents
# ============================================================

# Pre-initialized instances for convenience
researcher = get_researcher_llm()
drafter = get_drafter_llm()
reviewer = get_reviewer_llm()
triage = get_triage_llm()
binary_gate = get_binary_gate_llm()
discovery = get_discovery_llm()