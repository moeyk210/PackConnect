-- Canonical course codes: "csc510", "CSC-510" and " CSC 510 " all become "CSC 510".
-- Mirrors normalize_code() in backend/core/courses.py. Safe to re-run.
BEGIN;

CREATE OR REPLACE FUNCTION public.packconnect_normalize_code(raw text) RETURNS text
LANGUAGE sql IMMUTABLE AS $fn$
    SELECT CASE
        WHEN t ~ '^[A-Z]+[ -]*[0-9][A-Z0-9]*$'
            THEN regexp_replace(t, '^([A-Z]+)[ -]*([0-9][A-Z0-9]*)$', '\1 \2')
        ELSE t
    END
    FROM (SELECT btrim(regexp_replace(upper(raw), '\s+', ' ', 'g')) AS t) AS cleaned
$fn$;

-- 1. Remove rows that would become duplicates (same student, same canonical code),
--    keeping the oldest row of each group.
DELETE FROM public.completed_courses c
USING public.completed_courses keep
WHERE keep.student_id = c.student_id
  AND public.packconnect_normalize_code(keep.course_code) = public.packconnect_normalize_code(c.course_code)
  AND keep.id < c.id;

DELETE FROM public.current_courses c
USING public.current_courses keep
WHERE keep.student_id = c.student_id
  AND public.packconnect_normalize_code(keep.course_code) = public.packconnect_normalize_code(c.course_code)
  AND keep.id < c.id;

-- 2. Rewrite what is left (only rows that actually change).
UPDATE public.completed_courses
SET course_code = public.packconnect_normalize_code(course_code)
WHERE course_code <> public.packconnect_normalize_code(course_code);

UPDATE public.current_courses
SET course_code = public.packconnect_normalize_code(course_code)
WHERE course_code <> public.packconnect_normalize_code(course_code);

UPDATE public.advice_requests
SET course_code = public.packconnect_normalize_code(course_code)
WHERE course_code <> public.packconnect_normalize_code(course_code);

-- The helper only exists to run this migration.
DROP FUNCTION public.packconnect_normalize_code(text);

COMMIT;
