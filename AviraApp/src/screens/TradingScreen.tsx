/**
 * TradingScreen — Robinhood-style mobile trading dashboard
 * Real-time prices, multi-horizon forecasts, news, top 10 picks
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  RefreshControl,
  Dimensions,
  Linking,
  FlatList,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import api from '../services/api';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

const WATCHLIST = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'META', 'JPM', 'V', 'AMD'];
const HORIZONS = [
  { key: '1h', label: '1H' },
  { key: '1d', label: '1D' },
  { key: '1w', label: '1W' },
  { key: '1m', label: '1M' },
  { key: '3m', label: '3M' },
  { key: '1y', label: '1Y' },
];

const RATING_COLORS: Record<string, string> = {
  'STRONG BUY': '#10B981',
  'BUY': '#34D399',
  'HOLD': '#FBBF24',
  'SELL': '#F87171',
  'STRONG SELL': '#EF4444',
};

export default function TradingScreen() {
  const [selectedSymbol, setSelectedSymbol] = useState('AAPL');
  const [searchText, setSearchText] = useState('');
  const [activeHorizon, setActiveHorizon] = useState('1m');
  const [activeTab, setActiveTab] = useState<'chart' | 'news' | 'picks'>('chart');
  const [forecast, setForecast] = useState<any>(null);
  const [intradayTargets, setIntradayTargets] = useState<any>(null);
  const [news, setNews] = useState<any[]>([]);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [recsLoading, setRecsLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [watchlistPrices, setWatchlistPrices] = useState<Record<string, { price: number; change: number }>>({});

  // ── Fetch data ────────────────────────────────────────────────

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [fcRes, itRes, newsRes] = await Promise.allSettled([
        api.getStockForecast(selectedSymbol),
        api.getIntradayTargets(selectedSymbol),
        api.getMarketNews(selectedSymbol),
      ]);
      if (fcRes.status === 'fulfilled' && fcRes.value?.success) setForecast(fcRes.value);
      if (itRes.status === 'fulfilled' && itRes.value?.success) setIntradayTargets(itRes.value);
      if (newsRes.status === 'fulfilled' && newsRes.value?.success) setNews(newsRes.value.articles || []);
    } catch {}
    setLoading(false);
  }, [selectedSymbol]);

  const fetchWatchlist = useCallback(async () => {
    const prices: Record<string, { price: number; change: number }> = {};
    await Promise.allSettled(
      WATCHLIST.map(async (sym) => {
        try {
          const res = await api.getHistoricalPrices(sym, '1d');
          if (res?.success && res.prices?.length > 0) {
            const p = res.prices;
            const current = p[p.length - 1].close;
            const first = p[0].open;
            prices[sym] = { price: current, change: +((current - first) / first * 100).toFixed(2) };
          }
        } catch {}
      })
    );
    setWatchlistPrices(prices);
  }, []);

  const fetchRecommendations = useCallback(async () => {
    setRecsLoading(true);
    try {
      const res = await api.getTopRecommendations(20);
      if (res?.success) setRecommendations(res.top_recommendations || []);
    } catch {}
    setRecsLoading(false);
  }, []);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await fetchAll();
    setRefreshing(false);
  }, [fetchAll]);

  useEffect(() => {
    fetchAll();
    fetchWatchlist();
  }, [selectedSymbol]);

  const handleSearch = () => {
    const sym = searchText.toUpperCase().trim();
    if (sym) {
      setSelectedSymbol(sym);
      setSearchText('');
    }
  };

  // ── Chart SVG (simplified line chart) ─────────────────────────

  const renderMiniChart = () => {
    if (!forecast?.price_history?.length) return null;
    const closes = forecast.price_history.map((p: any) => p.close);
    const horizon = forecast.forecasts?.[activeHorizon];
    const forecastPts = horizon?.forecast || [];

    const all = [...closes, ...forecastPts];
    const min = Math.min(...all) * 0.998;
    const max = Math.max(...all) * 1.002;
    const W = SCREEN_WIDTH - 48;
    const H = 180;
    const totalPts = all.length;

    const x = (i: number) => (i / (totalPts - 1)) * W;
    const y = (v: number) => H - ((v - min) / (max - min)) * H;

    const histPath = closes.map((v: number, i: number) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ');
    const fOffset = closes.length - 1;
    const fcPath = forecastPts.map((v: number, i: number) =>
      `${i === 0 ? 'M' : 'L'}${x(fOffset + i).toFixed(1)},${y(v).toFixed(1)}`
    ).join(' ');

    return (
      <View style={s.chartContainer}>
        <View style={{ width: W, height: H }}>
          {/* Using react-native-svg would be better, but keeping it simple with a colored View overlay */}
          <Text style={s.chartPlaceholder}>
            {`${closes.length} hist pts + ${forecastPts.length} forecast pts\n`}
            {`$${closes[closes.length - 1]?.toFixed(2)} → $${forecastPts[forecastPts.length - 1]?.toFixed(2) || '—'}`}
          </Text>
        </View>
      </View>
    );
  };

  const activeForecast = forecast?.forecasts?.[activeHorizon];

  return (
    <SafeAreaView style={s.root} edges={['top']}>
      {/* Search bar */}
      <View style={s.header}>
        <Icon name="chart-line" size={24} color="#818CF8" />
        <Text style={s.headerTitle}>Avira Trading</Text>
        <View style={s.searchBox}>
          <Icon name="magnify" size={18} color="#6B7280" />
          <TextInput
            style={s.searchInput}
            placeholder="Ticker..."
            placeholderTextColor="#6B7280"
            value={searchText}
            onChangeText={setSearchText}
            onSubmitEditing={handleSearch}
            autoCapitalize="characters"
            returnKeyType="search"
          />
        </View>
      </View>

      {/* Watchlist horizontal scroll */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.watchlistRow}>
        {WATCHLIST.map(sym => {
          const p = watchlistPrices[sym];
          const selected = sym === selectedSymbol;
          return (
            <TouchableOpacity
              key={sym}
              onPress={() => setSelectedSymbol(sym)}
              style={[s.watchlistChip, selected && s.watchlistChipActive]}
            >
              <Text style={[s.watchlistSymbol, selected && s.watchlistSymbolActive]}>{sym}</Text>
              {p ? (
                <Text style={[s.watchlistPrice, { color: p.change >= 0 ? '#10B981' : '#EF4444' }]}>
                  {p.change >= 0 ? '+' : ''}{p.change}%
                </Text>
              ) : (
                <Text style={s.watchlistPrice}>...</Text>
              )}
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Tabs */}
      <View style={s.tabRow}>
        {[
          { key: 'chart', label: 'Charts', icon: 'chart-areaspline' },
          { key: 'news', label: 'News', icon: 'newspaper-variant' },
          { key: 'picks', label: 'Top 20', icon: 'trophy' },
        ].map(tab => (
          <TouchableOpacity
            key={tab.key}
            onPress={() => {
              setActiveTab(tab.key as any);
              if (tab.key === 'picks' && recommendations.length === 0) fetchRecommendations();
            }}
            style={[s.tab, activeTab === tab.key && s.tabActive]}
          >
            <Icon name={tab.icon} size={16} color={activeTab === tab.key ? '#818CF8' : '#6B7280'} />
            <Text style={[s.tabLabel, activeTab === tab.key && s.tabLabelActive]}>{tab.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={s.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#818CF8" />}
      >
        {/* ── Chart Tab ── */}
        {activeTab === 'chart' && (
          <>
            {/* Price header */}
            <View style={s.priceHeader}>
              <Text style={s.symbolLarge}>{selectedSymbol}</Text>
              {forecast && (
                <>
                  <Text style={s.priceLarge}>${forecast.current_price?.toFixed(2)}</Text>
                  <View style={s.ratingBadge}>
                    <Text style={[s.ratingText, { color: RATING_COLORS[forecast.overall_rating] || '#FFF' }]}>
                      {forecast.overall_rating}
                    </Text>
                  </View>
                </>
              )}
              {loading && <ActivityIndicator size="small" color="#818CF8" style={{ marginLeft: 8 }} />}
            </View>

            {/* Horizon buttons */}
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.horizonRow}>
              {HORIZONS.map(h => (
                <TouchableOpacity
                  key={h.key}
                  onPress={() => setActiveHorizon(h.key)}
                  style={[s.horizonBtn, activeHorizon === h.key && s.horizonBtnActive]}
                >
                  <Text style={[s.horizonLabel, activeHorizon === h.key && s.horizonLabelActive]}>{h.label}</Text>
                </TouchableOpacity>
              ))}
            </ScrollView>

            {/* Mini chart */}
            {renderMiniChart()}

            {/* Forecast details */}
            {activeForecast && (
              <View style={s.forecastGrid}>
                {[
                  { label: 'Target', value: `$${activeForecast.target_price}`, color: '#818CF8' },
                  { label: 'Direction', value: activeForecast.direction, color: activeForecast.direction === 'UP' ? '#10B981' : '#EF4444' },
                  { label: 'Upside', value: `${activeForecast.upside_pct}%`, color: activeForecast.upside_pct >= 0 ? '#10B981' : '#EF4444' },
                  { label: 'Method', value: activeForecast.method?.split(' ')[0], color: '#9CA3AF' },
                ].map((item, i) => (
                  <View key={i} style={s.forecastCard}>
                    <Text style={s.forecastCardLabel}>{item.label}</Text>
                    <Text style={[s.forecastCardValue, { color: item.color }]}>{item.value}</Text>
                  </View>
                ))}
              </View>
            )}

            {/* Intraday targets */}
            {intradayTargets?.trade_targets && (
              <View style={s.targetsSection}>
                <View style={s.targetHeader}>
                  <Icon name="target" size={18} color="#FBBF24" />
                  <Text style={s.targetTitle}>Day Trade Targets</Text>
                  <View style={[s.biasBadge, {
                    backgroundColor: intradayTargets.trade_targets.bias === 'bullish' ? '#065F4620' : '#7F1D1D20',
                  }]}>
                    <Text style={[s.biasText, {
                      color: intradayTargets.trade_targets.bias === 'bullish' ? '#10B981' : '#EF4444',
                    }]}>{intradayTargets.trade_targets.bias?.toUpperCase()}</Text>
                  </View>
                </View>

                <View style={s.tradeRow}>
                  {/* Call */}
                  <View style={[s.tradeCard, { borderColor: '#10B98130' }]}>
                    <Text style={[s.tradeLabel, { color: '#10B981' }]}>CALL</Text>
                    {['entry', 'stop_loss', 'target1', 'target2'].map(k => (
                      <View key={k} style={s.tradeItem}>
                        <Text style={s.tradeItemLabel}>{k.replace('_', ' ')}</Text>
                        <Text style={s.tradeItemValue}>${intradayTargets.trade_targets.call_trade?.[k]}</Text>
                      </View>
                    ))}
                    <Text style={s.rrText}>R:R {intradayTargets.trade_targets.call_trade?.risk_reward}x</Text>
                  </View>

                  {/* Put */}
                  <View style={[s.tradeCard, { borderColor: '#EF444430' }]}>
                    <Text style={[s.tradeLabel, { color: '#EF4444' }]}>PUT</Text>
                    {['entry', 'stop_loss', 'target1', 'target2'].map(k => (
                      <View key={k} style={s.tradeItem}>
                        <Text style={s.tradeItemLabel}>{k.replace('_', ' ')}</Text>
                        <Text style={s.tradeItemValue}>${intradayTargets.trade_targets.put_trade?.[k]}</Text>
                      </View>
                    ))}
                    <Text style={s.rrText}>R:R {intradayTargets.trade_targets.put_trade?.risk_reward}x</Text>
                  </View>
                </View>

                {/* Pivots */}
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginTop: 8 }}>
                  {['r3', 'r2', 'r1', 'pivot', 's1', 's2', 's3'].map(key => {
                    const val = intradayTargets.pivot_points?.classic?.[key];
                    if (!val) return null;
                    return (
                      <View key={key} style={[s.pivotChip, {
                        backgroundColor: key === 'pivot' ? '#37415120' : key.startsWith('r') ? '#EF444420' : '#10B98120',
                      }]}>
                        <Text style={[s.pivotText, {
                          color: key === 'pivot' ? '#D1D5DB' : key.startsWith('r') ? '#F87171' : '#34D399',
                        }]}>{key.toUpperCase()} ${val}</Text>
                      </View>
                    );
                  })}
                </ScrollView>
              </View>
            )}

            {/* All horizon summary */}
            {forecast && (
              <View style={s.allHorizons}>
                <Text style={s.sectionTitle}>All Horizons</Text>
                {HORIZONS.map(h => {
                  const hf = forecast.forecasts?.[h.key];
                  if (!hf) return null;
                  return (
                    <TouchableOpacity key={h.key} onPress={() => setActiveHorizon(h.key)} style={s.horizonSummary}>
                      <Text style={s.horizonSummaryLabel}>{h.label}</Text>
                      <Text style={[s.horizonSummaryDir, { color: hf.direction === 'UP' ? '#10B981' : '#EF4444' }]}>
                        {hf.direction === 'UP' ? '▲' : '▼'} {hf.upside_pct}%
                      </Text>
                      <Text style={s.horizonSummaryTarget}>${hf.target_price}</Text>
                    </TouchableOpacity>
                  );
                })}
              </View>
            )}
          </>
        )}

        {/* ── News Tab ── */}
        {activeTab === 'news' && (
          <View style={{ paddingBottom: 40 }}>
            <Text style={s.sectionTitle}>Financial News</Text>
            {news.length === 0 && <ActivityIndicator size="large" color="#818CF8" style={{ marginTop: 40 }} />}
            {news.slice(0, 25).map((article: any, i: number) => (
              <TouchableOpacity key={i} style={s.newsCard} onPress={() => article.url && Linking.openURL(article.url)}>
                <Text style={s.newsTitle} numberOfLines={2}>{article.title}</Text>
                <Text style={s.newsSummary} numberOfLines={2}>{article.summary}</Text>
                <View style={s.newsMeta}>
                  <Text style={s.newsSource}>{article.source}</Text>
                  <Text style={s.newsDate}>{article.published?.slice(0, 16)}</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* ── Picks Tab ── */}
        {activeTab === 'picks' && (
          <View style={{ paddingBottom: 40 }}>
            <Text style={s.sectionTitle}>Top 20 Investment Picks</Text>
            <Text style={s.sectionSubtitle}>Scored across 20+ data sources</Text>
            {recsLoading && <ActivityIndicator size="large" color="#818CF8" style={{ marginTop: 40 }} />}
            {recommendations.map((rec: any, i: number) => (
              <TouchableOpacity
                key={rec.symbol}
                style={s.recCard}
                onPress={() => { setSelectedSymbol(rec.symbol); setActiveTab('chart'); }}
              >
                <View style={[s.recRank, i < 3 ? s.recRankGold : {}]}>
                  <Text style={s.recRankText}>{i + 1}</Text>
                </View>
                <View style={s.recInfo}>
                  <View style={s.recTopRow}>
                    <Text style={s.recSymbol}>{rec.symbol}</Text>
                    <View style={[s.recRatingBadge, { borderColor: RATING_COLORS[rec.rating] || '#6B7280' }]}>
                      <Text style={[s.recRatingText, { color: RATING_COLORS[rec.rating] || '#6B7280' }]}>
                        {rec.rating}
                      </Text>
                    </View>
                  </View>
                  <Text style={s.recDetails}>
                    ${rec.price?.toFixed(2) || '—'} · Target ${rec.target_price?.toFixed(2) || '—'} · {rec.sector || '—'}
                  </Text>
                  {/* Score bars */}
                  <View style={s.scoreBars}>
                    {Object.entries(rec.scores || {}).map(([k, v]) => (
                      <View key={k} style={s.scoreBarRow}>
                        <Text style={s.scoreBarLabel}>{k.slice(0, 4)}</Text>
                        <View style={s.scoreBarBg}>
                          <View style={[s.scoreBarFill, {
                            width: `${v as number}%`,
                            backgroundColor: (v as number) >= 65 ? '#10B981' : (v as number) >= 45 ? '#FBBF24' : '#EF4444',
                          }]} />
                        </View>
                      </View>
                    ))}
                  </View>
                </View>
                <View style={s.recScore}>
                  <Text style={s.recScoreNum}>{rec.composite_score}</Text>
                  <Text style={s.recScoreLabel}>/100</Text>
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

// ── Styles ─────────────────────────────────────────────────────

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#0F172A' },
  header: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, gap: 8 },
  headerTitle: { fontSize: 18, fontWeight: '800', color: '#E2E8F0', flex: 1 },
  searchBox: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 10, height: 34, gap: 4 },
  searchInput: { color: '#F1F5F9', fontSize: 14, width: 80, padding: 0 },
  watchlistRow: { paddingHorizontal: 12, paddingVertical: 6 },
  watchlistChip: { backgroundColor: '#1E293B', borderRadius: 10, paddingHorizontal: 14, paddingVertical: 8, marginRight: 8, alignItems: 'center', borderWidth: 1, borderColor: '#334155' },
  watchlistChipActive: { borderColor: '#818CF8', backgroundColor: '#818CF810' },
  watchlistSymbol: { fontSize: 12, fontWeight: '700', color: '#E2E8F0' },
  watchlistSymbolActive: { color: '#818CF8' },
  watchlistPrice: { fontSize: 10, fontWeight: '600', color: '#6B7280', marginTop: 2 },
  tabRow: { flexDirection: 'row', paddingHorizontal: 16, paddingBottom: 8, gap: 4 },
  tab: { flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: 8, borderRadius: 8, gap: 4, backgroundColor: '#1E293B' },
  tabActive: { backgroundColor: '#818CF820' },
  tabLabel: { fontSize: 12, fontWeight: '600', color: '#6B7280' },
  tabLabelActive: { color: '#818CF8' },
  content: { flex: 1, paddingHorizontal: 16 },
  priceHeader: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 8, flexWrap: 'wrap' },
  symbolLarge: { fontSize: 24, fontWeight: '900', color: '#F1F5F9' },
  priceLarge: { fontSize: 28, fontWeight: '800', color: '#F1F5F9' },
  ratingBadge: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 10, paddingVertical: 4 },
  ratingText: { fontSize: 12, fontWeight: '800' },
  horizonRow: { marginTop: 12, marginBottom: 8 },
  horizonBtn: { backgroundColor: '#1E293B', borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8, marginRight: 8 },
  horizonBtnActive: { backgroundColor: '#4F46E5' },
  horizonLabel: { fontSize: 13, fontWeight: '700', color: '#6B7280' },
  horizonLabelActive: { color: '#FFF' },
  chartContainer: { backgroundColor: '#1E293B', borderRadius: 12, padding: 16, marginVertical: 8, minHeight: 180, justifyContent: 'center', alignItems: 'center' },
  chartPlaceholder: { color: '#94A3B8', textAlign: 'center', fontSize: 14, lineHeight: 22 },
  forecastGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginVertical: 8 },
  forecastCard: { flex: 1, minWidth: '22%', backgroundColor: '#1E293B', borderRadius: 10, padding: 10, alignItems: 'center' },
  forecastCardLabel: { fontSize: 10, color: '#6B7280', marginBottom: 4 },
  forecastCardValue: { fontSize: 16, fontWeight: '800' },
  targetsSection: { backgroundColor: '#1E293B', borderRadius: 12, padding: 12, marginVertical: 8 },
  targetHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 10 },
  targetTitle: { fontSize: 14, fontWeight: '700', color: '#F1F5F9', flex: 1 },
  biasBadge: { borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  biasText: { fontSize: 10, fontWeight: '800' },
  tradeRow: { flexDirection: 'row', gap: 8 },
  tradeCard: { flex: 1, backgroundColor: '#0F172A', borderRadius: 10, padding: 10, borderWidth: 1 },
  tradeLabel: { fontSize: 13, fontWeight: '800', marginBottom: 6, textAlign: 'center' },
  tradeItem: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 3 },
  tradeItemLabel: { fontSize: 11, color: '#6B7280', textTransform: 'capitalize' },
  tradeItemValue: { fontSize: 11, fontWeight: '700', color: '#E2E8F0' },
  rrText: { fontSize: 10, color: '#818CF8', textAlign: 'center', marginTop: 6, fontWeight: '700' },
  pivotChip: { borderRadius: 6, paddingHorizontal: 10, paddingVertical: 4, marginRight: 6 },
  pivotText: { fontSize: 10, fontWeight: '700', fontFamily: 'Menlo' },
  allHorizons: { marginTop: 12, paddingBottom: 20 },
  sectionTitle: { fontSize: 16, fontWeight: '800', color: '#F1F5F9', marginBottom: 8 },
  sectionSubtitle: { fontSize: 12, color: '#6B7280', marginBottom: 12, marginTop: -4 },
  horizonSummary: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1E293B', borderRadius: 10, padding: 12, marginBottom: 6 },
  horizonSummaryLabel: { fontSize: 13, fontWeight: '600', color: '#94A3B8', width: 70 },
  horizonSummaryDir: { fontSize: 15, fontWeight: '800', flex: 1 },
  horizonSummaryTarget: { fontSize: 13, fontWeight: '600', color: '#818CF8' },
  newsCard: { backgroundColor: '#1E293B', borderRadius: 12, padding: 14, marginBottom: 8 },
  newsTitle: { fontSize: 14, fontWeight: '700', color: '#F1F5F9', lineHeight: 20 },
  newsSummary: { fontSize: 12, color: '#94A3B8', marginTop: 4, lineHeight: 18 },
  newsMeta: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 },
  newsSource: { fontSize: 10, color: '#818CF8', fontWeight: '600' },
  newsDate: { fontSize: 10, color: '#4B5563' },
  recCard: { flexDirection: 'row', alignItems: 'center', backgroundColor: '#1E293B', borderRadius: 12, padding: 12, marginBottom: 8, gap: 10 },
  recRank: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#334155', alignItems: 'center', justifyContent: 'center' },
  recRankGold: { backgroundColor: '#78350F' },
  recRankText: { fontSize: 16, fontWeight: '900', color: '#F1F5F9' },
  recInfo: { flex: 1 },
  recTopRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  recSymbol: { fontSize: 16, fontWeight: '800', color: '#F1F5F9' },
  recRatingBadge: { borderWidth: 1, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 2 },
  recRatingText: { fontSize: 10, fontWeight: '800' },
  recDetails: { fontSize: 11, color: '#6B7280', marginTop: 2 },
  scoreBars: { flexDirection: 'row', gap: 4, marginTop: 6 },
  scoreBarRow: { flex: 1, alignItems: 'center' },
  scoreBarLabel: { fontSize: 8, color: '#4B5563', marginBottom: 2 },
  scoreBarBg: { width: '100%', height: 3, backgroundColor: '#334155', borderRadius: 2, overflow: 'hidden' },
  scoreBarFill: { height: 3, borderRadius: 2 },
  recScore: { alignItems: 'center' },
  recScoreNum: { fontSize: 22, fontWeight: '900', color: '#818CF8' },
  recScoreLabel: { fontSize: 9, color: '#6B7280' },
});
