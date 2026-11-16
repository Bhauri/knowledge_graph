from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import boto3
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer


class AppConfig(BaseModel):
    aws_region: str = Field(default="us-east-1")
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    bedrock_model_id: str = Field(default="amazon.nova-micro-v1:0")

    embedding_model_name: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")


def load_environment() -> None:
    project_root = Path(__file__).resolve().parent
    env_path = project_root / "virtual_env" / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        return
    load_dotenv()


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    load_environment()
    return AppConfig(
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_session_token=os.getenv("AWS_SESSION_TOKEN"),
        bedrock_model_id=os.getenv("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0"),
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
    )


@lru_cache(maxsize=1)
def get_bedrock_client():
    cfg = get_config()
    return boto3.client(
        "bedrock-runtime",
        region_name=cfg.aws_region,
        aws_access_key_id=cfg.aws_access_key_id,
        aws_secret_access_key=cfg.aws_secret_access_key,
        aws_session_token=cfg.aws_session_token,
    )


def create_bedrock_client(region: str, access_key_id: str, secret_access_key: str):
    return boto3.client(
        "bedrock-runtime",
        region_name=region,
        aws_access_key_id=access_key_id,
        aws_secret_access_key=secret_access_key,
    )


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    cfg = get_config()
    return SentenceTransformer(cfg.embedding_model_name)
