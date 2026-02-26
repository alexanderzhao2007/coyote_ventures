-- RLS policies for coyote_candidates and coyote_article_evaluations.
-- Run after 20260225_uuid_candidates_and_evaluations.sql.
-- Service role (SUPABASE_SERVICE_KEY) bypasses RLS; these protect anon key and allow future authenticated access.

-- Enable RLS on both tables
ALTER TABLE public.coyote_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coyote_article_evaluations ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- POLICIES FOR coyote_candidates
-- ============================================================================

CREATE POLICY "Service role can insert candidates"
    ON public.coyote_candidates
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "Service role can select candidates"
    ON public.coyote_candidates
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "Service role can update candidates"
    ON public.coyote_candidates
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can delete candidates"
    ON public.coyote_candidates
    FOR DELETE
    TO service_role
    USING (true);

CREATE POLICY "Authenticated users can read candidates"
    ON public.coyote_candidates
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can insert candidates"
    ON public.coyote_candidates
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- ============================================================================
-- POLICIES FOR coyote_article_evaluations
-- ============================================================================

CREATE POLICY "Service role can insert article_evaluations"
    ON public.coyote_article_evaluations
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "Service role can select article_evaluations"
    ON public.coyote_article_evaluations
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "Service role can update article_evaluations"
    ON public.coyote_article_evaluations
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can delete article_evaluations"
    ON public.coyote_article_evaluations
    FOR DELETE
    TO service_role
    USING (true);

CREATE POLICY "Authenticated users can read article_evaluations"
    ON public.coyote_article_evaluations
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can insert article_evaluations"
    ON public.coyote_article_evaluations
    FOR INSERT
    TO authenticated
    WITH CHECK (true);
