-- Default-deny, established before a single table exists.
--
-- SETUP-PLATFORM.md §6: "The RLS baseline should be the first migration, before the
-- postings tables. It is much easier to start default-deny than to retrofit it."
-- §7 calls this the single highest-value security step, on the grounds that the
-- realistic breach path is a table shipped with RLS off, not disk theft.
--
-- `anon` and `authenticated` are the roles reachable from outside the database
-- through PostgREST. Nothing in the pre-platform build reads Postgres from a
-- browser at all -- the dashboard fetches static JSON (SPEC.md §12.8), and the
-- project's Data API has "automatically expose new tables" switched off -- so the
-- baseline is that those roles get nothing until a later migration grants it
-- deliberately, table by table.
--
-- The pipeline itself connects on the direct connection string as the table owner
-- and is unaffected by any of this, which is the intended split: one writer that
-- owns the schema, and readers that must be granted access one table at a time.

DO $$
BEGIN
  -- Guard on role existence so this migration also applies cleanly to a plain
  -- Postgres (a throwaway container for the integration test, say), where
  -- Supabase's roles are simply absent.
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON SCHEMA public FROM anon;
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;
    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon;

    -- USAGE only: without it a later GRANT SELECT on a specific table cannot be
    -- reached at all. It conveys no access to anything by itself.
    GRANT USAGE ON SCHEMA public TO anon;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM anon;
  END IF;

  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON SCHEMA public FROM authenticated;
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM authenticated;
    REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM authenticated;

    GRANT USAGE ON SCHEMA public TO authenticated;

    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM authenticated;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM authenticated;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM authenticated;
  END IF;
END
$$;
