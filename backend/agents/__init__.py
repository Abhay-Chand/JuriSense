"""
Agents Package
==============
Multi-agent architecture for SaulGPT legal assistant.

Usage:
    from backend.agents import researcher, drafter, reviewer, manager
    
    result = await researcher.run("What is Section 138 of NIA?")
"""

from .llm_client import (
    researcher,
    drafter,
    reviewer,
    triage,
    get_researcher_llm,
    get_drafter_llm,
    get_reviewer_llm,
    get_triage_llm,
    RESEARCHER_MODEL,
    DRAFTER_MODEL,
    REVIEWER_MODEL,
    TRIAGE_MODEL
)

# Import agents
from .researcher import ResearcherAgent
from .drafter import DrafterAgent
from .reviewer import ReviewerAgent
from .triage import TriageAgent
from .manager import AgentManager

__all__ = [
    # LLM instances
    "researcher",
    "drafter",
    "reviewer",
    "triage",
    # Agent classes
    "ResearcherAgent",
    "DrafterAgent",
    "ReviewerAgent",
    "TriageAgent",
    "AgentManager",
    # Model names
    "RESEARCHER_MODEL",
    "DRAFTER_MODEL",
    "REVIEWER_MODEL",
    "TRIAGE_MODEL",
]