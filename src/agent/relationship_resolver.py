from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Any

import yaml


class RelationshipResolver:
    def __init__(self, relationship_file: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "relationship.yaml"
        self.relationship_file = Path(relationship_file) if relationship_file else default_path
        self.relationships = self._load_relationships()
        self.graph = self._build_graph()

    def _load_relationships(self) -> list[dict[str, str]]:
        if not self.relationship_file.exists():
            raise FileNotFoundError(f"Relationship file not found: {self.relationship_file}")

        raw = self.relationship_file.read_text(encoding="utf-8")
        config = yaml.safe_load(raw) or {}

        if isinstance(config, str):
            return self._parse_lines(raw)

        relationships = config.get("relationships", [])
        if not isinstance(relationships, list):
            raise ValueError("relationship.yaml must contain 'relationships' list")
        return [dict(item) for item in relationships]

    def _parse_lines(self, raw: str) -> list[dict[str, str]]:
        relationships: list[dict[str, str]] = []
        for line in raw.splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            parts = [part.strip() for part in cleaned.split("->")]
            if len(parts) != 3:
                continue
            relationships.append({"from": parts[0], "relationship": parts[1], "to": parts[2]})
        return relationships

    def _build_graph(self) -> dict[str, list[dict[str, str]]]:
        graph: dict[str, list[dict[str, str]]] = {}
        for item in self.relationships:
            src = item.get("from")
            dst = item.get("to")
            rel = item.get("relationship")
            if not src or not dst or not rel:
                continue
            graph.setdefault(src, []).append({"to": dst, "relationship": rel})
        return graph

    def shortest_path(self, source: str, target: str) -> list[dict[str, str]] | None:
        if source == target:
            return []

        queue: deque[tuple[str, list[dict[str, str]]]] = deque([(source, [])])
        visited = {source}

        while queue:
            current, path = queue.popleft()
            for edge in self.graph.get(current, []):
                nxt = edge["to"]
                new_path = path + [{"from": current, "relationship": edge["relationship"], "to": nxt}]
                if nxt == target:
                    return new_path
                if nxt in visited:
                    continue
                visited.add(nxt)
                queue.append((nxt, new_path))

        return None

    def resolve(self, target_entity: str, schema_resolution: list[dict[str, Any]]) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []

        for item in schema_resolution:
            selected = item.get("selected")
            concept = item.get("concept")
            filter_index = item.get("filter_index")

            if not selected:
                resolved.append(
                    {
                        "filter_index": filter_index,
                        "concept": concept,
                        "status": "UNRESOLVED",
                        "errors": ["No selected schema property"],
                        "path": None,
                    }
                )
                continue

            destination = selected.get("entity_name")
            if not destination:
                resolved.append(
                    {
                        "filter_index": filter_index,
                        "concept": concept,
                        "status": "UNRESOLVED",
                        "errors": ["Selected schema property missing entity_name"],
                        "path": None,
                    }
                )
                continue

            path = self.shortest_path(target_entity, destination)
            if path is None:
                resolved.append(
                    {
                        "filter_index": filter_index,
                        "concept": concept,
                        "status": "UNRESOLVED",
                        "errors": [f"No relationship path from {target_entity} to {destination}"],
                        "path": None,
                    }
                )
                continue

            resolved.append(
                {
                    "filter_index": filter_index,
                    "concept": concept,
                    "status": "RESOLVED",
                    "errors": [],
                    "path": path,
                    "path_length": len(path),
                    "destination_entity": destination,
                }
            )

        return resolved
