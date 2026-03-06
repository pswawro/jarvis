"""Market view — competitive positioning by drug category."""

from fastapi import APIRouter

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues

router = APIRouter()


def var_pct(actual, compare):
    return round((actual - compare) / compare * 100, 1) if compare else 0.0


@router.get("/market", response_model=TreeTableSpec)
def get_market_view(year: int = 2025, quarter: str | None = None, market_id: str | None = None, ta: str | None = None):
    comm = data_loader.commercial
    prods = data_loader.products

    if ta:
        ta_list = [t.strip() for t in ta.split(",")]
        ta_brands = prods[prods.therapeutic_area.isin(ta_list)].brand_id.tolist()
        comm = comm[comm.brand_id.isin(ta_brands)]
    if market_id:
        mkt_list = [m.strip() for m in market_id.split(",")]
        comm = comm[comm.market_id.isin(mkt_list)]

    c = comm[comm.period_date.dt.year == year]
    c_py = comm[comm.period_date.dt.year == year - 1]
    if quarter:
        q_num = int(quarter[1])
        c = c[c.period_date.dt.quarter == q_num]
        c_py = c_py[c_py.period_date.dt.quarter == q_num]

    # Full year for sparklines (monthly share %)
    c_full = comm[comm.period_date.dt.year == year]

    # Category-level aggregation
    cat_groups = c.groupby("category")
    cat_py_groups = c_py.groupby("category")

    cat_children: list[TreeNode] = []

    for category in sorted(c.category.unique()):
        cat_data = cat_groups.get_group(category)
        cat_brands = cat_data.brand_id.unique().tolist()

        # Brand-level nodes within this category
        brand_children: list[TreeNode] = []
        for brand_id in cat_brands:
            b = cat_data[cat_data.brand_id == brand_id]
            b_py = c_py[(c_py.category == category) & (c_py.brand_id == brand_id)]

            az_rev = b.az_revenue_usd_m.sum()
            mkt_size = b.total_market_size_usd_m.sum()
            share = round(az_rev / mkt_size * 100, 1) if mkt_size > 0 else 0.0
            growth = round(b.market_growth_pct.mean(), 1)

            # PY share for delta
            py_rev = b_py.az_revenue_usd_m.sum() if not b_py.empty else 0
            py_mkt = b_py.total_market_size_usd_m.sum() if not b_py.empty else 0
            py_share = round(py_rev / py_mkt * 100, 1) if py_mkt > 0 else 0.0
            share_delta = round(share - py_share, 1)

            # Monthly share sparkline
            b_full = c_full[(c_full.category == category) & (c_full.brand_id == brand_id)]
            monthly = b_full.groupby(b_full.period_date.dt.month).agg(
                az=("az_revenue_usd_m", "sum"),
                mkt=("total_market_size_usd_m", "sum"),
            )
            monthly = monthly.reindex(range(1, 13), fill_value=0)
            spark = [(round(r.az / r.mkt * 100, 1) if r.mkt > 0 else 0.0) for _, r in monthly.iterrows()]

            # Get brand name from products
            name_row = prods[prods.brand_id == brand_id]
            name = name_row.brand_name.values[0] if len(name_row) > 0 else brand_id

            brand_children.append(TreeNode(
                id=f"{category}_{brand_id}",
                name=name,
                values=TreeNodeValues(
                    actual=round(az_rev, 1),
                    budget=round(mkt_size, 1),
                    variance_pct=share_delta,  # Share Δ vs PY (pp)
                    py_variance_pct=growth,     # Market growth %
                    sparkline=spark,            # Monthly share %
                    market_share_pct=share,     # Absolute share
                ),
            ))

        # Category subtotal
        cat_az = sum(ch.values.actual for ch in brand_children)
        cat_mkt = sum(ch.values.budget for ch in brand_children)
        cat_share = round(cat_az / cat_mkt * 100, 1) if cat_mkt > 0 else 0.0

        # Category PY share
        if category in cat_py_groups.groups:
            cp = cat_py_groups.get_group(category)
            cat_py_rev = cp.az_revenue_usd_m.sum()
            cat_py_mkt = cp.total_market_size_usd_m.sum()
            cat_py_share = round(cat_py_rev / cat_py_mkt * 100, 1) if cat_py_mkt > 0 else 0.0
        else:
            cat_py_share = 0.0

        cat_share_delta = round(cat_share - cat_py_share, 1)
        cat_growth = round(cat_data.market_growth_pct.mean(), 1)

        # Category monthly share sparkline
        cf = c_full[c_full.category == category]
        cm = cf.groupby(cf.period_date.dt.month).agg(
            az=("az_revenue_usd_m", "sum"),
            mkt=("total_market_size_usd_m", "sum"),
        )
        cm = cm.reindex(range(1, 13), fill_value=0)
        cat_spark = [(round(r.az / r.mkt * 100, 1) if r.mkt > 0 else 0.0) for _, r in cm.iterrows()]

        cat_children.append(TreeNode(
            id=category,
            name=category,
            values=TreeNodeValues(
                actual=round(cat_az, 1),
                budget=round(cat_mkt, 1),
                variance_pct=cat_share_delta,
                py_variance_pct=cat_growth,
                sparkline=cat_spark,
                market_share_pct=cat_share,
            ),
            children=brand_children,
        ))

    # Grand total
    grand_az = sum(ch.values.actual for ch in cat_children)
    grand_mkt = sum(ch.values.budget for ch in cat_children)
    grand_share = round(grand_az / grand_mkt * 100, 1) if grand_mkt > 0 else 0.0

    grand_py_rev = c_py.az_revenue_usd_m.sum()
    grand_py_mkt = c_py.total_market_size_usd_m.sum()
    grand_py_share = round(grand_py_rev / grand_py_mkt * 100, 1) if grand_py_mkt > 0 else 0.0
    grand_share_delta = round(grand_share - grand_py_share, 1)
    grand_growth = round(c.market_growth_pct.mean(), 1)

    gf = c_full.groupby(c_full.period_date.dt.month).agg(
        az=("az_revenue_usd_m", "sum"),
        mkt=("total_market_size_usd_m", "sum"),
    )
    gf = gf.reindex(range(1, 13), fill_value=0)
    grand_spark = [(round(r.az / r.mkt * 100, 1) if r.mkt > 0 else 0.0) for _, r in gf.iterrows()]

    period_label = f"{'Q' + quarter[1] + ' ' if quarter else 'FY '}{year}"

    return TreeTableSpec(
        period_label=period_label,
        columns=["Name", "AZ Rev", "Shr Δ", "Mkt Grw", "Share", "Trend"],
        tree=TreeNode(
            id="TOTAL_AZ_MARKET",
            name="Total AZ",
            values=TreeNodeValues(
                actual=round(grand_az, 1),
                budget=round(grand_mkt, 1),
                variance_pct=grand_share_delta,
                py_variance_pct=grand_growth,
                sparkline=grand_spark,
                market_share_pct=grand_share,
            ),
            children=cat_children,
        ),
    )
