from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues

router = APIRouter()


def _sparkline(df, group_col, group_val, value_col, year):
    """Get 12 monthly values for a sparkline."""
    src = data_loader.revenue if value_col == "revenue" else data_loader.expenses
    s = src[src.year == year]
    if group_col and group_val:
        s = s[s[group_col] == group_val]
    monthly = s.groupby("month")[value_col].sum().reindex(range(1, 13), fill_value=0)
    return [round(v, 1) for v in monthly.values]


def _sparkline_multi(df_year, brand_ids, year):
    """Sparkline for a set of brands (for TA-level aggregation)."""
    s = df_year[df_year.brand_id.isin(brand_ids)]
    monthly = s.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
    return [round(v, 1) for v in monthly.values]


@router.get("/brand", response_model=TreeTableSpec)
def get_brand_view(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    rev = data_loader.revenue
    tgt = data_loader.targets[data_loader.targets.target_type == "revenue"]
    prods = data_loader.products
    geo = data_loader.geographies
    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        prods = prods[prods.therapeutic_area.isin(ta_list)]
        ta_brands = prods.brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands)]

    # Filter
    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = int(quarter[1])
        r = r[r.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        r = r[r.market_id.isin(mkt_list)]
        t = t[t.market_id.isin(mkt_list)]

    # Prior year
    r_py = rev[rev.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        r_py = r_py[r_py.market_id.isin(mkt_list)]

    # Full year data for sparklines (always 12 months regardless of quarter filter)
    r_full = rev[rev.year == year]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        r_full = r_full[r_full.market_id.isin(mkt_list)]

    # Commercial market data
    comm = data_loader.commercial
    c = comm[comm.period_date.dt.year == year]
    if quarter:
        c = c[c.period_date.dt.quarter == int(quarter[1])]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        c = c[c.market_id.isin(mkt_list)]

    # Brand-level aggregation
    brand_actual = r.groupby("brand_id")["revenue"].sum()
    brand_budget = t.groupby("entity_id")["budget_amount"].sum()
    brand_forecast = t.groupby("entity_id")["forecast_amount"].sum()
    brand_py = r_py.groupby("brand_id")["revenue"].sum()

    # Brand-level commercial: revenue-weighted market share, avg growth
    def _brand_commercial(brand_id):
        bc = c[c.brand_id == brand_id]
        if bc.empty:
            return None, None
        total_rev = bc["az_revenue_usd_m"].sum()
        if total_rev > 0:
            share = round((bc["az_market_share_pct"] * bc["az_revenue_usd_m"]).sum() / total_rev, 1)
        else:
            share = round(bc["az_market_share_pct"].mean(), 1)
        growth = round(bc["market_growth_pct"].mean(), 1)
        return share, growth

    def var_pct(actual, compare):
        return round((actual - compare) / compare * 100, 1) if compare else 0.0

    # Build tree: Total AZ → TAs → Brands
    ta_children = []
    for ta in prods.therapeutic_area.unique():
        ta_brands = prods[prods.therapeutic_area == ta].brand_id.tolist()
        brand_children = []

        for brand_id in ta_brands:
            name = prods[prods.brand_id == brand_id].brand_name.values[0]
            actual = float(brand_actual.get(brand_id, 0))
            budget = float(brand_budget.get(brand_id, 0))
            forecast = float(brand_forecast.get(brand_id, 0))
            py = float(brand_py.get(brand_id, 0))

            spark = r_full[r_full.brand_id == brand_id].groupby("month")["revenue"].sum()
            spark = spark.reindex(range(1, 13), fill_value=0)
            mkt_share, mkt_growth = _brand_commercial(brand_id)

            # Market-level children under each brand
            br = r[r.brand_id == brand_id]
            bt = t[t.entity_id == brand_id]
            bpy = r_py[r_py.brand_id == brand_id]
            bf = r_full[r_full.brand_id == brand_id]
            market_children = []
            for mid in sorted(br.market_id.unique()):
                m_actual = float(br[br.market_id == mid]["revenue"].sum())
                m_budget = float(bt[bt.market_id == mid]["budget_amount"].sum())
                m_forecast = float(bt[bt.market_id == mid]["forecast_amount"].sum())
                m_py = float(bpy[bpy.market_id == mid]["revenue"].sum())
                m_spark = bf[bf.market_id == mid].groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
                geo_row = geo[geo.market_id == mid]
                m_name = geo_row.market_name.values[0] if len(geo_row) > 0 else mid
                market_children.append(TreeNode(
                    id=f"{brand_id}_{mid}",
                    name=m_name,
                    values=TreeNodeValues(
                        actual=round(m_actual, 1),
                        budget=round(m_budget, 1),
                        variance_pct=var_pct(m_actual, m_budget),
                        prior_year=round(m_py, 1),
                        py_variance_pct=var_pct(m_actual, m_py),
                        sparkline=[round(v, 1) for v in m_spark.values],
                        forecast=round(m_forecast, 1),
                        forecast_variance_pct=var_pct(m_actual, m_forecast),
                    ),
                ))

            brand_children.append(TreeNode(
                id=brand_id,
                name=name,
                values=TreeNodeValues(
                    actual=round(actual, 1),
                    budget=round(budget, 1),
                    variance_pct=var_pct(actual, budget),
                    prior_year=round(py, 1),
                    py_variance_pct=var_pct(actual, py),
                    sparkline=[round(v, 1) for v in spark.values],
                    forecast=round(forecast, 1),
                    forecast_variance_pct=var_pct(actual, forecast),
                    market_share_pct=mkt_share,
                    market_growth_pct=mkt_growth,
                ),
                children=market_children,
            ))

        # TA subtotal
        ta_actual = sum(ch.values.actual for ch in brand_children)
        ta_budget = sum(ch.values.budget for ch in brand_children)
        ta_forecast = sum(ch.values.forecast or 0 for ch in brand_children)
        ta_py = sum(ch.values.prior_year or 0 for ch in brand_children)
        ta_spark = _sparkline_multi(r_full, ta_brands, year)

        ta_children.append(TreeNode(
            id=ta,
            name=ta,
            values=TreeNodeValues(
                actual=round(ta_actual, 1),
                budget=round(ta_budget, 1),
                variance_pct=var_pct(ta_actual, ta_budget),
                prior_year=round(ta_py, 1),
                py_variance_pct=var_pct(ta_actual, ta_py),
                sparkline=ta_spark,
                forecast=round(ta_forecast, 1),
                forecast_variance_pct=var_pct(ta_actual, ta_forecast),
            ),
            children=brand_children,
        ))

    # Grand total
    grand_actual = sum(tc.values.actual for tc in ta_children)
    grand_budget = sum(tc.values.budget for tc in ta_children)
    grand_forecast = sum(tc.values.forecast or 0 for tc in ta_children)
    grand_py = sum(tc.values.prior_year or 0 for tc in ta_children)
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
            children=ta_children,
        ),
    )
