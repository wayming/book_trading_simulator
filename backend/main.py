"""FastAPI application for Book Trading Simulator."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
from database import Database
from logging_config import setup_logging
import api_routes

setup_logging("book_simulator")
logger = logging.getLogger("book_simulator.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    db = Database()
    db.create_schema()

    # Seed default config from env vars if not already set
    if db.get_config("initial_fund") is None:
        db.set_config("initial_fund", str(config.INITIAL_FUND))
    if db.get_config("itick_token") is None:
        db.set_config("itick_token", config.ITICK_TOKEN)
    if db.get_config("fund_balance") is None:
        db.set_config("fund_balance", str(config.INITIAL_FUND))

    # Inject dependencies
    api_routes.init(db)

    logger.info("Book Trading Simulator backend ready.")
    yield

    db.close()
    logger.info("Book Trading Simulator shutdown complete.")


app = FastAPI(
    title="Book Trading Simulator",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_routes.router)


@app.get("/")
def root():
    return {"service": "Book Trading Simulator", "version": "0.1.0"}
