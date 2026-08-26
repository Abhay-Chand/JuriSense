# SaulGPT — Complete Feature Architecture

## Project Overview

SaulGPT is an AI-powered Indian Legal Intelligence Assistant using a 6-layer RAG pipeline to answer legal queries, draft documents, evaluate contracts, and provide structured legal analysis. It uses a 3-phase "Virtual Counsel" flow (Discovery → Strategy → Execution) for legal grievance handling with Llama 3.1 8B via Groq.

---

## 1. Backend Systems

### 1.1 API Server & Request Routing

**Source:** ackend/api_server.py (~1662 lines)

FastAPI server (port 8000) with CORS, Groq LLM initialization, and Knowledge Graph startup.

**Endpoints:**

| Method | Route | Auth | Purpose |
|--------|-------|------|---------|
| POST | /api/chat | Optional | Main chat: pipeline, triage state machine, drafting loop, IRAC |
| POST | /api/chat/stream | Optional | SSE-streaming variant |
| POST | /api/upload | No | Contract upload and evaluation (multipart) |
| GET | /api/document/{session_id} | No | Serve generated .docx as download |
| DELETE | /api/history/{session_id} | No | Clear session history |
| DELETE | /api/draft/state/{session_id} | No | Clear drafting state / cancel interview |
| GET | /api/health | No | Health check |
| GET | /api/conversations | Bearer | List conversations (paginated) |
| POST | /api/conversations | Bearer | Create conversation |
| GET | /api/conversations/{id} | Bearer | Load conversation with messages |
| DELETE | /api/conversations/{id} | Bearer | Delete conversation |
| POST | /api/conversations/migrate | Bearer | Bulk-import guest messages for session takeover |
| POST | /api/auth/signup | No | Register user |
| POST | /api/auth/login | No | Login user |
| GET | /api/auth/me | Bearer | Current user info |

**Request Pipeline** (for /api/chat):
1. Auth resolution (JWT or guest)
2. Conversation resolution (map session_id to conv_id or create new)
3. Message persistence (to SQLite if authenticated)
4. Interview state check
5. Interruption guard (clarification/hypothetical/pushback)
6. **Crisis pre-check** (regex: self-harm, active violence, confinement → helplines, stop)
7. Jurisdiction gate (non-Indian queries → rejected before processing)
8. Direct legal query patterns (15 regex → force knowledge mode)
9. Triage LLM call (classify: off-topic / direct legal / educational / document / grievance)
10. Triage state machine routing (3-phase flow or pass-through)
11. Pipeline dispatch (6-layer RAG fallthrough)
12. Response construction (widget metadata: remapped laws, urgency, jurisdiction)
13. Response persistence (conv_id injected for frontend tracking)

**State Stores:**
- ACTIVE_CONVERSATIONS: session_id → conv_id mapping
- SESSIONS: per-session drafting interview state
- SESSION_DOCUMENTS: generated .docx bytes
- TRIAGE_STATES: per-session 3-phase flow state

**Robust JSON Extraction:** _extract_json() with 4-layer fallback (pure JSON → markdown codeblock → markdown key-value → empty dict) used by all three core agents (triage, discovery, strategy).

---

### 1.2 Crisis Detection & Emergency Response

**Source:** `backend/api_server.py` — `_detect_crisis()` + `_CRISIS_PATTERNS`

Regex-based pre-check that fires **before any LLM call or pipeline processing**, positioned between the jurisdiction gate and the triage classification.

**3 crisis categories:**

| Category | Trigger examples | Response |
|---|---|---|
| **Self-harm** | "kill myself", "suicide", "hurt myself", "end my life" | Suicide prevention helplines (AASRA, iCall, Vandrevala) + emergency number |
| **Active violence** | "beating me right now", "trying to kill me", "weapon" | Police (100), National Emergency (112), Women's Helpline (1091) |
| **Confinement** | "locked in", "held against my will", "passport taken" | Police (100), National Emergency (112) |

**Design principle:** Hard stop — no Discovery, no RAG, no pipeline. The system refuses to process further until the user confirms safety.

---

### 1.3 6-Layer RAG Pipeline

**Source:** ackend/pipeline_orchestrator.py (~700 lines)

Sequential pipeline for all non-drafting queries.

