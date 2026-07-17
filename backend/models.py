"""Pydantic data models for Book Trading Simulator."""

from typing import Optional
from pydantic import BaseModel


#
# Config
#

class ConfigUpdate(BaseModel):
    initial_fund: float
    itick_token: str


class ConfigResponse(BaseModel):
    initial_fund: float
    region_balances: dict[str, float]
    itick_token_masked: str


#
# Trading
#

class BuyRequest(BaseModel):
    region: str = "AU"
    fund_amount: float
    symbol: str


class SellRequest(BaseModel):
    symbol: str
    region: str = "AU"


class TradeRecord(BaseModel):
    id: str
    action: str
    symbol: str
    quantity: int
    price: float
    total_value: float
    fund_balance_after: float
    region: str = "AU"
    timestamp: str


class Holding(BaseModel):
    id: str
    symbol: str
    region: str = "AU"
    quantity: int
    avg_price: float
    total_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


class AccountSummary(BaseModel):
    initial_fund: float
    fund_balance: float
    total_holdings_value: float
    total_portfolio_value: float
    total_pnl: float
    total_pnl_pct: float
    region_balances: dict[str, float] = {}
    holdings: list[Holding]


class TradeRecordsResponse(BaseModel):
    trades: list[TradeRecord]
    account: AccountSummary


#
# Health / Market
#

class HealthStatus(BaseModel):
    database: bool
    itick_configured: bool
    market_open: bool


class MarketStatus(BaseModel):
    is_open: bool
    reason: str
    current_sydney_time: str


class ErrorResponse(BaseModel):
    detail: str


#
# Quote (no trade, no market-hours restriction)
#

class QuoteResponse(BaseModel):
    symbol: str
    region: str
    price: float
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: str = ""
