"""Tool routing — maps tool names to data functions and display labels."""

import json

from routes.kpi import get_kpi
from routes.brand import get_brand_view
from routes.region import get_region_view
from routes.unit import get_unit_view
from routes.market import get_market_view
from routes.chart import get_brand_chart, get_region_chart, get_unit_chart, get_market_chart
import data_loader

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

# UI-only tools — these don't query data, they render in the frontend
UI_TOOLS = {"render_table", "render_chart", "propose_config", "clarify", "think", "decompose_variance"}
