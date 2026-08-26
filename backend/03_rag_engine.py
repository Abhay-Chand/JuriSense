"""
LEGAL GPT - STEP 3: RAG QUERY ENGINE
Connects ChromaDB retrieval to LLM for intelligent legal answers
This is the brain of your Legal GPT
"""

import os
import json
from typing import List, Dict
import chromadb
from chromadb.utils import embedding_functions
from anthropic import Anthropic  # or use openai

# ─────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────
CHROMA_DB_PATH = "./legal_gpt_chromadb"
COLLECTION_NAME = "indian_laws"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# LLM Config — using Claude (swap for OpenAI if preferred)
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "your-api-key-here")
LLM_MODEL = "claude-sonnet-4-20250514"


# ─────────────────────────────────────────
# SYSTEM PROMPT — The Legal GPT Persona
# ─────────────────────────────────────────

LEGAL_GPT_SYSTEM_PROMPT = """You are SaulGPT, an Indian legal procedural information assistant.

YOUR PURPOSE:
Explain Indian legal procedures, definitions, and relevant sections in a neutral, 
informative manner. You help users understand how the law works — not what they 
personally should do.

STRICT RULES:
1. NEVER give personal legal advice or operational instructions
   ❌ "You should arrest him immediately"
   ✅ "Under CrPC Section 41, police are authorized to arrest without warrant in cognizable offences"

2. NEVER tell the user what action to take personally
   ❌ "File an FIR right now"
   ✅ "Under BNSS Section 173, information about a cognizable offence is to be registered as an FIR"

3. ALWAYS explain law neutrally in third-person procedural language
4. ALWAYS cite exact sections and acts
5. ALWAYS note conditions, exceptions, and limitations of each law
6. ALWAYS mention relevant landmark judgments when applicable
7. ALWAYS end with the standard disclaimer
8. When laws conflict, explain both positions neutrally without taking sides

RESPONSE FORMAT:
1. Brief procedural overview
2. Numbered breakdown of applicable laws/sections
3. Conditions and exceptions
4. Relevant case law (if applicable)
5. Relevant Legal Sections (summary list)
6. Disclaimer

DISCLAIMER TO ALWAYS INCLUDE:
"This response provides general procedural information based on Indian law and does 
not constitute legal advice. For specific situations, consultation with a qualified 
legal professional is recommended."
"""


# ─────────────────────────────────────────
# QUERY CLASSIFIER
# ─────────────────────────────────────────

class QueryClassifier:
    """
    Classifies incoming queries to optimize retrieval
    """
    
    CATEGORY_KEYWORDS = {
        'criminal': [
            'murder', 'kill', 'theft', 'steal', 'arrest', 'bail', 'FIR',
            'police', 'crime', 'punishment', 'jail', 'prison', 'assault',
            'rape', 'kidnap', 'fraud', 'cheating', 'IPC', 'BNSS', 'CrPC'
        ],
        'civil': [
            'contract', 'breach', 'damages', 'suit', 'injunction', 'property',
            'evidence', 'witness', 'court', 'appeal', 'decree', 'CPC'
        ],
        'constitutional': [
            'fundamental right', 'article', 'constitution', 'preamble',
            'right to life', 'equality', 'freedom', 'directive', 'amendment',
            'writ', 'habeas corpus', 'mandamus', 'supreme court'
        ],
        'special': [
            'consumer', 'cybercrime', 'internet', 'hacking', 'GST', 'tax',
            'IT act', 'data', 'privacy', 'online', 'digital', 'complaint'
        ]
    }
    
    def classify(self, query: str) -> List[str]:
        """Returns list of relevant categories for the query"""
        query_lower = query.lower()
        matched = []
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                matched.append(category)
        
        # Default to all categories if no match (broad query)
        return matched if matched else ['criminal', 'constitutional', 'civil', 'special']


# ─────────────────────────────────────────
# RAG ENGINE
# ─────────────────────────────────────────

