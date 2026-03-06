import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load .env from the project root (one level above backend/) before importing config
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import config  # noqa: E402 — must come after load_dotenv
import data_loader
from routes import kpi, brand, region, unit, chart, market, assistant

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Log which AWS identity will be used so credential issues are obvious
    key = config.AWS_ACCESS_KEY_ID
    source = f"key {key[:8]}…{key[-4:]}" if key else "default credential chain (~/.aws/credentials / IAM role)"
    log.info("AWS credentials source: %s", source)
    data_loader.load_all()
    yield


app = FastAPI(title="Jarvis Analytics", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(kpi.router, prefix="/api")
app.include_router(brand.router, prefix="/api")
app.include_router(region.router, prefix="/api")
app.include_router(unit.router, prefix="/api")
app.include_router(chart.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")
