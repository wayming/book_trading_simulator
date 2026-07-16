interface Props {
  marketOpen: boolean;
  itickConfigured: boolean;
  configOpen: boolean;
  onToggleConfig: () => void;
}

export default function Header({ marketOpen, itickConfigured, configOpen, onToggleConfig }: Props) {
  return (
    <header>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <h1>Book Trading Simulator</h1>
        <span style={{ display: 'flex', alignItems: 'center', fontSize: 12, gap: 4 }}>
          <span className={`dot ${marketOpen ? 'ok' : 'err'}`} />
          <span style={{ opacity: 0.8 }}>{marketOpen ? 'Market Open' : 'Market Closed'}</span>
        </span>
        <span style={{ display: 'flex', alignItems: 'center', fontSize: 12, gap: 4, marginLeft: 8 }}>
          <span className={`dot ${itickConfigured ? 'ok' : 'err'}`} />
          <span style={{ opacity: 0.8 }}>{itickConfigured ? 'iTick Ready' : 'iTick: Not Set'}</span>
        </span>
      </div>
      <button className="header-btn" onClick={onToggleConfig}>
        {configOpen ? '✕ Close' : '⚙ Config'}
      </button>
    </header>
  );
}
