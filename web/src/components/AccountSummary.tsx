import type { AccountSummary as AccountSummaryType } from '../api';

interface Props {
  account: AccountSummaryType | null;
  region: string;
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function AccountSummary({ account, region }: Props) {
  if (!account) {
    return (
      <div className="card" style={{ flex: 1 }}>
        <h3>{region} · Account</h3>
        <div className="empty">Loading...</div>
      </div>
    );
  }

  const regionBalance = account.region_balances[region] ?? 0;
  const regionHoldings = account.holdings.filter(h => h.region === region);
  const holdingsValue = regionHoldings.reduce((sum, h) => sum + h.market_value, 0);
  const portfolioValue = regionBalance + holdingsValue;
  const pnl = portfolioValue - account.initial_fund;
  const pnlPct = account.initial_fund > 0 ? (pnl / account.initial_fund) * 100 : 0;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <h3>{region} · Account</h3>

      {/* Key metrics */}
      <div className="stats" style={{ marginBottom: 12 }}>
        <div className="stat">
          <div className="val">${fmt(regionBalance)}</div>
          <div className="lbl">Fund Balance</div>
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
      <h3 style={{ marginTop: 4 }}>Holdings ({regionHoldings.length})</h3>
      {regionHoldings.length === 0 ? (
        <div className="empty" style={{ padding: 20, fontSize: 12 }}>
          No holdings in {region}. Buy some stocks!
        </div>
      ) : (
        <div className="col-scroll">
          {regionHoldings.map(h => (
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
