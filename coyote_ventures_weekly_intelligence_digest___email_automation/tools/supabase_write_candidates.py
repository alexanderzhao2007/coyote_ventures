"""Tool for Discovery agent: insert candidate articles into Supabase coyote_candidates table (insert only)."""

import os
import re
import json
from datetime import datetime, date, timedelta, timezone
from typing import Type, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from rapidfuzz import fuzz


# Words that should never be treated as company-name tokens.
# Covers generic healthcare/tech vocabulary, geographic terms, and common verbs/articles.
_GENERIC_WORDS = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "has", "have", "had", "will", "would", "could", "should", "may", "might",
    "its", "our", "their", "your", "this", "that", "these", "those",
    "how", "why", "what", "when", "where", "who", "which",
    # Healthcare/tech generics
    "health", "healthcare", "digital", "medical", "care", "tech", "new",
    "mental", "public", "home", "virtual", "data", "platform", "system",
    "hospital", "clinic", "provider", "patient", "doctor", "nurse",
    "insurance", "payer", "employer", "government", "federal", "policy",
    "startup", "company", "firm", "fund", "venture", "capital",
    "series", "round", "funding", "raises", "million", "billion",
    "launches", "announces", "expands", "introduces", "unveils", "joins",
    "big", "small", "large", "major", "key", "top", "best", "first",
    # Geography generics
    "united", "states", "america", "american", "national", "state", "city",
    # Common report/study words
    "study", "report", "survey", "research", "analysis", "review",
    "global", "industry", "market", "sector", "service", "services",
}


def _extract_company_bigrams(title: str) -> list[str]:
    """Return Title-Case word-pair bigrams that look like company names.

    Both words must start with an uppercase letter, be at least 3 characters
    long (after stripping punctuation), and neither word may appear in the
    generic vocabulary list.  This catches entities like 'Grow Therapy' or
    'Bright Health' while ignoring common phrases like 'Mental Health'.
    """
    words = re.split(r"\s+", title.strip())
    bigrams: list[str] = []
    for i in range(len(words) - 1):
        w1 = re.sub(r"[^a-zA-Z]", "", words[i])
        w2 = re.sub(r"[^a-zA-Z]", "", words[i + 1])
        w1_generic = w1.lower() in _GENERIC_WORDS
        w2_generic = w2.lower() in _GENERIC_WORDS
        if (
            w1 and w2
            and len(w1) >= 3 and len(w2) >= 3
            and w1[0].isupper() and w2[0].isupper()
            and not w1_generic and not w2_generic
        ):
            bigrams.append(f"{w1.lower()} {w2.lower()}")
    return bigrams


def _extract_company_unigrams(title: str) -> list[str]:
    """Return single Title-Case words >= 5 chars that are not in _GENERIC_WORDS.

    Used as a fallback when no bigrams are found, to catch single-word company
    names like 'Veeva', 'Flatiron', or 'Hims'.
    """
    words = re.split(r"\s+", title.strip())
    result: list[str] = []
    for w in words:
        cleaned = re.sub(r"[^a-zA-Z]", "", w)
        if (
            cleaned
            and len(cleaned) >= 5
            and cleaned[0].isupper()
            and cleaned.lower() not in _GENERIC_WORDS
        ):
            result.append(cleaned.lower())
    return result


class SupabaseWriteCandidatesInput(BaseModel):
    """Input for writing candidate articles to Supabase."""
    articles_json: str = Field(
        ...,
        description="JSON array of articles. Each object: url (required), title (required), source (optional), published_date (optional)."
    )


def _last_complete_object_end(prefix: str) -> Optional[int]:
    """
    Find the index of the last '}' that closes a top-level object in a JSON array prefix.
    Skips braces inside strings so we don't mistake a } in a URL/title for structure.
    """
    if not prefix or len(prefix) <= 1:
        return None
    i = 0
    n = len(prefix)
    object_depth = 0  # counts only {} nesting; ignore [] so "[{...}]" top-level object closes at depth==1
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
            # If we are closing a top-level object in the array, object_depth will be 1 here.
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
    # Work on the prefix up to (and a bit before) the error so we don't include broken tail
    end = (error_pos if error_pos is not None else len(s)) - 1
    if end < 1:
        return None
    search = s[: end + 1]
    # Use brace-aware search so we don't treat } inside a string (e.g. URL) as object end
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


def _title_is_fuzzy_duplicate(title: str, against: list[str], threshold: int = 75) -> bool:
    """True if title is a near-duplicate of any string in *against*.

    Two checks are applied (either is sufficient to flag a duplicate):
    1. fuzz.ratio >= threshold (catches near-identical titles).
    2. Company-name bigram overlap: if both titles share a Title-Case
       word-pair that is not generic vocabulary (e.g. 'Grow Therapy'),
       they are treated as the same story told from a different angle.
    """
    if not title or not against:
        return False
    title_lower = title.lower()

    company_bigrams = _extract_company_bigrams(title)
    # Only use unigrams when no bigrams found — reduces false positives
    company_unigrams = _extract_company_unigrams(title) if not company_bigrams else []

    for existing in against:
        existing_lower = existing.lower()
        if fuzz.token_set_ratio(title_lower, existing_lower) >= threshold:
            return True
        # Company-name match: same startup / entity, different article angle
        if company_bigrams:
            for bigram in company_bigrams:
                if bigram in existing_lower:
                    return True
        # Single-word company fallback (e.g. 'Veeva', 'Flatiron')
        if company_unigrams:
            for unigram in company_unigrams:
                if unigram in existing_lower:
                    return True
    return False


