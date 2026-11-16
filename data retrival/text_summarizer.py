from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

try:
    from config import create_bedrock_client, get_bedrock_client, get_config
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    from config import create_bedrock_client, get_bedrock_client, get_config


DEFAULT_NOVA_MODEL_ID = "amazon.nova-micro-v1:0"

PROMPT = """
You are a business communication assistant.
Summarize the provided text in a precise, formal business style.
Rules:
- Keep the summary concise and factual.
- Use clear professional language.
- Do not add information that is not present in the source text.
- Output plain text only.
""".strip()


def _resolve_bedrock_client(aws_credentials: dict[str, str] | None):
    creds = aws_credentials or {}
    access_key = (creds.get("AWS_ACCESS_KEY_ID") or "").strip()
    secret_key = (creds.get("AWS_SECRET_ACCESS_KEY") or "").strip()
    if access_key and secret_key:
        region = (creds.get("AWS_REGION") or "").strip() or get_config().aws_region
        return create_bedrock_client(region, access_key, secret_key)
    return get_bedrock_client()


def summarize_text_business(
    text: str,
    model_id: str | None = None,
    aws_credentials: dict[str, str] | None = None,
) -> str:
    """Summarize user text using AWS Bedrock Nova model in business format.

    Uses the given browser-provided AWS credentials when both key values are set,
    otherwise falls back to the server environment configuration.
    """
    if not text or not text.strip():
        raise ValueError("text must not be empty")

    cfg = get_config()
    selected_model = model_id or cfg.bedrock_model_id or DEFAULT_NOVA_MODEL_ID
    if not selected_model.startswith("amazon.nova"):
        selected_model = DEFAULT_NOVA_MODEL_ID

    response: dict[str, Any] = _resolve_bedrock_client(aws_credentials).converse(
        modelId=selected_model,
        system=[{"text": PROMPT}],
        messages=[{"role": "user", "content": [{"text": text.strip()}]}],
        inferenceConfig={"temperature": 0, "maxTokens": 500},
    )

    summary = response["output"]["message"]["content"][0]["text"].strip()
    if summary.startswith("```"):
        summary = summary.replace("```text", "").replace("```", "").strip()
    return summary


def _main() -> None:
    parser = argparse.ArgumentParser(description="Summarize text using AWS Bedrock Nova model")
    parser.add_argument("text", help="Input text to summarize")
    parser.add_argument("--model-id", default=None, help="Optional Bedrock model id override")
    args = parser.parse_args()

    print(summarize_text_business(args.text, model_id=args.model_id))


if __name__ == "__main__":
    _main()
