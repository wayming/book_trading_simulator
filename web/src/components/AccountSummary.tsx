import type { AccountSummary as AccountSummaryType } from '../api';

interface Props {
  account: AccountSummaryType | null;
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AccountSummary({ account }: Props) {
  if (!account) {
    return (
      <div className="card" style={{ flex: 1 }}>
        <h3>Account Summary</h3>
        <div className="empty">Loading...</div>
      </div>
    );
  }

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <h3>Account Summary</h3>

      {/* Key metrics */}
      <div className="stats" style={{ marginBottom: 12 }}>
        <div className="stat">
          <div className="val">${fmt(account.fund_balance)}</div>
          <div className="lbl">Fund Balance</div>
        </div>
        <div className="stat">
          <div className="val">${fmt(account.total_holdings_value)}</div>
          <div className="lbl">Holdings Value</div>
        </div>
        <div className="stat">
          <div className="val">${fmt(account.total_portfolio_value)}</div>
          <div className="lbl">Portfolio Value</div>
        </div>
        <div className="stat">
          <div className={`val ${account.total_pnl >= 0 ? 'ok' : 'err'}`}>
            {account.total_pnl >= 0 ? '+' : ''}{fmt(account.total_pnl)}
          </div>
          <div className="lbl">Total P&amp;L ({account.total_pnl_pct >= 0 ? '+' : ''}{account.total_pnl_pct.toFixed(2)}%)</div>
        </div>
      </div>

      {/* Holdings list */}
      <h3 style={{ marginTop: 4 }}>Holdings ({account.holdings.length})</h3>
      {account.holdings.length === 0 ? (
        <div className="empty" style={{ padding: 20, fontSize: 12 }}>
          No holdings yet. Buy some stocks!
        </div>
      ) : (
        <div className="col-scroll">
          {account.holdings.map(h => (
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
                <span>Avg ${fmt(h.avg_price)}</span>
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
