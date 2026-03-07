"""Config endpoint — serves config.json and data freshness timestamp."""

from fastapi import APIRouter

import data_loader

router = APIRouter()


@router.get("/config")
def get_config():
    cfg = dict(data_loader.app_config)
    cfg["data_refreshed_at"] = data_loader.data_refreshed_at
    return cfg
