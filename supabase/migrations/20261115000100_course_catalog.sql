BEGIN;
CREATE TABLE IF NOT EXISTS public.courses (
    code text PRIMARY KEY CHECK (code = upper(btrim(code))),
    title text NOT NULL CHECK (length(btrim(title)) > 0),
    department text NOT NULL CHECK (length(btrim(department)) > 0),
    description text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.courses FROM PUBLIC, anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.courses TO service_role;
NOTIFY pgrst, 'reload schema';
COMMIT;