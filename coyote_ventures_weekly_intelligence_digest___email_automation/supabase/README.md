# Supabase setup for weekly digest pipeline

## 1. Create the tables (3-table, insert-only)

Each agent writes to its own table; no updates, only inserts.

1. Open [Supabase Dashboard](https://supabase.com/dashboard) → your project.
2. Go to **SQL Editor** → **New query**.
3. Paste the contents of `schema_three_tables.sql` and run it.

This creates:

- **coyote_candidates** — Discovery agent inserts here (url, title, source, snippet, published_date).
- **coyote_article_content** — Harvester agent inserts here (url, content, extraction_status, word_count, author).
- **coyote_article_evaluations** — Judge agent inserts here (url, relevance_score, exec_summary, etc.).

The **coyote_articles** view joins all three for digest/UI.

## 2. Add env vars

In the folder where you run `crewai run` (parent `coyote_ventures`), add to your `.env`:

```
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
```

- **SUPABASE_URL**: Project Settings → API → Project URL.
- **SUPABASE_SERVICE_KEY**: Project Settings → API → `service_role` key (secret; do not commit).

## 3. Article extractor (Playwright)

The Harvester uses Playwright + Trafilatura. After installing dependencies, install the browser once:

```bash
playwright install chromium
```

## 4. Test Supabase insertion (optional)

From project root, with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` in `.env`:

```bash
python coyote_ventures_weekly_intelligence_digest___email_automation/scripts/test_supabase_insert.py
```

This inserts one test row into each of the 3 tables (same `url`). Verify in the Supabase dashboard; you can delete the test row from `coyote_candidates` (content and evaluations will CASCADE delete).
