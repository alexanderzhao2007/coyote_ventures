#!/usr/bin/env python
"""Run only the thesis relevance judge (no Discovery). Requires unevaluated candidates in the DB."""
import os
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(script_dir)
project_root = os.path.dirname(package_dir)
sys.path.insert(0, project_root)

_env_path = os.path.join(project_root, ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from coyote_ventures_weekly_intelligence_digest___email_automation.main import run_judge_only

if __name__ == "__main__":
    run_judge_only()
