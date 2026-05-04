ALTER TABLE tenders
  ADD COLUMN IF NOT EXISTS tender_id TEXT,
  ADD COLUMN IF NOT EXISTS link_type VARCHAR(10) DEFAULT 'search',
  ADD COLUMN IF NOT EXISTS link_verified BOOLEAN DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS idx_tenders_tender_id ON tenders(tender_id);

ALTER TABLE alert_subscriptions
  ADD COLUMN IF NOT EXISTS keyword TEXT DEFAULT 'printing',
  ADD COLUMN IF NOT EXISTS confirmed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS token TEXT,
  ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS last_alerted_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS is_confirmed BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS confirm_token TEXT,
  ADD COLUMN IF NOT EXISTS last_sent TIMESTAMPTZ;

UPDATE alert_subscriptions
SET keyword = COALESCE(keyword, keywords[1], 'printing')
WHERE keyword IS NULL;

ALTER TABLE alert_subscriptions
  ALTER COLUMN keyword SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_email_keyword
  ON alert_subscriptions(email, keyword);

CREATE UNIQUE INDEX IF NOT EXISTS uq_alert_subscriptions_token
  ON alert_subscriptions(token)
  WHERE token IS NOT NULL;
