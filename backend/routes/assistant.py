"""LLM assistant endpoint — streams structured responses via SSE."""

import asyncio
import json
import logging
import re
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from anthropic import AnthropicBedrock
from models import AssistantRequest
import config

log = logging.getLogger(__name__)

import data_loader
from routes.kpi import get_kpi
from routes.brand import get_brand_view
from routes.region import get_region_view
from routes.unit import get_unit_view
from routes.market import get_market_view
from routes.chart import get_brand_chart, get_region_chart, get_unit_chart, get_market_chart

router = APIRouter()

client = AnthropicBedrock(aws_region=config.LLM_AWS_REGION)

# ---------------------------------------------------------------------------
# Semantic model — built once at startup from dimension tables
# ---------------------------------------------------------------------------

_SEMANTIC_MODEL: str = ""


def _build_semantic_model() -> str:
    """Build a rich description of the data domain from dimension tables."""
    prods = data_loader.products
    geos = data_loader.geographies
    orgs = data_loader.organization
    cats = sorted(data_loader.commercial["category"].unique())

    # Group brands by TA
    ta_brands = {}
    for _, row in prods.iterrows():
        ta = row["therapeutic_area"]
        if ta not in ta_brands:
            ta_brands[ta] = []
        ta_brands[ta].append({
            "id": row["brand_id"],
            "name": row["brand_name"],
            "indication": row["indication"],
        })

    # Build org structure
    unit_subs = {}
    for _, row in orgs.iterrows():
        unit = row["unit"]
        if unit not in unit_subs:
            unit_subs[unit] = []
        unit_subs[unit].append({
            "id": row["sub_unit_id"],
            "name": row["sub_unit_name"],
        })

    lines = ["## AstraZeneca Data Model", ""]

    # Portfolio
    lines.append("### Drug Portfolio (20 brands)")
    for ta, brands in ta_brands.items():
        brand_list = ", ".join(
            f"{b['name']} ({b['id']}) — {b['indication']}" for b in brands
        )
        lines.append(f"**{ta}**: {brand_list}")
    lines.append("")

    # Geographies
    lines.append("### Markets")
    for _, row in geos.iterrows():
        lines.append(f"- {row['market_name']} ({row['market_id']}) — Region: {row['region']}")
    lines.append("")

    # Org structure
    lines.append("### Organization (expense units)")
    for unit, subs in unit_subs.items():
        sub_list = ", ".join(f"{s['name']} ({s['id']})" for s in subs)
        lines.append(f"**{unit}**: {sub_list}")
    lines.append("")

    # Market categories
    lines.append("### Competitive Market Categories")
    lines.append(", ".join(cats))
    lines.append("")

    # Data availability
    lines.append("### Data Availability")
    lines.append("- Years: 2023, 2024, 2025")
    lines.append("- Granularity: monthly (Jan–Dec), aggregatable by quarter (Q1–Q4) or full year")
    lines.append("- Financial metrics: revenue, cost_of_sales, gross_profit, budget, forecast, prior_year")
    lines.append("- Expense metrics: personnel_costs, external_costs, other_costs, total_operating_expenses")
    lines.append("- Market metrics: total_market_size_usd_m, market_growth_pct, az_market_share_pct, az_revenue_usd_m")
    lines.append("")

    # Key relationships
    lines.append("### Key Relationships")
    lines.append("- Brand → Therapeutic Area (each brand belongs to exactly one TA)")
    lines.append("- Revenue is reported per brand × market (US, CN) × month")
    lines.append("- Expenses are reported per sub-unit × month (not by brand or market)")
    lines.append("- Market share is reported per brand × market × category × month")
    lines.append("- Targets (budget/forecast) exist for both revenue and expenses")

    return "\n".join(lines)


