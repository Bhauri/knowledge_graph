from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4


_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class GraphNode:
    node_uuid: UUID = field(default_factory=uuid4)
    node_type: str = ""
    business_key: str = ""
    display_name: str = ""
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    embedding_chunk_id: UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def normalize_key(value: Any, max_length: int = 255) -> str:
    if value is None:
        return ""

    key = str(value).strip().lower()
    key = _NON_ALNUM.sub("-", key)
    key = re.sub(r"-+", "-", key).strip("-")

    if len(key) <= max_length:
        return key

    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{key[: max_length - 13]}-{digest}"


def _json_safe_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral() else float(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [_json_safe_value(item) for item in value if item is not None]
    return value


def build_properties(row: Mapping[str, Any], excluded_columns: Iterable[str] = ()) -> dict[str, Any]:
    excluded = {column.lower() for column in excluded_columns}
    properties: dict[str, Any] = {}

    for column, value in row.items():
        if column.lower() in excluded or value is None:
            continue
        properties[column] = _json_safe_value(value)

    return properties


def _normalize_source_ref(source_ref: Mapping[str, Any]) -> dict[str, Any]:
    table = str(source_ref.get("table", "")).strip()
    column = str(source_ref.get("column", "")).strip()
    primary_key = source_ref.get("primary_key")

    return {
        "table": table,
        "column": column,
        "primary_key": _json_safe_value(primary_key),
    }


def update_source_refs(
    existing: Sequence[Mapping[str, Any]] | None,
    new_ref: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()

    def _append(ref: Mapping[str, Any]) -> None:
        normalized = _normalize_source_ref(ref)
        key = (normalized["table"], normalized["column"], normalized["primary_key"])
        if key in seen:
            return
        seen.add(key)
        refs.append(normalized)

    for ref in existing or []:
        _append(ref)

    if isinstance(new_ref, Mapping):
        _append(new_ref)
    else:
        for ref in new_ref:
            _append(ref)

    return refs


def create_node(
    *,
    node_type: str,
    business_key: Any,
    display_name: Any,
    source_ref: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    properties: Mapping[str, Any],
    embedding_chunk_id: UUID | None = None,
) -> GraphNode:
    normalized_display = str(display_name).strip() if display_name is not None else ""
    normalized_display = normalized_display[:255]

    business_key_value = normalize_key(business_key)
    if not business_key_value:
        raise ValueError("business_key must not be empty after normalization")

    return GraphNode(
        node_type=str(node_type).strip(),
        business_key=business_key_value,
        display_name=normalized_display or business_key_value,
        source_refs=update_source_refs([], source_ref),
        properties=dict(properties),
        embedding_chunk_id=embedding_chunk_id,
    )


def merge_nodes(nodes: Iterable[GraphNode]) -> list[GraphNode]:
    merged: dict[tuple[str, str], GraphNode] = {}

    for node in nodes:
        key = (node.node_type, node.business_key)
        current = merged.get(key)
        if current is None:
            merged[key] = node
            continue

        current.source_refs = update_source_refs(current.source_refs, node.source_refs)
        current.properties.update(node.properties)
        if len(node.display_name) > len(current.display_name):
            current.display_name = node.display_name
        if current.embedding_chunk_id is None:
            current.embedding_chunk_id = node.embedding_chunk_id

    return list(merged.values())
