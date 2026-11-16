from __future__ import annotations

from datetime import timedelta, timezone
from random import choice, random, randint
from pathlib import Path
import sys

from faker import Faker


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from seed_duckdb import connect_seed_db, drop_seed_tables, insert_rows, recreate_seed_table
from seed_text_utils import sample_scenario, themed_title, long_medical_text


TOTAL_ROWS = 3000
BATCH_SIZE = 500
MIN_WORDS = 100
MAX_WORDS = 200


def _build_observation_and_expectation(fake: Faker, scenario: dict[str, str]) -> tuple[str, str]:
    observation = long_medical_text(fake, scenario, "qe_observation", MIN_WORDS, MAX_WORDS)
    expectation = long_medical_text(fake, scenario, "qe_expectation", MIN_WORDS, MAX_WORDS)
    return observation, expectation


def build_quality_event(fake: Faker) -> tuple:
    created_at = fake.date_time_between(start_date="-2y", end_date="now", tzinfo=timezone.utc)
    open_offset_days = randint(0, 20)
    close_after_days = randint(1, 45)
    scenario = sample_scenario()

    date_opened = created_at + timedelta(days=open_offset_days)
    is_closed = random() > 0.45
    date_closed = date_opened + timedelta(days=close_after_days) if is_closed else None

    event_status = choice(["Open", "Investigation In Progress", "Containment In Progress", "Closed"])
    if date_closed:
        event_status = "Closed"

    observation, expectation = _build_observation_and_expectation(fake, scenario)
    title = themed_title(scenario, f"{scenario['test'].title()} Signal")

    return (
        title,
        fake.name(),
        date_opened,
        date_closed,
        fake.name(),
        fake.name(),
        observation,
        expectation,
        scenario["activity"],
        fake.name(),
        fake.city(),
        scenario["site"],
        random() > 0.35,
        random() > 0.6,
        choice(["Confirmed", "Pending Review", "Partially Confirmed"]),
        event_status,
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    insert_sql = """
        INSERT INTO dbo.qe (
            title,
            created_by,
            date_opend,
            date_closer,
            investigator,
            approver,
            observatrion,
            expectation,
            found_during_activity,
            who_discoverd,
            locaiton,
            initiating_site,
            containment_requireed,
            esc_required,
            event_confirm,
            status
        ) VALUES %s
    """

    qe_columns_sql = """
        title VARCHAR(255) NOT NULL,
        created_by VARCHAR(100),
        date_opend TIMESTAMPTZ DEFAULT current_timestamp,
        date_closer TIMESTAMPTZ,
        investigator VARCHAR(100),
        approver VARCHAR(100),
        observatrion VARCHAR,
        expectation VARCHAR,
        found_during_activity VARCHAR(255),
        who_discoverd VARCHAR(100),
        locaiton VARCHAR(255),
        initiating_site VARCHAR(255),
        containment_requireed BOOLEAN DEFAULT false,
        esc_required BOOLEAN DEFAULT false,
        event_confirm VARCHAR(255),
        status VARCHAR(50)
    """

    try:
        drop_seed_tables(connection)
        recreate_seed_table(connection, "qe", qe_columns_sql, id_column="qe_id")
        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = [build_quality_event(fake) for _ in range(BATCH_SIZE)]
            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()