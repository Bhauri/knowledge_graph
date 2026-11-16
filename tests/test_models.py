from __future__ import annotations

from datetime import datetime, timezone

from app.graph_creater.models import build_properties, create_node, normalize_key, update_source_refs


def test_normalize_key_slugs_and_trims() -> None:
    assert normalize_key("  FACT NCI / High Risk  ") == "fact-nci-high-risk"


def test_build_properties_trims_and_ignores_nulls() -> None:
    row = {
        "name": "  Example Name  ",
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "ignored": None,
    }

    properties = build_properties(row, excluded_columns={"ignored"})

    assert properties["name"] == "Example Name"
    assert properties["created_at"] == "2026-01-01T00:00:00+00:00"
    assert "ignored" not in properties


def test_update_source_refs_dedupes() -> None:
    existing = [{"table": "qe", "column": "created_by", "primary_key": 1}]
    merged = update_source_refs(existing, {"table": "qe", "column": "created_by", "primary_key": 1})
    assert merged == existing


def test_create_node_normalizes_key_and_sets_display() -> None:
    node = create_node(
        node_type="Person",
        business_key="  Jane Doe  ",
        display_name="  Jane Doe  ",
        source_ref={"table": "qe", "column": "created_by", "primary_key": 10},
        properties={"qe_id": 10},
    )

    assert node.business_key == "jane-doe"
    assert node.display_name == "Jane Doe"
    assert node.source_refs == [{"table": "qe", "column": "created_by", "primary_key": 10}]
