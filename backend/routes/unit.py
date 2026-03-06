from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues

router = APIRouter()


@router.get("/unit", response_model=TreeTableSpec)
def get_unit_view(year: int = 2025, quarter: str | None = None):
    exp = data_loader.expenses
    org = data_loader.organization
    tgt = data_loader.targets[data_loader.targets.target_type == "expense"]

    e = exp[exp.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    if quarter:
        q_num = int(quarter[1])
        e = e[e.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]

    e_py = exp[exp.year == year - 1]
    if quarter:
        e_py = e_py[e_py.quarter == quarter]

    e_full = exp[exp.year == year]

    def var_pct(actual, compare):
        return round((actual - compare) / compare * 100, 1) if compare else 0.0

    cost_cols = ["total_operating_expenses", "personnel_costs", "external_costs", "other_costs"]
    sub_agg = e.groupby("sub_unit_id")[cost_cols].sum()
    sub_budget = t.groupby("entity_id")["budget_amount"].sum()
    sub_forecast = t.groupby("entity_id")["forecast_amount"].sum()
    sub_py = e_py.groupby("sub_unit_id")["total_operating_expenses"].sum()

    # Build tree: Total AZ → Units → Sub-units
    unit_map: dict[str, list[TreeNode]] = {}
    for _, row in org.iterrows():
        sid = row.sub_unit_id
        unit_name = row.unit
        actual = float(sub_agg.loc[sid, "total_operating_expenses"]) if sid in sub_agg.index else 0.0
        personnel = float(sub_agg.loc[sid, "personnel_costs"]) if sid in sub_agg.index else 0.0
        external = float(sub_agg.loc[sid, "external_costs"]) if sid in sub_agg.index else 0.0
        other = float(sub_agg.loc[sid, "other_costs"]) if sid in sub_agg.index else 0.0
        budget = float(sub_budget.get(sid, 0))
        forecast = float(sub_forecast.get(sid, 0))
        py = float(sub_py.get(sid, 0))

        spark = e_full[e_full.sub_unit_id == sid].groupby("month")["total_operating_expenses"].sum()
        spark = spark.reindex(range(1, 13), fill_value=0)

        node = TreeNode(
            id=sid,
            name=row.sub_unit_name,
            values=TreeNodeValues(
                actual=round(actual, 1),
                budget=round(budget, 1),
                variance_pct=var_pct(actual, budget),
                prior_year=round(py, 1),
                py_variance_pct=var_pct(actual, py),
                sparkline=[round(v, 1) for v in spark.values],
                forecast=round(forecast, 1),
                forecast_variance_pct=var_pct(actual, forecast),
                personnel_costs=round(personnel, 1),
                external_costs=round(external, 1),
                other_costs=round(other, 1),
            ),
        )
        unit_map.setdefault(unit_name, []).append(node)

    unit_children = []
    for unit_name, subs in unit_map.items():
        u_actual = sum(s.values.actual for s in subs)
        u_budget = sum(s.values.budget for s in subs)
        u_forecast = sum(s.values.forecast or 0 for s in subs)
        u_py = sum(s.values.prior_year or 0 for s in subs)
        u_personnel = sum(s.values.personnel_costs or 0 for s in subs)
        u_external = sum(s.values.external_costs or 0 for s in subs)
        u_other = sum(s.values.other_costs or 0 for s in subs)
        u_spark = [
            round(sum(s.values.sparkline[i] for s in subs), 1) for i in range(12)
        ]

        unit_children.append(TreeNode(
            id=unit_name,
            name=unit_name,
            values=TreeNodeValues(
                actual=round(u_actual, 1),
                budget=round(u_budget, 1),
                variance_pct=var_pct(u_actual, u_budget),
                prior_year=round(u_py, 1),
                py_variance_pct=var_pct(u_actual, u_py),
                sparkline=u_spark,
                forecast=round(u_forecast, 1),
                forecast_variance_pct=var_pct(u_actual, u_forecast),
                personnel_costs=round(u_personnel, 1),
                external_costs=round(u_external, 1),
                other_costs=round(u_other, 1),
            ),
            children=subs,
        ))

    grand_actual = sum(c.values.actual for c in unit_children)
    grand_budget = sum(c.values.budget for c in unit_children)
    grand_forecast = sum(c.values.forecast or 0 for c in unit_children)
    grand_py = sum(c.values.prior_year or 0 for c in unit_children)
    grand_personnel = sum(c.values.personnel_costs or 0 for c in unit_children)
    grand_external = sum(c.values.external_costs or 0 for c in unit_children)
    grand_other = sum(c.values.other_costs or 0 for c in unit_children)
    grand_spark = e_full.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)

    period_label = f"{'Q' + quarter[1] + ' ' if quarter else 'FY '}{year}"

    return TreeTableSpec(
        period_label=period_label,
        columns=["Name", "Actual", "Forecast", "Personnel", "External", "Other", "vs Budget", "vs PY", "Trend"],
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
                personnel_costs=round(grand_personnel, 1),
                external_costs=round(grand_external, 1),
                other_costs=round(grand_other, 1),
            ),
            children=unit_children,
        ),
    )
