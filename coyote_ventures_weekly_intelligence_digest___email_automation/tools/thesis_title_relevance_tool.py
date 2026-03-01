"""Tool for Judge agent: score article relevance using only the article title (no full text)."""

import os
import json
import sys
import time
import requests
from typing import Type, Dict, Any, Optional

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


def _str(val: Any, default: Optional[str], max_len: int) -> Optional[str]:
    """Coerce to string for DB; return default if None, empty, or literal 'null'. Truncate to max_len."""
    if val is None:
        return default
    s = str(val).strip()
    if not s or s.lower() == "null":
        return default
    return s[:max_len] if len(s) > max_len else s


class ThesisTitleRelevanceInput(BaseModel):
    """Input schema for Thesis Title Relevance Tool."""
    article_title: str = Field(..., description="The article title only (no body)")
    use_static_thesis: bool = Field(
        True,
        description="If True (default), use the pre-loaded condensed thesis from config/thesis_summary.txt. Set False to pass thesis_text manually.",
    )
    thesis_text: Optional[str] = Field(
        None,
        description="Full thesis text (only used when use_static_thesis=False). Ignored when use_static_thesis=True.",
    )
    relevance_context: Optional[str] = Field(
        None,
        description="Optional context describing what is typically relevant vs not for scoring (e.g. guidelines).",
    )
    openai_api_key: Optional[str] = Field(
        None,
        description="OpenAI API key (optional if set as environment variable)",
    )


