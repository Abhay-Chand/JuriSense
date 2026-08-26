# SaulGPT - Project Memory

## Project Overview

**SaulGPT** is an AI-powered Indian Legal Intelligence Assistant. It uses a 6-layer RAG (Retrieval-Augmented Generation) architecture to answer legal queries about Indian law, draft legal documents, and evaluate contracts.

## Tech Stack

- **Frontend**: React 18 + Vite
- **Backend**: Python FastAPI
- **Vector Database**: ChromaDB
- **LLM Provider**: Groq (Llama 3.1 8B)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **NLP**: spaCy (en_core_web_sm)

## Architecture

### 6-Layer RAG Pipeline (`backend/legal_pipeline/`)

1. **Layer 1 - Understanding** (`layer1_understanding.py`): Query analysis, intent detection, legal domain classification
2. **Layer 2 - Retrieval** (`layer2_retrieval.py`): ChromaDB vector search with sentence embeddings
3. **Layer 3 - Reasoning** (`layer3_reasoning.py`): LLM-powered response generation using Groq
4. **Layer 4 - Validation** (`layer4_validation.py`): Fact-checking against retrieved legal sources
5. **Layer 5 - External** (`layer5_external.py`): DuckDuckGo fallback search, case law lookup
6. **Layer 6 - Evaluation** (`layer6_evaluator.py`): Confidence scoring, knowledge graph insights

### Document Types Supported

- Legal notices (cheque bounce, employment, general)
- FIR complaints
- Rental agreements
- Contract evaluation

### Data Sources

Legal acts stored in `data/raw_data/`:
- `indian_penal_code.json` - BNS 2023 (replaced IPC)
- `indian_constitution.json` - Constitution of India
- `CRPC_from_db.json` - BNSS 2023 (replaced CrPC)
- `CPC_from_db.json` - Code of Civil Procedure
- `NIA_from_db.json` - Negotiable Instruments Act
- `HMA_from_db.json` - Hindu Marriage Act
- `MVA_from_db.json` - Motor Vehicles Act
- `IEA_from_db.json` - Indian Evidence Act
- `IDA_from_db.json` - Indian Divorce Act

## Project Structure

```
legal_ass/
├── backend/                  # Python backend
│   ├── api_server.py        # FastAPI server (port 8000)
│   ├── pipeline_orchestrator.py
│   ├── interview_state.py   # Document drafting flow
│   ├── dynamic_drafter.py   # Legal document generation
│   ├── scrutiny_agent.py    # Contract evaluation
│   ├── layer1_understanding.py
│   ├── layer2_retrieval.py
│   ├── layer3_reasoning.py
│   ├── layer4_validation.py
│   ├── layer5_external.py
│   ├── layer6_evaluator.py
│   ├── layer6_knowledge_graph.py
│   ├── scraper/             # Legal data scraper
│   ├── requirements.txt
│   ├── tests/
│   └── logs/
├── data/
│   ├── raw_data/            # JSON legal acts
│   └── vector_db/           # ChromaDB embeddings
├── saulgpt-ui/              # Frontend
│   ├── src/                 # React UI components
│   │   ├── App.jsx         # Main app
│   │   ├── App.css
│   │   ├── LegalGlossary.js
│   │   ├── VetoCard.jsx
│   │   ├── JurisdictionBadge.jsx
│   │   ├── BNSCorrectionNotice.jsx
│   │   ├── UrgencyBanner.jsx
│   │   └── usePDF.js
│   ├── public/
│   ├── package.json
│   └── vite.config.js
├── skills/                  # Claude Code skills
├── agents/                  # Sub-agent definitions
├── docs/                    # Documentation
└── scripts/                 # Automation scripts
```

## Conventions

### Python
- Use `spacy.load("en_core_web_sm")` for NLP
- ChromaDB collection: `saulgpt_indian_laws`
- Chunk size: 1200 chars, overlap: 150
- Embedding model: `all-MiniLM-L6-v2`

### React
- Component-based architecture
- Use `.jsx` for components, `.js` for utilities
- Axios for API calls

### API Endpoints
- `POST /api/chat` - Main query endpoint
- `POST /api/upload` - Contract evaluation
- `DELETE /api/history/{session_id}` - Clear chat history
- `DELETE /api/draft/state/{session_id}` - Clear draft state

