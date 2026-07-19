import type { AccountSummary as AccountSummaryType } from '../api';

interface Props {
  account: AccountSummaryType | null;
  exchange: string;
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AccountSummary({ account, exchange }: Props) {
  if (!account) {
    return (
      <div className="card" style={{ flex: 1 }}>
        <h3>{exchange} · Account</h3>
        <div className="empty">Loading...</div>
      </div>
    );
  }

  const exchangeBalance = account.exchange_balances[exchange] ?? 0;
  const exchangeHoldings = account.holdings.filter(h => h.exchange === exchange);
  const holdingsValue = exchangeHoldings.reduce((sum, h) => sum + h.market_value, 0);
  const portfolioValue = exchangeBalance + holdingsValue;
  const pnl = portfolioValue - account.initial_fund;
  const pnlPct = account.initial_fund > 0 ? (pnl / account.initial_fund) * 100 : 0;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <h3>{exchange} · Account</h3>

      {/* Key metrics */}
      <div className="stats" style={{ marginBottom: 12 }}>
        <div className="stat">
          <div className="val">${fmt(exchangeBalance)}</div>
          <div className="lbl">Cash</div>
        </div>
        <div className="stat">
          <div className="val">${fmt(holdingsValue)}</div>
          <div className="lbl">Holdings Value</div>
        </div>
        <div className="stat">
          <div className="val">${fmt(portfolioValue)}</div>
          <div className="lbl">Portfolio Value</div>
        </div>
        <div className="stat">
          <div className={`val ${pnl >= 0 ? 'ok' : 'err'}`}>
            {pnl >= 0 ? '+' : ''}{fmt(pnl)}
          </div>
          <div className="lbl">P&amp;L ({pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%)</div>
        </div>
      </div>

      {/* Holdings */}
      <h3 style={{ marginTop: 4 }}>Holdings ({exchangeHoldings.length})</h3>
      {exchangeHoldings.length === 0 ? (
        <div className="empty" style={{ padding: 20, fontSize: 12 }}>
          No holdings in {exchange}. Buy some stocks!
        </div>
      ) : (
        <div className="col-scroll">
          {exchangeHoldings.map(h => (
            <div key={h.id} className="holding-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="holding-symbol">{h.symbol}</span>
                <span className={`holding-pnl ${h.unrealized_pnl >= 0 ? 'ok' : 'err'}`}>
                  {h.unrealized_pnl >= 0 ? '+' : ''}{fmt(h.unrealized_pnl)}
                  <span style={{ fontSize: 10, marginLeft: 4 }}>
                    ({h.unrealized_pnl_pct >= 0 ? '+' : ''}{h.unrealized_pnl_pct.toFixed(2)}%)
                  </span>
                </span>
              </div>
              <div className="holding-detail">
                <span>{h.quantity} shares</span>
                <span>Avg ${fmt(h.avg_cost)}</span>
                <span>Now ${fmt(h.current_price)}</span>
                <span>Mkt ${fmt(h.market_value)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
