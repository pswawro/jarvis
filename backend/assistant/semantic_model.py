"""Builds a rich description of the data domain from dimension tables."""

from pathlib import Path

import data_loader

_SEMANTIC_MODEL: str = ""
_TEMPLATE: str = ""


def _load_template() -> str:
    global _TEMPLATE
    if not _TEMPLATE:
        _TEMPLATE = (Path(__file__).parent / "prompts" / "semantic_model.txt").read_text()
    return _TEMPLATE


def _build_semantic_model() -> str:
    prods = data_loader.products
    geos = data_loader.geographies
    orgs = data_loader.organization
    cats = sorted(data_loader.commercial["category"].unique())

    # Group brands by TA
    ta_brands: dict[str, list[dict]] = {}
    for _, row in prods.iterrows():
        ta_brands.setdefault(row["therapeutic_area"], []).append({
            "id": row["brand_id"],
            "name": row["brand_name"],
            "indication": row["indication"],
        })

    # Group sub-units by unit
    unit_subs: dict[str, list[dict]] = {}
    for _, row in orgs.iterrows():
        unit_subs.setdefault(row["unit"], []).append({
            "id": row["sub_unit_id"],
            "name": row["sub_unit_name"],
        })

    # Render dynamic sections
    portfolio = "\n".join(
        f"**{ta}**: " + ", ".join(f"{b['name']} ({b['id']}) — {b['indication']}" for b in brands)
        for ta, brands in ta_brands.items()
    )

    markets = "\n".join(
        f"- {row['market_name']} ({row['market_id']}) — Region: {row['region']}"
        for _, row in geos.iterrows()
    )

    org_structure = "\n".join(
        f"**{unit}**: " + ", ".join(f"{s['name']} ({s['id']})" for s in subs)
        for unit, subs in unit_subs.items()
    )

    brand_count = sum(len(b) for b in ta_brands.values())

    return (_load_template()
            .replace("{{brand_count}}", str(brand_count))
            .replace("{{portfolio}}", portfolio)
            .replace("{{markets}}", markets)
            .replace("{{org_structure}}", org_structure)
            .replace("{{categories}}", ", ".join(cats)))


def get_semantic_model() -> str:
    global _SEMANTIC_MODEL
    if not _SEMANTIC_MODEL:
        _SEMANTIC_MODEL = _build_semantic_model()
    return _SEMANTIC_MODEL
