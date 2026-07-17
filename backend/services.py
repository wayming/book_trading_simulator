"""Business logic for Book Trading Simulator — market hours, iTick client, buy/sell."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from database import Database
from models import TradeRecord, AccountSummary, Holding

logger = logging.getLogger("book_simulator.services")

# Supported regions — each gets its own fund_balance
REGIONS = ["AU", "US", "HK", "SZ", "SH", "NL"]

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

    if now.weekday() >= 5:
        return False, "Market closed: ASX trading hours are Mon-Fri 10:00-16:00 AEST.", now_str

    market_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

    if now < market_open:
        return False, f"Market not yet open. ASX hours: 10:00-16:00 AEST, Mon-Fri. Current Sydney time: {now_str}", now_str
    if now >= market_close:
        return False, f"Market closed for the day. ASX hours: 10:00-16:00 AEST, Mon-Fri. Current Sydney time: {now_str}", now_str

    return True, "Market is open.", now_str


#
# Per-region fund balance helpers
#

def get_fund_balance(db: Database, region: str) -> float:
    """Get fund balance for a specific region."""
    return db.get_config_float(f"fund_balance_{region.upper()}", 0.0)


def set_fund_balance(db: Database, region: str, amount: float):
    """Set fund balance for a specific region."""
    db.set_config(f"fund_balance_{region.upper()}", str(round(amount, 4)))


def seed_region_funds(db: Database, initial_fund: float):
    """Set all region fund balances to the given amount."""
    for region in REGIONS:
        db.set_config(f"fund_balance_{region}", str(initial_fund))


def get_all_region_balances(db: Database) -> dict[str, float]:
    """Return {REGION: balance} for all regions."""
    return {r: get_fund_balance(db, r) for r in REGIONS}


#
# iTick client
#

def get_itick_client(token: str):
    """Get or create the iTick SDK client. Re-created if token changes."""
    global _itick_client, _itick_token

    if _itick_client is not None and _itick_token == token:
        return _itick_client

    try:
        from itick.sdk import Client
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
    """Fetch live stock quote from iTick. Returns the quote dict."""
    client = get_itick_client(token)
    region_upper = region.upper()
    symbol_upper = symbol.upper()

    logger.debug(f"[iTick REQUEST]  get_stock_quote(region='{region_upper}', code='{symbol_upper}')  token={token[:8]}...")
    try:
        quote = client.get_stock_quote(region_upper, symbol_upper)
        if quote is None:
            raise RuntimeError(f"No quote data returned for {region}:{symbol}")

        logger.debug(
            f"[iTick RESPONSE] {symbol_upper}  "
            f"price={quote.get('ld')}  open={quote.get('o')}  "
            f"high={quote.get('h')}  low={quote.get('l')}  "
            f"volume={quote.get('v')}  change={quote.get('ch')}  "
            f"change_pct={quote.get('chp')}%  "
            f"raw_keys={list(quote.keys())}"
        )
        return quote
    except Exception as e:
        logger.error(f"iTick quote error for {region}:{symbol}: {e}")
        raise RuntimeError(f"Failed to fetch quote for {symbol}: {e}")


#
# Trading
#

def buy_stock(db: Database, token: str, region: str, fund_amount: float, symbol: str) -> TradeRecord:
    """Execute a buy order using the region-specific fund balance."""
    region_upper = region.upper()
    fund_balance = get_fund_balance(db, region_upper)

    logger.debug(
        f"[BUY REQUEST] region={region_upper}  fund_amount={fund_amount}  symbol={symbol}  "
        f"fund_balance={fund_balance}"
    )

    # Check market hours (ASX only)
    if region_upper == "AU":
        is_open, reason, _ = is_asx_market_open()
        if not is_open:
            logger.warning(f"BUY rejected — {reason}")
            raise RuntimeError(reason)

    # Validate fund_amount
    if fund_amount > fund_balance:
        raise RuntimeError(
            f"Insufficient funds in {region_upper}. Available: ${fund_balance:,.2f}, requested: ${fund_amount:,.2f}"
        )

    # Fetch quote
    quote = fetch_stock_quote(token, region_upper, symbol)
    price = quote.get("ld")
    if price is None or price <= 0:
        raise RuntimeError(f"Invalid price ({price}) returned for {symbol}")

    logger.info(f"Quote for {symbol}: price=${price:.2f}")

    # Calculate max shares
    max_shares = int(fund_amount / price)
    if max_shares == 0:
        raise RuntimeError(
            f"Fund amount ${fund_amount:,.2f} insufficient to buy even 1 share of {symbol} at ${price:.2f}"
        )

    total_cost = max_shares * price
    new_fund_balance = round(fund_balance - total_cost, 4)
    set_fund_balance(db, region_upper, new_fund_balance)

    # Upsert holding with region
    db.upsert_holding(symbol, max_shares, price, total_cost, region_upper)

    # Record trade
    trade = db.insert_trade({
        "action": "BUY",
        "symbol": symbol.upper(),
        "quantity": max_shares,
        "price": price,
        "total_value": total_cost,
        "fund_balance_after": new_fund_balance,
        "region": region_upper,
    })

    logger.info(
        f"BUY [{region_upper}] {max_shares} shares of {symbol} at ${price:.2f} = ${total_cost:,.2f}. "
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


def sell_stock(db: Database, token: str, symbol: str, region: str = "AU") -> TradeRecord:
    """Sell ALL shares of a symbol."""
    region_upper = region.upper()

    logger.debug(f"[SELL REQUEST] symbol={symbol}  region={region_upper}")

    # Check market hours (ASX only)
    if region_upper == "AU":
        is_open, reason, _ = is_asx_market_open()
        if not is_open:
            logger.warning(f"SELL rejected — {reason}")
            raise RuntimeError(reason)

    # Find holding
    holding = db.get_holding(symbol)
    if not holding:
        raise RuntimeError(f"No holding found for symbol '{symbol}'. Nothing to sell.")

    logger.debug(
        f"[SELL HOLDING] symbol={holding['symbol']}  quantity={holding['quantity']}  "
        f"avg_price={holding['avg_price']}  total_cost={holding['total_cost']}  "
        f"region={holding.get('region', 'AU')}"
    )

    # Use holding's stored region for quote
    stored_region = holding.get("region", region_upper)

    # Fetch current quote
    quote = fetch_stock_quote(token, stored_region, symbol)
    price = quote.get("ld")
    if price is None or price <= 0:
        raise RuntimeError(f"Invalid price ({price}) returned for {symbol}")

    logger.info(f"Quote for {symbol}: price=${price:.2f}")

    quantity = holding["quantity"]
    total_value = quantity * price

    # Update region-specific fund balance
    fund_balance = get_fund_balance(db, stored_region)
    new_fund_balance = round(fund_balance + total_value, 4)
    set_fund_balance(db, stored_region, new_fund_balance)

    # Delete holding
    db.delete_holding(symbol)

    # Record trade
    trade = db.insert_trade({
        "action": "SELL",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": price,
        "total_value": total_value,
        "fund_balance_after": new_fund_balance,
        "region": stored_region,
    })

    pnl = total_value - holding["total_cost"]
    logger.info(
        f"SELL [{stored_region}] {quantity} shares of {symbol} at ${price:.2f} = ${total_value:,.2f}. "
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


#
# Account summary
#

def get_account_summary(db: Database, token: str) -> AccountSummary:
    """Build account summary with live prices and per-region fund balances."""
    initial_fund = db.get_config_float("initial_fund", 0.0)
    region_balances = get_all_region_balances(db)
    total_fund_balance = sum(region_balances.values())

    holdings_db = db.list_holdings()
    holdings_list: list[Holding] = []
    total_holdings_value = 0.0

    for h in holdings_db:
        current_price = 0.0
        market_value = 0.0
        unrealized_pnl = 0.0
        unrealized_pnl_pct = 0.0
        stored_region = h.get("region", "AU")

        try:
            quote = fetch_stock_quote(token, stored_region, h["symbol"])
            current_price = quote.get("ld", 0.0) or 0.0
            market_value = round(h["quantity"] * current_price, 4)
            unrealized_pnl = round(market_value - h["total_cost"], 4)
            if h["total_cost"] > 0:
                unrealized_pnl_pct = round((unrealized_pnl / h["total_cost"]) * 100, 2)
        except Exception as e:
            logger.warning(f"Could not fetch live price for {h['symbol']}: {e}")
            current_price = h["avg_price"]
            market_value = h["total_cost"]

        total_holdings_value += market_value

        holdings_list.append(Holding(
            id=h["id"],
            symbol=h["symbol"],
            region=stored_region,
            quantity=h["quantity"],
            avg_price=h["avg_price"],
            total_cost=h["total_cost"],
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
        ))

    total_portfolio_value = round(total_fund_balance + total_holdings_value, 4)
    total_initial = initial_fund * len(REGIONS)
    total_pnl = round(total_portfolio_value - total_initial, 4)
    total_pnl_pct = round((total_pnl / total_initial) * 100, 2) if total_initial > 0 else 0.0

    return AccountSummary(
        initial_fund=initial_fund,
        fund_balance=total_fund_balance,
        total_holdings_value=total_holdings_value,
        total_portfolio_value=total_portfolio_value,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        region_balances=region_balances,
        holdings=holdings_list,
    )
