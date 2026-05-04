ALTER TABLE tenders
  ADD COLUMN IF NOT EXISTS tender_id TEXT,
  ADD COLUMN IF NOT EXISTS link_type VARCHAR(10) DEFAULT 'search',
  ADD COLUMN IF NOT EXISTS link_verified BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_tenders_tender_id ON tenders(tender_id);
