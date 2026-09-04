# ⚖️ JuriSense

### Indian Legal Intelligence Assistant powered by RAG, LLMs & Multi-Agent AI

JuriSense is an AI-powered legal intelligence platform designed to help users research Indian legal information, analyze documents, draft legal documents, and work through structured legal reasoning workflows.

It combines **Retrieval-Augmented Generation (RAG)**, semantic and lexical retrieval, re-ranking, specialized AI agents, document processing, authentication, and a React-based user interface into a single application.

> **Important:** JuriSense is an AI assistance and research tool, not a substitute for a qualified legal professional. AI-generated content must be independently verified before being used for legal decisions or filings.

---

## ✨ Features

### 🔎 Legal Research
- Natural-language legal question answering
- Retrieval from an Indian legal knowledge base
- Semantic vector search
- BM25 lexical search
- Hybrid retrieval
- CrossEncoder re-ranking
- Source-grounded responses

### 🤖 AI Legal Assistant
- Conversational legal assistance
- Query triage and workflow routing
- Specialized research, drafting and review agents
- Context-aware responses
- Structured AI workflows

### 📄 Document Intelligence
- PDF processing
- Word document processing
- Document analysis
- Legal document workflows
- Draft generation and export

### 📝 Legal Drafting
- Legal notice drafting
- Structured document generation
- AI-assisted drafting workflows
- Review-oriented workflow

### ⚖️ Structured Legal Reasoning
- IRAC-style analysis
- Issue identification
- Rule identification
- Application
- Conclusion

### 🧠 Virtual Counsel
A multi-stage workflow intended to support:

```text
Discovery
   ↓
Strategy
   ↓
Execution
```

### 🔐 Authentication
- User registration
- Login
- JWT authentication
- Password hashing
- Conversation/user persistence

### 💬 Conversation History
- Persistent conversations
- Previous interaction retrieval
- New conversation workflows

### 🛡️ Safety & Reliability
- Retrieval-grounded responses
- Source-aware generation
- Input handling
- Legal-context safeguards
- Workflow separation

---

# 🏗️ Architecture

```text
                         ┌─────────────────────┐
                         │      React UI       │
                         │     Vite + React    │
                         └──────────┬──────────┘
                                    │
                                  HTTP
                                    │
                                    ▼
                         ┌─────────────────────┐
                         │       FastAPI       │
                         │    API Server       │
                         └──────────┬──────────┘
                                    │
               ┌────────────────────┼────────────────────┐
               │                    │                    │
               ▼                    ▼                    ▼
        Authentication        AI Workflows        Application Services
        JWT + SQLite          Agent Manager        Documents/Chat/etc.
                                    │
                  ┌─────────────────┼─────────────────┐
                  │                 │                 │
                  ▼                 ▼                 ▼
               Triage           Research          Drafting
                  │                 │                 │
                  └─────────────────┼─────────────────┘
                                    ▼
                                Reviewer
                                    │
                                    ▼
                              RAG Pipeline
                                    │
                  ┌─────────────────┴─────────────────┐
                  │                                   │
                  ▼                                   ▼
           Semantic Retrieval                   BM25 Retrieval
           Sentence Transformers                Lexical Search
                  │                                   │
                  └─────────────────┬─────────────────┘
                                    ▼
                              Candidate Set
                                    │
                                    ▼
                              CrossEncoder
                               Re-ranking
                                    │
                                    ▼
                              Relevant Context
                                    │
                                    ▼
                                Groq LLM
                                    │
                                    ▼
                            Grounded Response
```

---

# 🧰 Technology Stack

## Backend

| Technology | Purpose |
|---|---|
| Python 3.11 | Backend/runtime |
| FastAPI | REST API |
| Uvicorn | ASGI server |
| Pydantic | Data validation |
| SQLite | Application database |
| JWT | Authentication |
| Passlib + bcrypt | Password hashing |

## AI / RAG

| Technology | Purpose |
|---|---|
| Groq | LLM inference |
| LangChain | LLM/AI integration |
| Sentence Transformers | Embeddings |
| ChromaDB | Vector database |
| BM25 | Lexical retrieval |
| CrossEncoder | Re-ranking |
| spaCy | NLP processing |
| NetworkX | Graph-oriented processing |

