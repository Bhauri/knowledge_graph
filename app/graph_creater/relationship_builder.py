from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import yaml

from .edge_models import GraphEdge, create_edge
from .models import normalize_key
from .node_lookup_service import NodeLookupService


class RelationshipBuilder:
    def __init__(self, lookup_service: NodeLookupService, logger: logging.Logger | None = None) -> None:
        self.lookup_service = lookup_service
        self.logger = logger or logging.getLogger(self.__class__.__name__)
        self._missing_logged: set[tuple[str, str]] = set()
        self._yaml_relationships = self._load_yaml_relationships()

    @staticmethod
    def _node_key(prefix: str, value: Any) -> str:
        return normalize_key(f"{prefix}-{value}")

    @staticmethod
    def _business_key(table_name: str, primary_key: Any) -> str:
        return normalize_key(f"{table_name}-{primary_key}")

    @staticmethod
    def _source_ref(table: str, parent_pk: Any, child_pk: Any, relationship_source: str) -> dict[str, Any]:
        return {
            "table": table,
            "parent_pk": parent_pk,
            "child_pk": child_pk,
            "relationship_source": relationship_source,
        }

    def _connect(
        self,
        *,
        from_type: str,
        from_key: Any,
        to_type: str,
        to_key: Any,
        relationship: str,
        source_ref: Mapping[str, Any],
        properties: Mapping[str, Any] | None = None,
    ) -> GraphEdge | None:
        from_node_uuid = self.lookup_service.lookup_node(from_type, from_key)
        if from_node_uuid is None:
            self._log_missing_once(from_type, from_key, is_from=True)
            return None

        to_node_uuid = self.lookup_service.lookup_node(to_type, to_key)
        if to_node_uuid is None:
            self._log_missing_once(to_type, to_key, is_from=False)
            return None

        return create_edge(
            from_node_uuid=from_node_uuid,
            to_node_uuid=to_node_uuid,
            relationship=relationship,
            source_ref=source_ref,
            properties=properties or {},
        )

    def _log_missing_once(self, node_type: str, business_key: Any, *, is_from: bool) -> None:
        normalized_key = normalize_key(business_key)
        cache_key = (node_type, normalized_key)
        if cache_key in self._missing_logged:
            return
        self._missing_logged.add(cache_key)
        direction = "from" if is_from else "to"
        self.logger.warning("Missing %s-node: %s|%s", direction, node_type, normalized_key)

    @staticmethod
    def _load_yaml_relationships() -> list[dict[str, Any]]:
        config_path = Path(__file__).resolve().parents[2] / "config" / "table_specs.yaml"
        if not config_path.exists():
            return []

        with config_path.open("r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}

        relationships = payload.get("relationships", []) or []
        return [dict(item) for item in relationships if isinstance(item, dict)]

    def process_yaml_relationships(self, relationships: Iterable[Mapping[str, Any]], rows_by_table: Mapping[str, Iterable[Mapping[str, Any]]]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for relationship_spec in relationships:
            relationship_name = str(relationship_spec.get("relationship", "")).strip()
            if not relationship_name:
                continue

            source_spec = relationship_spec.get("source") or {}
            target_spec = relationship_spec.get("target") or {}
            foreign_key_spec = relationship_spec.get("foreign_key") or {}

            source_table = str(source_spec.get("table", "")).strip()
            source_node_type = str(source_spec.get("node_type", "")).strip()
            source_pk = str(source_spec.get("pk", "")).strip()
            target_table = str(target_spec.get("table", "")).strip()
            target_node_type = str(target_spec.get("node_type", "")).strip()
            target_pk = str(target_spec.get("pk", "")).strip()
            fk_column = str(foreign_key_spec.get("column", "")).strip()

            if not all([source_table, source_node_type, source_pk, target_table, target_node_type, target_pk, fk_column]):
                continue

            source_rows = list(rows_by_table.get(source_table, []))
            target_rows = list(rows_by_table.get(target_table, []))
            target_lookup: dict[Any, list[dict[str, Any]]] = defaultdict(list)
            for row in target_rows:
                target_value = row.get(target_pk)
                if target_value is None:
                    continue
                target_lookup[target_value].append(row)

            for source_row in source_rows:
                source_pk_value = source_row.get(source_pk)
                if source_pk_value is None:
                    continue

                source_key = self._business_key(source_table, source_pk_value)
                related_target_rows = target_lookup.get(source_row.get(fk_column))
                if not related_target_rows:
                    continue

                for target_row in related_target_rows:
                    target_pk_value = target_row.get(target_pk)
                    if target_pk_value is None:
                        continue

                    edge = self._connect(
                        from_type=source_node_type,
                        from_key=source_key,
                        to_type=target_node_type,
                        to_key=self._business_key(target_table, target_pk_value),
                        relationship=relationship_name,
                        source_ref=self._source_ref(source_table, source_pk_value, target_pk_value, fk_column),
                    )
                    if edge is not None:
                        edges.append(edge)

        return edges

    def process_qe(
        self,
        qe_rows: Iterable[Mapping[str, Any]],
        psp_rows: Iterable[Mapping[str, Any]],
        evaluation_rows: Iterable[Mapping[str, Any]],
        event_rows: Iterable[Mapping[str, Any]],
        containment_rows: Iterable[Mapping[str, Any]],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        psp_by_qe: dict[Any, list[Any]] = defaultdict(list)
        for row in psp_rows:
            if row.get("parent_qeid") is not None and row.get("psp_id") is not None:
                psp_by_qe[row["parent_qeid"]].append(row["psp_id"])

        evaluation_by_qe: dict[Any, list[Any]] = defaultdict(list)
        for row in evaluation_rows:
            if row.get("parent_qeid") is not None and row.get("eval_id") is not None:
                evaluation_by_qe[row["parent_qeid"]].append(row["eval_id"])

        events_by_qe: dict[Any, list[Any]] = defaultdict(list)
        for row in event_rows:
            if row.get("parent_qe_id") is not None and row.get("event_id") is not None:
                events_by_qe[row["parent_qe_id"]].append(row["event_id"])

        containment_by_qe: dict[Any, list[Any]] = defaultdict(list)
        for row in containment_rows:
            if row.get("parent_qe_id") is not None and row.get("con_id") is not None:
                containment_by_qe[row["parent_qe_id"]].append(row["con_id"])

        for row in qe_rows:
            qe_id = row.get("qe_id")
            if qe_id is None:
                continue

            qe_key = self._node_key("qe", qe_id)

            for psp_id in psp_by_qe.get(qe_id, []):
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type="PSP",
                    to_key=self._node_key("psp", psp_id),
                    relationship="HAS_PSP",
                    source_ref=self._source_ref("psp", qe_id, psp_id, "parent_qeid"),
                )
                if edge:
                    edges.append(edge)

            for eval_id in evaluation_by_qe.get(qe_id, []):
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type="Evaluation",
                    to_key=self._node_key("initial_evaluations", eval_id),
                    relationship="HAS_EVALUATION",
                    source_ref=self._source_ref("initial_evaluations", qe_id, eval_id, "parent_qeid"),
                )
                if edge:
                    edges.append(edge)

            for event_id in events_by_qe.get(qe_id, []):
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type="QEEvent",
                    to_key=self._node_key("qe_events", event_id),
                    relationship="HAS_EVENT",
                    source_ref=self._source_ref("qe_events", qe_id, event_id, "parent_qe_id"),
                )
                if edge:
                    edges.append(edge)

            for con_id in containment_by_qe.get(qe_id, []):
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type="ContainmentAction",
                    to_key=self._node_key("containment_actions", con_id),
                    relationship="HAS_CONTAINMENT_ACTION",
                    source_ref=self._source_ref("containment_actions", qe_id, con_id, "parent_qe_id"),
                )
                if edge:
                    edges.append(edge)

            for column, relationship, to_type in (
                ("investigator", "HAS_INVESTIGATOR", "Person"),
                ("approver", "APPROVED_BY", "Person"),
                ("created_by", "CREATED_BY", "Person"),
                ("initiating_site", "INITIATED_AT", "Site"),
            ):
                value = row.get(column)
                if value is None or not str(value).strip():
                    continue
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type=to_type,
                    to_key=value,
                    relationship=relationship,
                    source_ref=self._source_ref("qe", qe_id, str(value).strip(), column),
                )
                if edge:
                    edges.append(edge)

            location_value = row.get("locaiton") if row.get("locaiton") is not None else row.get("location")
            if location_value is not None and str(location_value).strip():
                edge = self._connect(
                    from_type="QualityEvent",
                    from_key=qe_key,
                    to_type="Location",
                    to_key=location_value,
                    relationship="OCCURRED_AT",
                    source_ref=self._source_ref("qe", qe_id, str(location_value).strip(), "locaiton"),
                )
                if edge:
                    edges.append(edge)

        return edges

    def process_psp(
        self,
        psp_rows: Iterable[Mapping[str, Any]],
        capa_rows: Iterable[Mapping[str, Any]],
        event_rows: Iterable[Mapping[str, Any]],
        containment_rows: Iterable[Mapping[str, Any]],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        capa_by_psp: dict[Any, list[Any]] = defaultdict(list)
        for row in capa_rows:
            if row.get("parent_psp_id") is not None and row.get("capa_id") is not None:
                capa_by_psp[row["parent_psp_id"]].append(row["capa_id"])

        events_by_psp: dict[Any, list[Any]] = defaultdict(list)
        for row in event_rows:
            if row.get("parent_psp_id") is not None and row.get("event_id") is not None:
                events_by_psp[row["parent_psp_id"]].append(row["event_id"])

        containment_by_psp: dict[Any, list[Any]] = defaultdict(list)
        for row in containment_rows:
            if row.get("parent_psp_id") is not None and row.get("con_id") is not None:
                containment_by_psp[row["parent_psp_id"]].append(row["con_id"])

        for row in psp_rows:
            psp_id = row.get("psp_id")
            if psp_id is None:
                continue
            psp_key = self._node_key("psp", psp_id)

            for column, relationship, to_type in (
                ("created_by", "CREATED_BY", "Person"),
                ("owniing_site", "OWNED_BY_SITE", "Site"),
                ("root_cause", "HAS_ROOT_CAUSE", "RootCause"),
                ("root_cause_category", "HAS_ROOT_CAUSE_CATEGORY", "RootCauseCategory"),
                ("tool_used", "USED_TOOL", "InvestigationTool"),
            ):
                value = row.get(column)
                if value is None or not str(value).strip():
                    continue
                edge = self._connect(
                    from_type="PSP",
                    from_key=psp_key,
                    to_type=to_type,
                    to_key=value,
                    relationship=relationship,
                    source_ref=self._source_ref("psp", psp_id, str(value).strip(), column),
                )
                if edge:
                    edges.append(edge)

            for capa_id in capa_by_psp.get(psp_id, []):
                edge = self._connect(
                    from_type="PSP",
                    from_key=psp_key,
                    to_type="CAPA",
                    to_key=self._node_key("capa", capa_id),
                    relationship="HAS_CAPA",
                    source_ref=self._source_ref("capa", psp_id, capa_id, "parent_psp_id"),
                )
                if edge:
                    edges.append(edge)

            for event_id in events_by_psp.get(psp_id, []):
                edge = self._connect(
                    from_type="PSP",
                    from_key=psp_key,
                    to_type="QEEvent",
                    to_key=self._node_key("qe_events", event_id),
                    relationship="HAS_EVENT",
                    source_ref=self._source_ref("qe_events", psp_id, event_id, "parent_psp_id"),
                )
                if edge:
                    edges.append(edge)

            for con_id in containment_by_psp.get(psp_id, []):
                edge = self._connect(
                    from_type="PSP",
                    from_key=psp_key,
                    to_type="ContainmentAction",
                    to_key=self._node_key("containment_actions", con_id),
                    relationship="HAS_CONTAINMENT_ACTION",
                    source_ref=self._source_ref("containment_actions", psp_id, con_id, "parent_psp_id"),
                )
                if edge:
                    edges.append(edge)

        return edges

    def process_capa(self, capa_rows: Iterable[Mapping[str, Any]]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for row in capa_rows:
            capa_id = row.get("capa_id")
            if capa_id is None:
                continue
            capa_key = self._node_key("capa", capa_id)

            for column, relationship, to_type in (
                ("qa_approver", "APPROVED_BY", "Person"),
                ("initiating_site", "INITIATED_AT", "Site"),
            ):
                value = row.get(column)
                if value is None or not str(value).strip():
                    continue
                edge = self._connect(
                    from_type="CAPA",
                    from_key=capa_key,
                    to_type=to_type,
                    to_key=value,
                    relationship=relationship,
                    source_ref=self._source_ref("capa", capa_id, str(value).strip(), column),
                )
                if edge:
                    edges.append(edge)

        return edges

    def process_containment(
        self,
        containment_rows: Iterable[Mapping[str, Any]],
        batch_rows: Iterable[Mapping[str, Any]],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        batches_by_con: dict[Any, list[Any]] = defaultdict(list)
        for row in batch_rows:
            if row.get("con_id") is not None and row.get("batch") is not None:
                batches_by_con[row["con_id"]].append(row["batch"])

        for row in containment_rows:
            con_id = row.get("con_id")
            if con_id is None:
                continue
            con_key = self._node_key("containment_actions", con_id)

            for column, relationship, to_type in (
                ("assign_to", "ASSIGNED_TO", "Person"),
                ("completed_by", "COMPLETED_BY", "Person"),
                ("quality_appropver", "APPROVED_BY", "Person"),
                ("quality_action_type", "HAS_ACTION_TYPE", "ActionType"),
                ("subtype", "HAS_ACTION_SUBTYPE", "ActionSubtype"),
            ):
                value = row.get(column)
                if value is None or not str(value).strip():
                    continue
                edge = self._connect(
                    from_type="ContainmentAction",
                    from_key=con_key,
                    to_type=to_type,
                    to_key=value,
                    relationship=relationship,
                    source_ref=self._source_ref("containment_actions", con_id, str(value).strip(), column),
                )
                if edge:
                    edges.append(edge)

            for batch_value in batches_by_con.get(con_id, []):
                edge = self._connect(
                    from_type="ContainmentAction",
                    from_key=con_key,
                    to_type="Batch",
                    to_key=self._node_key("batch_containment_details", batch_value),
                    relationship="HAS_BATCH",
                    source_ref=self._source_ref("batch_containment_details", con_id, batch_value, "con_id"),
                )
                if edge:
                    edges.append(edge)

        return edges

    def process_batch(self, batch_rows: Iterable[Mapping[str, Any]]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for row in batch_rows:
            batch_value = row.get("batch")
            site = row.get("batch_site")
            con_id = row.get("con_id")

            if batch_value is None or site is None or not str(site).strip():
                continue

            edge = self._connect(
                from_type="Batch",
                from_key=self._node_key("batch_containment_details", batch_value),
                to_type="Site",
                to_key=site,
                relationship="STORED_AT",
                source_ref=self._source_ref("batch_containment_details", con_id, str(site).strip(), "batch_site"),
            )
            if edge:
                edges.append(edge)

        return edges

    def process_event(self, event_rows: Iterable[Mapping[str, Any]]) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for row in event_rows:
            event_id = row.get("event_id")
            if event_id is None:
                continue

            event_key = self._node_key("qe_events", event_id)

            for column, relationship, to_type in (
                ("event_type", "HAS_EVENT_TYPE", "EventType"),
                ("testing_type", "HAS_TESTING_TYPE", "TestingType"),
                ("category", "HAS_CATEGORY", "Category"),
                ("failurecode", "HAS_FAILURE_CODE", "FailureCode"),
            ):
                value = row.get(column)
                if value is None or not str(value).strip():
                    continue
                edge = self._connect(
                    from_type="QEEvent",
                    from_key=event_key,
                    to_type=to_type,
                    to_key=value,
                    relationship=relationship,
                    source_ref=self._source_ref("qe_events", event_id, str(value).strip(), column),
                )
                if edge:
                    edges.append(edge)

            testing_id = row.get("testing_id")
            if testing_id is not None and str(testing_id).strip():
                edge = self._connect(
                    from_type="QEEvent",
                    from_key=event_key,
                    to_type="Test",
                    to_key=testing_id,
                    relationship="USES_TEST",
                    source_ref=self._source_ref("qe_events", event_id, str(testing_id).strip(), "testing_id"),
                )
                if edge:
                    edges.append(edge)

            defect_value = row.get("defect_item")
            if defect_value is None:
                defect_value = row.get("defect_item_description")
            if defect_value is not None and str(defect_value).strip():
                edge = self._connect(
                    from_type="QEEvent",
                    from_key=event_key,
                    to_type="DefectItem",
                    to_key=defect_value,
                    relationship="HAS_DEFECT_ITEM",
                    source_ref=self._source_ref("qe_events", event_id, str(defect_value).strip(), "defect_item"),
                )
                if edge:
                    edges.append(edge)

        return edges

    def process_evaluation(
        self,
        evaluation_rows: Iterable[Mapping[str, Any]],
        event_rows: Iterable[Mapping[str, Any]],
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for row in evaluation_rows:
            eval_id = row.get("eval_id")
            if eval_id is None:
                continue
            eval_key = self._node_key("initial_evaluations", eval_id)

            risk_value = row.get("overall_risk_level")
            if risk_value is None or not str(risk_value).strip():
                risk_value = row.get("overall_risk_lelve")

            if risk_value is not None and str(risk_value).strip():
                edge = self._connect(
                    from_type="Evaluation",
                    from_key=eval_key,
                    to_type="RiskLevel",
                    to_key=risk_value,
                    relationship="HAS_RISK_LEVEL",
                    source_ref=self._source_ref("initial_evaluations", eval_id, str(risk_value).strip(), "overall_risk_level"),
                )
                if edge:
                    edges.append(edge)

            direct_cause = row.get("direct_cause")
            if direct_cause is not None and str(direct_cause).strip():
                edge = self._connect(
                    from_type="Evaluation",
                    from_key=eval_key,
                    to_type="DirectCause",
                    to_key=direct_cause,
                    relationship="HAS_DIRECT_CAUSE",
                    source_ref=self._source_ref("initial_evaluations", eval_id, str(direct_cause).strip(), "direct_cause"),
                )
                if edge:
                    edges.append(edge)

            parent_event_id = row.get("parent_event_id")
            if parent_event_id is not None:
                edge = self._connect(
                    from_type="QEEvent",
                    from_key=self._node_key("qe_events", parent_event_id),
                    to_type="Evaluation",
                    to_key=eval_key,
                    relationship="HAS_EVALUATION",
                    source_ref=self._source_ref("initial_evaluations", parent_event_id, eval_id, "parent_event_id"),
                )
                if edge:
                    edges.append(edge)

        return edges
