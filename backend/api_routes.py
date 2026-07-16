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
    ErrorResponse,
)
import services

logger = logging.getLogger(__name__)

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

    return HealthStatus(
        database=db_ok,
        itick_configured=itick_ok,
        market_open=is_open,
    )


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
# Config
#

@router.get("/config")
def get_config() -> ConfigResponse:
    initial_fund = db.get_config_float("initial_fund", 0.0)
    fund_balance = db.get_config_float("fund_balance", initial_fund)
    token = _get_token()
    return ConfigResponse(
        initial_fund=initial_fund,
        fund_balance=fund_balance,
        itick_token_masked=_mask_token(token),
    )


@router.put("/config")
def update_config(body: ConfigUpdate) -> ConfigResponse:
    global _token_cache
    db.set_config("initial_fund", str(body.initial_fund))
    db.set_config("itick_token", body.itick_token)
    _token_cache = body.itick_token

    # Initialize fund_balance to initial_fund if not already set
    if db.get_config("fund_balance") is None:
        db.set_config("fund_balance", str(body.initial_fund))

    fund_balance = db.get_config_float("fund_balance", body.initial_fund)
    return ConfigResponse(
        initial_fund=body.initial_fund,
        fund_balance=fund_balance,
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

    try:
        return services.buy_stock(db, token, body.region, body.fund_amount, body.symbol)
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

    try:
        return services.sell_stock(db, token, body.symbol)
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
) -> TradeRecordsResponse:
    trades_raw = db.list_trades(limit, offset)
    trades = [TradeRecord(**t) for t in trades_raw]

    token = _get_token()
    try:
        account = services.get_account_summary(db, token)
    except Exception:
        # Fallback if iTick is unavailable
        initial_fund = db.get_config_float("initial_fund", 0.0)
        fund_balance = db.get_config_float("fund_balance", initial_fund)
        account = AccountSummary(
            initial_fund=initial_fund,
            fund_balance=fund_balance,
            total_holdings_value=0.0,
            total_portfolio_value=fund_balance,
            total_pnl=fund_balance - initial_fund,
            total_pnl_pct=((fund_balance - initial_fund) / initial_fund * 100) if initial_fund > 0 else 0.0,
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
        fund_balance = db.get_config_float("fund_balance", initial_fund)
        return AccountSummary(
            initial_fund=initial_fund,
            fund_balance=fund_balance,
            total_holdings_value=0.0,
            total_portfolio_value=fund_balance,
            total_pnl=fund_balance - initial_fund,
            total_pnl_pct=((fund_balance - initial_fund) / initial_fund * 100) if initial_fund > 0 else 0.0,
            holdings=[],
        )
