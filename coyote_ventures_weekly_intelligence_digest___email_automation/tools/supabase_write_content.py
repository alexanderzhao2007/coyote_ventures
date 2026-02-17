"""Tool for Harvester agent: insert extracted article content into Supabase coyote_article_content (insert only)."""

import os
import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseWriteContentInput(BaseModel):
    """Input for writing extracted content to Supabase."""
    articles_json: str = Field(
        ...,
        description="JSON array of extracted articles. Each object: url (required), content (full text), extraction_status (e.g. COMPLETE/PARTIAL), word_count (int), author (optional)."
    )


def _truncate(s: str | None, max_len: int) -> str | None:
    if s is None:
        return None
    return s[:max_len] if len(s) > max_len else s


class SupabaseWriteContentTool(BaseTool):
    """Harvester agent: insert-only into Supabase coyote_article_content. Duplicate url skipped."""

    name: str = "supabase_write_content"
    description: str = (
        "Insert extracted article content into the Supabase coyote_article_content table (Harvester table). "
        "Call with a JSON array of objects: url (required), content (full text), extraction_status (COMPLETE/PARTIAL), word_count (int), author (optional). "
        "Each url must already exist in coyote_candidates. Duplicate urls are skipped."
    )
    args_schema: Type[BaseModel] = SupabaseWriteContentInput

    def _run(self, articles_json: str) -> str:
        try:
            data = json.loads(articles_json)
            if not isinstance(data, list):
                data = [data] if isinstance(data, dict) else []
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}", "inserted": 0})

        supabase_url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not key:
            return json.dumps({"error": "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", "inserted": 0})

        try:
            from supabase import create_client
            client = create_client(supabase_url, key)
        except Exception as e:
            return json.dumps({"error": f"Supabase client: {e}", "inserted": 0})

        inserted = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            url_val = item.get("url") or item.get("URL")
            if not url_val:
                continue
            content_val = item.get("content") or item.get("text") or item.get("extracted_text")
            status = item.get("extraction_status") or "COMPLETE"
            word_count = item.get("word_count")
            if word_count is not None and not isinstance(word_count, int):
                try:
                    word_count = int(word_count)
                except (TypeError, ValueError):
                    word_count = None
            author_val = item.get("author")

            row = {
                "url": url_val[:2048] if len(url_val) > 2048 else url_val,
                "content": _truncate(content_val, 500_000),
                "extraction_status": (status or "COMPLETE")[:64],
                "word_count": word_count,
                "author": _truncate(author_val, 512) if author_val else None,
            }
            try:
                client.table("coyote_article_content").insert(row).execute()
                inserted += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
                    continue
                if "foreign key" in str(e).lower() or "23503" in str(e):
                    continue
                return json.dumps({"error": str(e), "inserted": inserted})

        return json.dumps({"inserted": inserted, "message": f"Inserted {inserted} rows into coyote_article_content."})