## Environment Variables

Required in backend (set in your environment):
- `GROQ_API_KEY` - Groq API key for LLM

## Running the Application

### Quick Start (Windows)
Double-click `scripts\start.bat` to launch everything at once.

Or use terminal commands:
```bash
# First time setup (one-time)
scripts\setup.bat

# Run the app
scripts\start.bat
```

### Manual Start
```bash
# Terminal 1 - Backend
cd backend
python api_server.py

# Terminal 2 - Frontend
cd saulgpt-ui
npm run dev
```

Open `http://localhost:5173`

### npm Scripts
```bash
# Run everything at once (npm v8+)
npm run dev

# Setup only
npm run setup

## Security

- Never hardcode API keys in source files
- Use environment variables for secrets
- Validate all user inputs

## Goal
- 3-phase "Virtual Counsel" pipeline: Discovery (empathetic investigation) → Strategy (SWOT + filtered options with route_to) → Drafting (existing interview_state + .docx) OR Advocate Mode (IRAC deep analysis).
- Replace old triage layer with Python-enforced state machine, kill old case analysis fallback.
- IRAC as intentional Advocate Mode: RAG-grounded, both-sides argumentation, domain guardrails.

## Constraints & Preferences
- Free Groq models only (llama-3.1-8b-instant); no paid models.
- Discovery gate: personal grievances only (knowledge/off-topic skip to pipeline).
- Tone Protocol: LLM response tone matches `emotional_state` — never overly dramatic.
- Hard 3-turn Discovery cap enforced by Python, not just LLM prompt.
- `route_to` field on each Strategy option controls routing: "document" → drafting interview, "pathfinder" → step-by-step procedure. Never routed to old case analysis mode.
- Strategy always returns EXACTLY 4 options (path_a..path_d). Invalid IDs (path_e) are stripped by validation.
- Emotional language = legal grievance, NOT off-topic (critical fix for angry/determined clients).
- Robust 4-layer JSON extraction on all LLM calls: pure JSON → markdown code block → markdown key-value → empty dict fallback.
- Document gating unchanged: triage → strategy → explicit user pick → drafting → scrutiny → confirmation → .docx.

## Progress
### Done
- **Phase 1-2 (Discovery + Strategy)**:
  - `prompts/discovery.py` — Phase 1 empathetic investigator prompt (Tone Protocol, max 3 questions, graceful vague-answer handling, `discovery_profile` JSON output).
  - `prompts/strategy.py` — Phase 2 strategy prompt (SWOT + exactly 4 options with `route_to` field + Counsel Override + evidence weakness flagging).
  - `discovery_agent.py` — DiscoveryAgent class wrapping LLM call with robust 4-layer JSON extraction.
  - `strategy_agent.py` — StrategyAgent class with option validation (strips path_e, pads missing IDs, enforces route_to).
  - `triage_state.py` — Added `current_mode` ("idle"|"discovery"|"strategy"), `discovery_profile`, `discovery_turn_count` fields.
  - `api_server.py` — Replaced old triage layer (lines 966-1141) with 3-phase state machine: idle → classification → discovery → strategy → drafting/pipeline.
  - `prompts/triage.py` — Removed document drafting priority bypass. Added CRITICAL RULE: emotional language = legal grievance, not off-topic.
  - Verified end-to-end: angry grievance → classification (pass_through=false) → Discovery (emotional_state=angry, desired_outcome=punishment) → Strategy (SWOT + 4 options with route_to).

- **Robust JSON Extraction**: All 3 LLM-facing agents (triage, discovery, strategy) use `_extract_json()` 4-layer parser — fixes markdown-output-from-LLM problem endemic to llama-3.1-8b-instant.

- **Old Case Analysis Killed**: `_get_route_to()` replaces `_map_path_to_mode()`. The "analysis" fallback is dead — unrecognized option IDs route to "pathfinder" instead of triggering hallucinated IRAC case analysis. "analysis" in old pipeline is still reachable for pass_through=true general Q&A (intentional), never from the new 3-phase flow.

- **IRAC Advocate Mode**: `prompts/irac.py` — structured FACTS/ISSUES/RULE/APPLICATION/CONCLUSION prompt with RAG grounding requirement, domain-specific statute mappings, both-sides argumentation in APPLICATION phase. `irac_agent.py` — calls Layer 2 RAG retrieval (`retrieve_with_hybrid_logic`) then LLM generation with IRAC prompt. Domain guardrails prevent hallucinated statutes (e.g., no factory acts for white-collar disputes, no constitutional articles unless government opponent). Application phase argues both sides: "If X argues Y, the counter is Z."

- **Frontend Advocate Mode button**: `TriageCards.jsx` — "⚖ Advocate Mode" button alongside "Explain These Options", wired via `api_server.py` strategy handler to detect "advocate" / "irac" / "deep legal analysis" keywords and route to `IRACAgent`. Resets `current_mode` to "idle" after output so user can continue chatting.

- **Strategy Option Validation**: StrategyAgent validates LLM output — strips path_e, pads missing path_a..path_d with safe defaults.

- **Phase 3 (Drafting)**: Unchanged — existing interview_state + scrutiny + .docx generator. Disambiguation (MAP), point-of-law queries, and contract evaluation still work.

- All prior Phase 1-5 work (triage_context, sliding window, localStorage, auth, IPC→BNS, cross-tab sync, etc.) still intact.

### Blocked
- (none)

## Key Decisions
- **LLM-decided mode over keywords**: When triage returns `pass_through=true`, `suggested_mode` from LLM replaces keyword regex mode detection. Keywords kept as fallback only when triage unavailable.
- **No hardcoded role→path templates**: Prompt uses first-principles reasoning (relationship→right→remedy→forum→options) for ANY user role.
- **Limitation exceptions downgrade, not veto**: Acknowledgment/continuous wrong/disability/government notice detected → time-barred becomes warning + consult lawyer, not hard stop.
- **Sliding window over LLM summarization**: Running summary from concatenated older turn metadata — avoids latency/cost.
- **Document gating**: Three-layer check — (1) triage identifies document intent, (2) user picks document path, (3) explicit "Yes" to "Shall I draft?" confirmation. No accidental generation.
- **Document format**: `.docx` (not PDF) — editable, printable, professional formatting with Times New Roman, margins, sections, signature blocks, enclosures, witness blocks, disclaimer footer.
- **Self-contained auth over Firebase**: JWT + bcrypt + SQLite — no external dependencies.
- **Direct DB bulk import for guest takeover**: `POST /api/conversations/migrate` with `bulk_import_messages()` replaces fragile per-turn API replay — single transaction, no race conditions.
- **IPC/BNS detection in all chat paths**: Not limited to document drafting — `_populate_frontend_widgets()` scans every response text + citations for repealed act names and populates `remapped_laws`.
- **Cross-tab auth sync**: `window.addEventListener("storage", ...)` ensures logout in one tab invalidates all tabs.
- **Unrelated query detection**: Mid-interview non-answer queries reset document state to prevent stale `pending_generation` confirmation from leaking across topics.

## Next Steps
1. Wire agent prompts from `prompts/` into actual agent code instead of delegating to old pipeline functions (blocked — risky refactor).
2. Pass full conversation context to Layer 3 LLM (currently Layer 3 receives conversation_history but the prompt injection could be richer).
3. Add session-to-user linking in frontend (guest auth or session takeover after login).
4. Add server-side pagination for large conversations.
5. Run `eval_pipeline.py` to establish baseline RAG accuracy metrics before further prompt tuning.

## Critical Context
- **python-dotenv** loaded first in `api_server.py` before any imports that need `GROQ_API_KEY`. `.env` is gitignored.
- **python-docx** available in `.venv`.
- **Vector DB**: ~2409 chunks from 9 Indian acts in ChromaDB collection "saulgpt_indian_laws". Embedding: `all-MiniLM-L6-v2`. Relative threshold: noise detection (max_score < 0.5 AND spread < 0.15 → web fallback).
- **Indian-law site filter added**: DuckDuckGo query appends "Indian law indiankanoon indiacode" + post-filter to Indian legal domains.
- **Agents call old layer functions** (`analyze_query`, `generate_legal_response`) — tech debt.
- **max_completion_tokens warning** is cosmetic only, no functional impact.
- **Phase 4 explicitly skips vector DB expansion** per user instruction.
- **Sliding window fix**: Agent path now saves turns to memory (was broken, turns were never saved in agent path). Layer 3 now receives `conversation_history` parameter with full past context.
- **SQLite DB**: `backend/saulgpt.db` auto-created on first `init_db()` call. WAL mode for concurrent access.
- **bcrypt pinned to 3.2.2**: passlib incompatible with bcrypt 4.x/5.x (`AttributeError: module 'bcrypt' has no attribute '__about__'`).
- **FastAPI Pydantic v2 workaround**: Use `fastapi_request: Request` instead of `Annotated[str, Header()]` — mixing body models and header dependencies crashes due to Pydantic v2 field collision.
- **Guest takeover API**: `POST /api/conversations/migrate` accepts `{turns: [{role, content, meta}], title?: string}`, does single-transaction bulk insert via `bulk_import_messages()`.
- **IPC→BNS detection scope**: `_populate_frontend_widgets()` scans ALL responses — checks citations for `is_repealed` flags AND response text for "IPC", "CrPC", "IEA" mentions. Runs on every chat response.
- **Cross-tab auth**: `window.addEventListener("storage")` fires when `saulgpt_token` is removed in another tab — calls `logout()` without re-entering the 401 interceptor.
- **Sliding window key facts**: `_build_summary()` now extracts dates (`dd?[-/.]\w+[-/.]\d+`), amounts (`₹\d+`, `Rs\.\d+`), and section numbers (`S\.\d+|Section\s+\d+`) before truncation.

## Relevant Files
- `backend/document_generator.py`: `.docx` builder — `generate_docx()` dispatches to template builders or dynamic fallback. Professional formatting with Times New Roman, 1-inch margins, body paragraphs, signature block, disclaimer.
- `backend/api_server.py`: Interview completion flow (lines ~412-473) — runs scrutiny, asks user confirmation, sets `pending_generation` state. `_generate_document_docx()` helper (stores bytes in `SESSION_DOCUMENTS`, returns download URL). `_is_confirmation()` checks for yes/ok/proceed patterns. `GET /api/document/{session_id}` serves `.docx` as attachment. Auth endpoints, conversation endpoints, `POST /api/conversations/migrate`, `_save_to_db()` for chat persistence, `_populate_frontend_widgets()` for IPC→BNS/widget mapping.
- `backend/interview_state.py`: Added `confirm_generation`, `scrutiny_result`, `display_name`, `pending_generation`, `interrupted` state.
- `backend/database.py`: SQLite schema + CRUD + `bulk_import_messages()` for session takeover.
- `backend/auth.py`: JWT creation/verification + bcrypt password hashing.
- `backend/pipeline_orchestrator.py`: Sliding window + `save_turn_to_memory()` + `_build_summary()` with key fact extraction.
- `backend/layer3_reasoning.py`: `generate_legal_response()` now accepts `conversation_history` parameter.
- `backend/layer4_validation.py`: `REPEALED_ACT_PATTERNS` — text-match fallback for IPC/CrPC/IEA mentions in generated output.
- `backend/layer5_external.py`: DuckDuckGo filtered to Indian legal domains.
- `backend/agents/manager.py`, `researcher.py`, `drafter.py`, `reviewer.py`, `triage.py`: Phase 1-2 triage/agent system.
- `backend/agents/llm_client.py`: `load_dotenv` from project root.
- `backend/triage_state.py`, `prompts/triage.py`: Triage state management and prompt templates.
- `backend/scrutiny_agent.py`: Limitation exception detection (acknowledgment, continuous wrong, disability, government).
- `backend/eval_pipeline.py`: RAG accuracy evaluation suite (8 gold-standard test cases).
- `backend/irac_agent.py`: Advocate Mode IRAC agent — calls Layer 2 RAG retrieval, generates structured FACTS/ISSUES/RULE/APPLICATION/CONCLUSION analysis.
- `backend/prompts/irac.py`: IRAC system prompt with domain guardrails, both-sides argumentation rules, RAG grounding requirement.
- `saulgpt-ui/src/App.jsx`: Auth state management, sidebar toggle, 401 interceptor, `storage` event listener, guest migration flow, conv_id persistence.
- `saulgpt-ui/src/AuthPage.jsx`: Login/Signup form with migration spinner.
- `saulgpt-ui/src/ConversationsSidebar.jsx`: Paginated sidebar with "Load more" button.
- `saulgpt-ui/src/App.css`: Auth page styles, sidebar styles, `@keyframes spin`.
- `scripts/launch.bat`, `Run.bat`: Removed hardcoded GROQ_API_KEY.
- `.env`: Stores GROQ_API_KEY (gitignored).
- `.env.example`: Template without real key.

## Session Summaries

### Session 3 — Phase 4.1 (.docx generator) + Remaining Tasks
- Built `backend/document_generator.py` — 5 template-based `.docx` builders (legal_notice, cheque_bounce, fir_complaint, employment_notice, rental_agreement) + dynamic fallback, all ~37KB each
- Three-layer document gate: triage intercepts → scrutiny validates → explicit "Shall I draft?" confirmation
- `GET /api/document/{session_id}` download endpoint returns `.docx` as attachment
- `.docx` download button added to frontend message UI (appears when `meta.document_ready` is true)
- **Critical fix**: Agent path now saves turns to conversation memory — sliding window was broken (turns never saved in agent path)
- **GROQ_API_KEY** moved from hardcoded fallback in 5 Python files + 2 batch files to `.env` file (loaded via `python-dotenv` in `api_server.py` and `llm_client.py`)
- **Indian-law site filter** added to DuckDuckGo fallback: query appends "indiankanoon indiacode" + post-filters results to Indian legal domains
- **Relative relevance threshold** replacing flat 0.25: noise detection (max_score < 0.5 AND spread < 0.15 → web fallback) adapts to query difficulty
- **Upload limit** increased from 10MB to 50MB
- `.gitignore` already excluded `.env` — no change needed

### Session 4 — User Auth + Persistent Chat History
- **`backend/database.py`**: SQLite schema (users, conversations, messages) with WAL mode + CRUD operations
- **`backend/auth.py`**: JWT token creation/verification (+30-day expiry), bcrypt password hashing via passlib+bcrypt 3.2.2
- **Backend auth endpoints**: `POST /api/auth/signup`, `POST /api/auth/login`, `GET /api/auth/me`
- **Backend conversation endpoints**: `GET /api/conversations` (list), `POST /api/conversations` (create), `GET /api/conversations/{id}` (detail with messages), `DELETE /api/conversations/{id}`
- **Chat persistence**: `_save_to_db()` helper auto-persists every chat turn to SQLite for authenticated users
- **Title auto-set**: Conversation title is set from first user query (max 60 chars)
- **`ACTIVE_CONVERSATIONS` dict**: Maps session_id → conv_id for seamless conversation tracking
- **`Request` injection**: Changed from `Annotated[str, Header()]` to `fastapi_request: Request` to avoid FastAPI pydantic v2 body/header mixing bug
- **Frontend `AuthPage.jsx`**: Login/Signup form with JWT token stored in localStorage
- **Frontend `ConversationsSidebar.jsx`**: Conversation list with create/delete/switch, relative timestamps
- **App.jsx refactored**: Conditional auth page render, axios instance with Bearer token, `conv_id` support in API calls, user menu with logout, sidebar toggle
- **App.css extended**: Auth page styles (card, tabs, form), sidebar styles, layout structure

### Session 1 — Agent Architecture & Encoding Fix
- Built 3-agent architecture (Researcher, Drafter, Reviewer) with centralized LLM client
- Centralized prompts in `backend/prompts/`
- Created test endpoints at `/api/test/{mode}` for isolated agent testing
- **ROOT CAUSE of 500 errors**: Windows cp1252 terminal can't encode Unicode emoji (🧠, ✅, 🚀, →) in 92 `print()` statements. Fixed via `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` in `api_server.py` line 22 + `chcp 65001` + `set PYTHONIOENCODING=utf-8` in batch files
- Vector DB confirmed to have 2409 chunks (not empty)
- Fixed mode inheritance for follow-up questions
- Fixed "how to file an FIR" being misrouted to document drafting (added question-signal detection)

### Session 5 — Auth Stabilization & Critical Bugfixes (This Session)
- **Fix: `/api/conversations` returns empty list for unknown users**: Old `get_conversations()` errored when querying non-existent user id. New behavior returns `{"conversations": [], "total": 0}` for any user not in DB.
- **Fix: Guest session takeover via bulk import**: `POST /api/conversations/migrate` with `{"turns": [...]}` does single-transaction `bulk_import_messages()`. Replaces fragile per-turn API replay. Fixed `meta` field JSON serialization (was passing dict to SQLite TEXT column).
- **Fix: IPC→BNS in ALL chat responses**: `_populate_frontend_widgets()` now scans response text + citations for repealed act names (IPC, CrPC, IEA) and populates `remapped_laws` + `meta.remapped_laws` in every response. Frontend BNSCorrectionNotice appears on all relevant responses now.
- **Fix: Stale interview state on unrelated follow-up**: Mid-interview queries that aren't field answers now trigger an interrupt asking "Would you like to answer the field or cancel the draft?" — new `interrupted` state in `InterviewState`. Cancel resets state; answer resumes.
- **Fix: Sliding window key fact extraction**: `_build_summary()` now uses regex to extract dates, amounts (`₹`, `Rs.`, `INR`), places, and section numbers from old turns before truncation.
- **Fix: `bulk_import_messages()` JSON meta**: Added `json.dumps()` for non-string meta values. Import statement `json` added to `database.py`.
- **Fix: `remapped_laws` in frontend meta**: `_populate_frontend_widgets()` now sets `result["meta"]["remapped_laws"]` in addition to `result["remapped_laws"]` so frontend `BNSCorrectionNotice` (which reads `msg.meta.remapped_laws`) gets the data.
- **New: `eval_pipeline.py`**: Automated RAG evaluation suite with 8 gold-standard test cases covering knowledge, analysis, pathfinder modes. Tests confidence thresholds, expected keywords, forbidden keywords, and hallucination flags. Run with `& ".venv\Scripts\python.exe" eval_pipeline.py`.
- **Full integration test verified**: signup, login, conversation CRUD, chat with agent pipeline, guest migration, IPC→BNS detection, unauthorized access rejection — all passing.

### Session 6 — IRAC Advocate Mode + Emotional Classification Fix
- **IRAC Advocate Mode built**: `prompts/irac.py` — 4321-char structured IRAC prompt with FACTS/ISSUES/RULE/APPLICATION/CONCLUSION, domain-specific statute mappings (employment, contracts, property, family, consumer, criminal, torts), both-sides argumentation rules, and RAG grounding requirement (never cite statutes not in retrieved docs).
- **`irac_agent.py`**: IRACAgent class with async Layer 2 RAG retrieval via `retrieve_with_hybrid_logic()`, context building from retrieved docs (top 8), LLM generation via `get_drafter_llm()`, structured response dict with citations and confidence.
- **Wired into `api_server.py`**: IRAC route handler in strategy phase (L1105+) — detects "advocate", "irac", "deep legal analysis" keywords or "advocate" button click. Runs IRACAgent, resets `current_mode` to "idle", returns structured IRAC analysis to frontend.
- **Frontend button**: `TriageCards.jsx` — ⚖ Advocate Mode button alongside "Explain These Options", sends "advocate" choice to backend. `allow_advocate` flag passed through `_build_triage_response()` (default true).
- **Old analysis path verified**: `pipeline_orchestrator.py` analysis mode only reachable via pass_through=true general Q&A fallback — never from new 3-phase flow. `_get_route_to()` only returns "document" or "pathfinder".
- **Import verification**: IRACAgent imports cleanly, all AST syntax checks pass.

### Session 2 — Drafter Model Fix & Agent Verification
- Fix: `DRAFTER_MODEL` changed from decommissioned `llama-3.1-70b-versatile` to `llama-3.1-8b-instant`
- Fix: `dynamic_drafter.py` API key fallback changed from `"YOUR_GROQ_API_KEY_HERE"` to actual key
- Fix: `GROQ_API_KEY` added to `Run.bat` and `scripts/launch.bat` env setup
- All 5 agent modes verified working:
  - ✅ **knowledge** — Section 138 explained with correct MVA reference
  - ✅ **analysis** — "Employer didn't pay salary" → FACTS/ISSUES/LAW/OUTCOME framework
  - ✅ **pathfinder** — "How to file an FIR" → step-by-step procedure
  - ✅ **document** — Cheque bounce notice with Section 138 NIA reference and field placeholders
  - ✅ **scrutiny** — Case limitation check returned ScrutinyResult
- Port 8000 zombie process issue noted: old server without env/encoding fixes may still be running