"""gRPC server implementation for Book Trading Simulator.

Implements TradingServiceServicer from proto/trading/trading.proto.
Reuses existing services.py and database.py modules.
"""

import logging
import sys
import os
from datetime import datetime, timezone

# Make generated stubs importable (they use flat `import trading_pb2`)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "grpc_stubs"))

import grpc
import trading_pb2 as trading_pb2
import trading_pb2_grpc as trading_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp

import services
from database import Database
from models import TradeRecord, Holding, AccountSummary

logger = logging.getLogger("book_simulator.grpc")

# Map proto OrderType enum → service string
_ORDER_TYPE_TO_STR = {
    trading_pb2.MARKET: "MARKET",
    trading_pb2.LIMIT: "LIMIT",
}

_ORDER_SIDE_TO_STR = {
    trading_pb2.BUY: "BUY",
    trading_pb2.SELL: "SELL",
}

_ORDER_SIDE_TO_PROTO = {
    "BUY": trading_pb2.BUY,
    "SELL": trading_pb2.SELL,
}

_TRADE_STATUS_TO_PROTO = {
    "PENDING": trading_pb2.PENDING,
    "FILLED": trading_pb2.FILLED,
    "PARTIALLY_FILLED": trading_pb2.PARTIALLY_FILLED,
    "REJECTED": trading_pb2.REJECTED,
    "CANCELLED": trading_pb2.CANCELLED,
}


def _to_timestamp(ts_str: str) -> Timestamp:
    """Convert ISO datetime string to protobuf Timestamp."""
    ts = Timestamp()
    if ts_str:
        try:
            dt = datetime.fromisoformat(ts_str)
            ts.FromDatetime(dt.replace(tzinfo=timezone.utc))
        except (ValueError, TypeError):
            pass
    return ts


def _trade_to_proto(tr: TradeRecord) -> trading_pb2.TradeResponse:
    """Map Pydantic TradeRecord → proto TradeResponse."""
    return trading_pb2.TradeResponse(
        trade_id=tr.trade_id,
        status=_TRADE_STATUS_TO_PROTO.get(tr.status, trading_pb2.FILLED),
        exchange=tr.exchange,
        symbol=tr.symbol,
        side=_ORDER_SIDE_TO_PROTO.get(tr.side, trading_pb2.BUY),
        filled_quantity=tr.filled_quantity,
        filled_price=tr.filled_price,
        total_amount=tr.total_amount,
        commission=tr.commission,
        remaining_cash=tr.remaining_cash,
        message=tr.message,
        executed_at=_to_timestamp(tr.executed_at),
    )


def _holding_to_proto(h: Holding) -> trading_pb2.StockHolding:
    """Map Pydantic Holding → proto StockHolding."""
    return trading_pb2.StockHolding(
        id=h.id,
        symbol=h.symbol,
        exchange=h.exchange,
        quantity=h.quantity,
        avg_cost=h.avg_cost,
        total_cost=h.total_cost,
        current_price=h.current_price,
        market_value=h.market_value,
        unrealized_pnl=h.unrealized_pnl,
        unrealized_pnl_pct=h.unrealized_pnl_pct,
    )


def _account_to_proto(a: AccountSummary) -> trading_pb2.ViewPortfolioResponse:
    """Map Pydantic AccountSummary → proto ViewPortfolioResponse."""
    ts = Timestamp()
    ts.GetCurrentTime()
    return trading_pb2.ViewPortfolioResponse(
        exchange=a.exchange,
        cash=a.cash,
        holdings=[_holding_to_proto(h) for h in a.holdings],
        total_holdings_value=a.total_holdings_value,
        total_portfolio_value=a.total_portfolio_value,
        total_unrealized_pnl=a.total_unrealized_pnl,
        total_unrealized_pnl_pct=a.total_unrealized_pnl_pct,
        timestamp=ts,
        initial_fund=a.initial_fund,
        exchange_balances=a.exchange_balances,
    )


