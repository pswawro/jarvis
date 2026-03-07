import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the project root (one level above backend/) before importing config
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import config  # noqa: E402 — must come after load_dotenv
import data_loader
from routes import kpi, brand, region, unit, chart, market, assistant, config_route, export, landing, phased, tree_generic

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = "explicit env vars" if config.AWS_ACCESS_KEY_ID else "default credential chain"
    log.info("AWS credentials source: %s", source)
    data_loader.load_all()
    # Pre-build semantic model so first assistant request is fast
    from routes.assistant import get_semantic_model
    get_semantic_model()
    yield


app = FastAPI(title="Jarvis Analytics", lifespan=lifespan)

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(kpi.router, prefix="/api")
app.include_router(brand.router, prefix="/api")
app.include_router(region.router, prefix="/api")
app.include_router(unit.router, prefix="/api")
app.include_router(chart.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
app.include_router(config_route.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(landing.router, prefix="/api")
app.include_router(phased.router, prefix="/api")
app.include_router(tree_generic.router, prefix="/api")
