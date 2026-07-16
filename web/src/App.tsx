import { useState, useEffect, useCallback } from 'react';
import {
  fetchHealth, fetchConfig, fetchRecords, updateConfig, buyStock, sellStock,
  type ConfigResponse, type ConfigUpdate, type TradeRecord, type TradeRecordsResponse,
} from './api';
import Header from './components/Header';
import ConfigPanel from './components/ConfigPanel';
import BuyForm from './components/BuyForm';
import SellForm from './components/SellForm';
import AccountSummary from './components/AccountSummary';
import TradeRecords from './components/TradeRecords';

const MAX_ITEMS = 200;

export default function App() {
  const [config, setConfig] = useState<ConfigResponse | null>(null);
  const [configOpen, setConfigOpen] = useState(false);
  const [data, setData] = useState<TradeRecordsResponse | null>(null);
  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [health, setHealth] = useState({ database: false, itick_configured: false, market_open: false });

  // Initial data load
  useEffect(() => {
    fetchHealth().then(h => setHealth(h));
    fetchConfig().then(c => setConfig(c));
    fetchRecords(MAX_ITEMS).then(d => {
      setData(d);
      setTrades(d.trades);
    });
  }, []);

  // Periodic health + data refresh
  useEffect(() => {
    const t = setInterval(() => {
      fetchHealth().then(h => setHealth(h));
      fetchRecords(MAX_ITEMS).then(d => {
        setData(d);
        setTrades(d.trades);
      });
    }, 15000);
    return () => clearInterval(t);
  }, []);

  // Refresh data after a trade (buy or sell)
  const refreshData = useCallback(async () => {
    const d = await fetchRecords(MAX_ITEMS);
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

  const handleBuy = useCallback(async (region: string, fundAmount: number, symbol: string) => {
    await buyStock({ region, fund_amount: fundAmount, symbol });
    await refreshData();
  }, [refreshData]);

  const handleSell = useCallback(async (symbol: string) => {
    await sellStock({ symbol });
    await refreshData();
  }, [refreshData]);

  return (
    <>
      <Header
        marketOpen={health.market_open}
        itickConfigured={health.itick_configured}
        configOpen={configOpen}
        onToggleConfig={() => setConfigOpen(prev => !prev)}
      />

      <div className="layout">
        {/* Column 1: Config + Buy + Sell */}
        <div className="col">
          <BuyForm onBuy={handleBuy} />
          <SellForm onSell={handleSell} />
        </div>

        {/* Column 2: Account Summary */}
        <div className="col">
          <AccountSummary account={data?.account ?? null} />
        </div>

        {/* Column 3: Trade Records */}
        <div className="col">
          <TradeRecords trades={trades} />
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
