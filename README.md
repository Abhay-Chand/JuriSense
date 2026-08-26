# SaulGPT — Indian Legal Intelligence Assistant

AI-powered Indian Legal Intelligence Assistant with a 6-layer RAG pipeline, 3-phase "Virtual Counsel" flow (Discovery → Strategy → Execution), document drafting, contract evaluation, and IRAC Advocate Mode.

## Quick Start

**Just double-click `start.vbs`** — it launches backend + frontend + opens browser.

First time? Run `scripts\setup.bat` once first.

### Manual

```bash
# Terminal 1 — Backend
cd backend
python api_server.py

# Terminal 2 — Frontend
cd saulgpt-ui
npm run dev
```

Open http://localhost:5173

## Features

- **6-Layer RAG Pipeline** — Hybrid vector search (ChromaDB + BM25 + cross-encoder reranking) over 9 Indian legal acts (BNS 2023, Constitution, BNSS 2023, CPC, NIA, HMA, MVA, BSA 2023, IDA)
- **3-Phase Virtual Counsel** — Empathic Discovery (3-turn cap) → SWOT Strategy (4 options with `route_to`) → Execution (drafting or pathfinder)
- **IRAC Advocate Mode** — Structured FACTS/ISSUES/RULE/APPLICATION/CONCLUSION analysis with RAG-grounded citations and both-sides argumentation
- **Document Drafting** — 5 template .docx generators (cheque bounce, legal notice, FIR, employment, rental agreement) + dynamic fallback, with scrutiny gate and field-by-field interview
- **Contract Evaluation** — Upload PDF/DOCX/TXT (50MB) for AI-powered clause analysis, risk scoring, and recommendations
- **Pre-Draft Scrutiny** — Limitation check (12+ claim types), remedy validity, repealed law detection (IPC→BNS, CrPC→BNSS, IEA→BSA), field validation
- **User Auth** — JWT + bcrypt, SQLite persistence, guest sessions with takeover on login, cross-tab sync
- **Conversation History** — Per-user chat history with pagination, create/delete/switch
- **Crisis Detection** — Self-harm/violence/confinement pre-check fires before any LLM call
- **BNS Correction** — Automatic detection of repealed laws (IPC, CrPC, IEA) and mapping to new codes
- **Edge Cases** — Ambiguity detection, interruption handling, unrelated query detection, vague-answer handling, time-barred downgrade

## Tech Stack

- **Frontend**: React 18 + Vite + jsPDF (PDF export)
- **Backend**: Python FastAPI + python-docx + APScheduler
- **Vector DB**: ChromaDB (all-MiniLM-L6-v2 embeddings, 2409 chunks)
- **LLM**: Groq (llama-3.1-8b-instant, temperature 0.1)
- **NLP**: spaCy (en_core_web_sm), DeBERTa (NLI), ms-marco-MiniLM (cross-encoder)
- **Auth**: JWT (HS256, 30-day expiry) + bcrypt (passlib) + SQLite (WAL mode)
- **External**: DuckDuckGo (Indian-law filtered), IndianKanoon scraper

## Documentation

| Document                                 | Description                                    |
| ---------------------------------------- | ---------------------------------------------- |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md)   | System architecture, state machines, data flow |
| [API_REFERENCE.md](docs/API_REFERENCE.md) | All API endpoints, request/response formats    |
| [SETUP_GUIDE.md](docs/SETUP_GUIDE.md)     | Setup instructions, testing, project structure |
| [FEATURES.md](docs/FEATURES.md)           | Detailed feature documentation                 |
| [CLAUDE.md](CLAUDE.md)                    | Project memory for AI-assisted development     |

## Environment

Copy `.env.example` to `.env` and add your `GROQ_API_KEY` (get one at https://console.groq.com).
