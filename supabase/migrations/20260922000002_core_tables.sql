-- The SPEC.md §6 schema.
--
-- Every table enables RLS in the same migration that creates it; tools/check_rls.py
-- fails the build otherwise. Four tables then get an explicit public SELECT policy
-- per SETUP-PLATFORM.md §7; the rest stay RLS-on-with-no-policies, which is
-- deny-all and is the intended state for them.

-- ---------------------------------------------------------------------------
-- companies
-- ---------------------------------------------------------------------------

CREATE TABLE companies (
  id                        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  -- Lowercase, protocol/www/path/query stripped. Nullable because several
  -- discovery sources cannot supply one: Getro exposes only a slug (§7.2) and
  -- Wellfound needs a second hop (§7.7). A company with no resolvable domain is
  -- ingested and flagged, never dropped (C-1.8).
  canonical_domain          TEXT UNIQUE,
  name                      TEXT NOT NULL,
  is_climate                BOOLEAN NOT NULL DEFAULT FALSE,
  industry_tags             JSONB,
  has_open_roles_signal     BOOLEAN NOT NULL DEFAULT FALSE,
  ats_provider              TEXT,
  ats_token                 TEXT,
  ats_status                TEXT NOT NULL DEFAULT 'unmapped',
  mapping_confidence        TEXT,
  mapping_method            TEXT,
  -- Free text, not an enum: §8.4's `unsupported_ats:{name}` carries the ATS name,
  -- and that distribution is §18 measurement 2.
  mapping_failure_reason    TEXT,
  mapping_last_attempt_at   TIMESTAMPTZ,
  ats_last_success_at       TIMESTAMPTZ,
  ats_consecutive_failures  INTEGER NOT NULL DEFAULT 0,
  last_nonzero_postings_at  TIMESTAMPTZ,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT companies_ats_status_known
    CHECK (ats_status IN ('unmapped', 'ok', 'failing', 'unmappable')),
  CONSTRAINT companies_mapping_confidence_known
    CHECK (mapping_confidence IS NULL
           OR mapping_confidence IN ('verified', 'probable', 'weak'))
);

-- §8.3: map has_open_roles_signal first, so degradation lands where it matters
-- least. §12.9's health page groups by ats_status.
CREATE INDEX companies_mapping_queue_idx
  ON companies (ats_status, has_open_roles_signal DESC);

ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- company_sources
-- ---------------------------------------------------------------------------

CREATE TABLE company_sources (
  company_id            BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  -- builtin | climatebase | climatetechlist | getro | consider
  -- | wellfound | yc | greentown | manual
  source                TEXT NOT NULL,
  source_id             TEXT,
  source_metadata_json  JSONB,
  PRIMARY KEY (company_id, source)
);

ALTER TABLE company_sources ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- postings -- the hot table: open, plus closed under 30 days
-- ---------------------------------------------------------------------------

CREATE TABLE postings (
  id                     BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  company_id             BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  ats_job_id             TEXT NOT NULL,
  title_raw              TEXT NOT NULL,
  department_raw         TEXT,
  location_raw           TEXT,
  workplace_type_raw     TEXT,
  location_class         TEXT NOT NULL DEFAULT 'unknown',
  city_raw               TEXT,
  url                    TEXT,
  first_seen_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at              TIMESTAMPTZ,
  posted_at              TIMESTAMPTZ,
  content_hash           TEXT,
  is_repost              BOOLEAN NOT NULL DEFAULT FALSE,
  comp_data_quality      TEXT NOT NULL DEFAULT 'none',
  comp_raw_summary       TEXT,
  comp_best_annual_usd   INTEGER,
  comp_floor_annual_usd  INTEGER,
  comp_tier_count        INTEGER NOT NULL DEFAULT 0,

  UNIQUE (company_id, ats_job_id),

  CONSTRAINT postings_location_class_known
    CHECK (location_class IN ('remote', 'hybrid', 'onsite', 'unknown')),
  CONSTRAINT postings_comp_quality_known
    CHECK (comp_data_quality IN ('structured', 'parsed', 'none'))
)
-- §6 write amplification: last_seen_at is updated once a day on every live
-- posting. fillfactor leaves room on the page so those updates stay HOT and do
-- not rewrite index entries.
WITH (fillfactor = 85);

-- first_seen_at is THE date: the sort key and the "Posted" filter (§6, §12.2).
CREATE INDEX postings_first_seen_idx ON postings (first_seen_at DESC);
-- Archive sweeps by closed_at, never by first_seen_at: a role open 60 days is
-- still applicable, and archiving by posting date would hide live jobs (§6).
CREATE INDEX postings_closed_at_idx ON postings (closed_at) WHERE closed_at IS NOT NULL;
CREATE INDEX postings_company_idx ON postings (company_id);
-- §10's comp backfill scans exactly this set, so it is worth the one index.
CREATE INDEX postings_comp_backfill_idx ON postings (comp_data_quality, first_seen_at)
  WHERE closed_at IS NULL;

-- Deliberately absent: any index on last_seen_at. SPEC.md §6 forbids it -- an
-- index there would turn every daily liveness update into an index write, which
-- is the whole cost the fillfactor above exists to avoid.

