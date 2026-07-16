import { useState } from 'react';
import type { ConfigResponse, ConfigUpdate } from '../api';

interface Props {
  config: ConfigResponse | null;
  open: boolean;
  onClose: () => void;
  onSaved: (cfg: ConfigResponse) => void;
  onSave: (cfg: ConfigUpdate) => Promise<ConfigResponse>;
}

export default function ConfigPanel({ config, open, onClose, onSaved, onSave }: Props) {
  const [fund, setFund] = useState(String(config?.initial_fund ?? 10000));
  const [token, setToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSave = async () => {
    setError(null);
    setSaving(true);
    try {
      const fundVal = parseFloat(fund);
      if (isNaN(fundVal) || fundVal <= 0) {
        setError('Initial fund must be a positive number.');
        setSaving(false);
        return;
      }
      if (!token.trim()) {
        setError('iTick token is required.');
        setSaving(false);
        return;
      }
      const result = await onSave({ initial_fund: fundVal, itick_token: token.trim() });
      onSaved(result);
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="config-overlay" onClick={onClose}>
      <div className="config-card" onClick={e => e.stopPropagation()}>
        <h2>Simulator Configuration</h2>

        <div className="form-group">
          <label>Initial Fund ($)</label>
          <input
            type="number"
            value={fund}
            onChange={e => setFund(e.target.value)}
            placeholder="10000"
            min="0"
            step="1000"
            style={{ width: '100%' }}
          />
        </div>

        <div className="form-group">
          <label>iTick API Token</label>
          <input
            type="password"
            value={token}
            onChange={e => setToken(e.target.value)}
            placeholder={config?.itick_token_masked || 'Enter your iTick API token'}
            style={{ width: '100%' }}
          />
        </div>

        {error && <div className="alert alert-error">{error}</div>}

        <div className="btn-row">
          <button className="btn" onClick={onClose} style={{ background: '#f3f4f6', color: '#333' }}>
            Cancel
          </button>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving} style={{ width: 'auto' }}>
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
