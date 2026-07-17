"""FastAPI routes for Book Trading Simulator."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from database import Database
from models import (
    ConfigUpdate, ConfigResponse,
    BuyRequest, SellRequest,
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
def get_quote(region: str = Query("AU"), symbol: str = Query(...)) -> QuoteResponse:
    """Fetch a live stock quote. No trading — works regardless of market hours."""
    token = _get_token()
    if not token:
        raise HTTPException(status_code=400, detail="iTick token not configured. Please set it in Config first.")

    logger.debug(f"[API QUOTE] region={region}  symbol={symbol}")

    try:
        quote = services.fetch_stock_quote(token, region, symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Quote failed: {e}")

    from datetime import datetime, timezone
    result = QuoteResponse(
        symbol=symbol.upper(),
        region=region.upper(),
        price=quote.get("ld", 0.0) or 0.0,
        open=quote.get("o", 0.0) or 0.0,
        high=quote.get("h", 0.0) or 0.0,
        low=quote.get("l", 0.0) or 0.0,
        volume=quote.get("v", 0.0) or 0.0,
        change=quote.get("ch", 0.0) or 0.0,
        change_pct=quote.get("chp", 0.0) or 0.0,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    logger.debug(
        f"[API QUOTE RESPONSE] symbol={result.symbol}  price={result.price}  "
        f"open={result.open}  high={result.high}  low={result.low}  "
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
    balances = services.get_all_region_balances(db)
    return ConfigResponse(
        initial_fund=initial_fund,
        region_balances=balances,
        itick_token_masked=_mask_token(token),
    )


@router.put("/config")
def update_config(body: ConfigUpdate) -> ConfigResponse:
    global _token_cache
    db.set_config("initial_fund", str(body.initial_fund))
    db.set_config("itick_token", body.itick_token)
    _token_cache = body.itick_token

    # Seed all region fund balances to initial_fund
    services.seed_region_funds(db, body.initial_fund)

    balances = services.get_all_region_balances(db)
    return ConfigResponse(
        initial_fund=body.initial_fund,
        region_balances=balances,
        itick_token_masked=_mask_token(body.itick_token),
    )


#
# Trading
#

@router.post("/buy")
def buy_stock(body: BuyRequest) -> TradeRecord:
    token = _get_token()
    if not token:
        raise HTTPException(status_code=400, detail="iTick token not configured. Please set it in Config first.")

    logger.debug(
        f"[API BUY] region={body.region}  fund_amount={body.fund_amount}  "
        f"symbol={body.symbol}"
    )
    try:
        result = services.buy_stock(db, token, body.region, body.fund_amount, body.symbol)
        logger.debug(
            f"[API BUY RESPONSE] id={result.id}  symbol={result.symbol}  "
            f"qty={result.quantity}  price={result.price}  "
            f"total={result.total_value}  fund_after={result.fund_balance_after}"
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in buy")
        raise HTTPException(status_code=500, detail=f"Buy failed: {e}")


@router.post("/sell")
def sell_stock(body: SellRequest) -> TradeRecord:
    token = _get_token()
    if not token:
        raise HTTPException(status_code=400, detail="iTick token not configured. Please set it in Config first.")

    logger.debug(f"[API SELL] symbol={body.symbol}  region={body.region}")
    try:
        result = services.sell_stock(db, token, body.symbol, body.region)
        logger.debug(
            f"[API SELL RESPONSE] id={result.id}  symbol={result.symbol}  "
            f"qty={result.quantity}  price={result.price}  "
            f"total={result.total_value}  fund_after={result.fund_balance_after}"
        )
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("Unexpected error in sell")
        raise HTTPException(status_code=500, detail=f"Sell failed: {e}")


#
# Records & Account
#

@router.get("/records")
def list_records(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    region: str = Query(None),
) -> TradeRecordsResponse:
    trades_raw = db.list_trades(limit, offset, region=region)
    trades = []
    for t in trades_raw:
        d = dict(t)
        if not d.get("region"):
            d["region"] = "AU"
        trades.append(TradeRecord(**d))

    token = _get_token()
    try:
        account = services.get_account_summary(db, token)
    except Exception:
        # Fallback if iTick is unavailable
        initial_fund = db.get_config_float("initial_fund", 0.0)
        fund_balance = db.get_config_float("fund_balance", initial_fund)
        balances = services.get_all_region_balances(db)
        total_fb = sum(balances.values())
        total_initial = initial_fund * len(services.REGIONS)
        account = AccountSummary(
            initial_fund=initial_fund,
            fund_balance=total_fb,
            total_holdings_value=0.0,
            total_portfolio_value=total_fb,
            total_pnl=total_fb - total_initial,
            total_pnl_pct=((total_fb - total_initial) / total_initial * 100) if total_initial > 0 else 0.0,
            region_balances=balances,
            holdings=[],
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
        balances = services.get_all_region_balances(db)
        total_fb = sum(balances.values())
        total_initial = initial_fund * len(services.REGIONS)
        return AccountSummary(
            initial_fund=initial_fund,
            fund_balance=total_fb,
            total_holdings_value=0.0,
            total_portfolio_value=total_fb,
            total_pnl=total_fb - total_initial,
            total_pnl_pct=((total_fb - total_initial) / total_initial * 100) if total_initial > 0 else 0.0,
            region_balances=balances,
            holdings=[],
        )
