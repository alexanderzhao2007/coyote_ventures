#!/usr/bin/env python
import os
import sys
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
        print(f"[judge_loop] Error checking unevaluated count: {e}", file=sys.stderr)
        return 0


def _drain_judge(factory, inputs, max_rounds: int = 20) -> int:
    """Run the judge crew in a loop until all unevaluated candidates are processed.
    Returns total number of candidates evaluated across all rounds."""
    total_processed = 0

    for round_num in range(1, max_rounds + 1):
        remaining = _unevaluated_count()
        print(f"\n[judge_loop] Round {round_num}: {remaining} unevaluated candidates remaining")
        if remaining == 0:
            print(f"[judge_loop] All candidates evaluated ({total_processed} total). Done.")
            break

        before = remaining
        factory.crew_judge_only().kickoff(inputs=inputs)
        after = _unevaluated_count()
        processed_this_round = before - after
        total_processed += processed_this_round
        print(f"[judge_loop] Round {round_num} complete: processed {processed_this_round}, {after} remaining")

        if processed_this_round == 0:
            print("[judge_loop] No progress this round — stopping to avoid infinite loop.", file=sys.stderr)
            break

        if _unevaluated_count() > 0:
            print("[judge_loop] Sleeping 30s before next round to avoid rate limits...")
            time.sleep(30)
    else:
        print(f"[judge_loop] Reached max rounds ({max_rounds}). {_unevaluated_count()} still unevaluated.", file=sys.stderr)

    print(f"[judge_loop] Finished. Total evaluated across all rounds: {total_processed}")
    return total_processed


def run():
    """
    Run the full automation: discovery then judge.
    After the combined crew finishes (discovery + one judge batch),
    a programmatic loop drains any remaining unevaluated candidates.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    factory = CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew()

    print("[run] Starting full crew (discovery + judge)...")
    factory.crew().kickoff(inputs=inputs)

    remaining = _unevaluated_count()
    if remaining > 0:
        print(f"\n[run] Full crew finished but {remaining} candidates still unevaluated. Starting judge drain loop...")
        _drain_judge(factory, inputs)
    else:
        print("[run] All candidates evaluated after full crew run. Done.")


def run_judge_only():
    """
    Run only the thesis relevance judge (evaluate task). No Discovery.
    Requires unevaluated candidates already in the DB (e.g. from a prior run or seed).
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    factory = CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew()
    _drain_judge(factory, inputs)


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
    import json
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
