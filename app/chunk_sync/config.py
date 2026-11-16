from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True, slots=True)
class ChunkSyncConfig:
    """Application settings for chunk + embedding synchronization."""

    embedding_model_name: str
    embedding_model_short_name: str
    embedding_dimensions: int
    embedding_version: int
    source_batch_size: int
    upsert_batch_size: int
    log_level: str



def load_environment() -> None:
    """Load environment variables from virtual_env/.env when available."""

    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / "virtual_env" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return
    load_dotenv()



def get_config() -> ChunkSyncConfig:
    """Create immutable config from environment variables."""

    load_environment()

    return ChunkSyncConfig(
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
        embedding_model_short_name=os.getenv("EMBEDDING_MODEL_SHORT_NAME", "all-MiniLM-L6-v2"),
        embedding_dimensions=int(os.getenv("EMBEDDING_DIMENSIONS", "384")),
        embedding_version=int(os.getenv("EMBEDDING_MODEL_VERSION", "1")),
        source_batch_size=int(os.getenv("SOURCE_BATCH_SIZE", "2000")),
        upsert_batch_size=int(os.getenv("UPSERT_BATCH_SIZE", "1000")),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
