#!/usr/bin/env python
import os
import sys

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


def train():
    """
    Train the crew for a given number of iterations.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().train(n_iterations=int(sys.argv[1]), filename=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while training the crew: {e}")

def replay():
    """
    Replay the crew execution from a specific task.
    """
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().replay(task_id=sys.argv[1])

    except Exception as e:
        raise Exception(f"An error occurred while replaying the crew: {e}")

def test():
    """
    Test the crew execution and returns the results.
    """
    inputs = {
        'thesis_url': 'https://www.coyote.ventures/thesis'
    }
    try:
        CoyoteVenturesWeeklyIntelligenceDigestEmailAutomationCrew().crew().test(n_iterations=int(sys.argv[1]), openai_model_name=sys.argv[2], inputs=inputs)

    except Exception as e:
        raise Exception(f"An error occurred while testing the crew: {e}")


def run_with_trigger():
    """
    Run the crew with trigger payload (e.g. from CrewAI triggers). Payload is passed as JSON in argv[1].
    """
    import json
    if len(sys.argv) < 2:
        raise Exception("No trigger payload provided. Please provide JSON payload as argument.")
    try:
        trigger_payload = json.loads(sys.argv[1])
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
        train()
    elif command == "replay":
        replay()
    elif command == "test":
        test()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
