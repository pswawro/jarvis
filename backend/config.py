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
LLM_MODEL_ID_HEAVY = os.getenv("LLM_MODEL_ID_HEAVY", "eu.anthropic.claude-sonnet-4-6")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_MAX_ITERATIONS = int(os.getenv("LLM_MAX_ITERATIONS", "10"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_DEBUG = os.getenv("LLM_DEBUG", "").lower() in ("1", "true", "yes")

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))

# Push Notifications (VAPID)
VAPID_PUBLIC_KEY = _optional("VAPID_PUBLIC_KEY")
VAPID_PRIVATE_KEY = _optional("VAPID_PRIVATE_KEY")
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "admin@example.com")

# Insights
INSIGHT_SENSITIVITY = _optional("INSIGHT_SENSITIVITY")
