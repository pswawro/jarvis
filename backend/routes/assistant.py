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

client = AnthropicBedrock(
    aws_region=config.LLM_AWS_REGION,
    aws_access_key=config.AWS_ACCESS_KEY_ID,
    aws_secret_key=config.AWS_SECRET_ACCESS_KEY,
    aws_session_token=config.AWS_SESSION_TOKEN,
)

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
    lines.append("- Revenue metrics: gross_product_sales, returns, rebates_negotiable, rebates_non_negotiable, early_payment_discount, patient_programs, tax_and_clawbacks, revenue (net), cost_of_sales, gross_profit")
    lines.append("- Targets: budget_amount, forecast_amount, mtp_amount (Mid-Term Plan), rbu2_amount (Reforecast)")
    lines.append("- Expense metrics: personnel_costs, external_costs, other_costs, total_operating_expenses")
    lines.append("- Headcount: fte_count, headcount per sub-unit per month")
    lines.append("- Market metrics: total_market_size_usd_m, market_growth_pct, az_market_share_pct, az_revenue_usd_m")
    lines.append("- Comparators: BUD (Budget), MTP (Mid-Term Plan), RBU2 (Reforecast), PYACT (Prior Year)")
    lines.append("")
    lines.append("### Comparator Guide")
    lines.append("- **BUD (Budget)**: Annual plan set before the fiscal year starts. Primary performance benchmark — 'are we on plan?'")
    lines.append("- **MTP (Mid-Term Plan)**: 3-5 year strategic plan updated annually. Shows alignment with long-term strategy — 'are we on track strategically?'")
    lines.append("- **RBU2 (Reforecast)**: Mid-year updated forecast. H1 is close to actuals, H2 diverges. Best for in-year tracking — 'are we hitting the latest forecast?'")
    lines.append("- **PYACT (Prior Year)**: Last year's actual results. Shows year-over-year growth — 'are we growing?'")
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
        "name": "query_config",
        "description": "Get the application configuration: available comparators (BUD/MTP/RBU2/PYACT), period types (MTD/QTD/YTD/FY), accounts (gross-to-net breakdown), scales ($M/$K/$B), column groups, and default settings. Use this to understand what dimensions and options are available in the dashboard.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "propose_config",
        "description": (
            "Propose a dashboard configuration change. Use when the user asks to 'show', 'compare', "
            "'switch to', 'focus on', or 'filter to' a particular view, comparator, market, or TA. "
            "The proposal renders as an interactive card with an Apply button. "
            "Only include fields that differ from the current dashboard state. "
            "Always include a plain-English summary explaining what the config does and why."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Plain-English explanation of what this config does (1-2 sentences).",
                },
                "comparator": {
                    "type": "string",
                    "enum": ["BUD", "MTP", "RBU2", "PYACT"],
                    "description": "BUD=Budget, MTP=Mid-Term Plan, RBU2=Reforecast, PYACT=Prior Year.",
                },
                "year": {"type": "integer", "description": "Fiscal year: 2023, 2024, or 2025"},
                "quarter": {"type": "string", "enum": ["Q1", "Q2", "Q3", "Q4"]},
                "market_id": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Markets: ['US'], ['CN'], or ['US','CN']. Omit to keep current.",
                },
                "ta": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Therapeutic areas: e.g. ['Oncology', 'CVRM']. Omit to keep current.",
                },
                "page": {
                    "type": "string",
                    "enum": ["overview", "landing", "phased"],
                    "description": (
                        "Dashboard page to switch to. "
                        "overview = tree table with KPI metrics (best for drill-down analysis). "
                        "landing = actuals + forecast timeline with cumulative chart (best for YTD tracking). "
                        "phased = scenario comparison table showing ACT vs BUD/MTP/RBU2/PY by period (best for plan variance). "
                        "Omit to keep current."
                    ),
                },
                "scenario_preset": {
                    "type": "string",
                    "enum": ["all", "bud", "mtp", "rbu2", "py", "bud_mtp", "bud_py"],
                    "description": (
                        "Scenario preset for the Phased tab. "
                        "all = show all scenarios, bud = ACT vs Budget, mtp = ACT vs MTP, "
                        "rbu2 = ACT vs RBU2, py = ACT vs Prior Year, "
                        "bud_mtp = ACT vs BUD & MTP, bud_py = ACT vs BUD & PY. "
                        "Only relevant when page='phased'. Omit to keep current."
                    ),
                },
                "dimension": {
                    "type": "string",
                    "enum": ["brand", "region", "unit", "market"],
                    "description": "DEPRECATED: Use 'levels' instead. Legacy dimension shortcut. Omit to keep current.",
                },
                "levels": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["ta", "brand", "market", "region", "unit", "sub_unit", "category"]},
                    "description": (
                        "Ordered drill hierarchy levels. All must be same domain. "
                        "Revenue levels: ta, brand, market, region. "
                        "Expense levels: unit, sub_unit. "
                        "Competitive levels: category, brand. "
                        "E.g. ['region', 'ta', 'brand'] for revenue by region then TA. "
                        "Omit to keep current."
                    ),
                },
                "scale": {
                    "type": "string",
                    "enum": ["K", "M", "B"],
                    "description": "Number scale ($K/$M/$B). Omit to keep current.",
                },
            },
            "required": ["summary"],
        },
    },
    {
        "name": "clarify",
        "description": (
            "Ask the user a clarifying question with 2-5 clickable options. "
            "Use this INSTEAD of guessing when the user's query is too vague to determine: "
            "which metric (revenue/expenses/market share), which scope (brand/region/unit), "
            "or which time period. Each option must be concise (under 10 words) and directly actionable."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask (1 sentence).",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-5 concise options. Each should work as a standalone follow-up question.",
                    "minItems": 2,
                    "maxItems": 5,
                },
            },
            "required": ["question", "options"],
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
    {
        "name": "decompose_variance",
        "description": (
            "Decompose a total variance into contributing factors. Call AFTER querying data to break down "
            "WHY a metric is above/below target. Each factor should be a specific driver (brand, market, category) "
            "with its contribution to the total variance in $M or pp. The result renders as a waterfall chart."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Chart title, e.g. 'Revenue variance vs Budget: +$320M'"},
                "total_label": {"type": "string", "description": "Label for the total bar, e.g. 'Total Variance'"},
                "total_value": {"type": "number", "description": "Total variance value (positive = favorable)"},
                "unit": {"type": "string", "enum": ["$M", "$B", "$K", "pp", "%"], "description": "Unit for display"},
                "factors": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "label": {"type": "string", "description": "Driver name, e.g. 'TAGRISSO US'"},
                            "value": {"type": "number", "description": "Contribution (positive = favorable, negative = unfavorable)"},
                            "detail": {"type": "string", "description": "Optional 1-line explanation"},
                        },
                        "required": ["label", "value"],
                    },
                    "description": "Ordered list of contributing factors. Should roughly sum to total_value.",
                },
            },
            "required": ["title", "total_label", "total_value", "unit", "factors"],
        },
    },
    {
        "name": "think",
        "description": (
            "Record your investigation reasoning. Call this BEFORE querying data to state your plan, "
            "and AFTER receiving results to record findings and decide next steps. "
            "The user sees these as investigation steps — be concise and specific."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "step": {
                    "type": "string",
                    "enum": ["plan", "finding", "pivot"],
                    "description": "plan = what you'll investigate next, finding = what you learned from data, pivot = changing direction based on findings",
                },
                "content": {
                    "type": "string",
                    "description": "1-2 sentences. For plan: what and why. For finding: the key insight from the data. For pivot: why you're changing approach.",
                },
            },
            "required": ["step", "content"],
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
    "query_config": lambda p: json.dumps(data_loader.app_config),
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
    "query_config": "dashboard configuration",
    "propose_config": "configuration proposal",
    "clarify": "clarification",
    "render_table": "table",
    "render_chart": "chart",
    "decompose_variance": "variance decomposition",
    "think": "reasoning",
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
        f"- Active page: {ctx.get('page', 'overview')}",
        f"- Drill hierarchy: {' → '.join(ctx.get('levels', ['ta', 'brand', 'market']))}",
        "- Available levels: Revenue=[ta, brand, market, region], Expense=[unit, sub_unit], Competitive=[category, brand]",
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

    comp = filters.get("comparator", "BUD")
    parts.append(f"- Comparator: {comp}")
    scale = filters.get("scale", "M")
    parts.append(f"- Scale: ${scale}")

    parts.extend([
        "",
        "## Response Modes — PICK EXACTLY ONE",
        "",
        "Every response must use exactly ONE of these three modes. Never mix them.",
        "",
        "### Mode 1: Clarify (vague query)",
        "Call the `clarify` tool ONLY. No text output, no other tools.",
        "Use when the user's query is too vague: 'How are we doing?', 'Show me the numbers', 'What about China?', single-word queries.",
        "Do NOT clarify when the user mentions a specific brand, TA, market, metric, or clicked on a data point.",
        "Each option must be a self-contained question the user could ask directly.",
        "",
        "### Mode 2: Configure (navigation request)",
        "Call the `propose_config` tool ONLY. Do NOT output any text before or after the tool call.",
        "Do NOT query data. Do NOT fabricate numbers or tables. Do NOT describe what the view looks like.",
        "JUST call propose_config with the right parameters. Nothing else.",
        "Use when the user wants to CHANGE the dashboard — switching comparators, markets, TAs, views, or periods.",
        "Trigger phrases: 'show me', 'set me', 'compare', 'switch to', 'focus on', 'filter to', 'vs plan/budget/forecast', 'view for'.",
        "- Always include a plain-English summary explaining what the config does.",
        "- Only include fields that differ from the current dashboard state.",
        "- Map user language: 'vs plan'/'vs budget' → BUD, 'vs forecast'/'vs reforecast' → RBU2, 'vs last year' → PYACT, 'vs MTP' → MTP.",
        "- **Compose the full view**: set page + levels + filters + scenario together when it makes sense.",
        "- **Page selection guide**:",
        "  - `overview`: best for drill-down analysis, seeing the tree hierarchy with KPIs, variances, sparklines.",
        "  - `landing`: best for YTD tracking — shows actuals + forecast cumulative chart and monthly table.",
        "  - `phased`: best for scenario comparison — shows ACT side by side with BUD/MTP/RBU2/PY by period.",
        "- When the user asks to 'compare scenarios' or 'show phased' or 'actuals vs budget by quarter', suggest page='phased' with the right scenario_preset.",
        "- When the user asks for 'YTD' or 'forecast' or 'landing', suggest page='landing'.",
        "- When the user asks for a 'breakdown' or 'drill down', suggest page='overview' with appropriate levels.",
        "",
        "### Mode 3: Analyze (data question)",
        "Conduct a structured investigation. Use the `think` tool to make your reasoning visible.",
        "Use when the user asks a question about the data: performance, trends, comparisons, drivers, rankings.",
        "",
        "Investigation pattern:",
        "1. **Plan** — Call `think(step=\"plan\")` to state what you'll investigate and why",
        "2. **Query** — Call the relevant data tool(s)",
        "3. **Record** — Call `think(step=\"finding\")` to note what you learned",
        "4. **Decide** — Either:",
        "   a. Drill deeper: call `think(step=\"plan\")` with next investigation step, then query more",
        "   b. Pivot: call `think(step=\"pivot\")` if findings suggest a different angle, then query",
        "   c. Synthesize: write your final response with XML tags",
        "",
        "Guidelines:",
        "- ALWAYS start with think(plan) before your first data query",
        "- ALWAYS call think(finding) after receiving data results — never skip to the next query",
        "- For simple questions (single metric lookup), use 1 plan + 1 finding + synthesis",
        "- For complex questions (trends, drivers, comparisons), investigate 2-4 angles",
        "- Never exceed 4 investigation steps — synthesize what you have",
        "- Each think content must be 1-2 sentences, specific, with numbers when available",
        "- Use XML tags for final response: <facts>...</facts>, <interpretation>...</interpretation>, <hypothesis>...</hypothesis>, <recommendations>...</recommendations>",
        "- You do NOT need all four sections. Simple questions may only need <facts>.",
        "- <recommendations> is OPTIONAL — only include when you have specific, actionable next steps grounded in the data.",
        "- Each recommendation should be a concrete action: 'Investigate Brand X Q3 pipeline delay', 'Compare RBU2 vs BUD for Oncology to validate forecast gap'.",
        "- Do NOT give generic advice like 'monitor closely' or 'keep tracking'. Be specific with brand/market/metric names.",
        "- Keep each section to 2-4 bullet points. Be dense with information, not verbose.",
        "- Use render_table when comparing 3+ items side-by-side. Use render_chart for trends or distributions.",
        "- When explaining WHY a metric is above/below target, use `decompose_variance` to show a waterfall of contributing factors.",
        "- To build a decomposition: query tree data (brand/region/unit), identify top 5-8 drivers by absolute variance contribution, then call decompose_variance.",
        "- Each factor should be a specific entity (brand, market, unit) with its dollar or percentage-point contribution.",
        "- Always query data first — never fabricate or estimate numbers.",
        "- NEVER output a table of numbers in text. Use render_table for tables.",
        "- NEVER describe what the dashboard shows — you don't see the screen. Only use queried data.",
        "",
        "**CRITICAL — Query scope vs. dashboard filters:**",
        "- The dashboard may have active filters (e.g. TA: Oncology). These are listed in 'Current Dashboard State' above.",
        "- When the user asks a SCOPED question ('How is Oncology doing?', 'Oncology brands vs budget'), KEEP the active TA/market filter in your query.",
        "- When the user asks a CROSS-SCOPE question ('top 5 brands overall', 'compare all TAs', 'total AZ revenue', 'which TA is biggest?'), you MUST OMIT the TA/market filter to get the full dataset — even if the dashboard currently has a filter active.",
        "- Look for scope signals: 'overall', 'across all', 'total', 'company-wide', 'by TA', 'all brands' → omit filters. Absence of a specific TA/market name in the question when asking for rankings or totals → omit filters.",
        "- When in doubt, query WITHOUT filters first to get the complete picture, then drill into specifics.",
        "",
        "- When the user asks about a specific brand/TA, use the right filters to get precise data.",
        "- Match the period and filters from the dashboard context unless the user asks for something different.",
    ])

    return "\n".join(parts)


def _parse_sections(text: str) -> list[tuple[str, str]]:
    """Parse XML-tagged sections from model output."""
    sections = []
    for tag in ("facts", "interpretation", "hypothesis", "recommendations"):
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

        # Build multi-turn conversation from history
        messages = []
        for h in req.history:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": req.question})

        log.info("Assistant request: question=%r history_len=%d context_page=%s", req.question, len(req.history), req.context.get("page"))
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
                    if config.LLM_DEBUG:
                        log.info("[DEBUG] final_text=\n%s", text_content[:2000])
                    # Guard: if text has no XML tags and looks like fabricated data (many $/ B values),
                    # the LLM probably failed to use a tool — log and send minimal error.
                    # Skip this guard if tools were already used in prior iterations (data is real).
                    if not used_tools and \
                       not any(f"<{t}>" in text_content for t in ("facts", "interpretation", "hypothesis")) and \
                       text_content.count("B0.") + text_content.count("B1.") + text_content.count("$") > 5:
                        log.warning("LLM returned fabricated table data instead of using tools — suppressing")
                        yield _sse("error", "I wasn't able to process that correctly. Could you rephrase your question?")
                        yield _sse("done", "")
                        sent_done = True
                        break
                    sections = _parse_sections(text_content)
                    for section_type, content in sections:
                        yield _sse(section_type, content)
                    yield _sse("done", "")
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

                    if name in ("render_table", "render_chart", "propose_config", "clarify", "think", "decompose_variance"):
                        # UI-only tools — no "Querying..." status, just emit the visual/event
                        if name == "think":
                            yield _sse("thinking", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Noted. Continue your investigation.",
                            })
                        elif name == "propose_config":
                            yield _sse("config_proposal", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Configuration proposal shown to user. They can apply it with one tap.",
                            })
                        elif name == "clarify":
                            yield _sse("clarification", json.dumps(tool_block.input))
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": "Clarification options shown to user. Wait for their response.",
                            })
                        else:
                            visual_spec = json.dumps({"tool": name, **tool_block.input})
                            log.info("Visual spec: %s", visual_spec[:200])
                            yield _sse("visual", visual_spec)
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": tool_block.id,
                                "content": f"Rendered {name.replace('render_', '')} for the user.",
                            })
                    else:
                        # Data query tools — show progress
                        yield _sse("tool_use", f"Querying {label}...")
                        params = {k: v for k, v in tool_block.input.items() if v is not None}
                        try:
                            result = TOOL_DISPATCH[name](params)
                            log.info("Tool %s returned %d chars", name, len(result))
                            if config.LLM_DEBUG:
                                log.info("[DEBUG] tool=%s result_preview=%s", name, result[:500])
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
                                "content": f"Error: {type(e).__name__}",
                                "is_error": True,
                            })
                        yield _sse("tool_done", f"Queried {label}")

                # If clarify or propose_config was used, stop — these are standalone responses
                if any(tb.name in ("clarify", "propose_config") for tb in tool_uses):
                    yield _sse("done", "")
                    sent_done = True
                    break

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

        except asyncio.CancelledError:
            log.info("Assistant SSE stream cancelled by client")
        except Exception as e:
            log.exception("Assistant error")
            yield _sse("error", "An error occurred processing your request.")
        finally:
            if not sent_done:
                yield _sse("done", "")

    return StreamingResponse(generate(), media_type="text/event-stream")
