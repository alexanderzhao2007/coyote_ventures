# Before running `crewai run` or `python main.py run`

## 1. Environment variables (`.env` in project root: `coyote_ventures`)

| Variable | Used by | Where to get it |
|----------|---------|------------------|
| **OPENAI_API_KEY** | Crew LLMs and Thesis Article Comparison tool (all gpt-4o-mini) | [OpenAI API keys](https://platform.openai.com/api-keys) |
| **SUPABASE_URL** | All three Supabase write tools | Supabase Dashboard → Project Settings → API → Project URL |
| **SUPABASE_SERVICE_KEY** | All three Supabase write tools | Supabase Dashboard → Project Settings → API → `service_role` key (secret) |
| **SERPLY_API_KEY** | SerplyNewsSearchTool (Discovery agent) | [Serply](https://serply.io/) after signup |

Create a `.env` file in `coyote_ventures` (parent of this folder) with:

```
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SERPLY_API_KEY=your_serply_api_key
```

## 2. Supabase tables

Run the 3-table schema once in Supabase:

1. [Supabase Dashboard](https://supabase.com/dashboard) → your project → **SQL Editor** → New query.
2. Paste the contents of `supabase/schema_three_tables.sql` and run it.

This creates `coyote_candidates`, `coyote_article_content`, `coyote_article_evaluations`, and the `coyote_articles` view.

## 3. Dependencies and Playwright

From project root (`coyote_ventures`):

```bash
pip install -e .
playwright install chromium
```

## 4. Run from project root

```bash
cd c:\Users\alexa\OneDrive\Desktop\Projects\coyote_ventures
crewai run
```

or

```bash
python main.py run
```

**Use `python main.py run`** so `.env` is loaded from the project root (main.py loads it). If you use `crewai run`, ensure the shell has `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` set, or run from the same directory where `.env` is and that your CLI loads it.

## Troubleshooting: only 20 articles / no rows in Supabase

- **Only ~20 articles in terminal**  
  The agent may be doing only 4 searches (4×5=20) instead of 12, or truncating the list. Check the SEARCH LOG in the output: you should see 12 distinct queries. If you see fewer, the agent is not following the “12 required keywords” instruction.

- **No rows in `coyote_candidates` after Discovery**  
  1. **Tool not called** – The agent must call `supabase_write_candidates` with a JSON array of all articles. If it only prints the list and never calls the tool, you get 0 inserts.  
  2. **Env vars not set** – When the crew runs, `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` must be in the process environment. Run with `python main.py run` from the project root (so `.env` is loaded), or set the variables in the shell before `crewai run`.  
  3. **Wrong or missing table** – Supabase must have the 3-table schema applied. If the table is still `coyote_articles` (old schema) or missing, inserts will fail.

- **Diagnostic output**  
  The Supabase write tool logs to **stderr** when it runs. Look for:
  - `[supabase_write_candidates] Called with N articles.` – Confirms the tool was invoked and how many items were passed. If you never see this, the agent did not call the tool.
  - `[supabase_write_candidates] SUPABASE_URL and SUPABASE_SERVICE_KEY must be set` – Env vars are missing.
  - `[supabase_write_candidates] Insert failed: ...` – Table missing, wrong schema, or permission error.

## Quick sanity check (optional)

From project root:

```bash
python -c "
from coyote_ventures_weekly_intelligence_digest___email_automation.crew import CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.article_extractor import ArticleExtractorTool
import os
assert os.getenv('OPENAI_API_KEY'), 'OPENAI_API_KEY not set'
assert os.getenv('SUPABASE_URL'), 'SUPABASE_URL not set'
assert os.getenv('SUPABASE_SERVICE_KEY'), 'SUPABASE_SERVICE_KEY not set'
CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew()
print('OK: env and crew ready.')
"
```

## Estimated cost per full run (~60 articles)

Rough estimate for **one full run**. Actual cost depends on article count, token usage, and current API prices.

| Component | What happens | Estimated cost (USD) |
|-----------|----------------|------------------------|
| **Serply** | 12 news searches | **$0** (free tier: 300/mo) or ~\$0.02 (overage ~\$1.25/1k) |
| **OpenAI – Embeddings** | Thesis + ~85 articles, text-embedding-3-small (~\$0.02/1M tokens) | **~\$0.01–0.02** |
| **OpenAI – Thesis tool** | ~60 × GPT-4o-mini (thesis + article + JSON analysis) | **~\$0.02–0.05** |
| **OpenAI – Discovery agent** | gpt-4o-mini: task + 12 search results (5 each) + format + Supabase write | **~\$0.03–0.10** |
| **OpenAI – Harvester agent** | gpt-4o-mini: task + context + tool outputs | **~\$0.02–0.06** |
| **OpenAI – Judge agent** | gpt-4o-mini: task + full-text articles context + evaluations | **~\$0.04–0.12** |
| **OpenAI – Chat LLM** | gpt-4o-mini: handoff/summary (1–2 calls) | **~\$0.01–0.05** |
| **Playwright / Trafilatura** | Local; no API cost | **\$0** |
| **Supabase** | Inserts; free tier usually sufficient | **\$0** (within free tier) |

**Total per run: about \$0.15–\$0.45** (OpenAI dominates; Serply free if under 300 searches/month).

Check current prices: [OpenAI Pricing](https://platform.openai.com/docs/pricing), [Serply Pricing](https://serply.io/pricing).

## Time

A full run does: 12 Serply searches (5 results each), up to ~60 Playwright extractions, and up to ~60 thesis comparisons. Expect **roughly 20–45 minutes** depending on rate limits and network.
