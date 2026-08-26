"""
Drafter Agent - Legal Document Creation
=============================
Handles: Legal notices, FIRs, rental agreements, contracts
Uses: interview_state.py + dynamic_drafter.py as tools
"""

from typing import Optional, Dict, Any, List
from .llm_client import drafter, get_drafter_llm
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompts.drafter import (
    DRAFTER_SYSTEM_PROMPT,
    LEGAL_NOTICE_PROMPT,
    CHEQUE_BOUNCE_NOTICE_PROMPT,
    EMPLOYMENT_NOTICE_PROMPT,
    FIR_COMPLAINT_PROMPT,
    RENTAL_AGREEMENT_PROMPT,
)

# Import existing drafting components as tools
try:
    from interview_state import InterviewState, get_interview_state, detect_document_type
    from dynamic_drafter import identify_required_fields, classify_document_request, build_dynamic_injection
except ImportError:
    InterviewState = None
    get_interview_state = None
    detect_document_type = None
    identify_required_fields = None
    classify_document_request = None


# Document type definitions
DOCUMENT_TYPES = {
    "legal_notice": {
        "name": "Legal Notice",
        "fields": ["sender_name", "sender_address", "recipient_name", "recipient_address", "subject", "details", "demand", "deadline"]
    },
    "cheque_bounce": {
        "name": "Cheque Bounce Notice",
        "fields": ["cheque_number", "cheque_amount", "cheque_date", "bank_name", "reason", "dishonour_date", "demand_amount", "deadline"]
    },
    "employment_notice": {
        "name": "Employment Notice",
        "fields": ["employer_name", "employee_name", "designation", "joining_date", "issue_description", "relief_sought"]
    },
    "fir_complaint": {
        "name": "FIR Complaint Draft",
        "fields": ["complainant_name", "complainant_address", "incident_date", "incident_time", "incident_place", "description", "accused_details", "witness_details"]
    },
    "rental_agreement": {
        "name": "Rental Agreement",
        "fields": ["owner_name", "owner_address", "tenant_name", "tenant_address", "property_address", "rent_amount", "security_deposit", "tenure"]
    }
}


