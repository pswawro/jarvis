from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues

router = APIRouter()


@router.get("/region", response_model=TreeTableSpec)
def get_region_view(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    rev = data_loader.revenue
    geo = data_loader.geographies
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = data_loader.products[data_loader.products.therapeutic_area.isin(ta_list)].brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
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

    def var_pct(actual, compare):
        return round((actual - compare) / compare * 100, 1) if compare else 0.0

    # Market-level aggregation
    market_actual = r.groupby("market_id")["revenue"].sum()
    market_budget = t.groupby("market_id")["budget_amount"].sum()
    market_forecast = t.groupby("market_id")["forecast_amount"].sum()
    market_py = r_py.groupby("market_id")["revenue"].sum()

    prods = data_loader.products

    # Build tree: Total AZ → Regions → Markets → Brands
    region_map: dict[str, list[TreeNode]] = {}
    for _, g in geo.iterrows():
        mid = g.market_id
        region = g.region
        actual = float(market_actual.get(mid, 0))
        budget = float(market_budget.get(mid, 0))
        forecast = float(market_forecast.get(mid, 0))
        py = float(market_py.get(mid, 0))

        spark = r_full[r_full.market_id == mid].groupby("month")["revenue"].sum()
        spark = spark.reindex(range(1, 13), fill_value=0)

        # Brand-level children under each market
        mr = r[r.market_id == mid]
        mt = t[t.market_id == mid]
        mpy = r_py[r_py.market_id == mid]
        mf = r_full[r_full.market_id == mid]
        brand_children = []
        for brand_id in sorted(mr.brand_id.unique()):
            b_actual = float(mr[mr.brand_id == brand_id]["revenue"].sum())
            b_budget = float(mt[mt.entity_id == brand_id]["budget_amount"].sum())
            b_forecast = float(mt[mt.entity_id == brand_id]["forecast_amount"].sum())
            b_py = float(mpy[mpy.brand_id == brand_id]["revenue"].sum())
            b_spark = mf[mf.brand_id == brand_id].groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
            prod_row = prods[prods.brand_id == brand_id]
            b_name = prod_row.brand_name.values[0] if len(prod_row) > 0 else brand_id
            brand_children.append(TreeNode(
                id=f"{mid}_{brand_id}",
                name=b_name,
                values=TreeNodeValues(
                    actual=round(b_actual, 1),
                    budget=round(b_budget, 1),
                    variance_pct=var_pct(b_actual, b_budget),
                    prior_year=round(b_py, 1),
                    py_variance_pct=var_pct(b_actual, b_py),
                    sparkline=[round(v, 1) for v in b_spark.values],
                    forecast=round(b_forecast, 1),
                    forecast_variance_pct=var_pct(b_actual, b_forecast),
                ),
            ))

        node = TreeNode(
            id=mid,
            name=g.market_name,
            values=TreeNodeValues(
                actual=round(actual, 1),
                budget=round(budget, 1),
                variance_pct=var_pct(actual, budget),
                prior_year=round(py, 1),
                py_variance_pct=var_pct(actual, py),
                sparkline=[round(v, 1) for v in spark.values],
                forecast=round(forecast, 1),
                forecast_variance_pct=var_pct(actual, forecast),
            ),
            children=brand_children,
        )
        region_map.setdefault(region, []).append(node)

    region_children = []
    for region, markets in region_map.items():
        reg_actual = sum(m.values.actual for m in markets)
        reg_budget = sum(m.values.budget for m in markets)
        reg_forecast = sum(m.values.forecast or 0 for m in markets)
        reg_py = sum(m.values.prior_year or 0 for m in markets)
        reg_spark = [
            round(sum(m.values.sparkline[i] for m in markets), 1) for i in range(12)
        ]

        region_children.append(TreeNode(
            id=region,
            name=region,
            values=TreeNodeValues(
                actual=round(reg_actual, 1),
                budget=round(reg_budget, 1),
                variance_pct=var_pct(reg_actual, reg_budget),
                prior_year=round(reg_py, 1),
                py_variance_pct=var_pct(reg_actual, reg_py),
                sparkline=reg_spark,
                forecast=round(reg_forecast, 1),
                forecast_variance_pct=var_pct(reg_actual, reg_forecast),
            ),
            children=markets,
        ))

    grand_actual = sum(c.values.actual for c in region_children)
    grand_budget = sum(c.values.budget for c in region_children)
    grand_forecast = sum(c.values.forecast or 0 for c in region_children)
    grand_py = sum(c.values.prior_year or 0 for c in region_children)
    grand_spark = r_full.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)

    period_label = f"{'Q' + quarter[1] + ' ' if quarter else 'FY '}{year}"

    return TreeTableSpec(
        period_label=period_label,
        columns=["Name", "Actual", "Forecast", "vs Budget", "vs PY", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=TreeNodeValues(
                actual=round(grand_actual, 1),
                budget=round(grand_budget, 1),
                variance_pct=var_pct(grand_actual, grand_budget),
                prior_year=round(grand_py, 1),
                py_variance_pct=var_pct(grand_actual, grand_py),
                sparkline=[round(v, 1) for v in grand_spark.values],
                forecast=round(grand_forecast, 1),
                forecast_variance_pct=var_pct(grand_actual, grand_forecast),
            ),
            children=region_children,
        ),
    )
