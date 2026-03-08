"""Shared fixtures and helpers for AI assistant tests."""

import json
import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

BASE_URL = os.getenv("TEST_BASE_URL", "http://localhost:8000/api")
RESULTS_DIR = Path(__file__).parent / "results"


@dataclass
class SSEEvent:
    type: str
    content: str
    data: dict | None = None  # parsed JSON if applicable


@dataclass
class AssistantResponse:
    """Parsed response from the assistant API."""
    events: list[SSEEvent] = field(default_factory=list)
    facts: str | None = None
    interpretation: str | None = None
    hypothesis: str | None = None
    recommendations: str | None = None
    visuals: list[dict] = field(default_factory=list)
    config_proposal: dict | None = None
    clarification: dict | None = None
    tools_used: list[str] = field(default_factory=list)
    tool_count: int = 0
    thinking_steps: list[dict] = field(default_factory=list)
    error: str | None = None
    duration_ms: int = 0


def parse_sse(text: str) -> list[SSEEvent]:
    """Parse SSE text stream into events."""
    events = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("data: "):
            raw = line[6:]
            try:
                parsed = json.loads(raw)
                events.append(SSEEvent(
                    type=parsed.get("type", ""),
                    content=parsed.get("content", ""),
                    data=parsed,
                ))
            except json.JSONDecodeError:
                pass
    return events


def ask(question: str, context: dict | None = None, history: list | None = None) -> AssistantResponse:
    """Send a question to the assistant API and parse the full response."""
    ctx = context or {"page": "overview", "filters": {}, "period": {"year": 2025}}
    hist = history or []

    start = time.time()
    resp = httpx.post(
        f"{BASE_URL}/assistant",
        json={"question": question, "history": hist, "context": ctx},
        timeout=120,
    )
    duration_ms = int((time.time() - start) * 1000)

    events = parse_sse(resp.text)
    result = AssistantResponse(events=events, duration_ms=duration_ms)

    for ev in events:
        match ev.type:
            case "facts":
                result.facts = ev.content
            case "interpretation":
                result.interpretation = ev.content
            case "hypothesis":
                result.hypothesis = ev.content
            case "recommendations":
                result.recommendations = ev.content
            case "visual":
                try:
                    result.visuals.append(json.loads(ev.content))
                except json.JSONDecodeError:
                    result.visuals.append({"raw": ev.content})
            case "config_proposal":
                try:
                    result.config_proposal = json.loads(ev.content)
                except json.JSONDecodeError:
                    pass
            case "clarification":
                try:
                    result.clarification = json.loads(ev.content)
                except json.JSONDecodeError:
                    pass
            case "tool_use":
                result.tools_used.append(ev.content)
                result.tool_count += 1
            case "thinking":
                try:
                    result.thinking_steps.append(json.loads(ev.content))
                except json.JSONDecodeError:
                    pass
            case "error":
                result.error = ev.content

    return result


def get_ground_truth(endpoint: str, **params) -> dict:
    """Fetch ground truth data from a data API endpoint."""
    resp = httpx.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
    return resp.json()


def extract_numbers(text: str) -> list[float]:
    """Extract all dollar amounts from text (e.g. $50,195.8M -> 50195.8)."""
    matches = re.findall(r"\$?([\d,]+\.?\d*)\s*[MBK]", text or "")
    return [float(m.replace(",", "")) for m in matches]


def extract_percentages(text: str) -> list[float]:
    """Extract all percentage values from text."""
    matches = re.findall(r"([+-]?\d+\.?\d*)%", text or "")
    return [float(m) for m in matches]


def save_result(test_name: str, run_label: str, result: AssistantResponse, extra: dict | None = None):
    """Save a test result to JSON for later comparison."""
    RESULTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    data = {
        "test": test_name,
        "run_label": run_label,
        "timestamp": timestamp,
        "duration_ms": result.duration_ms,
        "facts": result.facts,
        "interpretation": result.interpretation,
        "hypothesis": result.hypothesis,
        "recommendations": result.recommendations,
        "visuals": result.visuals,
        "config_proposal": result.config_proposal,
        "clarification": result.clarification,
        "tools_used": result.tools_used,
        "tool_count": result.tool_count,
        "thinking_steps": result.thinking_steps,
        "error": result.error,
        **(extra or {}),
    }
    filepath = RESULTS_DIR / f"{test_name}_{run_label}_{timestamp}.json"
    filepath.write_text(json.dumps(data, indent=2, default=str))
    return filepath
