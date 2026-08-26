"""
Agent Manager - Routes queries to the correct agent
=============================================
Decides which agent should handle the user's query.
Replaces pipeline_orchestrator.py
"""

from typing import Optional, Dict, Any, List
import re
from .researcher import ResearcherAgent
from .drafter import DrafterAgent
from .reviewer import ReviewerAgent


# Mode to Agent mapping
MODE_AGENT_MAP = {
    "knowledge": ResearcherAgent(),
    "analysis": ResearcherAgent(),
    "pathfinder": ResearcherAgent(),
    "document": DrafterAgent(),
    "interviewing": DrafterAgent(),
    "evaluate": ReviewerAgent(),
    "scrutiny": ReviewerAgent(),
}


# Keywords for automatic detection
QUERY_PATTERNS = {
    # Researcher patterns
    "legal_query": [
        r"what is (section|article|section)?",
        r"what are my rights",
        r"how do i (file|register|apply)",
        r"what is the procedure",
        r"explain",
        r"tell me about",
        r"legal question",
        r"can i sue",
        r"can i file",
        r"law says",
    ],
    "case_analysis": [
        r"analyze",
        r"my situation",
        r"i have a case",
        r"someone owed me",
        r"my employer",
        r"my landlord",
    ],
    "pathfinder": [
        r"step by step",
        r"procedure to",
        r"how to file",
        r"process",
        r"guide me",
    ],
    
    # Drafter patterns
    "document": [
        r"draft (a |an )?legal",
        r"write (a |an )?notice",
        r"create (a |an )?document",
        r"prepare (a |an )?notice",
        r"legal notice for",
    ],
    "interviewing": [
        r"draft a(.*) for me",
        r"i need to draft",
        r"help me draft",
    ],
    
    # Reviewer patterns  
    "evaluate": [
        r"review (my |the )?contract",
        r"check (my |the )?document",
        r"evaluate",
        r"upload",
    ],
    "scrutiny": [
        r"is this time-barred",
        r"check limitation",
        r"can i still file",
        r"check my case",
    ],
}


class AgentManager:
    """
    Agent Manager - Routes queries to the appropriate agent.
    
    Flow:
    User Query → Manager → Detect Intent → Select Agent → Run Agent → Return Result
    """
    
    def __init__(self):
        self.researcher = ResearcherAgent()
        self.drafter = DrafterAgent()
        self.reviewer = ReviewerAgent()
        self.name = "Manager"
    
    async def run(self, query: str, mode: str = None, file_data: bytes = None, 
               filename: str = None, session_id: str = None,
               conversation_history: List = None,
               triage_context: dict = None) -> Dict[str, Any]:
        """
        Main entry point - routes to correct agent.
        
        Args:
            query: User's input
            mode: Forced mode (optional)
            file_data: Uploaded file (optional)
            filename: File name (optional)
            session_id: Session ID for state
            conversation_history: Chat history
            triage_context: Triage output (role, goal, intake_fields, chosen_path)
        
        Returns:
            Dict with response from appropriate agent
        """
        # Force mode takes priority
        if mode and mode in MODE_AGENT_MAP:
            agent = MODE_AGENT_MAP[mode]
            return await agent.run(
                query=query,
                mode=mode,
                file_data=file_data,
                filename=filename,
                session_id=session_id,
                conversation_history=conversation_history,
                triage_context=triage_context
            )
        
        # Auto-detect mode
        detected_mode = await self.detect_mode(query, conversation_history)
        
        # Get the appropriate agent
        agent = MODE_AGENT_MAP.get(detected_mode)
        
        if not agent:
            # Fallback to researcher
            agent = self.researcher
            detected_mode = "knowledge"
        
        # Run the agent
        return await agent.run(
            query=query,
            mode=detected_mode,
            file_data=file_data,
            filename=filename,
            session_id=session_id,
            conversation_history=conversation_history,
            triage_context=triage_context
        )
    
    async def detect_mode(self, query: str, history: List = None) -> str:
        """
        Detect which mode/agent should handle this query.
        
        Priority:
        1. File upload → evaluate → Reviewer
        2. Draft keywords → document → Drafter
        3. Legal Q&A → knowledge → Researcher
        
        Returns:
            Mode string: knowledge | analysis | pathfinder | document | interviewing | evaluate | scrutiny
        """
        query_lower = query.lower()
        
        # Check for document/draft keywords first
        for pattern in QUERY_PATTERNS["document"]:
            if re.search(pattern, query_lower):
                return "document"
        
        for pattern in QUERY_PATTERNS["interviewing"]:
            if re.search(pattern, query_lower):
                return "interviewing"
        
        # Check for review/evaluation keywords
        for pattern in QUERY_PATTERNS["evaluate"]:
            if re.search(pattern, query_lower):
                return "evaluate"
        
        for pattern in QUERY_PATTERNS["scrutiny"]:
            if re.search(pattern, query_lower):
                return "scrutiny"
        
        # Check for researcher patterns
        for pattern in QUERY_PATTERNS["case_analysis"]:
            if re.search(pattern, query_lower):
                return "analysis"
        
        for pattern in QUERY_PATTERNS["pathfinder"]:
            if re.search(pattern, query_lower):
                return "pathfinder"
        
        for pattern in QUERY_PATTERNS["legal_query"]:
            if re.search(pattern, query_lower):
                return "knowledge"
        
        # Default to knowledge/researcher
        return "knowledge"
    
    async def get_available_modes(self) -> List[Dict[str, str]]:
        """Get list of available modes and their agents"""
        return [
            {"mode": "knowledge", "agent": "Researcher", "description": "Answer legal questions"},
            {"mode": "analysis", "agent": "Researcher", "description": "Analyze your legal situation"},
            {"mode": "pathfinder", "agent": "Researcher", "description": "Step-by-step procedures"},
            {"mode": "document", "agent": "Drafter", "description": "Draft legal documents"},
            {"mode": "interviewing", "agent": "Drafter", "description": "Interactive document creation"},
            {"mode": "evaluate", "agent": "Reviewer", "description": "Evaluate contracts"},
            {"mode": "scrutiny", "agent": "Reviewer", "description": "Check case validity"},
        ]


# Singleton instance
manager = AgentManager()