**Layer 0: Conversation Memory (Sliding Window)**
- Per-session verbatim turn memory
- Sliding window: 6 turns verbatim, older turns collapsed into key facts
- Thresholds: collapse at 9 turns, summarize at 12 turns
- Key fact extraction: regex for dates, amounts (INR/Rs.), places, section numbers
- Functions: save_turn_to_memory(), get_history_with_summary()

**Layer 1: Query Understanding** (layer1_understanding.py, ~400 lines)
- Language detection (langdetect, fallback "en")
- Intent classification: factual / procedure / definition / comparison / analysis / document / ambiguous
- Entity extraction (spaCy NER: PERSON, ORG, GPE, LAW, DATE, MONEY, TIME)
- Citation extraction (regex: "Section X of Y Act", "Article Z")
- Ambiguity detection (vague phrasing patterns)
- Query reformulation (LLM-based abbreviation expansion)
- spaCy model: en_core_web_sm

**Layer 2: Hybrid Vector Retrieval** (layer2_retrieval.py, ~350 lines)
- Vector DB: ChromaDB, collection "saulgpt_indian_laws"
- Embedding model: all-MiniLM-L6-v2
- Chunks: 1200 chars, 150 overlap (~2409 chunks, 9 acts)
- Hybrid: semantic search + BM25 keyword retrieval
- Cross-encoder reranking: ms-marco-MiniLM-L-6-v2 (8 candidates → 5 results)
- Noise detection: max_score < 0.5 AND spread < 0.15 → web fallback
- Deduplication by content hash
- Citation filtering prioritization

**Layer 3: LLM Reasoning** (layer3_reasoning.py, ~700 lines)
- Model: llama-3.1-8b-instant via Groq (temperature 0.1)
- Mode prompts: knowledge (neutral), analysis (FACTS/ISSUES/LAW/OUTCOME), document (drafting), pathfinder (step-by-step)
- Context: retrieved chunks + conversation history + mode instruction
- Knowledge Graph expansions injected
- Ambiguity handling → clarifying questions

**Layer 4: Response Validation** (layer4_validation.py, ~700 lines)
- Citation verification (regex cross-check against retrieved chunks)
- NLI hallucination check (DeBERTa, fallback to pattern matching)
- Repealed law interception (IPC/CrPC/IEA → BNS/BNSS/BSA; generates remapped_laws)
- Struck-down section detection
- Legal terminology enforcement (informal → formal)
- Disclaimer enforcement
- Remedy validation

**Layer 5: External Data** (layer5_external.py, ~450 lines)
- DuckDuckGo fallback (appends "Indian law indiankanoon indiacode")
- Post-filter to Indian legal domains (.gov.in, indiankanoon.org, indiacode.nic.in)
- IndianKanoon case law scraping (BeautifulSoup)
- Auto-updater (APScheduler, 30-day interval)

**Layer 6: Evaluator** — see Contract Evaluation System (1.6).

---

### 1.4 3-Phase Virtual Counsel Flow

**Source:** ackend/api_server.py (triage state machine), 	riage_state.py, discovery_agent.py, strategy_agent.py, prompts/discovery.py, prompts/strategy.py

Python-enforced state machine replacing old keyword-based triage for legal grievances.

**State Machine** (	riage_state.py, 47 fields):
- current_mode: "idle" | "discovery" | "strategy"
- discovery_profile: structured Phase 1 output
- discovery_turn_count: hard 3-turn cap (Python-enforced)
- strategy_data: SWOT + options
- selected_strategy_id: user-chosen path_a..path_d
- counsel_override: LLM-detected override flag

**Phase 1: Discovery** (discovery_agent.py, prompts/discovery.py)
- Structured 3-turn sequence with fixed objectives per turn:
  - **Turn 0 (Story & Legal Anchor)**: Empathy + brief area-of-law anchor + open-ended story question
  - **Turn 1 (Evidence & Timeline)**: Ask about documentary proof and exact dates; skip if already populated
  - **Turn 2 (Outcome & Priority)**: Ask what the user wants and what matters most; always final turn