class LegalRAGEngine:
    """
    Core RAG engine:
    1. Classifies query
    2. Retrieves relevant law sections
    3. Builds context prompt
    4. Gets LLM response
    5. Returns cited answer
    """
    
    def __init__(self):
        # Connect to ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self.collection = self.chroma_client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=self.embedding_fn
        )
        
        # LLM client
        self.llm = Anthropic(api_key=ANTHROPIC_API_KEY)
        
        # Query classifier
        self.classifier = QueryClassifier()
        
        print("✅ Legal RAG Engine initialized")
        print(f"   Laws indexed: {self.collection.count()} chunks")
    
    def retrieve(self, query: str, n_results: int = 8) -> List[Dict]:
        """
        Retrieves most relevant law sections for a query
        Uses multi-category search for comprehensive coverage
        """
        categories = self.classifier.classify(query)
        all_results = []
        seen_sections = set()
        
        # Search each relevant category
        results_per_category = max(2, n_results // len(categories))
        
        for category in categories:
            results = self.collection.query(
                query_texts=[query],
                n_results=results_per_category,
                where={"category": {"$eq": category}},
                include=['documents', 'metadatas', 'distances']
            )
            
            for i in range(len(results['ids'][0])):
                section_key = f"{results['metadatas'][0][i]['act']}_{results['metadatas'][0][i]['section']}"
                
                # Avoid duplicate sections
                if section_key not in seen_sections:
                    seen_sections.add(section_key)
                    all_results.append({
                        "relevance": round(1 - results['distances'][0][i], 3),
                        "act": results['metadatas'][0][i]['act'],
                        "section": results['metadatas'][0][i]['section'],
                        "title": results['metadatas'][0][i]['title'],
                        "category": category,
                        "text": results['documents'][0][i]
                    })
        
        # Sort by relevance
        all_results.sort(key=lambda x: x['relevance'], reverse=True)
        return all_results[:n_results]
    
    def build_context(self, retrieved_sections: List[Dict]) -> str:
        """
        Builds the context string from retrieved sections
        """
        context_parts = []
        
        for i, section in enumerate(retrieved_sections, 1):
            context_parts.append(f"""
[{i}] {section['act']} — Section {section['section']}
Title: {section['title']}
Relevance: {section['relevance']}
Content: {section['text'][:800]}
""")
        
        return "\n---\n".join(context_parts)
    
    def answer(self, query: str, conversation_history: List = None) -> Dict:
        """
        Main method: takes a query, returns a cited legal answer
        
        Args:
            query: User's legal question
            conversation_history: List of previous messages for multi-turn
        
        Returns:
            dict with answer, citations, and retrieved sections
        """
        print(f"\n🔍 Query: {query[:100]}")
        
        # Step 1: Retrieve relevant sections
        retrieved = self.retrieve(query, n_results=8)
        print(f"   Retrieved {len(retrieved)} relevant sections")
        
        if not retrieved:
            return {
                "answer": "I couldn't find relevant sections for this query. Please try rephrasing.",
                "citations": [],
                "retrieved_sections": []
            }
        
        # Step 2: Build context
        context = self.build_context(retrieved)
        
        # Step 3: Build messages
        messages = []
        
        # Add conversation history if exists
        if conversation_history:
            messages.extend(conversation_history)
        
        # Add current query with context
        messages.append({
            "role": "user",
            "content": f"""
RELEVANT LAW SECTIONS RETRIEVED:
{context}

USER QUESTION: {query}

Please answer based on the retrieved law sections above. 
Cite specific sections in your answer.
If the retrieved sections don't fully cover the question, 
say so and provide what you know.
"""
        })
        
        # Step 4: Get LLM response
        response = self.llm.messages.create(
            model=LLM_MODEL,
            max_tokens=2000,
            system=LEGAL_GPT_SYSTEM_PROMPT,
            messages=messages
        )
        
        answer_text = response.content[0].text
        
        # Step 5: Extract citations
        citations = [
            f"{s['act']} — Section {s['section']}: {s['title']}"
            for s in retrieved[:5]
        ]
        
        return {
            "answer": answer_text,
            "citations": citations,
            "retrieved_sections": retrieved,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens
        }


# ─────────────────────────────────────────
# INTERACTIVE TERMINAL DEMO
# ─────────────────────────────────────────

def run_interactive():
    """
    Interactive terminal interface for testing
    """
    print("\n" + "="*60)
    print("⚖️  LEGAL GPT — INTERACTIVE MODE")
    print("   Type 'quit' to exit")
    print("   Type 'history' to see conversation")
    print("="*60)
    
    engine = LegalRAGEngine()
    conversation_history = []
    
    while True:
        print()
        query = input("❓ Your legal question: ").strip()
        
        if not query:
            continue
        if query.lower() == 'quit':
            break
        if query.lower() == 'history':
            print("\n📜 Conversation History:")
            for msg in conversation_history:
                role = "You" if msg['role'] == 'user' else "Legal GPT"
                print(f"\n{role}: {str(msg['content'])[:200]}...")
            continue
        
        # Get answer
        result = engine.answer(query, conversation_history)
        
        print("\n" + "─"*60)
        print("⚖️  LEGAL GPT ANSWER:")
        print("─"*60)
        print(result['answer'])
        
        print("\n📜 SECTIONS CITED:")
        for citation in result['citations']:
            print(f"  • {citation}")
        
        print(f"\n💡 Tokens used: {result.get('tokens_used', 'N/A')}")
        print("─"*60)
        
        # Update conversation history for multi-turn
        conversation_history.append({"role": "user", "content": query})
        conversation_history.append({"role": "assistant", "content": result['answer']})
        
        # Keep history manageable (last 10 exchanges)
        if len(conversation_history) > 20:
            conversation_history = conversation_history[-20:]


# ─────────────────────────────────────────
# FASTAPI ENDPOINT (for your backend)
# ─────────────────────────────────────────

"""
To integrate with your existing FastAPI backend,
add this to your main.py:

from fastapi import FastAPI
from pydantic import BaseModel
from 03_rag_engine import LegalRAGEngine

app = FastAPI()
engine = LegalRAGEngine()

class QueryRequest(BaseModel):
    query: str
    conversation_history: list = []

@app.post("/api/legal/query")
async def legal_query(request: QueryRequest):
    result = engine.answer(
        request.query,
        request.conversation_history
    )
    return {
        "answer": result["answer"],
        "citations": result["citations"],
        "sections": [
            {
                "act": s["act"],
                "section": s["section"],
                "title": s["title"],
                "relevance": s["relevance"]
            }
            for s in result["retrieved_sections"][:5]
        ]
    }
"""

if __name__ == "__main__":
    run_interactive()
