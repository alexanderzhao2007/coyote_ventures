-- Three-table design: each agent inserts into one table only (no updates).
-- Join key: url
--
-- 1. coyote_candidates      <- Discovery agent
-- 2. coyote_article_content  <- Harvester agent
-- 3. coyote_article_evaluations <- Judge agent

-- Table 1: Discovery agent inserts here
CREATE TABLE IF NOT EXISTS public.coyote_candidates (
  url text PRIMARY KEY,
  title text NOT NULL,
  source text,
  snippet text,
  published_date date,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.coyote_candidates IS 'Discovery: candidate articles from search. Insert only.';

-- Table 2: Harvester agent inserts here (url must exist in coyote_candidates)
CREATE TABLE IF NOT EXISTS public.coyote_article_content (
  url text PRIMARY KEY REFERENCES public.coyote_candidates(url) ON DELETE CASCADE,
  content text,
  extraction_status text,
  word_count int,
  author text,
  extracted_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.coyote_article_content IS 'Harvester: extracted content per article. Insert only.';

-- Table 3: Judge agent inserts here (url must exist in coyote_candidates)
CREATE TABLE IF NOT EXISTS public.coyote_article_evaluations (
  url text PRIMARY KEY REFERENCES public.coyote_candidates(url) ON DELETE CASCADE,
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

COMMENT ON TABLE public.coyote_article_evaluations IS 'Judge: relevance and intelligence fields. Insert only.';

-- View: join all three for digest/UI
CREATE OR REPLACE VIEW public.coyote_articles AS
SELECT
  c.url,
  c.title,
  c.source,
  c.snippet,
  c.published_date,
  c.created_at,
  ac.content,
  ac.extraction_status,
  ac.word_count,
  ac.author,
  ac.extracted_at,
  e.relevance_score,
  e.confidence_score,
  e.signal_type,
  e.thesis_sector,
  e.focus_area_tags,
  e.geography,
  e.companies_mentioned,
  e.exec_summary,
  e.why_it_matters,
  e.rejection_reason,
  e.sent_in_weekly_digest,
  e.evaluated_at
FROM public.coyote_candidates c
LEFT JOIN public.coyote_article_content ac ON ac.url = c.url
LEFT JOIN public.coyote_article_evaluations e ON e.url = c.url;

COMMENT ON VIEW public.coyote_articles IS 'Joined view for digest/UI. Read-only.';
