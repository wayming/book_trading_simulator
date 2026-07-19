const BASE = '/api';

// ── Types (aligned with proto/trading/trading.proto) ──────────

export interface HealthStatus {
  database: boolean;
  itick_configured: boolean;
  market_open: boolean;
}

export interface MarketStatus {
  is_open: boolean;
  reason: string;
  current_sydney_time: string;
}

export interface ConfigResponse {
  initial_fund: number;
  exchange_balances: Record<string, number>;
  itick_token_masked: string;
}

export interface ConfigUpdate {
  initial_fund: number;
  itick_token: string;
}

export interface OrderRequest {
  exchange: string;
  side: string;          // "BUY" | "SELL"
  symbol: string;
  quantity: number;
  price: number;
  order_type: string;    // "MARKET" | "LIMIT"
}

export interface TradeRecord {
  trade_id: string;
  status: string;
  exchange: string;
  symbol: string;
  side: string;           // "BUY" | "SELL"
  filled_quantity: number;
  filled_price: number;
  total_amount: number;
  commission: number;
  remaining_cash: number;
  message: string;
  executed_at: string;
}

export interface Holding {
  id: string;
  symbol: string;
  exchange: string;
  quantity: number;
  avg_cost: number;
  total_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface AccountSummary {
  exchange: string;
  cash: number;
  holdings: Holding[];
  total_holdings_value: number;
  total_portfolio_value: number;
  total_unrealized_pnl: number;
  total_unrealized_pnl_pct: number;
  initial_fund: number;
  exchange_balances: Record<string, number>;
}

export interface TradeRecordsResponse {
  trades: TradeRecord[];
  account: AccountSummary;
}

export interface QuoteResponse {
  exchange: string;
  symbol: string;
  current_price: number;
  open_price: number;
  high_price: number;
  low_price: number;
  previous_close: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: string;
}

// ── API functions ──────────────────────────────────────────

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function fetchMarketStatus(): Promise<MarketStatus> {
  const res = await fetch(`${BASE}/market-status`);
  return res.json();
}

export async function fetchQuote(exchange: string, symbol: string): Promise<QuoteResponse> {
  const res = await fetch(`${BASE}/quote?exchange=${encodeURIComponent(exchange)}&symbol=${encodeURIComponent(symbol)}`);
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Quote failed');
  }
  return res.json();
}

export async function fetchConfig(): Promise<ConfigResponse> {
  const res = await fetch(`${BASE}/config`);
  return res.json();
}

export async function updateConfig(cfg: ConfigUpdate): Promise<ConfigResponse> {
  const res = await fetch(`${BASE}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(cfg),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Config update failed');
  }
  return res.json();
}

export async function submitOrder(req: OrderRequest): Promise<TradeRecord> {
  const res = await fetch(`${BASE}/order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Order failed');
  }
  return res.json();
}

export async function fetchRecords(limit = 50, offset = 0, exchange?: string): Promise<TradeRecordsResponse> {
  let url = `${BASE}/records?limit=${limit}&offset=${offset}`;
  if (exchange) url += `&exchange=${encodeURIComponent(exchange)}`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchAccount(): Promise<AccountSummary> {
  const res = await fetch(`${BASE}/account`);
  return res.json();
}
