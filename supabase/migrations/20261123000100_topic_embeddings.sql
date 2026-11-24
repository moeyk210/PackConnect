-- Meaning-based topic matching (issue #3).
-- Each student's advice topics get a numeric "fingerprint" (384 numbers from a
-- small language model), so search can match topics by meaning, not only by
-- shared words. pgvector stores the fingerprints and compares them.
-- The extension lives in the "extensions" schema, where Supabase keeps extensions.
BEGIN;
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA extensions;
ALTER TABLE public.students ADD COLUMN IF NOT EXISTS topic_embedding extensions.vector(384);
COMMIT;
