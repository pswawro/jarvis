from fastapi import APIRouter, Query

import data_loader
from models import KpiStripSpec, KpiCard, KpiComparison
from routes.shared import validate_params, safe_round, var_pct

router = APIRouter()


@router.get("/kpi", response_model=KpiStripSpec)
def get_kpi(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None, brand_id: str | None = None):
    validate_params(year=year, quarter=quarter)
    rev = data_loader.revenue
    exp = data_loader.expenses
    tgt = data_loader.targets

    # TA filter: restrict to brands in that therapeutic area
    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = data_loader.products[data_loader.products.therapeutic_area.isin(ta_list)].brand_id.tolist()
        rev = rev[rev.brand_id.isin(ta_brands)]
        tgt = tgt[tgt.entity_id.isin(ta_brands) | (tgt.target_type == "expense")]

    # Brand/product filter
    if brand_id:
        bid_list = [b.strip() for b in brand_id.split(",")]
        rev = rev[rev.brand_id.isin(bid_list)]
        tgt = tgt[tgt.entity_id.isin(bid_list) | (tgt.target_type == "expense")]

    # Market filter
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        rev = rev[rev.market_id.isin(mkt_list)]
        tgt = tgt[(tgt.market_id.isin(mkt_list)) | (tgt.target_type == "expense")]

    # Filter by year
    r = rev[rev.year == year]
    e = exp[exp.year == year]

    # Filter by quarter if specified
    if quarter:
        r = r[r.quarter == quarter]
        e = e[e.quarter == quarter]

    # Prior year
    r_py = rev[rev.year == year - 1]
    e_py = exp[exp.year == year - 1]
    if quarter:
        r_py = r_py[r_py.quarter == quarter]
        e_py = e_py[e_py.quarter == quarter]

    # Actuals
    total_revenue = r.revenue.sum()
    total_gross = r.gross_profit.sum()
    total_cogs = r.cost_of_sales.sum()

    filtered = bool(market_id or ta or brand_id)

    # Expenses have no market/TA breakdown — only show when unfiltered
    if not filtered:
        total_opex = e.total_operating_expenses.sum()
        op_profit = total_gross - total_opex
        margin = safe_round(op_profit / total_revenue * 100) if total_revenue else 0

    # Budget
    tgt_rev = tgt[(tgt.target_type == "revenue") & (tgt.period_date.dt.year == year)]
    tgt_exp = tgt[(tgt.target_type == "expense") & (tgt.period_date.dt.year == year)]
    if quarter:
        q_num = int(quarter[1])
        tgt_rev = tgt_rev[tgt_rev.period_date.dt.quarter == q_num]
        tgt_exp = tgt_exp[tgt_exp.period_date.dt.quarter == q_num]

    budget_rev = tgt_rev.budget_amount.sum()
    budget_gross = safe_round(budget_rev * (1 - total_cogs / total_revenue)) if total_revenue else 0
    if not filtered:
        budget_exp = tgt_exp.budget_amount.sum()
        budget_margin = safe_round((budget_gross - budget_exp) / budget_rev * 100) if budget_rev else 0

    # Prior year
    py_revenue = r_py.revenue.sum()
    py_gross = r_py.gross_profit.sum()
    if not filtered:
        py_opex = e_py.total_operating_expenses.sum()
        py_margin = safe_round((py_gross - py_opex) / py_revenue * 100) if py_revenue else 0

    period_lbl = f"{'Q' + quarter[1] + ' ' if quarter else 'FY '}{year}"

    cards = [
        KpiCard(
            label="Total Revenue",
            value=safe_round(total_revenue),
            unit="$M",
            comparisons=[
                KpiComparison(label="vs Budget", variance_pct=var_pct(total_revenue, budget_rev)),
                KpiComparison(label="vs PY", variance_pct=var_pct(total_revenue, py_revenue)),
            ],
        ),
        KpiCard(
            label="Gross Profit",
            value=safe_round(total_gross),
            unit="$M",
            comparisons=[
                KpiComparison(label="vs Budget", variance_pct=var_pct(total_gross, budget_gross)),
                KpiComparison(label="vs PY", variance_pct=var_pct(total_gross, py_gross)),
            ],
        ),
    ]

    if not filtered:
        cards += [
            KpiCard(
                label="Total OpEx",
                value=safe_round(total_opex),
                unit="$M",
                comparisons=[
                    KpiComparison(label="vs Budget", variance_pct=var_pct(total_opex, budget_exp)),
                    KpiComparison(label="vs PY", variance_pct=var_pct(total_opex, py_opex)),
                ],
            ),
            KpiCard(
                label="Op. Margin",
                value=safe_round(margin),
                unit="%",
                comparisons=[
                    KpiComparison(label="vs Budget", variance_pct=safe_round(margin - budget_margin)),
                    KpiComparison(label="vs PY", variance_pct=safe_round(margin - py_margin)),
                ],
            ),
        ]

    return KpiStripSpec(
        period_label=period_lbl,
        cards=cards,
    )