class SupabaseWriteCandidatesTool(BaseTool):
    """Discovery agent: insert-only into Supabase coyote_candidates. Duplicate URLs and fuzzy-duplicate titles are skipped."""

    name: str = "supabase_write_candidates"
    description: str = (
        "Insert candidate articles into the Supabase coyote_candidates table (Discovery table). "
        "Call with a JSON array of candidate articles from a single SerplyNews search: url (required), title (required), source (optional), published_date (optional). "
        "Use at most 5 articles per call (one search = one call). If the JSON is truncated, the tool will attempt to salvage all complete articles from the prefix. "
        "Duplicate URLs and fuzzy-duplicate titles (vs. articles in the last 7 days) are skipped."
    )
    args_schema: Type[BaseModel] = SupabaseWriteCandidatesInput

    def _run(self, articles_json: Optional[str] = None) -> str:
        import sys
        if not articles_json or (isinstance(articles_json, str) and not articles_json.strip()):
            return json.dumps(
                {
                    "error": "articles_json is required. Pass a JSON array of articles, e.g. [{\"url\":\"...\", \"title\":\"...\", \"source\":\"...\", \"published_date\":\"...\"}].",
                    "received": 0,
                    "inserted": 0,
                    "skipped_duplicates": 0,
                    "skipped_missing_url": 0,
                }
            )
        try:
            data = json.loads(articles_json)
        except json.JSONDecodeError as e:
            print(f"[supabase_write_candidates] Invalid JSON: {e}", file=sys.stderr)
            # Try to salvage a valid prefix (truncated payload): find last complete object before error
            data = _salvage_json_array_prefix(articles_json, e.pos)
            if data is None:
                return json.dumps(
                    {
                        "error": f"Invalid JSON: {e}. Call with at most 5 articles per search to avoid truncation.",
                        "received": 0,
                        "inserted": 0,
                        "skipped_duplicates": 0,
                        "skipped_missing_url": 0,
                        "skipped_older_than_7_days": 0,
                    }
                )
            print(f"[supabase_write_candidates] Salvaged {len(data)} complete article(s) from truncated payload.", file=sys.stderr)

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
        skipped_duplicate_title = 0
        skipped_missing_url = 0
        skipped_older_than_7_days = 0

        # Fetch titles from articles inserted in the last 7 days (for fuzzy dedupe)
        cutoff_datetime = datetime.now(timezone.utc) - timedelta(days=7)
        cutoff_iso = cutoff_datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
        existing_titles: list[str] = []
        try:
            result = (
                client.table("coyote_candidates")
                .select("title")
                .gte("created_at", cutoff_iso)
                .execute()
            )
            existing_titles = [r["title"] for r in (result.data or []) if r.get("title")]
        except Exception:
            pass

        seen_titles: list[str] = []
        cutoff_date = date.today() - timedelta(days=7)
        for item in data:
            if not isinstance(item, dict):
                continue
            url_val = item.get("url") or item.get("URL")
            title_val = item.get("title") or item.get("Title") or ""

            title_stripped = title_val.strip()
            if title_stripped and (
                _title_is_fuzzy_duplicate(title_stripped, existing_titles)
                or _title_is_fuzzy_duplicate(title_stripped, seen_titles)
            ):
                skipped_duplicate_title += 1
                continue
            if title_stripped:
                seen_titles.append(title_stripped)

            if not url_val:
                skipped_missing_url += 1
                continue
            source_val = item.get("source") or item.get("Source")
            pub_raw = item.get("published_date") or item.get("Published Date") or item.get("published_date")
            published_date_parsed = _parse_published_date(str(pub_raw)) if pub_raw else None

            # Enforce 7-day window: skip articles older than 7 days when we have a parsed date
            if published_date_parsed:
                try:
                    pub_dt = datetime.strptime(published_date_parsed, "%Y-%m-%d").date()
                    if pub_dt < cutoff_date:
                        skipped_older_than_7_days += 1
                        continue
                except ValueError:
                    # If parsing fails here, fall back to inserting (we already normalized once)
                    pass

            row = {
                "url": url_val[:2048] if len(url_val) > 2048 else url_val,
                "title": (title_val or "Untitled")[:2048] if title_val else "Untitled",
                "source": source_val,
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
                        "skipped_duplicate_title": skipped_duplicate_title,
                        "skipped_missing_url": skipped_missing_url,
                        "skipped_older_than_7_days": skipped_older_than_7_days,
                    }
                )

        if skipped_duplicates or skipped_duplicate_title or skipped_older_than_7_days:
            print(
                f"[supabase_write_candidates] Inserted {inserted} rows, "
                f"skipped {skipped_duplicates} duplicate URL(s), "
                f"skipped {skipped_duplicate_title} duplicate title(s), "
                f"skipped {skipped_older_than_7_days} older-than-7-days article(s).",
                file=sys.stderr,
            )
        return json.dumps(
            {
                "received": n_articles,
                "inserted": inserted,
                "skipped_duplicates": skipped_duplicates,
                "skipped_duplicate_title": skipped_duplicate_title,
                "skipped_missing_url": skipped_missing_url,
                "skipped_older_than_7_days": skipped_older_than_7_days,
                "message": f"Inserted {inserted} rows into coyote_candidates.",
            }
        )
