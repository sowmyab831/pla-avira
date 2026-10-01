/**
 * Earnings Watchlist Screen
 * Mobile view to manage a personal earnings watchlist (persisted locally)
 */
import React, { useState, useEffect } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, FlatList, Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

const WATCHLIST_KEY = 'avira_earnings_watchlist';

export default function WatchlistScreen() {
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [newSymbol, setNewSymbol] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadWatchlist();
  }, []);

  const loadWatchlist = async () => {
    try {
      const stored = await AsyncStorage.getItem(WATCHLIST_KEY);
      setWatchlist(stored ? JSON.parse(stored) : []);
    } catch {}
    setLoading(false);
  };

  const addSymbol = () => {
    const sym = newSymbol.toUpperCase().trim();
    if (!sym) return;
    if (!/^[A-Z]{1,5}$/.test(sym)) {
      Alert.alert('Invalid symbol', 'Enter a valid stock ticker (1-5 letters).');
      return;
    }
    if (watchlist.includes(sym)) {
      Alert.alert('Already added', `${sym} is already in your watchlist.`);
      return;
    }
    const updated = [...watchlist, sym];
    setWatchlist(updated);
    AsyncStorage.setItem(WATCHLIST_KEY, JSON.stringify(updated));
    setNewSymbol('');
  };

  const removeSymbol = (sym: string) => {
    const updated = watchlist.filter(s => s !== sym);
    setWatchlist(updated);
    AsyncStorage.setItem(WATCHLIST_KEY, JSON.stringify(updated));
  };

  const renderItem = ({ item }: { item: string }) => (
    <View style={s.item}>
      <Text style={s.symbol}>{item}</Text>
      <TouchableOpacity onPress={() => removeSymbol(item)}>
        <Icon name="close-circle" size={24} color="#ef4444" />
      </TouchableOpacity>
    </View>
  );

  if (loading) {
    return (
      <SafeAreaView style={s.container}>
        <View style={s.center}>
          <Text style={s.loadingText}>Loading watchlist...</Text>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={s.container}>
      <View style={s.header}>
        <Text style={s.title}>Earnings Watchlist</Text>
        <Text style={s.subtitle}>Your personal symbols for digest sharing</Text>
      </View>

      {/* Add symbol */}
      <View style={s.addRow}>
        <TextInput
          style={s.input}
          value={newSymbol}
          onChangeText={setNewSymbol}
          placeholder="Add symbol (e.g. NVDA)"
          placeholderTextColor="#888"
          autoCapitalize="characters"
          maxLength={5}
          returnKeyType="done"
          onSubmitEditing={addSymbol}
        />
        <TouchableOpacity style={s.addBtn} onPress={addSymbol}>
          <Icon name="plus" size={20} color="#fff" />
        </TouchableOpacity>
      </View>

      {/* List */}
      {watchlist.length === 0 ? (
        <View style={s.center}>
          <Icon name="playlist-plus" size={48} color="#444" />
          <Text style={s.emptyText}>No symbols yet</Text>
          <Text style={s.emptySubtext}>Add tickers to track their earnings</Text>
        </View>
      ) : (
        <FlatList
          data={watchlist}
          keyExtractor={item => item}
          renderItem={renderItem}
          contentContainerStyle={s.list}
        />
      )}

      {/* Info */}
      <View style={s.infoBox}>
        <Text style={s.infoText}>
          Use the "Share ▸ WhatsApp" button on the Earnings screen to generate a digest for your watchlist.
        </Text>
      </View>
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0f0f23' },
  header: { paddingHorizontal: 20, paddingTop: 12, paddingBottom: 8 },
  title: { fontSize: 24, fontWeight: '700', color: '#e0e0e0' },
  subtitle: { fontSize: 13, color: '#888', marginTop: 2 },
  addRow: { flexDirection: 'row', paddingHorizontal: 20, paddingVertical: 12, gap: 8 },
  input: {
    flex: 1, padding: 12, borderRadius: 8, backgroundColor: '#1a1a2e',
    borderWidth: 1, borderColor: '#2a2a4a', color: '#e0e0e0', fontSize: 16,
    textTransform: 'uppercase', fontWeight: '600',
  },
  addBtn: {
    width: 48, height: 48, borderRadius: 8, backgroundColor: '#6366f1',
    alignItems: 'center', justifyContent: 'center',
  },
  list: { paddingHorizontal: 20, paddingTop: 8 },
  item: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 14, borderRadius: 8, backgroundColor: '#1a1a2e',
    marginBottom: 8, borderWidth: 1, borderColor: '#2a2a4a',
  },
  symbol: { fontSize: 18, fontWeight: '700', color: '#e0e0e0' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 40 },
  loadingText: { fontSize: 16, color: '#888' },
  emptyText: { fontSize: 18, fontWeight: '600', color: '#888', marginTop: 12 },
  emptySubtext: { fontSize: 14, color: '#666', marginTop: 4 },
  infoBox: {
    margin: 20, padding: 12, borderRadius: 8,
    backgroundColor: '#6366f108', borderWidth: 1, borderColor: '#6366f122',
  },
  infoText: { fontSize: 13, color: '#888', lineHeight: 18 },
});
