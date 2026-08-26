# Setup Guide

## Prerequisites

- **Python** 3.10+
- **Node.js** 18+ (for frontend)
- **npm** 9+ (comes with Node.js)
- **Git** (for cloning)

## Quick Start (One-Click)

### First Time Setup (One-Time Only)
1. Double-click `scripts\setup.bat`
2. Wait for installation to complete (installs Python deps + npm packages)

### Run the Application
**Double-click `start.vbs`** — It will:
- Start the backend API (port 8000)
- Start the frontend (port 5173)
- Automatically open your browser to http://localhost:5173

## Manual Setup

### 1. Backend Setup
```bash
# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate

# Install dependencies
pip install -r backend\requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm

# Set up environment variables
copy .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 2. Environment Variables
Create `.env` in project root:
```
GROQ_API_KEY=your_groq_api_key_here
```

Get a free API key from: https://console.groq.com

### 3. Data Ingestion (First Time Only)
The project includes pre-embedded data in `data/vector_db/`. To re-ingest from scratch:
```bash
cd backend
python 02_chunk_and_embed.py
```

### 4. Frontend Setup
```bash
cd saulgpt-ui
npm install
```

## Running

### Terminal 1 — Backend
```bash
cd backend
python api_server.py
```
Server starts at http://localhost:8000

### Terminal 2 — Frontend
```bash
cd saulgpt-ui
npm run dev
```
Frontend starts at http://localhost:5173

## Manual Start (via npm)
```bash
# From project root — runs backend + frontend concurrently
npm run dev
```

## Testing

### RAG Evaluation
```bash
cd backend
.venv\Scripts\python.exe eval_pipeline.py
```
Runs 8 gold-standard test cases covering knowledge, analysis, and pathfinder modes.

### Individual Agent Testing
```bash
curl http://localhost:8000/api/test/knowledge?q=What+is+section+138
curl http://localhost:8000/api/test/analysis?q=Employer+did+not+pay+salary
curl http://localhost:8000/api/test/pathfinder?q=How+to+file+an+FIR
curl http://localhost:8000/api/test/document?q=Draft+a+cheque+bounce+notice
curl http://localhost:8000/api/test/scrutiny    # POST with payload
```

## Project Structure

```
legal_ass/
├── backend/
│   ├── api_server.py              # FastAPI entry point (port 8000)
│   ├── pipeline_orchestrator.py   # 6-layer pipeline controller
│   ├── discovery_agent.py         # Phase 1 — Discovery
│   ├── strategy_agent.py          # Phase 2 — Strategy
│   ├── irac_agent.py              # Advocate Mode IRAC analysis
│   ├── triage_state.py            # 3-phase flow state machine
│   ├── interview_state.py         # Document drafting state machine
│   ├── dynamic_drafter.py         # Dynamic field scoping
│   ├── document_generator.py      # .docx generation
│   ├── scrutiny_agent.py          # Pre-draft scrutiny
│   ├── layer1_understanding.py    # Query understanding
│   ├── layer2_retrieval.py        # Vector/hybrid retrieval
│   ├── layer3_reasoning.py        # LLM response generation
│   ├── layer4_validation.py       # Response validation
│   ├── layer5_external.py         # Web/case law fallback
│   ├── layer6_evaluator.py        # Contract evaluation
│   ├── layer6_knowledge_graph.py  # Legal knowledge graph
│   ├── database.py                # SQLite CRUD
│   ├── auth.py                    # JWT auth
│   ├── eval_pipeline.py           # RAG evaluation suite
│   ├── agents/                    # Sub-agent architecture
│   │   ├── manager.py             # Agent routing & dispatch
│   │   ├── llm_client.py          # Centralized LLM client
│   │   ├── triage.py              # Query classification
│   │   ├── researcher.py          # Knowledge Q&A
│   │   ├── drafter.py             # Document drafting
│   │   └── reviewer.py            # Contract scrutiny
│   ├── prompts/                   # LLM prompt templates
│   │   ├── triage.py
│   │   ├── discovery.py
│   │   ├── strategy.py
│   │   └── irac.py
│   └── tests/                     # Test files
├── saulgpt-ui/
│   ├── src/
│   │   ├── App.jsx                # Main chat UI
│   │   ├── AuthPage.jsx           # Login/signup
│   │   ├── ConversationsSidebar.jsx  # Chat history
│   │   ├── TriageCards.jsx        # Strategy options
│   │   ├── VetoCard.jsx           # Scrutiny results
│   │   ├── BNSCorrectionNotice.jsx  # Law update notices
│   │   ├── JurisdictionBadge.jsx  # Court info
│   │   ├── UrgencyBanner.jsx      # Deadline alerts
│   │   ├── LegalGlossary.js       # 200+ legal terms
│   │   └── usePDF.js              # PDF generation
│   ├── package.json
│   └── vite.config.js
├── data/
│   ├── raw_data/                  # JSON legal acts
│   └── vector_db/                 # ChromaDB embeddings
├── scripts/
│   ├── setup.bat                  # One-time setup
│   └── start.bat                  # Launch script
└── start.vbs                      # One-click launcher
```
