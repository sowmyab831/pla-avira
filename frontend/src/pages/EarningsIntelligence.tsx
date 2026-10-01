import React, { useState, useEffect, useCallback } from 'react';
import config from '../config';
const API_BASE = config.apiBase;

interface EarningsEntry {
  symbol: string;
  name: string;
  earnings_date: string;
  earnings_time: string;
  market_cap: number;
  sector: string;
  price: number;
  pe_ratio: number;
  eps_estimate: number;
  recommendation: string;
}

interface FullIntelligence {
  symbol: string;
  generated_at: string;
  llm_analysis: any;
  financials: any;
  sec_filings: any[];
  insider_trading: any;
  buyback: any;
  leadership: any;
  competitors: any[];
  supply_chain: any;
  geopolitical: any;
  analyst: any;
  social_sentiment: any;
  options: any;
  macro: any;
}

const fmtCap = (n: number) => {
  if (!n) return 'N/A';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
};
const pct = (n: number | undefined) => n != null ? `${(n * 100).toFixed(1)}%` : 'N/A';
const signalColor = (s: string) => {
  if (!s) return '#888';
  const l = s.toLowerCase();
  if (l === 'bullish' || l === 'buy') return '#22c55e';
  if (l === 'bearish' || l === 'sell') return '#ef4444';
  return '#f59e0b';
};

const DEEP_DIVE_STEPS = [
  { id: 'financials', label: 'Financials & earnings history', icon: '📊' },
  { id: 'sec', label: 'SEC filings (8-K / 10-K / 10-Q)', icon: '📄' },
  { id: 'insider', label: 'Insider trading activity', icon: '🕵️' },
  { id: 'buyback', label: 'Buyback & capital returns', icon: '💰' },
  { id: 'leadership', label: 'Leadership & governance', icon: '👔' },
  { id: 'competitors', label: 'Competitor positioning', icon: '⚔️' },
  { id: 'supply', label: 'Supply chain exposure', icon: '🔗' },
  { id: 'geopolitical', label: 'Geopolitical risk', icon: '🌐' },
  { id: 'analyst', label: 'Analyst ratings & targets', icon: '🎯' },
  { id: 'sentiment', label: 'Social sentiment', icon: '💬' },
  { id: 'options', label: 'Options flow & IV', icon: '📈' },
  { id: 'macro', label: 'Macro environment', icon: '🌍' },
  { id: 'llm', label: 'AI synthesis (qwen2.5:14b)', icon: '🧠' },
];

