BEGIN;
-- One row per sign-in. The signed session cookie carries the id; logout revokes
-- the row so a copied cookie stops working on the server.
CREATE TABLE IF NOT EXISTS public.auth_sessions (
 id text PRIMARY KEY,
 student_id bigint NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
 created_at timestamptz NOT NULL DEFAULT now(),
 revoked_at timestamptz
);
CREATE INDEX IF NOT EXISTS auth_sessions_student ON public.auth_sessions(student_id);
ALTER TABLE public.auth_sessions ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.auth_sessions FROM PUBLIC, anon, authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON TABLE public.auth_sessions TO service_role;
COMMIT;
