from __future__ import annotations

from datetime import date, timedelta, timezone
from random import choice, randint, random
from pathlib import Path
import sys

from faker import Faker


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from seed_duckdb import connect_seed_db, insert_rows, recreate_seed_table
from seed_text_utils import long_medical_text, sample_scenario, themed_title


TOTAL_ROWS = 2000
BATCH_SIZE = 500


def build_containment_action(fake: Faker, parent_qe_id: int, parent_psp_id: int | None) -> tuple:
    creation_date = fake.date_time_between(start_date="-1y", end_date="now", tzinfo=timezone.utc)
    scenario = sample_scenario()

    quality_action_type = choice([
        "Containment",
        "Corrective Action",
        "Preventive Action",
        "Investigation",
        "Verification",
    ])

    subtype = choice([
        "Immediate containment",
        "Root cause follow-up",
        "Supplier verification",
        "Line reinspection",
        "Customer protection",
    ])

    status = "Closed" if random() > 0.55 else choice(["Open", "In Progress", "Pending Review", "On Hold"])

    return (
        quality_action_type,
        subtype,
        status,
        creation_date,
        fake.name(),
        fake.name(),
        long_medical_text(fake, scenario, "containment_assessment", 220, 360),
        fake.name(),
        themed_title(scenario, subtype),
        long_medical_text(fake, scenario, "action_description", 180, 320),
        long_medical_text(fake, scenario, "justification", 120, 220),
        parent_qe_id,
        parent_psp_id,
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    containment_actions_columns_sql = """
        quality_action_type VARCHAR(100),
        subtype VARCHAR(100),
        status VARCHAR(50) DEFAULT 'Open',
        creation_date TIMESTAMPTZ DEFAULT current_timestamp,
        assign_to VARCHAR(100),
        completed_by VARCHAR(100),
        qa_assessment VARCHAR,
        quality_appropver VARCHAR(100),
        title VARCHAR(255) NOT NULL,
        description VARCHAR,
        justification VARCHAR,
        parent_qe_id INTEGER,
        parent_psp_id INTEGER
    """

    qe_ids_query = "SELECT qe_id FROM dbo.qe"
    psp_ids_query = "SELECT psp_id FROM dbo.psp"

    insert_sql = """
        INSERT INTO dbo.containment_actions (
            quality_action_type,
            subtype,
            status,
            creation_date,
            assign_to,
            completed_by,
            qa_assessment,
            quality_appropver,
            title,
            description,
            justification,
            parent_qe_id,
            parent_psp_id
        ) VALUES %s
    """

    try:
        recreate_seed_table(connection, "containment_actions", containment_actions_columns_sql, id_column="con_id")

        qe_ids = [row[0] for row in connection.execute(qe_ids_query).fetchall()]
        if not qe_ids:
            raise RuntimeError("No qe rows found. Seed dbo.qe before seeding dbo.containment_actions.")

        psp_ids = [row[0] for row in connection.execute(psp_ids_query).fetchall()]

        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = []
            for _ in range(BATCH_SIZE):
                parent_qe_id = choice(qe_ids)
                parent_psp_id = choice(psp_ids) if psp_ids and random() > 0.4 else None
                rows.append(build_containment_action(fake, parent_qe_id, parent_psp_id))

            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()