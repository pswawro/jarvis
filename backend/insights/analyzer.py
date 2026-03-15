"""AI-powered insight analysis using Bedrock (same client as assistant)."""

import json
import logging
import re
from pathlib import Path

from anthropic import AnthropicBedrock

import config
from assistant.prompt_builder import build_insight_prompt
from assistant.parsing import parse_sections
from assistant.tool_dispatch import TOOL_DISPATCH

log = logging.getLogger(__name__)

_TOOLS_PATH = Path(__file__).parent.parent / "assistant" / "tools.json"

# Tools excluded from insight analysis (UI-rendering only, no data value)
_INSIGHT_EXCLUDED_TOOLS = {"render_table", "render_chart", "propose_config", "clarify", "decompose_variance"}


def _get_analysis_tools() -> list[dict]:
    """Load tool schemas — data tools plus think (for investigation pattern)."""
    tools = json.loads(_TOOLS_PATH.read_text())
    return [t for t in tools if t["name"] not in _INSIGHT_EXCLUDED_TOOLS]


def _parse_analysis_response(text: str) -> dict | None:
    """Parse XML-tagged sections from the analysis response.

    Returns dict with 'sections' (list of (tag, content) tuples),
    'revised_severity', and 'push', or None on failure.
    """
    sections = parse_sections(text, extra_tags=("recommendations", "insight_severity", "insight_push"))

    # Separate insight-specific tags from content sections
    content_sections = []
    revised_severity = "informational"
    push = False
    for tag, content in sections:
        if tag == "insight_severity":
            revised_severity = content.strip().lower()
        elif tag == "insight_push":
            push = content.strip().lower() == "true"
        else:
            content_sections.append((tag, content))

    # Validate severity
    if revised_severity not in ("critical", "notable", "informational"):
        revised_severity = "informational"

    # Build explanation from sections for backward compatibility
    explanation = " ".join(content for _, content in content_sections)

    return {
        "explanation": explanation,
        "sections": content_sections,
        "revised_severity": revised_severity,
        "push": push,
    }


import threading

_client = None
_client_lock = threading.Lock()


def _get_client() -> AnthropicBedrock:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = AnthropicBedrock(
                    aws_region=config.LLM_AWS_REGION,
                    aws_access_key=config.AWS_ACCESS_KEY_ID,
                    aws_secret_key=config.AWS_SECRET_ACCESS_KEY,
                    aws_session_token=config.AWS_SESSION_TOKEN,
                )
    return _client


def analyze_insight(anomaly: dict) -> dict | None:
    """Run AI analysis on a single anomaly.

    Returns dict with 'explanation', 'sections', 'revised_severity', 'push'
    or None on failure.
    """
    client = _get_client()

    system = build_insight_prompt(anomaly)
    tools = _get_analysis_tools()
    messages = [{"role": "user", "content": "Analyze this anomaly and provide your assessment."}]

    try:
        for iteration in range(config.LLM_MAX_ITERATIONS):
            model = config.LLM_MODEL_ID_HEAVY if iteration >= 2 else config.LLM_MODEL_ID
            log.info("Insight analysis iter %d for %s (%s)",
                     iteration, anomaly.get("fingerprint", "?"), model)

            response = client.messages.create(
                model=model,
                max_tokens=config.LLM_MAX_TOKENS,
                temperature=config.LLM_TEMPERATURE,
                system=system,
                tools=tools,
                messages=messages,
            )

            tool_uses = []
            text_content = ""

            for block in response.content:
                if block.type == "tool_use":
                    tool_uses.append(block)
                elif block.type == "text":
                    text_content += block.text

            if not tool_uses:
                result = _parse_analysis_response(text_content)
                if result:
                    return result
                log.warning("Failed to parse analysis response: %s", text_content[:200])
                return None

            # Execute tool calls
            tool_results = []
            for tool_block in tool_uses:
                name = tool_block.name

                # Handle think tool inline — just log and acknowledge
                if name == "think":
                    step = tool_block.input.get("step", "")
                    content = tool_block.input.get("content", "")
                    log.info("Insight think [%s]: %s", step, content[:100])
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": "ok",
                    })
                elif name in TOOL_DISPATCH:
                    params = {k: v for k, v in tool_block.input.items() if v is not None}
                    try:
                        result = TOOL_DISPATCH[name](params)
                        log.info("Insight tool %s returned %d chars", name, len(result))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": result,
                        })
                    except Exception as e:
                        log.error("Insight tool %s failed: %s", name, e, exc_info=True)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": f"Tool '{name}' encountered an error. Try a different approach.",
                            "is_error": True,
                        })
                else:
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_block.id,
                        "content": "Tool not available for insight analysis.",
                        "is_error": True,
                    })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

    except Exception as e:
        log.exception("AI analysis failed for anomaly: %s", anomaly.get("fingerprint", "?"))
        return None

    log.warning("AI analysis hit max iterations for %s", anomaly.get("fingerprint", "?"))
    return None
