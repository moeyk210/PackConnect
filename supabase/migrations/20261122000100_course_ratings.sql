BEGIN;
-- Optional 1-5 course ratings collected with advice feedback (story 3.4).
-- They describe the course, not the advisor, and are only ever shown as
-- averages on a course page, and only once enough students have rated.
ALTER TABLE public.advice_feedback
 ADD COLUMN IF NOT EXISTS workload_rating smallint CHECK (workload_rating BETWEEN 1 AND 5),
 ADD COLUMN IF NOT EXISTS difficulty_rating smallint CHECK (difficulty_rating BETWEEN 1 AND 5);
NOTIFY pgrst, 'reload schema';
COMMIT;
