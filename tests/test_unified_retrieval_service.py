from __future__ import annotations

from webapp.flask_app_unified.retrieval_service import UnifiedRetrievalService


class DummyEmbeddingService:
    def generate(self, text: str) -> list[float]:
        return [0.1, 0.2, 0.3]


class DummyVectorRepo:
    def top_chunks(self, embedding: list[float], top_k: int):
        return [
            {
                "node_uuid": "node-1",
                "chunk_uuid": "chunk-1",
                "similarity": 0.95,
                "chunk_type": "text",
                "source_table": "table_a",
                "source_column": "col_a",
                "source_pk": 1,
                "text_content": "sample text",
            }
        ]


class DummyGraphTraversalService:
    def build_graph_response(self, question: str, matching_chunks: list[dict]):
        return {
            "nodes": [
                {
                    "node_uuid": "node-1",
                    "node_type": "PSP",
                    "business_key": "bk-1",
                    "display_name": "Primary Node",
                    "properties": {},
                },
                {
                    "node_uuid": "node-2",
                    "node_type": "event",
                    "business_key": "bk-2",
                    "display_name": "Event Node",
                    "properties": {},
                },
            ],
            "edges": [
                {
                    "source_node_uuid": "node-1",
                    "target_node_uuid": "node-2",
                    "relationship": "HAS_EVENT",
                    "direction": "outgoing",
                }
            ],
            "primary_nodes": {},
            "reference_nodes": {},
            "matching_chunks": matching_chunks,
        }

    def is_primary_node(self, node_type: str | None) -> bool:
        return str(node_type or "").strip().lower() == "psp"


def test_search_metrics_seed_node_count_uses_primary_nodes() -> None:
    service = UnifiedRetrievalService.__new__(UnifiedRetrievalService)
    service.embedding_service = DummyEmbeddingService()
    service.top_k = 3
    service.vector_repo = DummyVectorRepo()
    service.graph_traversal_service = DummyGraphTraversalService()

    result = service.search("What happened?")

    assert result["metrics"]["seed_node_count"] == 1
    assert result["metrics"]["path_count"] == 1
