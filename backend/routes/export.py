"""Export endpoint — CSV download for any view."""

import io
import csv
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from routes.brand import get_brand_view
from routes.region import get_region_view
from routes.unit import get_unit_view
from routes.market import get_market_view

router = APIRouter()


def _flatten_tree(node, path=None) -> list[dict]:
    """Flatten a tree node into rows with a path column."""
    if path is None:
        path = []
    current_path = path + [node.name]
    rows = []
    v = node.values
    row = {
        "path": " > ".join(current_path),
        "name": node.name,
        "level": len(current_path),
        "actual": v.actual,
        "budget": v.budget,
        "variance_pct": v.variance_pct,
    }
    if v.prior_year is not None:
        row["prior_year"] = v.prior_year
    if v.py_variance_pct is not None:
        row["py_variance_pct"] = v.py_variance_pct
    if v.forecast is not None:
        row["forecast"] = v.forecast
    if v.market_share_pct is not None:
        row["market_share_pct"] = v.market_share_pct
    if v.personnel_costs is not None:
        row["personnel_costs"] = v.personnel_costs
    if v.external_costs is not None:
        row["external_costs"] = v.external_costs
    if v.other_costs is not None:
        row["other_costs"] = v.other_costs
    rows.append(row)
    for child in node.children:
        rows.extend(_flatten_tree(child, current_path))
    return rows


def _csv_response(rows: list[dict], filename: str) -> StreamingResponse:
    if not rows:
        return StreamingResponse(io.StringIO(""), media_type="text/csv")
    # Collect all keys across all rows to handle varying fields
    all_keys: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                all_keys.append(k)
                seen.add(k)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=all_keys, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/brand")
def export_brand(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    spec = get_brand_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    rows = _flatten_tree(spec.tree)
    return _csv_response(rows, f"brand_{spec.period_label.replace(' ', '_')}.csv")


@router.get("/export/region")
def export_region(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    spec = get_region_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    rows = _flatten_tree(spec.tree)
    return _csv_response(rows, f"region_{spec.period_label.replace(' ', '_')}.csv")


@router.get("/export/unit")
def export_unit(year: int = 2025, quarter: str | None = None):
    spec = get_unit_view(year=year, quarter=quarter)
    rows = _flatten_tree(spec.tree)
    return _csv_response(rows, f"unit_{spec.period_label.replace(' ', '_')}.csv")


@router.get("/export/market")
def export_market(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    spec = get_market_view(year=year, quarter=quarter, market_id=market_id, ta=ta)
    rows = _flatten_tree(spec.tree)
    return _csv_response(rows, f"market_{spec.period_label.replace(' ', '_')}.csv")
