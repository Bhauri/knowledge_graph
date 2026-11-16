from __future__ import annotations

from typing import Any

import streamlit as st


def render_object_table(record: dict[str, Any]) -> None:
    table_rows = [
        {"field": key, "value": value}
        for key, value in record.items()
        if key not in {"text_chunks", "properties"}
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    properties = record.get("properties") or {}
    if isinstance(properties, dict) and properties:
        st.markdown("#### Properties")
        st.dataframe(
            [{"property": key, "value": value} for key, value in properties.items()],
            use_container_width=True,
            hide_index=True,
        )


def build_similar_table_rows(similar_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_rows: list[dict[str, Any]] = []
    for row in similar_rows:
        table_rows.append(
            {
                "node_type": row.get("node_type"),
                "similarity": row.get("similarity"),
                "business_key": row.get("business_key"),
                "chunk": row.get("text_preview") or row.get("chunk_type") or row.get("text_content") or "",
            }
        )
    return table_rows


def build_chunk_table_rows(related_text_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table_rows: list[dict[str, Any]] = []
    for idx, chunk in enumerate(related_text_chunks, start=1):
        table_rows.append(
            {
                "#": idx,
                "node_uuid": chunk.get("node_uuid"),
                "chunk_type": chunk.get("chunk_type"),
                "source_column": chunk.get("source_column"),
                "text_content": chunk.get("text_content"),
            }
        )
    return table_rows


def render_node_tree(root_node: dict[str, Any], visited_nodes: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> None:
    nodes_by_uuid = {
        str(node.get("node_uuid")): node
        for node in [root_node, *visited_nodes]
        if node and node.get("node_uuid")
    }

    edges_by_from: dict[str, list[dict[str, Any]]] = {}
    for rel in relationships:
        from_uuid = str(rel.get("from_node_uuid") or "")
        to_uuid = str(rel.get("to_node_uuid") or "")
        if not from_uuid or not to_uuid:
            continue
        edges_by_from.setdefault(from_uuid, []).append(rel)

    def node_label(node_uuid: str) -> str:
        node = nodes_by_uuid.get(node_uuid, {})
        return str(node.get("display_name") or node.get("business_key") or node_uuid)

    def render_children(parent_uuid: str, seen: set[str]) -> None:
        children = edges_by_from.get(parent_uuid, [])
        if not children:
            st.caption("No child objects.")
            return

        for rel in children:
            child_uuid = str(rel.get("to_node_uuid") or "")
            if not child_uuid:
                continue

            rel_name = str(rel.get("relationship") or "REL")
            title = f"{rel_name} -> {node_label(child_uuid)}"
            if child_uuid in seen:
                with st.expander(f"{title} (already shown)", expanded=False):
                    st.caption("Cycle detected; node already rendered higher in this branch.")
                continue

            child_node = nodes_by_uuid.get(child_uuid, {})
            with st.expander(title, expanded=False):
                render_object_table(child_node)
                render_children(child_uuid, seen | {child_uuid})

    if root_node.get("node_uuid"):
        root_uuid = str(root_node.get("node_uuid"))
        with st.expander(f"Root: {node_label(root_uuid)}", expanded=True):
            render_object_table(root_node)
            render_children(root_uuid, {root_uuid})