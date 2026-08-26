# SaulGPT Architecture

## System Overview

SaulGPT is an AI-powered Indian Legal Intelligence Assistant with a 6-layer RAG pipeline, 3-phase "Virtual Counsel" flow, and full document drafting capabilities. Built with Python FastAPI backend and React+Vite frontend.

---

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)                    │
│  saulgpt-ui/src/                                             │
│  ├── App.jsx              Core chat UI, state management      │
│  ├── AuthPage.jsx         Login/Signup                        │
│  ├── ConversationsSidebar.jsx  Chat history sidebar           │
│  ├── TriageCards.jsx      Strategy option cards               │
│  ├── VetoCard.jsx         Scrutiny result display             │
│  ├── BNSCorrectionNotice.jsx  Repealed law notifications      │
│  ├── JurisdictionBadge.jsx    Court jurisdiction info          │
│  ├── UrgencyBanner.jsx    Limitation deadline alerts           │
│  ├── LegalGlossary.js     200+ Indian legal terms              │
│  └── usePDF.js            jsPDF-based PDF generation           │
└──────────────┬──────────────────────────────────────────────┘
               │ HTTP (port 5173 → 8000)
               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend (FastAPI, port 8000)               │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐     │
│  │              api_server.py (1708 lines)              │     │
│  │  Request routing → auth → crisis check → triage     │     │
│  │  → state machine → pipeline dispatch → response      │     │
│  └──────────┬────────────────────────────────┬──────────┘     │
│             │                                │                │
│  ┌──────────▼──────────┐   ┌─────────────────▼────────────┐  │
│  │  3-Phase Flow        │   │  Pass-Through (General Q&A)  │  │
│  │  idle→discovery→     │   │  ┌─────────────────────────┐ │  │
│  │  strategy→execution  │   │  │ 6-Layer RAG Pipeline    │ │  │
│  │                      │   │  │ Layer 1: Understanding  │ │  │
│  │                      │   │  │ Layer 2: Retrieval      │ │  │
│  │                      │   │  │ Layer 3: Reasoning      │ │  │
│  │                      │   │  │ Layer 4: Validation     │ │  │
│  │                      │   │  │ Layer 5: External       │ │  │
│  │                      │   │  │ Layer 6: Evaluation     │ │  │
│  │                      │   │  └─────────────────────────┘ │  │
│  └──────────────────────┘   └──────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 2. 3-Phase Virtual Counsel Flow

### Phase 1: Discovery (empathic investigation)
- Max 3-turn conversation capped by Python state machine
- Each turn has fixed objectives (story → evidence → outcome)
- Tone Protocol: LLM matches user's emotional state
- Output: `discovery_profile` JSON (emotional_state, desired_outcome, evidence_quality, timeline, opponent)
- 4-layer JSON extraction from LLM output
- Graceful vague-answer handling (no re-asking)

### Phase 2: Strategy (SWOT + options)
- SWOT analysis (Strengths, Weaknesses, Opportunities, Threats)
- Exactly 4 strategic options (path_a..path_d)
- Each option has: title, description, pros, cons, timeline, difficulty, success_probability, route_to
- `route_to` field: "document" → drafting interview, "pathfinder" → step-by-step procedure
- Counsel Override for exceptional cases
- Validation strips invalid IDs, pads missing ones

### Phase 3: Execution
- Document → interview_state field collection → scrutiny → .docx
- Pathfinder → 6-layer pipeline in procedural mode
- IRAC Advocate Mode → structured legal analysis

## 3. 6-Layer RAG Pipeline

| Layer | File | Function | Key Tech |
|-------|------|----------|----------|
| 0 | pipeline_orchestrator.py | Conversation memory / sliding window | 6 turns verbatim, older summarized |
| 1 | layer1_understanding.py | Query analysis | spaCy NER, langdetect, regex |
| 2 | layer2_retrieval.py | Hybrid vector retrieval | ChromaDB + BM25 + cross-encoder |
| 3 | layer3_reasoning.py | LLM response generation | Groq llama-3.1-8b-instant |
| 4 | layer4_validation.py | Fact-checking | NLI (DeBERTa), citation verification |
| 5 | layer5_external.py | Web fallback | DuckDuckGo, IndianKanoon scraping |
| 6 | layer6_evaluator.py | Confidence scoring | Contract evaluation, KG insights |

## 4. State Machines

### Triage State (`triage_state.py`)
- `current_mode`: "idle" | "discovery" | "strategy"
- `discovery_turn_count`: Hard 3-turn cap (Python-enforced)
- `selected_strategy_id`: User's chosen path
- `counsel_override`: LLM-detected override flag

### Interview State (`interview_state.py`)
- States: IDLE → INTERVIEWING → DRAFTING → COMPLETE
- 5 predefined document schemas (legal_notice, cheque_bounce, employment_notice, fir, rental_agreement)
- Unrelated query detection (resets state)
- Interruption handling (clarification, hypothetical, pushback)

### Document Gate (3 layers)
1. Triage identifies document intent
2. User picks document path from Strategy options
3. Explicit "Shall I draft?" confirmation

## 5. Data Layer

| Store | Technology | Contents | Location |
|-------|-----------|----------|----------|
| Vector DB | ChromaDB | 2409 chunks, 9 Indian acts | data/vector_db/ |
| Relational | SQLite (WAL mode) | users, conversations, messages | backend/saulgpt.db |
| Raw Data | JSON files | 9 Indian legal acts | data/raw_data/ |
| Knowledge Graph | NetworkX DiGraph | 89 nodes, 67 edges | In-memory (on startup) |

## 6. Authentication

- JWT-based (30-day expiry, HS256)
- bcrypt password hashing (passlib)
- SQLite-backed user storage
- Guest sessions with localStorage persistence
- Cross-tab auth sync via storage event listener
- 401 interceptor (auto-logout on expired token)

## 7. Document Generation

- python-docx for .docx generation
- 5 template builders + dynamic fallback
- Times New Roman 12pt, 1-inch margins, 1.5 spacing
- Professional elements: header, title, recipient block, subject line, body paragraphs, signature block, enclosures, court details, verification, pagination, disclaimer footer
- Serving: `GET /api/document/{session_id}`