class GrpcTradingService(trading_pb2_grpc.TradingServiceServicer):
    """gRPC servicer wrapping existing services.py business logic."""

    def __init__(self, db: Database):
        self._db = db

    def _get_token(self, context) -> str:
        """Get iTick token from config. Fails with FAILED_PRECONDITION if not set."""
        token = self._db.get_config("itick_token") or ""
        if not token:
            context.abort(
                grpc.StatusCode.FAILED_PRECONDITION,
                "iTick token not configured. Set it via REST /api/config or ITICK_TOKEN env var.",
            )
        return token

    # ── InitExchange ──────────────────────────────────────

    def InitExchange(self, request: trading_pb2.InitExchangeRequest, context):
        exchange = request.exchange.upper() if request.exchange else "AU"
        initial_fund = request.initial_fund

        # Store initial_fund per exchange in config
        self._db.set_config(f"initial_fund_{exchange}", str(initial_fund))
        self._db.set_config("initial_fund", str(initial_fund))  # global default

        # Seed fund balance for this exchange
        self._db.set_config(
            f"fund_balance_{exchange}", str(round(initial_fund, 4))
        )

        logger.info(
            f"[gRPC InitExchange] exchange={exchange}  initial_fund={initial_fund}"
        )

        ts = Timestamp()
        ts.GetCurrentTime()
        return trading_pb2.InitExchangeResponse(
            success=True,
            message=f"Exchange {exchange} initialized with ${initial_fund:,.2f}",
            initial_fund=initial_fund,
            initialized_at=ts,
        )

    # ── GetQuote ──────────────────────────────────────────

    def GetQuote(self, request: trading_pb2.GetQuoteRequest, context):
        token = self._get_token(context)
        exchange = request.exchange or "AU"
        symbol = request.symbol.upper()

        logger.debug(f"[gRPC GetQuote] exchange={exchange}  symbol={symbol}")

        try:
            q = services.fetch_stock_quote(token, exchange, symbol)
        except Exception as e:
            context.abort(grpc.StatusCode.UNAVAILABLE, str(e))

        ts = Timestamp()
        ts.GetCurrentTime()
        return trading_pb2.GetQuoteResponse(
            exchange=exchange.upper(),
            symbol=symbol,
            current_price=q.get("current_price", 0.0) or 0.0,
            open_price=q.get("open_price", 0.0) or 0.0,
            high_price=q.get("high_price", 0.0) or 0.0,
            low_price=q.get("low_price", 0.0) or 0.0,
            previous_close=q.get("previous_close", 0.0) or 0.0,
            volume=int(q.get("volume", 0) or 0),
            timestamp=ts,
            change=q.get("change", 0.0) or 0.0,
            change_pct=q.get("change_pct", 0.0) or 0.0,
        )

    # ── SubmitOrder ───────────────────────────────────────

    def SubmitOrder(self, request: trading_pb2.OrderRequest, context):
        token = self._get_token(context)
        exchange = request.exchange or "AU"
        side = _ORDER_SIDE_TO_STR.get(request.side, "BUY")
        symbol = request.symbol.upper()
        quantity = request.quantity
        price = request.price
        order_type = _ORDER_TYPE_TO_STR.get(request.order_type, "MARKET")

        logger.debug(
            f"[gRPC SubmitOrder] side={side}  exchange={exchange}  "
            f"symbol={symbol}  quantity={quantity}  price={price}  "
            f"order_type={order_type}"
        )

        try:
            result = services.submit_order(
                self._db, token, exchange, side,
                symbol, quantity, price, order_type,
            )
        except RuntimeError as e:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(e))
        except Exception as e:
            logger.exception("gRPC SubmitOrder error")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

        return _trade_to_proto(result)

    # ── ViewPortfolio ─────────────────────────────────────

    def ViewPortfolio(self, request: trading_pb2.ViewPortfolioRequest, context):
        token = self._get_token(context)
        exchange = request.exchange or "AU"

        logger.debug(f"[gRPC ViewPortfolio] exchange={exchange}")

        try:
            account = services.get_account_summary(self._db, token)
        except Exception as e:
            logger.exception("gRPC ViewPortfolio error")
            context.abort(grpc.StatusCode.INTERNAL, str(e))

        # Set the requested exchange on the response
        account.exchange = exchange.upper()
        return _account_to_proto(account)
