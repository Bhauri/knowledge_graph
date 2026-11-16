import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from src.agent.intent_analyzer import IntentAnalyzer
from src.agent.business_concept_resolver import BusinessConceptResolver
from src.agent.schema_resolver import SchemaResolver

q = "how many psp failed with defect code 123"
intent = IntentAnalyzer().analyze(q)
print("INTENT", intent)
concepts = BusinessConceptResolver().resolve(intent)
print("CONCEPTS", concepts)
schema = SchemaResolver().resolve(target_entity=intent.get("target_entity", ""), concept_resolution=concepts)
for item in schema:
	print("CONCEPT", item.get("concept"), "STATUS", item.get("status"))
	for cand in item.get("candidates", [])[:5]:
		print(
			"  ",
			cand.get("entity_name"),
			cand.get("canonical_name"),
			cand.get("final_score"),
			cand.get("lexical_score"),
			cand.get("similarity"),
		)
