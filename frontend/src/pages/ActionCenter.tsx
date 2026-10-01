import React, { useState, useEffect, useCallback, useMemo } from 'react';
import config from '../config';
import { radarApi, RadarSignal } from '../api/nexus';
const API_BASE = config.apiBase;

interface ActionItem {
  id: string;
  title: string;
  source: string;
  priority: string;
  due_date?: string;
  status: string;
  category: string;
  deep_link?: string;
}

interface PendingNotification {
  approval_id: string;
  category: string;
  title: string;
  message: string;
  channels: string[];
  created_at: string;
  status: string;
}

interface NotifPrefs {
  whatsapp_enabled: boolean;
  whatsapp_number: string | null;
  email_enabled: boolean;
  email_address: string | null;
  push_enabled: boolean;
  categories: Record<string, boolean>;
}

function formatDue(iso?: string): { text: string; urgent: boolean } | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const due = new Date(d);
  due.setHours(0, 0, 0, 0);
  const days = Math.round((due.getTime() - today.getTime()) / 86400000);
  let rel = '';
  if (days < 0) rel = 'overdue';
  else if (days === 0) rel = 'today';
  else if (days === 1) rel = 'tomorrow';
  else if (days <= 5) rel = `in ${days} days`;
  const text = `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}${rel ? ` · ${rel}` : ''}`;
  return { text, urgent: days <= 2 };
}

const CATEGORIES: Record<string, { label: string; color: string }> = {
  bill: { label: 'Bill', color: '#f59e0b' },
  appointment: { label: 'Appointment', color: '#8b5cf6' },
  school: { label: 'School', color: '#10b981' },
  delivery: { label: 'Delivery', color: '#3b82f6' },
  renewal: { label: 'Renewal', color: '#ec4899' },
  travel: { label: 'Travel', color: '#06b6d4' },
  refund: { label: 'Refund', color: '#22c55e' },
  action: { label: 'Action', color: '#ef4444' },
  other: { label: 'Other', color: '#6b7280' },
};
function categoryInfo(cat?: string) {
  return CATEGORIES[cat || ''] || { label: (cat || 'other')[0].toUpperCase() + (cat || 'other').slice(1), color: '#6b7280' };
}

