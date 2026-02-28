"""
Thin wrapper around crewai_tools SerplyNewsSearchTool that catches API/JSON errors
and returns a clear message instead of "Expecting value: line 1 column 1 (char 0)".
"""
import json
from typing import Any

from crewai_tools import SerplyNewsSearchTool


class SerplyNewsSearchToolSafe(SerplyNewsSearchTool):
    """
    Same as SerplyNewsSearchTool but on empty/non-JSON or request errors returns
    a clear error string so the agent can retry or report (e.g. rate limit, bad key).
    """

    def _run(self, **kwargs: Any) -> Any:
        try:
            return super()._run(**kwargs)
        except json.JSONDecodeError as e:
            return (
                f"Serply news API returned invalid or empty JSON (often rate limit or server error). "
                f"Error: {e}. Check SERPLY_API_KEY and Serply quota; wait a minute and retry this search."
            )
        except Exception as e:
            return (
                f"Serply news search failed: {e}. "
                f"Check SERPLY_API_KEY and network; retry this search later."
            )
