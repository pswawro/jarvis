from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues
from routes.shared import validate_params, var_pct, period_label, COMPARATOR_FIELD, COMPARATOR_LABELS

router = APIRouter()


@router.get("/region", response_model=TreeTableSpec)
def get_region_view(
    year: int = 2025,
    quarter: str | None = None,
    market_id: str | None = None,
    ta: str | None = None,
    comparator: str = "BUD",
):
    validate_params(year=year, quarter=quarter, comparator=comparator)
    rev = data_loader.revenue
    geo = data_loader.geographies
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = data_loader.products[data_loader.products.therapeutic_area.isin(ta_list)].brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]
    mkt_list = [m.strip() for m in market_id.split(",")] if market_id else None
    if mkt_list:
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[tgt.market_id.isin(mkt_list)]
        geo = geo[geo.market_id.isin(mkt_list)]

    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = int(quarter[1])
        r = r[r.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]

    r_py = rev[rev.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]

    r_full = rev[rev.year == year]

    comp_label = COMPARATOR_LABELS.get(comparator, comparator)

    def _make_values(actual, budget, forecast, py, mtp, rbu2, spark):
        comp_val = py if comparator == "PYACT" else {"BUD": budget, "MTP": mtp, "RBU2": rbu2}.get(comparator, budget)
        return TreeNodeValues(
            actual=round(actual, 1),
            budget=round(budget, 1),
            variance_pct=var_pct(actual, budget),
            prior_year=round(py, 1),
            py_variance_pct=var_pct(actual, py),
            sparkline=spark,
            forecast=round(forecast, 1),
            forecast_variance_pct=var_pct(actual, forecast),
            mtp=round(mtp, 1),
            mtp_variance_pct=var_pct(actual, mtp),
            rbu2=round(rbu2, 1),
            rbu2_variance_pct=var_pct(actual, rbu2),
            comparator_label=comp_label,
            comparator_value=round(comp_val, 1),
            comparator_variance_pct=var_pct(actual, comp_val),
        )

    market_actual = r.groupby("market_id")["revenue"].sum()
    market_targets = t.groupby("market_id")[["budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"]].sum()
    market_py = r_py.groupby("market_id")["revenue"].sum()

    # Pre-compute sparklines in bulk
    market_month_rev = r_full.groupby(["market_id", "month"])["revenue"].sum().unstack(fill_value=0).reindex(columns=range(1, 13), fill_value=0)
    brand_market_month_rev = r_full.groupby(["market_id", "brand_id", "month"])["revenue"].sum().unstack(fill_value=0).reindex(columns=range(1, 13), fill_value=0)

    prods = data_loader.products
    brand_names = dict(zip(prods.brand_id, prods.brand_name))

    # Pre-compute brand-level targets and revenue per market
    brand_market_targets = t.groupby(["market_id", "entity_id"])[["budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"]].sum()
    brand_market_actual = r.groupby(["market_id", "brand_id"])["revenue"].sum()
    brand_market_py_rev = r_py.groupby(["market_id", "brand_id"])["revenue"].sum()

    region_map: dict[str, list[TreeNode]] = {}
    for _, g in geo.iterrows():
        mid = g.market_id
        region = g.region
        actual = float(market_actual.get(mid, 0))
        if mid in market_targets.index:
            mt_row = market_targets.loc[mid]
            budget = float(mt_row["budget_amount"])
            forecast = float(mt_row["forecast_amount"])
            mtp = float(mt_row["mtp_amount"])
            rbu2 = float(mt_row["rbu2_amount"])
        else:
            budget = forecast = mtp = rbu2 = 0.0
        py = float(market_py.get(mid, 0))

        spark = [round(v, 1) for v in market_month_rev.loc[mid].values] if mid in market_month_rev.index else [0.0] * 12

        # Brand children from pre-computed groupby
        brand_ids = brand_market_actual.loc[mid].index.tolist() if mid in brand_market_actual.index.get_level_values(0) else []
        brand_children = []
        for brand_id in sorted(brand_ids):
            b_actual = float(brand_market_actual.get((mid, brand_id), 0))
            b_key = (mid, brand_id)
            if b_key in brand_market_targets.index:
                bmt_row = brand_market_targets.loc[b_key]
                b_budget = float(bmt_row["budget_amount"])
                b_forecast = float(bmt_row["forecast_amount"])
                b_mtp = float(bmt_row["mtp_amount"])
                b_rbu2 = float(bmt_row["rbu2_amount"])
            else:
                b_budget = b_forecast = b_mtp = b_rbu2 = 0.0
            b_py = float(brand_market_py_rev.get((mid, brand_id), 0))
            b_spark = [round(v, 1) for v in brand_market_month_rev.loc[(mid, brand_id)].values] if (mid, brand_id) in brand_market_month_rev.index else [0.0] * 12
            b_name = brand_names.get(brand_id, brand_id)
            brand_children.append(TreeNode(
                id=f"{mid}_{brand_id}",
                name=b_name,
                values=_make_values(b_actual, b_budget, b_forecast, b_py, b_mtp, b_rbu2, b_spark),
            ))

        node = TreeNode(
            id=mid,
            name=g.market_name,
            values=_make_values(actual, budget, forecast, py, mtp, rbu2, spark),
            children=brand_children,
        )
        region_map.setdefault(region, []).append(node)

    region_children = []
    for region, markets in region_map.items():
        reg_actual = sum(m.values.actual for m in markets)
        reg_budget = sum(m.values.budget for m in markets)
        reg_forecast = sum(m.values.forecast or 0 for m in markets)
        reg_mtp = sum(m.values.mtp or 0 for m in markets)
        reg_rbu2 = sum(m.values.rbu2 or 0 for m in markets)
        reg_py = sum(m.values.prior_year or 0 for m in markets)
        reg_spark = [round(sum(m.values.sparkline[i] for m in markets), 1) for i in range(12)]

        region_children.append(TreeNode(
            id=region,
            name=region,
            values=_make_values(reg_actual, reg_budget, reg_forecast, reg_py, reg_mtp, reg_rbu2, reg_spark),
            children=markets,
        ))

    grand_actual = sum(c.values.actual for c in region_children)
    grand_budget = sum(c.values.budget for c in region_children)
    grand_forecast = sum(c.values.forecast or 0 for c in region_children)
    grand_mtp = sum(c.values.mtp or 0 for c in region_children)
    grand_rbu2 = sum(c.values.rbu2 or 0 for c in region_children)
    grand_py = sum(c.values.prior_year or 0 for c in region_children)
    grand_spark = r_full.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "Actual", f"vs {comp_label}", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=_make_values(grand_actual, grand_budget, grand_forecast, grand_py, grand_mtp, grand_rbu2,
                                [round(v, 1) for v in grand_spark.values]),
            children=region_children,
        ),
    )
