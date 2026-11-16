from __future__ import annotations

from webapp.fastapi_app.services.graph_tree_builder import GraphTreeBuilder


def test_graph_tree_builder_adds_relationship_and_children() -> None:
    builder = GraphTreeBuilder()
    root_node = {
        "node_uuid": "root-1",
        "business_key": "QE-123",
        "display_name": "Quality Event",
        "node_type": "QualityEvent",
        "properties": {"source": "test"},
    }
    nodes_by_uuid = {
        "root-1": root_node,
        "child-1": {
            "node_uuid": "child-1",
            "business_key": "PSP-10",
            "display_name": "PSP",
            "node_type": "PSP",
            "properties": {},
        },
    }
    edge_rows = [
        {
            "relationship": "HAS_PSP",
            "source": "root-1",
            "target": "child-1",
        }
    ]

    tree = builder.build_tree(root_node=root_node, nodes_by_uuid=nodes_by_uuid, edge_rows=edge_rows)

    assert tree["business_key"] == "QE-123"
    assert tree["relationship_from_parent"] is None
    assert len(tree["children"]) == 1
    assert tree["children"][0]["relationship_from_parent"] == "HAS_PSP"
    assert tree["children"][0]["business_key"] == "PSP-10"
