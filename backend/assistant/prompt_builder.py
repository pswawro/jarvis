"""Assembles the system prompt from templates, roles, and runtime context."""

import json
from pathlib import Path

from assistant.semantic_model import get_semantic_model

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
    """Load a role config by ID. Falls back to 'default'."""
    if role_id not in _role_cache:
        path = _ROLES_DIR / f"{role_id}.json"
        if not path.exists():
            path = _ROLES_DIR / "default.json"
        _role_cache[role_id] = json.loads(path.read_text())
    return _role_cache[role_id]


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


def build_system_prompt(ctx: dict, role_id: str = "default", user_vars: dict | None = None) -> str:
    """Build the full system prompt for a request.

    Args:
        ctx: Dashboard context (page, filters, period, dataPoint, etc.)
        role_id: Role ID to load from roles/ directory.
        user_vars: Extra template variables (e.g. {"market": "US"} for market_lead).
    """
    role = load_role(role_id)
    uv = user_vars or {}

    # Load templates
    base = _load_text(_PROMPTS_DIR / "system_base.txt")
    mode_clarify = _load_text(_PROMPTS_DIR / "mode_clarify.txt")
    mode_configure = _load_text(_PROMPTS_DIR / "mode_configure.txt")
    mode_analyze = _load_text(_PROMPTS_DIR / "mode_analyze.txt")

    # Resolve role prompt context with user variables
    role_context = role.get("prompt_context", "")
    for key, val in uv.items():
        role_context = role_context.replace(f"{{{{{key}}}}}", str(val))

    filters = ctx.get("filters", {})
    period = ctx.get("period", {})

    # Fill base template
    prompt = base
    replacements = {
        "{{role_context}}": role_context,
        "{{semantic_model}}": get_semantic_model(),
        "{{page}}": ctx.get("page", "overview"),
        "{{levels}}": " → ".join(ctx.get("levels", ["ta", "brand", "market"])),
        "{{year}}": str(period.get("year", 2025)),
        "{{quarter}}": str(period.get("quarter", "Full Year")),
        "{{filters}}": _build_filters_block(filters),
        "{{data_point}}": _build_data_point_block(ctx.get("dataPoint", {})),
        "{{comparator}}": filters.get("comparator", "BUD"),
        "{{scale}}": filters.get("scale", "M"),
    }
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    # Append response modes
    prompt += "\n\n## Response Modes — PICK EXACTLY ONE\n\n"
    prompt += "Every response must use exactly ONE of these three modes. Never mix them.\n\n"
    prompt += mode_clarify + "\n\n"
    prompt += mode_configure + "\n\n"
    prompt += mode_analyze

    return prompt
