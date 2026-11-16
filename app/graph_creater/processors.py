from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .models import GraphNode, build_properties, create_node, merge_nodes
from .table_specs import load_table_spec


def _source_ref(table_name: str, column_name: str, primary_key: Any) -> dict[str, Any]:
    return {
        "table": table_name,
        "column": column_name,
        "primary_key": primary_key,
    }


def _build_primary_node(
    table_name: str,
    row: Mapping[str, Any],
    primary_key_column: str,
    node_type: str,
    display_column: str | None = None,
    display_fallback_prefix: str | None = None,
    excluded_columns: Iterable[str] | None = None,
) -> GraphNode | None:
    primary_key = row.get(primary_key_column)
    if primary_key is None:
        return None

    display_value = row.get(display_column) if display_column else None
    if display_value is None or str(display_value).strip() == "":
        prefix = display_fallback_prefix or node_type
        display_value = f"{prefix} {primary_key}"

    properties = build_properties(row, excluded_columns=excluded_columns or ())
    return create_node(
        node_type=node_type,
        business_key=f"{table_name}-{primary_key}",
        display_name=display_value,
        source_ref=_source_ref(table_name, primary_key_column, primary_key),
        properties=properties,
    )


def _build_value_node(
    table_name: str,
    row: Mapping[str, Any],
    primary_key_column: str,
    source_column: str,
    node_type: str,
    display_value: Any | None = None,
    properties: Mapping[str, Any] | None = None,
) -> GraphNode | None:
    value = row.get(source_column)
    if value is None:
        return None

    text_value = str(value).strip()
    if not text_value:
        return None

    node_properties = dict(properties or {})
    return create_node(
        node_type=node_type,
        business_key=text_value,
        display_name=display_value if display_value is not None else text_value,
        source_ref=_source_ref(table_name, source_column, row.get(primary_key_column)),
        properties=node_properties,
    )


def _build_derived_node_properties(row: Mapping[str, Any], derived_node: Mapping[str, Any]) -> dict[str, Any]:
    column = str(derived_node.get("column", "")).strip()
    if not column:
        return {}

    value = row.get(column)
    if value is None:
        return {}

    text_value = str(value).strip()
    if not text_value:
        return {}

    return build_properties({column: value}, excluded_columns=())


def _build_nodes_from_spec(table_name: str, row: Mapping[str, Any]) -> list[GraphNode]:
    spec = load_table_spec(table_name)
    nodes: list[GraphNode] = []

    primary = spec.get("primary_node", {})
    primary_key_column = primary.get("primary_key_column")
    property_exclusions = _get_property_exclusions(spec)

    if primary_key_column:
        primary_node = _build_primary_node(
            table_name,
            row,
            str(primary_key_column),
            str(primary.get("node_type", "")),
            display_column=primary.get("display_column"),
            display_fallback_prefix=primary.get("display_fallback_prefix"),
            excluded_columns=property_exclusions,
        )
        if primary_node is not None:
            nodes.append(primary_node)

    for derived_node in spec.get("derived_nodes", []) or []:
        column = derived_node.get("column")
        node_type = derived_node.get("node_type")
        if not column or not node_type:
            continue

        if not _derived_node_allowed(row, derived_node):
            continue

        node = _build_value_node(
            table_name,
            row,
            str(primary_key_column),
            str(column),
            str(node_type),
            properties=_build_derived_node_properties(row, derived_node),
        )
        if node is not None:
            nodes.append(node)

    return nodes


def _get_property_exclusions(spec: Mapping[str, Any]) -> set[str]:
    properties_spec = spec.get("properties", {}) or {}
    excluded_columns = properties_spec.get("excluded_columns", []) or []
    return {str(column) for column in excluded_columns if str(column).strip()}


def _derived_node_allowed(row: Mapping[str, Any], derived_node: Mapping[str, Any]) -> bool:
    conditions = derived_node.get("conditions", {}) or {}
    field = conditions.get("field")
    allowed_values = conditions.get("allowed_values", []) or []
    if not field or not allowed_values:
        return True

    actual_value = str(row.get(field, "")).strip().lower()
    normalized_allowed = {str(value).strip().lower() for value in allowed_values if str(value).strip()}
    return actual_value in normalized_allowed


def process_qe_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("qe", row)


def process_psp_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("psp", row)


def process_capa_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("capa", row)


def process_containment_actions_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("containment_actions", row)


def process_batch_containment_details_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("batch_containment_details", row)


def process_qe_events_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("qe_events", row)


def process_initial_evaluations_row(row: Mapping[str, Any]) -> list[GraphNode]:
    return _build_nodes_from_spec("initial_evaluations", row)


def process_source_table(table_name: str, rows: Iterable[Mapping[str, Any]]) -> list[GraphNode]:
    nodes: list[GraphNode] = []
    for row in rows:
        nodes.extend(_build_nodes_from_spec(table_name, row))
    return merge_nodes(nodes)
