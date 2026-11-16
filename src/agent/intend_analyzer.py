from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"

for candidate in (PROJECT_ROOT, SRC_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

try:
    from src.agent.pipeline import process_query
except ModuleNotFoundError:
    from agent.pipeline import process_query


def analyze_intent(query: str) -> dict:
    """Compatibility helper for existing callers.

    Returns the intent stage output when available.
    """

    result = process_query(query)
    if result.get("status") == "VALID":
        return result["intent"]
    raise RuntimeError(f"Pipeline failed at {result.get('stage')}: {result.get('errors')}")


if __name__ == "__main__":
    user_query = input("Query: ")
    pipeline_result = process_query(user_query)
    print(json.dumps(pipeline_result, indent=2, default=str))