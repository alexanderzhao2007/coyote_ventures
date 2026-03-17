"""Weekly digest email pipeline: fetch top articles, build HTML email, send via Postmark, mark sent."""

import os
import sys
import json
import re
from datetime import date
from typing import List, Dict, Optional
from rapidfuzz import fuzz

_DIGEST_CPG_KEYWORDS = re.compile(
    r"supplement|nutraceutical|nutriceutical|vitamin[s]?\b|protein powder"
    r"|meal replacement|clean product|clean food|clean beverage|clean label"
    r"|superfood|probiotic|collagen|dietary supplement|sports nutrition"
    r"|whey|plant-based protein|gumm(?:y|ies)",
    re.IGNORECASE,
)


def _deduplicate_articles(articles: List[Dict], threshold: int = 75) -> List[Dict]:
    """Remove near-duplicate articles, keeping the higher-scored one.

    Input is assumed sorted DESC by relevance_score, so the first article in any
    duplicate pair is always the higher-scored one — we simply discard the later one.
    """
    kept: List[Dict] = []
    for candidate in articles:
        c_title = (candidate.get("title") or "").lower()
        is_dup = any(
            fuzz.token_set_ratio(c_title, (k.get("title") or "").lower()) >= threshold
            for k in kept
        )
        if is_dup:
            print(
                f"[digest] Dedup removed: {candidate.get('title', '')[:80]}",
                file=sys.stderr,
            )
        else:
            kept.append(candidate)
    return kept


def _get_supabase_client():
    supabase_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")
    from supabase import create_client
    return create_client(supabase_url, key)


def fetch_top_articles(limit: int = 7) -> List[Dict]:
    """Fetch top unsent articles from coyote_articles, sorted by relevance_score DESC."""
    client = _get_supabase_client()
    result = (
        client.table("coyote_articles")
        .select(
            "id, url, title, source, published_date, "
            "relevance_score, exec_summary, why_it_matters, focus_area_tags"
        )
        .eq("sent_in_weekly_digest", False)
        .not_.is_("relevance_score", "null")
        .gt("relevance_score", 0)
        .order("relevance_score", desc=True)
        .limit(limit + 3)
        .execute()
    )
    articles = result.data or []

    filtered: List[Dict] = []
    for art in articles:
        haystack = " ".join(
            str(art.get(f) or "") for f in ("title", "exec_summary", "focus_area_tags")
        )
        if _DIGEST_CPG_KEYWORDS.search(haystack):
            print(
                f"[digest] Post-fetch CPG filter removed: {art.get('title', '')[:80]}",
                file=sys.stderr,
            )
            continue
        filtered.append(art)
    return _deduplicate_articles(filtered)[:limit]


def build_email_html(articles: List[Dict]) -> str:
    """Build a clean, human-curated HTML email from article data. No LLM involved."""
    today = date.today().strftime("%B %d, %Y")
    article_sections = []

    for article in articles:
        title = article.get("title") or "Untitled"
        url = article.get("url") or "#"
        pub_date = article.get("published_date") or ""
        if pub_date:
            try:
                from datetime import datetime
                dt = datetime.strptime(str(pub_date)[:10], "%Y-%m-%d")
                pub_date = dt.strftime("%B %d, %Y")
            except (ValueError, TypeError):
                pass

        exec_summary = article.get("exec_summary") or ""
        why_it_matters = article.get("why_it_matters") or ""
        focus_area_tags = article.get("focus_area_tags") or ""
        relevance_score = article.get("relevance_score")
        score_display = f"Score: {int(relevance_score)}" if relevance_score is not None else ""

        meta_parts = [p for p in [focus_area_tags, score_display] if p]
        meta_line = " · ".join(meta_parts)

        section = f"""
        <tr><td style="padding: 0 0 32px 0;">
            <a href="{url}" style="font-size: 18px; font-weight: 600; color: #1a1a1a; text-decoration: none;">
                {title}</a>{f' <span style="color: #666; font-weight: 400;">— {pub_date}</span>' if pub_date else ''}
            {f'<p style="margin: 8px 0 0 0; font-size: 15px; line-height: 1.6; color: #333;">{exec_summary}</p>' if exec_summary else ''}
            {f'<p style="margin: 4px 0 0 0; font-size: 15px; line-height: 1.6; color: #555; font-style: italic;">{why_it_matters}</p>' if why_it_matters else ''}
            {f'<p style="margin: 6px 0 0 0; font-size: 13px; color: #888;">{meta_line}</p>' if meta_line else ''}
            <p style="margin: 10px 0 0 0;">
                <a href="{url}" style="display: inline-block; padding: 6px 16px; font-size: 13px; color: #fff; background-color: #2a2a2a; border-radius: 4px; text-decoration: none;">
                    Read Article</a>
            </p>
        </td></tr>"""
        article_sections.append(section)

    divider = '<tr><td style="padding: 0 0 32px 0; border-bottom: 1px solid #e0e0e0;"></td></tr><tr><td style="padding: 16px 0 0 0;"></td></tr>'
    articles_html = divider.join(article_sections)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin: 0; padding: 0; background-color: #f4f4f4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4;">
