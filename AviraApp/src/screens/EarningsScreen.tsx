/**
 * Earnings Intelligence Screen
 * Mobile view for upcoming earnings + 12-dimension deep analysis
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, RefreshControl, FlatList,
  Linking, Alert, Share,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import api from '../services/api';
// API base URL - matches mobile api.ts config
const API_BASE = 'http://localhost:30000';
const WATCHLIST_KEY = 'avira_earnings_watchlist';

interface EarningsEntry {
  symbol: string;
  name: string;
  earnings_date: string;
  earnings_time: string;
  price: number;
  pe_ratio: number;
  sector: string;
  recommendation: string;
  market_cap: number;
}

const fmtCap = (n: number) => {
  if (!n) return '–';
  if (n >= 1e12) return `$${(n / 1e12).toFixed(1)}T`;
  if (n >= 1e9) return `$${(n / 1e9).toFixed(1)}B`;
  if (n >= 1e6) return `$${(n / 1e6).toFixed(0)}M`;
  return `$${n}`;
};

const signalColor = (s: string) => {
  const l = (s || '').toLowerCase();
  if (l === 'bullish' || l === 'buy') return '#22c55e';
  if (l === 'bearish' || l === 'sell') return '#ef4444';
  return '#f59e0b';
};

export default function EarningsScreen() {
  const [upcoming, setUpcoming] = useState<EarningsEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [searchSymbol, setSearchSymbol] = useState('');
  const [selectedSymbol, setSelectedSymbol] = useState('');
  const [intel, setIntel] = useState<any>(null);
  const [loadingIntel, setLoadingIntel] = useState(false);
  const [days, setDays] = useState(90);
  const [sharing, setSharing] = useState(false);

  const loadUpcoming = useCallback(async () => {
    try {
      const d = await api.getUpcomingEarnings(days);
      setUpcoming(d.earnings || []);
    } catch { }
    setLoading(false);
    setRefreshing(false);
  }, [days]);

  useEffect(() => { loadUpcoming(); }, [loadUpcoming]);

  const analyzeSymbol = async (sym: string) => {
    setSelectedSymbol(sym.toUpperCase());
    setLoadingIntel(true);
    setIntel(null);
    try {
      const r = await fetch(`${API_BASE}/api/public/market/earnings/${sym}`);
      const d = await r.json();
      setIntel(d);
    } catch { }
    setLoadingIntel(false);
  };

  // Share the market + earnings digest via the phone's own WhatsApp.
  // Uses watchlist if symbols are present, otherwise general market digest.
  // Falls back to the native share sheet if WhatsApp isn't installed.
  const shareDigest = async () => {
    setSharing(true);
    try {
      // Load watchlist
      const stored = await AsyncStorage.getItem(WATCHLIST_KEY);
      const watchlist = stored ? JSON.parse(stored) : [];

      let digest;
      if (watchlist.length > 0) {
        digest = await api.getWatchDigest(watchlist, days > 30 ? 30 : days);
      } else {
        digest = await api.getMarketDigest(days > 30 ? 30 : days);
      }

      // WhatsApp uses *bold* / _italic_ markdown natively — message is preformatted.
      const text = digest.message || 'Avira Market Digest';
      const waUrl = `whatsapp://send?text=${encodeURIComponent(text)}`;
      const canOpen = await Linking.canOpenURL(waUrl);
      if (canOpen) {
        await Linking.openURL(waUrl);
      } else {
        await Share.share({ message: text, title: digest.title });
      }
    } catch (e) {
      Alert.alert('Share failed', 'Could not build the market digest. Try again.');
    }
    setSharing(false);
  };

  const renderEarningsItem = ({ item }: { item: EarningsEntry }) => (
    <TouchableOpacity
      style={[s.card, selectedSymbol === item.symbol && s.cardSelected]}
      onPress={() => analyzeSymbol(item.symbol)}
      activeOpacity={0.7}
    >
      <View style={s.cardRow}>
        <View style={{ flex: 1 }}>
          <Text style={s.symbol}>{item.symbol}</Text>
          <Text style={s.companyName} numberOfLines={1}>{item.name}</Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={s.date}>{item.earnings_date}</Text>
          <Text style={s.time}>{item.earnings_time}</Text>
        </View>
      </View>
      <View style={[s.cardRow, { marginTop: 8 }]}>
        <Text style={s.metric}>${item.price?.toFixed(2)}</Text>
        <Text style={s.metricLabel}>P/E {item.pe_ratio?.toFixed(1) || '–'}</Text>
        <Text style={s.metricLabel}>{fmtCap(item.market_cap)}</Text>
        {item.recommendation && (
          <View style={[s.badge, { backgroundColor: signalColor(item.recommendation) + '22' }]}>
            <Text style={[s.badgeText, { color: signalColor(item.recommendation) }]}>
              {item.recommendation}
            </Text>
          </View>
        )}
      </View>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={s.container}>
      {/* Header */}
      <View style={[s.header, { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }]}>
        <View>
          <Text style={s.title}>Earnings Intelligence</Text>
          <Text style={s.subtitle}>12-dimension AI analysis</Text>
        </View>
        <TouchableOpacity style={s.shareBtn} onPress={shareDigest} disabled={sharing}>
          <Text style={s.shareBtnText}>{sharing ? '…' : 'Share ▸ WhatsApp'}</Text>
        </TouchableOpacity>
      </View>

      {/* Search */}
      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={searchSymbol}
          onChangeText={t => setSearchSymbol(t.toUpperCase())}
          placeholder="Symbol (e.g. NVDA)"
          placeholderTextColor="#888"
          autoCapitalize="characters"
          returnKeyType="search"
          onSubmitEditing={() => searchSymbol && analyzeSymbol(searchSymbol)}
        />
        <TouchableOpacity
          style={s.searchBtn}
          onPress={() => searchSymbol && analyzeSymbol(searchSymbol)}
        >
          <Text style={s.searchBtnText}>Analyze</Text>
        </TouchableOpacity>
      </View>

      {/* Days filter */}
      <View style={s.filterRow}>
        {[14, 30, 60, 90].map(d => (
          <TouchableOpacity
            key={d}
            style={[s.filterBtn, days === d && s.filterBtnActive]}
            onPress={() => { setDays(d); setLoading(true); }}
          >
            <Text style={[s.filterBtnText, days === d && s.filterBtnTextActive]}>{d}d</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={{ flex: 1 }}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); loadUpcoming(); }} />}
      >
        {/* Upcoming List */}
        {loading ? (
          <ActivityIndicator size="large" color="#6366f1" style={{ marginTop: 40 }} />
        ) : upcoming.length === 0 ? (
          <View style={s.emptyState}>
            <Text style={s.emptyIcon}>📊</Text>
            <Text style={s.emptyText}>No upcoming earnings in {days} days</Text>
            <Text style={s.emptySubtext}>Use search to analyze any stock</Text>
          </View>
        ) : (
          upcoming.map((item, i) => (
            <View key={i}>{renderEarningsItem({ item })}</View>
          ))
        )}

        {/* Intelligence Report */}
        {loadingIntel && (
          <View style={s.intelLoading}>
            <ActivityIndicator size="large" color="#6366f1" />
            <Text style={s.intelLoadingText}>Running 12-dimension analysis for {selectedSymbol}...</Text>
            <Text style={s.intelLoadingSubtext}>
              Financials · Insider Trading · Analysts · Options · Supply Chain · LLM
            </Text>
          </View>
        )}

        {intel && !loadingIntel && (
          <View style={s.intelContainer}>
            {/* Header */}
            <View style={s.intelHeader}>
              <View>
                <Text style={s.intelSymbol}>{intel.financials?.name || intel.symbol}</Text>
                <Text style={s.intelMeta}>
                  {intel.financials?.sector} · ${intel.financials?.price?.toFixed(2)}
                </Text>
              </View>
              {intel.llm_analysis?.overall_outlook && (
                <View style={[s.outlookBadge, { backgroundColor: signalColor(intel.llm_analysis.overall_outlook) + '22' }]}>
                  <Text style={[s.outlookText, { color: signalColor(intel.llm_analysis.overall_outlook) }]}>
                    {intel.llm_analysis.overall_outlook?.toUpperCase()}
                  </Text>
                  {intel.llm_analysis.confidence && (
                    <Text style={[s.outlookConf, { color: signalColor(intel.llm_analysis.overall_outlook) }]}>
                      {intel.llm_analysis.confidence}%
                    </Text>
                  )}
                </View>
              )}
            </View>

            {/* Summary */}
            {intel.llm_analysis?.summary && (
              <View style={s.summaryBox}>
                <Text style={s.sectionTitle}>AI Summary</Text>
                <Text style={s.summaryText}>{intel.llm_analysis.summary}</Text>
              </View>
            )}

            {/* Scenarios */}
            {['bull_case', 'base_case', 'bear_case'].map(key => {
              const sc = intel.llm_analysis?.[key];
              if (!sc) return null;
              const label = key === 'bull_case' ? '🐂 Bull' : key === 'bear_case' ? '🐻 Bear' : '📊 Base';
              const color = key === 'bull_case' ? '#22c55e' : key === 'bear_case' ? '#ef4444' : '#f59e0b';
              return (
                <View key={key} style={[s.scenarioCard, { borderLeftColor: color }]}>
                  <View style={s.scenarioHeader}>
                    <Text style={[s.scenarioLabel, { color }]}>{label}</Text>
                    {sc.probability != null && (
                      <Text style={s.scenarioProb}>{sc.probability}% prob</Text>
                    )}
                  </View>
                  <Text style={s.scenarioText}>{sc.scenario}</Text>
                  {sc.target_price > 0 && (
                    <Text style={[s.scenarioTarget, { color }]}>Target: ${sc.target_price}</Text>
                  )}
                </View>
              );
            })}

            {/* Key Factors */}
            {intel.llm_analysis?.key_factors && (
              <View style={s.listSection}>
                <Text style={s.sectionTitle}>🔑 Key Factors</Text>
                {intel.llm_analysis.key_factors.map((f: string, i: number) => (
                  <Text key={i} style={s.listItem}>• {f}</Text>
                ))}
              </View>
            )}

            {/* Risks */}
            {intel.llm_analysis?.risks && (
              <View style={s.listSection}>
                <Text style={s.sectionTitle}>⚠️ Risks</Text>
                {intel.llm_analysis.risks.map((r: string, i: number) => (
                  <Text key={i} style={[s.listItem, { color: '#fca5a5' }]}>• {r}</Text>
                ))}
              </View>
            )}

            {/* Insider Trading */}
            {intel.insider_trading && (
              <View style={s.metricsRow}>
                <View style={[s.metricBox, { borderColor: '#22c55e33' }]}>
                  <Text style={s.metricBoxLabel}>Buys (90d)</Text>
                  <Text style={[s.metricBoxValue, { color: '#22c55e' }]}>
                    {intel.insider_trading.buy_count_90d || 0}
                  </Text>
                </View>
                <View style={[s.metricBox, { borderColor: '#ef444433' }]}>
                  <Text style={s.metricBoxLabel}>Sells (90d)</Text>
                  <Text style={[s.metricBoxValue, { color: '#ef4444' }]}>
                    {intel.insider_trading.sell_count_90d || 0}
                  </Text>
                </View>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Signal</Text>
                  <Text style={[s.metricBoxValue, { color: signalColor(intel.insider_trading.signal) }]}>
                    {intel.insider_trading.signal?.toUpperCase() || '–'}
                  </Text>
                </View>
              </View>
            )}

            {/* Options */}
            {intel.options && (
              <View style={s.metricsRow}>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>P/C Ratio</Text>
                  <Text style={s.metricBoxValue}>{intel.options.pc_ratio_oi?.toFixed(2) || '–'}</Text>
                </View>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Avg IV</Text>
                  <Text style={s.metricBoxValue}>{intel.options.avg_implied_volatility?.toFixed(1) || '–'}%</Text>
                </View>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Options Signal</Text>
                  <Text style={[s.metricBoxValue, { color: signalColor(intel.options.signal) }]}>
                    {intel.options.signal?.toUpperCase() || '–'}
                  </Text>
                </View>
              </View>
            )}

            {/* Analyst Consensus */}
            {intel.analyst && (
              <View style={s.metricsRow}>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Consensus</Text>
                  <Text style={[s.metricBoxValue, { color: signalColor(intel.analyst.recommendation) }]}>
                    {intel.analyst.recommendation?.toUpperCase() || '–'}
                  </Text>
                </View>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Target</Text>
                  <Text style={s.metricBoxValue}>${intel.analyst.target_mean?.toFixed(0) || '–'}</Text>
                </View>
                <View style={s.metricBox}>
                  <Text style={s.metricBoxLabel}>Analysts</Text>
                  <Text style={s.metricBoxValue}>{intel.analyst.num_analysts || '–'}</Text>
                </View>
              </View>
            )}

            {/* Disclaimer */}
            <View style={s.disclaimer}>
              <Text style={s.disclaimerText}>
                AI-generated research. Not financial advice. Always consult a licensed advisor.
              </Text>
            </View>
          </View>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  header: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: '#e0e0e0' },
  subtitle: { fontSize: 13, color: '#888', marginTop: 2 },
  shareBtn: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8,
    backgroundColor: '#25D366',
  },
  shareBtnText: { color: '#fff', fontWeight: '700', fontSize: 12 },
  searchRow: { flexDirection: 'row', paddingHorizontal: 20, marginBottom: 8, gap: 8 },
  searchInput: {
    flex: 1, padding: 10, borderRadius: 8, backgroundColor: '#1a1a2e',
    borderWidth: 1, borderColor: '#2a2a4a', color: '#e0e0e0', fontSize: 14,
  },
  searchBtn: {
    paddingHorizontal: 20, borderRadius: 8, justifyContent: 'center',
    backgroundColor: '#6366f1',
  },
  searchBtnText: { color: '#fff', fontWeight: '600', fontSize: 14 },
  filterRow: { flexDirection: 'row', paddingHorizontal: 20, marginBottom: 12, gap: 6 },
  filterBtn: { paddingHorizontal: 14, paddingVertical: 4, borderRadius: 6, backgroundColor: '#252540' },
  filterBtnActive: { backgroundColor: '#6366f1' },
  filterBtnText: { color: '#888', fontSize: 12, fontWeight: '600' },
  filterBtnTextActive: { color: '#fff' },
  card: {
    marginHorizontal: 20, marginBottom: 8, padding: 14, borderRadius: 10,
    backgroundColor: '#1a1a2e', borderWidth: 1, borderColor: '#2a2a4a',
  },
  cardSelected: { borderColor: '#6366f1' },
  cardRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  symbol: { fontSize: 16, fontWeight: '700', color: '#6366f1' },
  companyName: { fontSize: 12, color: '#aaa', marginTop: 2, maxWidth: 200 },
  date: { fontSize: 14, fontWeight: '600', color: '#e0e0e0' },
  time: { fontSize: 11, color: '#888' },
  metric: { fontSize: 14, fontWeight: '600', color: '#e0e0e0' },
  metricLabel: { fontSize: 12, color: '#888' },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  badgeText: { fontSize: 11, fontWeight: '600' },
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyIcon: { fontSize: 32 },
  emptyText: { fontSize: 16, fontWeight: '600', color: '#888', marginTop: 8 },
  emptySubtext: { fontSize: 13, color: '#666', marginTop: 4 },
  intelLoading: { alignItems: 'center', paddingVertical: 40 },
  intelLoadingText: { fontSize: 14, fontWeight: '600', color: '#888', marginTop: 12 },
  intelLoadingSubtext: { fontSize: 12, color: '#666', marginTop: 4, textAlign: 'center', paddingHorizontal: 40 },
  intelContainer: { marginHorizontal: 20, marginTop: 8 },
  intelHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 },
  intelSymbol: { fontSize: 20, fontWeight: '700', color: '#e0e0e0' },
  intelMeta: { fontSize: 12, color: '#888', marginTop: 2 },
  outlookBadge: { paddingHorizontal: 14, paddingVertical: 6, borderRadius: 8, alignItems: 'center' },
  outlookText: { fontSize: 14, fontWeight: '700' },
  outlookConf: { fontSize: 11, marginTop: 2 },
  summaryBox: {
    padding: 14, borderRadius: 8, marginBottom: 12,
    backgroundColor: '#6366f10d', borderWidth: 1, borderColor: '#6366f133',
  },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#e0e0e0', marginBottom: 6 },
  summaryText: { fontSize: 13, color: '#ccc', lineHeight: 20 },
  scenarioCard: {
    padding: 12, borderRadius: 8, marginBottom: 8,
    backgroundColor: '#1a1a2e', borderLeftWidth: 3,
  },
  scenarioHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  scenarioLabel: { fontSize: 14, fontWeight: '700' },
  scenarioProb: { fontSize: 12, color: '#888' },
  scenarioText: { fontSize: 13, color: '#ccc', lineHeight: 18 },
  scenarioTarget: { fontSize: 14, fontWeight: '700', marginTop: 6 },
  listSection: { marginBottom: 12, padding: 12, borderRadius: 8, backgroundColor: '#1a1a2e' },
  listItem: { fontSize: 13, color: '#bbb', lineHeight: 20, marginTop: 2 },
  metricsRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  metricBox: {
    flex: 1, padding: 10, borderRadius: 8, backgroundColor: '#1a1a2e',
    borderWidth: 1, borderColor: '#2a2a4a', alignItems: 'center',
  },
  metricBoxLabel: { fontSize: 10, color: '#888', textTransform: 'uppercase' },
  metricBoxValue: { fontSize: 16, fontWeight: '700', color: '#e0e0e0', marginTop: 4 },
  disclaimer: {
    marginTop: 12, padding: 10, borderRadius: 8,
    backgroundColor: '#f59e0b0d', borderWidth: 1, borderColor: '#f59e0b33',
  },
  disclaimerText: { fontSize: 11, color: '#f59e0b', textAlign: 'center' },
});
