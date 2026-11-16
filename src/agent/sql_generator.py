from __future__ import annotations

import re
from typing import Any


class SQLGenerator:
    @staticmethod
    def _parse_canonical(canonical_name: str) -> tuple[str, str]:
        cleaned = canonical_name.strip()
        if "." in cleaned:
            entity, property_key = cleaned.split(".", 1)
            return entity, property_key
        return "", cleaned

    @staticmethod
    def _safe_json_key(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _is_number(value: Any) -> bool:
        if isinstance(value, (int, float)):
            return True
        if not isinstance(value, str):
            return False
        return bool(re.fullmatch(r"[-+]?\d+(\.\d+)?", value.strip()))

    def _build_filter_clause(
        self,
        node_alias: str,
        property_key: str,
        operator: str,
        param_name: str,
        value: Any,
        parameters: dict[str, Any],
    ) -> str:
        op = operator.upper()
        json_expr = f"({node_alias}.properties ->> '{self._safe_json_key(property_key)}')"

        if op == "IN":
            if isinstance(value, (list, tuple, set)):
                parameters[param_name] = [str(item) for item in value]
            else:
                parameters[param_name] = [item.strip() for item in str(value).split(",") if item.strip()]
            return f"list_contains(${param_name}, {json_expr})"

        if op == "LIKE":
            parameters[param_name] = str(value)
            return f"{json_expr} LIKE ${param_name}"

        if op in {">", "<", ">=", "<="} and self._is_number(value):
            parameters[param_name] = float(value)
            return f"{json_expr}::DOUBLE {op} ${param_name}"

        parameters[param_name] = str(value)
        return f"{json_expr} {operator} ${param_name}"

    def generate(self, query_plan: dict[str, Any]) -> dict[str, Any]:
        if query_plan.get("status") != "VALID":
            raise ValueError("Cannot generate SQL for non-VALID plan")

        target_entity = str(query_plan["target_entity"])
        operation = str(query_plan.get("operation", "")).upper()

        select_clause = (
            "COUNT(DISTINCT n0.node_uuid) AS value"
            if operation == "COUNT"
            else "n0.node_uuid, n0.node_type, n0.business_key, n0.display_name, n0.properties"
        )

        from_clause = "FROM graph_nodes n0"
        join_clauses: list[str] = []
        where_clauses: list[str] = []

        parameters: dict[str, Any] = {}
        where_clauses.append("n0.node_type = $target_node_type")
        parameters["target_node_type"] = target_entity

        alias_map: dict[str, str] = {"root": "n0"}

        for idx, filter_item in enumerate(query_plan.get("filters", [])):
            selected = filter_item.get("selected") or {}
            canonical = str(selected.get("canonical_name") or "")
            property_entity, property_key = self._parse_canonical(canonical)
            if not property_key:
                raise ValueError(f"Missing property mapping for filter: {filter_item.get('concept')}")

            path = filter_item.get("path", [])
            current_alias = "n0"

            for step_index, edge in enumerate(path):
                edge_alias = f"e_{idx}_{step_index}"
                next_alias = f"n_{idx}_{step_index + 1}"
                rel_param = f"rel_{idx}_{step_index}"
                node_type_param = f"node_type_{idx}_{step_index + 1}"

                parameters[rel_param] = str(edge["relationship"])
                parameters[node_type_param] = str(edge["to"])

                join_clauses.append(
                    f"JOIN graph_edges {edge_alias} ON {edge_alias}.from_node_uuid = {current_alias}.node_uuid "
                    f"AND {edge_alias}.relationship = ${rel_param}"
                )
                join_clauses.append(
                    f"JOIN graph_nodes {next_alias} ON {next_alias}.node_uuid = {edge_alias}.to_node_uuid "
                    f"AND {next_alias}.node_type = ${node_type_param}"
                )

                alias_map[f"filter_{idx}_step_{step_index + 1}"] = next_alias
                current_alias = next_alias

            if property_entity:
                entity_param = f"filter_entity_{idx}"
                parameters[entity_param] = property_entity
                where_clauses.append(f"{current_alias}.node_type = ${entity_param}")

            operator = str(filter_item.get("operator", "=")).upper()
            param_name = f"p{idx}"
            value = filter_item.get("value")
            where_clauses.append(
                self._build_filter_clause(
                    node_alias=current_alias,
                    property_key=property_key,
                    operator=operator,
                    param_name=param_name,
                    value=value,
                    parameters=parameters,
                )
            )

        sql_parts = [f"SELECT {select_clause}", from_clause]
        if join_clauses:
            sql_parts.extend(join_clauses)
        if where_clauses:
            sql_parts.append("WHERE " + " AND ".join(where_clauses))

        group_by = query_plan.get("group_by", [])
        group_expressions: list[str] = []
        group_selects: list[str] = []
        for group_index, group_item in enumerate(group_by):
            group_field = str(group_item)
            group_expr = f"n0.properties ->> '{self._safe_json_key(group_field)}'"
            group_expressions.append(group_expr)
            group_selects.append(f"{group_expr} AS group_{group_index}")

        if group_expressions:
            if operation == "COUNT":
                sql_parts[0] = f"SELECT {', '.join(group_selects)}, COUNT(DISTINCT n0.node_uuid) AS value"
            sql_parts.append("GROUP BY " + ", ".join(group_expressions))

        sort = query_plan.get("sort", [])
        if sort:
            order_parts: list[str] = []
            for item in sort:
                if isinstance(item, dict):
                    field = str(item.get("field", "")).strip()
                    direction = str(item.get("direction", "ASC")).upper()
                else:
                    field = str(item).strip()
                    direction = "ASC"

                if not field:
                    continue
                if direction not in {"ASC", "DESC"}:
                    direction = "ASC"

                expr = f"n0.properties ->> '{self._safe_json_key(field)}'"
                order_parts.append(f"{expr} {direction}")

            if order_parts:
                sql_parts.append("ORDER BY " + ", ".join(order_parts))

        if query_plan.get("limit"):
            sql_parts.append("LIMIT $limit")
            parameters["limit"] = int(query_plan["limit"])

        return {
            "sql": "\n".join(sql_parts),
            "parameters": parameters,
            "aliases": alias_map,
            "tables": ["graph_nodes", "graph_edges"],
        }
