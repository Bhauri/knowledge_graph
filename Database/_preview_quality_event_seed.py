from seed_quality_events import build_quality_event
from faker import Faker

fake = Faker()
row = build_quality_event(fake)

print("TITLE:", row[0])
print("OBS_WORDS:", len(row[6].split()))
print("EXP_WORDS:", len(row[7].split()))
print("OBS_SAMPLE:", row[6][:500])
print("EXP_SAMPLE:", row[7][:500])
