"""FastAPI routes for Book Trading Simulator — aligned with proto/trading/trading.proto."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import Database
from models import (
    ConfigUpdate, ConfigResponse,
    OrderRequest,
    TradeRecord, TradeRecordsResponse,
    AccountSummary,
    HealthStatus, MarketStatus,
    ErrorResponse, QuoteResponse,
)
import services

logger = logging.getLogger("book_simulator.api")

router = APIRouter(prefix="/api")

# Injected by main.py on startup
db: Database
_token_cache: str = ""


def init(db_instance: Database):
    global db
    db = db_instance


def _get_token() -> str:
    """Get the iTick token from config. Cached for reuse."""
    global _token_cache
    stored = db.get_config("itick_token") or ""
    if stored:
        _token_cache = stored
    return _token_cache


def _mask_token(token: str) -> str:
    """Mask token for safe display."""
    if len(token) > 8:
        return token[:4] + "****" + token[-4:]
    return "****"


#
# Health
#

@router.get("/health")
def get_health() -> HealthStatus:
    db_ok = True
    try:
        db.get_db().execute("SELECT 1")
    except Exception:
        db_ok = False

    token = _get_token()
    itick_ok = bool(token)

    is_open, _, _ = services.is_asx_market_open()

    import logging
    debug_on = logging.getLogger("book_simulator").level <= logging.DEBUG

    return HealthStatus(
        database=db_ok,
        itick_configured=itick_ok,
        market_open=is_open,
    )


#
# Debug — toggle debug logging at runtime
#

@router.get("/debug")
def get_debug_status() -> dict:
    """Check whether debug logging is enabled."""
    import logging
    root = logging.getLogger("book_simulator")
    debug_on = root.level <= logging.DEBUG
    return {
        "debug_enabled": debug_on,
        "current_level": logging.getLevelName(root.level),
        "hint": "Set LOG_LEVEL=DEBUG env var, or POST /api/debug/toggle to switch at runtime.",
    }


@router.post("/debug/toggle")
def toggle_debug() -> dict:
    """Toggle debug logging on/off at runtime."""
    import logging
    root = logging.getLogger("book_simulator")
    if root.level <= logging.DEBUG:
        root.setLevel(logging.INFO)
        for h in root.handlers:
            h.setLevel(logging.INFO)
        logger.info("Debug logging DISABLED (level=INFO)")
        return {"debug_enabled": False, "level": "INFO"}
    else:
        root.setLevel(logging.DEBUG)
        for h in root.handlers:
            h.setLevel(logging.DEBUG)
        logger.info("Debug logging ENABLED (level=DEBUG)")
        return {"debug_enabled": True, "level": "DEBUG"}


#
# Market Status
#

@router.get("/market-status")
def get_market_status() -> MarketStatus:
    is_open, reason, sydney_time = services.is_asx_market_open()
    return MarketStatus(
        is_open=is_open,
        reason=reason,
        current_sydney_time=sydney_time,
    )


#
# Quote — real-time price lookup, no market-hours restriction
#

@router.get("/quote")
def get_quote(exchange: str = Query("AU"), symbol: str = Query(...)) -> QuoteResponse:
    """Fetch a live stock quote. No trading — works regardless of market hours."""
    token = _get_token()
    if not token:
        raise HTTPException(status_code=400, detail="iTick token not configured. Please set it in Config first.")

    logger.debug(f"[API QUOTE] exchange={exchange}  symbol={symbol}")

    try:
        quote = services.fetch_stock_quote(token, exchange, symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quote failed: {e}")

    from datetime import datetime, timezone
    result = QuoteResponse(
        exchange=exchange.upper(),
        symbol=symbol.upper(),
        current_price=quote.get("current_price", 0.0) or 0.0,
        open_price=quote.get("open_price", 0.0) or 0.0,
        high_price=quote.get("high_price", 0.0) or 0.0,
        low_price=quote.get("low_price", 0.0) or 0.0,
        previous_close=quote.get("previous_close", 0.0) or 0.0,
        volume=quote.get("volume", 0.0) or 0.0,
        change=quote.get("change", 0.0) or 0.0,
        change_pct=quote.get("change_pct", 0.0) or 0.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    logger.debug(
        f"[API QUOTE RESPONSE] symbol={result.symbol}  current_price={result.current_price}  "
        f"open_price={result.open_price}  high_price={result.high_price}  low_price={result.low_price}  "
        f"volume={result.volume}  change={result.change}"
    )
    return result


#
# Config
#

@router.get("/config")
def get_config() -> ConfigResponse:
    initial_fund = db.get_config_float("initial_fund", 0.0)
    token = _get_token()
    balances = services.get_all_exchange_balances(db)
    return ConfigResponse(
        initial_fund=initial_fund,
        exchange_balances=balances,
        itick_token_masked=_mask_token(token),
    )


@router.put("/config")
def update_config(body: ConfigUpdate) -> ConfigResponse:
    global _token_cache
    db.set_config("initial_fund", str(body.initial_fund))
    db.set_config("itick_token", body.itick_token)
    _token_cache = body.itick_token

    # Seed all exchange fund balances to initial_fund
    services.seed_exchange_funds(db, body.initial_fund)

    balances = services.get_all_exchange_balances(db)
    return ConfigResponse(
        initial_fund=body.initial_fund,
        exchange_balances=balances,
        itick_token_masked=_mask_token(body.itick_token),
    )


#
# Trading
#

@router.post("/order")
def submit_order(body: OrderRequest) -> TradeRecord:
    token = _get_token()
    if not token:
        raise HTTPException(status_code=400, detail="iTick token not configured. Please set it in Config first.")

    logger.debug(
        f"[API ORDER] side={body.side}  exchange={body.exchange}  "
        f"symbol={body.symbol}  quantity={body.quantity}  "
        f"price={body.price}  order_type={body.order_type}"
    )
    try:
        result = services.submit_order(
            db, token, body.exchange, body.side,
            body.symbol, body.quantity, body.price, body.order_type,
        )
        logger.debug(
            f"[API ORDER RESPONSE] trade_id={result.trade_id}  symbol={result.symbol}  "
            f"side={result.side}  filled_quantity={result.filled_quantity}  "
            f"filled_price={result.filled_price}  total_amount={result.total_amount}  "
            f"remaining_cash={result.remaining_cash}"
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in submit_order")
        raise HTTPException(status_code=500, detail=f"Order failed: {e}")


#
# Records & Account
#

@router.get("/records")
def list_records(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    exchange: str = Query(None),
) -> TradeRecordsResponse:
    trades_raw = db.list_trades(limit, offset, region=exchange)
    trades = []
    for t in trades_raw:
        d = dict(t)
        if not d.get("exchange"):
            d["exchange"] = d.get("region", "AU")
        trades.append(TradeRecord(
            trade_id=d.get("id", ""),
            status="FILLED",
            exchange=d.get("exchange", "AU"),
            symbol=d.get("symbol", ""),
            side=d.get("action", "BUY"),
            filled_quantity=d.get("quantity", 0),
            filled_price=d.get("price", 0.0),
            total_amount=d.get("total_value", 0.0),
            commission=0.0,
            remaining_cash=d.get("fund_balance_after", 0.0),
            message="",
            executed_at=d.get("timestamp", ""),
        ))

    token = _get_token()
    try:
        account = services.get_account_summary(db, token)
    except Exception:
        # Fallback if iTick is unavailable
        initial_fund = db.get_config_float("initial_fund", 0.0)
        balances = services.get_all_exchange_balances(db)
        total_cash = sum(balances.values())
        total_initial = initial_fund * len(services.EXCHANGES)
        account = AccountSummary(
            exchange="",
            cash=total_cash,
            holdings=[],
            total_holdings_value=0.0,
            total_portfolio_value=total_cash,
            total_unrealized_pnl=total_cash - total_initial,
            total_unrealized_pnl_pct=((total_cash - total_initial) / total_initial * 100) if total_initial > 0 else 0.0,
            initial_fund=initial_fund,
            exchange_balances=balances,
        )

    return TradeRecordsResponse(trades=trades, account=account)


@router.get("/account")
def get_account() -> AccountSummary:
    token = _get_token()
    try:
        return services.get_account_summary(db, token)
    except Exception as e:
        # Fallback if iTick is unavailable
        logger.warning(f"Account summary fallback (iTick unavailable): {e}")
        initial_fund = db.get_config_float("initial_fund", 0.0)
        balances = services.get_all_exchange_balances(db)
        total_cash = sum(balances.values())
        total_initial = initial_fund * len(services.EXCHANGES)
        return AccountSummary(
            exchange="",
            cash=total_cash,
            holdings=[],
            total_holdings_value=0.0,
            total_portfolio_value=total_cash,
            total_unrealized_pnl=total_cash - total_initial,
            total_unrealized_pnl_pct=((total_cash - total_initial) / total_initial * 100) if total_initial > 0 else 0.0,
            initial_fund=initial_fund,
            exchange_balances=balances,
        )
