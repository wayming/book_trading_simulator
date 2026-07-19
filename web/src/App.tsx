import { useState, useEffect, useCallback, useMemo } from 'react';
import {
  fetchHealth, fetchConfig, fetchRecords, updateConfig, submitOrder,
  type ConfigResponse, type ConfigUpdate, type TradeRecord, type TradeRecordsResponse,
} from './api';
import Header from './components/Header';
import ConfigPanel from './components/ConfigPanel';
import BuyForm from './components/BuyForm';
import SellForm from './components/SellForm';
import QuoteForm from './components/QuoteForm';
import AccountSummary from './components/AccountSummary';
import TradeRecords from './components/TradeRecords';

const EXCHANGES = ['AU', 'US', 'HK', 'SZ', 'SH', 'NL'];
const MAX_ITEMS = 200;

export default function App() {
  const [activeExchange, setActiveExchange] = useState('AU');
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [data, setData] = useState<TradeRecordsResponse | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [health, setHealth] = useState({ database: false, itick_configured: false, market_open: false });

  // Initial data load
  useEffect(() => {
    fetchHealth().then(h => setHealth(h));
    fetchConfig().then(c => setConfig(c));
    fetchRecords(MAX_ITEMS, 0).then(d => {
      setData(d);
      setTrades(d.trades);
    });
  }, []);

  // Periodic health + data refresh
  useEffect(() => {
    const t = setInterval(() => {
      fetchHealth().then(h => setHealth(h));
      fetchRecords(MAX_ITEMS, 0).then(d => {
        setData(d);
        setTrades(d.trades);
      });
    }, 15000);
    return () => clearInterval(t);
  }, []);

  // Refresh data after a trade
  const refreshData = useCallback(async () => {
    const d = await fetchRecords(MAX_ITEMS, 0);
    setData(d);
    setTrades(d.trades);
    const c = await fetchConfig();
    setConfig(c);
  }, []);

  const handleConfigSaved = useCallback((cfg: ConfigResponse) => {
    setConfig(cfg);
    setHealth(prev => ({ ...prev, itick_configured: true }));
  }, []);

  const handleSaveConfig = useCallback(async (cfg: ConfigUpdate): Promise<ConfigResponse> => {
    const result = await updateConfig(cfg);
    return result;
  }, []);

  const handleOrder = useCallback(async (side: string, exchange: string, symbol: string, quantity: number, price: number, orderType: string) => {
    await submitOrder({ side, exchange, symbol, quantity, price, order_type: orderType });
    await refreshData();
  }, [refreshData]);

  // Filter trades by active exchange
  const exchangeTrades = useMemo(
    () => trades.filter(t => t.exchange === activeExchange),
    [trades, activeExchange]
  );

  return (
    <>
      <Header
        itickConfigured={health.itick_configured}
        configOpen={configOpen}
        onToggleConfig={() => setConfigOpen(prev => !prev)}
      />

      {/* Exchange tabs */}
      <div className="tab-bar">
        {EXCHANGES.map(r => (
          <button
            key={r}
            className={`tab${r === activeExchange ? ' active' : ''}`}
            onClick={() => setActiveExchange(r)}
          >
            {r}
          </button>
        ))}
      </div>

      <div className="layout" style={{ height: 'calc(100vh - 48px - 45px)' }}>
        {/* Column 1: Quote + Buy + Sell */}
        <div className="col">
          <QuoteForm defaultExchange={activeExchange} />
          <BuyForm onSubmit={handleOrder} defaultExchange={activeExchange} />
          <SellForm onSubmit={handleOrder} defaultExchange={activeExchange} />
        </div>

        {/* Column 2: Account Summary */}
        <div className="col">
          <AccountSummary account={data?.account ?? null} exchange={activeExchange} />
        </div>

        {/* Column 3: Trade Records */}
        <div className="col">
          <TradeRecords trades={exchangeTrades} exchange={activeExchange} />
        </div>
      </div>

      <ConfigPanel
        config={config}
        open={configOpen}
        onClose={() => setConfigOpen(false)}
        onSaved={handleConfigSaved}
        onSave={handleSaveConfig}
      />
    </>
  );
}
