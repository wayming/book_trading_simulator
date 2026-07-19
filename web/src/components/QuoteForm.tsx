import { useState, useEffect } from 'react';
import { fetchQuote, type QuoteResponse } from '../api';

interface Props {
  defaultExchange?: string;
}

function fmt(n: number): string {
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function QuoteForm({ defaultExchange = 'AU' }: Props) {
  const [exchange, setExchange] = useState(defaultExchange);
  useEffect(() => { setExchange(defaultExchange); }, [defaultExchange]);
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setQuote(null);

    if (!symbol.trim()) {
      setError('Symbol is required.');
      return;
    }

    setLoading(true);
    try {
      const result = await fetchQuote(exchange, symbol.trim().toUpperCase());
      setQuote(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Quote failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3>Stock Quote</h3>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Exchange</label>
          <select value={exchange} onChange={e => setExchange(e.target.value)} style={{ width: '100%' }}>
            <option value="AU">AU — Australia (ASX)</option>
            <option value="US">US — United States</option>
            <option value="HK">HK — Hong Kong</option>
            <option value="SZ">SZ — Shenzhen</option>
            <option value="SH">SH — Shanghai</option>
            <option value="NL">NL — Netherlands</option>
          </select>
        </div>

        <div className="form-group">
          <label>Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={e => setSymbol(e.target.value)}
            placeholder="e.g. CBA"
            style={{ width: '100%', textTransform: 'uppercase' }}
          />
        </div>

        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Fetching...' : 'Get Quote'}
        </button>
      </form>

      {error && <div className="alert alert-error" style={{ marginTop: 8 }}>{error}</div>}

      {quote && (
        <div style={{ marginTop: 12, padding: 10, background: '#f9fafb', borderRadius: 6, border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <span style={{ fontFamily: "'JetBrains Mono', 'Fira Code', monospace", fontWeight: 700, fontSize: 16 }}>
              {quote.symbol}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{quote.exchange}</span>
          </div>
          <div style={{ fontSize: 28, fontWeight: 700, color: quote.change >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            ${fmt(quote.current_price)}
          </div>
          <div style={{ fontSize: 12, marginTop: 2, color: quote.change >= 0 ? 'var(--success)' : 'var(--danger)' }}>
            {quote.change >= 0 ? '+' : ''}{fmt(quote.change)} ({quote.change_pct >= 0 ? '+' : ''}{quote.change_pct.toFixed(2)}%)
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <div className="stat" style={{ flex: 1 }}>
              <div className="val" style={{ fontSize: 14 }}>{fmt(quote.open_price)}</div>
              <div className="lbl">Open</div>
            </div>
            <div className="stat" style={{ flex: 1 }}>
              <div className="val" style={{ fontSize: 14 }}>{fmt(quote.high_price)}</div>
              <div className="lbl">High</div>
            </div>
            <div className="stat" style={{ flex: 1 }}>
              <div className="val" style={{ fontSize: 14 }}>{fmt(quote.low_price)}</div>
              <div className="lbl">Low</div>
            </div>
            <div className="stat" style={{ flex: 1 }}>
              <div className="val" style={{ fontSize: 14 }}>{quote.volume.toLocaleString()}</div>
              <div className="lbl">Volume</div>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            Previous Close: ${fmt(quote.previous_close)}
          </div>
        </div>
      )}
    </div>
  );
}
