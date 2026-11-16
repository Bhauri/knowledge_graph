from __future__ import annotations

import json
from typing import Any

from config import get_bedrock_client, get_config


PROMPT = """
You are a query parser for a Quality Management system.

Extract the user's request without resolving database meaning.

Return ONLY JSON:

{
  "operation": "COUNT|RETRIEVE|EXISTS|SUM|AVERAGE|MIN|MAX",
  "target_entity": "...",
  "filters": [
    {
      "text": "...",
      "business_concept": "...",
      "value": "...",
      "entity_context": "..."
    }
  ],
  "group_by": [],
  "sort": [],
  "limit": null
}

Rules:
- target_entity = the main object the user wants returned/count.
- entity_context = ONLY a valid business entity:
  Batch, CAPA, ContainmentAction, Evaluation,
  PSP, QEEvent, QualityEvent
- business_concepts = overdue, open, closed, high priority, low priority, root cause, created by, 
assigned to, create_Date, origin, location, severity, type, category, subcategory, etc.
- entity_context can not be business_concepts and vice versa.
- NEVER put a property name in entity_context.
- NEVER put a concept name in entity_context.
- Do not resolve concepts to database columns.
- Do not resolve relationships.
- Extract the user's business phrase as text.
- target_entity is the main entity being requested.
- Preserve filter wording from the user.
- Do NOT invent business concepts.
- Do NOT convert words into database properties.
- Do NOT choose columns.
- Do NOT resolve relationships.
- Related entities go in entity_context only when explicitly clear.
- Return ONLY valid JSON.
"""

class IntentAnalyzer:
    def analyze(self, user_query: str) -> dict[str, Any]:
        if not user_query.strip():
            raise ValueError("Query cannot be empty")

        cfg = get_config()

        response = get_bedrock_client().converse(
            modelId=cfg.bedrock_model_id,
            system=[{"text": PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_query}]}],
            inferenceConfig={"temperature": 0, "maxTokens": 800},
        )

        text_response = response["output"]["message"]["content"][0]["text"].strip()
        if text_response.startswith("```"):
            text_response = text_response.replace("```json", "").replace("```", "").strip()

        return json.loads(text_response)
