from __future__ import annotations

import json
from typing import Any

from db.database import Database

from .business_concept_resolver import BusinessConceptResolver
from .intent_analyzer import IntentAnalyzer
from .query_planner import QueryPlanner
from .relationship_resolver import RelationshipResolver
from .schema_resolver import SchemaResolver
from .sql_generator import SQLGenerator
from .sql_validator import SQLValidator


class QueryPipeline:
    def __init__(self) -> None:
        self.intent_analyzer = IntentAnalyzer()
        self.concept_resolver = BusinessConceptResolver()
        self.schema_resolver = SchemaResolver()
        self.relationship_resolver = RelationshipResolver()
        self.query_planner = QueryPlanner()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.database = Database()

    def process_query(self, user_query: str) -> dict[str, Any]:
        def print_stage(stage_name: str, payload: Any) -> None:
            print(f"***** {stage_name} *******")
            print(json.dumps(payload, indent=2, default=str))

        try:
            intent = self.intent_analyzer.analyze(user_query)
            print_stage("Intent Analyzer", intent)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Intent Analyzer",
                "errors": [str(exc)],
            }
            print_stage("Intent Analyzer", error_result)
            return error_result

        try:
            concept_resolution = self.concept_resolver.resolve(intent)
            print_stage("Concept Resolver", concept_resolution)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Concept Resolver",
                "errors": [str(exc)],
            }
            print_stage("Concept Resolver", error_result)
            return error_result

        try:
            schema_resolution = self.schema_resolver.resolve(
                target_entity=str(intent.get("target_entity", "")),
                concept_resolution=concept_resolution,
            )
            #print_stage("Semantic Schema Resolver", schema_resolution)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Semantic Schema Resolver",
                "errors": [str(exc)],
            }
            #print_stage("Semantic Schema Resolver", error_result)
            return error_result

        if any(item.get("status") == "UNRESOLVED" for item in schema_resolution):
            error_result = {
                "status": "INVALID",
                "stage": "Semantic Schema Resolver",
                "errors": [
                    error
                    for item in schema_resolution
                    for error in item.get("errors", [])
                ],
            }
            #print_stage("Semantic Schema Resolver", error_result)
            return error_result

        try:
            relationship_resolution = self.relationship_resolver.resolve(
                target_entity=str(intent.get("target_entity", "")),
                schema_resolution=schema_resolution,
            )
            #print_stage("Relationship Resolver", relationship_resolution)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Relationship Resolver",
                "errors": [str(exc)],
            }
            #print_stage("Relationship Resolver", error_result)
            return error_result

        if any(item.get("status") != "RESOLVED" for item in relationship_resolution):
            error_result = {
                "status": "INVALID",
                "stage": "Relationship Resolver",
                "errors": [
                    error
                    for item in relationship_resolution
                    for error in item.get("errors", [])
                ],
            }
            #print_stage("Relationship Resolver", error_result)
            return error_result

        try:
            query_plan = self.query_planner.plan(
                intent=intent,
                concept_resolution=concept_resolution,
                schema_resolution=schema_resolution,
                relationship_resolution=relationship_resolution,
            )
            #print_stage("Query Planner", query_plan)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Query Planner",
                "errors": [str(exc)],
            }
            #print_stage("Query Planner", error_result)
            return error_result

        if query_plan.get("status") not in {"VALID", "AMBIGUOUS"}:
            error_result = {
                "status": "INVALID",
                "stage": "Query Planner",
                "errors": query_plan.get("errors", ["Query plan is not valid"]),
            }
            #print_stage("Query Planner", error_result)
            return error_result

        if query_plan.get("status") != "VALID":
            error_result = {
                "status": "INVALID",
                "stage": "Query Planner",
                "errors": query_plan.get("errors", ["Query plan is ambiguous"]),
            }
            return error_result

        try:
            generated = self.sql_generator.generate(query_plan)
            #print_stage("SQL Generator", generated)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "SQL Generator",
                "errors": [str(exc)],
            }
            return error_result

        validation = self.sql_validator.validate(query_plan, generated)
        #print_stage("SQL Validator", validation)
        if validation.get("status") != "VALID":
            error_result = {
                "status": "INVALID",
                "stage": "SQL Validator",
                "errors": validation.get("errors", ["SQL validation failed"]),
            }
            return error_result

        try:
            rows = self.database.execute(generated["sql"], generated["parameters"])
            #print_stage("Execute SQL", rows)
        except Exception as exc:
            error_result = {
                "status": "INVALID",
                "stage": "Execute SQL",
                "errors": [str(exc)],
            }
            return error_result

        final_result = {
            "status": "VALID",
            "intent": intent,
            "concept_resolution": concept_resolution,
            "schema_resolution": schema_resolution,
            "relationship_resolution": relationship_resolution,
            "query_plan": query_plan,
            "sql": generated["sql"],
            "parameters": generated["parameters"],
            "result": rows,
        }
        #print_stage("Final Response", final_result)
        return final_result

def process_query(user_query: str) -> dict[str, Any]:
    pipeline = QueryPipeline()
    return pipeline.process_query(user_query)
