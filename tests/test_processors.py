from __future__ import annotations

import app.graph_creater.processors as processors
from app.graph_creater.processors import process_initial_evaluations_row, process_qe_events_row, process_qe_row
from app.graph_creater.table_specs import load_table_spec


def test_process_qe_row_creates_main_and_dimension_nodes() -> None:
    row = {
        "qe_id": 7,
        "title": "Line deviation",
        "created_by": " Alice ",
        "date_opend": "2026-01-01",
        "date_closer": None,
        "investigator": "Bob",
        "approver": "Cara",
        "observatrion": "Observation",
        "expectation": "Expectation",
        "found_during_activity": "Inspection",
        "who_discoverd": "Dan",
        "locaiton": "  Boston  ",
        "initiating_site": " Plant A ",
        "containment_requireed": True,
        "esc_required": False,
        "event_confirm": "Confirmed",
        "status": "Open",
    }

    nodes = process_qe_row(row)
    node_types = {node.node_type for node in nodes}

    assert "QualityEvent" in node_types
    assert "Person" in node_types
    assert "Site" in node_types
    assert "Location" in node_types


def test_process_qe_events_row_skips_testing_nodes_for_non_oox() -> None:
    row = {
        "event_id": 1,
        "event_descrption": "Supplier issue",
        "event_type": "supplier",
        "testing_type": "Test",
        "testing_id": "TEST-1",
        "test_description": "Should be skipped",
        "test_result": None,
        "test_date": None,
        "event_description": "Event detail",
        "specificatin": "Spec",
        "category": "Category",
        "failurecode": "FC-001",
    }

    nodes = process_qe_events_row(row)
    node_types = {node.node_type for node in nodes}

    assert "EventType" in node_types
    assert "TestingType" not in node_types
    assert "Test" not in node_types


def test_process_qe_events_row_includes_testing_nodes_for_oox() -> None:
    row = {
        "event_id": 2,
        "event_descrption": "OOX event",
        "event_type": "oox",
        "testing_type": "Validation",
        "testing_id": "TEST-2",
        "test_description": "Detailed test description",
        "test_result": "Pass",
        "test_date": None,
        "event_description": "Event detail",
        "specificatin": "Spec",
        "category": "Category",
        "failurecode": "FC-002",
    }

    nodes = process_qe_events_row(row)
    node_types = {node.node_type for node in nodes}

    assert "TestingType" in node_types
    assert "Test" in node_types


def test_process_initial_evaluations_row_creates_risk_and_direct_cause_nodes() -> None:
    row = {
        "eval_id": 3,
        "parent_qeid": 5,
        "parent_event_id": 8,
        "create_date": "2026-01-01",
        "due_date": "2026-02-01",
        "closed_date": None,
        "shord_desc": "Initial evaluation",
        "status": "Open",
        "impact_on_product_medical_device": "Impact",
        "risk_to_patine_health": "Risk",
        "quality_system_failure": "Failure",
        "ridk_to_dat": "Risk data",
        "overall_risk_lelve": "Low",
        "initial_assess_outcome": "NCI",
        "overall_risk_level": "High",
        "direct_cause": "Operator error",
        "threshold_exceeded": False,
        "regularoty_impact": "None",
    }

    nodes = process_initial_evaluations_row(row)
    node_types = {node.node_type for node in nodes}

    assert "Evaluation" in node_types
    assert "RiskLevel" in node_types
    assert "DirectCause" in node_types


def test_table_spec_loader_reads_yaml_configuration() -> None:
    spec = load_table_spec("qe")

    assert spec["source_table"] == "qe"
    assert spec["primary_node"]["node_type"] == "QualityEvent"
    assert spec["primary_node"]["primary_key_column"] == "qe_id"
    assert spec["derived_nodes"][0]["column"] == "created_by"
    assert spec["derived_nodes"][0]["node_type"] == "Person"


def test_process_qe_row_honors_yaml_excluded_columns() -> None:
    row = {
        "qe_id": 7,
        "title": "Line deviation",
        "created_by": "Alice",
        "observation": "Observation text",
        "expectation": "Expectation text",
    }

    nodes = process_qe_row(row)
    primary_node = next(node for node in nodes if node.node_type == "QualityEvent")

    assert "qe_id" not in primary_node.properties
    assert "observation" not in primary_node.properties
    assert "expectation" not in primary_node.properties
    assert "title" in primary_node.properties


def test_derived_nodes_use_their_own_source_column_properties() -> None:
    row = {
        "qe_id": 7,
        "title": "Line deviation",
        "created_by": "Alice",
        "investigator": "Bob",
        "approver": "Cara",
        "observation": "Observation text",
        "expectation": "Expectation text",
    }

    nodes = process_qe_row(row)
    person_node = next(node for node in nodes if node.node_type == "Person" and node.business_key == "alice")

    assert person_node.properties == {"created_by": "Alice"}
    assert "title" not in person_node.properties
    assert "observation" not in person_node.properties


def test_process_source_table_uses_yaml_for_yaml_only_tables() -> None:
    row = {
        "custom_id": 99,
        "title": "Custom title",
        "owner": "Alice",
        "description": "Custom description",
    }

    nodes = processors.process_source_table("custom_table", [row])
    node_types = {node.node_type for node in nodes}

    assert "CustomNode" in node_types
    assert "Person" in node_types
