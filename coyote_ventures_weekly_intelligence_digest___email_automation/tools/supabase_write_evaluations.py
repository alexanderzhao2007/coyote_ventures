"""Tool for Judge agent: insert evaluation results into Supabase coyote_article_evaluations (insert only)."""

import os
import sys
import json
from typing import Type, Any

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


class SupabaseWriteEvaluationsInput(BaseModel):
    """Input for writing evaluations to Supabase."""
    evaluations_json: str = Field(
        ...,
        description="A JSON string that is an array of evaluation objects. Example: '[{\"url\": \"https://...\", \"relevance_score\": 70, ...}]'. Each object: url (required), relevance_score, confidence_score, signal_type, exec_summary, why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, rejection_reason, sent_in_weekly_digest (default false). URLs must already exist in coyote_candidates."
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
        "REQUIRED TOOL: Insert evaluation results into the Supabase coyote_article_evaluations table. "
        "You MUST call this tool after every batch of ~10 evaluations. "
        "Parameter: evaluations_json (a JSON string that is an array of objects). "
        "Each object must include: url (required—use exact URL from supabase_read_candidates), relevance_score, confidence_score, signal_type, "
        "exec_summary, why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, "
        "rejection_reason, sent_in_weekly_digest=false. "
        "Example: evaluations_json='[{\"url\":\"https://...\",\"relevance_score\":70,...}]'. "
        "Each url must exist in coyote_candidates. Duplicate urls are skipped. Returns inserted count and skip reasons."
    )
    args_schema: Type[BaseModel] = SupabaseWriteEvaluationsInput

    def _run(self, evaluations_json: str) -> str:
        print(f"[supabase_write_evaluations] Tool called with evaluations_json type: {type(evaluations_json).__name__}, length: {len(str(evaluations_json)) if evaluations_json else 0}", file=sys.stderr)
        try:
            if isinstance(evaluations_json, list):
                data = evaluations_json
            elif isinstance(evaluations_json, dict):
                data = evaluations_json.get("evaluations", evaluations_json.get("candidate_articles", [evaluations_json]))
                if not isinstance(data, list):
                    data = [data]
            else:
                data = json.loads(evaluations_json)
            if not isinstance(data, list):
                data = [data] if isinstance(data, dict) else []
            print(f"[supabase_write_evaluations] Parsed {len(data)} evaluation(s) to insert", file=sys.stderr)
        except json.JSONDecodeError as e:
            return json.dumps({"error": f"Invalid JSON: {e}", "inserted": 0, "skipped_no_url": 0, "skipped_duplicate": 0, "skipped_foreign_key": 0})
        except TypeError:
            return json.dumps({"error": "evaluations_json must be a JSON string or list", "inserted": 0, "skipped_no_url": 0, "skipped_duplicate": 0, "skipped_foreign_key": 0})

        supabase_url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not key:
            return json.dumps({"error": "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set", "inserted": 0, "skipped_no_url": 0, "skipped_duplicate": 0, "skipped_foreign_key": 0})

        try:
            from supabase import create_client
            client = create_client(supabase_url, key)
        except Exception as e:
            return json.dumps({"error": f"Supabase client: {e}", "inserted": 0, "skipped_no_url": 0, "skipped_duplicate": 0, "skipped_foreign_key": 0})

        inserted = 0
        skipped_no_url = 0
        skipped_duplicate = 0
        skipped_foreign_key = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            url_val = (item.get("url") or item.get("URL") or "").strip()
            if not url_val:
                skipped_no_url += 1
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
                err_str = str(e).lower()
                if "duplicate" in err_str or "unique" in err_str or "23505" in str(e):
                    skipped_duplicate += 1
                    continue
                if "foreign key" in err_str or "23503" in str(e):
                    skipped_foreign_key += 1
                    print(
                        f"[supabase_write_evaluations] Skipped URL (not in coyote_candidates): {url_val[:80]}...",
                        file=sys.stderr,
                    )
                    continue
                return json.dumps({
                    "error": str(e),
                    "inserted": inserted,
                    "skipped_no_url": skipped_no_url,
                    "skipped_duplicate": skipped_duplicate,
                    "skipped_foreign_key": skipped_foreign_key,
                })

        if skipped_foreign_key or skipped_duplicate or (len(data) > 0 and inserted == 0):
            print(
                f"[supabase_write_evaluations] inserted={inserted}, skipped_duplicate={skipped_duplicate}, skipped_foreign_key={skipped_foreign_key}, skipped_no_url={skipped_no_url}",
                file=sys.stderr,
            )
        return json.dumps({
            "inserted": inserted,
            "skipped_no_url": skipped_no_url,
            "skipped_duplicate": skipped_duplicate,
            "skipped_foreign_key": skipped_foreign_key,
            "message": f"Inserted {inserted} rows into coyote_article_evaluations."
            + (f" Skipped: {skipped_foreign_key} URLs not in candidates, {skipped_duplicate} duplicates, {skipped_no_url} missing url." if (skipped_foreign_key or skipped_duplicate or skipped_no_url) else ""),
        })
