import type { TradeRecord } from '../api';

interface Props {
  trades: TradeRecord[];
  exchange: string;
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatDate(ts: string): string {
  if (!ts) return '';
  const d = new Date(ts);
  return d.toLocaleString('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export default function TradeRecords({ trades, exchange }: Props) {
  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      <h3>{exchange} · Trading Records ({trades.length})</h3>

      {trades.length === 0 ? (
        <div className="empty">
          <p>No trades in {exchange} yet</p>
          <p style={{ fontSize: 12, marginTop: 8 }}>Buy or sell stocks to see records here.</p>
        </div>
      ) : (
        <div className="col-scroll">
          <table className="trade-table">
            <thead>
              <tr>
                <th>Date</th>
                <th>Side</th>
                <th>Symbol</th>
                <th className="num">Qty</th>
                <th className="num">Price</th>
                <th className="num">Total</th>
                <th className="num">Cash After</th>
              </tr>
            </thead>
            <tbody>
              {trades.map(t => (
                <tr key={t.trade_id}>
                  <td style={{ fontSize: 11, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                    {formatDate(t.executed_at)}
                  </td>
                  <td>
                    <span className={`badge ${t.side === 'BUY' ? 'badge-buy' : 'badge-sell'}`}>
                      {t.side}
                    </span>
                  </td>
                  <td style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontWeight: 600 }}>
                    {t.symbol}
                  </td>
                  <td className="num">{t.filled_quantity}</td>
                  <td className="num">${fmt(t.filled_price)}</td>
                  <td className="num">${fmt(t.total_amount)}</td>
                  <td className="num">${fmt(t.remaining_cash)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
