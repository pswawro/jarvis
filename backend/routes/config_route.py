"""Config endpoint — serves config.json and data freshness timestamp."""

from fastapi import APIRouter

import data_loader
import config as app_config

router = APIRouter()


@router.get("/config")
def get_config():
    cfg = dict(data_loader.app_config)
    cfg["data_refreshed_at"] = data_loader.data_refreshed_at
    cfg["vapid_public_key"] = app_config.VAPID_PUBLIC_KEY
    return cfg


@router.get("/config/filters")
def get_filter_options():
    """Return available filter options derived from loaded data."""
    prods = data_loader.products
    geo = data_loader.geographies

    markets = [
        {"id": row.market_id, "label": row.market_name}
        for _, row in geo[["market_id", "market_name"]].drop_duplicates().iterrows()
    ]
    tas = sorted(prods["therapeutic_area"].dropna().unique().tolist())
    products = [
        {"id": row.brand_id, "label": row.brand_name, "ta": row.therapeutic_area}
        for _, row in prods[["brand_id", "brand_name", "therapeutic_area"]].drop_duplicates().iterrows()
    ]

    return {"markets": markets, "tas": tas, "products": products}
