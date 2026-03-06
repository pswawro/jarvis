from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import data_loader
from routes import kpi, brand, region, unit, chart, market, assistant


@asynccontextmanager
async def lifespan(app: FastAPI):
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
