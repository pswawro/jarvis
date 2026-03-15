import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import config
import data_loader
from routes import kpi, brand, region, unit, chart, market, assistant, config_route, export, landing, phased, tree_generic, insights_route
from rate_limit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    source = "explicit env vars" if config.AWS_ACCESS_KEY_ID else "default credential chain"
    log.info("AWS credentials source: %s", source)
    data_loader.load_all()
    from assistant.semantic_model import get_semantic_model
    get_semantic_model()
    yield


app = FastAPI(title="Jarvis Analytics", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:4173")
CORS_ORIGINS = [o.strip() for o in _cors_raw.split(",")]
if "*" in CORS_ORIGINS:
    log.warning("CORS_ORIGINS contains wildcard '*' — this is insecure in production")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-User-Id"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(KeyError)
async def key_error_handler(request: Request, exc: KeyError):
    log.warning("Missing data key: %s on %s %s", exc, request.method, request.url.path)
    return JSONResponse(status_code=400, content={"detail": f"Missing data column: {exc}"})


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
app.include_router(insights_route.router, prefix="/api")
