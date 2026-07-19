"""Business logic for Book Trading Simulator — market hours, iTick client, buy/sell."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

from database import Database
from models import TradeRecord, AccountSummary, Holding

logger = logging.getLogger("book_simulator.services")

# Supported exchanges — each gets its own fund_balance
EXCHANGES = ["AU", "US", "HK", "SZ", "SH", "NL"]

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
# Per-exchange fund balance helpers
#

def get_fund_balance(db: Database, exchange: str) -> float:
    """Get fund balance for a specific exchange."""
    return db.get_config_float(f"fund_balance_{exchange.upper()}", 0.0)


def set_fund_balance(db: Database, exchange: str, amount: float):
    """Set fund balance for a specific exchange."""
    db.set_config(f"fund_balance_{exchange.upper()}", str(round(amount, 4)))


def seed_exchange_funds(db: Database, initial_fund: float):
    """Set all exchange fund balances to the given amount."""
    for exchange in EXCHANGES:
        db.set_config(f"fund_balance_{exchange}", str(initial_fund))


def get_all_exchange_balances(db: Database) -> dict[str, float]:
    """Return {EXCHANGE: balance} for all exchanges."""
    return {e: get_fund_balance(db, e) for e in EXCHANGES}


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


def fetch_stock_quote(token: str, exchange: str, symbol: str) -> dict:
    """Fetch live stock quote from iTick. Returns a dict with proto-aligned keys."""
    client = get_itick_client(token)
    exchange_upper = exchange.upper()
    symbol_upper = symbol.upper()

    logger.debug(f"[iTick REQUEST]  get_stock_quote(exchange='{exchange_upper}', code='{symbol_upper}')  token={token[:8]}...")
    try:
        quote = client.get_stock_quote(exchange_upper, symbol_upper)
        if quote is None:
            raise RuntimeError(f"No quote data returned for {exchange}:{symbol}")

        current_price = quote.get("ld", 0.0) or 0.0
        change_val = quote.get("ch", 0.0) or 0.0
        previous_close = round(current_price - change_val, 4)

        logger.debug(
            f"[iTick RESPONSE] {symbol_upper}  "
            f"current_price={current_price}  open_price={quote.get('o')}  "
            f"high_price={quote.get('h')}  low_price={quote.get('l')}  "
            f"volume={quote.get('v')}  change={change_val}  "
            f"change_pct={quote.get('chp')}%  previous_close={previous_close}  "
            f"raw_keys={list(quote.keys())}"
        )
        return {
            "current_price": current_price,
            "open_price": quote.get("o", 0.0) or 0.0,
            "high_price": quote.get("h", 0.0) or 0.0,
            "low_price": quote.get("l", 0.0) or 0.0,
            "volume": quote.get("v", 0.0) or 0.0,
            "change": change_val,
            "change_pct": quote.get("chp", 0.0) or 0.0,
            "previous_close": previous_close,
        }
    except Exception as e:
        logger.error(f"iTick quote error for {exchange}:{symbol}: {e}")
        raise RuntimeError(f"Failed to fetch quote for {symbol}: {e}")


#
# Trading
#

def submit_order(db: Database, token: str, exchange: str, side: str,
                 symbol: str, quantity: int, price: float, order_type: str) -> TradeRecord:
    """Submit a buy or sell order. Dispatches to buy_stock / sell_stock based on side."""
    side_upper = side.upper()
    if side_upper == "BUY":
        return buy_stock(db, token, exchange, symbol, quantity, price, order_type)
    elif side_upper == "SELL":
        return sell_stock(db, token, exchange, symbol, quantity, price, order_type)
    else:
        raise RuntimeError(f"Unknown order side: {side}. Must be BUY or SELL.")


def buy_stock(db: Database, token: str, exchange: str, symbol: str,
              quantity: int, price: float, order_type: str) -> TradeRecord:
    """Execute a buy order. Uses quantity + price (proto-aligned)."""
    exchange_upper = exchange.upper()
    fund_balance = get_fund_balance(db, exchange_upper)

    logger.debug(
        f"[BUY REQUEST] exchange={exchange_upper}  symbol={symbol}  "
        f"quantity={quantity}  price={price}  order_type={order_type}  "
        f"fund_balance={fund_balance}"
    )

    # Check market hours (ASX only)
    if exchange_upper == "AU":
        is_open, reason, _ = is_asx_market_open()
        if not is_open:
            logger.warning(f"BUY rejected — {reason}")
            raise RuntimeError(reason)

    # Validate quantity
    if quantity <= 0:
        raise RuntimeError("Quantity must be positive")

    # Fetch quote
    quote = fetch_stock_quote(token, exchange_upper, symbol)
    current_price = quote.get("current_price")
    if current_price is None or current_price <= 0:
        raise RuntimeError(f"Invalid price ({current_price}) returned for {symbol}")

    # Determine execution price
    order_type_upper = order_type.upper()
    if order_type_upper == "MARKET":
        execution_price = current_price
    elif order_type_upper == "LIMIT":
        execution_price = price
        if current_price > price:
            raise RuntimeError(
                f"Limit price ${price:.2f} is below current price ${current_price:.2f}. Order not filled."
            )
    else:
        raise RuntimeError(f"Unknown order_type: {order_type}")

    total_cost = quantity * execution_price
    if total_cost > fund_balance:
        raise RuntimeError(
            f"Insufficient funds in {exchange_upper}. Available: ${fund_balance:,.2f}, needed: ${total_cost:,.2f}"
        )

    new_fund_balance = round(fund_balance - total_cost, 4)
    set_fund_balance(db, exchange_upper, new_fund_balance)

    # Upsert holding
    db.upsert_holding(symbol, quantity, execution_price, total_cost, exchange_upper)

    # Record trade
    trade_id = db.insert_trade({
        "action": "BUY",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": execution_price,
        "total_value": total_cost,
        "fund_balance_after": new_fund_balance,
        "exchange": exchange_upper,
    })

    logger.info(
        f"BUY [{exchange_upper}] {quantity} shares of {symbol} at ${execution_price:.2f} = ${total_cost:,.2f}. "
        f"Fund: ${fund_balance:,.2f} → ${new_fund_balance:,.2f}"
    )

    return TradeRecord(
        trade_id=trade_id,
        status="FILLED",
        exchange=exchange_upper,
        symbol=symbol.upper(),
        side="BUY",
        filled_quantity=quantity,
        filled_price=execution_price,
        total_amount=total_cost,
        commission=0.0,
        remaining_cash=new_fund_balance,
        message="",
        executed_at=datetime.now().isoformat(),
    )


def sell_stock(db: Database, token: str, exchange: str, symbol: str,
               quantity: int, price: float, order_type: str) -> TradeRecord:
    """Sell a specific quantity of a symbol (proto-aligned)."""
    exchange_upper = exchange.upper()

    logger.debug(
        f"[SELL REQUEST] exchange={exchange_upper}  symbol={symbol}  "
        f"quantity={quantity}  price={price}  order_type={order_type}"
    )

    # Check market hours (ASX only)
    if exchange_upper == "AU":
        is_open, reason, _ = is_asx_market_open()
        if not is_open:
            logger.warning(f"SELL rejected — {reason}")
            raise RuntimeError(reason)

    # Validate quantity
    if quantity <= 0:
        raise RuntimeError("Quantity must be positive")

    # Find holding
    holding = db.get_holding(symbol)
    if not holding:
        raise RuntimeError(f"No holding found for symbol '{symbol}'. Nothing to sell.")

    if holding["quantity"] < quantity:
        raise RuntimeError(
            f"Insufficient shares. Holding: {holding['quantity']}, requested: {quantity}"
        )

    logger.debug(
        f"[SELL HOLDING] symbol={holding['symbol']}  quantity={holding['quantity']}  "
        f"avg_price={holding['avg_price']}  total_cost={holding['total_cost']}  "
        f"exchange={holding.get('exchange', 'AU')}"
    )

    # Use holding's stored exchange for quote
    stored_exchange = holding.get("exchange", exchange_upper)

    # Fetch current quote
    quote = fetch_stock_quote(token, stored_exchange, symbol)
    current_price = quote.get("current_price")
    if current_price is None or current_price <= 0:
        raise RuntimeError(f"Invalid price ({current_price}) returned for {symbol}")

    # Determine execution price
    order_type_upper = order_type.upper()
    if order_type_upper == "MARKET":
        execution_price = current_price
    elif order_type_upper == "LIMIT":
        execution_price = price
        if current_price < price:
            raise RuntimeError(
                f"Limit price ${price:.2f} is above current price ${current_price:.2f}. Order not filled."
            )
    else:
        raise RuntimeError(f"Unknown order_type: {order_type}")

    total_value = quantity * execution_price

    # Update exchange-specific fund balance
    fund_balance = get_fund_balance(db, stored_exchange)
    new_fund_balance = round(fund_balance + total_value, 4)
    set_fund_balance(db, stored_exchange, new_fund_balance)

    # Update or delete holding
    remaining_qty = holding["quantity"] - quantity
    if remaining_qty > 0:
        # Partial sell — reduce quantity and cost basis proportionally
        avg_price = holding["total_cost"] / holding["quantity"]
        new_total_cost = holding["total_cost"] - (quantity * avg_price)
        db.update_holding_qty_and_cost(symbol, remaining_qty, new_total_cost, stored_exchange)
    else:
        # Full sell — delete holding
        db.delete_holding(symbol)

    # Record trade
    trade_id = db.insert_trade({
        "action": "SELL",
        "symbol": symbol.upper(),
        "quantity": quantity,
        "price": execution_price,
        "total_value": total_value,
        "fund_balance_after": new_fund_balance,
        "exchange": stored_exchange,
    })

    pnl = total_value - (holding["avg_price"] * quantity)
    logger.info(
        f"SELL [{stored_exchange}] {quantity} shares of {symbol} at ${execution_price:.2f} = ${total_value:,.2f}. "
        f"P&L: ${pnl:,.2f}. Fund: ${fund_balance:,.2f} → ${new_fund_balance:,.2f}"
    )

    return TradeRecord(
        trade_id=trade_id,
        status="FILLED",
        exchange=stored_exchange,
        symbol=symbol.upper(),
        side="SELL",
        filled_quantity=quantity,
        filled_price=execution_price,
        total_amount=total_value,
        commission=0.0,
        remaining_cash=new_fund_balance,
        message="",
        executed_at=datetime.now().isoformat(),
    )


#
# Account summary
#

def get_account_summary(db: Database, token: str) -> AccountSummary:
    """Build account summary with live prices and per-exchange fund balances."""
    initial_fund = db.get_config_float("initial_fund", 0.0)
    exchange_balances = get_all_exchange_balances(db)
    total_cash = sum(exchange_balances.values())

    holdings_db = db.list_holdings()
    holdings_list: list[Holding] = []
    total_holdings_value = 0.0

    for h in holdings_db:
        current_price = 0.0
        market_value = 0.0
        unrealized_pnl = 0.0
        unrealized_pnl_pct = 0.0
        stored_exchange = h.get("exchange", "AU")

        try:
            quote = fetch_stock_quote(token, stored_exchange, h["symbol"])
            current_price = quote.get("current_price", 0.0) or 0.0
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
            exchange=stored_exchange,
            quantity=h["quantity"],
            avg_cost=h["avg_price"],
            total_cost=h["total_cost"],
            current_price=current_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
        ))

    total_portfolio_value = round(total_cash + total_holdings_value, 4)
    total_initial = initial_fund * len(EXCHANGES)
    total_unrealized_pnl = round(total_portfolio_value - total_initial, 4)
    total_unrealized_pnl_pct = round((total_unrealized_pnl / total_initial) * 100, 2) if total_initial > 0 else 0.0

    return AccountSummary(
        exchange="",
        cash=total_cash,
        holdings=holdings_list,
        total_holdings_value=total_holdings_value,
        total_portfolio_value=total_portfolio_value,
        total_unrealized_pnl=total_unrealized_pnl,
        total_unrealized_pnl_pct=total_unrealized_pnl_pct,
        initial_fund=initial_fund,
        exchange_balances=exchange_balances,
    )
