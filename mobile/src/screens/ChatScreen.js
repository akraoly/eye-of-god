import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, FlatList,
  StyleSheet, ActivityIndicator, KeyboardAvoidingView,
  Platform, Keyboard, Alert,
} from 'react-native';
import { apiJSON } from '../utils/api';
import { colors } from '../utils/theme';
import {
  speak, stopSpeaking, startRecording, stopRecordingAndTranscribe, isRecording,
} from '../utils/voice';

let sessionId = `mob_${Date.now()}`;

export default function ChatScreen() {
  const [messages,  setMessages]  = useState([]);
  const [input,     setInput]     = useState('');
  const [loading,   setLoading]   = useState(false);
  const [recording, setRecording] = useState(false);
  const [autoSpeak, setAutoSpeak] = useState(true);
  const [speaking,  setSpeaking]  = useState(false);
  const listRef = useRef(null);

  useEffect(() => {
    if (messages.length > 0) {
      setTimeout(() => listRef.current?.scrollToEnd({ animated: true }), 100);
    }
  }, [messages]);

  async function send(text = input.trim(), isVocal = false, voiceEnergy = 'normal', voiceDuration = 0) {
    if (!text || loading) return;
    setInput('');
    Keyboard.dismiss();
    stopSpeaking();
    setSpeaking(false);

    const userMsg = { id: Date.now(), role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setLoading(true);

    try {
      const data = await apiJSON('/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: text, session_id: sessionId, vocal_input: isVocal, voice_energy: voiceEnergy, voice_duration: voiceDuration }),
      });

      const aiMsg = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.response,
        agents: data.agents_used || [],
      };
      setMessages(prev => [...prev, aiMsg]);

      // TTS automatique si activé
      if (autoSpeak && data.response) {
        setSpeaking(true);
        speak(data.response, {
          onDone: () => setSpeaking(false),
          onError: () => setSpeaking(false),
        });
      }
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

  async function toggleRecording() {
    if (recording) {
      // Arrêter et transcrire
      setRecording(false);
      setLoading(true);
      try {
        const result = await stopRecordingAndTranscribe('fr-FR');
        const text = typeof result === 'string' ? result : result?.text;
        const voiceEnergy = result?.voice_energy || 'normal';
        const voiceDuration = result?.voice_duration || 0;
        if (text?.trim()) {
          await send(text.trim(), true, voiceEnergy, voiceDuration);
        } else {
          Alert.alert('Voix', 'Transcription vide — réessaie en parlant plus clairement.');
          setLoading(false);
        }
      } catch (e) {
        Alert.alert('Erreur micro', e.message);
        setLoading(false);
      }
    } else {
      // Démarrer l'enregistrement
      try {
        stopSpeaking();
        setSpeaking(false);
        await startRecording();
        setRecording(true);
      } catch (e) {
        Alert.alert('Erreur micro', e.message);
      }
    }
  }

  function toggleSpeak(content) {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
    } else {
      setSpeaking(true);
      speak(content, {
        onDone: () => setSpeaking(false),
        onError: () => setSpeaking(false),
      });
    }
  }

  function renderMsg({ item }) {
    const isUser  = item.role === 'user';
    const isError = item.role === 'error';
    const isAI    = item.role === 'assistant';
    return (
      <View style={[s.msgRow, isUser && s.msgRowUser]}>
        {!isUser && (
          <View style={s.avatar}>
            <Text style={s.avatarText}>👁</Text>
          </View>
        )}
        <View style={[
          s.bubble,
          isUser  && s.bubbleUser,
          isAI    && s.bubbleAI,
          isError && s.bubbleError,
        ]}>
          {item.agents?.length > 0 && (
            <View style={s.agentBadges}>
              {item.agents.map(a => (
                <Text key={a} style={s.agentBadge}>{a.toUpperCase()}</Text>
              ))}
            </View>
          )}
          <Text style={[s.msgText, isUser && s.msgTextUser]}>{item.content}</Text>
          {isAI && (
            <TouchableOpacity style={s.speakMsgBtn} onPress={() => toggleSpeak(item.content)}>
              <Text style={s.speakMsgIcon}>{speaking ? '⏹' : '🔊'}</Text>
            </TouchableOpacity>
          )}
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
      {/* Barre outils voix */}
      <View style={s.voiceToolbar}>
        <TouchableOpacity
          style={[s.voiceToggle, autoSpeak && s.voiceToggleOn]}
          onPress={() => { setAutoSpeak(v => !v); stopSpeaking(); setSpeaking(false); }}
        >
          <Text style={[s.voiceToggleText, autoSpeak && s.voiceToggleTextOn]}>
            {autoSpeak ? '🔊 Auto ON' : '🔇 Auto OFF'}
          </Text>
        </TouchableOpacity>
        {speaking && (
          <TouchableOpacity style={s.stopSpeakBtn} onPress={() => { stopSpeaking(); setSpeaking(false); }}>
            <Text style={s.stopSpeakText}>⏹ Stopper la voix</Text>
          </TouchableOpacity>
        )}
      </View>

      {messages.length === 0 ? (
        <View style={s.welcome}>
          <Text style={s.welcomeEye}>👁️</Text>
          <Text style={s.welcomeTitle}>Bonjour, Mr Vitch</Text>
          <Text style={s.welcomeSub}>Expert OSEE · SOC · Red Team · Compagnon IA</Text>
          <Text style={s.welcomeVoice}>🎙️ Utilise le bouton micro pour parler</Text>
          <View style={s.suggestions}>
            {[
              'Fais un diagnostic système',
              'Explique le Kerberoasting',
              'Techniques de privesc Linux',
            ].map(q => (
              <TouchableOpacity key={q} style={s.suggestion} onPress={() => send(q)}>
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

      {loading && !recording && (
        <View style={s.thinkingRow}>
          <ActivityIndicator size="small" color={colors.accent} />
          <Text style={s.thinkingText}> {recording ? 'transcription…' : 'réflexion…'}</Text>
        </View>
      )}

      {recording && (
        <View style={s.recordingBar}>
          <View style={s.recDot} />
          <Text style={s.recordingText}>Enregistrement… appuie sur ⏹ pour envoyer</Text>
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
          onSubmitEditing={() => send()}
          blurOnSubmit={false}
          editable={!recording}
        />

        {/* Bouton micro */}
        <TouchableOpacity
          style={[s.micBtn, recording && s.micBtnActive]}
          onPress={toggleRecording}
          disabled={loading && !recording}
          activeOpacity={0.7}
        >
          <Text style={s.micIcon}>{recording ? '⏹' : '🎙️'}</Text>
        </TouchableOpacity>

        {/* Bouton envoyer texte */}
        <TouchableOpacity
          style={[s.sendBtn, (!input.trim() || loading) && s.sendBtnOff]}
          onPress={() => send()}
          disabled={!input.trim() || loading || recording}
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
  voiceToolbar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 12, paddingVertical: 6,
    backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  voiceToggle: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  voiceToggleOn: { borderColor: '#a78bfa', backgroundColor: '#8b5cf618' },
  voiceToggleText: { color: colors.textMuted, fontSize: 11, fontWeight: '600' },
  voiceToggleTextOn: { color: '#a78bfa' },
  stopSpeakBtn: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8, borderWidth: 1, borderColor: '#f9731660', backgroundColor: '#f9731618' },
  stopSpeakText: { color: '#f97316', fontSize: 11, fontWeight: '600' },
  list: { padding: 12, paddingBottom: 8 },
  welcome: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  welcomeEye: { fontSize: 56, marginBottom: 12 },
  welcomeTitle: { fontSize: 22, fontWeight: '700', color: colors.accent, marginBottom: 6 },
  welcomeSub: { fontSize: 12, color: colors.textMuted, textAlign: 'center', marginBottom: 8 },
  welcomeVoice: { fontSize: 11, color: '#a78bfa', marginBottom: 28 },
  suggestions: { width: '100%', gap: 8 },
  suggestion: { backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 14 },
  suggestionText: { color: colors.text, fontSize: 13 },
  msgRow: { flexDirection: 'row', marginBottom: 12, alignItems: 'flex-start' },
  msgRowUser: { justifyContent: 'flex-end' },
  avatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.accent,
    justifyContent: 'center', alignItems: 'center', marginRight: 8,
  },
  avatarText: { fontSize: 14 },
  bubble: { maxWidth: '82%', padding: 12, borderRadius: 14, borderTopLeftRadius: 4 },
  bubbleUser: { backgroundColor: colors.accentGlow, borderTopLeftRadius: 14, borderTopRightRadius: 4 },
  bubbleAI: { backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.border },
  bubbleError: { backgroundColor: '#3a1010', borderWidth: 1, borderColor: colors.red },
  agentBadges: { flexDirection: 'row', flexWrap: 'wrap', gap: 4, marginBottom: 6 },
  agentBadge: {
    fontSize: 9, color: colors.accent, backgroundColor: '#001a2e',
    paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4,
    borderWidth: 1, borderColor: colors.accent, fontWeight: '700', letterSpacing: 1,
  },
  msgText: { color: colors.text, fontSize: 14, lineHeight: 20 },
  msgTextUser: { color: colors.white },
  speakMsgBtn: { alignSelf: 'flex-end', marginTop: 6, opacity: 0.6 },
  speakMsgIcon: { fontSize: 14 },
  thinkingRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 8 },
  thinkingText: { color: colors.textMuted, fontSize: 12 },
  recordingBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    paddingHorizontal: 16, paddingVertical: 10,
    backgroundColor: '#ff000018', borderTopWidth: 1, borderTopColor: '#ff000030',
  },
  recDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.red },
  recordingText: { color: colors.red, fontSize: 12, fontWeight: '600', flex: 1 },
  inputRow: {
    flexDirection: 'row', alignItems: 'flex-end', padding: 12,
    paddingBottom: Platform.OS === 'ios' ? 24 : 12,
    backgroundColor: colors.bgCard, borderTopWidth: 1, borderTopColor: colors.border, gap: 8,
  },
  input: {
    flex: 1, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border,
    borderRadius: 20, paddingHorizontal: 16, paddingVertical: 10,
    color: colors.text, fontSize: 14, maxHeight: 100,
  },
  micBtn: {
    width: 44, height: 44, backgroundColor: '#8b5cf618',
    borderRadius: 22, justifyContent: 'center', alignItems: 'center',
    borderWidth: 1, borderColor: '#a78bfa60',
  },
  micBtnActive: { backgroundColor: '#ff000030', borderColor: colors.red },
  micIcon: { fontSize: 18 },
  sendBtn: {
    width: 44, height: 44, backgroundColor: colors.accent,
    borderRadius: 22, justifyContent: 'center', alignItems: 'center',
  },
  sendBtnOff: { backgroundColor: colors.textDim },
  sendIcon: { color: colors.bg, fontSize: 16, fontWeight: '700' },
});
