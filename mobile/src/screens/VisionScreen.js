import React, { useState } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Image,
} from 'react-native';
import { apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

export default function VisionScreen() {
  const [tab,       setTab]      = useState('screenshot');
  const [prompt,    setPrompt]   = useState('');
  const [result,    setResult]   = useState(null);
  const [loading,   setLoading]  = useState(false);
  const [error,     setError]    = useState('');

  const doScreenshot = async () => {
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await apiFetch(`/api/vision/screenshot${prompt.trim() ? `?prompt=${encodeURIComponent(prompt)}` : ''}`, { method: 'POST' });
      if (!r.ok) { const e = await r.json(); setError(e.detail || 'Erreur capture'); return; }
      const d = await r.json();
      setResult(d);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const doAnalyzeB64 = async () => {
    if (!b64Input.trim()) { setError('Entrez une image en base64'); return; }
    setLoading(true); setError(''); setResult(null);
    try {
      const r = await apiFetch('/api/vision/analyze', {
        method: 'POST',
        body: JSON.stringify({ image_b64: b64Input.trim(), media_type: 'image/png', prompt: prompt.trim() || undefined }),
      });
      if (!r.ok) { const e = await r.json(); setError(e.detail || 'Erreur analyse'); return; }
      const d = await r.json();
      setResult(d);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  };

  const [b64Input, setB64Input] = useState('');

  return (
    <View style={s.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {[
          { id: 'screenshot', label: '📷 Capture serveur' },
          { id: 'analyze',    label: '🔍 Analyser image' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => { setTab(t.id); setResult(null); setError(''); }}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView contentContainerStyle={s.list}>
        {/* Header */}
        <View style={s.headerCard}>
          <Text style={s.headerIcon}>👁</Text>
          <View>
            <Text style={s.headerTitle}>CLAUDE VISION</Text>
            <Text style={s.headerSub}>Analyse visuelle par IA — claude-sonnet-4-6</Text>
          </View>
        </View>

        {/* Prompt commun */}
        <View style={s.promptRow}>
          <TextInput
            style={s.promptInput}
            value={prompt}
            onChangeText={setPrompt}
            placeholder="Prompt personnalisé (optionnel)…"
            placeholderTextColor={colors.textDim}
            multiline
          />
        </View>

        {tab === 'screenshot' && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>📷 Capture d'écran du serveur Kali</Text>
            <Text style={s.sectionDesc}>
              Capture l'écran du serveur et l'analyse avec Claude Vision.{'\n'}
              Idéal pour inspecter l'état du bureau à distance.
            </Text>

            <View style={s.presets}>
              {[
                'Décris l\'état du bureau en détail',
                'Y a-t-il des alertes ou erreurs visibles ?',
                'Analyse les terminaux ouverts',
                'Identifie les processus actifs',
              ].map(q => (
                <TouchableOpacity key={q} style={s.presetBtn} onPress={() => setPrompt(q)}>
                  <Text style={s.presetText}>{q}</Text>
                </TouchableOpacity>
              ))}
            </View>

            <TouchableOpacity style={[s.actionBtn, loading && s.actionBtnOff]} onPress={doScreenshot} disabled={loading}>
              {loading ? <ActivityIndicator size="small" color={colors.bg} /> : <Text style={s.actionBtnText}>📸 Capturer & Analyser</Text>}
            </TouchableOpacity>
          </View>
        )}

        {tab === 'analyze' && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>🔍 Analyser une image (Base64)</Text>
            <Text style={s.sectionDesc}>
              Collez une image encodée en base64 pour l'analyser avec Claude Vision.
            </Text>
            <TextInput
              style={[s.promptInput, { height: 80, marginTop: 8 }]}
              value={b64Input}
              onChangeText={setB64Input}
              placeholder="Image en base64 (iVBORw0KGgo…)"
              placeholderTextColor={colors.textDim}
              multiline
            />
            <TouchableOpacity style={[s.actionBtn, (loading || !b64Input.trim()) && s.actionBtnOff]} onPress={doAnalyzeB64} disabled={loading || !b64Input.trim()}>
              {loading ? <ActivityIndicator size="small" color={colors.bg} /> : <Text style={s.actionBtnText}>🔬 Analyser l'image</Text>}
            </TouchableOpacity>
          </View>
        )}

        {error ? (
          <View style={s.errorBox}>
            <Text style={s.errorText}>❌ {error}</Text>
          </View>
        ) : null}

        {loading && !result && (
          <View style={s.loadingWrap}>
            <ActivityIndicator size="large" color={colors.accent} />
            <Text style={s.loadingText}>Claude Vision analyse…</Text>
          </View>
        )}

        {result && (
          <View style={s.resultCard}>
            <View style={s.resultHeader}>
              <Text style={s.resultLabel}>ANALYSE CLAUDE VISION</Text>
              <Text style={s.resultSource}>{result.source}</Text>
            </View>

            {result.image_b64 && (
              <Image
                source={{ uri: `data:${result.media_type || 'image/png'};base64,${result.image_b64}` }}
                style={s.resultImg}
                resizeMode="contain"
              />
            )}

            <View style={s.resultBody}>
              <Text style={s.resultText}>{result.analysis}</Text>
            </View>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 16, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  list: { padding: 14, gap: 14, paddingBottom: 32 },
  headerCard: {
    flexDirection: 'row', alignItems: 'center', gap: 14,
    backgroundColor: colors.bgCard, borderRadius: 14, padding: 16,
    borderWidth: 1, borderColor: colors.accent + '40',
  },
  headerIcon: { fontSize: 32 },
  headerTitle: { color: colors.accent, fontSize: 14, fontWeight: '800', letterSpacing: 2 },
  headerSub: { color: colors.textMuted, fontSize: 11, marginTop: 2 },
  promptRow: {},
  promptInput: {
    backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.border,
    borderRadius: 10, padding: 12, color: colors.text, fontSize: 13, minHeight: 48,
  },
  section: { backgroundColor: colors.bgCard, borderRadius: 14, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 10 },
  sectionTitle: { color: colors.accent, fontSize: 13, fontWeight: '700', letterSpacing: 1 },
  sectionDesc: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
  presets: { gap: 6 },
  presetBtn: { padding: 10, backgroundColor: colors.bgCardLight, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  presetText: { color: colors.textMuted, fontSize: 12 },
  actionBtn: {
    backgroundColor: colors.accent, borderRadius: 12, padding: 16,
    alignItems: 'center', flexDirection: 'row', justifyContent: 'center', gap: 8,
  },
  actionBtnOff: { backgroundColor: colors.textDim },
  actionBtnText: { color: colors.bg, fontWeight: '700', fontSize: 14 },
  errorBox: { backgroundColor: '#ff444418', borderWidth: 1, borderColor: '#ff444440', borderRadius: 10, padding: 14 },
  errorText: { color: colors.red, fontSize: 13 },
  loadingWrap: { alignItems: 'center', gap: 12, padding: 20 },
  loadingText: { color: colors.textMuted, fontSize: 13 },
  resultCard: {
    backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1,
    borderColor: colors.accent + '40', overflow: 'hidden',
  },
  resultHeader: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    padding: 12, backgroundColor: colors.bgCardLight, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  resultLabel: { color: colors.accent, fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  resultSource: { color: colors.textDim, fontSize: 10, backgroundColor: colors.bg, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  resultImg: { width: '100%', height: 200, backgroundColor: '#000' },
  resultBody: { padding: 14 },
  resultText: { color: colors.text, fontSize: 13, lineHeight: 20 },
});
