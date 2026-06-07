import React, { useState, useRef, useEffect } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView,
  Platform, Keyboard,
} from 'react-native';
import { apiJSON } from '../utils/api';
import { colors } from '../utils/theme';

let sessionId = `mob_${Date.now()}`;

export default function ChatScreen() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages]);

  async function send() {
    const text = input.trim();
    if (!text || loading) return;
    setInput('');
    Keyboard.dismiss();

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await apiJSON('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const aiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.response,
        agents: data.agents_used || [],
      };
      setMessages(prev => [...prev, aiMsg]);
    } catch (e) {
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        role: 'error',
        content: e.message,
      }]);
    } finally {
      setLoading(false);
    }
  }

  function renderMsg({ item }) {
    const isUser = item.role === 'user';
    const isError = item.role === 'error';
    return (
      <View style={[s.msgRow, isUser && s.msgRowUser]}>
        {!isUser && (
          <View style={s.avatar}>
            <Text style={s.avatarText}>👁</Text>
          </View>
        )}
        <View style={[
          s.bubble,
          isUser ? s.bubbleUser : s.bubbleAI,
          isError && s.bubbleError,
        ]}>
          {item.agents?.length > 0 && (
            <View style={s.agentBadges}>
              {item.agents.map(a => (
                <Text key={a} style={s.agentBadge}>{a.toUpperCase()}</Text>
              ))}
            </View>
          )}
          <Text style={[s.msgText, isUser && s.msgTextUser]}>
            {item.content}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={s.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      keyboardVerticalOffset={90}
    >
      {messages.length === 0 ? (
        <View style={s.welcome}>
          <Text style={s.welcomeEye}>👁️</Text>
          <Text style={s.welcomeTitle}>Bonjour, Mr Vitch</Text>
          <Text style={s.welcomeSub}>Expert OSEE · SOC · Red Team · Compagnon IA</Text>
          <View style={s.suggestions}>
            {[
              'Fais un diagnostic système',
              'Explique le Kerberoasting',
              'Techniques de privesc Linux',
            ].map(q => (
              <TouchableOpacity key={q} style={s.suggestion} onPress={() => setInput(q)}>
                <Text style={s.suggestionText}>{q}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      ) : (
        <FlatList
          ref={listRef}
          data={messages}
          keyExtractor={m => String(m.id)}
          renderItem={renderMsg}
          contentContainerStyle={s.list}
          onContentSizeChange={() => listRef.current?.scrollToEnd({ animated: true })}
        />
      )}

      {loading && (
        <View style={s.thinkingRow}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={s.thinkingText}> réflexion...</Text>
        </View>
      )}

      <View style={s.inputRow}>
        <TextInput
          style={s.input}
          value={input}
          onChangeText={setInput}
          placeholder="Message ou commande…"
          placeholderTextColor={colors.textDim}
          multiline
          maxLength={2000}
          onSubmitEditing={send}
          blurOnSubmit={false}
        />
        <TouchableOpacity
          style={[s.sendBtn, (!input.trim() || loading) && s.sendBtnOff]}
          onPress={send}
          disabled={!input.trim() || loading}
          activeOpacity={0.7}
        >
          <Text style={s.sendIcon}>➤</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  list: { padding: 12, paddingBottom: 8 },
  welcome: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  welcomeEye: { fontSize: 56, marginBottom: 12 },
  welcomeTitle: { fontSize: 22, fontWeight: '700', color: colors.accent, marginBottom: 6 },
  welcomeSub: { fontSize: 12, color: colors.textMuted, textAlign: 'center', marginBottom: 32 },
  suggestions: { width: '100%', gap: 8 },
  suggestion: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 10,
    padding: 14,
  },
  suggestionText: { color: colors.text, fontSize: 13 },
  msgRow: { flexDirection: 'row', marginBottom: 12, alignItems: 'flex-start' },
  msgRowUser: { justifyContent: 'flex-end' },
  avatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.bgCard,
    borderWidth: 1, borderColor: colors.accent,
    justifyContent: 'center', alignItems: 'center',
    marginRight: 8,
  },
  avatarText: { fontSize: 14 },
  bubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 14,
    borderTopLeftRadius: 4,
  },
  bubbleUser: {
    backgroundColor: colors.accentGlow,
    borderTopLeftRadius: 14,
    borderTopRightRadius: 4,
  },
  bubbleAI: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
  },
  bubbleError: {
    backgroundColor: '#3a1010',
    borderColor: colors.red,
  },
  agentBadges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 },
  agentBadge: {
    fontSize: 9, color: colors.accent,
    backgroundColor: '#001a2e',
    paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 4, borderWidth: 1, borderColor: colors.accent,
    fontWeight: '700', letterSpacing: 1,
  },
  msgText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  msgTextUser: { color: colors.white },
  thinkingRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingHorizontal: 16, paddingBottom: 8,
  },
  thinkingText: { color: colors.textMuted, fontSize: 12 },
  inputRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    padding: 12,
    paddingBottom: Platform.OS === 'ios' ? 24 : 12,
    backgroundColor: colors.bgCard,
    borderTopWidth: 1,
    borderTopColor: colors.border,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: colors.text,
    fontSize: 14,
    maxHeight: 100,
  },
  sendBtn: {
    width: 44, height: 44,
    backgroundColor: colors.accent,
    borderRadius: 22,
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendBtnOff: { backgroundColor: colors.textDim },
  sendIcon: { color: colors.bg, fontSize: 16, fontWeight: '700' },
});
