"""Article extractor using Playwright (fetch) + Trafilatura (extract). Preserves tool interface for crew."""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from typing import Type
import json
from datetime import datetime


def _normalize_date(date_str: str | None) -> str:
    """Normalize date to YYYY-MM-DD if possible."""
    if not date_str or not str(date_str).strip():
        return ""
    s = str(date_str).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    try:
        if "T" in s:
            s = s.split("T")[0]
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
            try:
                parsed = datetime.strptime(s[:30], fmt)
                return parsed.strftime("%Y-%m-%d")
            except ValueError:
                continue
    except Exception:
        pass
    return s[:10] if len(s) >= 10 else s


class ArticleExtractorInput(BaseModel):
    """Input schema for Article Extractor Tool."""
    url: str = Field(..., description="The URL of the article to extract content from")


class ArticleExtractorTool(BaseTool):
    """Extracts article content using a real browser (Playwright) and Trafilatura. Better at avoiding blocks and paywalls."""

    name: str = "article_extractor"
    description: str = (
        "Extracts clean article content from web URLs using a real browser and article-specific extraction. "
        "Returns structured JSON with title, text, author, publication date, word count, and extraction status. "
        "Handles paywalls and JS-rendered pages better than simple HTTP requests."
    )
    args_schema: Type[BaseModel] = ArticleExtractorInput

    def _run(self, url: str) -> str:
        result = {
            "title": "",
            "text": "",
            "author": "",
            "published_date": "",
            "url": url,
            "word_count": 0,
            "extraction_status": "COMPLETE",
            "error_message": "",
        }

        try:
            html_content = self._fetch_with_playwright(url)
            if not html_content:
                result["extraction_status"] = "PARTIAL"
                result["error_message"] = "No HTML received from page"
                return json.dumps(result, indent=2)

            # Paywall hint from raw HTML
            html_lower = html_content.lower()
            if any(
                x in html_lower
                for x in (
                    "paywall",
                    "subscription",
                    "subscribe now",
                    "premium content",
                    "login to continue",
                    "register to read",
                    "member exclusive",
                )
            ):
                result["extraction_status"] = "PARTIAL"

            # Trafilatura: extract main text and metadata
            import trafilatura

            text = trafilatura.extract(
                html_content,
                include_comments=False,
                include_tables=True,
                no_fallback=False,
            )
            meta = trafilatura.extract_metadata(html_content)

            if meta:
                result["title"] = (meta.title or "").strip() or result["title"]
                result["author"] = (meta.author or "").strip() or result["author"]
                if meta.date:
                    result["published_date"] = _normalize_date(meta.date)

            if text and isinstance(text, str):
                result["text"] = text.strip()
                result["word_count"] = len(result["text"].split())

            if not result["text"] or len(result["text"]) < 100:
                result["extraction_status"] = "PARTIAL"
                if not result["error_message"]:
                    result["error_message"] = (
                        "Limited content extracted - may be blocked by paywall or unsupported page structure"
                    )

            return json.dumps(result, indent=2)

        except Exception as e:
            result["extraction_status"] = "PARTIAL"
            result["error_message"] = str(e)
            return json.dumps(result, indent=2)

    def _fetch_with_playwright(self, url: str, timeout_ms: int = 30_000) -> str | None:
        """Fetch page HTML using Playwright (headless Chromium). Returns None on failure."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                )
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(2000)
                html = page.content()
            except Exception:
                html = None
            finally:
                browser.close()
        return html
