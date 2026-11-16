from __future__ import annotations

from datetime import date, timedelta, timezone
from random import choice, randint
from pathlib import Path
import sys

from faker import Faker


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from seed_duckdb import connect_seed_db, insert_rows, recreate_seed_table
from seed_text_utils import long_medical_text, sample_scenario


TOTAL_ROWS = 12000
BATCH_SIZE = 1000


def build_capa_record(fake: Faker, parent_psp_id: int) -> tuple:
    creation_date = fake.date_time_between(start_date="-1y", end_date="now", tzinfo=timezone.utc)
    due_date = date.today() + timedelta(days=randint(7, 180))
    completed_date = due_date if choice([True, False, False]) else None
    scenario = sample_scenario()

    return (
        parent_psp_id,
        creation_date,
        due_date,
        completed_date,
        long_medical_text(fake, scenario, "capa_assessment", 300, 550),
        fake.name(),
        scenario["site"],
        long_medical_text(fake, scenario, "action_description", 180, 320),
        choice(["Open", "In Progress", "On Hold", "Closed", "Verified"]),
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    capa_columns_sql = """
        parent_psp_id INTEGER,
        creation_date TIMESTAMPTZ DEFAULT current_timestamp,
        due_date DATE,
        completed_date DATE,
        aq_assessment VARCHAR,
        qa_approver VARCHAR(100),
        initiating_site VARCHAR(255),
        action_take VARCHAR,
        status VARCHAR(50) DEFAULT 'Open'
    """

    psp_ids_query = "SELECT psp_id FROM dbo.psp"

    insert_sql = """
        INSERT INTO dbo.capa (
            parent_psp_id,
            creation_date,
            due_date,
            completed_date,
            aq_assessment,
            qa_approver,
            initiating_site,
            action_take,
            status
        ) VALUES %s
    """

    try:
        recreate_seed_table(connection, "capa", capa_columns_sql, id_column="capa_id")

        psp_ids = [row[0] for row in connection.execute(psp_ids_query).fetchall()]

        if not psp_ids:
            raise RuntimeError("No psp rows found. Seed dbo.psp before seeding dbo.capa.")

        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = [build_capa_record(fake, choice(psp_ids)) for _ in range(BATCH_SIZE)]
            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()