## Documents

| Technology | Purpose |
|---|---|
| PyMuPDF | PDF processing |
| python-docx | Word document processing/generation |

## Frontend

| Technology | Purpose |
|---|---|
| React 18 | UI |
| Vite | Frontend tooling |
| Axios | API communication |
| jsPDF | PDF export |

---

# 📁 Project Structure

```text
JuriSense/
│
├── backend/
│   ├── api_server.py
│   ├── database.py
│   ├── auth.py
│   │
│   ├── agents/
│   │   ├── manager.py
│   │   ├── llm_client.py
│   │   ├── researcher.py
│   │   ├── drafter.py
│   │   ├── reviewer.py
│   │   └── triage.py
│   │
│   ├── layer1_understanding.py
│   ├── layer2_retrieval.py
│   ├── layer3_generation.py
│   ├── layer4_verification.py
│   ├── layer5_safety.py
│   ├── layer6_response.py
│   │
│   ├── pipeline_orchestrator.py
│   ├── 02_chunk_and_embed.py
│   ├── 03_rag_engine.py
│   │
│   ├── document_generator.py
│   ├── dynamic_drafter.py
│   ├── irac_agent.py
│   ├── scrutiny_agent.py
│   └── eval_pipeline.py
│
├── data/
│   ├── raw_data/
│   └── vector_db/
│
├── jurisense-ui/
│   ├── src/
│   ├── public/
│   ├── package.json
│   └── vite.config.*
│
├── docs/
│   ├── ARCHITECTURE.md
│   └── SETUP_GUIDE.md
│
├── scripts/
│   ├── setup.bat
│   └── start.bat
│
├── .env.example
├── README.md
└── LICENSE
```

---

# 🚀 Installation

## Prerequisites

Install the following before starting:

- Python **3.11**
- Node.js 18+ recommended
- npm
- Git

### Why Python 3.11?

The current dependency stack contains older AI packages.

In particular, the pinned `sentence-transformers`/ChromaDB ecosystem can cause Windows build problems on newer Python versions.

**Python 3.11 is the recommended version for this repository.**

Check:

```powershell
py -0p
```

You should see Python 3.11 installed.

Then:

```powershell
py -3.11 --version
```

---

# 🐍 Backend Setup

From the project root:

```powershell
py -3.11 -m venv .venv
```

Activate the environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Verify:

```powershell
python --version
```

Expected:

```text
Python 3.11.x
```

Verify the interpreter:

```powershell
python -c "import sys; print(sys.executable)"
```

It should point to:

```text
JuriSense\.venv\Scripts\python.exe
```

Upgrade packaging tools:

```powershell
python -m pip install --upgrade pip setuptools wheel
```

Install dependencies:

```powershell
python -m pip install -r backend\requirements.txt
```

---

# 🔧 Important Hugging Face Compatibility Fix

The project currently uses:

```text
sentence-transformers==2.2.2
```

This older version expects the `cached_download` API from older versions of `huggingface-hub`.

If you see:

```text
ImportError:
cannot import name 'cached_download'
from 'huggingface_hub'
```

install the compatible versions:

```powershell
python -m pip uninstall -y huggingface-hub transformers sentence-transformers

python -m pip install `
  "huggingface-hub==0.20.3" `
  "transformers==4.35.2" `
  "sentence-transformers==2.2.2"
```

Verify:

```powershell
python -c "import huggingface_hub; print('HF Hub:', huggingface_hub.__version__); import transformers; print('Transformers:', transformers.__version__); import sentence_transformers; print('Sentence Transformers:', sentence_transformers.__version__)"
```

Expected:

```text
HF Hub: 0.20.3
Transformers: 4.35.2
Sentence Transformers: 2.2.2
```

---

# 🔑 Environment Variables

Create a `.env` file in the **project root**, next to `README.md`.

Example:

```env
GROQ_API_KEY=your_groq_api_key_here
```

Start from:

```text
.env.example
```

Do not commit your real API key.

Your `.gitignore` should include:

```text
.env
.venv/
__pycache__/
```

---

# 🤖 Groq Configuration

The application uses Groq for LLM inference.

The exact model IDs are configured in:

```text
backend/agents/llm_client.py
```

If a configured model has been deprecated or removed by Groq, update the model ID there to a currently supported Groq model.

For example, current Groq-supported models can be checked from the official Groq documentation before changing production configuration.

Do not blindly change every model. Match the model to the workflow:

```text
Complex reasoning
        ↓
