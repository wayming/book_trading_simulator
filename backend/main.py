"""FastAPI application for Book Trading Simulator."""

import logging
import time
from concurrent import futures
from contextlib import asynccontextmanager

import grpc
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

import config
from database import Database
from logging_config import setup_logging
import api_routes

# gRPC imports — add stubs path before importing generated code
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "grpc_stubs"))
import trading_pb2_grpc
from grpc_server import GrpcTradingService

setup_logging("book_simulator")
logger = logging.getLogger("book_simulator.main")
trace_logger = logging.getLogger("book_simulator.http")

# Confirm log level at startup
_root_log = logging.getLogger("book_simulator")
_level_name = logging.getLevelName(_root_log.level)
logger.info(f"Log level configured: {_level_name} (set LOG_LEVEL env var to change)")
logger.debug("DEBUG logging is ENABLED — this message confirms it works")


class TraceMiddleware:
    """Pure ASGI middleware — logs every HTTP request and response with timing.
    Avoids BaseHTTPMiddleware which can interfere with FastAPI lifespan events."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        method = scope.get("method", "?")
        path = scope.get("path", "/")
        qs = scope.get("query_string", b"")
        qs_str = f"?{qs.decode()}" if qs else ""

        # Client IP
        client = "unknown"
        if scope.get("client"):
            client = scope["client"][0]

        trace_logger.info(f"--> {method} {path}{qs_str}  [client={client}]")

        # Capture status code from response
        status_code = 0

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            trace_logger.info(
                f"<-- {method} {path}  {status_code}  {elapsed_ms:.1f}ms"
            )


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
    import services
    services.seed_exchange_funds(db, config.INITIAL_FUND)

    # Inject dependencies
    api_routes.init(db)

    # Start gRPC server on port 50051
    grpc_server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    trading_pb2_grpc.add_TradingServiceServicer_to_server(
        GrpcTradingService(db), grpc_server
    )
    grpc_server.add_insecure_port("0.0.0.0:50051")
    grpc_server.start()
    logger.info("gRPC server listening on port 50051")

    logger.info("Book Trading Simulator backend ready.")
    yield

    # Shutdown
    grpc_server.stop(grace=5)
    db.close()
    logger.info("Book Trading Simulator shutdown complete.")


app = FastAPI(
    title="Book Trading Simulator",
    version="0.1.0",
    lifespan=lifespan,
)

# Trace middleware — added first (wraps all others) as raw ASGI middleware
app.add_middleware(TraceMiddleware)

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
