import { useState } from 'react';

interface Props {
  onBuy: (region: string, fundAmount: number, symbol: string) => Promise<void>;
}

export default function BuyForm({ onBuy }: Props) {
  const [region, setRegion] = useState('AU');
  const [fundAmount, setFundAmount] = useState('');
  const [symbol, setSymbol] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    const amount = parseFloat(fundAmount);
    if (isNaN(amount) || amount <= 0) {
      setMessage({ type: 'error', text: 'Fund amount must be a positive number.' });
      return;
    }
    if (!symbol.trim()) {
      setMessage({ type: 'error', text: 'Symbol is required.' });
      return;
    }

    setLoading(true);
    try {
      await onBuy(region, amount, symbol.trim().toUpperCase());
      setMessage({ type: 'success', text: `Buy order executed for ${symbol.trim().toUpperCase()}` });
      setFundAmount('');
      setSymbol('');
    } catch (e) {
      setMessage({ type: 'error', text: e instanceof Error ? e.message : 'Buy failed' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h3>Buy Stock</h3>
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>Region</label>
          <select value={region} onChange={e => setRegion(e.target.value)} style={{ width: '100%' }}>
            <option value="AU">AU — Australia (ASX)</option>
            <option value="US">US — United States</option>
            <option value="HK">HK — Hong Kong</option>
            <option value="SZ">SZ — Shenzhen</option>
            <option value="SH">SH — Shanghai</option>
          </select>
        </div>

        <div className="form-group">
          <label>Fund Amount ($)</label>
          <input
            type="number"
            value={fundAmount}
            onChange={e => setFundAmount(e.target.value)}
            placeholder="e.g. 5000"
            min="0"
            step="100"
            style={{ width: '100%' }}
          />
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
          {loading ? 'Buying...' : 'Buy'}
        </button>

        {message && (
          <div className={`alert alert-${message.type}`}>{message.text}</div>
        )}
      </form>
    </div>
  );
}
