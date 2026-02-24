#!/usr/bin/env python
"""
Standalone test for Supabase insertions (all 3 tables).
Run from project root with .env set: SUPABASE_URL, SUPABASE_SERVICE_KEY.

  cd c:\\Users\\alexa\\OneDrive\\Desktop\\Projects\\coyote_ventures
  python coyote_ventures_weekly_intelligence_digest___email_automation/scripts/test_supabase_insert.py
"""
import os
import sys

# Load .env from project root if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

def main():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        print("Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env or environment.", file=sys.stderr)
        sys.exit(1)

    from supabase import create_client
    client = create_client(url, key)

    test_url = "https://example.com/test-article-" + str(os.getpid())
    test_title = "Test article (insert test)"

    # 1) Insert candidate (no snippet column used anymore)
    print("1. Inserting into coyote_candidates...")
    try:
        client.table("coyote_candidates").insert(
            {
                "url": test_url,
                "title": test_title,
                "source": "Test",
                "published_date": "2026-02-01",
            }
        ).execute()
        print("   OK: coyote_candidates insert succeeded.")
    except Exception as e:
        print("   FAIL:", e)
        sys.exit(1)

    # 2) Insert content (requires url in candidates)
    print("2. Inserting into coyote_article_content...")
    try:
        client.table("coyote_article_content").insert({
            "url": test_url,
            "content": "This is test extracted content for the insert test.",
            "extraction_status": "COMPLETE",
            "word_count": 10,
            "author": "Test Author",
        }).execute()
        print("   OK: coyote_article_content insert succeeded.")
    except Exception as e:
        print("   FAIL:", e)
        sys.exit(1)

    # 3) Insert evaluation (requires url in candidates)
    print("3. Inserting into coyote_article_evaluations...")
    try:
        client.table("coyote_article_evaluations").insert({
            "url": test_url,
            "relevance_score": 75,
            "confidence_score": 80,
            "signal_type": "Market",
            "exec_summary": "Test exec summary.",
            "why_it_matters": "Test why it matters.",
            "sent_in_weekly_digest": False,
        }).execute()
        print("   OK: coyote_article_evaluations insert succeeded.")
    except Exception as e:
        print("   FAIL:", e)
        sys.exit(1)

    print("")
    print("All 3 tables: insert OK. Check Supabase Dashboard for url:", test_url)
    print("(You can delete this test row from coyote_candidates; content and evaluations will CASCADE.)")


if __name__ == "__main__":
    main()
