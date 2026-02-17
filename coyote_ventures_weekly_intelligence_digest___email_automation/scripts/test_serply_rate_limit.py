#!/usr/bin/env python
"""
Test Serply news API: multiple requests in sequence to check rate limits and response shape.
Run from project root so .env is loaded (SERPLY_API_KEY).

  cd /path/to/coyote_ventures
  python coyote_ventures_weekly_intelligence_digest___email_automation/scripts/test_serply_rate_limit.py
"""
import os
import sys
import json
import time

# Project root = parent of coyote_ventures_weekly_intelligence_digest___email_automation
_script_dir = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(os.path.dirname(_script_dir))
_env = os.path.join(_root, ".env")
if os.path.isfile(_env):
    from dotenv import load_dotenv
    load_dotenv(_env)

try:
    import requests
except ImportError:
    print("Install requests: pip install requests", file=sys.stderr)
    sys.exit(1)


def main():
    api_key = os.getenv("SERPLY_API_KEY")
    if not api_key:
        print("SERPLY_API_KEY not set in .env or environment.", file=sys.stderr)
        sys.exit(1)

    base = "https://api.serply.io/v1/news"
    headers = {"X-Api-Key": api_key}
    # Simulate agent: 3 searches in quick succession (agent does 12)
    queries = ["health funding", "women's health", "healthcare innovation"]
    print(f"Making {len(queries)} Serply news requests...")
    for i, q in enumerate(queries):
        url = f"{base}/q={requests.utils.quote(q)}"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            body_preview = (r.text or "")[:200]
            is_json = False
            if r.text and r.text.strip():
                try:
                    json.loads(r.text)
                    is_json = True
                except json.JSONDecodeError:
                    pass
            print(f"  {i+1}. q={q!r} -> status={r.status_code} json={is_json} body_start={body_preview!r}")
            if r.status_code == 429:
                print("  -> Rate limited (429). Wait or check Serply quota.")
            elif r.status_code in (401, 403):
                print("  -> Auth error. Check SERPLY_API_KEY.")
            if i < len(queries) - 1:
                time.sleep(0.5)
        except requests.RequestException as e:
            print(f"  {i+1}. q={q!r} -> error: {e}")
    print("Done.")


if __name__ == "__main__":
    main()