Stronger model

Routing/classification
        ↓
Fast smaller model
```

---

# 🧠 Build the Vector Database

The repository contains legal source data under:

```text
data/raw_data/
```

The RAG system expects a persistent vector database under:

```text
data/vector_db/
```

If `data/vector_db/` is missing or empty, build the index.

From the project root:

```powershell
python backend\02_chunk_and_embed.py
```

The indexing process creates embeddings using:

```text
all-MiniLM-L6-v2
```

and stores them in ChromaDB.

The expected collection is:

```text
saulgpt_indian_laws
```

### Important

The embedding model may download from Hugging Face the first time it runs.

The first indexing operation can therefore take longer than subsequent runs.

---

# ▶️ Start the Backend

From the project root:

```powershell
.\.venv\Scripts\Activate.ps1
cd backend
python api_server.py
```

The backend is expected to run on:

```text
http://localhost:8000
```

FastAPI documentation should be available at:

```text
http://localhost:8000/docs
```

and:

```text
http://localhost:8000/redoc
```

---

# 🎨 Start the Frontend

Open another terminal.

From the project root:

```powershell
cd jurisense-ui
npm install
npm run dev
```

Vite will display the local frontend URL, typically:

```text
http://localhost:5173
```

Open that URL in your browser.

---

# 🔄 Typical Development Workflow

Use two terminals.

### Terminal 1 — Backend

```powershell
cd JuriSense
.\.venv\Scripts\Activate.ps1
cd backend
python api_server.py
```

### Terminal 2 — Frontend

```powershell
cd JuriSense\jurisense-ui
npm run dev
```

---

# 🧪 Verify the Installation

Before testing the UI, verify Python:

```powershell
python --version
```

Then verify important AI packages:

```powershell
python -c "import chromadb; print('ChromaDB OK')"
python -c "import sentence_transformers; print('Sentence Transformers OK')"
python -c "import transformers; print('Transformers OK')"
python -c "import fastapi; print('FastAPI OK')"
```

Then start the backend:

```powershell
cd backend
python api_server.py
```

Finally start the frontend:

```powershell
cd jurisense-ui
npm run dev
```

---

# 🐛 Common Errors & Fixes

## 1. `Microsoft Visual C++ 14.0 or greater is required`

Example:

```text
Building wheel for chroma-hnswlib
error: Microsoft Visual C++ 14.0 or greater is required
```

### Cause

A package is being built from source because a compatible Windows wheel is unavailable for the selected Python version.

### Recommended fix

Use Python 3.11.

```powershell
deactivate

Remove-Item -Recurse -Force .venv

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend\requirements.txt
```

Do not immediately install Visual Studio Build Tools unless you specifically want to compile native dependencies.

---

# 2. `cannot import name 'cached_download'`

Example:

```text
ImportError:
cannot import name 'cached_download'
from 'huggingface_hub'
```

### Fix

```powershell
python -m pip uninstall -y huggingface-hub transformers sentence-transformers

python -m pip install `
  "huggingface-hub==0.20.3" `
  "transformers==4.35.2" `
  "sentence-transformers==2.2.2"
```

Then verify the versions as described above.

---

# 3. `GROQ_API_KEY not set`

Example:

```text
ValueError:
GROQ_API_KEY not set
```

### Fix

Create:

```text
.env
```

in the project root:

```env
GROQ_API_KEY=your_actual_key
```

Then restart the backend.

Do not put the key directly into source code.

---

# 4. `ModuleNotFoundError`

Example:

```text
ModuleNotFoundError: No module named 'xyz'
```

First confirm the virtual environment:

```powershell
python -c "import sys; print(sys.executable)"
```

It should point to:

```text
.venv\Scripts\python.exe
```

Then install using the same interpreter:

```powershell
python -m pip install <package>
```

Do not use a different global Python installation accidentally.

---

# 5. Wrong Python Version

