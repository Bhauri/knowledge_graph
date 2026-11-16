from __future__ import annotations

import re
from typing import Any

from config import get_embedding_model
from db.database import Database


class SchemaResolver:
    AMBIGUITY_GAP_THRESHOLD = 0.05
    FINAL_SCORE_CUTOFF = 0.65

    def __init__(self) -> None:
        self.db = Database()
        self.embedding_model = get_embedding_model()

    @staticmethod
    def _normalize(value: str) -> str:
        if not value:
            return ""
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _lexical_score(self, query_norm: str, candidate: dict[str, Any]) -> float:
        property_name = self._normalize(str(candidate.get("property_name") or ""))
        canonical_name = self._normalize(str(candidate.get("canonical_name") or ""))
        searchable = self._normalize(str(candidate.get("searchable_text") or ""))

        aliases_raw = candidate.get("aliases") or []
        aliases = {
            self._normalize(str(alias))
            for alias in aliases_raw
            if alias
        }

        if query_norm in aliases:
            return 1.0
        if query_norm == property_name:
            return 0.95
        if query_norm == canonical_name:
            return 0.90
        if query_norm in searchable:
            return 0.75

        query_tokens = set(query_norm.split())
        candidate_tokens = set(property_name.split())
        for alias in aliases:
            candidate_tokens.update(alias.split())
        if not query_tokens:
            return 0.0

        overlap = len(query_tokens & candidate_tokens) / max(len(query_tokens), 1)
        return min(overlap, 0.70)

    def resolve(
        self,
        target_entity: str,
        concept_resolution: list[dict[str, Any]],
        top_k: int = 8,
        similarity_threshold: float = 0.60,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []

        sql = """
            WITH scored AS (
                SELECT
                    id,
                    entity_name,
                    property_name,
                    canonical_name,
                    data_type,
                    filterable,
                    aliases,
                    searchable_text,
                    list_cosine_similarity(embedding, CAST($query_embedding AS FLOAT[])) AS similarity
                FROM dbo.schema_index
                WHERE embedding IS NOT NULL
                  AND filterable = true
            )
            SELECT *
            FROM scored
            WHERE similarity >= $threshold
            ORDER BY similarity DESC
            LIMIT $candidate_limit
            """

        for concept_item in concept_resolution:
            concept = (
                concept_item.get("filter_concept")
                or concept_item.get("input_concept")
                or concept_item.get("resolved_concept")
            )
            if concept_item.get("status") not in {"RESOLVED", "UNMATCHED_YAML"}:
                results.append(
                    {
                        "concept": concept_item.get("filter_concept") or concept_item.get("input_concept"),
                        "status": "UNRESOLVED",
                        "errors": concept_item.get("errors", ["Concept unresolved"]),
                        "candidates": [],
                        "selected": None,
                    }
                )
                continue

            query_text = str(concept)
            query_norm = self._normalize(query_text)
            query_embedding = self.embedding_model.encode(query_text, normalize_embeddings=True)
            query_vector = query_embedding.tolist()

            rows = self.db.execute(
                sql,
                {
                    "query_embedding": query_vector,
                    "threshold": similarity_threshold,
                    "candidate_limit": max(top_k * 5, 30),
                },
            )

            candidates: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                similarity = float(item.get("similarity") or 0)
                lexical = self._lexical_score(query_norm, item)
                entity_bonus = 1.0 if str(item.get("entity_name")) == target_entity else 0.0
                final_score = similarity * 0.50 + lexical * 0.45 + entity_bonus * 0.05

                item["id"] = str(item.get("id")) if item.get("id") is not None else None
                item["similarity"] = round(similarity, 4)
                item["lexical_score"] = round(lexical, 4)
                item["entity_bonus"] = entity_bonus
                item["final_score"] = round(final_score, 4)
                candidates.append(item)

            candidates.sort(key=lambda x: x["final_score"], reverse=True)
            candidates = [item for item in candidates if item["final_score"] > self.FINAL_SCORE_CUTOFF]
            candidates = candidates[:top_k]

            selected = candidates[0] if candidates else None
            ambiguous = False
            if len(candidates) > 1:
                ambiguous = (candidates[0]["final_score"] - candidates[1]["final_score"]) < self.AMBIGUITY_GAP_THRESHOLD

            status = "RESOLVED"
            errors: list[str] = []
            if not selected:
                status = "UNRESOLVED"
                errors.append(f"No schema candidate found for concept '{query_text}'")
            elif ambiguous:
                status = "AMBIGUOUS"

            results.append(
                {
                    "concept": query_text,
                    "filter_index": concept_item.get("filter_index"),
                    "concept_source": concept_item.get("source"),
                    "status": status,
                    "errors": errors,
                    "selected": selected,
                    "candidates": candidates,
                }
            )

        return results
