"""Tool for Judge agent: insert evaluation results into Supabase coyote_article_evaluations (insert only)."""

import os
import sys
import json
from typing import Type, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _valid_uuid(s: Any) -> Optional[str]:
    """Return normalized UUID string if s looks like a valid UUID; else None."""
    if s is None:
        return None
    raw = str(s).strip()
    if len(raw) < 32:
        return None
    # Accept with or without hyphens
    try:
        import uuid
        u = uuid.UUID(raw)
        return str(u)
    except (ValueError, AttributeError):
        return None


def _last_complete_object_end(prefix: str) -> Optional[int]:
    """
    Find the index of the last '}' that closes a top-level object in a JSON array prefix.
    Skips braces inside strings so we don't mistake a } in a summary/url-like text for structure.
    """
    if not prefix or len(prefix) <= 1:
        return None
    i = 0
    n = len(prefix)
    object_depth = 0
    in_string = False
    string_char = None
    escape = False
    last_object_end: Optional[int] = None

    while i < n:
        c = prefix[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == "\\":
                escape = True
            elif c == string_char:
                in_string = False
            i += 1
            continue
        if c in ("'", '"'):
            in_string = True
            string_char = c
            i += 1
            continue
        if c == "{":
            object_depth += 1
            i += 1
            continue
        if c == "}":
            if object_depth == 1:
                last_object_end = i
            object_depth -= 1
            i += 1
            continue
        i += 1

    return last_object_end


def _salvage_json_array_prefix(s: str, error_pos: Optional[int]) -> Optional[list]:
    """If the payload is truncated, try to parse a valid array prefix. Returns list or None."""
    if not s or not s.strip().startswith("["):
        return None
    end = (error_pos if error_pos is not None else len(s)) - 1
    if end < 1:
        return None
    search = s[: end + 1]
    idx = _last_complete_object_end(search)
    if idx is None:
        return None
    prefix = search[: idx + 1] + "]"
    try:
        parsed = json.loads(prefix)
        if isinstance(parsed, list) and all(isinstance(x, dict) for x in parsed):
            return parsed
    except json.JSONDecodeError:
        return None
    return None


class SupabaseWriteEvaluationsInput(BaseModel):
    """Input for writing evaluations to Supabase."""

    evaluations_json: str = Field(
        ...,
        description=(
            "A JSON string containing an array of evaluation objects. "
            "Each object should be shaped like the output from thesis_title_relevance_tool, "
            "plus a required 'candidate_id' field (UUID string) from supabase_read_candidates article.id. "
            "Example: '[{\"candidate_id\": \"...\", \"relevance_score\": 70, ...}]'. "
            "Each candidate_id must exist in coyote_candidates."
        ),
    )


def _num(val: Any) -> int | float | None:
    """Coerce numeric values (int/float/str) to float for DB; return None if invalid."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _str_or_none(val: Any, max_len: int = 8192) -> str | None:
    """Normalize to trimmed string, enforcing max length; return None for empty."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:max_len] if len(s) > max_len else s


class SupabaseWriteEvaluationsTool(BaseTool):
    """Judge agent: insert-only into Supabase coyote_article_evaluations. Duplicate candidate_id are skipped."""

    name: str = "supabase_write_evaluations"
    description: str = (
        "Insert evaluation results into the Supabase coyote_article_evaluations table. "
        "Call with a JSON array of evaluation objects, or an object with 'evaluations' or 'evaluation_list' key. "
        "To avoid platform truncation, send at most 2 evaluation objects per call (split batches if needed). "
        "Each object: candidate_id (required, UUID from read_candidates article.id), plus fields from thesis_title_relevance_tool (relevance_score, exec_summary, etc.). "
        "Each candidate_id must exist in coyote_candidates. Duplicate candidate_id are skipped. Returns inserted count and skip reasons."
    )
    args_schema: Type[BaseModel] = SupabaseWriteEvaluationsInput

    def _run(self, evaluations_json: Optional[str] = None) -> str:
        # 1. Explicit empty/missing input check (align with write_candidates)
        if not evaluations_json or (isinstance(evaluations_json, str) and not evaluations_json.strip()):
            return json.dumps(
                {
                    "error": "evaluations_json is required. Pass a JSON array of evaluation objects, e.g. [{\"candidate_id\":\"<uuid>\", \"relevance_score\": 70, ...}].",
                    "inserted": 0,
                    "skipped_no_candidate_id": 0,
                    "skipped_duplicate": 0,
                    "skipped_foreign_key": 0,
                    "skipped_invalid": 0,
                }
            )

        length = len(evaluations_json) if isinstance(evaluations_json, str) else 0
        print(
            f"[supabase_write_evaluations] Called with type={type(evaluations_json).__name__}, length={length}",
            file=sys.stderr,
        )

        # 2. Parse JSON; accept array or wrapper object (align with write_candidates)
        try:
            data = json.loads(evaluations_json) if isinstance(evaluations_json, str) else evaluations_json
        except json.JSONDecodeError as e:
            # Try to salvage a valid prefix (truncated payload): find last complete object before error
            salvaged = _salvage_json_array_prefix(evaluations_json, e.pos) if isinstance(evaluations_json, str) else None
            if salvaged is None:
                return json.dumps(
                    {
                        "error": f"Invalid JSON for evaluations_json: {e}",
                        "inserted": 0,
                        "skipped_no_candidate_id": 0,
                        "skipped_duplicate": 0,
                        "skipped_foreign_key": 0,
                        "skipped_invalid": 0,
                    }
                )
            print(
                f"[supabase_write_evaluations] Salvaged {len(salvaged)} evaluation object(s) from truncated payload.",
                file=sys.stderr,
            )
            data = salvaged

        if isinstance(data, dict):
            # Accept wrappers: evaluations, evaluation_list, evaluation_objects
            data = data.get("evaluations") or data.get("evaluation_list") or data.get("evaluation_objects") or data
        if not isinstance(data, list):
            data = [data] if isinstance(data, dict) else []

        print(
            f"[supabase_write_evaluations] Parsed {len(data)} evaluation object(s) to insert",
            file=sys.stderr,
        )

        # 2. Ensure Supabase client is available
        supabase_url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not key:
            return json.dumps(
                {
                    "error": "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set",
                    "inserted": 0,
                    "skipped_no_candidate_id": 0,
                    "skipped_duplicate": 0,
                    "skipped_foreign_key": 0,
                    "skipped_invalid": 0,
                }
            )

        try:
            from supabase import create_client

            client = create_client(supabase_url, key)
        except Exception as e:
            return json.dumps(
                {
                    "error": f"Supabase client initialization failed: {e}",
                    "inserted": 0,
                    "skipped_no_candidate_id": 0,
                    "skipped_duplicate": 0,
                    "skipped_foreign_key": 0,
                    "skipped_invalid": 0,
                }
            )

        # 3. Insert each evaluation, mapping fields from title tool output
        inserted = 0
        skipped_no_candidate_id = 0
        skipped_duplicate = 0
        skipped_foreign_key = 0
        skipped_invalid = 0

        for idx, item in enumerate(data):
            if not isinstance(item, dict):
                skipped_invalid += 1
                continue

            raw_cid = item.get("candidate_id") or item.get("candidate_Id") or item.get("id")
            candidate_id_val = _valid_uuid(raw_cid)
            if not candidate_id_val:
                skipped_no_candidate_id += 1
                continue

            # These fields match the JSON contract of thesis_title_relevance_tool
            focus = item.get("focus_area_tags")
            companies = item.get("companies_mentioned")

            row = {
                "candidate_id": candidate_id_val,
                "relevance_score": _num(item.get("relevance_score")),
                "confidence_score": _num(item.get("confidence_score")),
                "signal_type": _str_or_none(item.get("signal_type"), 128),
                "thesis_sector": _str_or_none(item.get("thesis_sector"), 512),
                "focus_area_tags": _str_or_none(focus, 2048),
                "geography": _str_or_none(item.get("geography"), 512),
                "companies_mentioned": _str_or_none(companies, 2048),
                "exec_summary": _str_or_none(item.get("exec_summary"), 8192),
                "why_it_matters": _str_or_none(item.get("why_it_matters"), 2048),
                "rejection_reason": _str_or_none(item.get("rejection_reason"), 1024),
                "sent_in_weekly_digest": bool(item.get("sent_in_weekly_digest", False)),
            }

            try:
                client.table("coyote_article_evaluations").insert(row).execute()
                inserted += 1
            except Exception as e:
                err_str = str(e).lower()
                if "duplicate" in err_str or "unique" in err_str or "23505" in err_str:
                    skipped_duplicate += 1
                    continue
                if "foreign key" in err_str or "23503" in err_str:
                    skipped_foreign_key += 1
                    print(
                        f"[supabase_write_evaluations] Skipped candidate_id (no matching candidate): {candidate_id_val}",
                        file=sys.stderr,
                    )
                    continue

                # Any other DB error: return immediately with partial counts and the error message
                return json.dumps(
                    {
                        "error": str(e),
                        "inserted": inserted,
                        "skipped_no_candidate_id": skipped_no_candidate_id,
                        "skipped_duplicate": skipped_duplicate,
                        "skipped_foreign_key": skipped_foreign_key,
                        "skipped_invalid": skipped_invalid,
                    }
                )

        if skipped_foreign_key or skipped_duplicate or skipped_no_candidate_id or skipped_invalid:
            print(
                "[supabase_write_evaluations] "
                f"inserted={inserted}, "
                f"skipped_duplicate={skipped_duplicate}, "
                f"skipped_foreign_key={skipped_foreign_key}, "
                f"skipped_no_candidate_id={skipped_no_candidate_id}, "
                f"skipped_invalid={skipped_invalid}",
                file=sys.stderr,
            )

        message = f"Inserted {inserted} rows into coyote_article_evaluations."
        if skipped_foreign_key or skipped_duplicate or skipped_no_candidate_id or skipped_invalid:
            message += (
                f" Skipped: {skipped_foreign_key} candidate_id not in candidates, "
                f"{skipped_duplicate} duplicates, "
                f"{skipped_no_candidate_id} missing or invalid candidate_id, "
                f"{skipped_invalid} invalid objects."
            )
        if skipped_foreign_key > 0 or skipped_no_candidate_id > 0:
            message += (
                " Fix: use the id from each article in the same supabase_read_candidates response as candidate_id."
            )

        return json.dumps(
            {
                "inserted": inserted,
                "skipped_no_candidate_id": skipped_no_candidate_id,
                "skipped_duplicate": skipped_duplicate,
                "skipped_foreign_key": skipped_foreign_key,
                "skipped_invalid": skipped_invalid,
                "message": message,
            }
        )
