#!/usr/bin/env python
"""Quick test: run supabase_read_candidates and print output. Run from project root with .env set."""
import os
import sys
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
package_dir = os.path.dirname(script_dir)
project_root = os.path.dirname(package_dir)
sys.path.insert(0, project_root)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(project_root, ".env"))
except ImportError:
    pass

from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_read_candidates import SupabaseReadCandidatesTool

def main():
    tool = SupabaseReadCandidatesTool()
    result = tool._run(limit=5)
    parsed = json.loads(result)
    print("--- Supabase read candidates output ---")
    print(json.dumps(parsed, indent=2))
    print("--- End ---")

if __name__ == "__main__":
    main()
