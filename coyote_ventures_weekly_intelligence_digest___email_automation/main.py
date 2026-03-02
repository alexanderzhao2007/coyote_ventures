#!/usr/bin/env python
import os
import sys
import json
import time

# Use UTF-8 for stdout/stderr on Windows so CrewAI event bus (emoji) doesn't cause
# "Sync handler error" and event pairing mismatch warnings
if sys.platform == "win32":
    import io
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Load .env from project root so SUPABASE_* and API keys are set when tools run
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_env_path = os.path.join(_root, ".env")
if os.path.isfile(_env_path):
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

from coyote_ventures_weekly_intelligence_digest___email_automation.crew import CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_read_candidates import SupabaseReadCandidatesTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.thesis_title_relevance_tool import ThesisTitleRelevanceTool
from coyote_ventures_weekly_intelligence_digest___email_automation.tools.supabase_write_evaluations import SupabaseWriteEvaluationsTool


def _unevaluated_count() -> int:
    """Direct Supabase query for remaining unevaluated candidates."""
    supabase_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not key:
        return 0
    try:
        from supabase import create_client
        client = create_client(supabase_url, key)
        result = (
            client.table("coyote_candidates_unevaluated")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        return result.count or 0
    except Exception as e:
        print(f"[evaluate] Error checking unevaluated count: {e}", file=sys.stderr)
        return 0


def evaluate_batch(batch_size: int = 3) -> int:
    """Score and write one batch of unevaluated candidates. Returns count processed."""
    reader = SupabaseReadCandidatesTool()
    scorer = ThesisTitleRelevanceTool()
    writer = SupabaseWriteEvaluationsTool()

    raw = json.loads(reader._run(limit=batch_size, offset=0))
    articles = raw.get("articles", [])
    if not articles:
        return 0

    processed = 0
    for article in articles:
        title = article.get("title", "")
        candidate_id = article.get("id", "")
        if not title or not candidate_id:
            print(f"[evaluate] Skipping article with missing title or id: {article}", file=sys.stderr)
            continue
        try:
            result = json.loads(scorer._run(article_title=title, use_static_thesis=True))
            result["candidate_id"] = candidate_id
            writer._run(evaluations_json=json.dumps([result]))
            score = result.get("relevance_score", "?")
            print(f"[evaluate] Scored '{title[:80]}' -> {score}")
            processed += 1
        except Exception as e:
            print(f"[evaluate] Error scoring '{title[:80]}': {e}", file=sys.stderr)

    return processed


def evaluate_all(batch_size: int = 3, sleep_between: int = 2) -> int:
    """Evaluate all unevaluated candidates in batches. Returns total processed."""
    total = 0
    while True:
        remaining = _unevaluated_count()
        if remaining == 0:
            break
        print(f"\n[evaluate] {remaining} unevaluated candidates remaining")
        processed = evaluate_batch(batch_size)
        total += processed
        if processed == 0:
            print("[evaluate] Batch returned 0 processed — stopping.", file=sys.stderr)
            break
        time.sleep(sleep_between)

    print(f"[evaluate] Finished. Total evaluated: {total}")
    return total


def run():
    """
    Run the full automation: discovery crew then direct evaluation pipeline.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    factory = CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew()

    print("[run] Starting discovery crew...")
    factory.crew().kickoff(inputs=inputs)

    remaining = _unevaluated_count()
    if remaining > 0:
        print(f"\n[run] Discovery complete. {remaining} candidates to evaluate...")
        evaluate_all()
    else:
        print("[run] No candidates to evaluate. Done.")


def run_judge_only():
    """
    Evaluate unevaluated candidates directly (no discovery, no agent).
    Requires unevaluated candidates already in the DB (e.g. from a prior run or seed).
    """
    evaluate_all()


def _clear_evaluations() -> int:
    """Delete all rows from coyote_article_evaluations. Returns count deleted."""
    supabase_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    if not supabase_url or not key:
        print("[rescore] SUPABASE_URL and SUPABASE_SERVICE_KEY must be set.", file=sys.stderr)
        return 0
    try:
        from supabase import create_client
        client = create_client(supabase_url, key)
        result = (
            client.table("coyote_article_evaluations")
            .select("id", count="exact")
            .limit(1)
            .execute()
        )
        total = result.count or 0
        if total == 0:
            print("[rescore] No existing evaluations to delete.")
            return 0
        print(f"[rescore] Deleting {total} existing evaluations...")
        client.table("coyote_article_evaluations").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
        print(f"[rescore] Deleted {total} evaluations.")
        return total
    except Exception as e:
        print(f"[rescore] Error clearing evaluations: {e}", file=sys.stderr)
        return 0


def rescore():
    """
    Delete all existing evaluations and re-score every candidate article
    using the current scoring prompt/rubric.
    """
    _clear_evaluations()
    remaining = _unevaluated_count()
    print(f"[rescore] {remaining} candidates now unevaluated. Starting evaluation...")
    evaluate_all()
    print("[rescore] Rescore complete.")


def train(n_iterations: int, filename: str):
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().train(
            n_iterations=n_iterations,
            filename=filename,
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")


def replay(task_id: str):
    """
    Replay the crew execution from a specific task.
    """
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().replay(task_id=task_id)
    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")


def test(n_iterations: int, openai_model_name: str):
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().test(
            n_iterations=n_iterations,
            openai_model_name=openai_model_name,
            inputs=inputs,
        )
    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger(trigger_payload_json: str):
    """
    Run the crew with trigger payload (e.g. from CrewAI triggers). Payload is passed as JSON in argv[1].
    """
    try:
        trigger_payload = json.loads(trigger_payload_json)
    except json.JSONDecodeError:
        raise Exception("Invalid JSON payload provided as argument")
    inputs = {
        "thesis_url": "https://www.coyote.ventures/thesis",
        "crewai_trigger_payload": trigger_payload,
    }
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().kickoff(inputs=inputs)
    except Exception as e:
        raise Exception(f"An error occurred while running the crew with trigger: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: main.py <command> [<args>]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "run":
        run()
    elif command == "run_judge_only":
        run_judge_only()
    elif command == "rescore":
        rescore()
    elif command == "train":
        if len(sys.argv) < 4:
            print("Usage: main.py train <n_iterations> <filename>")
            sys.exit(1)
        train(int(sys.argv[2]), sys.argv[3])
    elif command == "replay":
        if len(sys.argv) < 3:
            print("Usage: main.py replay <task_id>")
            sys.exit(1)
        replay(sys.argv[2])
    elif command == "test":
        if len(sys.argv) < 4:
            print("Usage: main.py test <n_iterations> <openai_model_name>")
            sys.exit(1)
        test(int(sys.argv[2]), sys.argv[3])
    elif command == "run_with_trigger":
        if len(sys.argv) < 3:
            print("Usage: main.py run_with_trigger <trigger_payload_json>")
            sys.exit(1)
        run_with_trigger(sys.argv[2])
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
