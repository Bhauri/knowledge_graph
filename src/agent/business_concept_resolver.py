from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ConceptDefinition(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    operators: list[str] = Field(default_factory=list)
    value_type: str = "string"
    semantic_role: str | None = None
    rules: list[dict[str, Any]] = Field(default_factory=list)


class BusinessConceptResolver:
    def __init__(self, concepts_file: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[2] / "config" / "business_concepts.yaml"
        self.concepts_file = Path(concepts_file) if concepts_file else default_path
        self.concepts = self._load_concepts()

    def _load_concepts(self) -> list[ConceptDefinition]:
        if not self.concepts_file.exists():
            raise FileNotFoundError(f"Concept file not found: {self.concepts_file}")

        payload = yaml.safe_load(self.concepts_file.read_text(encoding="utf-8")) or {}
        records = payload.get("business_concepts", [])

        if isinstance(records, list):
            return [ConceptDefinition.model_validate(record) for record in records]

        if isinstance(records, dict):
            concepts: list[ConceptDefinition] = []
            for concept_name, concept_config in records.items():
                config = dict(concept_config or {})
                concepts.append(
                    ConceptDefinition.model_validate(
                        {
                            "name": concept_name,
                            "aliases": config.get("aliases", []),
                            "operators": config.get("operators", []),
                            "value_type": config.get("value_type", "string"),
                            "semantic_role": config.get("semantic_role"),
                            "rules": config.get("rules", []),
                        }
                    )
                )
            return concepts

        raise ValueError("business_concepts.yaml must contain 'business_concepts' list or mapping")

    @staticmethod
    def _norm(value: str) -> str:
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
        value = value.replace("_", " ")
        return " ".join(value.lower().strip().split())

    def resolve(self, intent: dict[str, Any]) -> list[dict[str, Any]]:
        resolved: list[dict[str, Any]] = []

        for idx, filter_item in enumerate(intent.get("filters", [])):
            filter_concept = str(
                filter_item.get("business_concept")
                or filter_item.get("concept")
                or filter_item.get("text")
                or ""
            ).strip()
            concept_norm = self._norm(filter_concept)

            selected: ConceptDefinition | None = None
            for concept in self.concepts:
                aliases = {self._norm(alias) for alias in concept.aliases}
                aliases.add(self._norm(concept.name))
                if concept_norm in aliases:
                    selected = concept
                    break

            if selected is None:
                resolved.append(
                    {
                        "filter_index": idx,
                        "filter_concept": filter_concept,
                        "input_concept": filter_concept,
                        "resolved_concept": filter_concept,
                        "status": "UNMATCHED_YAML",
                        "source": "schema_fallback",
                        "errors": [],
                    }
                )
                continue

            resolved.append(
                {
                    "filter_index": idx,
                    "filter_concept": filter_concept,
                    "input_concept": filter_concept,
                    "resolved_concept": selected.name,
                    "aliases": selected.aliases,
                    "rules": {
                        "operators": selected.operators,
                        "value_type": selected.value_type,
                        "semantic_role": selected.semantic_role,
                        "rule_blocks": selected.rules,
                    },
                    "status": "RESOLVED",
                    "source": "business_concepts_yaml",
                    "errors": [],
                }
            )

        return resolved
