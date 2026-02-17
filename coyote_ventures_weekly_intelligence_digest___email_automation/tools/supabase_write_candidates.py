"""Tool for Discovery agent: insert candidate articles into Supabase coyote_candidates table (insert only)."""

import os
import json
from datetime import datetime
from typing import Type, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseWriteCandidatesInput(BaseModel):
    """Input for writing candidate articles to Supabase."""
    articles_json: str = Field(
        ...,
        description="JSON array of articles. Each object: url (required), title (required), source (optional), published_date (optional), snippet (optional)."
    )


def _parse_published_date(value: Optional[str]) -> Optional[str]:
    """Try to convert Serply-style date to YYYY-MM-DD for Postgres date column."""
    if not value or not value.strip():
        return None
    s = value.strip()
    # Already YYYY-MM-DD
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # Try common formats
    for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z", "%d %b %Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[: min(30, len(s))], fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


class SupabaseWriteCandidatesTool(BaseTool):
    """Discovery agent: insert-only into Supabase coyote_candidates. Duplicate URLs are skipped."""

    name: str = "supabase_write_candidates"
    description: str = (
        "Insert candidate articles into the Supabase coyote_candidates table (Discovery table). "
        "Call with a JSON array of articles: url (required), title (required), source (optional), published_date (optional), snippet (optional). "
        "Duplicate URLs are skipped. Returns the number of rows inserted."
    )
    args_schema: Type[BaseModel] = SupabaseWriteCandidatesInput

    def _run(self, articles_json: str) -> str:
        import sys
        try:
            data = json.loads(articles_json)
        except json.JSONDecodeError as e:
            print(f"[supabase_write_candidates] Invalid JSON: {e}", file=sys.stderr)
            return json.dumps(
                {
                    "error": f"Invalid JSON: {e}",
                    "received": 0,
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "skipped_missing_url": 0,
                }
            )

        # Accept either a JSON array or { "candidate_articles": [...] } from the agent's response format
        if isinstance(data, dict) and "candidate_articles" in data:
            data = data["candidate_articles"]
        if not isinstance(data, list):
            print(f"[supabase_write_candidates] Expected JSON array or {{candidate_articles: [...]}}, got {type(data).__name__}", file=sys.stderr)
            return json.dumps(
                {
                    "error": "articles_json must be a JSON array or object with 'candidate_articles' array",
                    "received": 0,
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "skipped_missing_url": 0,
                }
            )

        n_articles = len(data)
        print(f"[supabase_write_candidates] Called with {n_articles} articles.", file=sys.stderr)

        supabase_url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not key:
            msg = "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment"
            print(f"[supabase_write_candidates] {msg}", file=sys.stderr)
            return json.dumps(
                {
                    "error": msg,
                    "received": n_articles,
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "skipped_missing_url": 0,
                }
            )

        try:
            from supabase import create_client
            client = create_client(supabase_url, key)
        except Exception as e:
            return json.dumps(
                {
                    "error": f"Supabase client: {e}",
                    "received": n_articles,
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "skipped_missing_url": 0,
                }
            )

        inserted = 0
        skipped_duplicates = 0
        skipped_missing_url = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            url_val = item.get("url") or item.get("URL")
            title_val = item.get("title") or item.get("Title") or ""
            if not url_val:
                skipped_missing_url += 1
                continue
            source_val = item.get("source") or item.get("Source")
            pub_raw = item.get("published_date") or item.get("Published Date") or item.get("published_date")
            published_date_parsed = _parse_published_date(str(pub_raw)) if pub_raw else None
            snippet_val = item.get("snippet") or item.get("Snippet")

            row = {
                "url": url_val[:2048] if len(url_val) > 2048 else url_val,
                "title": (title_val or "Untitled")[:2048] if title_val else "Untitled",
                "source": source_val,
                "snippet": snippet_val,
                "published_date": published_date_parsed,
            }
            try:
                client.table("coyote_candidates").insert(row).execute()
                inserted += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
                    skipped_duplicates += 1
                    continue
                print(f"[supabase_write_candidates] Insert failed: {e}", file=sys.stderr)
                return json.dumps(
                    {
                        "error": str(e),
                        "received": n_articles,
                        "inserted": inserted,
                        "skipped_duplicates": skipped_duplicates,
                        "skipped_missing_url": skipped_missing_url,
                    }
                )

        if skipped_duplicates:
            print(f"[supabase_write_candidates] Inserted {inserted} rows, skipped {skipped_duplicates} duplicate URL(s).", file=sys.stderr)
        return json.dumps(
            {
                "received": n_articles,
                "inserted": inserted,
                "skipped_duplicates": skipped_duplicates,
                "skipped_missing_url": skipped_missing_url,
                "message": f"Inserted {inserted} rows into coyote_candidates.",
            }
        )