const ActionCenter: React.FC = () => {
  const [activeTab, setActiveTab] = useState('action_items');
  const [actionItems, setActionItems] = useState<ActionItem[]>([]);
  const [pendingNotifs, setPendingNotifs] = useState<PendingNotification[]>([]);
  const [prefs, setPrefs] = useState<NotifPrefs | null>(null);
  const [loading, setLoading] = useState(true);
  const [editingPrefs, setEditingPrefs] = useState(false);
  const [whatsappNum, setWhatsappNum] = useState('');
  const [emailAddr, setEmailAddr] = useState('');
  const [digestMsg, setDigestMsg] = useState('');
  const [digestDays, setDigestDays] = useState(14);
  const [digestLoading, setDigestLoading] = useState(false);
  const [inboxes, setInboxes] = useState<{ id: string; email: string; provider: string; last_sync: string | null }[]>([]);
  const [showConnect, setShowConnect] = useState(false);
  const [gmailUser, setGmailUser] = useState('');
  const [gmailPass, setGmailPass] = useState('');
  const [connectMsg, setConnectMsg] = useState('');
  const [connecting, setConnecting] = useState(false);
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const token = localStorage.getItem('auth_token');

  const categoryCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const item of actionItems) c[item.category || 'other'] = (c[item.category || 'other'] || 0) + 1;
    return c;
  }, [actionItems]);
  const displayItems = useMemo(() => {
    if (categoryFilter === 'all') return actionItems;
    return actionItems.filter(item => (item.category || 'other') === categoryFilter);
  }, [actionItems, categoryFilter]);

  const headers = useCallback(() => ({
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  }), [token]);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_BASE}/api/integrations/action-items`, { headers: headers() }).then(r => r.json()).catch(() => ({ items: [] })),
      fetch(`${API_BASE}/api/notifications/pending`, { headers: headers() }).then(r => r.json()).catch(() => ({ pending: [] })),
      fetch(`${API_BASE}/api/notifications/preferences`, { headers: headers() }).then(r => r.json()).catch(() => ({ preferences: null })),
      radarApi.signals('open').catch(() => ({ signals: [] as RadarSignal[], counts: {} })),
      radarApi.accounts().catch(() => []),
    ]).then(([ai, notifs, prefsData, radar, accts]) => {
      const fromRadar: ActionItem[] = (radar.signals || []).map((s: RadarSignal) => ({
        id: s.id, title: s.subject, source: `inbox · ${s.sender_name || s.sender_domain || 'email'}`,
        priority: s.priority, due_date: s.due_date || undefined, status: 'open', category: s.category,
        deep_link: s.deep_link || undefined,
      }));
      setInboxes(accts as any[]);
      setActionItems([...fromRadar, ...(Array.isArray(ai.items) ? ai.items : Array.isArray(ai.action_items) ? ai.action_items : [])]);
      setPendingNotifs(notifs.pending || []);
      if (prefsData.preferences) {
        setPrefs(prefsData.preferences);
        setWhatsappNum(prefsData.preferences.whatsapp_number || '');
        setEmailAddr(prefsData.preferences.email_address || '');
      }
      setLoading(false);
    });
  }, [headers]);

  useEffect(() => { loadData(); }, [loadData]);

  const approveNotif = async (id: string) => {
    await fetch(`${API_BASE}/api/notifications/approve/${id}`, { method: 'POST', headers: headers() });
    loadData();
  };

  const rejectNotif = async (id: string) => {
    await fetch(`${API_BASE}/api/notifications/reject/${id}`, { method: 'POST', headers: headers() });
    loadData();
  };

  const savePrefs = async () => {
    await fetch(`${API_BASE}/api/notifications/preferences`, {
      method: 'PUT',
      headers: headers(),
      body: JSON.stringify({
        whatsapp_number: whatsappNum || null,
        whatsapp_enabled: !!whatsappNum,
        email_address: emailAddr || null,
        email_enabled: !!emailAddr,
      }),
    });
    setEditingPrefs(false);
    loadData();
  };

  const testChannel = async (channel: 'whatsapp' | 'email') => {
    const r = await fetch(`${API_BASE}/api/notifications/test/${channel}`, {
      method: 'POST', headers: headers(),
    });
    const d = await r.json();
    alert(d.success ? `✅ ${channel} test sent!` : `❌ ${d.error || 'Failed'}`);
  };

  const previewDigest = useCallback(() => {
    setDigestLoading(true);
    fetch(`${API_BASE}/api/notifications/digest/preview?earnings_days=${digestDays}`, { headers: headers() })
      .then(r => r.json())
      .then(d => { setDigestMsg(d.message || 'No data'); setDigestLoading(false); })
      .catch(() => { setDigestMsg('Failed to build digest'); setDigestLoading(false); });
  }, [digestDays, headers]);

  const sendDigest = async (now: boolean) => {
    setDigestLoading(true);
    const r = await fetch(`${API_BASE}/api/notifications/digest/send`, {
      method: 'POST', headers: headers(),
      body: JSON.stringify({ earnings_days: digestDays, auto_send: now }),
    });
    const d = await r.json();
    setDigestLoading(false);
    if (now) {
      const wa = d?.sent?.results?.whatsapp;
      alert(wa?.success ? '✅ Digest sent to WhatsApp!' : `Queued. ${wa?.error || 'Configure WhatsApp to deliver instantly.'}`);
    } else {
      alert('✅ Digest queued in Pending Approvals.');
    }
    loadData();
  };

  const tabs = [
    { id: 'action_items', label: 'Action Items', count: actionItems.length },
    { id: 'pending', label: 'Pending Approvals', count: pendingNotifs.length },
    { id: 'digest', label: 'Market Digest', count: 0 },
    { id: 'settings', label: 'Notification Settings', count: 0 },
  ];

  const priorityColor = (p: string) => {
    if (p === 'high' || p === 'urgent') return '#ef4444';
    if (p === 'medium') return '#f59e0b';
    return '#22c55e';
  };

  return (
    <div style={{ padding: '24px', maxWidth: 1200, margin: '0 auto' }}>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, margin: 0 }}>Action Center</h1>
        <p style={{ color: '#888', marginTop: 4, fontSize: 14 }}>
          Email action items, notifications, and alerts — all in one place
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border-color, #333)' }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            style={{
              padding: '10px 20px', border: 'none', cursor: 'pointer',
              background: 'transparent', fontSize: 14, fontWeight: 600,
              color: activeTab === t.id ? '#6366f1' : '#888',
              borderBottom: activeTab === t.id ? '2px solid #6366f1' : '2px solid transparent',
              display: 'flex', alignItems: 'center', gap: 6,
            }}
          >
            {t.label}
            {t.count > 0 && (
              <span style={{
                padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 700,
                background: '#6366f122', color: '#6366f1',
              }}>{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#888' }}>Loading...</div>
      ) : (
        <>
          {/* Action Items */}
          {activeTab === 'action_items' && (
            <div>
              <div style={{
                marginBottom: 12, padding: '14px 18px', borderRadius: 12,
                background: 'var(--card-bg, #1a1a2e)', border: '1px solid var(--border-color, #2a2a4a)',
              }}>
                {inboxes.length > 0 ? (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                    <div style={{ fontSize: 13 }}>
                      📬 <b>{inboxes[0].email}</b> <span style={{ color: '#888' }}>· {inboxes[0].last_sync ? `synced ${new Date(inboxes[0].last_sync).toLocaleString()}` : 'not synced yet'}</span>
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button disabled={connecting} onClick={async () => { setConnecting(true); setConnectMsg(''); try { const r = await radarApi.sync(14); setConnectMsg(r.report.map((x: any) => x.error ? `${x.account}: ${x.error}` : `${x.scanned} scanned, ${x.new_signals} new`).join(' · ')); loadData(); } catch (e: any) { setConnectMsg(String(e?.response?.data?.detail?.error || e?.response?.data?.detail || 'Sync failed')); } finally { setConnecting(false); } }}
                        style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: '#6366f1', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 12 }}>{connecting ? 'Syncing…' : 'Sync now'}</button>
                      <button onClick={async () => { await radarApi.removeAccount(inboxes[0].id); setShowConnect(true); setConnectMsg(''); loadData(); }}
                        style={{ padding: '6px 14px', borderRadius: 8, border: '1px solid #ef444455', background: 'transparent', color: '#ef4444', fontWeight: 600, cursor: 'pointer', fontSize: 12 }}>Disconnect</button>
                    </div>
                  </div>
                ) : showConnect ? (
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>Connect Gmail</div>
                    <div style={{ fontSize: 12, color: '#888', marginBottom: 10 }}>
                      Uses IMAP with a Google <b>App Password</b> (not your normal password). Google Account → Security → 2-Step Verification → App passwords → “Avira”. Avira reads headers only, masks personal data, and never stores email bodies.
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      <input value={gmailUser} onChange={e => setGmailUser(e.target.value)} placeholder="you@gmail.com" autoComplete="username"
                        style={{ flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color, #2a2a4a)', background: 'var(--bg-tertiary, #12122a)', color: 'inherit' }} />
                      <input value={gmailPass} onChange={e => setGmailPass(e.target.value)} type="password" placeholder="16-letter app password" autoComplete="new-password"
                        style={{ flex: 1, minWidth: 200, padding: '8px 12px', borderRadius: 8, border: '1px solid var(--border-color, #2a2a4a)', background: 'var(--bg-tertiary, #12122a)', color: 'inherit' }} />
                      <button disabled={connecting || !gmailUser || !gmailPass}
                        onClick={async () => {
                          setConnecting(true); setConnectMsg('');
                          try {
                            await radarApi.addAccount({ email: gmailUser.trim(), app_password: gmailPass, provider: 'gmail' });
                            setGmailPass(''); setConnectMsg('Connected. Scanning the last 14 days…');
                            const r = await radarApi.sync(14);
                            setConnectMsg(r.report.map((x: any) => x.error ? `${x.account}: ${x.error}` : `${x.scanned} emails scanned, ${x.new_signals} action items found`).join(' · '));
                            setShowConnect(false); loadData();
                          } catch (e: any) {
                            const d = e?.response?.data?.detail; setConnectMsg(typeof d === 'string' ? d : d?.error || 'Could not connect.');
                          } finally { setConnecting(false); }
                        }}
                        style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: '#6366f1', color: '#fff', fontWeight: 600, cursor: 'pointer', opacity: connecting || !gmailUser || !gmailPass ? 0.5 : 1 }}>
                        {connecting ? 'Connecting…' : 'Connect & scan'}
                      </button>
                      <button onClick={() => { setShowConnect(false); setGmailPass(''); setConnectMsg(''); }} style={{ padding: '8px 12px', borderRadius: 8, border: 'none', background: 'transparent', color: '#888', cursor: 'pointer' }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
                    <div style={{ fontSize: 13, color: '#888' }}>
                      📭 No inbox connected. Connect Gmail to extract bills, appointments, school notices and deadlines.
                    </div>
                    <button onClick={() => setShowConnect(true)} style={{ padding: '8px 18px', borderRadius: 8, border: 'none', background: '#6366f1', color: '#fff', fontWeight: 600, cursor: 'pointer', fontSize: 12 }}>Connect Gmail</button>
                  </div>
                )}
                {connectMsg && <div style={{ fontSize: 12, marginTop: 8, color: connectMsg.toLowerCase().includes('fail') || connectMsg.toLowerCase().includes('not') || connectMsg.toLowerCase().includes('looks like') ? '#f59e0b' : '#22c55e' }}>{connectMsg}</div>}
              </div>
              {actionItems.length === 0 ? (
                <div style={{
                  textAlign: 'center', padding: 60,
                  background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
                  border: '1px solid var(--border-color, #2a2a4a)',
                }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>✅</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#888' }}>No pending action items</div>
                  <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
                    {inboxes.length ? 'Inbox connected — nothing actionable right now.' : 'Connect Gmail to auto-extract bills, appointments, school notices and deadlines from your inbox'}
                  </div>
                  {inboxes.length === 0 && (
                    <button
                      onClick={() => setShowConnect(true)}
                      style={{
                        marginTop: 16, padding: '8px 20px', borderRadius: 8, border: 'none',
                        background: '#6366f1', color: '#fff', fontWeight: 600, cursor: 'pointer',
                      }}
                    >
                      Connect Gmail
                    </button>
                  )}
                </div>
              ) : (
                <div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', marginBottom: 12 }}>
                    <span style={{ fontSize: 12, color: '#888' }}>Filter:</span>
                    <button onClick={() => setCategoryFilter('all')} style={{ padding: '4px 12px', borderRadius: 10, border: '1px solid var(--border-color, #2a2a4a)', background: categoryFilter === 'all' ? '#6366f1' : 'var(--card-bg, #1a1a2e)', color: categoryFilter === 'all' ? '#fff' : '#aaa', fontSize: 12, cursor: 'pointer' }}>All ({actionItems.length})</button>
                    {Object.entries(categoryCounts).map(([cat, count]) => {
                      const info = categoryInfo(cat);
                      const active = categoryFilter === cat;
                      return (
                        <button key={cat} onClick={() => setCategoryFilter(cat)} style={{ padding: '4px 12px', borderRadius: 10, border: `1px solid ${info.color}`, background: active ? info.color : 'var(--card-bg, #1a1a2e)', color: active ? '#fff' : info.color, fontSize: 12, fontWeight: 600, cursor: 'pointer' }}>
                          {info.label} ({count})
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ fontSize: 12, color: '#666', marginBottom: 12 }}>✓ Promotional and newsletter emails are filtered out automatically.</div>
                  {displayItems.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: 40, color: '#888' }}>No items in this category.</div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {displayItems.map((item, i) => (
                        <div key={i} style={{
                            padding: '14px 18px', borderRadius: 8,
                            background: 'var(--card-bg, #1a1a2e)',
                            border: '1px solid var(--border-color, #2a2a4a)',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                          }}>
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: 600, fontSize: 14 }}>{item.title}</div>
                              <div style={{ fontSize: 12, color: '#888', marginTop: 4, display: 'flex', gap: 12, alignItems: 'center' }}>
                                <span>Source: {item.source}</span>
                                {item.due_date && (() => {
                                  const due = formatDue(item.due_date);
                                  return due ? <span style={{ color: due.urgent ? '#f59e0b' : 'inherit', fontWeight: due.urgent ? 600 : 400 }}>Due: {due.text}</span> : null;
                                })()}
                                <span style={{ padding: '1px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600, background: categoryInfo(item.category).color + '22', color: categoryInfo(item.category).color }}>{categoryInfo(item.category).label}</span>
                              </div>
                      </div>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <span style={{
                          padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                          background: priorityColor(item.priority) + '22',
                          color: priorityColor(item.priority),
                        }}>{item.priority}</span>
                        {item.deep_link && (
                          <a href={item.deep_link} target="_blank" rel="noreferrer" style={{
                            padding: '4px 12px', borderRadius: 6, textDecoration: 'none',
                            background: '#6366f122', color: '#6366f1', fontSize: 12, fontWeight: 600,
                          }}>Open</a>
                        )}
                        <button
                          onClick={async () => { if (item.source.startsWith('inbox')) { await radarApi.update(item.id, 'done'); loadData(); } }}
                          style={{
                            padding: '4px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                            background: '#22c55e22', color: '#22c55e', fontSize: 12, fontWeight: 600,
                          }}>Done</button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
              )}
            </div>
          )}

          {/* Pending Notifications */}
          {activeTab === 'pending' && (
            <div>
              {pendingNotifs.length === 0 ? (
                <div style={{
                  textAlign: 'center', padding: 60,
                  background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
                  border: '1px solid var(--border-color, #2a2a4a)',
                }}>
                  <div style={{ fontSize: 32, marginBottom: 8 }}>🔔</div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: '#888' }}>No pending notifications</div>
                  <div style={{ fontSize: 13, color: '#666', marginTop: 4 }}>
                    Notifications from earnings alerts, price alerts, and action items will appear here for your approval
                  </div>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {pendingNotifs.map((n) => (
                    <div key={n.approval_id} style={{
                      padding: '14px 18px', borderRadius: 8,
                      background: 'var(--card-bg, #1a1a2e)',
                      border: '1px solid var(--border-color, #2a2a4a)',
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: 14 }}>{n.title}</div>
                          <div style={{ fontSize: 13, color: '#ccc', marginTop: 4, lineHeight: 1.5 }}>{n.message}</div>
                          <div style={{ fontSize: 12, color: '#888', marginTop: 6, display: 'flex', gap: 12 }}>
                            <span>Category: {n.category}</span>
                            <span>Channels: {n.channels.join(', ')}</span>
                            <span>{new Date(n.created_at).toLocaleString()}</span>
                          </div>
                        </div>
                        <div style={{ display: 'flex', gap: 8, marginLeft: 16 }}>
                          <button
                            onClick={() => approveNotif(n.approval_id)}
                            style={{
                              padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
                              background: '#22c55e', color: '#fff', fontWeight: 600, fontSize: 13,
                            }}
                          >
                            Send
                          </button>
                          <button
                            onClick={() => rejectNotif(n.approval_id)}
                            style={{
                              padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
                              background: '#ef444422', color: '#ef4444', fontWeight: 600, fontSize: 13,
                            }}
                          >
                            Dismiss
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Market Digest */}
          {activeTab === 'digest' && (
            <div style={{
              background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
              border: '1px solid var(--border-color, #2a2a4a)', padding: 24,
            }}>
              <h3 style={{ fontSize: 18, fontWeight: 600, marginTop: 0, marginBottom: 6 }}>
                📈 Market & Earnings Digest
              </h3>
              <p style={{ fontSize: 13, color: '#888', marginTop: 0, marginBottom: 16 }}>
                A concise snapshot of the market regime, AI Boom index, and upcoming earnings —
                ready to share to your WhatsApp.
              </p>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
                <span style={{ fontSize: 13, color: '#aaa' }}>Earnings window:</span>
                {[7, 14, 30, 60, 90].map(d => (
                  <button key={d} onClick={() => setDigestDays(d)} style={{
                    padding: '4px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                    background: digestDays === d ? '#6366f1' : 'var(--bg-secondary, #252540)',
                    color: digestDays === d ? '#fff' : '#aaa', fontSize: 12, fontWeight: 600,
                  }}>{d}d</button>
                ))}
                <button onClick={previewDigest} disabled={digestLoading} style={{
                  padding: '6px 16px', borderRadius: 6, border: 'none', cursor: 'pointer',
                  background: '#6366f1', color: '#fff', fontWeight: 600, fontSize: 13, marginLeft: 8,
                }}>{digestLoading ? 'Loading…' : 'Preview'}</button>
              </div>

              <pre style={{
                background: 'var(--bg-secondary, #0f0f1e)', borderRadius: 8, padding: 16,
                fontSize: 13, color: '#ddd', whiteSpace: 'pre-wrap', wordBreak: 'break-word',
                fontFamily: 'inherit', minHeight: 120, margin: 0, lineHeight: 1.6,
              }}>
                {digestMsg || 'Click "Preview" to generate the latest digest.'}
              </pre>

              <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
                <button onClick={() => sendDigest(false)} disabled={digestLoading} style={{
                  padding: '10px 20px', borderRadius: 8, border: 'none', cursor: 'pointer',
                  background: '#6366f122', color: '#6366f1', fontWeight: 600,
                }}>Queue for Approval</button>
                <button onClick={() => sendDigest(true)} disabled={digestLoading || !prefs?.whatsapp_enabled} style={{
                  padding: '10px 20px', borderRadius: 8, border: 'none',
                  cursor: prefs?.whatsapp_enabled ? 'pointer' : 'not-allowed',
                  background: prefs?.whatsapp_enabled ? '#22c55e' : '#22c55e22',
                  color: prefs?.whatsapp_enabled ? '#fff' : '#22c55e88', fontWeight: 600,
                }}>Send to WhatsApp now</button>
              </div>
              {!prefs?.whatsapp_enabled && (
                <div style={{ fontSize: 12, color: '#888', marginTop: 10 }}>
                  Enable WhatsApp in <b>Notification Settings</b> to deliver instantly.
                </div>
              )}
            </div>
          )}

          {/* Notification Settings */}
          {activeTab === 'settings' && (
            <div style={{
              background: 'var(--card-bg, #1a1a2e)', borderRadius: 12,
              border: '1px solid var(--border-color, #2a2a4a)', padding: 24,
            }}>
              <h3 style={{ fontSize: 18, fontWeight: 600, marginBottom: 20, marginTop: 0 }}>
                Notification Channels
              </h3>
              <p style={{ fontSize: 13, color: '#888', marginBottom: 20, marginTop: 0 }}>
                Configure where you'd like to receive alerts. All notifications require your explicit approval before sending.
              </p>

              {/* WhatsApp */}
              <div style={{
                padding: 16, borderRadius: 8, marginBottom: 12,
                background: 'var(--bg-secondary, #252540)',
                border: prefs?.whatsapp_enabled ? '1px solid #22c55e33' : '1px solid transparent',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>📱 WhatsApp</div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                      {prefs?.whatsapp_enabled ? `Connected: ${prefs.whatsapp_number}` : 'Not configured'}
                    </div>
                  </div>
                  <span style={{
                    padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: prefs?.whatsapp_enabled ? '#22c55e22' : '#88888822',
                    color: prefs?.whatsapp_enabled ? '#22c55e' : '#888',
                  }}>
                    {prefs?.whatsapp_enabled ? 'Active' : 'Inactive'}
                  </span>
                </div>
                {editingPrefs && (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      value={whatsappNum}
                      onChange={e => setWhatsappNum(e.target.value)}
                      placeholder="+1234567890"
                      style={{
                        flex: 1, padding: '8px 12px', borderRadius: 6,
                        border: '1px solid var(--border-color, #333)',
                        background: 'var(--bg-primary, #0f0f23)', color: 'var(--text-color, #e0e0e0)',
                      }}
                    />
                    {prefs?.whatsapp_enabled && (
                      <button onClick={() => testChannel('whatsapp')} style={{
                        padding: '8px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                        background: '#6366f122', color: '#6366f1', fontWeight: 600, fontSize: 12,
                      }}>Test</button>
                    )}
                  </div>
                )}
              </div>

              {/* Email */}
              <div style={{
                padding: 16, borderRadius: 8, marginBottom: 12,
                background: 'var(--bg-secondary, #252540)',
                border: prefs?.email_enabled ? '1px solid #22c55e33' : '1px solid transparent',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>📧 Email</div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>
                      {prefs?.email_enabled ? `Connected: ${prefs.email_address}` : 'Not configured'}
                    </div>
                  </div>
                  <span style={{
                    padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: prefs?.email_enabled ? '#22c55e22' : '#88888822',
                    color: prefs?.email_enabled ? '#22c55e' : '#888',
                  }}>
                    {prefs?.email_enabled ? 'Active' : 'Inactive'}
                  </span>
                </div>
                {editingPrefs && (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <input
                      value={emailAddr}
                      onChange={e => setEmailAddr(e.target.value)}
                      placeholder="you@example.com"
                      style={{
                        flex: 1, padding: '8px 12px', borderRadius: 6,
                        border: '1px solid var(--border-color, #333)',
                        background: 'var(--bg-primary, #0f0f23)', color: 'var(--text-color, #e0e0e0)',
                      }}
                    />
                    {prefs?.email_enabled && (
                      <button onClick={() => testChannel('email')} style={{
                        padding: '8px 12px', borderRadius: 6, border: 'none', cursor: 'pointer',
                        background: '#6366f122', color: '#6366f1', fontWeight: 600, fontSize: 12,
                      }}>Test</button>
                    )}
                  </div>
                )}
              </div>

              {/* Push Notifications */}
              <div style={{
                padding: 16, borderRadius: 8, marginBottom: 20,
                background: 'var(--bg-secondary, #252540)',
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 15 }}>🔔 Push Notifications</div>
                    <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>Coming soon — mobile app integration</div>
                  </div>
                  <span style={{
                    padding: '2px 10px', borderRadius: 4, fontSize: 11, fontWeight: 600,
                    background: '#88888822', color: '#888',
                  }}>Coming Soon</span>
                </div>
              </div>

              {/* Alert Categories */}
              <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>Alert Categories</h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8, marginBottom: 20 }}>
                {[
                  { key: 'earnings_alerts', label: 'Earnings Alerts', desc: 'Upcoming earnings, beat/miss reports' },
                  { key: 'price_alerts', label: 'Price Alerts', desc: 'Stock price triggers' },
                  { key: 'action_items', label: 'Action Items', desc: 'Email-extracted tasks and deadlines' },
                  { key: 'calendar_reminders', label: 'Calendar Reminders', desc: 'Event and appointment reminders' },
                  { key: 'market_alerts', label: 'Market Alerts', desc: 'VIX spikes, major moves' },
                ].map(cat => (
                  <div key={cat.key} style={{
                    padding: 12, borderRadius: 8,
                    background: 'var(--bg-secondary, #252540)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                  }}>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: 13 }}>{cat.label}</div>
                      <div style={{ fontSize: 11, color: '#888' }}>{cat.desc}</div>
                    </div>
                    <div style={{
                      width: 36, height: 20, borderRadius: 10, cursor: 'pointer',
                      background: prefs?.categories?.[cat.key] ? '#6366f1' : '#333',
                      position: 'relative', transition: 'background 0.2s',
                    }}>
                      <div style={{
                        width: 16, height: 16, borderRadius: '50%', background: '#fff',
                        position: 'absolute', top: 2,
                        left: prefs?.categories?.[cat.key] ? 18 : 2,
                        transition: 'left 0.2s',
                      }} />
                    </div>
                  </div>
                ))}
              </div>

              {/* Actions */}
              <div style={{ display: 'flex', gap: 8 }}>
                {editingPrefs ? (
                  <>
                    <button onClick={savePrefs} style={{
                      padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: '#22c55e', color: '#fff', fontWeight: 600,
                    }}>Save Changes</button>
                    <button onClick={() => setEditingPrefs(false)} style={{
                      padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
                      background: '#ef444422', color: '#ef4444', fontWeight: 600,
                    }}>Cancel</button>
                  </>
                ) : (
                  <button onClick={() => setEditingPrefs(true)} style={{
                    padding: '10px 24px', borderRadius: 8, border: 'none', cursor: 'pointer',
                    background: '#6366f1', color: '#fff', fontWeight: 600,
                  }}>Edit Settings</button>
                )}
              </div>

              {/* Governance Notice */}
              <div style={{
                marginTop: 20, padding: 12, borderRadius: 8,
                background: '#6366f108', border: '1px solid #6366f122', fontSize: 12, color: '#888', lineHeight: 1.5,
              }}>
                <b style={{ color: '#6366f1' }}>Governance:</b> Avira will never send any notification without your explicit approval.
                All outbound messages are queued and shown in the "Pending Approvals" tab first.
                You control what gets sent and where.
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default ActionCenter;
