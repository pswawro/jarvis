"""LLM assistant endpoint — streams structured responses via SSE."""

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from anthropic import AnthropicBedrock

from models import AssistantRequest
import config
from assistant.prompt_builder import build_system_prompt, load_role
from assistant.tool_dispatch import TOOL_DISPATCH, TOOL_LABELS, UI_TOOLS
from assistant.parsing import sse, parse_sections

log = logging.getLogger(__name__)

router = APIRouter()

client = AnthropicBedrock(
    aws_region=config.LLM_AWS_REGION,
    aws_access_key=config.AWS_ACCESS_KEY_ID,
    aws_secret_key=config.AWS_SECRET_ACCESS_KEY,
    aws_session_token=config.AWS_SESSION_TOKEN,
)

# Load tool schemas once at import time
_TOOLS_PATH = Path(__file__).parent.parent / "assistant" / "tools.json"
TOOLS = json.loads(_TOOLS_PATH.read_text())


def _get_tools_for_role(role_id: str) -> list[dict]:
    """Filter tool list based on role permissions."""
    role = load_role(role_id)
    allowed = role.get("tools", ["*"])
    if "*" in allowed:
        return TOOLS
    return [t for t in TOOLS if t["name"] in allowed]


@router.post("/assistant")
async def assistant_chat(req: AssistantRequest):
    async def generate():
        # TODO: resolve role_id from authenticated user session
        role_id = req.context.get("role", "default")
        user_vars = req.context.get("user_vars", {})

        system = build_system_prompt(req.context, role_id=role_id, user_vars=user_vars)
        tools = _get_tools_for_role(role_id)

        # Build multi-turn conversation from history
        messages = []
        for h in req.history:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": req.question})

        log.info("Assistant request: question=%r history_len=%d context_page=%s role=%s",
                 req.question, len(req.history), req.context.get("page"), role_id)
        if config.LLM_DEBUG:
            log.info("[DEBUG] system_prompt=\n%s", system)
            log.info("[DEBUG] messages=%s", json.dumps(messages, default=str)[:2000])

        sent_done = False
        used_tools = False  # Track if tools were used in prior iterations
        try:
            for iteration in range(config.LLM_MAX_ITERATIONS):
                # Use heavy model from iteration 2+ (multi-step Mode 3 analysis)
                model = config.LLM_MODEL_ID_HEAVY if iteration >= 2 else config.LLM_MODEL_ID
                log.info("Iteration %d — calling Claude (%s)...", iteration, model)
                # Run blocking API call in thread so SSE events flush immediately
                response = await asyncio.to_thread(
                    client.messages.create,
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
                    log.info("Final response (%d chars)", len(text_content))
                    if config.LLM_DEBUG:
                        log.info("[DEBUG] final_text=\n%s", text_content[:2000])
                    # Guard: if text has no XML tags and looks like fabricated data,
                    # the LLM probably failed to use a tool — log and send minimal error.
                    # Skip this guard if tools were already used in prior iterations.
                    if not used_tools and \
                       not any(f"<{t}>" in text_content for t in ("facts", "interpretation", "hypothesis")) and \
                       text_content.count("B0.") + text_content.count("B1.") + text_content.count("$") > 5:
                        log.warning("LLM returned fabricated table data instead of using tools — suppressing")
                        yield sse("error", "I wasn't able to process that correctly. Could you rephrase your question?")
                        yield sse("done", "")
                        sent_done = True
                        break
                    sections = parse_sections(text_content)
                    for section_type, content in sections:
                        yield sse(section_type, content)
                    yield sse("done", "")
                    sent_done = True
                    break

                # Execute tool calls — yield SSE events immediately
                used_tools = True
                tool_results = []
                for tool_block in tool_uses:
                    name = tool_block.name
                    label = TOOL_LABELS.get(name, name)
                    log.info("Tool call: %s params=%r", name, tool_block.input)
                    if config.LLM_DEBUG:
                        log.info("[DEBUG] iter=%d tool=%s full_input=%s", iteration, name, json.dumps(tool_block.input, default=str))

                    if name in UI_TOOLS:
                        # UI-only tools — no "Querying..." status, just emit the visual/event
                        if name == "think":
                            yield sse("thinking", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Noted. Continue your investigation.",
                            })
                        elif name == "propose_config":
                            yield sse("config_proposal", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Configuration proposal shown to user. They can apply it with one tap.",
                            })
                        elif name == "clarify":
                            yield sse("clarification", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Clarification options shown to user. Wait for their response.",
                            })
                        else:
                            visual_spec = json.dumps({"tool": name, **tool_block.input})
                            log.info("Visual spec: %s", visual_spec[:200])
                            yield sse("visual", visual_spec)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": f"Rendered {name.replace('render_', '')} for the user.",
                            })
                    else:
                        # Data query tools — show progress
                        if name not in TOOL_DISPATCH:
                            log.warning("Unknown tool requested: %s", name)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": f"Unknown tool '{name}'. Available tools: {', '.join(TOOL_DISPATCH.keys())}",
                                "is_error": True,
                            })
                            continue
                        yield sse("tool_use", f"Querying {label}...")
                        params = {k: v for k, v in tool_block.input.items() if v is not None}
                        try:
                            result = await asyncio.to_thread(TOOL_DISPATCH[name], params)
                            log.info("Tool %s returned %d chars", name, len(result))
                            if config.LLM_DEBUG:
                                log.info("[DEBUG] tool=%s result_preview=%s", name, result[:500])
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": result,
                            })
                        except Exception as e:
                            log.error("Tool %s failed: %s", name, e, exc_info=True)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": f"Tool '{name}' encountered an error. Try a different approach or parameters.",
                                "is_error": True,
                            })
                        yield sse("tool_done", f"Queried {label}")

                # If clarify or propose_config was used, stop — these are standalone responses
                if any(tb.name in ("clarify", "propose_config") for tb in tool_uses):
                    yield sse("done", "")
                    sent_done = True
                    break

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except asyncio.CancelledError:
            log.info("Assistant SSE stream cancelled by client")
        except Exception as e:
            log.exception("Assistant error")
            yield sse("error", "An error occurred processing your request.")
        finally:
            if not sent_done:
                yield sse("done", "")

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
