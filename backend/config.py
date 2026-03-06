"""Application configuration from environment variables."""

import os


def _optional(key: str) -> str | None:
    """Return the env var value, or None if it is absent or empty.

    Passing None for AWS credentials lets boto3 fall back on its default
    credential chain (IAM role, ~/.aws/credentials, runtime env vars, etc.).
    """
    value = os.getenv(key, "")
    return value if value else None


# AWS Credentials (explicit values take priority; empty → default credential chain)
AWS_ACCESS_KEY_ID = _optional("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = _optional("AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = _optional("AWS_SESSION_TOKEN")

# LLM Assistant
LLM_AWS_REGION = os.getenv("LLM_AWS_REGION", "eu-west-1")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "eu.anthropic.claude-sonnet-4-6")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_MAX_ITERATIONS = int(os.getenv("LLM_MAX_ITERATIONS", "10"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
