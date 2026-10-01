# PolicyPilot
### Evidence-Grounded Enterprise Policy & Knowledge Assistant
**Physics Wallah Internal AI Tool**

---

PolicyPilot is a production-style enterprise AI application that answers employee questions using ONLY authorized company policy documents. It never invents company policy.

> **Core Principle**: If the answer cannot be supported by available company documents, the system refuses to answer.

---

## Problem Statement

Generic AI chatbots are dangerous for enterprise HR/policy use because they:
- Hallucinate company policies that don't exist
- Mix general knowledge with company-specific rules
- Provide no citations or audit trail
- Cannot distinguish between policy versions

PolicyPilot solves this by building an **evidence-first** agentic system.

---

## Architecture

`mermaid
graph TD
    U[Employee] --> Q[Query]
    Q --> QA[Query Analyzer]
    QA --> AC[Access Checker / RBAC]
    AC --> R[Retriever + ChromaDB]
    R --> EV[Evidence Validator]
    EV --> COND{Evidence Sufficient?}
    COND -->|YES| AG[Answer Generator]
    COND -->|NO - retries left| CRAG[Corrective RAG]
    CRAG --> R
    COND -->|NO - max retries| REF[Refusal Node]
    AG --> AV[Answer Validator]
    AV --> CG[Citation Generator]
    CG --> RESP[Response to User]
    REF --> RESP
`

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Flask + Jinja2 + HTML5 + CSS3 + Vanilla JS |
| Backend | Python + Flask |
| AI Orchestration | LangGraph |
| AI Framework | LangChain |
| LLM | Ollama (local, configurable) |
| Embeddings | Ollama local models |
| Vector DB | ChromaDB |
| Database | PostgreSQL |
| Document Processing | PyMuPDF + python-docx |
| Evaluation | DeepEval |
| Observability | LangSmith (optional) |
| Containerization | Docker + Docker Compose |

---

## Document Coverage

PolicyPilot indexes all 44 Physics Wallah policy documents across categories:

- HR: Leave, Attendance, Probation, Separation, PIP, IJDP, POSH
- Finance: Travel, Reimbursement, VPF, TDS, Asset Allocation
- Compliance: AML, Anti-Corruption, Code of Conduct, Whistleblower
- IT: Acceptable Usage, Vibe Coding, Vulnerability Management, AI SOP
- Benefits: Group Medical, GTLI, PW Pathshala
- And more...

---

## LangGraph Agent Flow

`
START
  -> query_analyzer      (extract intent, category, temporal scope)
  -> access_checker      (RBAC validation)
  -> retriever           (ChromaDB with metadata filtering)
  -> evidence_validator  (LLM-based sufficiency check)
  -> [conditional]
      if SUFFICIENT:
          -> answer_generator
          -> answer_validator
          -> citation_generator
          -> END
      if INSUFFICIENT + retries left:
          -> corrective_rag (query refinement)
          -> retriever (loop)
      if INSUFFICIENT + max retries:
          -> refusal
          -> END
`

---

## Corrective RAG

When initial retrieval is insufficient, PolicyPilot applies:

1. **Filler word removal** — strips conversational noise
2. **Keyword extraction** — maps to policy-specific terms
3. **Synonym expansion** — uses domain-specific synonyms
4. **PW-specific prefix** — adds organizational context

Max retries is configurable via MAX_RETRIES env var.

---

## Hallucination Prevention

The system uses multiple layers:

1. **Evidence Validator** — LLM checks if retrieved chunks actually support the question
2. **Confidence Threshold** — Configurable minimum score (default 0.65) to answer
3. **Answer Validator** — Post-generation check for unsupported claims
4. **Evidence-only System Prompt** — Strictly prohibits using general knowledge
5. **Refusal Node** — Dedicated refusal with helpful alternatives

---

## RBAC

