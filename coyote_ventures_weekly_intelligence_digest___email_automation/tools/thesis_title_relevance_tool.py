"""Tool for Judge agent: score article relevance using only the article title (no full text)."""

import os
import json
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
    thesis_text: str = Field(..., description="The full text of the investment thesis")
    article_title: str = Field(..., description="The article title only (no body)")
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
        "Call with thesis_text and article_title (and optional relevance_context). Returns a result shaped for "
        "supabase_write_evaluations: relevance_score (0-100), confidence_score, signal_type, exec_summary, "
        "why_it_matters, thesis_sector, focus_area_tags, geography, companies_mentioned, rejection_reason. "
        "Judge adds url per article and passes the array to supabase_write_evaluations."
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

    def _run(
        self,
        thesis_text: str,
        article_title: str,
        relevance_context: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ) -> str:
        try:
            api_key = self._get_api_key(openai_api_key)
            if not thesis_text.strip():
                raise ValueError("Thesis text cannot be empty")
            if not article_title.strip():
                raise ValueError("Article title cannot be empty")

            context_block = ""
            if relevance_context and relevance_context.strip():
                context_block = f"\n\nADDITIONAL CONTEXT FOR RELEVANCE (use when scoring):\n{relevance_context.strip()}\n"

            prompt = f"""You are an investment analyst. Score how relevant this article is to the investment thesis using ONLY the article title. You do not have the article body—titles can be sensational or vague, so score conservatively.

INVESTMENT THESIS:
{thesis_text[:4000]}...

ARTICLE TITLE ONLY:
{article_title}
{context_block}

Return exactly one JSON object with these keys only (no markdown, no explanation):
{{
  "relevance_score": 65,
  "confidence_score": 70,
  "signal_type": "One of: direct_thesis_match, market_intelligence, other",
  "exec_summary": "1-2 sentence summary of why the title suggests relevance or not",
  "why_it_matters": "Brief reason relevant for investment/market intelligence, or empty if low relevance",
  "thesis_sector": "Thesis sector most relevant (e.g. women's health, care model) or null",
  "focus_area_tags": "Comma-separated tags (e.g. AI health, virtual health) or empty",
  "geography": "Geography if suggested by title or null",
  "companies_mentioned": "Comma-separated company names if any, or empty string",
  "rejection_reason": "Only if relevance_score < 50, brief reason; otherwise null"
}}

Use relevance_score 0-100: 70+ direct thesis match, 50-69 market intelligence, under 50 reject. signal_type: direct_thesis_match for strong alignment, market_intelligence for related context, other otherwise."""

            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 600,
            }

            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
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
