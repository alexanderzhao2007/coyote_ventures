"""Preview the weekly digest email in a browser without sending it."""

import os
import sys
import tempfile
import webbrowser

_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_env_path = os.path.join(_root, ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, _root)

from coyote_ventures_weekly_intelligence_digest___email_automation.tools.weekly_digest import (
    fetch_top_articles,
    build_email_html,
)

articles = fetch_top_articles(limit=10)
if not articles:
    print("[preview] No unsent articles found in coyote_articles.")
    sys.exit(0)

html = build_email_html(articles)
tmp = os.path.join(tempfile.gettempdir(), "digest_preview.html")
with open(tmp, "w", encoding="utf-8") as f:
    f.write(html)
webbrowser.open(f"file:///{tmp}")
print(f"[preview] Opened preview with {len(articles)} articles: {tmp}")