| Role | Access |
|---|---|
| employee | All general policies |
| manager | + sensitive HR content |
| hr | All HR policies |
| admin | All documents + admin dashboard |

---

## Document Versioning

- Multiple versions tracked per document
- Only ctive versions used for current policy questions
- rchived versions accessible for historical queries
- Duplicate detection via MD5 file hashing
- Two confirmed duplicates identified and archived in PW document set

---

## Docker Setup

`ash
# 1. Copy environment file
cp .env.example .env
# Edit .env with your JWT_SECRET and FLASK_SECRET_KEY

# 2. Start all services
docker-compose up -d

# 3. Wait for Ollama to pull models (~5-10 min on first run)
docker-compose logs -f ollama_init

# 4. Seed the database
docker-compose exec backend python scripts/seed_database.py

# 5. Copy PW policy documents to documents/raw/
# 6. Ingest documents
docker-compose exec backend python scripts/ingest_documents.py

# 7. Open http://localhost:5000
`

---

## Local Setup (without Docker)

`ash
# Prerequisites: Python 3.11+, PostgreSQL, ChromaDB, Ollama

# 1. Clone and setup
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with local connection strings

# 3. Start Ollama and pull models
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 4. Run database migrations
# (tables are created by Docker init.sql or manually)

# 5. Seed database
python scripts/seed_database.py

# 6. Ingest documents
python scripts/ingest_documents.py --dir "PW POLICY/"

# 7. Start Flask
python -m backend.main
`

---

## Environment Variables

See .env.example for all configuration options. Key variables:

| Variable | Description |
|---|---|
| OLLAMA_MODEL | LLM model name (default: llama3.2:3b) |
| EMBEDDING_MODEL | Embedding model (default: nomic-embed-text) |
| EVIDENCE_THRESHOLD | Min confidence to answer (default: 0.65) |
| MAX_RETRIES | Corrective RAG retries (default: 2) |
| RETRIEVAL_TOP_K | Documents to retrieve (default: 5) |
| LANGSMITH_TRACING | Enable LangSmith tracing (default: false) |
| JWT_SECRET | JWT signing secret (required) |

---

## API Documentation

### Auth
- POST /auth/login — Get JWT token
- POST /auth/register — Register new user
- GET /auth/me — Current user info

### Chat
- POST /chat — Standard chat (JSON response)
- POST /chat/stream — Streaming chat (SSE)
- GET /chat/conversations — List conversations
- GET /chat/conversations/{id}/messages — Get messages

### Documents
- POST /documents/upload — Upload policy (HR+ role)
- GET /documents — List all documents
- GET /documents/{id} — Document details
- POST /documents/{id}/archive — Archive document
- POST /documents/{id}/reindex — Re-index (admin only)

### Admin
- GET /admin/analytics — Platform metrics
- GET /admin/audit-logs — Audit log with pagination
- GET /admin/users — All users

### Health
- GET /health — Service health check

---

## Testing

`ash
# Unit tests
pytest tests/unit/ -v

# All tests
pytest tests/ -v

# DeepEval evaluation
pytest backend/evaluation/deepeval_tests.py -v

# Refusal accuracy only
pytest backend/evaluation/deepeval_tests.py -v -k "refusal"
`

---

## Evaluation Methodology

100-question dataset:
- **70 answerable questions** — covering all PW policy categories
- **30 unanswerable questions** — testing hallucination resistance

Metrics:
- Faithfulness (DeepEval)
- Answer Relevance (DeepEval)
- Hallucination (DeepEval)
- Refusal Accuracy (custom metric)

---

## Future Improvements

- [ ] Semantic chunking (sentence-transformer based)
- [ ] Multi-modal support (scanned PDF via OCR)
- [ ] Policy change notifications
- [ ] Slack/Teams integration
- [ ] Real-time policy update webhooks
- [ ] Automated policy expiry alerts
- [ ] Fine-tuned embedding model on PW domain
- [ ] GraphRAG for policy relationship mapping