class ThesisTitleRelevanceTool(BaseTool):
    """Score relevance of an article to the investment thesis using only its title (GPT-4o-mini, no embeddings)."""

    name: str = "thesis_title_relevance_tool"
    description: str = (
        "Scores how relevant an article is to the investment thesis using ONLY the article title. "
        "Call with article_title and use_static_thesis=True (default) to use the pre-loaded condensed thesis—no need to scrape or pass thesis text. "
        "Returns a result shaped for supabase_write_evaluations: relevance_score (0-100), confidence_score, signal_type, exec_summary, "
        "why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, rejection_reason. "
        "Judge adds candidate_id (UUID from read_candidates article.id) per article and passes the array to supabase_write_evaluations."
    )
    args_schema: Type[BaseModel] = ThesisTitleRelevanceInput

    def _get_api_key(self, provided_key: Optional[str] = None) -> str:
        if provided_key:
            return provided_key
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key must be provided either as parameter or OPENAI_API_KEY environment variable"
            )
        return api_key

    def _get_thesis_text(self, use_static_thesis: bool, thesis_text: Optional[str]) -> str:
        """Resolve thesis text from static file or provided argument."""
        if use_static_thesis:
            base = os.path.dirname(os.path.abspath(__file__))
            pkg_root = os.path.dirname(base)
            path = os.path.join(pkg_root, "config", "thesis_summary.txt")
            if not os.path.isfile(path):
                raise FileNotFoundError(
                    f"Static thesis not found at {path}. Create config/thesis_summary.txt or use use_static_thesis=False with thesis_text."
                )
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        if not thesis_text or not thesis_text.strip():
            raise ValueError("thesis_text is required when use_static_thesis=False")
        return thesis_text.strip()

    def _run(
        self,
        article_title: str,
        use_static_thesis: bool = True,
        thesis_text: Optional[str] = None,
        relevance_context: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ) -> str:
        try:
            api_key = self._get_api_key(openai_api_key)
            resolved_thesis = self._get_thesis_text(use_static_thesis, thesis_text)
            if not article_title.strip():
                raise ValueError("Article title cannot be empty")

            context_block = ""
            if relevance_context and relevance_context.strip():
                context_block = f"\n\nADDITIONAL CONTEXT FOR RELEVANCE (use when scoring):\n{relevance_context.strip()}\n"

            prompt = f"""You are an investment analyst. Score how relevant this article is to the investment thesis using ONLY the article title. You do not have the article body—titles can be sensational or vague, so score conservatively.

INVESTMENT THESIS:
{resolved_thesis[:4000]}{"..." if len(resolved_thesis) > 4000 else ""}

ARTICLE TITLE ONLY:
{article_title}
{context_block}

STEP 1 — CHECK DISQUALIFIERS FIRST (geography and focus-area gates). These override everything else:
  a) Does the title reference a NON-U.S. country (UK, India, Canada, China, etc.)? If YES → score MUST be ≤ 30, UNLESS the article is an unmistakable 100% match on a thesis focus area (e.g., a named company in a thesis sector raising a specific round). "Related to healthcare abroad" is NOT enough to override.
  b) Does the title reference a U.S. state, county, or city that is NOT New York, Los Angeles, Chicago, Boston, or San Francisco? If YES and the finding is local in scope (no clear national-scale impact) → score MUST be ≤ 30, same exception as (a).
  c) Which of the 17 focus areas does this title map to? If NONE → score MUST be ≤ 40, UNLESS the article qualifies as market intelligence (see 50-59 in the rubric), in which case it may score up to 59.

STEP 2 — Only if the article passed the geography/focus-area gates above, determine specificity:
  a) Does the title mention a SPECIFIC company, funding round, technology, legislation, or measurable development? Or is it generic/vague?
  b) Is the geography clearly U.S. national or one of the 5 listed cities?

STEP 3 — Assign a relevance_score using this DETAILED rubric:
  90-100: Title explicitly names a company, funding round, or policy change that DIRECTLY matches a thesis focus area. Rare—reserve for unmistakable hits.
  80-89:  Title strongly implies a specific thesis focus area AND mentions a concrete detail (company name, dollar amount, named technology, specific legislation).
  70-79:  Title clearly maps to a thesis focus area with moderate specificity (names a sector or trend within a focus area, but lacks a concrete company/amount/policy).
  60-69:  Title is related to a thesis focus area but is BROAD or lacks specificity (e.g., "Digital health trends in 2026"). Requires a clear connection to a specific focus area.
  50-59:  MARKET INTELLIGENCE — Title provides valuable context for healthcare investing even though it does not directly match a specific thesis focus area. Examples: major healthcare M&A or IPO activity, broad regulatory/policy changes (CMS, FDA), industry trend reports or market sizing data, large payer/insurer strategy shifts, healthcare workforce or spending trends. The article must still be U.S.-focused and actionable for investment decision-making.
  40-49:  Title is healthcare-adjacent but not useful for investing decisions (e.g., pharma earnings, hospital construction, clinical trial results).
  30-39:  Title is only loosely connected to healthcare or investment.
  0-29:   Title has no meaningful connection to the thesis.

IMPORTANT: Use the FULL range of scores. Do NOT default to any single number. Each article should be scored on its own merits based on the rubric above.

Return exactly one JSON object with these keys only (no markdown, no explanation outside the JSON):
{{
  "relevance_score": <integer 0-100>,
  "confidence_score": <integer 0-100>,
  "signal_type": "One of: direct_thesis_match, market_intelligence, other",
  "exec_summary": "1-2 sentence summary of why the title suggests relevance or not",
  "why_it_matters": "Brief reason relevant for investment/market intelligence, or empty if low relevance",
  "thesis_sector": "Thesis sector most relevant (e.g. women's health, care model) or null",
  "focus_area_tags": "Comma-separated tags (e.g. AI health, virtual health) or empty",
  "geography": "Geography if suggested by title or null",
  "companies_mentioned": "Comma-separated company names if any, or empty string",
  "rejection_reason": "Only if relevance_score < 50, brief reason; otherwise null"
}}

signal_type: "direct_thesis_match" for score 70+, "market_intelligence" for 50-69, "other" for below 50.

HARD SCORING CAPS — These are the HIGHEST-PRIORITY rules. Apply them LAST and force the score down if violated, even if the rubric above suggested a higher score:
1. NON-U.S. COUNTRY: If the title mentions or implies ANY country other than the United States (e.g., UK, India, South Africa, Canada, China, Australia, etc.), the relevance_score MUST NOT exceed 30. The ONLY exception: the article is an unmistakable, 100% direct match on a thesis focus area (e.g., a named thesis-sector company with a specific funding amount). Merely being "about healthcare" in another country is NOT enough.
2. NON-LISTED U.S. LOCALITY: If the title references state-level, county-level, or city-level news for any location other than New York, Los Angeles, Chicago, Boston, or San Francisco — and the scope is local (not clearly national-scale) — the relevance_score MUST NOT exceed 30. Same narrow exception as rule 1.
3. NO DIRECT FOCUS-AREA RELEVANCE: If the article has no direct relevance to ANY of the 17 investment focus areas, the relevance_score MUST NOT exceed 40 — UNLESS the article qualifies as market intelligence (major M&A, regulatory changes, industry trends, payer strategy shifts, workforce/spending data), in which case it may score up to 59. Generic health news that does not map to a focus area and is not actionable market intelligence does not qualify.
4. PRIORITY ORDER: Geography caps (rules 1-2) OVERRIDE focus-area relevance. An article can match a thesis focus area perfectly but still score ≤ 30 if it fails geography."""

            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4.1-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.15,
                "max_tokens": 600,
            }

            max_retries = 3
            base_delay = 5
            last_err = None
            for attempt in range(1, max_retries + 1):
                try:
                    response = requests.post(url, headers=headers, json=payload, timeout=45)
                    response.raise_for_status()
                    break
                except requests.RequestException as e:
                    last_err = e
                    if attempt < max_retries:
                        delay = base_delay * (2 ** (attempt - 1))
                        print(
                            f"[title_relevance] Attempt {attempt}/{max_retries} failed: {e}. "
                            f"Retrying in {delay}s...",
                            file=sys.stderr,
                        )
                        time.sleep(delay)
                    else:
                        raise last_err

            data = response.json()
            content = data["choices"][0]["message"]["content"]

            start_idx = content.find("{")
            end_idx = content.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                gpt = json.loads(content[start_idx:end_idx])
            else:
                gpt = {
                    "relevance_score": 50,
                    "confidence_score": 50,
                    "signal_type": "other",
                    "exec_summary": "Title-only analysis; unable to parse model response.",
                    "why_it_matters": "",
                    "thesis_sector": None,
                    "focus_area_tags": "",
                    "geography": None,
                    "companies_mentioned": "",
                    "rejection_reason": None,
                }

            relevance_score = gpt.get("relevance_score")
            if relevance_score is not None:
                try:
                    relevance_score = int(relevance_score)
                except (TypeError, ValueError):
                    relevance_score = 50
            else:
                relevance_score = 50
            relevance_score = max(0, min(100, relevance_score))

            focus = gpt.get("focus_area_tags")
            if isinstance(focus, list):
                focus = ", ".join(str(x) for x in focus) if focus else ""
            companies = gpt.get("companies_mentioned")
            if isinstance(companies, list):
                companies = ", ".join(str(x) for x in companies) if companies else ""

            result = {
                "relevance_score": relevance_score,
                "confidence_score": int(gpt.get("confidence_score", 70)),
                "signal_type": _str(gpt.get("signal_type"), "other", 128),
                "exec_summary": _str(gpt.get("exec_summary"), "", 8192),
                "why_it_matters": _str(gpt.get("why_it_matters"), "", 2048),
                "thesis_sector": _str(gpt.get("thesis_sector"), None, 512),
                "focus_area_tags": _str(focus, "", 2048),
                "geography": _str(gpt.get("geography"), None, 512),
                "companies_mentioned": _str(companies, "", 2048),
                "rejection_reason": _str(gpt.get("rejection_reason"), None, 1024),
            }
            return json.dumps(result)

        except Exception as e:
            error_result = {
                "relevance_score": 0,
                "confidence_score": 0,
                "signal_type": "other",
                "exec_summary": f"Title-only analysis failed: {str(e)}"[:500],
                "why_it_matters": "",
                "thesis_sector": None,
                "focus_area_tags": "",
                "geography": None,
                "companies_mentioned": "",
                "rejection_reason": str(e)[:1024] if str(e) else None,
            }
            return json.dumps(error_result)
