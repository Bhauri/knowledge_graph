from __future__ import annotations

from collections import defaultdict
from random import choice, random
from pathlib import Path
import sys

from faker import Faker


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from seed_duckdb import connect_seed_db, insert_rows, recreate_seed_table
from seed_text_utils import long_medical_text, sample_scenario


TOTAL_ROWS = 8000
BATCH_SIZE = 1000


def build_batch_record(fake: Faker, con_id: int, batch_index: int) -> tuple:
    batch_status = choice([
        "Open",
        "In Progress",
        "On Hold",
        "Disposition Pending",
        "Closed",
    ])

    batch_code = f"BATCH-{con_id}-{batch_index:04d}"
    deleteion_ind = random() < 0.12
    scenario = sample_scenario()

    return (
        con_id,
        batch_status,
        batch_code,
        scenario["site"],
        long_medical_text(fake, scenario, "batch_material", 60, 120),
        choice([
            "Accept",
            "Reject",
            "Rework",
            "Quarantine",
            "Return to Supplier",
            "Use As Is",
        ]),
        deleteion_ind,
        long_medical_text(fake, scenario, "deletion_comment", 40, 80) if deleteion_ind else None,
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    batch_columns_sql = """
        con_id INTEGER NOT NULL,
        batch_status VARCHAR(50),
        batch VARCHAR(100) NOT NULL,
        batch_site VARCHAR(255),
        batch_material VARCHAR,
        desposition_decision VARCHAR,
        deleteion_ind BOOLEAN DEFAULT false,
        deleteion_commetn VARCHAR,
        PRIMARY KEY (con_id, batch)
    """

    con_ids_query = "SELECT con_id FROM dbo.containment_actions"

    insert_sql = """
        INSERT INTO dbo.batch_containment_details (
            con_id,
            batch_status,
            batch,
            batch_site,
            batch_material,
            desposition_decision,
            deleteion_ind,
            deleteion_commetn
        ) VALUES %s
    """

    try:
        recreate_seed_table(connection, "batch_containment_details", batch_columns_sql)

        con_ids = [row[0] for row in connection.execute(con_ids_query).fetchall()]

        if not con_ids:
            raise RuntimeError(
                "No containment_actions rows found. Seed dbo.containment_actions before seeding batch_containment_details."
            )

        batch_counts: dict[int, int] = defaultdict(int)

        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = []
            for _ in range(BATCH_SIZE):
                con_id = choice(con_ids)
                batch_counts[con_id] += 1
                rows.append(build_batch_record(fake, con_id, batch_counts[con_id]))

            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()