"""Application configuration from environment variables."""

import os

# LLM Assistant
LLM_AWS_REGION = os.getenv("LLM_AWS_REGION", "eu-west-1")
LLM_MODEL_ID = os.getenv("LLM_MODEL_ID", "eu.anthropic.claude-sonnet-4-6")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_MAX_ITERATIONS = int(os.getenv("LLM_MAX_ITERATIONS", "10"))

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
