const BASE = '/api';

// ── Types ────────────────────────────────────────────

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
  region_balances: Record<string, number>;
  itick_token_masked: string;
}

export interface ConfigUpdate {
  initial_fund: number;
  itick_token: string;
}

export interface BuyRequest {
  region: string;
  fund_amount: number;
  symbol: string;
}

export interface SellRequest {
  symbol: string;
  region: string;
}

export interface TradeRecord {
  id: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  total_value: number;
  fund_balance_after: number;
  region: string;
  timestamp: string;
}

export interface Holding {
  id: string;
  symbol: string;
  region: string;
  quantity: number;
  avg_price: number;
  total_cost: number;
  current_price: number;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
}

export interface AccountSummary {
  initial_fund: number;
  fund_balance: number;
  total_holdings_value: number;
  total_portfolio_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  region_balances: Record<string, number>;
  holdings: Holding[];
}

export interface TradeRecordsResponse {
  trades: TradeRecord[];
  account: AccountSummary;
}

export interface QuoteResponse {
  symbol: string;
  region: string;
  price: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  change: number;
  change_pct: number;
  timestamp: string;
}

// ── API functions ─────────────────────────────────────

export async function fetchHealth(): Promise<HealthStatus> {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function fetchMarketStatus(): Promise<MarketStatus> {
  const res = await fetch(`${BASE}/market-status`);
  return res.json();
}

export async function fetchQuote(region: string, symbol: string): Promise<QuoteResponse> {
  const res = await fetch(`${BASE}/quote?region=${encodeURIComponent(region)}&symbol=${encodeURIComponent(symbol)}`);
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

export async function buyStock(req: BuyRequest): Promise<TradeRecord> {
  const res = await fetch(`${BASE}/buy`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Buy failed');
  }
  return res.json();
}

export async function sellStock(req: SellRequest): Promise<TradeRecord> {
  const res = await fetch(`${BASE}/sell`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.detail || 'Sell failed');
  }
  return res.json();
}

export async function fetchRecords(limit = 50, offset = 0, region?: string): Promise<TradeRecordsResponse> {
  let url = `${BASE}/records?limit=${limit}&offset=${offset}`;
  if (region) url += `&region=${encodeURIComponent(region)}`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchAccount(): Promise<AccountSummary> {
  const res = await fetch(`${BASE}/account`);
  return res.json();
}
