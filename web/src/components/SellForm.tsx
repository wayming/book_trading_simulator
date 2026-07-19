import { useState, useEffect } from 'react';

interface Props {
  onSell: (exchange: string, symbol: string, quantity: number, price: number, orderType: string) => Promise<void>;
  defaultExchange?: string;
}

export default function SellForm({ onSell, defaultExchange = 'AU' }: Props) {
  const [exchange, setExchange] = useState(defaultExchange);
  useEffect(() => { setExchange(defaultExchange); }, [defaultExchange]);
  const [symbol, setSymbol] = useState('');
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [orderType, setOrderType] = useState('MARKET');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'error' | 'success'; text: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);

    const qty = parseInt(quantity);
    if (isNaN(qty) || qty <= 0) {
      setMessage({ type: 'error', text: 'Quantity must be a positive integer.' });
      return;
    }
    const prc = parseFloat(price);
    if (orderType === 'LIMIT' && (isNaN(prc) || prc <= 0)) {
      setMessage({ type: 'error', text: 'Limit price must be a positive number.' });
      return;
    }
    if (!symbol.trim()) {
      setMessage({ type: 'error', text: 'Symbol is required.' });
      return;
    }

    setLoading(true);
    try {
      await onSell(exchange, symbol.trim().toUpperCase(), qty, isNaN(prc) ? 0 : prc, orderType);
      setMessage({ type: 'success', text: `Sell order executed for ${symbol.trim().toUpperCase()}` });
      setSymbol('');
      setQuantity('');
      setPrice('');
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

        <div className="form-group">
          <label>Quantity (shares)</label>
          <input
            type="number"
            value={quantity}
            onChange={e => setQuantity(e.target.value)}
            placeholder="e.g. 50"
            min="1"
            step="1"
            style={{ width: '100%' }}
          />
        </div>

        <div className="form-group">
          <label>Order Type</label>
          <select value={orderType} onChange={e => setOrderType(e.target.value)} style={{ width: '100%' }}>
            <option value="MARKET">Market</option>
            <option value="LIMIT">Limit</option>
          </select>
        </div>

        {orderType === 'LIMIT' && (
          <div className="form-group">
            <label>Limit Price ($)</label>
            <input
              type="number"
              value={price}
              onChange={e => setPrice(e.target.value)}
              placeholder="e.g. 105.00"
              min="0"
              step="0.01"
              style={{ width: '100%' }}
            />
          </div>
        )}

        <button type="submit" className="btn btn-danger" disabled={loading}>
          {loading ? 'Selling...' : 'Sell'}
        </button>

        {message && (
          <div className={`alert alert-${message.type}`}>{message.text}</div>
        )}
      </form>
    </div>
  );
}
