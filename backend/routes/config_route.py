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
