from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues
from routes.shared import validate_params, safe_round, var_pct, period_label, COMPARATOR_FIELD, COMPARATOR_LABELS

router = APIRouter()


def _sparkline_multi(df_year, brand_ids, year):
    """Sparkline for a set of brands (for TA-level aggregation)."""
    s = df_year[df_year.brand_id.isin(brand_ids)]
    monthly = s.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)
    return [round(v, 1) for v in monthly.values]


@router.get("/brand", response_model=TreeTableSpec)
def get_brand_view(
    year: int = 2025,
    quarter: str | None = None,
    market_id: str | None = None,
    ta: str | None = None,
    comparator: str = "BUD",
):
    validate_params(year=year, quarter=quarter, comparator=comparator)
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

    mkt_list = [m.strip() for m in market_id.split(",")] if market_id else None

    # Filter by year/quarter
    r = rev[rev.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = int(quarter[1])
        r = r[r.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]
    if mkt_list:
        r = r[r.market_id.isin(mkt_list)]
        t = t[t.market_id.isin(mkt_list)]

    # Prior year
    r_py = rev[rev.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]
    if mkt_list:
        r_py = r_py[r_py.market_id.isin(mkt_list)]

    # Full year for sparklines
    r_full = rev[rev.year == year]
    if mkt_list:
        r_full = r_full[r_full.market_id.isin(mkt_list)]

    # Commercial market data
    comm = data_loader.commercial
    c = comm[comm.period_date.dt.year == year]
    if quarter:
        c = c[c.period_date.dt.quarter == int(quarter[1])]
    if mkt_list:
        c = c[c.market_id.isin(mkt_list)]

    # Brand-level aggregation (consolidated groupby)
    brand_actual = r.groupby("brand_id")["revenue"].sum()
    brand_targets = t.groupby("entity_id")[["budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"]].sum()
    brand_py = r_py.groupby("brand_id")["revenue"].sum()

    # Pre-compute all sparklines in bulk
    brand_month_rev = r_full.groupby(["brand_id", "month"])["revenue"].sum().unstack(fill_value=0).reindex(columns=range(1, 13), fill_value=0)
    brand_market_month_rev = r_full.groupby(["brand_id", "market_id", "month"])["revenue"].sum().unstack(fill_value=0).reindex(columns=range(1, 13), fill_value=0)

    # Lookup dicts for O(1) name resolution
    brand_names = dict(zip(prods.brand_id, prods.brand_name))
    market_names = dict(zip(geo.market_id, geo.market_name))

    # Pre-compute brand→market revenue and PY for market-level children
    brand_market_actual = r.groupby(["brand_id", "market_id"])["revenue"].sum()
    brand_market_py = r_py.groupby(["brand_id", "market_id"])["revenue"].sum()
    brand_market_targets = t.groupby(["entity_id", "market_id"])[["budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"]].sum()

    # Determine comparator field
    comp_field = COMPARATOR_FIELD.get(comparator)
    comp_label = COMPARATOR_LABELS.get(comparator, comparator)

    def _brand_commercial(brand_id):
        bc = c[c.brand_id == brand_id]
        if bc.empty:
            return None, None
        total_rev = bc["az_revenue_usd_m"].sum()
        if total_rev > 0:
            share = safe_round((bc["az_market_share_pct"] * bc["az_revenue_usd_m"]).sum() / total_rev)
        else:
            share = safe_round(bc["az_market_share_pct"].mean())
        growth = safe_round(bc["market_growth_pct"].mean())
        return share, growth

    def _make_values(actual, budget, forecast, py, mtp, rbu2, spark, mkt_share=None, mkt_growth=None):
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
            market_share_pct=mkt_share,
            market_growth_pct=mkt_growth,
        )

    # Build tree: Total AZ → TAs → Brands
    ta_children = []
    for ta_name in prods.therapeutic_area.unique():
        ta_brand_ids = prods[prods.therapeutic_area == ta_name].brand_id.tolist()
        brand_children = []

        for brand_id in ta_brand_ids:
            name = brand_names.get(brand_id, brand_id)
            actual = float(brand_actual.get(brand_id, 0))
            if brand_id in brand_targets.index:
                tgt_row = brand_targets.loc[brand_id]
                budget = float(tgt_row["budget_amount"])
                forecast = float(tgt_row["forecast_amount"])
                mtp = float(tgt_row["mtp_amount"])
                rbu2 = float(tgt_row["rbu2_amount"])
            else:
                budget = forecast = mtp = rbu2 = 0.0
            py = float(brand_py.get(brand_id, 0))

            spark_list = [round(v, 1) for v in brand_month_rev.loc[brand_id].values] if brand_id in brand_month_rev.index else [0.0] * 12
            mkt_share, mkt_growth = _brand_commercial(brand_id)

            # Market-level children from pre-computed groupby
            brand_mkts = brand_market_actual.loc[brand_id].index.tolist() if brand_id in brand_market_actual.index.get_level_values(0) else []
            market_children = []
            for mid in sorted(brand_mkts):
                m_actual = float(brand_market_actual.get((brand_id, mid), 0))
                bmt_key = (brand_id, mid)
                if bmt_key in brand_market_targets.index:
                    bmt_row = brand_market_targets.loc[bmt_key]
                    m_budget = float(bmt_row["budget_amount"])
                    m_forecast = float(bmt_row["forecast_amount"])
                    m_mtp = float(bmt_row["mtp_amount"])
                    m_rbu2 = float(bmt_row["rbu2_amount"])
                else:
                    m_budget = m_forecast = m_mtp = m_rbu2 = 0.0
                m_py = float(brand_market_py.get((brand_id, mid), 0))
                m_spark = brand_market_month_rev.loc[(brand_id, mid)].values if (brand_id, mid) in brand_market_month_rev.index else [0.0] * 12
                m_name = market_names.get(mid, mid)
                market_children.append(TreeNode(
                    id=f"{brand_id}_{mid}",
                    name=m_name,
                    values=_make_values(m_actual, m_budget, m_forecast, m_py, m_mtp, m_rbu2,
                                        [round(v, 1) for v in m_spark]),
                ))

            brand_children.append(TreeNode(
                id=brand_id,
                name=name,
                values=_make_values(actual, budget, forecast, py, mtp, rbu2, spark_list, mkt_share, mkt_growth),
                children=market_children,
            ))

        # TA subtotal
        ta_actual = sum(ch.values.actual for ch in brand_children)
        ta_budget = sum(ch.values.budget for ch in brand_children)
        ta_forecast = sum(ch.values.forecast or 0 for ch in brand_children)
        ta_mtp = sum(ch.values.mtp or 0 for ch in brand_children)
        ta_rbu2 = sum(ch.values.rbu2 or 0 for ch in brand_children)
        ta_py = sum(ch.values.prior_year or 0 for ch in brand_children)
        ta_spark = _sparkline_multi(r_full, ta_brand_ids, year)

        ta_children.append(TreeNode(
            id=ta_name,
            name=ta_name,
            values=_make_values(ta_actual, ta_budget, ta_forecast, ta_py, ta_mtp, ta_rbu2, ta_spark),
            children=brand_children,
        ))

    # Grand total
    grand_actual = sum(tc.values.actual for tc in ta_children)
    grand_budget = sum(tc.values.budget for tc in ta_children)
    grand_forecast = sum(tc.values.forecast or 0 for tc in ta_children)
    grand_mtp = sum(tc.values.mtp or 0 for tc in ta_children)
    grand_rbu2 = sum(tc.values.rbu2 or 0 for tc in ta_children)
    grand_py = sum(tc.values.prior_year or 0 for tc in ta_children)
    grand_spark = r_full.groupby("month")["revenue"].sum().reindex(range(1, 13), fill_value=0)

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "Actual", f"vs {comp_label}", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ",
            name="Total AZ",
            values=_make_values(grand_actual, grand_budget, grand_forecast, grand_py, grand_mtp, grand_rbu2,
                                [round(v, 1) for v in grand_spark.values]),
            children=ta_children,
        ),
    )
