from __future__ import annotations

import re
from typing import Any

from db.database import Database


class SQLValidator:
    _ALLOWED_OPERATORS = {"=", "!=", ">", "<", ">=", "<=", "IN", "LIKE"}

    def __init__(self) -> None:
        self.db = Database()

    @staticmethod
    def _extract_tables(sql_text: str) -> set[str]:
        matches = re.findall(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", sql_text, flags=re.IGNORECASE)
        return {name.lower() for name in matches}

    def validate(self, query_plan: dict[str, Any], generated: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []

        if query_plan.get("status") != "VALID":
            return {"status": "INVALID", "errors": ["Query plan is not VALID"]}

        graph_node_columns = self.db.table_columns("main", "graph_nodes")
        graph_edge_columns = self.db.table_columns("main", "graph_edges")
        if not graph_node_columns:
            errors.append("Missing required table graph_nodes")
        if not graph_edge_columns:
            errors.append("Missing required table graph_edges")

        sql_text = generated.get("sql", "")
        if not sql_text or "$" not in sql_text:
            errors.append("Generated SQL is empty or not parameterized")
            return {"status": "VALID" if not errors else "INVALID", "errors": errors}

        used_tables = self._extract_tables(sql_text)
        disallowed_tables = used_tables - {"graph_nodes", "graph_edges"}
        if disallowed_tables:
            errors.append(
                "SQL uses disallowed tables: "
                + ", ".join(sorted(disallowed_tables))
            )

        if "graph_nodes" not in used_tables:
            errors.append("SQL must reference graph_nodes")

        for filter_item in query_plan.get("filters", []):
            if filter_item.get("status") != "RESOLVED":
                errors.append(f"Unresolved filter concept: {filter_item.get('concept')}")
                continue

            selected = filter_item.get("selected") or {}
            canonical = str(selected.get("canonical_name") or "")
            if "." not in canonical:
                errors.append(f"Invalid canonical mapping: {canonical}")
                continue

            _, property_key = canonical.split(".", 1)
            if not property_key.strip():
                errors.append(f"Invalid property mapping in canonical name: {canonical}")

            operator = str(filter_item.get("operator", "")).upper()
            if operator not in self._ALLOWED_OPERATORS:
                errors.append(f"Unsupported operator: {operator}")

        return {"status": "VALID" if not errors else "INVALID", "errors": errors}
