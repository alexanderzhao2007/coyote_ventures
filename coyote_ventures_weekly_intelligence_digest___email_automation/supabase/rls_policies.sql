-- Row Level Security (RLS) Policies for Coyote Ventures Tables
-- 
-- IMPORTANT: Service role keys bypass RLS entirely, so these policies primarily:
-- 1. Protect against accidental use of anon keys
-- 2. Prepare for future authenticated access patterns
-- 3. Provide defense in depth security
--
-- Current operations using SUPABASE_SERVICE_KEY will continue to work regardless of RLS.

-- Enable RLS on all three tables
ALTER TABLE public.coyote_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coyote_article_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coyote_article_evaluations ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- POLICIES FOR coyote_candidates
-- ============================================================================

-- Policy: Allow service role full access (INSERT, SELECT, UPDATE, DELETE)
-- Note: Service role bypasses RLS, but this policy provides explicit documentation
-- and works if RLS behavior changes or for other service role scenarios
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

-- Policy: Allow authenticated users to read candidates (for future web UI)
CREATE POLICY "Authenticated users can read candidates"
    ON public.coyote_candidates
    FOR SELECT
    TO authenticated
    USING (true);

-- Policy: Allow authenticated users to insert candidates (if needed for future web UI)
CREATE POLICY "Authenticated users can insert candidates"
    ON public.coyote_candidates
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- ============================================================================
-- POLICIES FOR coyote_article_content
-- ============================================================================

-- Service role policies for article_content
CREATE POLICY "Service role can insert article_content"
    ON public.coyote_article_content
    FOR INSERT
    TO service_role
    WITH CHECK (true);

CREATE POLICY "Service role can select article_content"
    ON public.coyote_article_content
    FOR SELECT
    TO service_role
    USING (true);

CREATE POLICY "Service role can update article_content"
    ON public.coyote_article_content
    FOR UPDATE
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role can delete article_content"
    ON public.coyote_article_content
    FOR DELETE
    TO service_role
    USING (true);

-- Authenticated user policies for article_content
CREATE POLICY "Authenticated users can read article_content"
    ON public.coyote_article_content
    FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Authenticated users can insert article_content"
    ON public.coyote_article_content
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- ============================================================================
-- POLICIES FOR coyote_article_evaluations
-- ============================================================================

-- Service role policies for article_evaluations
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

-- Authenticated user policies for article_evaluations
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

-- ============================================================================
-- VIEW SECURITY: coyote_articles
-- ============================================================================
--
-- The view 'coyote_articles' is read-only and automatically inherits RLS from
-- its underlying tables (coyote_candidates, coyote_article_content, 
-- coyote_article_evaluations).
--
-- When querying the view:
-- 1. RLS policies are checked on ALL three underlying tables
-- 2. A user can read from the view ONLY if they have SELECT permission on
--    all three tables (via RLS policies)
-- 3. Since the view is read-only, only SELECT policies matter
--
-- Current behavior:
-- - Service role: Can read from view (has SELECT policies on all tables)
-- - Authenticated users: Can read from view (has SELECT policies on all tables)
-- - Anonymous users: Cannot read from view (no SELECT policies)
--
-- No additional RLS configuration needed for the view itself. The view uses
-- SECURITY INVOKER (default), meaning it runs with the permissions of the
-- user querying it, which is the correct behavior for RLS.

-- ============================================================================
-- NOTES
-- ============================================================================
-- 
-- Anonymous access is blocked by default (no policies for anon role).
-- If you need anonymous read access in the future, add policies like:
--
-- CREATE POLICY "Anonymous can read candidates"
--     ON public.coyote_candidates
--     FOR SELECT
--     TO anon
--     USING (true);
--
-- (You would need similar policies for the other two tables if you want
-- anonymous users to be able to query the coyote_articles view.)