- Adaptive skip: each turn checks existing profile and skips if target fields are already filled
- Legal Framework Anchor: LLM names the relevant area of law before asking questions ("This falls under Indian Employment Law")
- Tone Protocol: matches emotional_state (angry/frustrated/desperate/calm)
- Graceful vague-answer handling (no re-asking on "I don't know")
- Hard 3-turn Python cap (enforced by api_server.py line 1205: `discovery_turn >= 2`)
- Discovery Profile output: emotional_state, desired_outcome, evidence_quality, timeline, user_priority, opponent_profile
- 4-layer JSON extraction
- Emotional-language fix: CRITICAL RULE ensures anger/frustration = legal grievance, not off-topic

**Phase 2: Strategy** (strategy_agent.py, prompts/strategy.py)
- SWOT: Strengths, Weaknesses, Opportunities, Threats
- Exactly 4 options (path_a..path_d), each with:
  - route_to: "document" (drafting) or "pathfinder" (procedure)
  - title, description, pros, cons, estimated_timeline, difficulty, success_probability
- Counsel Override for exceptional cases (government opponent, acknowledgment)
- Evidence weakness flagging
- Validation: strips path_e, pads with universal catch-alls, validates route_to
- Unrecognized routing → pathfinder with preamble note

**Phase 3: Execution**
- Document → interview_state field collection
- Pathfinder → 6-layer pipeline in procedural mode
- IRAC Advocate Mode → keyword/button-invoked structured analysis

---

### 1.5 IRAC Advocate Mode

**Source:** ackend/irac_agent.py, prompts/irac.py

Structured legal analysis for law students/advocates. Never invoked as hidden fallback.

**IRAC Structure:** FACTS (neutral) → ISSUES (legal questions) → RULE (RAG-grounded statutes) → APPLICATION (both-sides argumentation) → CONCLUSION (balanced assessment)

**Domain Statute Mappings:** Employment, Contracts, Property, Family, Consumer, Criminal, Torts

**Guardrails:**
- Domain guardrails (no factory acts for white-collar disputes, no constitutional articles unless government opponent)
- All citations RAG-grounded (never outside retrieved docs)
- No verdict — Application argues both sides

**Invocation:** Frontend "Advocate Mode" button + natural language ("advocate", "irac", "deep legal analysis"). Resets to "idle" after output.

---

### 1.6 Document Drafting System

**Interview State** (interview_state.py, ~950 lines)
- State machine: IDLE → INTERVIEWING → DRAFTING → COMPLETE
- Document families: letter, pleading, affidavit, agreement
- 5 predefined schemas: legal_notice, cheque_bounce, employment_notice, fir, rental_agreement
- Each schema: 5-9 fields (sender, recipient, dates, amounts, etc.)

**Dynamic Field Scoping** (dynamic_drafter.py, ~400 lines)
- LLM-driven field identification (max 7 fields)
- Classifies document type from query
- Builds prompt injections from collected values
- Session-cached field scope
- Falls back to static schemas

**Interview Loop:**
- Progressive field-by-field questioning
- Interruption handling (clarification, hypothetical, pushback)
- Unrelated query detection (resets state)
- Progress tracking per message

**Three-Layer Document Gate:**
1. Triage identifies document intent
2. User picks document path from Strategy options
3. Explicit "Shall I draft?" confirmation

**.docx Generation** (document_generator.py, ~980 lines)
- Rendering: python-docx, Times New Roman 12pt, 1-inch margins, 1.5 spacing
- 4-family: letter, pleading, affidavit, agreement
- Primitive functions: add_header, add_title, add_recipient_block, add_subject_line, add_body, add_signature_block, add_enclosures, add_court_details, add_verification, add_pagination

---

### 1.7 Contract Evaluation System

**Source:** ackend/layer6_evaluator.py (~470 lines)

- Format support: PDF (PyMuPDF), DOCX (python-docx)
- Chunking: 5000-character at paragraph boundaries
- Evaluation dimensions: clarity, enforceability, compliance, risk, completeness
- Per-chunk LLM evaluation (llama-3.1-8b-instant)
- Output: overall_score, risk_level (low/medium/high/critical), clauses, summary, recommendations
- Upload max: 50MB

---

### 1.8 Pre-Draft Legal Scrutiny Engine

**Source:** ackend/scrutiny_agent.py (~640 lines)

**ScrutinyResult:** is_valid, issues, warnings, limitation_status, remedy_feasibility, limitation_date, bns_mapping, risk_score (0-100), recommendations

**Checks:**
1. Limitation (12 claim types with periods, exception detection: acknowledgment, continuous wrong, disability, government)
2. Remedy validity
3. BNS/BSA enforcement (IPC/CrPC/IEA → BNS/BNSS/BSA)
4. Field validation per doc type

