from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable

import streamlit as st

from frontend_app.streamlit_shared_ui import build_chunk_table_rows, render_object_table


APP_TITLE = "Semantic Search"
APP_SUBTITLE = "Search similar chunks by text and traverse graph for matched business keys."


def load_semantic_search_function() -> Callable[[str, int, int, int], dict[str, Any]]:
    project_root = Path(__file__).resolve().parents[2]
    script_path = project_root / "data retrival" / "semantic_search.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find semantic search script: {script_path}")

    spec = spec_from_file_location("semantic_search_module", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from: {script_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "semantic_search_and_traverse"):
        raise AttributeError("semantic_search_and_traverse function not found in semantic_search.py")

    return module.semantic_search_and_traverse


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    if "semantic_result" not in st.session_state:
        st.session_state["semantic_result"] = None
    if "semantic_error" not in st.session_state:
        st.session_state["semantic_error"] = ""

    with st.form("semantic_search_form"):
        query_text = st.text_area("Input Text", height=150, placeholder="Enter text to search similar chunks")
        c1, c2, c3 = st.columns(3)
        top_k_chunks = c1.number_input("Top Chunks", min_value=1, max_value=100, value=10, step=1)
        top_k_keys = c2.number_input("Top Business Keys", min_value=1, max_value=20, value=5, step=1)
        max_depth = c3.number_input("Graph Max Depth", min_value=1, max_value=20, value=5, step=1)
        submitted = st.form_submit_button("Run Semantic Search")

    if submitted:
        text = (query_text or "").strip()
        if not text:
            st.session_state["semantic_result"] = None
            st.session_state["semantic_error"] = "Please enter text for semantic search."
        else:
            try:
                run_semantic = load_semantic_search_function()
                with st.spinner("Running semantic search and graph traversal..."):
                    st.session_state["semantic_result"] = run_semantic(
                        text,
                        int(top_k_chunks),
                        int(top_k_keys),
                        int(max_depth),
                    )
                st.session_state["semantic_error"] = ""
            except Exception as exc:
                st.session_state["semantic_result"] = None
                st.session_state["semantic_error"] = f"Semantic search failed: {exc}"

    if st.session_state.get("semantic_error"):
        st.error(st.session_state["semantic_error"])

    result = st.session_state.get("semantic_result")
    if not result:
        st.info("Submit text above to see semantic chunk matches and graph traversal by business key.")
        return

    st.markdown("### Similar Chunk Matches")
    chunk_rows = result.get("chunk_matches") or []
    if chunk_rows:
        st.dataframe(
            [
                {
                    "similarity": f"{float(row.get('similarity') or 0.0):.4f}",
                    "business_key": row.get("business_key"),
                    "node_type": row.get("node_type"),
                    "chunk_type": row.get("chunk_type"),
                    "text_content": row.get("text_content"),
                }
                for row in chunk_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("No semantic chunk matches found.")

    keys = result.get("business_keys") or []
    graph_map = result.get("graph_traversal_by_key") or {}

    st.markdown("### Business Key Graph Traversal")
    if not keys:
        st.info("No matched business keys available for graph traversal.")
        return

    key_tabs = st.tabs([str(k) for k in keys])
    for i, key in enumerate(keys):
        with key_tabs[i]:
            payload = graph_map.get(key, {})
            similarity = float(payload.get("similarity") or 0.0)
            graph_data = payload.get("graph") or {}

            st.caption(f"Similarity: {similarity:.4f}")

            start_node = graph_data.get("start_node")
            visited_nodes = graph_data.get("visited_nodes") or []
            relationships = graph_data.get("relationships") or []
            related_text_chunks = graph_data.get("related_text_chunks") or []

            c1, c2, c3 = st.columns(3)
            c1.metric("Visited Nodes", len(visited_nodes))
            c2.metric("Relationships", len(relationships))
            c3.metric("Found", "Yes" if graph_data.get("found") else "No")

            with st.expander("Start Node", expanded=True):
                if start_node:
                    render_object_table(start_node)
                else:
                    st.info("No start node found for this key.")

            with st.expander("Visited Nodes", expanded=False):
                if visited_nodes:
                    for node in visited_nodes:
                        with st.expander(str(node.get("display_name") or node.get("business_key") or node.get("node_uuid") or "Node"), expanded=False):
                            render_object_table(node)
                else:
                    st.info("No visited nodes.")

            with st.expander("Relationships", expanded=False):
                if relationships:
                    st.dataframe(
                        [
                            {
                                "relationship": rel.get("relationship"),
                                "from_business_key": rel.get("from_business_key"),
                                "to_business_key": rel.get("to_business_key"),
                            }
                            for rel in relationships
                        ],
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No relationships.")

            with st.expander("Related Text Chunks", expanded=False):
                if related_text_chunks:
                    st.dataframe(
                        build_chunk_table_rows(related_text_chunks),
                        use_container_width=True,
                        hide_index=True,
                    )
                else:
                    st.info("No related text chunks.")


if __name__ == "__main__":
    main()