Check:

```powershell
python --version
```

If it shows:

```text
Python 3.12
```

or:

```text
Python 3.14
```

recreate the environment:

```powershell
deactivate
Remove-Item -Recurse -Force .venv

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

---

# 6. PowerShell blocks activation

If:

```powershell
.\.venv\Scripts\Activate.ps1
```

is blocked by execution policy, you can activate for the current PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

---

# 7. Port 8000 already in use

If FastAPI cannot bind to port 8000, find the process:

```powershell
netstat -ano | findstr :8000
```

Then stop the relevant process if appropriate.

Alternatively, use the project's supported configuration rather than randomly changing frontend/backend ports.

---

# 8. Frontend shows `500 Internal Server Error`

A 500 response means the backend encountered an error.

Check the **backend terminal first**.

Do not assume the frontend is broken.

Typical causes include:

- Missing `GROQ_API_KEY`
- AI dependency mismatch
- Missing vector database
- Model/API failure
- Invalid backend configuration
- Runtime exception

Always inspect the backend traceback before changing frontend code.

---

# 9. RAG returns no useful results

Check whether:

```text
data/vector_db/
```

exists and contains the ChromaDB data.

If it is missing, run:

```powershell
python backend\02_chunk_and_embed.py
```

Then restart the backend.

---

# 10. Model download problems

Sentence Transformers may download models the first time.

Check:

- Internet connectivity
- Hugging Face availability
- Correct package versions
- Local cache permissions

Do not repeatedly reinstall the entire environment for a model-download problem.

---

# 11. Frontend cannot connect to backend

Verify:

```text
Backend:
http://localhost:8000

Frontend:
http://localhost:5173
```

Then inspect:

- Browser DevTools → Network
- Browser Console
- Backend terminal
- API endpoint URL
- CORS configuration

Do not change backend API contracts just to hide a frontend integration problem.

---

# ⚠️ Important Compatibility Notes

This repository currently contains an older AI dependency stack.

The following versions are particularly important:

```text
Python:
3.11

sentence-transformers:
2.2.2

huggingface-hub:
0.20.3

transformers:
4.35.2
```

Keep these versions stable unless you have tested a newer compatible stack.

A package upgrade can cause runtime incompatibilities even when installation succeeds.

---

# 🔐 Security Notes

Never commit:

```text
.env
API keys
JWT secrets
User credentials
Private legal documents
Database files containing sensitive user data
```

For a production deployment, additionally consider:

- HTTPS
- Secret management
- Strong JWT configuration
- Token expiration/rotation
- Rate limiting
- File type/size validation
- Malware scanning for uploads
- Authorization checks
- User-level data isolation
- Prompt-injection defenses
- Audit logging
- Secure CORS configuration
- Encryption at rest
- Secure database deployment

---

# ⚖️ Legal Safety

JuriSense should be treated as an **AI-assisted legal information and workflow system**.

AI output can contain:

- Incorrect interpretations
- Missing context
- Outdated information
- Retrieval errors
- Hallucinated claims

Legal responses should therefore be verified against authoritative sources and, where appropriate, reviewed by a qualified legal professional.

Do not present generated content as guaranteed legal advice.

---

# 📊 RAG Design

The project's retrieval strategy combines multiple retrieval signals.

```text
User Query
    │
    ▼
Query Processing
    │
    ├───────────────┐
    ▼               ▼
Vector Search      BM25
    │               │
    └───────┬───────┘
            ▼
      Candidate Merge
            │
            ▼
       CrossEncoder
        Re-ranking
            │
            ▼
       Top Context
            │
            ▼
           LLM
            │
            ▼
      Final Response