class DrafterAgent:
    """
    Drafter Agent handles:
    - Legal notice creation (document mode)
    - Interactive document drafting (interviewing mode)
    """
    
    def __init__(self):
        self.llm = drafter
        self.name = "Drafter"
        self.capabilities = ["legal_notice", "fir_complaint", "rental_agreement", "employment_notice"]
    
    async def run(self, query: str, mode: str = "document", conversation_history: List = None, session_id: str = None, triage_context: dict = None, **kwargs) -> Dict[str, Any]:
        """
        Main entry point for the agent.
        
        Args:
            query: User's request
            mode: document | interviewing
            conversation_history: Previous messages
            session_id: Session ID for interview state
            triage_context: Triage data (role, goal, intake_fields)
        
        Returns:
            Dict with drafted document or interview questions
        """
        if mode == "interviewing":
            return await self.interview_draft(query, conversation_history, session_id, triage_context=triage_context)
        else:
            return await self.document_draft(query, conversation_history, triage_context=triage_context)
    
    async def document_draft(self, query: str, history: List = None, triage_context: dict = None) -> Dict[str, Any]:
        """Direct document creation (one-shot)"""
        # Detect document type
        if classify_document_request:
            doc_type, is_static = classify_document_request(query)
        else:
            doc_type = self._detect_doc_type(query)
        
        # Get required fields
        if identify_required_fields:
            scope_result = identify_required_fields(query)
            required_fields = scope_result.get("fields", [])
        else:
            required_fields = DOCUMENT_TYPES.get(doc_type, {}).get("fields", [])
        
        # For one-shot drafting, generate directly
        draft_prompt = self._build_draft_prompt(query, doc_type, required_fields, triage_context)
        
        # Generate draft
        response = await self._generate_draft(draft_prompt, doc_type)
        
        return {
            "response": response,
            "document_type": doc_type,
            "mode_used": "document",
            "required_fields": required_fields,
            "interview_complete": True
        }
    
    async def interview_draft(self, query: str, history: List = None, session_id: str = None, triage_context: dict = None) -> Dict[str, Any]:
        """Interactive interview-based document creation"""
        # Get or create interview state
        if get_interview_state and session_id:
            state = get_interview_state(session_id)
            
            if state and state.is_complete:
                return {
                    "response": "Document created successfully",
                    "document_type": state.doc_type,
                    "mode_used": "interviewing",
                    "interview_complete": True
                }
        
        # Detect document type
        if detect_document_type:
            doc_type = detect_document_type(query)
        else:
            doc_type = self._detect_doc_type(query)
        
        # Get required fields
        if identify_required_fields:
            scope_result = identify_required_fields(query)
            required_fields = scope_result.get("fields", [])
        else:
            required_fields = DOCUMENT_TYPES.get(doc_type, {}).get("fields", [])
        
        return {
            "response": f"I need to draft a {DOCUMENT_TYPES.get(doc_type, {}).get('name', 'document')}. Please provide the following information:\n\n" + 
                       "\n".join([f"- {field.replace('_', ' ').title()}" for field in required_fields[:5]]),
            "document_type": doc_type,
            "mode_used": "interviewing",
            "required_fields": required_fields,
            "interview_progress": 0,
            "is_interviewing": True,
            "interview_complete": False
        }
    
    async def _generate_draft(self, prompt: str, doc_type: str) -> str:
        """Generate the actual document"""
        from langchain_core.prompts import PromptTemplate
        from langchain_core.output_parsers import StrOutputParser
        
        template = PromptTemplate.from_template("""
You are a legal document draft generator. Create a proper legal document based on the user's request.

Document Type: {doc_type}

User Request: {prompt}

Create a professional legal document with:
1. Proper heading and format
2. All relevant parties clearly identified
3. Facts and circumstances
4. Legal grounds and references
5. Relief/Demand
6. Verification and signature block

Generate the complete document:
""")
        
        chain = template | self.llm | StrOutputParser()
        
        result = chain.invoke({"doc_type": doc_type, "prompt": prompt})
        return result
    
    def _detect_doc_type(self, query: str) -> str:
        """Detect document type from query"""
        query_lower = query.lower()
        
        if "cheque" in query_lower or "bounce" in query_lower or "dishonour" in query_lower:
            return "cheque_bounce"
        elif "fir" in query_lower or "police" in query_lower or "complaint" in query_lower:
            return "fir_complaint"
        elif "rental" in query_lower or "lease" in query_lower or "rent" in query_lower:
            return "rental_agreement"
        elif "employment" in query_lower or "salary" in query_lower or "job" in query_lower:
            return "employment_notice"
        else:
            return "legal_notice"
    
    def _build_draft_prompt(self, query: str, doc_type: str, fields: List[str], triage_context: dict = None) -> str:
        """Build prompt for draft generation"""
        preamble = ""
        if triage_context:
            tc_lines = ["Case Context from Triage:"]
            if triage_context.get("role"):
                tc_lines.append(f"- User Role: {triage_context['role']}")
            if triage_context.get("goal"):
                tc_lines.append(f"- Goal: {triage_context['goal']}")
            if triage_context.get("chosen_path"):
                tc_lines.append(f"- Strategy: {triage_context['chosen_path']}")
            intake = triage_context.get("intake_fields", {})
            for k, v in intake.items():
                if v:
                    tc_lines.append(f"- {k.replace('_', ' ').title()}: {v}")
            preamble = "\n".join(tc_lines) + "\n\n"
        return f"{preamble}Create a {DOCUMENT_TYPES.get(doc_type, {}).get('name', 'legal document')} based on: {query}"


# Singleton instance
agent = DrafterAgent()