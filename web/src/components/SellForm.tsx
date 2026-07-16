import { useState } from 'react';

interface Props {
  onSell: (symbol: string) => Promise<void>;
}

export default function SellForm({ onSell }: Props) {
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
      await onSell(symbol.trim().toUpperCase());
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
