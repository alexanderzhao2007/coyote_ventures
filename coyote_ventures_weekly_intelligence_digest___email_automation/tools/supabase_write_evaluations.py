"""Tool for Judge agent: insert evaluation results into Supabase coyote_article_evaluations (insert only)."""

import os
import json
from typing import Type, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseWriteEvaluationsInput(BaseModel):
    """Input for writing evaluations to Supabase."""
    evaluations_json: str = Field(
        ...,
        description="JSON array of evaluations. Each object: url (required), relevance_score, confidence_score, signal_type, exec_summary, why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, rejection_reason, sent_in_weekly_digest (default false)."
    )


def _num(val: Any) -> int | float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _str_or_none(val: Any, max_len: int = 8192) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:max_len] if len(s) > max_len else s


class SupabaseWriteEvaluationsTool(BaseTool):
    """Judge agent: insert-only into Supabase coyote_article_evaluations. Duplicate url skipped."""

    name: str = "supabase_write_evaluations"
    description: str = (
        "Insert evaluation results into the Supabase coyote_article_evaluations table (Judge table). "
        "Call with a JSON array of objects: url (required), relevance_score, confidence_score, signal_type, "
        "exec_summary, why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, "
        "rejection_reason, sent_in_weekly_digest (default false). Each url must exist in coyote_candidates. Duplicate urls skipped."
    )
    args_schema: Type[BaseModel] = SupabaseWriteEvaluationsInput

    def _run(self, evaluations_json: str) -> str:
        try:
            data = json.loads(evaluations_json)
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

            focus = item.get("focus_area_tags") or item.get("focus_area_tags")
            if isinstance(focus, list):
                focus = json.dumps(focus) if focus else None
            companies = item.get("companies_mentioned") or item.get("companies_mentioned")
            if isinstance(companies, list):
                companies = json.dumps(companies) if companies else None

            row = {
                "url": url_val[:2048] if len(url_val) > 2048 else url_val,
                "relevance_score": _num(item.get("relevance_score")),
                "confidence_score": _num(item.get("confidence_score")),
                "signal_type": _str_or_none(item.get("signal_type"), 128),
                "thesis_sector": _str_or_none(item.get("thesis_sector"), 512),
                "focus_area_tags": _str_or_none(focus, 2048),
                "geography": _str_or_none(item.get("geography"), 512),
                "companies_mentioned": _str_or_none(companies, 2048),
                "exec_summary": _str_or_none(item.get("exec_summary") or item.get("executive_summary")),
                "why_it_matters": _str_or_none(item.get("why_it_matters") or item.get("investment_implications") or item.get("relevance_reasoning")),
                "rejection_reason": _str_or_none(item.get("rejection_reason"), 1024),
                "sent_in_weekly_digest": bool(item.get("sent_in_weekly_digest", False)),
            }
            try:
                client.table("coyote_article_evaluations").insert(row).execute()
                inserted += 1
            except Exception as e:
                if "duplicate" in str(e).lower() or "unique" in str(e).lower() or "23505" in str(e):
                    continue
                if "foreign key" in str(e).lower() or "23503" in str(e):
                    continue
                return json.dumps({"error": str(e), "inserted": inserted})

        return json.dumps({"inserted": inserted, "message": f"Inserted {inserted} rows into coyote_article_evaluations."})
