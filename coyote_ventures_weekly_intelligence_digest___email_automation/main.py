#!/usr/bin/env python
import os
import sys

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

# This main file is intended to be a way for your to run your
# crew locally, so refrain from adding unnecessary logic into this file.
# Replace with inputs you want to test with, it will automatically
# interpolate any tasks and agents information

def run():
    """
    Run the crew.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().kickoff(inputs=inputs)


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
