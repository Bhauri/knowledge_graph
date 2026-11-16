from __future__ import annotations

from datetime import date, timedelta, timezone
from random import choice, random, randint
from pathlib import Path
import sys

from faker import Faker


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.append(str(CURRENT_DIR))

from seed_duckdb import connect_seed_db, insert_rows, recreate_seed_table
from seed_text_utils import (
    long_medical_text,
    random_defer_item,
    random_event_status,
    random_specification,
    random_test_result,
    random_testing_type,
    sample_scenario,
    testing_id,
)


TOTAL_ROWS = 6000
BATCH_SIZE = 1000


def build_qe_event(fake: Faker, parent_qe_id: int, parent_psp_id: int | None) -> tuple:
    create_date = fake.date_time_between(start_date="-2y", end_date="now", tzinfo=timezone.utc)
    due_date = date.today() + timedelta(days=randint(7, 120))
    closed_date = due_date if random() > 0.55 else None
    scenario = sample_scenario()

    event_type = choice(["oox", "supplier", "process", "product", "other"])
    status = random_event_status(closed_date is not None)

    is_oox = event_type == "oox"

    return (
        parent_qe_id,
        parent_psp_id,
        create_date,
        due_date,
        closed_date,
        status,
        long_medical_text(fake, scenario, "qe_event_description", 300, 550),
        random_defer_item(),
        long_medical_text(fake, scenario, "defect_description", 160, 260),
        event_type,
        random_testing_type() if is_oox else None,
        testing_id() if is_oox else None,
        long_medical_text(fake, scenario, "test_description", 130, 220) if is_oox else None,
        random_test_result() if is_oox else None,
        date.today() - timedelta(days=randint(0, 90)) if is_oox else None,
        long_medical_text(fake, scenario, "qe_event_description", 300, 550),
        random_specification(),
        scenario["category"],
        scenario["failure_code"],
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    qe_events_columns_sql = """
        parent_qe_id INTEGER,
        parent_psp_id INTEGER,
        create_date TIMESTAMPTZ DEFAULT current_timestamp,
        due_date DATE,
        closed_date DATE,
        status VARCHAR(50) DEFAULT 'Open',
        event_descrption VARCHAR,
        defer_item VARCHAR(255),
        defect_item_description VARCHAR,
        event_type VARCHAR(100),
        testing_type VARCHAR(100),
        testing_id VARCHAR(100),
        test_description VARCHAR,
        test_result VARCHAR(255),
        test_date DATE,
        event_description VARCHAR,
        specificatin VARCHAR,
        category VARCHAR(100),
        failurecode VARCHAR(100)
    """

    qe_ids_query = "SELECT qe_id FROM dbo.qe"
    psp_ids_query = "SELECT psp_id FROM dbo.psp"

    insert_sql = """
        INSERT INTO dbo.qe_events (
            parent_qe_id,
            parent_psp_id,
            create_date,
            due_date,
            closed_date,
            status,
            event_descrption,
            defer_item,
            defect_item_description,
            event_type,
            testing_type,
            testing_id,
            test_description,
            test_result,
            test_date,
            event_description,
            specificatin,
            category,
            failurecode
        ) VALUES %s
    """

    try:
        recreate_seed_table(connection, "qe_events", qe_events_columns_sql, id_column="event_id")

        qe_ids = [row[0] for row in connection.execute(qe_ids_query).fetchall()]
        if not qe_ids:
            raise RuntimeError("No qe rows found. Seed dbo.qe before seeding dbo.qe_events.")

        psp_ids = [row[0] for row in connection.execute(psp_ids_query).fetchall()]

        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = []
            for _ in range(BATCH_SIZE):
                parent_qe_id = choice(qe_ids)
                parent_psp_id = choice(psp_ids) if psp_ids and random() > 0.45 else None
                rows.append(build_qe_event(fake, parent_qe_id, parent_psp_id))

            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()