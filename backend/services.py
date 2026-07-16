"""Business logic for Book Trading Simulator — market hours, iTick client, buy/sell."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from database import Database
from models import TradeRecord, AccountSummary, Holding

logger = logging.getLogger(__name__)

# Module-level iTick client cache
_itick_client = None
_itick_token = None


def get_sydney_time() -> datetime:
    """Return current time in Australia/Sydney timezone."""
    return datetime.now(ZoneInfo("Australia/Sydney"))


def is_asx_market_open() -> tuple[bool, str, str]:
    """Check if ASX market is currently open.

    ASX trading hours: Mon-Fri, 10:00–16:00 Sydney time.
    Returns (is_open, reason, sydney_time_iso_string).
    """
    now = get_sydney_time()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Check weekday
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False, "Market closed: ASX trading hours are Mon-Fri 10:00-16:00 AEST.", now_str

    # Check trading hours
    market_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if now < market_open:
        return False, f"Market not yet open. ASX hours: 10:00-16:00 AEST, Mon-Fri. Current Sydney time: {now_str}", now_str
    if now >= market_close:
        return False, f"Market closed for the day. ASX hours: 10:00-16:00 AEST, Mon-Fri. Current Sydney time: {now_str}", now_str

    return True, "Market is open.", now_str


def get_itick_client(token: str):
    """Get or create the iTick SDK client. Re-created if token changes."""
    global _itick_client, _itick_token

    if _itick_client is not None and _itick_token == token:
        return _itick_client

    try:
        from itick_sdk import Client
        _itick_client = Client(token)
        _itick_token = token
        logger.info("iTick client created successfully")
        return _itick_client
    except ImportError:
        logger.error("itick-sdk package not installed. Run: pip install itick-sdk")
        raise RuntimeError("itick-sdk package not installed. Run: pip install itick-sdk")
    except Exception as e:
        logger.error(f"Failed to create iTick client: {e}")
        raise RuntimeError(f"Failed to create iTick client: {e}")


def fetch_stock_quote(token: str, region: str, symbol: str) -> dict:
    """Fetch live stock quote from iTick. Returns the quote dict with keys
    like 's' (symbol), 'ld' (latest price), 'o' (open), 'h' (high), 'l' (low), 'v' (volume).
    """
    client = get_itick_client(token)
    try:
        quote = client.get_stock_quote(region.upper(), symbol.upper())
        if quote is None:
            raise RuntimeError(f"No quote data returned for {region}:{symbol}")
        return quote
    except Exception as e:
        logger.error(f"iTick quote error for {region}:{symbol}: {e}")
        raise RuntimeError(f"Failed to fetch quote for {symbol}: {e}")


def buy_stock(db: Database, token: str, region: str, fund_amount: float, symbol: str) -> TradeRecord:
    """Execute a buy order: query quote, calculate max shares, update holdings and fund.

    Returns the trade record.
    Raises RuntimeError on market-closed, insufficient funds, or iTick errors.
    """
    # 1. Check market hours
    is_open, reason, sydney_time = is_asx_market_open()
    if not is_open:
        logger.warning(f"BUY rejected — {reason}")
        raise RuntimeError(reason)

    # 2. Get current fund balance
    fund_balance = db.get_config_float("fund_balance", 0.0)

    # 3. Validate fund_amount
    if fund_amount > fund_balance:
        raise RuntimeError(
            f"Insufficient funds. Available: ${fund_balance:,.2f}, requested: ${fund_amount:,.2f}"
        )

    # 4. Fetch quote
    quote = fetch_stock_quote(token, region, symbol)
    price = quote.get("ld")
    if price is None or price <= 0:
        raise RuntimeError(f"Invalid price ({price}) returned for {symbol}")

    logger.info(f"Quote for {symbol}: price=${price:.2f}")

    # 5. Calculate max shares
    max_shares = int(fund_amount / price)
    if max_shares == 0:
        raise RuntimeError(
            f"Fund amount ${fund_amount:,.2f} insufficient to buy even 1 share of {symbol} at ${price:.2f}"
        )

    total_cost = max_shares * price

    # 6. Update fund balance
    new_fund_balance = round(fund_balance - total_cost, 4)
    db.set_config("fund_balance", str(new_fund_balance))

    # 7. Upsert holding
    db.upsert_holding(symbol, max_shares, price, total_cost)

    # 8. Record trade
    trade = db.insert_trade({
        "action": "BUY",
        "symbol": symbol.upper(),
        "quantity": max_shares,
        "price": price,
        "total_value": total_cost,
        "fund_balance_after": new_fund_balance,
    })

    logger.info(
        f"BUY {max_shares} shares of {symbol} at ${price:.2f} = ${total_cost:,.2f}. "
        f"Fund: ${fund_balance:,.2f} → ${new_fund_balance:,.2f}"
    )

    return TradeRecord(
        id=trade,
        action="BUY",
        symbol=symbol.upper(),
        quantity=max_shares,
        price=price,
        total_value=total_cost,
        fund_balance_after=new_fund_balance,
        timestamp=datetime.now().isoformat(),
    )


def sell_stock(db: Database, token: str, symbol: str) -> TradeRecord:
    """Sell ALL shares of a symbol at current market price.

    Returns the trade record.
    Raises RuntimeError on market-closed, symbol not held, or iTick errors.
    """
    # 1. Check market hours
    is_open, reason, sydney_time = is_asx_market_open()
    if not is_open:
        logger.warning(f"SELL rejected — {reason}")
        raise RuntimeError(reason)

    # 2. Find holding
    holding = db.get_holding(symbol)
    if not holding:
        raise RuntimeError(f"No holding found for symbol '{symbol}'. Nothing to sell.")

    # 3. Fetch current quote
    quote = fetch_stock_quote(token, "AU", symbol)
    price = quote.get("ld")
    if price is None or price <= 0:
        raise RuntimeError(f"Invalid price ({price}) returned for {symbol}")

    logger.info(f"Quote for {symbol}: price=${price:.2f}")

    # 4. Calculate proceeds
    quantity = holding["quantity"]
    total_value = quantity * price

    # 5. Update fund balance
    fund_balance = db.get_config_float("fund_balance", 0.0)
    new_fund_balance = round(fund_balance + total_value, 4)
    db.set_config("fund_balance", str(new_fund_balance))

    # 6. Delete holding
    db.delete_holding(symbol)

    # 7. Record trade
    trade = db.insert_trade({
        "action": "SELL",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": price,
        "total_value": total_value,
        "fund_balance_after": new_fund_balance,
    })

    pnl = total_value - holding["total_cost"]
    logger.info(
        f"SELL {quantity} shares of {symbol} at ${price:.2f} = ${total_value:,.2f}. "
        f"P&L: ${pnl:,.2f}. Fund: ${fund_balance:,.2f} → ${new_fund_balance:,.2f}"
    )

    return TradeRecord(
        id=trade,
        action="SELL",
        symbol=symbol.upper(),
        quantity=quantity,
        price=price,
        total_value=total_value,
        fund_balance_after=new_fund_balance,
        timestamp=datetime.now().isoformat(),
    )


def get_account_summary(db: Database, token: str) -> AccountSummary:
    """Build account summary with live prices for all holdings."""
    initial_fund = db.get_config_float("initial_fund", 0.0)
    fund_balance = db.get_config_float("fund_balance", initial_fund)

    holdings_db = db.list_holdings()
    holdings_list: list[Holding] = []
    total_holdings_value = 0.0

    for h in holdings_db:
        current_price = 0.0
        market_value = 0.0
        unrealized_pnl = 0.0
        unrealized_pnl_pct = 0.0

        # Try to fetch live price
        try:
            quote = fetch_stock_quote(token, "AU", h["symbol"])
            current_price = quote.get("ld", 0.0) or 0.0
            market_value = round(h["quantity"] * current_price, 4)
            unrealized_pnl = round(market_value - h["total_cost"], 4)
            if h["total_cost"] > 0:
                unrealized_pnl_pct = round((unrealized_pnl / h["total_cost"]) * 100, 2)
        except Exception as e:
            logger.warning(f"Could not fetch live price for {h['symbol']}: {e}")
            # Use avg_price as fallback
            current_price = h["avg_price"]
            market_value = h["total_cost"]

        total_holdings_value += market_value

        holdings_list.append(Holding(
            id=h["id"],
            symbol=h["symbol"],
            quantity=h["quantity"],
            avg_price=h["avg_price"],
            total_cost=h["total_cost"],
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
        ))

    total_portfolio_value = round(fund_balance + total_holdings_value, 4)
    total_pnl = round(total_portfolio_value - initial_fund, 4)
    total_pnl_pct = round((total_pnl / initial_fund) * 100, 2) if initial_fund > 0 else 0.0

    return AccountSummary(
        initial_fund=initial_fund,
        fund_balance=fund_balance,
        total_holdings_value=total_holdings_value,
        total_portfolio_value=total_portfolio_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        holdings=holdings_list,
    )
