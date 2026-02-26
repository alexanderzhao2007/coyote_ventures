"""Tool for Harvester: read candidate articles from Supabase coyote_candidates (full list)."""

import os
import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseReadCandidatesInput(BaseModel):
    """Input for reading candidates (optional limit, offset, and unevaluated filter)."""
    limit: int = Field(
        default=60,
        description="Number of rows to return (default 60). Use limit=5 or 10 for batched evaluation; then use offset for the next batch.",
    )
    offset: int = Field(
        default=0,
        description="Rows to skip (pagination). Use 0 for first batch, then 5, 10, 15, ... Only the id from this response may be used for write_evaluations (as candidate_id).",
    )
    unevaluated_only: bool = Field(
        default=True,
        description="If true (default), return only candidates that do not yet have a row in coyote_article_evaluations—guarantees no re-evaluation. Newest first by created_at.",
    )


class SupabaseReadCandidatesTool(BaseTool):
    """Harvester: read all candidate articles from coyote_candidates so the full list is available regardless of task output length."""

    name: str = "supabase_read_candidates"
    description: str = (
        "Read candidate articles from Supabase. By default returns only candidates not yet in coyote_article_evaluations (newest first by created_at), so you never re-evaluate. "
        "Use limit and offset for pagination: limit=5, offset=0 then 5, 10, 15, ... until count is 0. "
        "Each article has: id (required—use as candidate_id in write_evaluations), url, title, source, published_date."
    )
    args_schema: Type[BaseModel] = SupabaseReadCandidatesInput

    def _run(self, limit: int = 60, offset: int = 0, unevaluated_only: bool = True) -> str:
        supabase_url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not key:
            return json.dumps({"error": "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", "articles": []})

        try:
            from supabase import create_client
            client = create_client(supabase_url, key)
        except Exception as e:
            return json.dumps({"error": str(e), "articles": []})

        try:
            limit = max(1, min(int(limit), 500))
            offset = max(0, int(offset))
            end = offset + limit - 1
            # Use view so we only get candidates with no evaluation row (newest first)
            table_or_view = "coyote_candidates_unevaluated" if unevaluated_only else "coyote_candidates"
            result = (
                client.table(table_or_view)
                .select("id, url, title, source, published_date")
                .order("created_at", desc=True)
                .range(offset, end)
                .execute()
            )
            rows = result.data or []
            # Normalize so each article has id (for write_evaluations candidate_id), url, title, etc.
            articles = []
            for r in rows:
                id_val = r.get("id")
                id_val = str(id_val).strip() if id_val is not None else ""
                url_val = r.get("url") or r.get("URL") or ""
                if isinstance(url_val, str):
                    url_val = url_val.strip()
                title_val = r.get("title") or r.get("Title") or ""
                source_val = r.get("source") or r.get("Source")
                pub = r.get("published_date")
                if hasattr(pub, "isoformat"):
                    pub = pub.isoformat()[:10] if pub else None
                elif pub is not None:
                    pub = str(pub)[:10]
                articles.append({
                    "id": id_val or "",
                    "url": url_val,
                    "title": title_val or "",
                    "source": source_val,
                    "published_date": pub,
                })
            return json.dumps({"articles": articles, "count": len(articles)})
        except Exception as e:
            return json.dumps({"error": str(e), "articles": []})
