import { useState, useEffect } from 'react';

interface Props {
  onSell: (symbol: string, region: string) => Promise<void>;
  defaultRegion?: string;
}

export default function SellForm({ onSell, defaultRegion = 'AU' }: Props) {
  const [region, setRegion] = useState(defaultRegion);
  useEffect(() => { setRegion(defaultRegion); }, [defaultRegion]);
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    if (!symbol.trim()) {
      setMessage({ type: 'error', text: 'Symbol is required.' });
      return;
    }

    setLoading(true);
    try {
      await onSell(symbol.trim().toUpperCase(), region);
      setMessage({ type: 'success', text: `Sell order executed for ${symbol.trim().toUpperCase()}` });
      setSymbol('');
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Sell failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3>Sell Stock</h3>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Region</label>
          <select value={region} onChange={e => setRegion(e.target.value)} style={{ width: '100%' }}>
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

        <button type="submit" className="btn btn-danger" disabled={loading}>
          {loading ? 'Selling...' : 'Sell All'}
        </button>

        {message && (
          <div className={`alert alert-${message.type}`}>{message.text}</div>
        )}
      </form>
    </div>
  );
}
