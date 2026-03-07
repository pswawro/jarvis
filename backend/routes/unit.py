from fastapi import APIRouter, Query

import data_loader
from models import TreeTableSpec, TreeNode, TreeNodeValues
from routes.shared import validate_params, var_pct, period_label, COMPARATOR_FIELD, COMPARATOR_LABELS

router = APIRouter()


@router.get("/unit", response_model=TreeTableSpec)
def get_unit_view(year: int = 2025, quarter: str | None = None, comparator: str = "BUD"):
    validate_params(year=year, quarter=quarter, comparator=comparator)
    exp = data_loader.expenses
    org = data_loader.organization
    tgt = data_loader.targets[data_loader.targets.target_type == "expense"]
    hc = data_loader.headcount

    e = exp[exp.year == year]
    t = tgt[tgt.period_date.dt.year == year]
    h = hc[hc.year == year]
    if quarter:
        q_num = int(quarter[1])
        e = e[e.quarter == quarter]
        t = t[t.period_date.dt.quarter == q_num]
        h = h[h.quarter == quarter]

    e_py = exp[exp.year == year - 1]
    if quarter:
        e_py = e_py[e_py.quarter == quarter]

    e_full = exp[exp.year == year]
    comp_label = COMPARATOR_LABELS.get(comparator, comparator)

    cost_cols = ["total_operating_expenses", "personnel_costs", "external_costs", "other_costs"]
    sub_agg = e.groupby("sub_unit_id")[cost_cols].sum()
    sub_targets = t.groupby("entity_id")[["budget_amount", "forecast_amount", "mtp_amount", "rbu2_amount"]].sum()
    sub_py = e_py.groupby("sub_unit_id")["total_operating_expenses"].sum()

    # Pre-compute sparklines in bulk
    sub_month_exp = e_full.groupby(["sub_unit_id", "month"])["total_operating_expenses"].sum().unstack(fill_value=0).reindex(columns=range(1, 13), fill_value=0)

    # FTE aggregation
    sub_fte = h.groupby("sub_unit_id")["fte_count"].mean()
    sub_hc = h.groupby("sub_unit_id")["headcount"].max()

    # Build tree: Total AZ → Units → Sub-units
    unit_map: dict[str, list[TreeNode]] = {}
    for _, row in org.iterrows():
        sid = row.sub_unit_id
        unit_name = row.unit
        if sid in sub_agg.index:
            agg_row = sub_agg.loc[sid]
            actual = float(agg_row["total_operating_expenses"])
            personnel = float(agg_row["personnel_costs"])
            external = float(agg_row["external_costs"])
            other = float(agg_row["other_costs"])
        else:
            actual = personnel = external = other = 0.0
        if sid in sub_targets.index:
            tgt_row = sub_targets.loc[sid]
            budget = float(tgt_row["budget_amount"])
            forecast = float(tgt_row["forecast_amount"])
            mtp = float(tgt_row["mtp_amount"])
            rbu2 = float(tgt_row["rbu2_amount"])
        else:
            budget = forecast = mtp = rbu2 = 0.0
        py = float(sub_py.get(sid, 0))
        fte = float(sub_fte.get(sid, 0))
        headcount = int(sub_hc.get(sid, 0))
        cost_per_fte = round(actual / fte, 2) if fte > 0 else None

        spark = [round(v, 1) for v in sub_month_exp.loc[sid].values] if sid in sub_month_exp.index else [0.0] * 12

        comp_val = py if comparator == "PYACT" else {"BUD": budget, "MTP": mtp, "RBU2": rbu2}.get(comparator, budget)

        node = TreeNode(
            id=sid,
            name=row.sub_unit_name,
            values=TreeNodeValues(
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
                personnel_costs=round(personnel, 1),
                external_costs=round(external, 1),
                other_costs=round(other, 1),
                fte_count=round(fte, 1),
                headcount=headcount,
                cost_per_fte=cost_per_fte,
            ),
        )
        unit_map.setdefault(unit_name, []).append(node)

    unit_children = []
    for unit_name, subs in unit_map.items():
        u_actual = sum(s.values.actual for s in subs)
        u_budget = sum(s.values.budget for s in subs)
        u_forecast = sum(s.values.forecast or 0 for s in subs)
        u_mtp = sum(s.values.mtp or 0 for s in subs)
        u_rbu2 = sum(s.values.rbu2 or 0 for s in subs)
        u_py = sum(s.values.prior_year or 0 for s in subs)
        u_personnel = sum(s.values.personnel_costs or 0 for s in subs)
        u_external = sum(s.values.external_costs or 0 for s in subs)
        u_other = sum(s.values.other_costs or 0 for s in subs)
        u_fte = sum(s.values.fte_count or 0 for s in subs)
        u_hc = sum(s.values.headcount or 0 for s in subs)
        u_spark = [round(sum(s.values.sparkline[i] for s in subs), 1) for i in range(12)]
        u_comp = u_py if comparator == "PYACT" else {"BUD": u_budget, "MTP": u_mtp, "RBU2": u_rbu2}.get(comparator, u_budget)

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
                mtp=round(u_mtp, 1),
                mtp_variance_pct=var_pct(u_actual, u_mtp),
                rbu2=round(u_rbu2, 1),
                rbu2_variance_pct=var_pct(u_actual, u_rbu2),
                comparator_label=comp_label,
                comparator_value=round(u_comp, 1),
                comparator_variance_pct=var_pct(u_actual, u_comp),
                personnel_costs=round(u_personnel, 1),
                external_costs=round(u_external, 1),
                other_costs=round(u_other, 1),
                fte_count=round(u_fte, 1),
                headcount=u_hc,
                cost_per_fte=round(u_actual / u_fte, 2) if u_fte > 0 else None,
            ),
            children=subs,
        ))

    grand_actual = sum(c.values.actual for c in unit_children)
    grand_budget = sum(c.values.budget for c in unit_children)
    grand_forecast = sum(c.values.forecast or 0 for c in unit_children)
    grand_mtp = sum(c.values.mtp or 0 for c in unit_children)
    grand_rbu2 = sum(c.values.rbu2 or 0 for c in unit_children)
    grand_py = sum(c.values.prior_year or 0 for c in unit_children)
    grand_personnel = sum(c.values.personnel_costs or 0 for c in unit_children)
    grand_external = sum(c.values.external_costs or 0 for c in unit_children)
    grand_other = sum(c.values.other_costs or 0 for c in unit_children)
    grand_fte = sum(c.values.fte_count or 0 for c in unit_children)
    grand_hc = sum(c.values.headcount or 0 for c in unit_children)
    grand_spark = e_full.groupby("month")["total_operating_expenses"].sum().reindex(range(1, 13), fill_value=0)
    grand_comp = grand_py if comparator == "PYACT" else {"BUD": grand_budget, "MTP": grand_mtp, "RBU2": grand_rbu2}.get(comparator, grand_budget)

    return TreeTableSpec(
        period_label=period_label(year, quarter),
        columns=["Name", "Actual", f"vs {comp_label}", "FTE", "$/FTE", "Trend"],
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
                mtp=round(grand_mtp, 1),
                mtp_variance_pct=var_pct(grand_actual, grand_mtp),
                rbu2=round(grand_rbu2, 1),
                rbu2_variance_pct=var_pct(grand_actual, grand_rbu2),
                comparator_label=comp_label,
                comparator_value=round(grand_comp, 1),
                comparator_variance_pct=var_pct(grand_actual, grand_comp),
                personnel_costs=round(grand_personnel, 1),
                external_costs=round(grand_external, 1),
                other_costs=round(grand_other, 1),
                fte_count=round(grand_fte, 1),
                headcount=grand_hc,
                cost_per_fte=round(grand_actual / grand_fte, 2) if grand_fte > 0 else None,
            ),
            children=unit_children,
        ),
    )
