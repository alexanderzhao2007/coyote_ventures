-- One-time: remove duplicate rows (same url) from two runs, then ensure one row per url.
-- Run this in Supabase SQL Editor if you see repeated articles from multiple automation runs.
--
-- Step 1: Dedupe coyote_article_evaluations (keep latest evaluated_at per url, even though
--          candidate_id is now the primary key). We derive url from coyote_candidates.
-- Step 2: Dedupe coyote_candidates (keep latest created_at per url)
-- Step 3: Ensure PRIMARY KEY / uniqueness so future runs cannot insert duplicate urls.

-- =============================================================================
-- STEP 1: coyote_article_evaluations — keep one row per url (latest evaluated_at)
-- =============================================================================
-- If your table already has url as PRIMARY KEY, this block does nothing harmful.
-- If you have duplicates, this deletes older duplicates.

DELETE FROM public.coyote_article_evaluations a
USING public.coyote_article_evaluations b
JOIN public.coyote_candidates ca ON ca.id = a.candidate_id
JOIN public.coyote_candidates cb ON cb.id = b.candidate_id
WHERE ca.url = cb.url
  AND a.evaluated_at < b.evaluated_at;

-- =============================================================================
-- STEP 2: coyote_candidates — keep one row per url (latest created_at)
-- =============================================================================
-- Evaluations reference candidates by candidate_id; after this, each url has one
-- surviving candidate row (the one with the latest created_at), and any evaluations
-- for deleted candidates are removed via ON DELETE CASCADE.

DELETE FROM public.coyote_candidates c
USING public.coyote_candidates b
WHERE c.url = b.url
  AND c.created_at < b.created_at;

-- =============================================================================
-- STEP 3: Ensure one row per url going forward (if not already enforced)
-- =============================================================================
-- In the UUID schema, coyote_candidates.url already has a UNIQUE constraint
-- (coyote_candidates_url_key). If you created tables differently, you can still
-- enforce uniqueness on url with:
--
-- ALTER TABLE public.coyote_candidates ADD CONSTRAINT coyote_candidates_url_key UNIQUE (url);
