"""
Thin wrapper around crewai_tools SerplyNewsSearchTool that catches API/JSON errors
and retries with exponential backoff before surfacing an error to the agent.
"""
import json
import sys
import time
from typing import Any

from crewai_tools import SerplyNewsSearchTool

_MAX_RETRIES = 3
_BASE_DELAY = 5  # seconds; delays: 5, 10, 20


class SerplyNewsSearchToolSafe(SerplyNewsSearchTool):
    """
    Same as SerplyNewsSearchTool but retries on rate-limit / transient errors
    with exponential backoff. Returns a clear error string only after all retries
    are exhausted.
    """

    def _run(self, **kwargs: Any) -> Any:
        last_error = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return super()._run(**kwargs)
            except (json.JSONDecodeError, Exception) as e:
                last_error = e
                if attempt < _MAX_RETRIES:
                    delay = _BASE_DELAY * (2 ** (attempt - 1))
                    print(
                        f"[serply_safe] Attempt {attempt}/{_MAX_RETRIES} failed: {e}. "
                        f"Retrying in {delay}s...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)

        return (
            f"Serply news search failed after {_MAX_RETRIES} attempts. "
            f"Last error: {last_error}. Check SERPLY_API_KEY and Serply quota."
        )
