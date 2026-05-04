CREATE TABLE tenders (
  id SERIAL PRIMARY KEY,
  ref_number TEXT UNIQUE NOT NULL,
  title TEXT NOT NULL,
  organisation TEXT,
  state VARCHAR(60),
  portal_source VARCHAR(30),
  category VARCHAR(60),
  value_inr NUMERIC(15,2) DEFAULT 0,
  emd_amount NUMERIC(15,2) DEFAULT 0,
  bid_end_date TIMESTAMPTZ,
  published_date TIMESTAMPTZ,
  portal_url TEXT,
  tender_id TEXT,
  link_type VARCHAR(10) DEFAULT 'search',
  link_verified BOOLEAN DEFAULT FALSE,
  keywords TEXT[],
  relevance_score SMALLINT DEFAULT 50,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  is_active BOOLEAN DEFAULT TRUE,
  search_vector TSVECTOR GENERATED ALWAYS AS
    (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(organisation,''))) STORED
);
CREATE INDEX idx_tenders_deadline  ON tenders(bid_end_date);
CREATE INDEX idx_tenders_state     ON tenders(state);
CREATE INDEX idx_tenders_portal    ON tenders(portal_source);
CREATE INDEX idx_tenders_category  ON tenders(category);
CREATE INDEX idx_tenders_fts       ON tenders USING GIN(search_vector);
CREATE INDEX idx_tenders_keywords  ON tenders USING GIN(keywords);
CREATE INDEX idx_tenders_tender_id ON tenders(tender_id);

CREATE TABLE alert_subscriptions (
  id SERIAL PRIMARY KEY,
  email TEXT NOT NULL,
  whatsapp TEXT,
  keywords TEXT[] DEFAULT ARRAY['printing'],
  states TEXT[] DEFAULT ARRAY[]::TEXT[],
  frequency VARCHAR(10) DEFAULT 'daily',
  is_active BOOLEAN DEFAULT TRUE,
  last_sent TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE fetch_logs (
  id SERIAL PRIMARY KEY,
  portal VARCHAR(30),
  keyword_used TEXT,
  fetched_at TIMESTAMPTZ DEFAULT NOW(),
  tenders_found INTEGER DEFAULT 0,
  new_added INTEGER DEFAULT 0,
  status VARCHAR(10),
  error_msg TEXT
);
