"""Tool for Harvester: read candidate articles from Supabase coyote_candidates (full list)."""

import os
import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseReadCandidatesInput(BaseModel):
    """Input for reading candidates (optional limit)."""
    limit: int = Field(
        default=60,
        description="Maximum number of rows to return (default 60, matches max candidates per Discovery run). Use to get the full candidate list for extraction.",
    )


class SupabaseReadCandidatesTool(BaseTool):
    """Harvester: read all candidate articles from coyote_candidates so the full list is available regardless of task output length."""

    name: str = "supabase_read_candidates"
    description: str = (
        "Read candidate articles from the Supabase coyote_candidates table. "
        "Returns the most recently inserted rows first (by created_at). "
        "Each article in the 'articles' array has: url (required for write_evaluations), title, source, published_date. Use to get the current run's candidates after Discovery."
    )
    args_schema: Type[BaseModel] = SupabaseReadCandidatesInput

    def _run(self, limit: int = 60) -> str:
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
            result = (
                client.table("coyote_candidates")
                .select("url, title, source, published_date")
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = result.data or []
            # Normalize so each article always has "url" (required for write_evaluations)
            articles = []
            for r in rows:
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
                    "url": url_val,
                    "title": title_val or "",
                    "source": source_val,
                    "published_date": pub,
                })
            return json.dumps({"articles": articles, "count": len(articles)})
        except Exception as e:
            return json.dumps({"error": str(e), "articles": []})
