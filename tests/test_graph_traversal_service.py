from __future__ import annotations

from pathlib import Path

from webapp.flask_app_unified.graph_traversal_service import GraphTraversalService


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, node_rows, edge_rows):
        self.node_rows = node_rows
        self.edge_rows = edge_rows

    def execute(self, query, params=None):
        sql = str(query)
        if "FROM graph_nodes" in sql:
            return FakeResult(self.node_rows)
        if "FROM graph_edges" in sql:
            return FakeResult(self.edge_rows)
        raise AssertionError(f"Unexpected query: {sql}")


def test_breadth_first_search_uses_policy_and_stops_at_reference_nodes(tmp_path: Path) -> None:
    policy_path = tmp_path / "travel_policy.yaml"
    policy_path.write_text(
        """
graph_traversal:
  max_depth: 2
  bidirectional: false
  primary_nodes:
    psps:
      - psp
  reference_nodes:
    persons:
      - person
  relationships:
    HAS_PSP:
      traverse: true
    CREATED_BY:
      traverse: false
""".strip()
    )

    db = FakeDB(
        node_rows=[
            {
                "node_uuid": "seed-1",
                "node_type": "quality_event",
                "business_key": "QE-1",
                "display_name": "QE One",
                "properties": {},
            },
            {
                "node_uuid": "psp-1",
                "node_type": "psp",
                "business_key": "PSP-1",
                "display_name": "PSP One",
                "properties": {},
            },
            {
                "node_uuid": "person-1",
                "node_type": "person",
                "business_key": "PER-1",
                "display_name": "Person One",
                "properties": {},
            },
        ],
        edge_rows=[
            {
                "edge_uuid": "edge-1",
                "from_node_uuid": "seed-1",
                "to_node_uuid": "psp-1",
                "relationship": "HAS_PSP",
            },
            {
                "edge_uuid": "edge-2",
                "from_node_uuid": "psp-1",
                "to_node_uuid": "person-1",
                "relationship": "CREATED_BY",
            },
        ],
    )

    service = GraphTraversalService(db=db, policy_path=policy_path)
    result = service.breadth_first_search(["seed-1"], [{"node_uuid": "seed-1"}], question="test")

    assert result["primary_nodes"]["psps"][0]["business_key"] == "PSP-1"
    assert result["reference_nodes"]["persons"] == []
    assert any(edge["relationship"] == "HAS_PSP" for edge in result["edges"])
    assert not any(edge["relationship"] == "CREATED_BY" for edge in result["edges"])