**Severity Levels:** "serious" (red, blocking), "warning" (gold, acknowledgeable), "info" (teal, acknowledgeable)

---

### 1.9 Legal Knowledge Graph

**Source:** ackend/layer6_knowledge_graph.py (~560 lines)

- NetworkX DiGraph: 89 nodes, 67 edges
- Relationships: Act replacements (IPC→BNS, CrPC→BNSS, IEA→BSA), constitutional hierarchy, cross-act links, procedural chains (FIR→Investigation→Charge Sheet→Trial→Appeal)
- ~30 act aliases resolved to canonical names
- expand_context(): injects graph into pipeline, returns replaced_acts for frontend

---

### 1.10 Authentication & User Persistence

**JWT Auth** (ackend/auth.py, 42 lines)
- bcrypt hashing (passlib)
- JWT: 30-day expiry, HS256

**SQLite DB** (ackend/database.py, ~170 lines)
- Tables: users, conversations, messages
- WAL mode, foreign keys, thread-local connections
- bulk_import_messages() for guest session takeover

---

### 1.11 Legal Data Ingestion Pipeline

**Scraper** (ackend/scraper/, 4 files + config)
- LegalScraperEngine: IndiaCodeScraper (DSpace) + KanoonScraper (BeautifulSoup)
- 25 scrapeable acts in config

**Chunking & Embedding** ( 2_chunk_and_embed.py, ~469 lines)
- Chunk: 1200 chars, 150 overlap
- Embedding: all-MiniLM-L6-v2
- Universal key detector (14+ key variants per field)
- 5 JSON structures supported
- Lineage header: [Act: X] [Section Y: Z].

**Embedded Acts (9):** BNS 2023, Constitution of India, BNSS 2023, CPC, Negotiable Instruments Act, Hindu Marriage Act, Motor Vehicles Act, BSA 2023, Indian Divorce Act

---

### 1.12 RAG Evaluation Suite

**Source:** ackend/eval_pipeline.py (~250 lines)

8 gold-standard test cases (knowledge, analysis, pathfinder). Metrics: retrieval_coverage, citation_accuracy, hallucination_score, overall_score.

---

## 2. Frontend Application

### 2.1 Core Chat Interface

**Source:** saulgpt-ui/src/App.jsx (935 lines)

**19 State Variables:**
- Auth: token, user, authLoading
- Chat: messages, input, loading, loadingLabel, forceMode, interviewActive
- UI: showSuggestions, showDropZone, showGlossary, glossaryCategory, showSidebar
- Session: convId, refreshTrigger

**Sub-components (inline):**
- TypingIndicator({ label }): animated bot-typing dots
- InterviewProgress({ pct }): progress bar (0-100%)
- RiskBadge({ risk }): color-coded pill (High/Medium/Low)
- PipelineMeta({ data }): collapsible debug panel (citations, repealed laws, validation, confidence)
- Message({ msg, onTriageChoice }): single chat message renderer with markdown, widgets, and export bar
- DropZone({ onFile, disabled }): drag-and-drop contract upload

**7 useEffect Hooks:**
1. convRef sync (prevents stale overwrites)
2. Persist convId to localStorage
3. Page refresh recovery (load conversation from API on mount)
4. Persist guest messages (last 6)
5. Auto-scroll on message/loading change
6. Auto-resize textarea
7. Cross-tab auth sync (storage event listener)

**Key Functions:**
- api(): axios instance with Bearer token + 401 interceptor (auto-logout)
- sendMessage(): core send → POST /api/chat → handle interview/triage/complete states
- handleFile(): contract upload → POST /api/upload
- handleTriageChoice(): triage card → sendMessage
- clearChat(), cancelInterview(), handleAuth(), logout()

**Welcome Screen:** Animated seal, "Your Counsel Awaits", feature cards (Ask/Draft/Evaluate), 5 suggested queries.

**Send Flow:** Validation → optimistic append → POST /api/chat → response processing → loading=false.

**Mode Selector:** 5 buttons (Auto, Knowledge, Analysis, Document, Pathfinder).

**Chat Input:** Auto-resizing textarea, contextual placeholder, disabled during loading, file upload button, send button with spinner.

---

### 2.2 Document Drafting UI

