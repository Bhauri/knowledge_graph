from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class GraphEdge:
    from_node_uuid: UUID
    to_node_uuid: UUID
    relationship: str
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    properties: dict[str, Any] = field(default_factory=dict)
    edge_uuid: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def merge_edge_source_refs(
    existing: Sequence[Mapping[str, Any]] | None,
    new_ref: Mapping[str, Any] | Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any, Any]] = set()

    def _append(ref: Mapping[str, Any]) -> None:
        item = {
            "table": str(ref.get("table", "")).strip(),
            "parent_pk": ref.get("parent_pk"),
            "child_pk": ref.get("child_pk"),
            "relationship_source": str(ref.get("relationship_source", "")).strip(),
        }
        key = (item["table"], item["parent_pk"], item["child_pk"], item["relationship_source"])
        if key in seen:
            return
        seen.add(key)
        refs.append(item)

    for ref in existing or []:
        _append(ref)

    if isinstance(new_ref, Mapping):
        _append(new_ref)
    else:
        for ref in new_ref:
            _append(ref)

    return refs


def create_edge(
    *,
    from_node_uuid: UUID,
    to_node_uuid: UUID,
    relationship: str,
    source_ref: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    properties: Mapping[str, Any] | None = None,
) -> GraphEdge:
    refs = merge_edge_source_refs([], source_ref)
    edge_properties = {key: value for key, value in (properties or {}).items() if value is not None}

    return GraphEdge(
        from_node_uuid=from_node_uuid,
        to_node_uuid=to_node_uuid,
        relationship=relationship.strip(),
        source_refs=refs,
        properties=edge_properties,
    )
