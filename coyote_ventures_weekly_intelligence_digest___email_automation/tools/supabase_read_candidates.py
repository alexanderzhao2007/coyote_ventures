"""Tool for Harvester: read candidate articles from Supabase coyote_candidates (full list)."""

import os
import json
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseReadCandidatesInput(BaseModel):
    """Input for reading candidates (optional limit)."""
    limit: int = Field(
        default=100,
        description="Maximum number of rows to return (default 100). Use to get the full candidate list for extraction.",
    )


class SupabaseReadCandidatesTool(BaseTool):
    """Harvester: read all candidate articles from coyote_candidates so the full list is available regardless of task output length."""

    name: str = "supabase_read_candidates"
    description: str = (
        "Read candidate articles from the Supabase coyote_candidates table. "
        "Returns a JSON array of objects: url, title, source, published_date, snippet. "
        "Call this to get the complete list of candidates (e.g. after Discovery wrote 60 articles) when the previous task output was truncated."
    )
    args_schema: Type[BaseModel] = SupabaseReadCandidatesInput

    def _run(self, limit: int = 100) -> str:
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
            result = client.table("coyote_candidates").select("url, title, source, published_date, snippet").limit(limit).execute()
            rows = result.data or []
            return json.dumps({"articles": rows, "count": len(rows)})
        except Exception as e:
            return json.dumps({"error": str(e), "articles": []})
