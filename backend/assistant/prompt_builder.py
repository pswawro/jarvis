"""Assembles the system prompt from templates, roles, and runtime context."""

import json
import re as _re
from pathlib import Path

from assistant.semantic_model import get_semantic_model

def _sanitize_value(val: str, max_len: int = 500) -> str:
    cleaned = _re.sub(r'<[^>]+>', '', str(val))
    return cleaned[:max_len]


_DIR = Path(__file__).parent
_PROMPTS_DIR = _DIR / "prompts"
_ROLES_DIR = _DIR / "roles"

# Cache loaded files
_file_cache: dict[str, str] = {}
_role_cache: dict[str, dict] = {}


def _load_text(path: Path) -> str:
    key = str(path)
    if key not in _file_cache:
        _file_cache[key] = path.read_text()
    return _file_cache[key]


def load_role(role_id: str) -> dict:
    """Load a role config by ID. Falls back to 'default'.

    Validates role_id to prevent path traversal attacks.
    """
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', role_id):
        role_id = "default"
    if role_id not in _role_cache:
        path = _ROLES_DIR / f"{role_id}.json"
        if not path.exists():
            path = _ROLES_DIR / "default.json"
        _role_cache[role_id] = json.loads(path.read_text())
    return _role_cache[role_id]


def _build_core(role_context: str) -> str:
    """Build the shared core prompt (personality + semantic model)."""
    core = _load_text(_PROMPTS_DIR / "system_core.txt")
    return (core
            .replace("{{role_context}}", role_context)
            .replace("{{semantic_model}}", get_semantic_model()))


def _build_filters_block(filters: dict) -> str:
    active = []
    if filters.get("market_id"):
        active.append(f"Markets: {', '.join(filters['market_id'])}")
    if filters.get("ta"):
        active.append(f"TAs: {', '.join(filters['ta'])}")
    if active:
        return f"- Active filters: {'; '.join(active)}"
    return "- Filters: none (showing all)"


def _build_data_point_block(dp: dict) -> str:
    if not dp:
        return ""
    lines = ["", "## Data Point the User Clicked"]
    if dp.get("node_name"):
        lines.append(f"- Entity: {dp['node_name']} (ID: {dp.get('node_id', '?')})")
    if dp.get("parent_path"):
        lines.append(f"- Hierarchy: {' → '.join(dp['parent_path'])} → {dp.get('node_name', '')}")
    if dp.get("values"):
        vals = dp["values"]
        val_parts = []
        if vals.get("actual") is not None:
            val_parts.append(f"Actual: ${vals['actual']:.0f}M")
        if vals.get("budget") is not None:
            val_parts.append(f"Budget: ${vals['budget']:.0f}M")
        if vals.get("variance_pct") is not None:
            val_parts.append(f"vs Budget: {vals['variance_pct']:+.1f}%")
        if vals.get("py_variance_pct") is not None:
            val_parts.append(f"vs PY: {vals['py_variance_pct']:+.1f}%")
        if vals.get("market_share_pct") is not None:
            val_parts.append(f"Share: {vals['market_share_pct']:.1f}%")
        if val_parts:
            lines.append(f"- Metrics: {', '.join(val_parts)}")
    if dp.get("drill_path"):
        lines.append(f"- Drill path: {' → '.join(dp['drill_path'])}")
    if dp.get("series_name"):
        lines.append(f"- Chart series: {dp['series_name']}")
    if dp.get("x_label"):
        lines.append(f"- Time point: {dp['x_label']}")
    if dp.get("formatted_value"):
        lines.append(f"- Value: {dp['formatted_value']}")
    return "\n".join(lines)


def _build_dashboard_block(ctx: dict) -> str:
    """Build the dashboard state section."""
    dashboard = _load_text(_PROMPTS_DIR / "system_dashboard.txt")
    filters = ctx.get("filters", {})
    period = ctx.get("period", {})
    replacements = {
        "{{page}}": _sanitize_value(ctx.get("page", "overview")),
        "{{levels}}": " → ".join(ctx.get("levels", ["ta", "brand", "market"])),
        "{{year}}": _sanitize_value(str(period.get("year", 2025))),
        "{{quarter}}": _sanitize_value(str(period.get("quarter", "Full Year"))),
        "{{filters}}": _build_filters_block(filters),
        "{{data_point}}": _build_data_point_block(ctx.get("dataPoint", {})),
        "{{comparator}}": _sanitize_value(filters.get("comparator", "BUD")),
        "{{scale}}": _sanitize_value(filters.get("scale", "M")),
    }
    for placeholder, value in replacements.items():
        dashboard = dashboard.replace(placeholder, value)
    return dashboard


def build_insight_prompt(anomaly: dict) -> str:
    """Build system prompt for insight analysis.

    Uses: core (personality + semantic model) + anomaly context + analyze mode + insight extras.
    """
    entity = anomaly["entity"]
    parts = [entity["type"]]
    for k, v in entity.items():
        if k != "type":
            parts.append(f"{k}={v}")
    entity_desc = ", ".join(parts)

    core = _build_core("You are analyzing an automatically detected data anomaly. Investigate thoroughly using data tools.")
    mode_analyze = _load_text(_PROMPTS_DIR / "mode_analyze.txt")
    insight_extra = _load_text(_PROMPTS_DIR / "insight_analysis.txt")

    # Fill anomaly placeholders
    insight_section = (insight_extra
                       .replace("{{detection_type}}", anomaly["detection_type"])
                       .replace("{{entity_description}}", entity_desc)
                       .replace("{{raw_stats}}", json.dumps(anomaly.get("raw_stats", {}), indent=2))
                       .replace("{{data_domain}}", anomaly.get("data_domain", "")))

    prompt = core
    prompt += "\n\n" + insight_section
    prompt += "\n\n## Response Mode\n\n"
    prompt += mode_analyze

    return prompt


def build_system_prompt(ctx: dict, role_id: str = "default", user_vars: dict | None = None) -> str:
    """Build the full system prompt for assistant chat.

    Uses: core (personality + semantic model) + dashboard state + all 3 response modes.
    """
    role = load_role(role_id)
    uv = user_vars or {}

    # Resolve role prompt context with user variables
    role_context = role.get("prompt_context", "")
    for key, val in uv.items():
        role_context = role_context.replace(f"{{{{{key}}}}}", str(val))

    core = _build_core(role_context)
    dashboard = _build_dashboard_block(ctx)

    mode_clarify = _load_text(_PROMPTS_DIR / "mode_clarify.txt")
    mode_configure = _load_text(_PROMPTS_DIR / "mode_configure.txt")
    mode_analyze = _load_text(_PROMPTS_DIR / "mode_analyze.txt")
    mode_analyze_dashboard = _load_text(_PROMPTS_DIR / "mode_analyze_dashboard.txt")

    prompt = core
    prompt += "\n\n" + dashboard
    prompt += "\n\n## Response Modes — PICK EXACTLY ONE\n\n"
    prompt += "Every response must use exactly ONE of these three modes. Never mix them.\n\n"
    prompt += mode_clarify + "\n\n"
    prompt += mode_configure + "\n\n"
    prompt += mode_analyze + "\n\n"
    prompt += mode_analyze_dashboard

    return prompt
