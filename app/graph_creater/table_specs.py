from __future__ import annotations

import yaml
from pathlib import Path
from typing import Any

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _load_all_specs() -> dict[str, dict[str, Any]]:
    config_path = _CONFIG_DIR / "table_specs.yaml"
    if not config_path.exists():
        raise FileNotFoundError(f"Table spec config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    specs = payload.get("tables", {})
    if not isinstance(specs, dict):
        raise ValueError("Expected 'tables' mapping in table_specs.yaml")
    return specs


_TABLE_SPECS: dict[str, dict[str, Any]] | None = None


def load_table_spec(table_name: str) -> dict[str, Any]:
    global _TABLE_SPECS
    if _TABLE_SPECS is None:
        _TABLE_SPECS = _load_all_specs()

    spec = _TABLE_SPECS.get(table_name)
    if spec is None:
        raise KeyError(f"No table spec defined for {table_name}")
    return spec
