/**
 * Assistant Screen - Main chat interface for shopping, travel, and general queries
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  SafeAreaView,
} from 'react-native';
import Icon from 'react-native-vector-icons/MaterialCommunityIcons';
import api, { AssistantResponse, Session } from '../services/api';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  type?: string;
  results?: any[];
  timestamp: Date;
}

const AssistantScreen: React.FC = () => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [showSessions, setShowSessions] = useState(false);
  const [connected, setConnected] = useState<boolean | null>(null);
  const flatListRef = useRef<FlatList>(null);

  useEffect(() => {
    checkConnection();
    loadSessions();
  }, []);

  const checkConnection = async () => {
    const result = await api.testConnection();
    setConnected(result.success);
  };

  const loadSessions = async () => {
    try {
      const data = await api.getSessions();
      setSessions(data);
    } catch (error) {
      console.error('Failed to load sessions:', error);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage: Message = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const response: AssistantResponse = await api.chat(input);

      const assistantMessage: Message = {
        id: `msg_${Date.now()}_response`,
        role: 'assistant',
        content: response.response || 'No response',
        type: response.type,
        results: response.results,
        timestamp: new Date(),
      };

      setMessages(prev => [...prev, assistantMessage]);
      loadSessions();
    } catch (error) {
      setMessages(prev => [...prev, {
        id: `msg_${Date.now()}_error`,
        role: 'assistant',
        content: 'Connection error. Please check your network.',
        timestamp: new Date(),
      }]);
    } finally {
      setLoading(false);
    }
  };

  const startNewSession = async () => {
    await api.newSession();
    setMessages([]);
    setShowSessions(false);
  };

  const loadSession = async (sessionId: string) => {
    try {
      const data = await api.loadSession(sessionId);
      const loadedMessages: Message[] = data.context.map((msg, idx) => ({
        id: `${sessionId}_${idx}`,
        role: msg.role as 'user' | 'assistant',
        content: msg.masked_content || msg.content,
        timestamp: new Date(msg.timestamp),
      }));
      setMessages(loadedMessages);
      setShowSessions(false);
    } catch (error) {
      console.error('Failed to load session:', error);
    }
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.role === 'user';

    return (
      <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.assistantBubble]}>
        {!isUser && item.type && item.type !== 'chat_response' && (
          <View style={styles.typeIndicator}>
            <Icon 
              name={item.type === 'shopping_result' ? 'cart' : 'airplane'} 
              size={14} 
              color={item.type === 'shopping_result' ? '#3B82F6' : '#8B5CF6'} 
            />
            <Text style={styles.typeText}>
              {item.type === 'shopping_result' ? 'Shopping' : 'Travel'}
            </Text>
          </View>
        )}
        <Text style={[styles.messageText, isUser && styles.userMessageText]}>
          {item.content}
        </Text>
        {item.results && item.results.length > 0 && (
          <View style={styles.resultsContainer}>
            {item.results.slice(0, 3).map((result, idx) => (
              <View key={idx} style={styles.resultCard}>
                <Text style={styles.resultTitle} numberOfLines={1}>
                  {result.title || result.airlines?.join(', ')}
                </Text>
                <Text style={styles.resultPrice}>
                  ${result.final_price?.toFixed(2) || result.price?.toFixed(2)}
                </Text>
                {result.why && (
                  <Text style={styles.resultWhy}>{result.why}</Text>
                )}
              </View>
            ))}
          </View>
        )}
        <Text style={styles.timestamp}>
          {item.timestamp.toLocaleTimeString()}
        </Text>
      </View>
    );
  };

  const renderQuickAction = (icon: string, label: string, query: string, color: string) => (
    <TouchableOpacity 
      style={[styles.quickAction, { borderColor: color }]}
      onPress={() => setInput(query)}
    >
      <Icon name={icon} size={24} color={color} />
      <Text style={styles.quickActionLabel}>{label}</Text>
    </TouchableOpacity>
  );

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setShowSessions(!showSessions)}>
          <Icon name="history" size={24} color="#374151" />
        </TouchableOpacity>
        <View style={styles.headerTitle}>
          <Text style={styles.title}>Avira Assistant</Text>
          <View style={styles.statusContainer}>
            <View style={[styles.statusDot, connected ? styles.connected : styles.disconnected]} />
            <Text style={styles.statusText}>
              {connected === null ? 'Checking...' : connected ? 'Connected' : 'Offline'}
            </Text>
          </View>
        </View>
        <TouchableOpacity onPress={startNewSession}>
          <Icon name="plus" size={24} color="#3B82F6" />
        </TouchableOpacity>
      </View>

      {/* Sessions Panel */}
      {showSessions && (
        <View style={styles.sessionsPanel}>
          <Text style={styles.sessionsPanelTitle}>Chat History</Text>
          {sessions.map(session => (
            <TouchableOpacity
              key={session.session_id}
              style={styles.sessionItem}
              onPress={() => loadSession(session.session_id)}
            >
              <Text style={styles.sessionPreview} numberOfLines={1}>
                {session.preview || 'New conversation'}
              </Text>
              <Text style={styles.sessionMeta}>{session.message_count} messages</Text>
            </TouchableOpacity>
          ))}
        </View>
      )}

      {/* Messages */}
      <KeyboardAvoidingView 
        style={styles.chatContainer}
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        keyboardVerticalOffset={90}
      >
        {messages.length === 0 ? (
          <View style={styles.emptyState}>
            <Icon name="robot-happy" size={64} color="#3B82F6" />
            <Text style={styles.emptyTitle}>How can I help you?</Text>
            <Text style={styles.emptySubtitle}>
              Shopping, flights, health, finance & more
            </Text>
            <View style={styles.quickActions}>
              {renderQuickAction('cart', 'Shop', 'Find iPhone 16 Pro Max 256GB', '#3B82F6')}
              {renderQuickAction('airplane', 'Travel', 'Flights from NYC to LA Dec 25', '#8B5CF6')}
              {renderQuickAction('currency-usd', 'Finance', 'What is my top spending?', '#10B981')}
              {renderQuickAction('heart-pulse', 'Health', 'How is my health report?', '#EF4444')}
            </View>
          </View>
        ) : (
          <FlatList
            ref={flatListRef}
            data={messages}
            renderItem={renderMessage}
            keyExtractor={item => item.id}
            contentContainerStyle={styles.messagesList}
            onContentSizeChange={() => flatListRef.current?.scrollToEnd()}
          />
        )}

        {loading && (
          <View style={styles.loadingContainer}>
            <ActivityIndicator size="small" color="#3B82F6" />
          </View>
        )}

        {/* Input */}
        <View style={styles.inputContainer}>
          <TextInput
            style={styles.input}
            value={input}
            onChangeText={setInput}
            placeholder="Ask anything..."
            placeholderTextColor="#9CA3AF"
            multiline
            maxLength={500}
            onSubmitEditing={sendMessage}
          />
          <TouchableOpacity 
            style={[styles.sendButton, (!input.trim() || loading) && styles.sendButtonDisabled]}
            onPress={sendMessage}
            disabled={!input.trim() || loading}
          >
            <Icon name="send" size={20} color="#FFF" />
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFF',
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
  },
  headerTitle: {
    alignItems: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
  },
  statusContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 4,
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
  sessionsPanel: {
    backgroundColor: '#FFF',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: '#E5E7EB',
    maxHeight: 200,
  },
  sessionsPanelTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
    marginBottom: 8,
  },
  sessionItem: {
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  sessionPreview: {
    fontSize: 14,
    color: '#111827',
  },
  sessionMeta: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 2,
  },
  chatContainer: {
    flex: 1,
  },
  emptyState: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: '#111827',
    marginTop: 16,
  },
  emptySubtitle: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 4,
    marginBottom: 24,
  },
  quickActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 12,
  },
  quickAction: {
    width: '45%',
    padding: 16,
    backgroundColor: '#FFF',
    borderRadius: 12,
    borderWidth: 1,
    alignItems: 'center',
  },
  quickActionLabel: {
    fontSize: 14,
    fontWeight: '500',
    color: '#374151',
    marginTop: 8,
  },
  messagesList: {
    padding: 16,
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
    marginBottom: 12,
  },
  userBubble: {
    backgroundColor: '#3B82F6',
    alignSelf: 'flex-end',
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: '#FFF',
    alignSelf: 'flex-start',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  typeIndicator: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  typeText: {
    fontSize: 12,
    fontWeight: '500',
    marginLeft: 4,
    color: '#6B7280',
  },
  messageText: {
    fontSize: 15,
    color: '#111827',
    lineHeight: 22,
  },
  userMessageText: {
    color: '#FFF',
  },
  timestamp: {
    fontSize: 10,
    color: '#9CA3AF',
    marginTop: 4,
    alignSelf: 'flex-end',
  },
  resultsContainer: {
    marginTop: 12,
  },
  resultCard: {
    backgroundColor: '#F9FAFB',
    padding: 10,
    borderRadius: 8,
    marginBottom: 8,
  },
  resultTitle: {
    fontSize: 13,
    fontWeight: '500',
    color: '#111827',
  },
  resultPrice: {
    fontSize: 16,
    fontWeight: '700',
    color: '#10B981',
    marginTop: 4,
  },
  resultWhy: {
    fontSize: 11,
    color: '#3B82F6',
    fontStyle: 'italic',
    marginTop: 4,
  },
  loadingContainer: {
    padding: 12,
    alignItems: 'center',
  },
  inputContainer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    backgroundColor: '#FFF',
    borderTopWidth: 1,
    borderTopColor: '#E5E7EB',
  },
  input: {
    flex: 1,
    backgroundColor: '#F3F4F6',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    fontSize: 15,
    maxHeight: 100,
    color: '#111827',
  },
  sendButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#3B82F6',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  sendButtonDisabled: {
    backgroundColor: '#9CA3AF',
  },
});

export default AssistantScreen;
