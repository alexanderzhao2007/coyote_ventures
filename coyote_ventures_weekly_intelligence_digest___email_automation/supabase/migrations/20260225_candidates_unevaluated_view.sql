-- View: candidates that do not yet have an evaluation.
-- Use this for the judge so we only ever pull newest unevaluated articles (no re-evaluation).

DO $$
BEGIN
  IF to_regclass('public.coyote_candidates') IS NOT NULL
     AND to_regclass('public.coyote_article_evaluations') IS NOT NULL THEN

    CREATE OR REPLACE VIEW public.coyote_candidates_unevaluated AS
    SELECT
      c.id,
      c.url,
      c.title,
      c.source,
      c.published_date,
      c.created_at
    FROM public.coyote_candidates c
    LEFT JOIN public.coyote_article_evaluations e ON e.candidate_id = c.id
    WHERE e.candidate_id IS NULL;

    COMMENT ON VIEW public.coyote_candidates_unevaluated IS
      'Candidates with no row in coyote_article_evaluations. Query with ORDER BY created_at DESC for newest-first.';

  END IF;
END $$;
