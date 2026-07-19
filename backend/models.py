"""Pydantic data models for Book Trading Simulator — aligned with proto/trading/trading.proto."""

from typing import Optional
from pydantic import BaseModel


#
# Config (infrastructure — no proto equivalent)
#

class ConfigUpdate(BaseModel):
    initial_fund: float
    itick_token: str


class ConfigResponse(BaseModel):
    initial_fund: float
    exchange_balances: dict[str, float]
    itick_token_masked: str


#
# Trading — aligned with proto BuyStockRequest / SellStockRequest
#

class BuyRequest(BaseModel):
    exchange: str = "AU"
    symbol: str
    quantity: int
    price: float
    order_type: str = "MARKET"   # "MARKET" | "LIMIT"


class SellRequest(BaseModel):
    exchange: str = "AU"
    symbol: str
    quantity: int
    price: float
    order_type: str = "MARKET"   # "MARKET" | "LIMIT"


# aligned with proto TradeResponse
class TradeRecord(BaseModel):
    trade_id: str
    status: str = "FILLED"       # PENDING | FILLED | PARTIALLY_FILLED | REJECTED | CANCELLED
    exchange: str = "AU"
    symbol: str
    side: str = "BUY"            # BUY | SELL
    filled_quantity: int
    filled_price: float
    total_amount: float
    commission: float = 0.0
    remaining_cash: float
    message: str = ""
    executed_at: str = ""


# aligned with proto StockHolding
class Holding(BaseModel):
    id: str
    symbol: str
    exchange: str = "AU"
    quantity: int
    avg_cost: float
    total_cost: float
    current_price: float = 0.0
    market_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0


# aligned with proto ViewPortfolioResponse
class AccountSummary(BaseModel):
    exchange: str = ""
    cash: float
    holdings: list[Holding]
    total_holdings_value: float
    total_portfolio_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_pct: float
    initial_fund: float
    exchange_balances: dict[str, float] = {}


class TradeRecordsResponse(BaseModel):
    trades: list[TradeRecord]
    account: AccountSummary


#
# Health / Market (no proto equivalent)
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
# Quote — aligned with proto GetQuoteResponse
#

class QuoteResponse(BaseModel):
    exchange: str
    symbol: str
    current_price: float
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    previous_close: float = 0.0
    volume: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    timestamp: str = ""
