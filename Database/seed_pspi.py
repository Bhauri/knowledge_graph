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
from seed_text_utils import long_medical_text, root_cause_category, sample_scenario, themed_title


TOTAL_ROWS = 7000


def build_pspi_record(fake: Faker, parent_qeid: int) -> tuple:
    created_on = fake.date_time_between(start_date="-1y", end_date="now", tzinfo=timezone.utc)
    due_date = date.today() + timedelta(days=randint(7, 120))
    closed_date = due_date if choice([True, False]) else None
    scenario = sample_scenario()

    return (
        parent_qeid,
        themed_title(scenario, "PSP Investigation"),
        fake.name(),
        created_on,
        scenario["site"],
        long_medical_text(fake, scenario, "psp_description", 300, 550),
        long_medical_text(fake, scenario, "psp_investigation", 300, 550),
        long_medical_text(fake, scenario, "investigation_plan", 130, 220),
        long_medical_text(fake, scenario, "psp_summary", 300, 550),
        scenario["tool"],
        long_medical_text(fake, scenario, "historical_parameter", 120, 220),
        long_medical_text(fake, scenario, "root_cause", 120, 220),
        root_cause_category(),
        choice([True, False]),
        long_medical_text(fake, scenario, "justification", 120, 220),
        due_date,
        closed_date,
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    qe_ids_query = "SELECT qe_id FROM dbo.qe"
    insert_sql = """
        INSERT INTO dbo.psp (
            parent_qeid,
            title,
            created_by,
            create_on,
            owniing_site,
            description,
            investigation,
            investigation_plan,
            investigation_summary,
            tool_used,
            historical_paramter,
            root_cause,
            root_cause_category,
            capa_require,
            justification,
            psp_due_date,
            closed_date
        ) VALUES %s
    """

    psp_columns_sql = """
        parent_qeid INTEGER,
        title VARCHAR(255) NOT NULL,
        created_by VARCHAR(100),
        create_on TIMESTAMPTZ DEFAULT current_timestamp,
        owniing_site VARCHAR(255),
        description VARCHAR,
        investigation VARCHAR,
        investigation_plan VARCHAR,
        investigation_summary VARCHAR,
        tool_used VARCHAR(255),
        historical_paramter VARCHAR,
        root_cause VARCHAR,
        root_cause_category VARCHAR(100),
        capa_require BOOLEAN DEFAULT false,
        justification VARCHAR,
        psp_due_date DATE,
        closed_date DATE
    """

    try:
        qe_ids = [row[0] for row in connection.execute(qe_ids_query).fetchall()]

        if not qe_ids:
            raise RuntimeError("No qe rows found. Seed dbo.qe before seeding dbo.pspi.")

        recreate_seed_table(connection, "psp", psp_columns_sql, id_column="psp_id")
        rows = [build_pspi_record(fake, choice(qe_ids)) for _ in range(TOTAL_ROWS)]
        insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()