def get_semantic_model() -> str:
    global _SEMANTIC_MODEL
    if not _SEMANTIC_MODEL:
        _SEMANTIC_MODEL = _build_semantic_model()
    return _SEMANTIC_MODEL


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "query_kpi",
        "description": "Get top-level KPI cards: Total Revenue, Gross Profit, Total OpEx, Operating Margin. Each card shows the value plus vs Budget and vs Prior Year variance. Good starting point for understanding overall company performance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "description": "Fiscal year: 2023, 2024, or 2025", "default": 2025},
                "quarter": {"type": "string", "description": "Quarter: Q1, Q2, Q3, Q4. Omit for full year.", "nullable": True},
                "market_id": {"type": "string", "description": "Filter by market: 'US', 'CN', or 'US,CN'. Omit for all.", "nullable": True},
                "ta": {"type": "string", "description": "Filter by therapeutic area: e.g. 'Oncology', 'CVRM,R&I'. Omit for all.", "nullable": True},
            },
        },
    },
    {
        "name": "query_brand",
        "description": "Get revenue breakdown by brand. Returns a hierarchical tree: Total AZ → Therapeutic Area → Brand → Market. Each node has: actual revenue ($M), budget, variance_pct (vs budget), prior_year, py_variance_pct (vs PY), 12-month sparkline, forecast, market_share_pct. Use this to compare brands, find top/bottom performers, or understand TA composition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "description": "Filter to specific TA(s). Use exact names: Oncology, CVRM, R&I, Rare Disease, V&I", "nullable": True},
            },
        },
    },
    {
        "name": "query_brand_chart",
        "description": "Get cumulative monthly revenue trend by brand. Returns time series with x_labels (months) and series (one per TA or brand). Use drill param with a node ID to see children of a specific TA or brand. Good for tracking YTD trajectory vs budget/PY.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "nullable": True},
                "drill": {"type": "string", "description": "Node ID to drill into (e.g. 'Oncology', 'TAGRISSO')", "nullable": True},
            },
        },
    },
    {
        "name": "query_region",
        "description": "Get revenue breakdown by geography. Hierarchy: Total AZ → Region (North America, International) → Market (US, CN) → Brand. Use this to compare regional performance or see which brands drive a specific market.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "query_region_chart",
        "description": "Get cumulative monthly revenue trend by region. Use drill to see brands within a region/market.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "nullable": True},
                "drill": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "query_unit",
        "description": "Get operating expenses by organizational unit. Hierarchy: Total AZ → Unit (R&D, Commercial, Operations, Finance, Enabling) → Sub-unit. Each node has: actual spend ($M), budget, variance_pct, personnel_costs, external_costs, other_costs. Use this for cost analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "query_unit_chart",
        "description": "Get cumulative monthly expense trend by unit. Use drill to see sub-units.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "drill": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "query_market",
        "description": "Get competitive market share data. Hierarchy: Total AZ → Drug Category (e.g. 'EGFR TKI inhibitors') → Brand. Metrics: AZ revenue, market_share_pct, variance_pct (share delta vs PY in pp), py_variance_pct (market growth %), 12-month share sparkline. Use this to assess competitive positioning.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "query_market_chart",
        "description": "Get monthly market share % trend (not cumulative). Shows how AZ's share in each category evolves month-over-month. Use drill to see individual brand share trends within a category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "year": {"type": "integer", "default": 2025},
                "quarter": {"type": "string", "nullable": True},
                "market_id": {"type": "string", "nullable": True},
                "ta": {"type": "string", "nullable": True},
                "drill": {"type": "string", "nullable": True},
            },
        },
    },
    {
        "name": "render_table",
        "description": "Render a summary table for the user. The user sees a small clickable icon; tapping it opens the full table. Use for comparisons, rankings, or structured breakdowns.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "headers": {"type": "array", "items": {"type": "string"}},
                "rows": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
            },
            "required": ["title", "headers", "rows"],
        },
    },
    {
        "name": "render_chart",
        "description": "Render a chart for the user. The user sees a small clickable icon; tapping it opens the full chart. Use for trends, distributions, or visual comparisons.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "type": {"type": "string", "enum": ["bar", "line"]},
                "labels": {"type": "array", "items": {"type": "string"}},
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "values": {"type": "array", "items": {"type": "number"}},
                            "color": {"type": "string"},
                        },
                        "required": ["name", "values"],
                    },
                },
            },
            "required": ["title", "type", "labels", "datasets"],
        },
    },
]