<tr><td align="center" style="padding: 40px 20px;">
    <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; padding: 40px;">
    <tr><td style="padding: 0 0 8px 0;">
        <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #1a1a1a;">
            Coyote Ventures Weekly Intelligence Digest</h1>
        <p style="margin: 8px 0 32px 0; font-size: 14px; color: #888;">{today} · {len(articles)} articles</p>
    </td></tr>
    {articles_html}
    <tr><td style="padding: 32px 0 0 0; border-top: 1px solid #e0e0e0;">
        <p style="margin: 0; font-size: 12px; color: #aaa;">
            This digest was automatically curated from articles scored by the Coyote Ventures intelligence pipeline.</p>
    </td></tr>
    </table>
</td></tr>
</table>
</body>
</html>"""
    return html


def send_email(subject: str, html_body: str) -> dict:
    """Send the digest email via Postmark. Returns the Postmark API response."""
    server_token = os.environ.get("POSTMARK_SERVER_TOKEN")
    from_email = os.environ.get("DIGEST_FROM_EMAIL")
    to_email = os.environ.get("DIGEST_RECIPIENT_EMAIL")

    missing = []
    if not server_token:
        missing.append("POSTMARK_SERVER_TOKEN")
    if not from_email:
        missing.append("DIGEST_FROM_EMAIL")
    if not to_email:
        missing.append("DIGEST_RECIPIENT_EMAIL")
    if missing:
        raise RuntimeError(f"Missing env vars: {', '.join(missing)}")

    from postmarker.core import PostmarkClient
    client = PostmarkClient(server_token=server_token)

    recipients = [addr.strip() for addr in to_email.split(",")]
    response = client.emails.send(
        From=from_email,
        To=",".join(recipients),
        Subject=subject,
        HtmlBody=html_body,
    )
    return response


def _suppress_near_duplicate_articles(client, sent_ids: List[str], threshold: int = 75) -> int:
    """Mark unsent near-duplicates of just-sent articles as sent.

    After a digest is sent, any unsent article whose title is a near-duplicate of a
    sent article is suppressed so it never appears in a future digest. This prevents
    the same story resurfacing in a later week because it scored slightly lower.
    """
    # Fetch titles of the articles we just sent
    try:
        sent_result = (
            client.table("coyote_candidates")
            .select("id, title")
            .in_("id", sent_ids)
            .execute()
        )
    except Exception as e:
        print(f"[digest] Could not fetch sent titles for dedup suppression: {e}", file=sys.stderr)
        return 0

    sent_titles = [
        (a["id"], (a.get("title") or "").lower())
        for a in (sent_result.data or [])
    ]
    if not sent_titles:
        return 0

    # Fetch all remaining unsent articles
    try:
        unsent_result = (
            client.table("coyote_articles")
            .select("id, title")
            .eq("sent_in_weekly_digest", False)
            .execute()
        )
    except Exception as e:
        print(f"[digest] Could not fetch unsent articles for dedup suppression: {e}", file=sys.stderr)
        return 0

    suppressed = 0
    for unsent in (unsent_result.data or []):
        unsent_title = (unsent.get("title") or "").lower()
        unsent_id = unsent["id"]
        for _, sent_title in sent_titles:
            if fuzz.token_set_ratio(unsent_title, sent_title) >= threshold:
                try:
                    client.table("coyote_article_evaluations").update(
                        {"sent_in_weekly_digest": True}
                    ).eq("candidate_id", unsent_id).execute()
                    suppressed += 1
                    print(
                        f"[digest] Suppressed near-duplicate of sent article: {unsent.get('title', '')[:80]}",
                        file=sys.stderr,
                    )
                except Exception as e:
                    print(f"[digest] Error suppressing duplicate {unsent_id}: {e}", file=sys.stderr)
                break  # only suppress once per unsent article

    return suppressed


def mark_articles_sent(article_ids: List[str]) -> int:
    """Set sent_in_weekly_digest=true for the given article IDs (candidate_ids).

    Also suppresses unsent near-duplicates of the sent articles so they don't
    resurface in future digests. Returns count of articles marked (sent + suppressed).
    """
    if not article_ids:
        return 0
    client = _get_supabase_client()
    updated = 0
    for aid in article_ids:
        try:
            client.table("coyote_article_evaluations").update(
                {"sent_in_weekly_digest": True}
            ).eq("candidate_id", aid).execute()
            updated += 1
        except Exception as e:
            print(f"[digest] Error marking article {aid} as sent: {e}", file=sys.stderr)

    suppressed = _suppress_near_duplicate_articles(client, article_ids)
    if suppressed:
        print(f"[digest] Suppressed {suppressed} near-duplicate article(s).", file=sys.stderr)

    return updated
