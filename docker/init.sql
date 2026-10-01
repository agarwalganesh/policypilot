-- =============================================================
-- PolicyPilot — PostgreSQL Schema
-- Runs on container init via docker-entrypoint-initdb.d
-- =============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ─────────────────────────────────────────────────────────────
-- users
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'employee'
        CHECK (role IN ('employee', 'manager', 'hr', 'admin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- documents (canonical document identity)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    category VARCHAR(100),
    department VARCHAR(100),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- document_versions (one canonical document, multiple versions)
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'archived', 'draft')),
    effective_date DATE,
    last_updated DATE,
    source_file VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64),
    chunk_count INTEGER DEFAULT 0,
    indexed BOOLEAN NOT NULL DEFAULT FALSE,
    access_roles TEXT[] NOT NULL DEFAULT ARRAY['employee','manager','hr','admin'],
    uploaded_by UUID REFERENCES users(id),
    notes TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Ensure only one active version per document
CREATE UNIQUE INDEX IF NOT EXISTS uq_doc_active_version
    ON document_versions (document_id)
    WHERE status = 'active';

-- ─────────────────────────────────────────────────────────────
-- conversations
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- messages
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources JSONB,
    decision VARCHAR(20) CHECK (decision IN ('ANSWER', 'REFUSE', 'RETRIEVE_AGAIN', NULL)),
    confidence FLOAT,
    retry_count INTEGER DEFAULT 0,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- audit_logs
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    conversation_id UUID REFERENCES conversations(id),
    query TEXT NOT NULL,
    decision VARCHAR(20),
    sources JSONB,
    retry_count INTEGER DEFAULT 0,
    latency_ms INTEGER,
    agent_trace_id VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- evaluation_results
-- ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS evaluation_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_name VARCHAR(255),
    question TEXT NOT NULL,
    expected_answer TEXT,
    actual_answer TEXT,
    faithfulness_score FLOAT,
    relevance_score FLOAT,
    hallucination_score FLOAT,
    refusal_correct BOOLEAN,
    should_answer BOOLEAN,
    did_answer BOOLEAN,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────
-- Indexes
-- ─────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_doc_versions_document ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_versions_status ON document_versions(status);

-- ─────────────────────────────────────────────────────────────
-- Updated_at trigger function
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