```

This is preferable to relying exclusively on semantic similarity because legal queries frequently contain exact terms such as:

- Section numbers
- Act names
- Case names
- Legal phrases

---

# 🧩 Multi-Agent Design

JuriSense separates several AI responsibilities.

```text
                   User Request
                        │
                        ▼
                     Triage
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Research       Drafting      Review
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                  Final Response
```

The benefit of specialization is better separation of responsibilities.

However, multi-agent systems also introduce:

- More latency
- More token usage
- Routing errors
- Context-management complexity
- Debugging complexity

For production, agents should only be used where dynamic workflow selection provides meaningful value.

---

# 🧪 Testing & Evaluation

Before production deployment, establish an evaluation dataset containing realistic legal queries.

### Retrieval metrics

- Recall@K
- Precision@K
- MRR
- nDCG

### Generation metrics

- Faithfulness
- Relevance
- Citation correctness
- Completeness
- Legal grounding

### System metrics

- Latency
- Error rate
- Token usage
- Cost per request
- Retrieval failure rate

Human/legal-expert review should be included for high-risk legal workflows.

---

# 🚢 Production Considerations

The current architecture is suitable as a development/prototype foundation, but production deployment should address:

### Infrastructure

- Docker
- Production ASGI deployment
- PostgreSQL where appropriate
- Redis/queue for long-running jobs
- Object storage for documents
- Centralized logging
- Monitoring
- Tracing

### AI reliability

- Evaluation pipeline
- Retrieval thresholds
- Citation validation
- Output validation
- Prompt-injection protection
- Model fallback
- Model/version management

### Scalability

Potential production flow:

```text
Client
  ↓
Load Balancer
  ↓
FastAPI
  ↓
Queue ──────────────┐
  ↓                 │
Workers             │
  ↓                 │
RAG / Agents        │
  ↓                 │
LLM                  │
  ↓                 │
Database / Storage ◄─┘
```

Do not introduce all of these components just for the sake of complexity. Add them when actual scale and reliability requirements justify them.

---

# 🛠️ Development Guidelines

When modifying the project:

1. Understand the existing architecture first.
2. Keep API contracts stable.
3. Avoid unnecessary dependency upgrades.
4. Keep secrets out of source control.
5. Test AI changes against representative queries.
6. Test retrieval independently from generation.
7. Log enough information to debug failures.
8. Avoid silently changing legal/business logic.
9. Keep frontend and backend responsibilities separated.
10. Prefer measured improvements over assumptions.

---

# 🔮 Future Improvements

Potential future work includes:

- Better domain-specific embeddings
- Improved structure-aware legal chunking
- Stronger reranking
- Citation verification
- OCR for scanned legal documents
- PostgreSQL migration
- Asynchronous job processing
- Redis caching
- Production vector database
- Automated RAG evaluation
- Human feedback loops
- Better observability
- Model routing
- Streaming responses
- Fine-grained authorization
- Document versioning
- Audit trails

---

# 🤝 Contributing

Contributions are welcome.

Recommended workflow:

```bash
git clone <repository-url>
cd JuriSense

# Create a feature branch
git checkout -b feature/your-feature

# Make changes
# Test locally

git add .
git commit -m "feat: describe your change"
git push origin feature/your-feature
```

Before opening a pull request:

- Verify the backend starts.
- Verify the frontend builds.
- Verify existing APIs still work.
- Verify no secrets are committed.
- Test affected AI workflows.
- Document breaking changes.

---

# 📜 License

See the repository's `LICENSE` file for licensing information.

---

# 👨‍💻 Project

**JuriSense — Indian Legal Intelligence Assistant**

Built with:

```text
Python
FastAPI
React
RAG
ChromaDB
Sentence Transformers
BM25
CrossEncoder
LangChain
Groq
SQLite
```

---

## ⭐ If You Find This Project Useful

Consider starring the repository and sharing feedback.

For issues, use the repository's issue tracker and include:

```text
Python version
OS
Installation command
Full error message
Backend traceback
Frontend console error
Steps to reproduce
```

This makes debugging substantially easier.

---

## Quick Start

For experienced users:

```powershell
# Root directory

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r backend\requirements.txt

# If Hugging Face compatibility error occurs:
python -m pip install "huggingface-hub==0.20.3" "transformers==4.35.2"

# Configure .env with GROQ_API_KEY

# Build vector DB if missing:
python backend\02_chunk_and_embed.py

# Terminal 1
cd backend
python api_server.py

# Terminal 2
cd jurisense-ui
npm install
npm run dev
```

Then open the Vite URL shown in the terminal.

---

> **JuriSense is intended for research, education, and AI-assisted legal workflows. Always verify important legal information against authoritative sources and obtain professional legal advice where necessary.**