ALTER TABLE postings ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- postings_archive -- closed 30+ days
-- ---------------------------------------------------------------------------

-- url and content_hash are dropped here on purpose (§6): the link is dead, and
-- repost matching moved to posting_hashes below, which outlives the archive move.
CREATE TABLE postings_archive (
  id                     BIGINT PRIMARY KEY,
  company_id             BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  ats_job_id             TEXT NOT NULL,
  title_raw              TEXT NOT NULL,
  department_raw         TEXT,
  location_raw           TEXT,
  workplace_type_raw     TEXT,
  location_class         TEXT,
  city_raw               TEXT,
  first_seen_at          TIMESTAMPTZ NOT NULL,
  last_seen_at           TIMESTAMPTZ NOT NULL,
  closed_at              TIMESTAMPTZ NOT NULL,
  posted_at              TIMESTAMPTZ,
  is_repost              BOOLEAN NOT NULL DEFAULT FALSE,
  comp_data_quality      TEXT NOT NULL DEFAULT 'none',
  comp_raw_summary       TEXT,
  comp_best_annual_usd   INTEGER,
  comp_floor_annual_usd  INTEGER,
  comp_tier_count        INTEGER NOT NULL DEFAULT 0
);

-- One index, per §6.
CREATE INDEX postings_archive_company_dept_idx
  ON postings_archive (company_id, department_raw);

ALTER TABLE postings_archive ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- posting_comp_tiers -- never dropped or trimmed; these are the asset (§11)
-- ---------------------------------------------------------------------------

CREATE TABLE posting_comp_tiers (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  posting_id   BIGINT NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
  tier_label   TEXT,
  min_amount   NUMERIC,
  max_amount   NUMERIC,
  currency     TEXT,
  period       TEXT,
  -- §11.1, and the reason this column exists before any data is collected: it is
  -- unrecoverable later. A backfill appends an observation rather than
  -- overwriting one, because a mid-posting range edit is signal.
  observed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

  CONSTRAINT posting_comp_tiers_period_known
    CHECK (period IS NULL OR period IN ('year', 'month', 'week', 'hour'))
);

CREATE INDEX posting_comp_tiers_posting_idx ON posting_comp_tiers (posting_id);

ALTER TABLE posting_comp_tiers ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- posting_hashes -- repost detection that survives the archive move (§6, §10)
-- ---------------------------------------------------------------------------

CREATE TABLE posting_hashes (
  content_hash  TEXT NOT NULL,
  company_id    BIGINT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  closed_at     TIMESTAMPTZ,
  PRIMARY KEY (content_hash, company_id)
);

ALTER TABLE posting_hashes ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- runs -- one row per pipeline run (§14)
-- ---------------------------------------------------------------------------

CREATE TABLE runs (
  id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  started_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at          TIMESTAMPTZ,
  companies_polled     INTEGER NOT NULL DEFAULT 0,
  http_ok              INTEGER NOT NULL DEFAULT 0,
  http_err             INTEGER NOT NULL DEFAULT 0,
  total_live_postings  INTEGER NOT NULL DEFAULT 0,
  new_postings         INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX runs_started_at_idx ON runs (started_at DESC);

ALTER TABLE runs ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- notifications_sent -- at-most-once per posting per profile (§13.1)
-- ---------------------------------------------------------------------------

CREATE TABLE notifications_sent (
  posting_id   BIGINT NOT NULL REFERENCES postings(id) ON DELETE CASCADE,
  -- Profile NAME only, never an email address. SPEC.md §6 states the rule
  -- predates the move off a committed database and survives it.
  profile      TEXT NOT NULL,
  sent_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (posting_id, profile),

  CONSTRAINT notifications_sent_profile_is_not_an_address
    CHECK (profile NOT LIKE '%@%')
);

ALTER TABLE notifications_sent ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- Policies
--
-- SETUP-PLATFORM.md §7's first row: companies, postings, postings_archive and
-- posting_comp_tiers get public SELECT; writes are the pipeline's alone. Every
-- other table stays RLS-enabled with zero policies, which denies everything.
--
-- No write policies are needed anywhere: the pipeline connects as the table owner
-- on the direct connection string and is not subject to RLS, and service_role
-- carries BYPASSRLS. Anything that is *not* one of those two gets only what is
-- granted below.
-- ---------------------------------------------------------------------------

CREATE POLICY companies_public_read ON companies FOR SELECT USING (true);
CREATE POLICY postings_public_read ON postings FOR SELECT USING (true);
CREATE POLICY postings_archive_public_read ON postings_archive FOR SELECT USING (true);
CREATE POLICY posting_comp_tiers_public_read ON posting_comp_tiers FOR SELECT USING (true);

-- A policy alone is not access: the table-level grant has to exist too, and the
-- baseline migration revoked it.
DO $$
DECLARE
  reader TEXT;
BEGIN
  FOREACH reader IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = reader) THEN
      EXECUTE format(
        'GRANT SELECT ON companies, postings, postings_archive, posting_comp_tiers TO %I',
        reader
      );
    END IF;
  END LOOP;
END
$$;
