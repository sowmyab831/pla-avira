/**
 * Avira Mobile App - Main Entry Point
 * Cross-platform React Native app for iOS and Android
 */
import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';

// Screens
import SimpleHomeScreen from './src/screens/SimpleHomeScreen';
import AssistantScreen from './src/screens/AssistantScreen';

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

// Placeholder screens - to be implemented
const FinanceScreen = () => <PlaceholderScreen title="Finance" icon="currency-usd" />;
const HealthScreen = () => <PlaceholderScreen title="Health" icon="heart-pulse" />;
const CalendarScreen = () => <PlaceholderScreen title="Calendar" icon="calendar" />;
const SettingsScreen = () => <PlaceholderScreen title="Settings" icon="cog" />;

import { View, Text, StyleSheet } from 'react-native';

const PlaceholderScreen = ({ title, icon }: { title: string; icon: string }) => (
  <View style={placeholderStyles.container}>
    <Icon name={icon} size={64} color="#9CA3AF" />
    <Text style={placeholderStyles.title}>{title}</Text>
    <Text style={placeholderStyles.subtitle}>Coming soon</Text>
  </View>
);

const placeholderStyles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#F9FAFB',
  },
  title: {
    fontSize: 24,
    fontWeight: '600',
    color: '#374151',
    marginTop: 16,
  },
  subtitle: {
    fontSize: 14,
    color: '#9CA3AF',
    marginTop: 4,
  },
});

function MainTabs() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ focused, color, size }) => {
          let iconName: string;
          switch (route.name) {
            case 'Home':
              iconName = 'home';
              break;
            case 'Assistant':
              iconName = 'robot';
              break;
            case 'Finance':
              iconName = 'currency-usd';
              break;
            case 'Health':
              iconName = 'heart-pulse';
              break;
            case 'Calendar':
              iconName = 'calendar';
              break;
            default:
              iconName = 'circle';
          }
          return <Icon name={iconName} size={size} color={color} />;
        },
        tabBarActiveTintColor: '#3B82F6',
        tabBarInactiveTintColor: '#9CA3AF',
        tabBarStyle: {
          backgroundColor: '#FFF',
          borderTopColor: '#E5E7EB',
          paddingBottom: 5,
          height: 60,
        },
        tabBarLabelStyle: {
          fontSize: 11,
          fontWeight: '500',
        },
        headerShown: false,
      })}
    >
      <Tab.Screen name="Home" component={SimpleHomeScreen} />
      <Tab.Screen name="Assistant" component={AssistantScreen} />
      <Tab.Screen name="Finance" component={FinanceScreen} />
      <Tab.Screen name="Health" component={HealthScreen} />
      <Tab.Screen name="Calendar" component={CalendarScreen} />
    </Tab.Navigator>
  );
}

export default function App() {
  return (
    <SafeAreaProvider>
      <NavigationContainer>
        <Stack.Navigator screenOptions={{ headerShown: false }}>
          <Stack.Screen name="Main" component={MainTabs} />
          <Stack.Screen 
            name="Settings" 
            component={SettingsScreen}
            options={{ 
              headerShown: true,
              title: 'Settings',
            }}
          />
        </Stack.Navigator>
      </NavigationContainer>
    </SafeAreaProvider>
  );
}
