"""Phased view — scenario comparison pivot with tree hierarchy.

Shows ACT vs BUD vs MTP vs RBU2 vs PY side by side,
togglable between Month, Quarter, and Year granularity.
Supports composable drill hierarchy via `levels` param.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

import data_loader
from routes.shared import validate_params, LEVEL_COLS

router = APIRouter()

# Use LEVEL_COLS from shared module

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class PhasedTreeNode(BaseModel):
    id: str
    name: str
    periods: list[dict]  # {label, ACT, BUD, MTP, RBU2, PY}
    children: list["PhasedTreeNode"] = []


class PhasedTreeSpec(BaseModel):
    type: str = "phased_tree"
    period_label: str
    granularity: str
    period_labels: list[str]
    scenarios: list[str]
    tree: PhasedTreeNode


def _period_labels(granularity: str, year: int) -> list[str]:
    if granularity == "month":
        return MONTHS[:]
    elif granularity == "quarter":
        return ["Q1", "Q2", "Q3", "Q4"]
    return [str(year)]


def _empty_periods(labels: list[str]) -> list[dict]:
    return [{"label": l, "ACT": 0.0, "BUD": 0.0, "MTP": 0.0, "RBU2": 0.0, "PY": 0.0} for l in labels]


def _add_periods(a: list[dict], b: list[dict]) -> list[dict]:
    """Sum two period lists element-wise."""
    return [
        {"label": a[i]["label"], "ACT": a[i]["ACT"] + b[i]["ACT"], "BUD": a[i]["BUD"] + b[i]["BUD"],
         "MTP": a[i]["MTP"] + b[i]["MTP"], "RBU2": a[i]["RBU2"] + b[i]["RBU2"], "PY": a[i]["PY"] + b[i]["PY"]}
        for i in range(len(a))
    ]


@router.get("/phased", response_model=PhasedTreeSpec)
def get_phased_view(
    year: int = 2025,
    granularity: str = "quarter",
    market_id: str | None = None,
    ta: str | None = None,
    brand_id: str | None = None,
    entity_type: str = "ta",
    dimension: str | None = None,
    levels: str | None = None,
):
    if granularity not in ("month", "quarter", "year"):
        raise HTTPException(status_code=400, detail=f"Invalid granularity '{granularity}'. Must be month, quarter, or year.")

    # Parse levels
    level_list = [lv.strip() for lv in levels.split(",") if lv.strip()] if levels else None

    # Detect expense domain
    if level_list and any(lv in ("unit", "sub_unit") for lv in level_list):
        return _phased_expense(year, granularity)
    if dimension == "unit":
        return _phased_expense(year, granularity)

    if not level_list:
        if dimension == "brand":
            level_list = ["brand"]
        elif dimension in ("region", "market"):
            level_list = ["ta"]
        else:
            level_list = ["ta", "brand"]

    validate_params(year=year)

    rev = data_loader.revenue
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]
    prods = data_loader.products
    geo = data_loader.geographies

    # Filters
    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        prods = prods[prods.therapeutic_area.isin(ta_list)]
        ta_brands = prods.brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]
    if brand_id:
        bid_list = [b.strip() for b in brand_id.split(",")]
        prods = prods[prods.brand_id.isin(bid_list)]
        rev = rev[rev.brand_id.isin(bid_list)]
        tgt = tgt[tgt.entity_id.isin(bid_list)]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[tgt.market_id.isin(mkt_list)]

    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    r_py = rev[rev.year == year - 1]

    # Enrich with dimension columns
    r = r.merge(prods[["brand_id", "brand_name", "therapeutic_area"]], on="brand_id", how="left")
    r = r.merge(geo[["market_id", "market_name", "region"]], on="market_id", how="left")
    t = t.merge(prods[["brand_id", "brand_name", "therapeutic_area"]], left_on="entity_id", right_on="brand_id", how="left")
    t = t.merge(geo[["market_id", "market_name", "region"]], on="market_id", how="left")
    r_py = r_py.merge(prods[["brand_id", "brand_name", "therapeutic_area"]], on="brand_id", how="left")
    r_py = r_py.merge(geo[["market_id", "market_name", "region"]], on="market_id", how="left")

    # Build group columns
    group_cols = []
    name_cols = []
    for lv in level_list:
        cfg = LEVEL_COLS.get(lv)
        if cfg:
            group_cols.append(cfg["group"])
            name_cols.append(cfg["name"])
    if not group_cols:
        group_cols = ["therapeutic_area"]
        name_cols = ["therapeutic_area"]

    # Period config
    plabels = _period_labels(granularity, year)

    # Add period key column
    if granularity == "month":
        r = r.copy(); r["_pkey"] = r["month"]
        t = t.copy(); t["_pkey"] = t.period_date.dt.month
        r_py = r_py.copy(); r_py["_pkey"] = r_py["month"]
    elif granularity == "quarter":
        r = r.copy(); r["_pkey"] = r["quarter"].map(lambda q: int(q[1]) if isinstance(q, str) else q)
        t = t.copy(); t["_pkey"] = t.period_date.dt.quarter
        r_py = r_py.copy(); r_py["_pkey"] = r_py["quarter"].map(lambda q: int(q[1]) if isinstance(q, str) else q)
    else:
        r = r.copy(); r["_pkey"] = year
        t = t.copy(); t["_pkey"] = year
        r_py = r_py.copy(); r_py["_pkey"] = year

    # Pre-aggregate by all group cols + period key
    act_agg = r.groupby(group_cols + ["_pkey"])["revenue"].sum().reset_index()
    tgt_agg = t.groupby(group_cols + ["_pkey"])[["budget_amount", "mtp_amount", "rbu2_amount"]].sum().reset_index()
    py_agg = r_py.groupby(group_cols + ["_pkey"])["revenue"].sum().reset_index()

    def _get_periods(act_df, tgt_df, py_df, grp_filter: dict) -> list[dict]:
        """Get period data for a specific group filter."""
        af, tf, pf = act_df, tgt_df, py_df
        for col, val in grp_filter.items():
            af = af[af[col] == val]
            tf = tf[tf[col] == val]
            pf = pf[pf[col] == val]

        act_by_p = dict(zip(af["_pkey"], af["revenue"]))
        bud_by_p = dict(zip(tf["_pkey"], tf["budget_amount"])) if len(tf) > 0 else {}
        mtp_by_p = dict(zip(tf["_pkey"], tf["mtp_amount"])) if len(tf) > 0 else {}
        rbu2_by_p = dict(zip(tf["_pkey"], tf["rbu2_amount"])) if len(tf) > 0 else {}
        py_by_p = dict(zip(pf["_pkey"], pf["revenue"]))

        periods = []
        for pl in plabels:
            if granularity == "month":
                pk = MONTHS.index(pl) + 1
            elif granularity == "quarter":
                pk = int(pl[1])
            else:
                pk = year
            periods.append({
                "label": pl,
                "ACT": round(float(act_by_p.get(pk, 0)), 1),
                "BUD": round(float(bud_by_p.get(pk, 0)), 1),
                "MTP": round(float(mtp_by_p.get(pk, 0)), 1),
                "RBU2": round(float(rbu2_by_p.get(pk, 0)), 1),
                "PY": round(float(py_by_p.get(pk, 0)), 1),
            })
        return periods

    def _build_level(depth: int, parent_filter: dict) -> list[PhasedTreeNode]:
        if depth >= len(group_cols):
            return []

        gcol = group_cols[depth]
        ncol = name_cols[depth]

        # Get unique values from actuals + targets + PY
        filtered_act = act_agg
        filtered_tgt = tgt_agg
        for col, val in parent_filter.items():
            filtered_act = filtered_act[filtered_act[col] == val]
            filtered_tgt = filtered_tgt[filtered_tgt[col] == val]

        all_vals = sorted(set(filtered_act[gcol].dropna().unique()) | set(filtered_tgt[gcol].dropna().unique()))

        # Name mapping
        name_map = {}
        if gcol != ncol:
            src = r
            for col, val in parent_filter.items():
                src = src[src[col] == val]
            if len(src) > 0:
                name_map = dict(zip(src[gcol], src[ncol]))

        nodes = []
        for val in all_vals:
            current_filter = {**parent_filter, gcol: val}
            children = _build_level(depth + 1, current_filter)
            name = name_map.get(val, str(val))

            if children:
                # Aggregate from children
                periods = _empty_periods(plabels)
                for child in children:
                    periods = _add_periods(periods, child.periods)
            else:
                periods = _get_periods(act_agg, tgt_agg, py_agg, current_filter)

            nodes.append(PhasedTreeNode(
                id=str(val),
                name=str(name),
                periods=periods,
                children=children,
            ))
        return nodes

    top_children = _build_level(0, {})

    # Grand total
    grand_periods = _empty_periods(plabels)
    for child in top_children:
        grand_periods = _add_periods(grand_periods, child.periods)

    scenarios = ["ACT", "BUD", "MTP", "RBU2", "PY"]

    return PhasedTreeSpec(
        period_label=f"Phased {year}",
        granularity=granularity,
        period_labels=plabels,
        scenarios=scenarios,
        tree=PhasedTreeNode(
            id="TOTAL",
            name="Total",
            periods=grand_periods,
            children=top_children,
        ),
    )


def _phased_expense(year: int, granularity: str) -> PhasedTreeSpec:
    """Phased view for expense/unit dimension — uses expense data."""
    exp = data_loader.expenses
    org = data_loader.organization
    tgt = data_loader.targets[data_loader.targets.target_type == "expense"]

    e = exp[exp.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    e_py = exp[exp.year == year - 1]

    plabels = _period_labels(granularity, year)
    scenarios = ["ACT", "BUD", "MTP", "RBU2", "PY"]

    unit_subs = org.groupby("unit")["sub_unit_id"].apply(list).to_dict()

    children = []
    for unit_name in sorted(unit_subs.keys()):
        subs = unit_subs[unit_name]
        er = e[e.sub_unit_id.isin(subs)]
        et = t[t.entity_id.isin(subs)]
        epy = e_py[e_py.sub_unit_id.isin(subs)]

        if granularity == "month":
            act_by_p = er.groupby("month")["total_operating_expenses"].sum()
            tgt_by_p = et.groupby(et.period_date.dt.month)[["budget_amount", "mtp_amount", "rbu2_amount"]].sum()
            py_by_p = epy.groupby("month")["total_operating_expenses"].sum()
        elif granularity == "quarter":
            act_by_p = er.groupby("quarter")["total_operating_expenses"].sum()
            tgt_by_p = et.groupby(et.period_date.dt.quarter)[["budget_amount", "mtp_amount", "rbu2_amount"]].sum()
            py_by_p = epy.groupby("quarter")["total_operating_expenses"].sum()
        else:
            act_by_p = tgt_by_p = py_by_p = None

        periods = []
        for pl in plabels:
            if granularity == "month":
                pk = MONTHS.index(pl) + 1
                act = round(float(act_by_p.get(pk, 0)), 1)
                bud = round(float(tgt_by_p.loc[pk, "budget_amount"]), 1) if act_by_p is not None and pk in tgt_by_p.index else 0.0
                mtp = round(float(tgt_by_p.loc[pk, "mtp_amount"]), 1) if act_by_p is not None and pk in tgt_by_p.index else 0.0
                rbu2 = round(float(tgt_by_p.loc[pk, "rbu2_amount"]), 1) if act_by_p is not None and pk in tgt_by_p.index else 0.0
                py = round(float(py_by_p.get(pk, 0)), 1)
            elif granularity == "quarter":
                q_num = int(pl[1])
                act = round(float(act_by_p.get(pl, 0)), 1)
                bud = round(float(tgt_by_p.loc[q_num, "budget_amount"]), 1) if tgt_by_p is not None and q_num in tgt_by_p.index else 0.0
                mtp = round(float(tgt_by_p.loc[q_num, "mtp_amount"]), 1) if tgt_by_p is not None and q_num in tgt_by_p.index else 0.0
                rbu2 = round(float(tgt_by_p.loc[q_num, "rbu2_amount"]), 1) if tgt_by_p is not None and q_num in tgt_by_p.index else 0.0
                py = round(float(py_by_p.get(pl, 0)), 1)
            else:
                act = round(float(er.total_operating_expenses.sum()), 1)
                bud = round(float(et.budget_amount.sum()), 1)
                mtp = round(float(et.mtp_amount.sum()), 1)
                rbu2 = round(float(et.rbu2_amount.sum()), 1)
                py = round(float(epy.total_operating_expenses.sum()), 1)

            periods.append({"label": pl, "ACT": act, "BUD": bud, "MTP": mtp, "RBU2": rbu2, "PY": py})

        children.append(PhasedTreeNode(id=unit_name, name=unit_name, periods=periods))

    grand_periods = _empty_periods(plabels)
    for child in children:
        grand_periods = _add_periods(grand_periods, child.periods)

    return PhasedTreeSpec(
        period_label=f"Phased {year} — Expenses",
        granularity=granularity,
        period_labels=plabels,
        scenarios=scenarios,
        tree=PhasedTreeNode(id="TOTAL", name="Total Expenses", periods=grand_periods, children=children),
    )