# Map tool names to function calls
TOOL_DISPATCH = {
    "query_kpi": lambda p: get_kpi(**p).model_dump_json(),
    "query_brand": lambda p: get_brand_view(**p).model_dump_json(),
    "query_brand_chart": lambda p: get_brand_chart(**p).model_dump_json(),
    "query_region": lambda p: get_region_view(**p).model_dump_json(),
    "query_region_chart": lambda p: get_region_chart(**p).model_dump_json(),
    "query_unit": lambda p: get_unit_view(**p).model_dump_json(),
    "query_unit_chart": lambda p: get_unit_chart(**p).model_dump_json(),
    "query_market": lambda p: get_market_view(**p).model_dump_json(),
    "query_market_chart": lambda p: get_market_chart(**p).model_dump_json(),
}

TOOL_LABELS = {
    "query_kpi": "KPI summary",
    "query_brand": "brand revenue data",
    "query_brand_chart": "brand trend data",
    "query_region": "region revenue data",
    "query_region_chart": "region trend data",
    "query_unit": "expense data by unit",
    "query_unit_chart": "expense trend data",
    "query_market": "market share data",
    "query_market_chart": "market share trends",
    "render_table": "table",
    "render_chart": "chart",
}


def _sse(event_type: str, content: str) -> str:
    return f"data: {json.dumps({'type': event_type, 'content': content})}\n\n"