- Interview badge ("Drafting Mode Active" with gold pulse) replaces mode selector during interview
- Cancel button (red, clears draft state)
- Input placeholder changes to "Type your answer..." during interview
- InterviewProgress per message
- .docx download button on completion (meta.document_ready flag)

### 2.3 Contract Evaluation UI

- DropZone (drag-and-drop, accepts PDF/DOCX/TXT, 50MB max)
- Upload button (paperclip icon, disabled during loading)
- "Running Red Pen evaluation..." loading label
- Evaluation response with risk level display

### 2.4 Response Widget System

Each widget conditionally renders based on response metadata:

**BNSCorrectionNotice** (BNSCorrectionNotice.jsx, 118 lines):
- "LEGISLATION UPDATE 2024" card
- Maps old law (IPC/CrPC/IEA, strikethrough red) → new law (BNS/BNSS/BSA, green check)
- Triggered by meta.remapped_laws

**VetoCard** (VetoCard.jsx, 144 lines):
- Collapsible scrutiny result with severity levels
- Serious: red pulsing, blocking gate (Consult Lawyer / Draft Demand Letter)
- Warning/Info: gold/teal, acknowledgment checkbox
- Sections: Limitation Act, Remedy Not Recognized, Law Updated BNS/BNSS
- Auto-corrections display

**UrgencyBanner** (UrgencyBanner.jsx, 83 lines):
- Critical (<30d): red pulsing, siren icon
- Warning (<90d): amber static, clock icon
- Shows limitation days + deadline date
- Triggered by urgency_flags or limitation_days

**JurisdictionBadge** (JurisdictionBadge.jsx, 151 lines):
- Court level: 8 types (Supreme Court gold, High Court teal, District Court green, etc.)
- Jurisdiction type: 8 icons (Civil, Criminal, Consumer, Family, Revenue, etc.)
- Territorial + pecuniary info
- Court description footnote

**TriageCards** (TriageCards.jsx, 121 lines):
- "Strategic Options" with info banners (limitation, jurisdiction)
- Clickable option cards (gold label + description + arrow)
- Action row: SWOT toggle, "Explain These Options", "Advocate Mode"
- Expandable SWOT analysis (4 color-coded boxes)

**PipelineMeta:** Collapsible debug panel showing mode, domain, laws, graph insights, case law, elapsed time, citations, validation status, confidence, hallucination warnings.

**Export Bar:** Copy (clipboard), Download PDF (jsPDF), Download .docx (backend URL).

### 2.5 Conversation Management

**Source:** saulgpt-ui/src/ConversationsSidebar.jsx (87 lines)

- Left panel (260px) with mobile backdrop overlay
- Header: "Chats (N)" + New (+) + Close (X)
- Conversation list: title (truncated 28 chars), relative time, delete on hover
- Active: gold border highlight
- Pagination: "Load more (N remaining)" button
- useEffect: fetches on mount + refreshTrigger change, AbortController cleanup
- Sidebar toggle via hamburger button

**loadConversation():** Clears UI → sets convId early → fetches messages → populates → handles error with message in chat

**newConversation():** Clears UI → setConvId(null) → creates on backend → triggers sidebar refresh

**deleteConversation():** Deletes on backend → clears local state if active → triggers sidebar refresh

### 2.6 Authentication & Session Management

**AuthPage** (AuthPage.jsx, 66 lines):
- Tabbed login/signup form
- Migration overlay (guest session takeover spinner)
- JWT stored in localStorage

**Session Features:**
- Page refresh recovery (loads last conversation from API)
- Guest message persistence (last 6 in localStorage)
- Guest session takeover (bulk-import on login)
- Cross-tab auth sync (storage event listener → auto-logout)
- 401 interceptor (expired token → logout)

### 2.7 Supporting Utilities

**LegalGlossary** (LegalGlossary.js, 287 lines):
- 200+ Indian legal terms with plain-language definitions
- 10 categories: Constitutional, Criminal Law, Criminal Procedure, Commercial Law, Civil Procedure, Consumer Law, Labour Law, Property Law, Family Law, General
- Functions: scanForTerms(), getTermDefinition(), getTermsByCategory(), getCategories()
- Glossary sidebar with category filter + search

