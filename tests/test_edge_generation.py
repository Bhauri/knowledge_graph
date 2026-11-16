from __future__ import annotations

from uuid import uuid4

from app.graph_creater.graph_edge_service import GraphEdgeService
from app.graph_creater.node_lookup_service import NodeLookupService
from app.graph_creater.relationship_builder import RelationshipBuilder


class DummyEngine:
    pass


class DummyStore:
    def fetch_all(self, _sql, _params=None):
        return []


def _lookup_with_values(values: dict[tuple[str, str], object]) -> NodeLookupService:
    lookup = NodeLookupService(DummyStore())
    lookup._cache = values
    return lookup


def test_process_qe_creates_expected_relationships() -> None:
    qe_uuid = uuid4()
    person_uuid = uuid4()
    site_uuid = uuid4()
    location_uuid = uuid4()

    lookup = _lookup_with_values(
        {
            ("QualityEvent", "qe-1"): qe_uuid,
            ("Person", "alice"): person_uuid,
            ("Site", "plant-a"): site_uuid,
            ("Location", "boston"): location_uuid,
        }
    )

    builder = RelationshipBuilder(lookup)
    edges = builder.process_qe(
        qe_rows=[
            {
                "qe_id": 1,
                "created_by": "Alice",
                "investigator": "Alice",
                "approver": "Alice",
                "initiating_site": "Plant A",
                "locaiton": "Boston",
            }
        ],
        psp_rows=[],
        evaluation_rows=[],
        event_rows=[],
        containment_rows=[],
    )

    relationships = {edge.relationship for edge in edges}
    assert "CREATED_BY" in relationships
    assert "HAS_INVESTIGATOR" in relationships
    assert "APPROVED_BY" in relationships
    assert "INITIATED_AT" in relationships
    assert "OCCURRED_AT" in relationships


def test_process_qe_skips_missing_nodes() -> None:
    lookup = _lookup_with_values({("QualityEvent", "qe-1"): uuid4()})
    builder = RelationshipBuilder(lookup)

    edges = builder.process_qe(
        qe_rows=[
            {
                "qe_id": 1,
                "created_by": "Missing Person",
            }
        ],
        psp_rows=[],
        evaluation_rows=[],
        event_rows=[],
        containment_rows=[],
    )

    assert edges == []
    assert lookup.missing_nodes >= 1


def test_process_yaml_relationships_creates_edges_from_specs() -> None:
    source_uuid = uuid4()
    target_uuid = uuid4()
    lookup = _lookup_with_values({("QualityEvent", "qe-1"): source_uuid, ("PSP", "psp-2"): target_uuid})

    builder = RelationshipBuilder(lookup)
    edges = builder.process_yaml_relationships(
        [
            {
                "relationship": "HAS_PSP",
                "source": {"table": "qe", "node_type": "QualityEvent", "pk": "qe_id"},
                "target": {"table": "psp", "node_type": "PSP", "pk": "psp_id"},
                "foreign_key": {"column": "parent_qeid"},
            }
        ],
        rows_by_table={
            "qe": [{"qe_id": 1, "parent_qeid": 2}],
            "psp": [{"psp_id": 2, "parent_qeid": 1}],
        },
    )

    assert len(edges) == 1
    assert edges[0].relationship == "HAS_PSP"
    assert edges[0].from_node_uuid == source_uuid
    assert edges[0].to_node_uuid == target_uuid


def test_edge_deduplication() -> None:
    service = GraphEdgeService(DummyEngine(), DummyStore(), logger=None)

    from app.graph_creater.edge_models import create_edge

    a = uuid4()
    b = uuid4()
    edges = [
        create_edge(
            from_node_uuid=a,
            to_node_uuid=b,
            relationship="HAS_PSP",
            source_ref={"table": "psp", "parent_pk": 1, "child_pk": 2, "relationship_source": "parent_qeid"},
        ),
        create_edge(
            from_node_uuid=a,
            to_node_uuid=b,
            relationship="HAS_PSP",
            source_ref={"table": "psp", "parent_pk": 1, "child_pk": 2, "relationship_source": "parent_qeid"},
        ),
    ]

    deduped, skipped = service._dedupe_edges(edges)
    assert len(deduped) == 1
    assert skipped == 1
