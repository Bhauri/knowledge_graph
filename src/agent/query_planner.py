from __future__ import annotations

from typing import Any

from .relationship_resolver import RelationshipResolver


class QueryPlanner:
    DISTANCE_SCORE_WEIGHT = 0.15
    CANDIDATE_SCORE_WEIGHT = 0.85
    AMBIGUITY_GAP_THRESHOLD = 0.05

    def __init__(self, relationship_resolver: RelationshipResolver | None = None) -> None:
        self.relationship_resolver = relationship_resolver or RelationshipResolver()

    def _score_candidate_with_distance(
        self,
        target_entity: str,
        candidate: dict[str, Any],
    ) -> dict[str, Any] | None:
        destination = str(candidate.get("entity_name") or "").strip()
        if not destination:
            return None

        path = self.relationship_resolver.shortest_path(target_entity, destination)
        if path is None:
            return None

        base_score = float(candidate.get("final_score") or 0.0)
        relationship_distance = len(path)
        distance_score = 1 / (relationship_distance + 1)
        adjusted_score = (
            base_score * self.CANDIDATE_SCORE_WEIGHT
            + distance_score * self.DISTANCE_SCORE_WEIGHT
        )

        scored = dict(candidate)
        scored["base_score"] = round(base_score, 4)
        scored["relationship_distance"] = relationship_distance
        scored["distance_score"] = round(distance_score, 4)
        scored["adjusted_score"] = round(adjusted_score, 4)
        scored["path"] = path
        return scored

    def _select_with_distance(
        self,
        target_entity: str,
        schema_item: dict[str, Any],
    ) -> dict[str, Any] | None:
        candidates = schema_item.get("candidates", [])
        if not candidates:
            return None

        scored_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            scored = self._score_candidate_with_distance(target_entity, candidate)
            if scored is not None:
                scored_candidates.append(scored)

        if not scored_candidates:
            return None

        scored_candidates.sort(key=lambda item: item["adjusted_score"], reverse=True)
        return {
            "selected": scored_candidates[0],
            "candidates": scored_candidates,
        }

    def _should_apply_distance(
        self,
        schema_item: dict[str, Any],
    ) -> bool:
        if str(schema_item.get("status")) == "AMBIGUOUS":
            return True

        candidates = schema_item.get("candidates", [])
        if len(candidates) < 2:
            return False

        top = float(candidates[0].get("final_score") or 0.0)
        second = float(candidates[1].get("final_score") or 0.0)
        return (top - second) < self.AMBIGUITY_GAP_THRESHOLD

    def plan(
        self,
        intent: dict[str, Any],
        concept_resolution: list[dict[str, Any]],
        schema_resolution: list[dict[str, Any]],
        relationship_resolution: list[dict[str, Any]],
    ) -> dict[str, Any]:
        target_entity = str(intent.get("target_entity") or "").strip()
        operation = str(intent.get("operation") or "").strip().upper()

        errors: list[str] = []
        if not target_entity:
            errors.append("target_entity is missing")
        if not operation:
            errors.append("operation is missing")

        concept_by_index = {
            item.get("filter_index"): item
            for item in concept_resolution
        }
        schema_by_index = {
            item.get("filter_index"): item
            for item in schema_resolution
            if item.get("filter_index") is not None
        }
        schema_by_concept = {
            str(item.get("concept")): item
            for item in schema_resolution
        }
        relationship_by_index = {
            item.get("filter_index"): item
            for item in relationship_resolution
            if item.get("filter_index") is not None
        }
        relationship_by_concept = {
            str(item.get("concept")): item
            for item in relationship_resolution
        }

        plan_filters: list[dict[str, Any]] = []
        combined_resolution: list[dict[str, Any]] = []
        plan_status = "VALID"

        for index, filter_item in enumerate(intent.get("filters", [])):
            concept_item = concept_by_index.get(index)
            if concept_item is None:
                errors.append(f"Missing concept resolution for filter index {index}")
                plan_status = "INVALID"
                continue

            resolved_concept = concept_item.get("resolved_concept") or concept_item.get("input_concept")
            schema_item = schema_by_index.get(index) or schema_by_concept.get(str(resolved_concept))
            relation_item = relationship_by_index.get(index) or relationship_by_concept.get(str(resolved_concept))

            if concept_item.get("status") not in {"RESOLVED", "UNMATCHED_YAML"}:
                plan_status = "INVALID"
                errors.extend(concept_item.get("errors", [f"Concept unresolved: {resolved_concept}"]))

            if not schema_item or schema_item.get("status") == "UNRESOLVED":
                plan_status = "INVALID"
                errors.append(f"Schema unresolved for concept: {resolved_concept}")

            if not relation_item or relation_item.get("status") != "RESOLVED":
                plan_status = "INVALID"
                errors.append(f"Relationship unresolved for concept: {resolved_concept}")

            if schema_item and relation_item:
                selected = schema_item.get("selected")
                candidates = schema_item.get("candidates", [])
                path = relation_item.get("path")
                used_distance_for_tiebreak = False

                if self._should_apply_distance(schema_item):
                    selection = self._select_with_distance(target_entity, schema_item)
                    if selection is not None:
                        selected = selection["selected"]
                        candidates = selection["candidates"]
                        path = selected.get("path")
                        used_distance_for_tiebreak = True

                merged_status = (
                    "RESOLVED"
                    if schema_item.get("status") == "RESOLVED" and relation_item.get("status") == "RESOLVED"
                    else "UNRESOLVED"
                )

                merged_item = {
                    "filter_index": index,
                    "concept": resolved_concept,
                    "operator": filter_item.get("operator"),
                    "value": filter_item.get("value"),
                    "selected": selected,
                    "candidates": candidates,
                    "path": path,
                    "status": merged_status,
                    "business_concept": {
                        "status": concept_item.get("status"),
                        "source": concept_item.get("source"),
                        "filter_concept": concept_item.get("filter_concept"),
                        "resolved_concept": concept_item.get("resolved_concept"),
                        "rules": concept_item.get("rules", {}),
                        "aliases": concept_item.get("aliases", []),
                        "errors": concept_item.get("errors", []),
                    },
                    "schema_resolution": {
                        "status": schema_item.get("status"),
                        "concept_source": schema_item.get("concept_source"),
                        "selected": selected,
                        "candidates": candidates,
                        "errors": schema_item.get("errors", []),
                        "used_distance_for_tiebreak": used_distance_for_tiebreak,
                    },
                    "relationship_resolution": {
                        "status": relation_item.get("status"),
                        "path": path,
                        "path_length": len(path or []),
                        "destination_entity": relation_item.get("destination_entity"),
                        "errors": relation_item.get("errors", []),
                    },
                }

                plan_filters.append(merged_item)
                combined_resolution.append(merged_item)

        target_property = f"{target_entity}.{target_entity.lower().replace(' ', '_')}_id" if target_entity else None

        if errors and plan_status == "VALID":
            plan_status = "INVALID"

        return {
            "status": plan_status,
            "operation": operation,
            "target_entity": target_entity,
            "target_property": target_property,
            "filters": plan_filters,
            "combined_resolution": combined_resolution,
            "group_by": intent.get("group_by", []),
            "sort": intent.get("sort", []),
            "limit": intent.get("limit"),
            "errors": errors,
        }