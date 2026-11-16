from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPTS = [
    "seed_quality_events.py",
    "seed_pspi.py",
    "seed_qe_events.py",
    "seed_initial_evaluations.py",
    "seed_capa.py",
    "seed_containment_actions.py",
    "seed_batch_containment_details.py",
]


def main() -> None:
    current_dir = Path(__file__).resolve().parent

    for script_name in SCRIPTS:
        script_path = current_dir / script_name
        print(f"Running {script_name}...")
        subprocess.run([sys.executable, str(script_path)], check=True)

    print("All database seeders completed successfully.")


if __name__ == "__main__":
    main()