**PDF Generation** (usePDF.js, 405 lines):
- jsPDF-based A4 PDF generator
- Professional formatting: letterhead, gold rules, document type label, validation badge, citations block, auto page breaks
- Color palette: gold, ink, sage, red, amber
- Section starters for 13 pattern types
- 25mm margins (Indian legal standard)

---

## 3. Agent Architecture

### 3.1 Central LLM Client

**Source:** ackend/agents/llm_client.py

4 pre-initialized ChatGroq instances:
- Researcher: mixtral-8x7b-32768 (temperature 0.1)
- Drafter: llama-3.1-8b-instant (temperature 0.1)
- Reviewer: llama-3.1-8b-instant (temperature 0.1)
- Triage: llama-3.1-8b-instant (temperature 0.1)

All load GROQ_API_KEY from .env.

### 3.2 Agent Manager & Routing

**Source:** ackend/agents/manager.py

AgentManager with mode detection (regex patterns) and route dispatch:
- legal_query → ResearcherAgent
- case_analysis → ResearcherAgent (analysis mode)
- pathfinder → ResearcherAgent (pathfinder mode)
- document → DrafterAgent
- interviewing → DrafterAgent
- evaluate → ReviewerAgent
- scrutiny → ReviewerAgent

### 3.3 Sub-Agents

**TriageAgent** (gents/triage.py): Query classification (LLM + keyword fallback), TOWS analysis generation.

**ResearcherAgent** (gents/researcher.py): Knowledge Q&A, case analysis (FACTS/ISSUES/LAW/OUTCOME), pathfinder (step-by-step). Includes IPC/CrPC→BNS/BNSS mapping.

**DrafterAgent** (gents/drafter.py): Document type detection, field collection, LLM document generation.

**ReviewerAgent** (gents/reviewer.py): Contract evaluation, pre-draft scrutiny, limitation check, red flag detection, veto check.

---

## 4. Data Layer

### 4.1 SQLite (Relational)
- Tables: users, conversations, messages
- File: backend/saulgpt.db
- WAL mode for concurrency

### 4.2 ChromaDB (Vector)
- Collection: saulgpt_indian_laws
- ~2409 chunks, 9 acts
- Path: data/vector_db/

### 4.3 JSON Raw Data
- Path: data/raw_data/
- 9 JSON files (one per embedded act)

### 4.4 Knowledge Graph (In-Memory)
- NetworkX DiGraph
- Built on server startup from module import

---

## File Reference Summary

**Backend (23 root + 6 agents + 8 prompts + 4 scraper + 3 tests = 45 Python files)**
- api_server.py (1662L) — FastAPI entry point
- pipeline_orchestrator.py (700L) — 6-layer pipeline controller
- layer1_understanding.py (400L) — Query analysis
- layer2_retrieval.py (350L) — Vector/hybrid retrieval
- layer3_reasoning.py (700L) — LLM response generation
- layer4_validation.py (700L) — Response validation
- layer5_external.py (450L) — Web/case law fallback
- layer6_evaluator.py (470L) — Contract evaluation
- layer6_knowledge_graph.py (560L) — Legal knowledge graph
- interview_state.py (950L) — Document drafting state machine
- document_generator.py (980L) — .docx generation
- dynamic_drafter.py (400L) — Dynamic field scoping
- scrutiny_agent.py (640L) — Pre-draft scrutiny
- discovery_agent.py (80L) — Phase 1 discovery
- strategy_agent.py (160L) — Phase 2 strategy
- irac_agent.py (110L) — Advocate mode IRAC
- triage_state.py (60L) — 3-phase flow state
- database.py (170L) — SQLite CRUD
- auth.py (42L) — JWT auth
- eval_pipeline.py (250L) — RAG evaluation

**Frontend (14 script + 5 CSS files)**
- App.jsx (935L) — Main app shell
- ConversationsSidebar.jsx (87L) — Conversation list
- AuthPage.jsx (66L) — Login/signup
- TriageCards.jsx (121L) — Strategy options
- VetoCard.jsx (144L) — Scrutiny blocking card
- BNSCorrectionNotice.jsx (118L) — Law update notice
- JurisdictionBadge.jsx (151L) — Court info badge
- UrgencyBanner.jsx (83L) — Deadline alert
- LegalGlossary.js (287L) — 200+ legal terms
- usePDF.js (405L) — PDF generator
- App.css (1228L) — Dark courtroom theme styles
