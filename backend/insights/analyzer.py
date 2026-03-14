"""AI-powered insight analysis using Bedrock (same client as assistant)."""

import asyncio
import json
import logging
from pathlib import Path

from anthropic import AnthropicBedrock

import config
from assistant.tool_dispatch import TOOL_DISPATCH, UI_TOOLS
from assistant.prompt_builder import load_role

log = logging.getLogger(__name__)

_TOOLS_PATH = Path(__file__).parent.parent / "assistant" / "tools.json"
_PROMPT_PATH = Path(__file__).parent.parent / "assistant" / "prompts" / "insight_analysis.txt"


def _build_analysis_prompt(anomaly: dict) -> str:
    """Build the system prompt for analyzing a single anomaly."""
    template = _PROMPT_PATH.read_text()
    entity = anomaly["entity"]

    # Build entity description
    parts = [entity["type"]]
    for k, v in entity.items():
        if k != "type":
            parts.append(f"{k}={v}")
    entity_desc = ", ".join(parts)

    return (template
            .replace("{{detection_type}}", anomaly["detection_type"])
            .replace("{{entity_description}}", entity_desc)
            .replace("{{raw_stats}}", json.dumps(anomaly.get("raw_stats", {}), indent=2))
            .replace("{{data_domain}}", anomaly.get("data_domain", "")))


def _get_data_tools() -> list[dict]:
    """Load tool schemas, excluding UI-only tools."""
    tools = json.loads(_TOOLS_PATH.read_text())
    return [t for t in tools if t["name"] not in UI_TOOLS]


def analyze_insight(anomaly: dict) -> dict | None:
    """Run AI analysis on a single anomaly.

    Returns dict with 'explanation', 'revised_severity', 'push' or None on failure.
    """
    client = AnthropicBedrock(
        aws_region=config.LLM_AWS_REGION,
        aws_access_key=config.AWS_ACCESS_KEY_ID,
        aws_secret_key=config.AWS_SECRET_ACCESS_KEY,
        aws_session_token=config.AWS_SESSION_TOKEN,
    )

    system = _build_analysis_prompt(anomaly)
    tools = _get_data_tools()
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
                # Parse the JSON response
                try:
                    # Extract JSON from possible markdown code block
                    text = text_content.strip()
                    if "```json" in text:
                        text = text.split("```json")[1].split("```")[0].strip()
                    elif "```" in text:
                        text = text.split("```")[1].split("```")[0].strip()
                    result = json.loads(text)
                    # Validate required fields
                    if all(k in result for k in ("explanation", "revised_severity", "push")):
                        return result
                    log.warning("AI response missing required fields: %s", result)
                    return None
                except (json.JSONDecodeError, IndexError) as e:
                    log.warning("Failed to parse AI response: %s — text: %s", e, text_content[:200])
                    return None

            # Execute tool calls
            tool_results = []
            for tool_block in tool_uses:
                name = tool_block.name
                if name in TOOL_DISPATCH:
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
                        log.error("Insight tool %s failed: %s", name, e)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": f"Error: {type(e).__name__}",
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
