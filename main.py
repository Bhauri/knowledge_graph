from __future__ import annotations

import json

from src.agent.pipeline import process_query


if __name__ == "__main__":
    query = input("Query: ")
    result = process_query(query)
    print(json.dumps(result, indent=2, default=str))