const EarningsIntelligence: React.FC = () => {
  const [upcoming, setUpcoming] = useState<EarningsEntry[]>([]);
  const [loadingUpcoming, setLoadingUpcoming] = useState(true);
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [intel, setIntel] = useState<FullIntelligence | null>(null);
  const [loadingIntel, setLoadingIntel] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');
  const [searchSymbol, setSearchSymbol] = useState('');
  const [daysAhead, setDaysAhead] = useState(90);
  const [deepDiveStep, setDeepDiveStep] = useState(0);
  const [deepDiveElapsed, setDeepDiveElapsed] = useState(0);
  const token = localStorage.getItem('auth_token');

  const headers = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  // Load upcoming earnings (public endpoint, no auth required)
  useEffect(() => {
    setLoadingUpcoming(true);
    fetch(`${API_BASE}/api/public/market/earnings/upcoming?days=${daysAhead}`)
      .then(r => r.json())
      .then(d => { setUpcoming(d.earnings || []); setLoadingUpcoming(false); })
      .catch(() => setLoadingUpcoming(false));
  }, [daysAhead]);

  // Advance the deep-dive step indicator while the analysis runs.
  // Steps tick on a timer (the backend runs all dimensions in one request),
  // slowing down as it approaches the LLM synthesis stage.
  useEffect(() => {
    if (!loadingIntel) return;
    setDeepDiveStep(0);
    setDeepDiveElapsed(0);
    const tick = setInterval(() => {
      setDeepDiveElapsed(e => e + 1);
      setDeepDiveStep(s => {
        // Front-load fast data fetches, linger on the LLM step
        const maxStep = DEEP_DIVE_STEPS.length - 1;
        return s < maxStep ? s + 1 : s;
      });
    }, 1400);
    return () => clearInterval(tick);
  }, [loadingIntel]);

  // Load full intelligence for selected symbol
  const loadIntelligence = useCallback((sym: string) => {
    setSelectedSymbol(sym);
    setLoadingIntel(true);
    setIntel(null);
    setActiveTab('overview');
    fetch(`${API_BASE}/api/earnings/intelligence/${sym}`, { headers: headers() })
      .then(r => r.json())
      .then(d => { setIntel(d); setLoadingIntel(false); })
      .catch(() => setLoadingIntel(false));
  }, [headers]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchSymbol.trim()) loadIntelligence(searchSymbol.trim().toUpperCase());
  };

  const tabs = [
    { id: 'overview', label: 'AI Analysis' },
    { id: 'financials', label: 'Financials' },
    { id: 'insider', label: 'Insider Trading' },
    { id: 'analysts', label: 'Analysts' },
    { id: 'options', label: 'Options Flow' },
    { id: 'supply', label: 'Supply Chain' },
    { id: 'leadership', label: 'Leadership' },
    { id: 'competitors', label: 'Competitors' },
    { id: 'sentiment', label: 'Sentiment' },
    { id: 'sec', label: 'SEC Filings' },
  ];

  return (
    <div style={{ padding: '16px', maxWidth: 1400, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20, flexWrap: 'wrap', gap: 12 }}>
        <div style={{ flex: 1, minWidth: 200 }}>
          <h1 style={{ fontSize: 24, fontWeight: 700, margin: 0 }}>Earnings Intelligence</h1>
          <p style={{ color: '#888', marginTop: 4, fontSize: 13 }}>
            12-dimension AI-powered pre-earnings analysis
          </p>
        </div>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
          <input
            value={searchSymbol}
            onChange={e => setSearchSymbol(e.target.value.toUpperCase())}
            placeholder="Symbol (e.g. NVDA)"
            style={{
              padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color, #333)',
              background: 'var(--card-bg, #1a1a2e)', color: 'var(--text-color, #e0e0e0)',
              fontSize: 14, width: 120,
            }}
          />
          <button
            type="submit"
            style={{
              padding: '8px 16px', borderRadius: 8, border: 'none',
              background: 'linear-gradient(135deg, #6366f1, #8b5cf6)', color: '#fff',
              fontWeight: 600, cursor: 'pointer', fontSize: 14,
            }}
          >
            Analyze
          </button>
        </form>
      </div>

      {/* Upcoming Earnings Calendar */}
      <div style={{
        background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
        border: '1px solid var(--border-color, #2a2a4a)', padding: 16, marginBottom: 20,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 8 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, margin: 0 }}>Upcoming Earnings</h2>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {[14, 30, 60, 90].map(d => (
              <button
                key={d}
                onClick={() => setDaysAhead(d)}
                style={{
                  padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
                  background: daysAhead === d ? '#6366f1' : 'var(--bg-secondary, #252540)',
                  color: daysAhead === d ? '#fff' : '#aaa', fontSize: 12, fontWeight: 600,
                }}
              >
                {d}d
              </button>
            ))}
          </div>
        </div>

        {loadingUpcoming ? (
          <div style={{ textAlign: 'center', padding: 30, color: '#888' }}>
            <div style={{ fontSize: 24, marginBottom: 8 }}>⏳</div>
            Scanning earnings calendar...
          </div>
        ) : upcoming.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 30, color: '#888', fontSize: 13 }}>
            No upcoming earnings found in the next {daysAhead} days.
            <br />Use the search bar above to analyze any stock.
          </div>
        ) : (
          <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 800 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color, #333)' }}>
                  {['Date', 'Symbol', 'Company', 'Price', 'P/E', 'EPS Est.', 'Cap', 'Sector', 'Rating', 'Action'].map(h => (
                    <th key={h} style={{ padding: '8px 8px', textAlign: 'left', color: '#888', fontWeight: 600, fontSize: 10, textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {upcoming.map((e, i) => (
                  <tr
                    key={i}
                    style={{
                      borderBottom: '1px solid var(--border-color, #222)',
                      cursor: 'pointer',
                      background: selectedSymbol === e.symbol ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                    }}
                    onClick={() => loadIntelligence(e.symbol)}
                  >
                    <td style={{ padding: '8px 8px', whiteSpace: 'nowrap' }}>
                      <span style={{ fontWeight: 600, fontSize: 12 }}>{e.earnings_date}</span>
                      <span style={{ color: '#888', marginLeft: 4, fontSize: 10 }}>{e.earnings_time}</span>
                    </td>
                    <td style={{ padding: '8px 8px', fontWeight: 700, color: '#6366f1', fontSize: 12 }}>{e.symbol}</td>
                    <td style={{ padding: '8px 8px', maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>{e.name}</td>
                    <td style={{ padding: '8px 8px', fontFamily: 'monospace', fontSize: 12 }}>${e.price?.toFixed(2)}</td>
                    <td style={{ padding: '8px 8px', fontFamily: 'monospace', fontSize: 12 }}>{e.pe_ratio?.toFixed(1) || '–'}</td>
                    <td style={{ padding: '8px 8px', fontFamily: 'monospace', fontSize: 12 }}>${e.eps_estimate?.toFixed(2) || '–'}</td>
                    <td style={{ padding: '8px 8px', fontSize: 11 }}>{fmtCap(e.market_cap)}</td>
                    <td style={{ padding: '8px 8px', fontSize: 11, color: '#aaa' }}>{e.sector}</td>
                    <td style={{ padding: '8px 8px' }}>
                      <span style={{
                        padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                        background: signalColor(e.recommendation) + '22',
                        color: signalColor(e.recommendation),
                      }}>
                        {e.recommendation || '–'}
                      </span>
                    </td>
                    <td style={{ padding: '8px 8px' }}>
                      <button
                        onClick={(ev) => { ev.stopPropagation(); loadIntelligence(e.symbol); }}
                        style={{
                          padding: '4px 10px', borderRadius: 6, border: 'none', cursor: 'pointer',
                          background: '#6366f1', color: '#fff', fontSize: 10, fontWeight: 600,
                        }}
                      >
                        Deep Dive
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Full Intelligence Report */}
      {(loadingIntel || intel) && (
        <div style={{
          background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
          border: '1px solid var(--border-color, #2a2a4a)', padding: 16,
        }}>
          {loadingIntel ? (
            <div style={{ padding: '24px 16px' }}>
              {/* Deep Dive workspace header */}
              <div style={{ textAlign: 'center', marginBottom: 20 }}>
                <div style={{ fontSize: 28, marginBottom: 8 }}>🧠</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: '#e0e0e0' }}>
                  Deep-diving {selectedSymbol}
                </div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 4 }}>
                  Running 12-dimension pre-earnings analysis · {deepDiveElapsed}s elapsed
                </div>
              </div>

              {/* Progress bar */}
              <div style={{
                height: 6, background: '#252540', borderRadius: 3, marginBottom: 20,
                overflow: 'hidden', maxWidth: 560, margin: '0 auto 20px',
              }}>
                <div style={{
                  width: `${Math.min(95, ((deepDiveStep + 1) / DEEP_DIVE_STEPS.length) * 100)}%`,
                  height: '100%', borderRadius: 3,
                  background: 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                  transition: 'width 0.8s ease',
                }} />
              </div>

              {/* Step checklist — two columns on wide screens */}
              <div style={{
                display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                gap: 6, maxWidth: 760, margin: '0 auto',
              }}>
                {DEEP_DIVE_STEPS.map((step, i) => {
                  const done = i < deepDiveStep;
                  const active = i === deepDiveStep;
                  return (
                    <div key={step.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '7px 10px', borderRadius: 8, fontSize: 12,
                      background: active ? 'rgba(99,102,241,0.12)' : 'transparent',
                      border: active ? '1px solid rgba(99,102,241,0.35)' : '1px solid transparent',
                      color: done ? '#22c55e' : active ? '#c7d2fe' : '#555',
                      transition: 'all 0.3s ease',
                    }}>
                      <span style={{ width: 18, textAlign: 'center', flexShrink: 0 }}>
                        {done ? '✓' : active ? (
                          <span style={{
                            display: 'inline-block', width: 10, height: 10, borderRadius: '50%',
                            border: '2px solid #6366f1', borderTopColor: 'transparent',
                            animation: 'spin 0.8s linear infinite',
                          }} />
                        ) : '○'}
                      </span>
                      <span style={{ marginRight: 4 }}>{step.icon}</span>
                      <span style={{ fontWeight: active ? 600 : 400 }}>{step.label}</span>
                    </div>
                  );
                })}
              </div>

              <div style={{ textAlign: 'center', marginTop: 18, fontSize: 11, color: '#666' }}>
                You can keep browsing — the report will appear here when ready.
              </div>
            </div>
          ) : intel && (
            <>
              {/* Symbol Header */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16, flexWrap: 'wrap', gap: 12 }}>
                <div style={{ flex: 1, minWidth: 200 }}>
                  <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0 }}>
                    {intel.financials?.name || intel.symbol}
                    <span style={{ color: '#6366f1', marginLeft: 6, fontSize: 16 }}>({intel.symbol})</span>
                  </h2>
                  <p style={{ color: '#888', margin: '4px 0 0', fontSize: 12 }}>
                    {intel.financials?.sector} · {intel.financials?.industry} · {fmtCap(intel.financials?.market_cap)} · ${intel.financials?.price?.toFixed(2)}
                  </p>
                </div>
                {intel.llm_analysis?.overall_outlook && (
                  <div style={{
                    padding: '6px 16px', borderRadius: 8,
                    background: signalColor(intel.llm_analysis.overall_outlook) + '22',
                    color: signalColor(intel.llm_analysis.overall_outlook),
                    fontWeight: 700, fontSize: 14, textTransform: 'uppercase',
                  }}>
                    {intel.llm_analysis.overall_outlook}
                    {intel.llm_analysis.confidence && (
                      <span style={{ fontSize: 11, opacity: 0.8, marginLeft: 6 }}>
                        {intel.llm_analysis.confidence}% conf.
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Tab Navigation */}
              <div style={{
                display: 'flex', gap: 4, marginBottom: 16, overflowX: 'auto', WebkitOverflowScrolling: 'touch',
                borderBottom: '1px solid var(--border-color, #333)', paddingBottom: 0,
              }}>
                {tabs.map(t => (
                  <button
                    key={t.id}
                    onClick={() => setActiveTab(t.id)}
                    style={{
                      padding: '8px 12px', border: 'none', cursor: 'pointer',
                      background: 'transparent', fontSize: 12, fontWeight: 600, whiteSpace: 'nowrap',
                      color: activeTab === t.id ? '#6366f1' : '#888',
                      borderBottom: activeTab === t.id ? '2px solid #6366f1' : '2px solid transparent',
                    }}
                  >
                    {t.label}
                  </button>
                ))}
              </div>

              {/* Tab Content */}
              <div style={{ minHeight: 300 }}>
                {/* AI Analysis */}
                {activeTab === 'overview' && intel.llm_analysis && (
                  <div>
                    {intel.llm_analysis.summary && (
                      <div style={{
                        padding: 14, borderRadius: 8, marginBottom: 16,
                        background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.2)',
                      }}>
                        <div style={{ fontWeight: 600, marginBottom: 6, color: '#6366f1', fontSize: 13 }}>Executive Summary</div>
                        <div style={{ lineHeight: 1.6, fontSize: 13 }}>{intel.llm_analysis.summary}</div>
                      </div>
                    )}

                    {/* Scenarios */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12, marginBottom: 16 }}>
                      {[
                        { key: 'bull_case', label: 'Bull Case', color: '#22c55e', icon: '🐂' },
                        { key: 'base_case', label: 'Base Case', color: '#f59e0b', icon: '📊' },
                        { key: 'bear_case', label: 'Bear Case', color: '#ef4444', icon: '🐻' },
                      ].map(sc => {
                        const data = intel.llm_analysis[sc.key];
                        if (!data) return null;
                        return (
                          <div key={sc.key} style={{
                            padding: 12, borderRadius: 8,
                            background: sc.color + '0a', border: `1px solid ${sc.color}33`,
                          }}>
                            <div style={{ fontWeight: 600, color: sc.color, marginBottom: 6, fontSize: 13 }}>
                              {sc.icon} {sc.label}
                              {data.probability != null && (
                                <span style={{ float: 'right', fontSize: 11, opacity: 0.8 }}>
                                  {data.probability}% prob
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: 12, lineHeight: 1.5, color: '#ccc' }}>
                              {data.scenario}
                            </div>
                            {data.target_price > 0 && (
                              <div style={{ marginTop: 8, fontFamily: 'monospace', fontWeight: 600, color: sc.color, fontSize: 13 }}>
                                Target: ${data.target_price}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>

                    {/* Key Factors + Risks + Catalysts */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 12 }}>
                      {[
                        { key: 'key_factors', label: 'Key Factors', icon: '🔑' },
                        { key: 'risks', label: 'Risks', icon: '⚠️' },
                        { key: 'catalysts', label: 'Catalysts', icon: '🚀' },
                      ].map(section => {
                        const items = intel.llm_analysis[section.key];
                        if (!items || !Array.isArray(items)) return null;
                        return (
                          <div key={section.key} style={{
                            padding: 12, borderRadius: 8,
                            background: 'var(--bg-secondary, #252540)',
                          }}>
                            <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>{section.icon} {section.label}</div>
                            {items.map((item: string, i: number) => (
                              <div key={i} style={{ fontSize: 12, padding: '3px 0', color: '#bbb', lineHeight: 1.4 }}>
                                • {item}
                              </div>
                            ))}
                          </div>
                        );
                      })}
                    </div>

                    {/* Earnings Estimate + Recommendation */}
                    {intel.llm_analysis.earnings_estimate && (
                      <div style={{
                        marginTop: 16, padding: 12, borderRadius: 8,
                        background: 'var(--bg-secondary, #252540)',
                        display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 12,
                      }}>
                        <div>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>EPS Est.</div>
                          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }}>
                            ${intel.llm_analysis.earnings_estimate.eps_estimate?.toFixed(2) || '–'}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>Revenue Est.</div>
                          <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }}>
                            {intel.llm_analysis.earnings_estimate.revenue_estimate || '–'}
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>Beat Probability</div>
                          <div style={{ fontSize: 16, fontWeight: 700, color: '#6366f1' }}>
                            {intel.llm_analysis.earnings_estimate.beat_probability || '–'}%
                          </div>
                        </div>
                        <div>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>AI Recommendation</div>
                          <div style={{
                            fontSize: 16, fontWeight: 700,
                            color: signalColor(intel.llm_analysis.recommendation),
                            textTransform: 'uppercase',
                          }}>
                            {intel.llm_analysis.recommendation || '–'}
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Financials Tab */}
                {activeTab === 'financials' && intel.financials && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
                      {[
                        { label: 'Revenue Growth', value: pct(intel.financials.revenue_growth) },
                        { label: 'Earnings Growth', value: pct(intel.financials.earnings_growth) },
                        { label: 'Profit Margin', value: pct(intel.financials.profit_margins) },
                        { label: 'Gross Margin', value: pct(intel.financials.gross_margins) },
                        { label: 'P/E (Trailing)', value: intel.financials.pe_ratio?.toFixed(1) || '–' },
                        { label: 'P/E (Forward)', value: intel.financials.forward_pe?.toFixed(1) || '–' },
                        { label: 'PEG Ratio', value: intel.financials.peg_ratio?.toFixed(2) || '–' },
                        { label: 'Beta', value: intel.financials.beta?.toFixed(2) || '–' },
                        { label: 'EPS (TTM)', value: `$${intel.financials.eps_trailing?.toFixed(2) || '–'}` },
                        { label: 'EPS (FWD)', value: `$${intel.financials.eps_forward?.toFixed(2) || '–'}` },
                        { label: 'FCF', value: fmtCap(intel.financials.free_cash_flow) },
                        { label: 'D/E Ratio', value: intel.financials.debt_to_equity?.toFixed(1) || '–' },
                      ].map((m, i) => (
                        <div key={i} style={{ padding: 10, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>{m.label}</div>
                          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace', marginTop: 4 }}>{m.value}</div>
                        </div>
                      ))}
                    </div>
                    {intel.financials.earnings_history?.length > 0 && (
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)', overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Earnings History (Last 4 Quarters)</div>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 400 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #333' }}>
                              {['Quarter', 'EPS Estimate', 'EPS Actual', 'Surprise'].map(h => (
                                <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#888', fontSize: 10 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {intel.financials.earnings_history.map((eh: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                <td style={{ padding: '6px 8px', fontSize: 12 }}>{eh.quarter}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12 }}>${eh.eps_estimate?.toFixed(2)}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12 }}>${eh.eps_actual?.toFixed(2)}</td>
                                <td style={{
                                  padding: '6px 8px', fontFamily: 'monospace', fontWeight: 600, fontSize: 12,
                                  color: eh.surprise_pct > 0 ? '#22c55e' : eh.surprise_pct < 0 ? '#ef4444' : '#888',
                                }}>
                                  {eh.surprise_pct > 0 ? '+' : ''}{eh.surprise_pct?.toFixed(1)}%
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Insider Trading */}
                {activeTab === 'insider' && intel.insider_trading && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10, marginBottom: 16 }}>
                      <div style={{
                        padding: 12, borderRadius: 8, background: '#22c55e11', border: '1px solid #22c55e33',
                      }}>
                        <div style={{ fontSize: 10, color: '#888' }}>BUYS (90d)</div>
                        <div style={{ fontSize: 24, fontWeight: 700, color: '#22c55e' }}>
                          {intel.insider_trading.buy_count_90d || 0}
                        </div>
                      </div>
                      <div style={{
                        padding: 12, borderRadius: 8, background: '#ef444411', border: '1px solid #ef444433',
                      }}>
                        <div style={{ fontSize: 10, color: '#888' }}>SELLS (90d)</div>
                        <div style={{ fontSize: 24, fontWeight: 700, color: '#ef4444' }}>
                          {intel.insider_trading.sell_count_90d || 0}
                        </div>
                      </div>
                      <div style={{
                        padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)',
                      }}>
                        <div style={{ fontSize: 10, color: '#888' }}>SIGNAL</div>
                        <div style={{
                          fontSize: 18, fontWeight: 700, textTransform: 'uppercase',
                          color: signalColor(intel.insider_trading.signal),
                        }}>
                          {intel.insider_trading.signal || '–'}
                        </div>
                      </div>
                    </div>
                    {intel.insider_trading.recent_transactions?.length > 0 && (
                      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 500 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #333' }}>
                              {['Insider', 'Title', 'Type', 'Date', 'Shares', 'Value'].map(h => (
                                <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#888', fontSize: 10 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {intel.insider_trading.recent_transactions.map((t: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                <td style={{ padding: '6px 8px', fontWeight: 600, fontSize: 12 }}>{t.insider}</td>
                                <td style={{ padding: '6px 8px', color: '#aaa', fontSize: 11 }}>{t.relation}</td>
                                <td style={{
                                  padding: '6px 8px', fontSize: 12,
                                  color: t.transaction?.toLowerCase().includes('buy') ? '#22c55e' : '#ef4444',
                                }}>{t.transaction}</td>
                                <td style={{ padding: '6px 8px', fontSize: 12 }}>{t.date}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12 }}>{t.shares?.toLocaleString()}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12 }}>{fmtCap(t.value)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Analysts */}
                {activeTab === 'analysts' && intel.analyst && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
                      {[
                        { label: 'Consensus', value: intel.analyst.recommendation?.toUpperCase() || '–', color: signalColor(intel.analyst.recommendation) },
                        { label: 'Mean Target', value: `$${intel.analyst.target_mean?.toFixed(2) || '–'}`, color: '#6366f1' },
                        { label: 'Low / High', value: `$${intel.analyst.target_low?.toFixed(0) || '–'} – $${intel.analyst.target_high?.toFixed(0) || '–'}`, color: '#888' },
                        { label: '# Analysts', value: intel.analyst.num_analysts || '–', color: '#f59e0b' },
                      ].map((m, i) => (
                        <div key={i} style={{ padding: 10, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>{m.label}</div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: m.color, marginTop: 4 }}>{m.value}</div>
                        </div>
                      ))}
                    </div>
                    {intel.analyst.recent_ratings?.length > 0 && (
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Recent Analyst Ratings</div>
                        {intel.analyst.recent_ratings.map((r: any, i: number) => (
                          <div key={i} style={{
                            display: 'flex', justifyContent: 'space-between', padding: '6px 0',
                            borderBottom: i < intel.analyst.recent_ratings.length - 1 ? '1px solid #222' : 'none',
                            fontSize: 12, flexWrap: 'wrap', gap: 8,
                          }}>
                            <span style={{ fontWeight: 600 }}>{r.firm}</span>
                            <span style={{ color: signalColor(r.grade) }}>{r.grade}</span>
                            <span style={{ color: '#888' }}>{r.date?.split(' ')[0]}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Options Flow */}
                {activeTab === 'options' && intel.options && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10, marginBottom: 16 }}>
                      {[
                        { label: 'P/C Ratio (OI)', value: intel.options.pc_ratio_oi?.toFixed(3) || '–' },
                        { label: 'P/C Ratio (Vol)', value: intel.options.pc_ratio_volume?.toFixed(3) || '–' },
                        { label: 'Avg IV', value: `${intel.options.avg_implied_volatility?.toFixed(1) || '–'}%` },
                        { label: 'Signal', value: intel.options.signal?.toUpperCase() || '–', color: signalColor(intel.options.signal) },
                      ].map((m, i) => (
                        <div key={i} style={{ padding: 10, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                          <div style={{ fontSize: 10, color: '#888', textTransform: 'uppercase' }}>{m.label}</div>
                          <div style={{ fontSize: 15, fontWeight: 700, color: (m as any).color || '#e0e0e0', marginTop: 4, fontFamily: 'monospace' }}>{m.value}</div>
                        </div>
                      ))}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
                      <div style={{ padding: 12, borderRadius: 8, background: '#22c55e0a', border: '1px solid #22c55e33' }}>
                        <div style={{ fontWeight: 600, color: '#22c55e', marginBottom: 8, fontSize: 13 }}>Calls</div>
                        <div style={{ fontSize: 12 }}>Open Interest: <b>{intel.options.total_call_oi?.toLocaleString() || '–'}</b></div>
                        <div style={{ fontSize: 12 }}>Volume: <b>{intel.options.total_call_volume?.toLocaleString() || '–'}</b></div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 8, background: '#ef44440a', border: '1px solid #ef444433' }}>
                        <div style={{ fontWeight: 600, color: '#ef4444', marginBottom: 8, fontSize: 13 }}>Puts</div>
                        <div style={{ fontSize: 12 }}>Open Interest: <b>{intel.options.total_put_oi?.toLocaleString() || '–'}</b></div>
                        <div style={{ fontSize: 12 }}>Volume: <b>{intel.options.total_put_volume?.toLocaleString() || '–'}</b></div>
                      </div>
                    </div>
                  </div>
                )}

                {/* Supply Chain */}
                {activeTab === 'supply' && intel.supply_chain && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10, marginBottom: 16 }}>
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Raw Materials</div>
                        {(intel.supply_chain.raw_materials || []).map((m: string, i: number) => (
                          <div key={i} style={{ fontSize: 12, padding: '3px 0', color: '#bbb' }}>• {m}</div>
                        ))}
                      </div>
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Key Suppliers</div>
                        {(intel.supply_chain.key_suppliers || []).map((s: string, i: number) => (
                          <div key={i} style={{ fontSize: 12, padding: '3px 0', color: '#bbb' }}>• {s}</div>
                        ))}
                      </div>
                      <div style={{ padding: 12, borderRadius: 8, background: '#ef44440a', border: '1px solid #ef444433' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, color: '#ef4444', fontSize: 13 }}>Supply Risks</div>
                        {(intel.supply_chain.supply_risks || []).map((r: string, i: number) => (
                          <div key={i} style={{ fontSize: 13, padding: '3px 0', color: '#fca5a5' }}>⚠ {r}</div>
                        ))}
                      </div>
                    </div>
                    {intel.supply_chain.commodity_prices && Object.keys(intel.supply_chain.commodity_prices).length > 0 && (
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Commodity Prices (30d)</div>
                        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                          {Object.entries(intel.supply_chain.commodity_prices).map(([key, val]: [string, any]) => (
                            <div key={key} style={{ fontSize: 13 }}>
                              <span style={{ textTransform: 'capitalize', fontWeight: 600 }}>{key}</span>: ${val.current}
                              <span style={{ color: val['30d_change_pct'] > 0 ? '#22c55e' : '#ef4444', marginLeft: 4 }}>
                                {val['30d_change_pct'] > 0 ? '+' : ''}{val['30d_change_pct']}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {intel.geopolitical?.risks?.length > 0 && (
                      <div style={{ padding: 14, borderRadius: 8, background: 'var(--bg-secondary, #252540)', marginTop: 12 }}>
                        <div style={{ fontWeight: 600, marginBottom: 8 }}>Geopolitical Exposure</div>
                        {intel.geopolitical.risks.map((r: any, i: number) => (
                          <div key={i} style={{ display: 'flex', gap: 12, padding: '6px 0', fontSize: 13, borderBottom: '1px solid #222' }}>
                            <span style={{ fontWeight: 600, minWidth: 100 }}>{r.region}</span>
                            <span style={{
                              padding: '1px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                              background: r.risk === 'high' ? '#ef444422' : r.risk === 'medium' ? '#f59e0b22' : '#22c55e22',
                              color: r.risk === 'high' ? '#ef4444' : r.risk === 'medium' ? '#f59e0b' : '#22c55e',
                            }}>{r.risk}</span>
                            <span style={{ color: '#aaa' }}>{r.detail}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Leadership */}
                {activeTab === 'leadership' && intel.leadership && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10, marginBottom: 16 }}>
                      {[
                        { label: 'Overall Risk', value: intel.leadership.governance_risk },
                        { label: 'Audit Risk', value: intel.leadership.audit_risk },
                        { label: 'Board Risk', value: intel.leadership.board_risk },
                        { label: 'Compensation', value: intel.leadership.compensation_risk },
                        { label: 'Shareholder Rights', value: intel.leadership.shareholder_rights_risk },
                      ].map((m, i) => (
                        <div key={i} style={{ padding: 10, borderRadius: 8, background: 'var(--bg-secondary, #252540)', textAlign: 'center' }}>
                          <div style={{ fontSize: 10, color: '#888' }}>{m.label}</div>
                          <div style={{ fontSize: 18, fontWeight: 700, marginTop: 4, color: typeof m.value === 'number' && m.value <= 3 ? '#22c55e' : typeof m.value === 'number' && m.value >= 7 ? '#ef4444' : '#f59e0b' }}>{m.value ?? '–'}</div>
                        </div>
                      ))}
                    </div>
                    {intel.leadership.officers?.length > 0 && (
                      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 400 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #333' }}>
                              {['Name', 'Title', 'Total Pay', 'Age'].map(h => (
                                <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#888', fontSize: 10 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {intel.leadership.officers.map((o: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                <td style={{ padding: '6px 8px', fontWeight: 600, fontSize: 12 }}>{o.name}</td>
                                <td style={{ padding: '6px 8px', color: '#aaa', fontSize: 11 }}>{o.title}</td>
                                <td style={{ padding: '6px 8px', fontFamily: 'monospace', fontSize: 12 }}>{o.total_pay ? fmtCap(o.total_pay) : '–'}</td>
                                <td style={{ padding: '6px 8px', fontSize: 12 }}>{o.age || '–'}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                )}

                {/* Competitors */}
                {activeTab === 'competitors' && intel.competitors && (
                  <div>
                    {Array.isArray(intel.competitors) && intel.competitors.length > 0 && intel.competitors[0].symbol ? (
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 10 }}>
                        {intel.competitors.map((c: any, i: number) => (
                          <div key={i} style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                            <div style={{ fontWeight: 700, fontSize: 14, marginBottom: 8 }}>
                              <span style={{ color: '#6366f1' }}>{c.symbol}</span> — {c.name}
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6, fontSize: 12 }}>
                              <div>Price: <b>${c.price?.toFixed(2)}</b></div>
                              <div>P/E: <b>{c.pe_ratio?.toFixed(1) || '–'}</b></div>
                              <div>Rev Growth: <b style={{ color: (c.revenue_growth || 0) > 0 ? '#22c55e' : '#ef4444' }}>{pct(c.revenue_growth)}</b></div>
                              <div>Margins: <b>{pct(c.profit_margins)}</b></div>
                              <div>Cap: <b>{fmtCap(c.market_cap)}</b></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ color: '#888', textAlign: 'center', padding: 30, fontSize: 13 }}>
                        Competitor data not available for this symbol.
                      </div>
                    )}
                  </div>
                )}

                {/* Sentiment */}
                {activeTab === 'sentiment' && intel.social_sentiment && (
                  <div>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(100px, 1fr))', gap: 10, marginBottom: 16 }}>
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontSize: 10, color: '#888' }}>AVG SENTIMENT</div>
                        <div style={{ fontSize: 24, fontWeight: 700, color: signalColor(intel.social_sentiment.signal) }}>
                          {intel.social_sentiment.avg_sentiment?.toFixed(3) || '0'}
                        </div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontSize: 10, color: '#888' }}>SIGNAL</div>
                        <div style={{ fontSize: 18, fontWeight: 700, color: signalColor(intel.social_sentiment.signal), textTransform: 'uppercase' }}>
                          {intel.social_sentiment.signal}
                        </div>
                      </div>
                      <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontSize: 10, color: '#888' }}>ARTICLES</div>
                        <div style={{ fontSize: 24, fontWeight: 700 }}>{intel.social_sentiment.article_count || 0}</div>
                      </div>
                    </div>
                    {intel.social_sentiment.articles?.map((a: any, i: number) => (
                      <div key={i} style={{
                        padding: '10px 12px', borderBottom: '1px solid #222', fontSize: 12,
                        display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8,
                      }}>
                        <div style={{ flex: 1, minWidth: 200 }}>
                          <div style={{ fontWeight: 500, lineHeight: 1.4 }}>{a.title}</div>
                          <div style={{ color: '#888', fontSize: 11, marginTop: 2 }}>{a.source} · {a.published}</div>
                        </div>
                        <span style={{
                          padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                          background: a.sentiment > 0.1 ? '#22c55e22' : a.sentiment < -0.1 ? '#ef444422' : '#f59e0b22',
                          color: a.sentiment > 0.1 ? '#22c55e' : a.sentiment < -0.1 ? '#ef4444' : '#f59e0b',
                        }}>
                          {a.sentiment?.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                )}

                {/* SEC Filings */}
                {activeTab === 'sec' && (
                  <div>
                    {intel.sec_filings?.length > 0 ? (
                      <div style={{ overflowX: 'auto', WebkitOverflowScrolling: 'touch' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, minWidth: 400 }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid #333' }}>
                              {['Form', 'Date', 'Document'].map(h => (
                                <th key={h} style={{ padding: '6px 8px', textAlign: 'left', color: '#888', fontSize: 10 }}>{h}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {intel.sec_filings.map((f: any, i: number) => (
                              <tr key={i} style={{ borderBottom: '1px solid #222' }}>
                                <td style={{ padding: '6px 8px' }}>
                                  <span style={{
                                    padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 600,
                                    background: f.form === '10-K' ? '#6366f122' : f.form === '8-K' ? '#f59e0b22' : '#22c55e22',
                                    color: f.form === '10-K' ? '#6366f1' : f.form === '8-K' ? '#f59e0b' : '#22c55e',
                                  }}>{f.form}</span>
                                </td>
                                <td style={{ padding: '6px 8px', fontSize: 12 }}>{f.date}</td>
                                <td style={{ padding: '6px 8px', fontSize: 12 }}>
                                  {f.url ? (
                                    <a href={f.url} target="_blank" rel="noopener noreferrer" style={{ color: '#6366f1', textDecoration: 'none' }}>
                                      {f.description || 'View Filing'}
                                    </a>
                                  ) : (
                                    <span style={{ color: '#888' }}>{f.description || '–'}</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div style={{ color: '#888', textAlign: 'center', padding: 30, fontSize: 13 }}>
                        No recent SEC filings found.
                      </div>
                    )}
                    {intel.buyback && (
                      <div style={{ marginTop: 16, padding: 12, borderRadius: 8, background: 'var(--bg-secondary, #252540)' }}>
                        <div style={{ fontWeight: 600, marginBottom: 8, fontSize: 13 }}>Share Structure</div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 8, fontSize: 12 }}>
                          <div>Shares Out: <b>{(intel.buyback.shares_outstanding / 1e9)?.toFixed(2)}B</b></div>
                          <div>Float: <b>{(intel.buyback.float_shares / 1e9)?.toFixed(2)}B</b></div>
                          <div>Short %: <b style={{ color: (intel.buyback.short_pct_float || 0) > 5 ? '#ef4444' : '#22c55e' }}>{(intel.buyback.short_pct_float * 100)?.toFixed(1)}%</b></div>
                          <div>Buyback: <b style={{ color: intel.buyback.has_active_buyback ? '#22c55e' : '#888' }}>{intel.buyback.has_active_buyback ? `Active (${fmtCap(intel.buyback.recent_buyback_amount)})` : 'None'}</b></div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}

      {/* Disclaimer */}
      <div style={{ marginTop: 24, padding: 12, borderRadius: 8, background: '#f59e0b11', border: '1px solid #f59e0b33', fontSize: 11, color: '#f59e0b', lineHeight: 1.5 }}>
        <b>Disclaimer:</b> AVIRA is an educational and research tool. Nothing displayed constitutes investment advice. 
        AI-generated analysis may contain errors. Past performance does not guarantee future results. 
        Always consult a licensed financial advisor before making investment decisions.
      </div>
    </div>
  );
};

export default EarningsIntelligence;
