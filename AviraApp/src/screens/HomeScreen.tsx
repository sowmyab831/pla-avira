/**
 * Home Screen - Dashboard with quick access to all features
 */
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  SafeAreaView,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import api from '../services/api';

interface DashboardData {
  connected: boolean;
  finance?: { balance: number; expenses: number };
  health?: { alerts: number };
  calendar?: { upcoming: number };
}

const HomeScreen: React.FC<{ navigation: any }> = ({ navigation }) => {
  const [data, setData] = useState<DashboardData>({ connected: false });
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    setRefreshing(true);
    try {
      const connectionResult = await api.testConnection();
      
      let finance, health, calendar;
      if (connectionResult.success) {
        try {
          const [financeData, healthData, calendarData] = await Promise.all([
            api.getFinanceSummary().catch(() => null),
            api.getHealthReport().catch(() => null),
            api.getUpcomingEvents(7).catch(() => []),
          ]);
          
          finance = financeData ? {
            balance: financeData.balance || 0,
            expenses: financeData.total_expenses || 0,
          } : undefined;
          
          health = healthData ? {
            alerts: healthData.alerts?.length || 0,
          } : undefined;
          
          calendar = {
            upcoming: Array.isArray(calendarData) ? calendarData.length : 0,
          };
        } catch (e) {
          console.log('Dashboard data fetch error:', e);
        }
      }

      setData({
        connected: connectionResult.success,
        finance,
        health,
        calendar,
      });
    } catch (error) {
      setData({ connected: false });
    } finally {
      setRefreshing(false);
    }
  };

  const QuickCard = ({ 
    icon, 
    title, 
    value, 
    subtitle, 
    color, 
    onPress 
  }: {
    icon: string;
    title: string;
    value: string;
    subtitle: string;
    color: string;
    onPress: () => void;
  }) => (
    <TouchableOpacity style={styles.quickCard} onPress={onPress}>
      <View style={[styles.iconContainer, { backgroundColor: `${color}20` }]}>
        <Icon name={icon} size={24} color={color} />
      </View>
      <Text style={styles.cardTitle}>{title}</Text>
      <Text style={styles.cardValue}>{value}</Text>
      <Text style={styles.cardSubtitle}>{subtitle}</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={loadDashboard} />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.greeting}>Welcome back</Text>
            <Text style={styles.title}>Avira</Text>
          </View>
          <View style={styles.connectionStatus}>
            <View style={[styles.statusDot, data.connected ? styles.connected : styles.disconnected]} />
            <Text style={styles.statusText}>
              {data.connected ? 'Connected' : 'Offline'}
            </Text>
          </View>
        </View>

        {/* Assistant Card */}
        <TouchableOpacity 
          style={styles.assistantCard}
          onPress={() => navigation.navigate('Assistant')}
        >
          <View style={styles.assistantContent}>
            <Icon name="robot-happy" size={40} color="#3B82F6" />
            <View style={styles.assistantText}>
              <Text style={styles.assistantTitle}>AI Assistant</Text>
              <Text style={styles.assistantSubtitle}>
                Shopping, travel, health & more
              </Text>
            </View>
          </View>
          <Icon name="chevron-right" size={24} color="#9CA3AF" />
        </TouchableOpacity>

        {/* Quick Stats */}
        <Text style={styles.sectionTitle}>Quick Overview</Text>
        <View style={styles.quickCards}>
          <QuickCard
            icon="currency-usd"
            title="Finance"
            value={data.finance ? `$${data.finance.balance.toLocaleString()}` : '--'}
            subtitle={data.finance ? `$${data.finance.expenses.toLocaleString()} spent` : 'Tap to view'}
            color="#10B981"
            onPress={() => navigation.navigate('Finance')}
          />
          <QuickCard
            icon="heart-pulse"
            title="Health"
            value={data.health ? `${data.health.alerts}` : '--'}
            subtitle={data.health?.alerts ? 'alerts' : 'No alerts'}
            color="#EF4444"
            onPress={() => navigation.navigate('Health')}
          />
          <QuickCard
            icon="calendar"
            title="Calendar"
            value={data.calendar ? `${data.calendar.upcoming}` : '--'}
            subtitle="upcoming events"
            color="#8B5CF6"
            onPress={() => navigation.navigate('Calendar')}
          />
          <QuickCard
            icon="shield-check"
            title="Privacy"
            value="Protected"
            subtitle="Data masked"
            color="#3B82F6"
            onPress={() => navigation.navigate('Settings')}
          />
        </View>

        {/* Quick Actions */}
        <Text style={styles.sectionTitle}>Quick Actions</Text>
        <View style={styles.actionButtons}>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => navigation.navigate('Assistant')}
          >
            <Icon name="cart" size={20} color="#3B82F6" />
            <Text style={styles.actionText}>Shop</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => navigation.navigate('Assistant')}
          >
            <Icon name="airplane" size={20} color="#8B5CF6" />
            <Text style={styles.actionText}>Travel</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => navigation.navigate('Finance')}
          >
            <Icon name="receipt" size={20} color="#10B981" />
            <Text style={styles.actionText}>Bills</Text>
          </TouchableOpacity>
          <TouchableOpacity 
            style={styles.actionButton}
            onPress={() => navigation.navigate('Health')}
          >
            <Icon name="file-document" size={20} color="#EF4444" />
            <Text style={styles.actionText}>Labs</Text>
          </TouchableOpacity>
        </View>

        {/* Server Info */}
        <View style={styles.serverInfo}>
          <Text style={styles.serverTitle}>Server</Text>
          <Text style={styles.serverUrl}>aviraa.duckdns.org:30000</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  scrollContent: {
    padding: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
  },
  greeting: {
    fontSize: 14,
    color: '#6B7280',
  },
  title: {
    fontSize: 28,
    fontWeight: '700',
    color: '#111827',
  },
  connectionStatus: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FFF',
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  connected: {
    backgroundColor: '#10B981',
  },
  disconnected: {
    backgroundColor: '#EF4444',
  },
  statusText: {
    fontSize: 12,
    color: '#6B7280',
  },
  assistantCard: {
    backgroundColor: '#FFF',
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 24,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  assistantContent: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  assistantText: {
    marginLeft: 16,
  },
  assistantTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
  },
  assistantSubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 12,
  },
  quickCards: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  quickCard: {
    width: '48%',
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 16,
    marginBottom: 12,
  },
  iconContainer: {
    width: 40,
    height: 40,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  cardTitle: {
    fontSize: 12,
    color: '#6B7280',
  },
  cardValue: {
    fontSize: 20,
    fontWeight: '700',
    color: '#111827',
    marginTop: 4,
  },
  cardSubtitle: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  actionButtons: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 24,
  },
  actionButton: {
    flex: 1,
    backgroundColor: '#FFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    marginHorizontal: 4,
  },
  actionText: {
    fontSize: 12,
    color: '#374151',
    marginTop: 8,
  },
  serverInfo: {
    backgroundColor: '#F3F4F6',
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
  },
  serverTitle: {
    fontSize: 12,
    color: '#6B7280',
  },
  serverUrl: {
    fontSize: 14,
    color: '#374151',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
});

export default HomeScreen;
