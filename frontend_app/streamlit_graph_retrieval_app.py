from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Any, Callable

import streamlit as st
from streamlit.errors import StreamlitAPIException

from frontend_app.streamlit_shared_ui import build_chunk_table_rows, build_similar_table_rows, render_node_tree, render_object_table


APP_TITLE = "Graph Retrieval Explorer"
APP_SUBTITLE = "Submit a business key to fetch graph node details and relationships."


def load_retrieval_function() -> Callable[[str, int], dict[str, Any]]:
    """Load retrieve_business_key_path_properties from the existing script file."""
    project_root = Path(__file__).resolve().parent.parent
    script_path = project_root / "data retrival" / "graph_retrieval.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find graph retrieval script: {script_path}")

    spec = spec_from_file_location("graph_retrieval_module", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from: {script_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "retrieve_business_key_path_properties"):
        raise AttributeError(
            "retrieve_business_key_path_properties function not found in graph_retrieval.py"
        )

    return module.retrieve_business_key_path_properties


def load_summarizer_function() -> Callable[[str], str]:
    """Load summarize_text_business from the existing script file."""
    project_root = Path(__file__).resolve().parent.parent
    script_path = project_root / "data retrival" / "text_summarizer.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find text summarizer script: {script_path}")

    spec = spec_from_file_location("text_summarizer_module", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from: {script_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "summarize_text_business"):
        raise AttributeError(
            "summarize_text_business function not found in text_summarizer.py"
        )

    return module.summarize_text_business


def load_semantic_search_function() -> Callable[[str, int, int, int], dict[str, Any]]:
    """Load semantic_search_and_traverse from the existing script file."""
    project_root = Path(__file__).resolve().parent.parent
    script_path = project_root / "data retrival" / "semantic_search.py"
    if not script_path.exists():
        raise FileNotFoundError(f"Could not find semantic search script: {script_path}")

    spec = spec_from_file_location("semantic_search_module", script_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module spec from: {script_path}")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "semantic_search_and_traverse"):
        raise AttributeError(
            "semantic_search_and_traverse function not found in semantic_search.py"
        )

    return module.semantic_search_and_traverse


def run_semantic_find_similar(
    query_text: str,
    max_depth: int,
    top_k_chunks: int = 10,
    top_k_keys: int = 5,
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    run_semantic = load_semantic_search_function()
    semantic_result = run_semantic(
        query_text,
        top_k_chunks=int(top_k_chunks),
        top_k_keys=int(top_k_keys),
        max_depth=int(max_depth),
    )

    similar_rows: list[dict[str, Any]] = []
    for row in semantic_result.get("chunk_matches") or []:
        text_value = str(row.get("text_content") or "")
        similar_rows.append(
            {
                "chunk_uuid": row.get("chunk_uuid"),
                "node_uuid": row.get("node_uuid"),
                "similarity": float(row.get("similarity") or 0.0),
                "node_type": row.get("node_type"),
                "business_key": row.get("business_key"),
                "chunk_type": row.get("chunk_type"),
                "text_preview": text_value if len(text_value) <= 120 else f"{text_value[:120]}...",
            }
        )

    business_keys = [str(k) for k in (semantic_result.get("business_keys") or [])]
    graph_results: dict[str, Any] = {}
    graph_map = semantic_result.get("graph_traversal_by_key") or {}
    for key in business_keys:
        entry = graph_map.get(key) or {}
        graph_data = dict(entry.get("graph") or {})
        graph_data["semantic_similarity"] = entry.get("similarity")
        graph_results[key] = graph_data

    return similar_rows, business_keys, graph_results


def open_similar_nodes_page(
    similar_rows: list[dict[str, Any]],
    source_label: str,
    max_depth: int,
    business_keys: list[str] | None = None,
    graph_results: dict[str, Any] | None = None,
) -> None:
    if business_keys is None or graph_results is None:
        business_keys = []
        seen: set[str] = set()
        for row in similar_rows:
            key = str(row.get("business_key") or "").strip()
            if not key or key in seen:
                continue
            seen.add(key)
            business_keys.append(key)

        retrieve = load_retrieval_function()
        graph_results = {}
        for key in business_keys:
            try:
                graph_results[key] = retrieve(key, max_depth=max_depth)
            except Exception as exc:
                graph_results[key] = {
                    "found": False,
                    "business_key": key,
                    "error": str(exc),
                    "start_node": None,
                    "visited_nodes": [],
                    "relationships": [],
                }

    st.session_state["similar_nodes_page_payload"] = {
        "source": source_label,
        "similar_rows": similar_rows,
        "business_keys": business_keys,
        "graph_results": graph_results,
    }

    app_dir = Path(__file__).resolve().parent
    absolute_targets = [
        app_dir / "pages" / "3_Similar_Nodes.py",
    ]

    for target in (
        "pages/3_Similar_Nodes.py",
        "3_Similar_Nodes.py",
        "frontend_app/pages/3_Similar_Nodes.py",
        "Similar Nodes",
    ):
        try:
            st.switch_page(target)
            return
        except StreamlitAPIException:
            continue

    for target in absolute_targets:
        try:
            st.switch_page(str(target))
            return
        except StreamlitAPIException:
            continue

    st.session_state["show_similar_nodes_inline_page"] = True
    st.rerun()


def render_similar_nodes_inline(payload: dict[str, Any]) -> None:
    st.subheader("Similar Nodes")
    st.caption("Nodes returned from Find Similar search")

    back_col, _ = st.columns([1, 5])
    if back_col.button("Back"):
        st.session_state["show_similar_nodes_inline_page"] = False
        st.rerun()

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


def main() -> None:
    st.set_page_config(page_title=APP_TITLE, layout="wide")

    st.title(APP_TITLE)
    st.caption(APP_SUBTITLE)

    with st.sidebar:
        st.markdown("### AWS Credentials")
        aws_access_key_id = st.text_input(
            "AWS_ACCESS_KEY_ID", type="password", autocomplete="off", key="aws_access_key_id"
        )
        aws_secret_access_key = st.text_input(
            "AWS_SECRET_ACCESS_KEY", type="password", autocomplete="off", key="aws_secret_access_key"
        )
        aws_region = st.text_input(
            "AWS_REGION", value="us-east-1", autocomplete="off", key="aws_region"
        )
        st.session_state["aws_credentials"] = {
            "AWS_ACCESS_KEY_ID": aws_access_key_id.strip(),
            "AWS_SECRET_ACCESS_KEY": aws_secret_access_key.strip(),
            "AWS_REGION": aws_region.strip() or "us-east-1",
        }

    if "last_result" not in st.session_state:
        st.session_state["last_result"] = None
    if "last_error" not in st.session_state:
        st.session_state["last_error"] = ""
    if "chunk_summaries" not in st.session_state:
        st.session_state["chunk_summaries"] = {}
    if "last_max_depth" not in st.session_state:
        st.session_state["last_max_depth"] = 5
    if "show_similar_nodes_inline_page" not in st.session_state:
        st.session_state["show_similar_nodes_inline_page"] = False

    left_panel, right_panel = st.columns([1, 3], gap="large")

    with left_panel:
        st.markdown("### Search")
        with st.form("graph_retrieval_form"):
            business_key = st.text_input("Business Key", placeholder="Enter business key")
            max_depth = st.number_input("Max Depth", min_value=1, max_value=50, value=5, step=1)
            submitted = st.form_submit_button("Retrieve")

        if submitted:
            normalized_key = business_key.strip()
            if not normalized_key:
                st.session_state["last_result"] = None
                st.session_state["last_error"] = "Please enter a business key."
            else:
                try:
                    retrieve = load_retrieval_function()
                    with st.spinner("Retrieving graph data..."):
                        st.session_state["last_result"] = retrieve(
                            normalized_key, max_depth=int(max_depth)
                        )
                    st.session_state["last_max_depth"] = int(max_depth)
                    st.session_state["last_error"] = ""
                except Exception as exc:
                    st.session_state["last_result"] = None
                    st.session_state["last_error"] = f"Failed to retrieve graph data: {exc}"

    with right_panel:
        result = st.session_state.get("last_result")
        last_error = st.session_state.get("last_error", "")

        if last_error:
            st.error(last_error)
        if not result:
            st.info("Submit a business key from the left panel to view tabs and graph.")
            return

        if st.session_state.get("show_similar_nodes_inline_page"):
            payload = st.session_state.get("similar_nodes_page_payload") or {}
            if payload:
                render_similar_nodes_inline(payload)
                return
            st.session_state["show_similar_nodes_inline_page"] = False

        found = bool(result.get("found"))
        if not found:
            st.info(f"No node found for business key: {result.get('business_key', '')}")

        tab_primary, tab_related, tab_relation, tab_chunks = st.tabs(
            ["Primary Object", "Related Object", "Relation", "Chunks"]
        )

        start_node = result.get("start_node")
        visited_nodes = result.get("visited_nodes") or []
        relationships = result.get("relationships") or []
        related_text_chunks = result.get("related_text_chunks") or []

        with tab_primary:
            st.subheader("Start Node")
            if start_node:
                st.caption(f"Text chunks for primary object: {len(start_node.get('text_chunks') or [])}")
                render_object_table(start_node)
            else:
                st.info("No start node available.")

        with tab_related:
            st.subheader("Visited Nodes")
            start_uuid = (start_node or {}).get("node_uuid")
            related_nodes = [
                node for node in visited_nodes if str(node.get("node_uuid")) != str(start_uuid)
            ]
            st.caption(f"Total related objects: {len(related_nodes)}")
            if related_nodes:
                for idx, node in enumerate(related_nodes, start=1):
                    node_uuid = str(node.get("node_uuid") or "")
                    node_label = str(node.get("display_name") or node.get("business_key") or node_uuid)
                    with st.expander(f"Related Object {idx}: {node_label}", expanded=idx == 1):
                        st.caption(f"Node UUID: {node_uuid}")
                        render_object_table(node)
            else:
                st.info("No related objects found.")

        with tab_relation:
            st.subheader("Relationships")
            st.caption(f"Total relations: {len(relationships)}")
            if relationships:
                relationship_rows = []
                for idx, rel in enumerate(relationships, start=1):
                    relationship_rows.append(
                        {
                            "#": idx,
                            "relationship": rel.get("relationship"),
                            "from_business_key": rel.get("from_business_key"),
                            "to_business_key": rel.get("to_business_key"),
                            "from_node_uuid": rel.get("from_node_uuid"),
                            "to_node_uuid": rel.get("to_node_uuid"),
                        }
                    )

                st.dataframe(relationship_rows, use_container_width=True, hide_index=True)

                with st.expander("Relationships (JSON)"):
                    st.json(relationships)
            else:
                st.info("No relationships found.")

        with tab_chunks:
            st.subheader("Related Text Chunks")
            st.caption(f"Total chunks: {len(related_text_chunks)}")
            if related_text_chunks:
                node_info_by_uuid = {
                    str(node.get("node_uuid")): node
                    for node in visited_nodes
                    if node.get("node_uuid")
                }
                chunk_rows = []
                for idx, chunk in enumerate(related_text_chunks, start=1):
                    chunk_node_uuid = str(chunk.get("node_uuid") or "")
                    node_info = node_info_by_uuid.get(chunk_node_uuid, {})
                    chunk_rows.append(
                        {
                            "node_type": node_info.get("node_type"),
                            "business_key": node_info.get("business_key"),
                            "chunk_type": chunk.get("chunk_type"),
                            "text_content": chunk.get("text_content"),
                        }
                    )

                header_cols = st.columns([1.1, 1.2, 1.1, 3, 1, 1])
                header_cols[0].markdown("**Node Type**")
                header_cols[1].markdown("**Business Key**")
                header_cols[2].markdown("**Chunk Type**")
                header_cols[3].markdown("**Text Content**")
                header_cols[4].markdown("**Summary**")
                header_cols[5].markdown("**Find Similar**")

                for idx, row in enumerate(chunk_rows, start=1):
                    row_key = f"chunk_{idx}"
                    row_cols = st.columns([1.1, 1.2, 1.1, 3, 1, 1])
                    row_cols[0].write(row.get("node_type") or "")
                    row_cols[1].write(row.get("business_key") or "")
                    row_cols[2].write(row.get("chunk_type") or "")

                    text_value = str(row.get("text_content") or "")
                    preview = text_value if len(text_value) <= 120 else f"{text_value[:120]}..."
                    row_cols[3].write(preview)
                    if len(text_value) > 120:
                        with row_cols[3].expander("Expand text", expanded=False):
                            st.write(text_value)

                    if row_cols[4].button("Summary", key=f"{row_key}_summary_btn"):
                        if not text_value.strip():
                            summaries = dict(st.session_state.get("chunk_summaries", {}))
                            summaries[row_key] = "No text content available for this chunk."
                            st.session_state["chunk_summaries"] = summaries
                        else:
                            try:
                                summarize_text = load_summarizer_function()
                                with st.spinner("Generating business summary..."):
                                    summary_text = summarize_text(
                                        text_value,
                                        aws_credentials=st.session_state.get("aws_credentials"),
                                    )
                                summaries = dict(st.session_state.get("chunk_summaries", {}))
                                summaries[row_key] = summary_text
                                st.session_state["chunk_summaries"] = summaries
                            except Exception as exc:
                                summaries = dict(st.session_state.get("chunk_summaries", {}))
                                summaries[row_key] = f"Summary generation failed: {exc}"
                                st.session_state["chunk_summaries"] = summaries

                    if row_cols[5].button("Find Similar", key=f"{row_key}_similar_text_btn"):
                        if text_value.strip():
                            try:
                                with st.spinner("Running semantic search..."):
                                    similar_rows, semantic_keys, semantic_graph_results = run_semantic_find_similar(
                                        text_value,
                                        max_depth=int(st.session_state.get("last_max_depth", 5)),
                                    )
                                open_similar_nodes_page(
                                    similar_rows,
                                    source_label="Original text (semantic)",
                                    max_depth=int(st.session_state.get("last_max_depth", 5)),
                                    business_keys=semantic_keys,
                                    graph_results=semantic_graph_results,
                                )
                            except Exception as exc:
                                st.error(f"Semantic search failed: {exc}")
                        else:
                            st.warning("No text content available for semantic search.")

                    summary_text = (st.session_state.get("chunk_summaries", {}) or {}).get(row_key, "")
                    if summary_text:
                        st.markdown(f"**Summary:** {summary_text}")
                        summary_action_cols = st.columns([1.2, 6])
                        if summary_action_cols[0].button(
                            "Find Similar (Summary)",
                            key=f"{row_key}_similar_summary_btn",
                        ):
                            if summary_text.strip():
                                try:
                                    with st.spinner("Running semantic search..."):
                                        similar_rows, semantic_keys, semantic_graph_results = run_semantic_find_similar(
                                            summary_text,
                                            max_depth=int(st.session_state.get("last_max_depth", 5)),
                                        )
                                    open_similar_nodes_page(
                                        similar_rows,
                                        source_label="Summary text (semantic)",
                                        max_depth=int(st.session_state.get("last_max_depth", 5)),
                                        business_keys=semantic_keys,
                                        graph_results=semantic_graph_results,
                                    )
                                except Exception as exc:
                                    st.error(f"Semantic search failed: {exc}")
                            else:
                                st.warning("Summary is empty for semantic search.")

                    st.markdown("---")

                with st.expander("Chunks (JSON)"):
                    st.json(related_text_chunks)
            else:
                st.info("No related text chunks found.")

        with st.expander("Raw Response"):
            st.json(result)


if __name__ == "__main__":
    main()
