-- UUID-based workflow: coyote_candidates gets auto-generated id; evaluations reference candidate by id.
-- Run after clearing tables. Only coyote_candidates and coyote_article_evaluations are used in this workflow.

-- Drop view first (depends on evaluations)
DROP VIEW IF EXISTS public.coyote_candidates_unevaluated;

-- Drop tables (order: evaluations then candidates because of FK)
DROP TABLE IF EXISTS public.coyote_article_evaluations;
DROP TABLE IF EXISTS public.coyote_candidates;

-- Table 1: Discovery agent inserts here. id is auto-generated; url is unique for dedupe.
CREATE TABLE public.coyote_candidates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  url text NOT NULL,
  title text NOT NULL,
  source text,
  published_date date,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT coyote_candidates_url_key UNIQUE (url)
);

COMMENT ON TABLE public.coyote_candidates IS 'Discovery: candidate articles. Each row gets a unique id; evaluations reference this id.';

-- Table 2: Judge agent inserts here. candidate_id references coyote_candidates(id).
CREATE TABLE public.coyote_article_evaluations (
  candidate_id uuid PRIMARY KEY REFERENCES public.coyote_candidates(id) ON DELETE CASCADE,
  relevance_score numeric,
  confidence_score numeric,
  signal_type text,
  thesis_sector text,
  focus_area_tags text,
  geography text,
  companies_mentioned text,
  exec_summary text,
  why_it_matters text,
  rejection_reason text,
  sent_in_weekly_digest boolean NOT NULL DEFAULT false,
  evaluated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.coyote_article_evaluations IS 'Judge: one evaluation per candidate, linked by candidate_id (uuid).';

-- View: candidates that do not yet have an evaluation (for read_candidates with unevaluated_only=true).
CREATE VIEW public.coyote_candidates_unevaluated AS
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
