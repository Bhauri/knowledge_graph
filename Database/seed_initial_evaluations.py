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
from seed_text_utils import long_medical_text, random_event_status, sample_scenario, themed_title


TOTAL_ROWS = 4000
BATCH_SIZE = 1000


def build_initial_evaluation(fake: Faker, parent_qe_id: int, parent_event_id: int | None) -> tuple:
    create_date = fake.date_time_between(start_date="-2y", end_date="now", tzinfo=timezone.utc)
    due_date = date.today() + timedelta(days=randint(7, 120))
    closed_date = due_date if random() > 0.6 else None
    scenario = sample_scenario()
    status = random_event_status(closed_date is not None)

    return (
        parent_qe_id,
        parent_event_id,
        create_date,
        due_date,
        closed_date,
        themed_title(scenario, "Initial Evaluation"),
        status,
        long_medical_text(fake, scenario, "initial_eval", 120, 220),
        long_medical_text(fake, scenario, "capa_assessment", 140, 240),
        long_medical_text(fake, scenario, "psp_description", 140, 240),
        choice([
            "Data traceability weakness",
            "System control gap",
            "Inspection coverage issue",
            "Supplier escalation delay",
            "Training deficiency",
        ]),
        choice(["Low", "Moderate", "High", "Critical"]),
        long_medical_text(fake, scenario, "qe_expectation", 120, 220),
        choice(["Low", "Moderate", "High", "Critical"]),
        long_medical_text(fake, scenario, "root_cause", 120, 200),
        random() > 0.7,
        long_medical_text(fake, scenario, "justification", 100, 180),
    )


def main() -> None:
    connection = connect_seed_db()

    fake = Faker()

    initial_evaluations_columns_sql = """
        parent_qeid INTEGER,
        parent_event_id INTEGER,
        create_date TIMESTAMPTZ DEFAULT current_timestamp,
        due_date DATE,
        closed_date DATE,
        shord_desc VARCHAR(255),
        status VARCHAR(50) DEFAULT 'Open',
        impact_on_product_medical_device VARCHAR,
        risk_to_patine_health VARCHAR,
        quality_system_failure VARCHAR,
        ridk_to_dat VARCHAR,
        overall_risk_lelve VARCHAR(50),
        initial_assess_outcome VARCHAR,
        overall_risk_level VARCHAR(50),
        direct_cause VARCHAR,
        threshold_exceeded BOOLEAN DEFAULT false,
        regularoty_impact VARCHAR
    """

    qe_ids_query = "SELECT qe_id FROM dbo.qe"
    event_ids_query = "SELECT event_id FROM dbo.qe_events"

    insert_sql = """
        INSERT INTO dbo.initial_evaluations (
            parent_qeid,
            parent_event_id,
            create_date,
            due_date,
            closed_date,
            shord_desc,
            status,
            impact_on_product_medical_device,
            risk_to_patine_health,
            quality_system_failure,
            ridk_to_dat,
            overall_risk_lelve,
            initial_assess_outcome,
            overall_risk_level,
            direct_cause,
            threshold_exceeded,
            regularoty_impact
        ) VALUES %s
    """

    try:
        recreate_seed_table(
            connection,
            "initial_evaluations",
            initial_evaluations_columns_sql,
            id_column="eval_id",
        )

        qe_ids = [row[0] for row in connection.execute(qe_ids_query).fetchall()]
        if not qe_ids:
            raise RuntimeError("No qe rows found. Seed dbo.qe before seeding dbo.initial_evaluations.")

        event_ids = [row[0] for row in connection.execute(event_ids_query).fetchall()]

        for _ in range(0, TOTAL_ROWS, BATCH_SIZE):
            rows = []
            for _ in range(BATCH_SIZE):
                parent_qe_id = choice(qe_ids)
                parent_event_id = choice(event_ids) if event_ids and random() > 0.45 else None
                rows.append(build_initial_evaluation(fake, parent_qe_id, parent_event_id))

            insert_rows(connection, insert_sql, rows)
    finally:
        connection.close()


if __name__ == "__main__":
    main()