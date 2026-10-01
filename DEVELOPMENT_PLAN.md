# PolicyPilot — Development Plan

> **Evidence-Grounded Enterprise Policy & Knowledge Assistant**
> Physics Wallah Internal AI Tool

---

## Document Inventory Analysis

### Confirmed Duplicate Files (identical MD5)

| Original File | Duplicate | Action |
|---|---|---|
| `1764592835_GROUP_MEDICAL_COVERAGE_POLICY451.pdf` | `GROUP MEDICAL COVERAGE POLICY.pdf` | Keep original; mark duplicate as archived |
| `1773829923_Updated_document_-_AI_SOP_(1)671.docx` | `Updated document - AI SOP (1).docx` | Keep original; mark duplicate as archived |

### New Documents (numbered prefix = newer uploads from system)

| Numbered File | Inferred Policy | Status |
|---|---|---|
| `1786597140_REWARDS_AND_RECOGNITION_POLICY_(1)_(2)394.docx` | Rewards & Recognition Policy | **New** |
| `1790256906_Leave_Policy_2026_-_Final_FTP_Updated593.pdf` | Leave Policy 2026 | **Newer version** |
| `1790406164_POSH_Policy-_Revised_(2)920.pdf` | POSH Policy (Revised) | **New** |

### Total: 44 unique policies (2 archived duplicates, 3 newly discovered policies)

---

## Architecture Decisions

### Decision 1: Flask (not FastAPI)
User explicitly specified Flask. Using Jinja2 for server-rendered pages + REST JSON endpoints for AJAX/streaming.

### Decision 2: Ollama for LLM and Embeddings
No paid API required. Both LLM and embedding model are configurable via .env.

### Decision 3: ChromaDB for Vector Store
Persistent ChromaDB instance in Docker. Metadata filtering for RBAC and version filtering.

### Decision 4: Evidence-First Agentic Design
LangGraph orchestrates every query. Simple retrieve-then-answer is prohibited by design.

### Decision 5: Semantic Chunking Deferred
Initial: RecursiveCharacterTextSplitter. Factory pattern allows swapping chunker later.

### Decision 6: RBAC via JWT + Document Metadata
Access control at retriever level using ChromaDB metadata where filters.

### Decision 7: LangSmith Optional
All LangSmith calls guarded by if settings.LANGSMITH_TRACING. App works without LangSmith.

---

## Implementation Phases

### PHASE 1 - Project Skeleton (current)
- [x] Directory structure
- [x] DEVELOPMENT_PLAN.md
- [ ] .env.example
- [ ] requirements.txt
- [ ] Docker Compose
- [ ] Database schema (SQL)
- [ ] Flask app skeleton

### PHASE 2 - Document Ingestion Pipeline
- [ ] PDF loader (PyMuPDF)
- [ ] DOCX loader
- [ ] Metadata extractor
- [ ] Text cleaner
- [ ] Chunker (RecursiveCharacterTextSplitter)
- [ ] Embedding generator (local Ollama)
- [ ] ChromaDB indexer
- [ ] Duplicate detector

### PHASE 3 - Basic RAG
- [ ] ChromaDB retriever
- [ ] Metadata filtering
- [ ] Basic answer generator
- [ ] Citation formatter

### PHASE 4 - LangGraph Agent
- [ ] AgentState definition
- [ ] All nodes (query_analyzer, access_checker, retriever, evidence_validator, answer_generator, answer_validator, citation_generator, refusal)
- [ ] Graph edges (conditional)

### PHASE 5 - Corrective RAG
- [ ] Query refinement strategies
- [ ] Retry logic with max_retries
- [ ] Fallback to refusal

### PHASE 6 - Conversational Memory
- [ ] Conversation history (PostgreSQL)
- [ ] Follow-up query handling

### PHASE 7 - Authentication and RBAC
- [ ] JWT auth middleware
- [ ] Role-based document access

### PHASE 8 - Admin Dashboard
- [ ] Document upload, versioning, re-index

### PHASE 9 - LangSmith Integration
### PHASE 10 - DeepEval Integration
### PHASE 11 - Security and Hardening
### PHASE 12 - UI/UX Polish + README

---

## RBAC Document Access Matrix

| Role | HR Policies | IT Policies | Finance | Compliance |
|---|---|---|---|---|
| employee | Yes | Yes | Yes (general) | Yes |
| manager | Yes | Yes | Yes | Yes |
| hr | Yes | Yes | Yes | Yes |
| admin | Yes | Yes | Yes | Yes |

---

## Evidence Scoring Thresholds

| Threshold | Default Value | Env Var |
|---|---|---|
| Minimum evidence score to answer | 0.65 | EVIDENCE_THRESHOLD |
| Top-K retrieval | 5 | RETRIEVAL_TOP_K |
| Maximum corrective RAG retries | 2 | MAX_RETRIES |
| Minimum chunk similarity | 0.4 | MIN_SIMILARITY |
