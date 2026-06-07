/**
 * AudioCaptureScreen — Capture audio mobile
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, FlatList, Switch, Alert,
} from 'react-native';
import { colors } from '../../utils/theme';
import { apiJSON, apiFetch, API_BASE } from '../../utils/api';
import { getToken } from '../../utils/api';

const WS_BASE = API_BASE.replace(/^http/, 'ws');

// ── Waveform bars (data-driven) ───────────────────────────────────────────────
function WaveformBars({ active, data }) {
  const [heights, setHeights] = useState(Array(32).fill(4));
  const mockRef = useRef(null);

  useEffect(() => {
    if (data && data.length > 0) {
      // Real samples from WebSocket — map to bar heights
      const step = Math.floor(data.length / 32) || 1;
      setHeights(
        Array.from({ length: 32 }, (_, i) => {
          const val = Math.abs(data[i * step] || 0);
          return 4 + Math.min(val * 36, 36);
        })
      );
    }
  }, [data]);

  // Mock fallback when active but no WS data
  useEffect(() => {
    if (active && (!data || data.length === 0)) {
      mockRef.current = setInterval(() => {
        setHeights(Array(32).fill(0).map(() => 4 + Math.random() * 32));
      }, 100);
    } else {
      clearInterval(mockRef.current);
      if (!active) setHeights(Array(32).fill(4));
    }
    return () => clearInterval(mockRef.current);
  }, [active, data]);

  return (
    <View style={s.waveform}>
      {heights.map((h, i) => (
        <View key={i} style={[s.waveBar, {
          height: h,
          backgroundColor: active ? `hsl(${160 + i * 4}, 80%, 55%)` : colors.textDim,
        }]} />
      ))}
    </View>
  );
}

// ── Timer ─────────────────────────────────────────────────────────────────────
function useRecordTimer(running) {
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(null);
  useEffect(() => {
    if (running) {
      startRef.current = Date.now();
      setElapsed(0);
      const t = setInterval(() => setElapsed(Math.floor((Date.now() - startRef.current) / 1000)), 500);
      return () => clearInterval(t);
    } else { setElapsed(0); }
  }, [running]);
  const mm = String(Math.floor(elapsed / 60)).padStart(2, '0');
  const ss = String(elapsed % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export default function AudioCaptureScreen() {
  const [sessions,        setSessions]        = useState([]);
  const [sessionId,       setSessionId]       = useState('');
  const [microphones,     setMicrophones]     = useState([]);
  const [micLoading,      setMicLoading]      = useState(false);
  const [selectedMic,     setSelectedMic]     = useState('');
  const [duration,        setDuration]        = useState(30);
  const [quality,         setQuality]         = useState('medium');
  const [recording,       setRecording]       = useState(false);
  const [recordings,      setRecordings]      = useState([]);
  const [keyword,         setKeyword]         = useState('');
  const [keywordActive,   setKeywordActive]   = useState(false);
  const [loading,         setLoading]         = useState(false);
  const [isStreaming,     setIsStreaming]      = useState(false);
  const [waveformData,    setWaveformData]     = useState([]);
  const [packetsReceived, setPacketsReceived] = useState(0);
  const wsRef       = useRef(null);
  const ppsRef      = useRef(0);
  const ppsTimer    = useRef(null);
  const timer = useRecordTimer(recording);
  const recordTimeout = useRef(null);

  // Load sessions
  useEffect(() => {
    apiJSON('/pentest/jobs').then(d => setSessions(d.jobs || [])).catch(() => {});
  }, []);

  // Load recordings
  const loadRecordings = useCallback(() => {
    const qs = sessionId ? `?session_id=${sessionId}` : '';
    apiJSON(`/audio/recordings${qs}`).then(d => setRecordings(d.recordings || [])).catch(() => {});
  }, [sessionId]);

  useEffect(() => {
    loadRecordings();
    const t = setInterval(loadRecordings, 5000);
    return () => clearInterval(t);
  }, [loadRecordings]);

  const startStream = useCallback(async () => {
    if (!sessionId) { Alert.alert('Erreur', 'Sélectionner une session'); return; }
    if (wsRef.current) wsRef.current.close();
    setPacketsReceived(0);
    ppsRef.current = 0;

    let token = '';
    try { token = await getToken(); } catch {}
    const url = `${WS_BASE}/api/audio/stream/${sessionId}?token=${token}`;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsStreaming(true);
        ppsTimer.current = setInterval(() => {
          setPacketsReceived(ppsRef.current);
        }, 1000);
      };

      ws.onmessage = (evt) => {
        ppsRef.current += 1;
        try {
          const msg = JSON.parse(evt.data);
          if (msg.samples && Array.isArray(msg.samples)) {
            setWaveformData(msg.samples);
          } else if (typeof evt.data === 'string' && evt.data.startsWith('[')) {
            setWaveformData(JSON.parse(evt.data));
          }
        } catch {
          // binary chunk — generate mock from length
          setWaveformData(Array(64).fill(0).map(() => Math.random()));
        }
      };

      ws.onerror = () => {
        setIsStreaming(false);
        clearInterval(ppsTimer.current);
      };

      ws.onclose = () => {
        setIsStreaming(false);
        clearInterval(ppsTimer.current);
      };
    } catch (e) {
      Alert.alert('Stream', `WebSocket unavailable: ${e.message}`);
    }
  }, [sessionId]);

  const stopStream = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    clearInterval(ppsTimer.current);
    setIsStreaming(false);
    setWaveformData([]);
    setPacketsReceived(0);
  }, []);

  useEffect(() => () => {
    if (wsRef.current) wsRef.current.close();
    clearInterval(ppsTimer.current);
  }, []);

  const listMics = async () => {
    if (!sessionId) { Alert.alert('Erreur', 'Sélectionner une session'); return; }
    setMicLoading(true);
    try {
      const d = await apiJSON(`/audio/microphones/${sessionId}`);
      setMicrophones(d.microphones || []);
    } catch { Alert.alert('Erreur', 'Impossible de lister les microphones'); }
    setMicLoading(false);
  };

  const startRecording = async () => {
    if (!sessionId) { Alert.alert('Erreur', 'Sélectionner une session'); return; }
    setLoading(true);
    try {
      await apiJSON('/audio/record', {
        method: 'POST',
        body: JSON.stringify({
          session_id: sessionId, duration, quality,
          microphone: selectedMic || undefined,
          keyword: keywordActive && keyword ? keyword : undefined,
        }),
      });
      setRecording(true);
      recordTimeout.current = setTimeout(() => {
        setRecording(false);
        loadRecordings();
      }, duration * 1000);
    } catch (e) { Alert.alert('Erreur', e.message); }
    setLoading(false);
  };

  const stopRecording = async () => {
    clearTimeout(recordTimeout.current);
    setRecording(false);
    try { await apiFetch('/audio/record/stop', { method: 'POST', body: JSON.stringify({ session_id: sessionId }) }); } catch {}
    loadRecordings();
  };

  useEffect(() => () => clearTimeout(recordTimeout.current), []);

  const QUALITY = ['low', 'medium', 'high'];
  const DURATION_OPTIONS = [10, 30, 60, 120, 300];
  const fmtDur = s => s < 60 ? `${s}s` : `${Math.floor(s / 60)}m`;
  const fmtSize = b => !b ? '' : b < 1048576 ? `${(b / 1024).toFixed(0)}KB` : `${(b / 1048576).toFixed(1)}MB`;

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
      {/* Header */}
      <View style={s.header}>
        <Text style={s.icon}>🎤</Text>
        <View>
          <Text style={s.title}>AUDIO CAPTURE</Text>
          <Text style={s.subtitle}>Enregistrement · Surveillance</Text>
        </View>
      </View>

      {/* Session selector */}
      <View style={s.card}>
        <Text style={s.cardLabel}>SESSION CIBLE</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 10 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {sessions.length === 0 && (
              <Text style={{ color: colors.textMuted, fontSize: 13 }}>Aucune session active</Text>
            )}
            {sessions.map(s2 => (
              <TouchableOpacity key={s2.job_id} onPress={() => setSessionId(s2.job_id)}
                style={[s.chip, sessionId === s2.job_id && s.chipActive]}>
                <Text style={[s.chipText, sessionId === s2.job_id && s.chipTextActive]}>
                  {s2.target}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </ScrollView>
        <TouchableOpacity onPress={listMics} disabled={micLoading || !sessionId} style={[s.btn, { opacity: !sessionId ? 0.4 : 1 }]}>
          {micLoading ? <ActivityIndicator color={colors.bg} size="small" /> : <Text style={s.btnText}>🎙 Lister les micros</Text>}
        </TouchableOpacity>
        {microphones.map((m, i) => {
          const mid = m.id || m.name || String(i);
          return (
            <TouchableOpacity key={i} onPress={() => setSelectedMic(mid)}
              style={[s.micRow, selectedMic === mid && s.micRowActive]}>
              <Text style={[s.micText, selectedMic === mid && { color: colors.accent }]}>
                🎙 {m.name || `Mic ${i}`}
              </Text>
              {m.default && <Text style={s.defaultBadge}>DEFAULT</Text>}
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Params */}
      <View style={s.card}>
        <Text style={s.cardLabel}>DURÉE</Text>
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 14 }}>
          {DURATION_OPTIONS.map(d => (
            <TouchableOpacity key={d} onPress={() => setDuration(d)}
              style={[s.chip, duration === d && s.chipActive]}>
              <Text style={[s.chipText, duration === d && s.chipTextActive]}>{fmtDur(d)}</Text>
            </TouchableOpacity>
          ))}
        </View>
        <Text style={s.cardLabel}>QUALITÉ</Text>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {QUALITY.map(q => (
            <TouchableOpacity key={q} onPress={() => setQuality(q)}
              style={[s.chip, quality === q && s.chipActive, { flex: 1 }]}>
              <Text style={[s.chipText, quality === q && s.chipTextActive, { textAlign: 'center' }]}>{q}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Keyword */}
      <View style={s.card}>
        <View style={s.row}>
          <Text style={s.cardLabel}>DÉTECTION MOT-CLÉ</Text>
          <Switch value={keywordActive} onValueChange={setKeywordActive}
            trackColor={{ false: colors.textDim, true: colors.accent }}
            thumbColor={colors.white} />
        </View>
        <TextInput
          value={keyword} onChangeText={setKeyword} editable={keywordActive}
          placeholder="mot-clé, alarme…" placeholderTextColor={colors.textDim}
          style={[s.input, { opacity: keywordActive ? 1 : 0.5 }]}
        />
      </View>

      {/* Record controls */}
      <View style={s.card}>
        <Text style={s.cardLabel}>VISUALISATION</Text>
        <WaveformBars active={recording || isStreaming} data={waveformData} />
        {recording && (
          <Text style={s.timerText}>⏺ {timer} / {fmtDur(duration)}</Text>
        )}
        {isStreaming && (
          <Text style={s.streamBadge}>📡 LIVE · {packetsReceived} pkt/s</Text>
        )}
        <View style={{ marginTop: 12, gap: 8 }}>
          {!recording ? (
            <TouchableOpacity onPress={startRecording} disabled={loading || !sessionId}
              style={[s.recordBtn, { opacity: !sessionId ? 0.4 : 1 }]}>
              {loading ? <ActivityIndicator color="#ef4444" size="small" /> : <Text style={s.recordBtnText}>⏺ Enregistrer</Text>}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={stopRecording} style={s.stopBtn}>
              <Text style={s.stopBtnText}>⏹ Arrêter</Text>
            </TouchableOpacity>
          )}
          {!isStreaming ? (
            <TouchableOpacity onPress={startStream} disabled={!sessionId}
              style={[s.streamBtn, { opacity: !sessionId ? 0.4 : 1 }]}>
              <Text style={s.streamBtnText}>📡 Start Stream</Text>
            </TouchableOpacity>
          ) : (
            <TouchableOpacity onPress={stopStream} style={s.streamStopBtn}>
              <Text style={s.streamBtnText}>⏹ Stop Stream</Text>
            </TouchableOpacity>
          )}
        </View>
      </View>

      {/* Recordings list */}
      <View style={s.card}>
        <Text style={s.cardLabel}>ENREGISTREMENTS ({recordings.length})</Text>
        {recordings.length === 0 ? (
          <Text style={s.empty}>Aucun enregistrement</Text>
        ) : (
          recordings.map((rec, i) => (
            <View key={i} style={s.recRow}>
              <View style={{ flex: 1 }}>
                <Text style={s.recName}>{rec.filename || `rec_${rec.id?.slice(0, 8)}`}</Text>
                <Text style={s.recMeta}>
                  {rec.duration ? `${rec.duration}s` : ''}
                  {rec.size ? ` · ${fmtSize(rec.size)}` : ''}
                  {rec.created_at ? ` · ${rec.created_at.slice(11, 19)}` : ''}
                </Text>
                {rec.keyword_hits > 0 && (
                  <Text style={s.keywordHit}>🔑 {rec.keyword_hits} détection(s)</Text>
                )}
              </View>
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 20 },
  icon: { fontSize: 32 },
  title: { fontSize: 16, fontWeight: '800', color: colors.accent, letterSpacing: 2 },
  subtitle: { fontSize: 11, color: colors.textMuted, letterSpacing: 1 },
  card: { backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 14 },
  cardLabel: { fontSize: 10, color: colors.textDim, letterSpacing: 1.5, fontWeight: '700', marginBottom: 8 },
  btn: { backgroundColor: colors.accent, borderRadius: 8, padding: 10, alignItems: 'center' },
  btnText: { color: colors.bg, fontWeight: '800', fontSize: 14 },
  chip: { paddingVertical: 6, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bgCardLight },
  chipActive: { borderColor: colors.accent, backgroundColor: colors.accent + '20' },
  chipText: { color: colors.textMuted, fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: colors.accent },
  micRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', padding: 8, marginTop: 6, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  micRowActive: { borderColor: colors.accent, backgroundColor: colors.accent + '10' },
  micText: { color: colors.text, fontSize: 13 },
  defaultBadge: { color: colors.accent, fontSize: 10, fontWeight: '700' },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, color: colors.text, fontSize: 13, marginTop: 6 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  waveform: { flexDirection: 'row', alignItems: 'flex-end', height: 40, gap: 2, backgroundColor: colors.bg, borderRadius: 8, padding: 4 },
  waveBar: { flex: 1, borderRadius: 2, backgroundColor: colors.textDim },
  timerText: { color: '#ef4444', fontWeight: '800', fontSize: 16, fontFamily: 'monospace', textAlign: 'center', marginTop: 8 },
  recordBtn: { borderWidth: 1, borderColor: '#ef4444', borderRadius: 8, padding: 12, alignItems: 'center', backgroundColor: '#ef444420' },
  recordBtnText: { color: '#ef4444', fontWeight: '800', fontSize: 15 },
  stopBtn: { borderWidth: 1, borderColor: colors.yellow, borderRadius: 8, padding: 12, alignItems: 'center', backgroundColor: colors.yellow + '20' },
  stopBtnText: { color: colors.yellow, fontWeight: '800', fontSize: 15 },
  recRow: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, backgroundColor: colors.bg, borderRadius: 8, marginBottom: 8, borderWidth: 1, borderColor: colors.border },
  recName: { color: colors.text, fontSize: 13, fontWeight: '600' },
  recMeta: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  keywordHit: { color: colors.yellow, fontSize: 11, marginTop: 2 },
  empty: { color: colors.textMuted, fontSize: 13, textAlign: 'center', paddingVertical: 16 },
  streamBadge: { color: '#22d3ee', fontSize: 12, fontWeight: '700', textAlign: 'center', marginTop: 6 },
  streamBtn: { borderWidth: 1, borderColor: '#22d3ee', borderRadius: 8, padding: 12, alignItems: 'center', backgroundColor: '#22d3ee20' },
  streamStopBtn: { borderWidth: 1, borderColor: colors.textDim, borderRadius: 8, padding: 12, alignItems: 'center', backgroundColor: colors.textDim + '20' },
  streamBtnText: { color: '#22d3ee', fontWeight: '800', fontSize: 14 },
});