def _build_system_prompt(ctx: dict) -> str:
    semantic = get_semantic_model()

    parts = [
        "You are Jarvis, an AI analytics assistant embedded in AstraZeneca's financial dashboard.",
        "You help executives and analysts understand revenue performance, operating expenses, and competitive market positioning.",
        "",
        "## Your Personality",
        "- Concise and precise — lead with numbers, not filler",
        "- Use $XB or $XM format for currency, Xpp for share point changes, X% for percentages",
        "- When a number is negative, say 'miss' or 'below'; when positive, say 'beat' or 'above'",
        "- Reference specific brands, TAs, and markets by name — never be vague",
        "",
        semantic,
        "",
        "## Current Dashboard State",
        f"- Active view: {ctx.get('view', 'Brand')}",
        f"- Period: year={ctx.get('period', {}).get('year', 2025)}, quarter={ctx.get('period', {}).get('quarter', 'Full Year')}",
    ]

    filters = ctx.get("filters", {})
    active_filters = []
    if filters.get("market_id"):
        active_filters.append(f"Markets: {', '.join(filters['market_id'])}")
    if filters.get("ta"):
        active_filters.append(f"TAs: {', '.join(filters['ta'])}")
    if active_filters:
        parts.append(f"- Active filters: {'; '.join(active_filters)}")
    else:
        parts.append("- Filters: none (showing all)")

    dp = ctx.get("dataPoint")
    if dp:
        parts.append("")
        parts.append("## Data Point the User Clicked")
        if dp.get("node_name"):
            parts.append(f"- Entity: {dp['node_name']} (ID: {dp.get('node_id', '?')})")
        if dp.get("parent_path"):
            parts.append(f"- Hierarchy: {' → '.join(dp['parent_path'])} → {dp.get('node_name', '')}")
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
                parts.append(f"- Metrics: {', '.join(val_parts)}")
        if dp.get("drill_path"):
            parts.append(f"- Drill path: {' → '.join(dp['drill_path'])}")
        if dp.get("series_name"):
            parts.append(f"- Chart series: {dp['series_name']}")
        if dp.get("x_label"):
            parts.append(f"- Time point: {dp['x_label']}")
        if dp.get("formatted_value"):
            parts.append(f"- Value: {dp['formatted_value']}")

    parts.extend([
        "",
        "## Response Format",
        "Use XML tags to structure your answer. Include only the sections that are relevant to the question:",
        "- <facts>...</facts> — Objective data points. Always include when you queried data. Be specific with numbers.",
        "- <interpretation>...</interpretation> — Your analysis: what patterns mean, what's driving the numbers, comparisons.",
        "- <hypothesis>...</hypothesis> — Forward-looking: risks, opportunities, what to watch, suggested actions.",
        "",
        "Guidelines:",
        "- Be concise. Prefer bullet points over paragraphs. No filler or preamble.",
        "- You do NOT need all three sections. A simple factual question may only need <facts>. An analytical question may need <facts> and <interpretation>. Include <hypothesis> only when you have a genuine forward-looking insight.",
        "- Keep each section to 2-4 bullet points. Be dense with information, not verbose.",
        "- Use render_table when comparing 3+ items side-by-side. Use render_chart for trends or distributions.",
        "- Always query data first — never fabricate or estimate numbers.",
        "- When the user asks about a specific brand/TA, use the right filters to get precise data rather than fetching everything.",
        "- Match the period and filters from the dashboard context unless the user asks for something different.",
    ])

    return "\n".join(parts)


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Parse XML-tagged sections from model output."""
    sections = []
    for tag in ("facts", "interpretation", "hypothesis"):
        pattern = f"<{tag}>(.*?)</{tag}>"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            sections.append((tag, match.group(1).strip()))

    # If no XML tags found, treat entire text as facts
    if not sections and text.strip():
        sections.append(("facts", text.strip()))

    return sections


@router.post("/assistant")
async def assistant_chat(req: AssistantRequest):
    async def generate():
        system = _build_system_prompt(req.context)
        messages = [{"role": "user", "content": req.question}]
        log.info("Assistant request: question=%r context_view=%s", req.question, req.context.get("view"))

        try:
            for iteration in range(config.LLM_MAX_ITERATIONS):
                log.info("Iteration %d — calling Claude...", iteration)
                # Run blocking API call in thread so SSE events flush immediately
                response = await asyncio.to_thread(
                    client.messages.create,
                    model=config.LLM_MODEL_ID,
                    max_tokens=config.LLM_MAX_TOKENS,
                    system=system,
                    tools=TOOLS,
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
                    sections = _parse_sections(text_content)
                    for section_type, content in sections:
                        yield _sse(section_type, content)
                    yield _sse("done", "")
                    break

                # Execute tool calls — yield SSE events immediately
                tool_results = []
                for tool_block in tool_uses:
                    name = tool_block.name
                    label = TOOL_LABELS.get(name, name)
                    log.info("Tool call: %s params=%r", name, tool_block.input)
                    yield _sse("tool_use", f"Querying {label}...")

                    if name in ("render_table", "render_chart"):
                        visual_spec = json.dumps({"tool": name, **tool_block.input})
                        log.info("Visual spec: %s", visual_spec[:200])
                        yield _sse("visual", visual_spec)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tool_block.id,
                            "content": f"Rendered {name.replace('render_', '')} for the user.",
                        })
                    else:
                        params = {k: v for k, v in tool_block.input.items() if v is not None}
                        try:
                            result = TOOL_DISPATCH[name](params)
                            log.info("Tool %s returned %d chars", name, len(result))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": result,
                            })
                        except Exception as e:
                            log.error("Tool %s failed: %s", name, e)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": f"Error: {str(e)}",
                                "is_error": True,
                            })

                    yield _sse("tool_done", f"Queried {label}")

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except Exception as e:
            log.exception("Assistant error")
            yield _sse("error", str(e))

    return StreamingResponse(generate(), media_type="text/event-stream")
