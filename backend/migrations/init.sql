CREATE TABLE IF NOT EXISTS tenders (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    title TEXT NOT NULL,
    buyer VARCHAR(255),
    state VARCHAR(120),
    category VARCHAR(120),
    estimated_value DOUBLE PRECISION,
    deadline TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    tender_url TEXT,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    raw_payload JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_tenders_source_external_id UNIQUE (source, external_id)
);

CREATE INDEX IF NOT EXISTS ix_tenders_deadline ON tenders(deadline);
CREATE INDEX IF NOT EXISTS ix_tenders_state ON tenders(state);
CREATE INDEX IF NOT EXISTS ix_tenders_source ON tenders(source);

CREATE TABLE IF NOT EXISTS alert_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    states TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_alert_subscriptions_email ON alert_subscriptions(email);

CREATE TABLE IF NOT EXISTS fetch_runs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(80) NOT NULL,
    status VARCHAR(40) NOT NULL,
    tenders_seen INTEGER NOT NULL DEFAULT 0,
    tenders_saved INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);
