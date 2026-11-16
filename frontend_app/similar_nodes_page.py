from __future__ import annotations

from typing import Any

import streamlit as st

from frontend_app.streamlit_shared_ui import build_chunk_table_rows, build_similar_table_rows, render_node_tree, render_object_table


APP_TITLE = "Similar Nodes"
APP_SUBTITLE = "Nodes returned from Find Similar search."


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    payload = st.session_state.get("similar_nodes_page_payload")
    if not payload:
        st.info("No similar-node result found. Use Find Similar from the Chunks tab first.")
        return

    source = str(payload.get("source") or "")
    similar_rows = payload.get("similar_rows") or []
    business_keys = payload.get("business_keys") or []
    graph_results = payload.get("graph_results") or {}

    st.caption(f"Source: {source}")

    if similar_rows:
        st.markdown("### Similar Search Results")
        st.dataframe(build_similar_table_rows(similar_rows), use_container_width=True, hide_index=True)

    if not business_keys:
        st.warning("No business keys were returned by the similar search.")
        return

    st.markdown("### Node Results")
    tabs = st.tabs([str(k) for k in business_keys])
    for idx, key in enumerate(business_keys):
        with tabs[idx]:
            graph_data: dict[str, Any] = graph_results.get(key, {})
            if graph_data.get("error"):
                st.error(str(graph_data.get("error")))

            start_node = graph_data.get("start_node")
            visited_nodes = graph_data.get("visited_nodes") or []
            relationships = graph_data.get("relationships") or []
            related_text_chunks = graph_data.get("related_text_chunks") or []

            c1, c2, c3 = st.columns(3)
            c1.metric("Found", "Yes" if graph_data.get("found") else "No")
            c2.metric("Visited Nodes", len(visited_nodes))
            c3.metric("Relationships", len(relationships))

            with st.expander("Start Node", expanded=True):
                if start_node:
                    render_object_table(start_node)
                else:
                    st.info("No start node available.")

            with st.expander("Visited Node Tree", expanded=True):
                if start_node:
                    render_node_tree(start_node, visited_nodes, relationships)
                elif visited_nodes:
                    for node in visited_nodes:
                        with st.expander(str(node.get("display_name") or node.get("business_key") or node.get("node_uuid") or "Node"), expanded=False):
                            render_object_table(node)
                else:
                    st.info("No visited nodes.")

            with st.expander("Related Text Chunks", expanded=False):
                if related_text_chunks:
                    st.dataframe(build_chunk_table_rows(related_text_chunks), use_container_width=True, hide_index=True)
                else:
                    st.info("No related text chunks.")


if __name__ == "__main__":
    main()