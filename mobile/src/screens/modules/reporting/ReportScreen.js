/**
 * ReportScreen — Génération de rapports d'audit professionnels
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, Switch, FlatList, Alert,
} from 'react-native';
import { colors } from '../../../utils/theme';
import { apiJSON } from '../../../utils/api';

const FORMATS = [
  { id: 'pdf',      icon: '📄', label: 'PDF'      },
  { id: 'html',     icon: '🌐', label: 'HTML'     },
  { id: 'docx',     icon: '📝', label: 'DOCX'     },
  { id: 'markdown', icon: '📋', label: 'Markdown' },
];

const STEPS = [
  'Collecte des preuves…',
  'Analyse des données…',
  'Construction MITRE…',
  'Génération du document…',
  'Finalisation…',
];

const RISK_COLOR = (score) => {
  if (score >= 80) return '#ef4444';
  if (score >= 60) return '#f97316';
  if (score >= 40) return '#eab308';
  return '#22c55e';
};

const FORMAT_ICON = { pdf: '📄', html: '🌐', docx: '📝', markdown: '📋', json: '📦' };

export default function ReportScreen() {
  const [campaignId,  setCampaignId]  = useState('');
  const [title,       setTitle]       = useState('Rapport d\'Audit');
  const [company,     setCompany]     = useState('');
  const [format,      setFormat]      = useState('html');
  const [options,     setOptions]     = useState({
    include_screenshots:     true,
    include_network:         true,
    include_mitre:           true,
    include_recommendations: true,
  });
  const [reports,     setReports]     = useState([]);
  const [generating,  setGenerating]  = useState(false);
  const [stepIdx,     setStepIdx]     = useState(0);
  const [progress,    setProgress]    = useState(0);
  const [loading,     setLoading]     = useState(false);

  const loadReports = useCallback(async () => {
    if (!campaignId) return;
    setLoading(true);
    try {
      const d = await apiJSON(`/reports/audit/campaign/${campaignId}`);
      setReports(d.reports || []);
    } catch {}
    setLoading(false);
  }, [campaignId]);

  useEffect(() => { loadReports(); }, [loadReports]);

  const toggleOption = (key) => setOptions(o => ({ ...o, [key]: !o[key] }));

  const generate = async () => {
    if (!campaignId) { Alert.alert('Erreur', 'Saisissez un campaign_id'); return; }
    setGenerating(true);
    setStepIdx(0);
    setProgress(0);

    let idx = 0;
    const tick = setInterval(() => {
      idx++;
      if (idx < STEPS.length) {
        setStepIdx(idx);
        setProgress(Math.round((idx / STEPS.length) * 90));
      } else {
        clearInterval(tick);
      }
    }, 900);

    try {
      await apiJSON('/reports/audit/generate', {
        method: 'POST',
        body: JSON.stringify({
          campaign_id: campaignId,
          format,
          title,
          options: { ...options, company_name: company },
        }),
      });
      clearInterval(tick);
      setProgress(100);
      setTimeout(() => {
        setGenerating(false);
        setProgress(0);
        loadReports();
      }, 1000);
    } catch (e) {
      clearInterval(tick);
      setGenerating(false);
      Alert.alert('Erreur', e.message);
    }
  };

  const relativeDate = (iso) => {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return 'à l\'instant';
    if (m < 60) return `il y a ${m} min`;
    return new Date(iso).toLocaleDateString('fr');
  };

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
      {/* Header */}
      <View style={s.header}>
        <Text style={s.icon}>📋</Text>
        <View>
          <Text style={s.title}>RAPPORTS D'AUDIT</Text>
          <Text style={s.subtitle}>PDF · HTML · DOCX · Markdown</Text>
        </View>
      </View>

      {/* Campagne */}
      <View style={s.card}>
        <Text style={s.cardLabel}>CAMPAIGN ID</Text>
        <TextInput
          value={campaignId} onChangeText={setCampaignId}
          placeholder="campaign_id" placeholderTextColor={colors.textDim}
          style={s.input} autoCapitalize="none"
        />
        <TextInput
          value={title} onChangeText={setTitle}
          placeholder="Titre du rapport" placeholderTextColor={colors.textDim}
          style={[s.input, { marginTop: 8 }]}
        />
        <TextInput
          value={company} onChangeText={setCompany}
          placeholder="Entreprise (optionnel)" placeholderTextColor={colors.textDim}
          style={[s.input, { marginTop: 8 }]}
        />
      </View>

      {/* Format */}
      <View style={s.card}>
        <Text style={s.cardLabel}>FORMAT</Text>
        <View style={s.chipRow}>
          {FORMATS.map(f => (
            <TouchableOpacity key={f.id} onPress={() => setFormat(f.id)}
              style={[s.chip, format === f.id && s.chipActive]}>
              <Text style={[s.chipText, format === f.id && s.chipTextActive]}>
                {f.icon} {f.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Options */}
      <View style={s.card}>
        <Text style={s.cardLabel}>CONTENU</Text>
        {[
          ['include_screenshots',     '📸 Screenshots'],
          ['include_network',         '📡 Captures réseau'],
          ['include_mitre',           '🎯 Matrice MITRE ATT&CK'],
          ['include_recommendations', '💡 Recommandations'],
        ].map(([key, label]) => (
          <View key={key} style={s.toggleRow}>
            <Text style={s.toggleLabel}>{label}</Text>
            <Switch
              value={options[key]}
              onValueChange={() => toggleOption(key)}
              trackColor={{ false: colors.textDim, true: colors.accent }}
              thumbColor={colors.white || '#fff'}
            />
          </View>
        ))}
      </View>

      {/* Génération */}
      {generating ? (
        <View style={s.card}>
          <Text style={s.cardLabel}>GÉNÉRATION EN COURS</Text>
          <View style={s.progressBarContainer}>
            <View style={[s.progressBarFill, { width: `${progress}%` }]} />
          </View>
          <Text style={s.stepText}>{STEPS[stepIdx]}</Text>
          <Text style={s.progressPct}>{progress}%</Text>
        </View>
      ) : (
        <TouchableOpacity onPress={generate} disabled={!campaignId} style={[s.genBtn, { opacity: !campaignId ? 0.4 : 1 }]}>
          <Text style={s.genBtnText}>📊 Générer le rapport</Text>
        </TouchableOpacity>
      )}

      {/* Liste des rapports */}
      <View style={s.card}>
        <View style={s.cardHeader}>
          <Text style={s.cardLabel}>RAPPORTS ({reports.length})</Text>
          <TouchableOpacity onPress={loadReports} style={s.refreshBtn}>
            <Text style={s.refreshText}>{loading ? '...' : '↺'}</Text>
          </TouchableOpacity>
        </View>
        {reports.length === 0 ? (
          <Text style={s.empty}>
            {campaignId ? 'Aucun rapport généré' : 'Saisissez un campaign_id'}
          </Text>
        ) : (
          reports.map((r, i) => (
            <View key={i} style={s.reportCard}>
              <View style={s.reportTop}>
                <Text style={s.reportFormat}>{FORMAT_ICON[r.format] || '📄'} {(r.format || '').toUpperCase()}</Text>
                {r.risk_score != null && (
                  <View style={[s.riskBadge, { backgroundColor: RISK_COLOR(r.risk_score) + '30', borderColor: RISK_COLOR(r.risk_score) }]}>
                    <Text style={[s.riskText, { color: RISK_COLOR(r.risk_score) }]}>RISK {Math.round(r.risk_score)}</Text>
                  </View>
                )}
                <View style={s.statusBadge(r.status)}>
                  <Text style={s.statusText(r.status)}>{r.status}</Text>
                </View>
              </View>
              <Text style={s.reportTitle}>{r.title}</Text>
              <Text style={s.reportMeta}>
                {r.pages_count ? `${r.pages_count} pages · ` : ''}
                {r.file_size ? `${Math.round(r.file_size / 1024)} KB · ` : ''}
                {relativeDate(r.created_at)}
              </Text>
              {r.status === 'completed' && (
                <TouchableOpacity onPress={() => Alert.alert('Téléchargement', `Rapport: ${r.report_id}\nFichier: ${r.file_path || 'N/A'}`)}
                  style={s.downloadBtn}>
                  <Text style={s.downloadText}>⬇ Télécharger</Text>
                </TouchableOpacity>
              )}
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
  subtitle: { fontSize: 11, color: colors.textMuted || '#64748b', letterSpacing: 1 },
  card: { backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 14 },
  cardLabel: { fontSize: 10, color: colors.textDim, letterSpacing: 1.5, fontWeight: '700', marginBottom: 8 },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, color: colors.text, fontSize: 13 },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { paddingVertical: 7, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bgCard },
  chipActive: { borderColor: colors.accent, backgroundColor: colors.accent + '20' },
  chipText: { color: colors.textMuted || '#94a3b8', fontSize: 12, fontWeight: '600' },
  chipTextActive: { color: colors.accent },
  toggleRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border },
  toggleLabel: { color: colors.text, fontSize: 13 },
  genBtn: { backgroundColor: colors.accent, borderRadius: 12, padding: 14, alignItems: 'center', marginBottom: 14 },
  genBtnText: { color: colors.bg, fontWeight: '800', fontSize: 15 },
  progressBarContainer: { height: 8, backgroundColor: colors.bg, borderRadius: 4, overflow: 'hidden', marginVertical: 10 },
  progressBarFill: { height: '100%', backgroundColor: colors.accent, borderRadius: 4 },
  stepText: { color: colors.textMuted || '#64748b', fontSize: 12, textAlign: 'center' },
  progressPct: { color: colors.accent, fontSize: 20, fontWeight: '800', textAlign: 'center', marginTop: 4 },
  empty: { color: colors.textMuted || '#64748b', textAlign: 'center', padding: 20, fontSize: 13 },
  reportCard: { backgroundColor: colors.bg, borderRadius: 10, borderWidth: 1, borderColor: colors.border, padding: 12, marginBottom: 10 },
  reportTop: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  reportFormat: { fontSize: 12, fontWeight: '700', color: colors.accent },
  riskBadge: { borderWidth: 1, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  riskText: { fontSize: 10, fontWeight: '700' },
  statusBadge: (st) => ({ marginLeft: 'auto', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4,
    backgroundColor: st === 'completed' ? '#22c55e20' : st === 'failed' ? '#ef444420' : '#f59e0b20' }),
  statusText: (st) => ({ fontSize: 10, fontWeight: '700',
    color: st === 'completed' ? '#22c55e' : st === 'failed' ? '#ef4444' : '#f59e0b' }),
  reportTitle: { fontSize: 13, fontWeight: '600', color: colors.text, marginBottom: 3 },
  reportMeta: { fontSize: 11, color: colors.textMuted || '#64748b' },
  downloadBtn: { marginTop: 8, borderWidth: 1, borderColor: colors.accent, borderRadius: 6, padding: 8, alignItems: 'center' },
  downloadText: { color: colors.accent, fontSize: 12, fontWeight: '700' },
  refreshBtn: { padding: 4 },
  refreshText: { color: colors.accent, fontSize: 16 },
});
