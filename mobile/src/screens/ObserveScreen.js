import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

const PERIODS = [7, 14, 30, 90];
const PRI_COLOR = { 1: '#f87171', 2: '#f59e0b', 3: '#a78bfa', 4: '#38bdf8', 5: '#64748b' };
const PRI_LABEL = { 1: 'P1 Critique', 2: 'P2 Élevé', 3: 'P3 Moyen', 4: 'P4 Faible', 5: 'P5 Info' };
const STATUS_DOT = { ok: '#6ee7b7', warning: '#f59e0b', critical: '#f87171' };
const STATUS_STYLE = {
  success: { color: '#6ee7b7', bg: '#10b98118', border: '#10b98140', label: '✓' },
  error:   { color: '#f87171', bg: '#ef444418', border: '#ef444440', label: '✕' },
  skipped: { color: '#94a3b8', bg: '#94a3b810', border: '#94a3b820', label: '—' },
};

function timeAgo(iso) {
  if (!iso) return '';
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'à l\'instant';
  if (m < 60) return `il y a ${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `il y a ${h}h`;
  return `il y a ${Math.floor(h / 24)}j`;
}

function HealthRing({ score }) {
  const color = score >= 80 ? '#6ee7b7' : score >= 60 ? '#a78bfa' : score >= 40 ? '#f59e0b' : '#f87171';
  return (
    <View style={[hr.wrap, { borderColor: color, shadowColor: color }]}>
      <Text style={[hr.score, { color }]}>{score}</Text>
      <Text style={hr.of}>/100</Text>
    </View>
  );
}

export default function ObserveScreen() {
  const [tab,    setTab]    = useState('ai');
  const [period, setPeriod] = useState(7);

  return (
    <View style={s.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {[
          { id: 'ai',      label: '🤖 Analyse IA' },
          { id: 'health',  label: '🩺 Santé' },
          { id: 'actions', label: '📋 Actions' },
          { id: 'report',  label: '📄 Rapport' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'ai'      && <TabAI period={period} setPeriod={setPeriod} />}
      {tab === 'health'  && <TabHealth period={period} setPeriod={setPeriod} />}
      {tab === 'actions' && <TabActions />}
      {tab === 'report'  && <TabReport period={period} />}
    </View>
  );
}

function TabAI({ period, setPeriod }) {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [elapsed, setElapsed] = useState(0);

  const run = useCallback(async () => {
    setLoading(true); setError(''); setData(null); setElapsed(0);
    const t0 = Date.now();
    const timer = setInterval(() => setElapsed(Math.round((Date.now() - t0) / 1000)), 500);
    try {
      const r = await apiFetch(`/api/observe/ai-analysis?days=${period}`, { method: 'POST' });
      if (r.ok) setData(await r.json());
      else { const e = await r.json().catch(() => ({})); setError(e.detail || 'Erreur analyse IA'); }
    } catch (e) { setError(String(e)); }
    clearInterval(timer);
    setElapsed(Math.round((Date.now() - Date.now()) / 1000));
    setLoading(false);
  }, [period]);

  return (
    <View style={{ flex: 1 }}>
      <View style={s.ctrlBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {PERIODS.map(p => (
            <TouchableOpacity key={p} style={[s.periodBtn, period === p && s.periodBtnActive]} onPress={() => setPeriod(p)}>
              <Text style={[s.periodText, period === p && s.periodTextActive]}>{p}j</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        <TouchableOpacity style={s.aiBtn} onPress={run} disabled={loading}>
          <Text style={s.aiBtnText}>{loading ? `⏳ ${elapsed}s…` : '🤖 Analyser'}</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={s.list}>
        {error ? <Text style={s.error}>❌ {error}</Text> : null}

        {!data && !loading && !error && (
          <View style={s.emptyWrap}>
            <Text style={s.emptyIcon}>🤖</Text>
            <Text style={s.empty}>Lance une analyse pour que Claude évalue l'état du système.</Text>
          </View>
        )}

        {loading && (
          <View style={s.emptyWrap}>
            <ActivityIndicator size="large" color={colors.accent} />
            <Text style={s.empty}>Claude analyse {period} jours d'activité…</Text>
          </View>
        )}

        {data && (
          <>
            {/* Score + résumé */}
            <View style={s.scoreCard}>
              <HealthRing score={data.health_score ?? 0} />
              <View style={{ flex: 1 }}>
                <Text style={[s.healthLabel, { color: '#6ee7b7' }]}>{data.health_label || '—'}</Text>
                <Text style={s.summary}>{data.summary}</Text>
              </View>
            </View>

            {/* Problèmes critiques */}
            {data.critical_issues?.length > 0 && (
              <Section title="🚨 Problèmes critiques" color="#f87171">
                {data.critical_issues.map((issue, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#ef444440', backgroundColor: '#ef444412' }]}>
                    <Text style={[s.itemText, { color: '#f87171' }]}>#{i + 1} {issue}</Text>
                  </View>
                ))}
              </Section>
            )}

            {/* Analyse par agent */}
            {data.agent_analysis?.length > 0 && (
              <Section title="🤖 Analyse par agent">
                {data.agent_analysis.map((a, i) => (
                  <View key={i} style={s.agentCard}>
                    <View style={[s.agentDot, { backgroundColor: STATUS_DOT[a.status] || '#64748b' }]} />
                    <View style={{ flex: 1 }}>
                      <View style={s.agentHeader}>
                        <Text style={s.agentName}>{a.agent}</Text>
                        <Text style={[s.agentStatus, { color: STATUS_DOT[a.status] || '#64748b', borderColor: STATUS_DOT[a.status] + '40' || '#64748b40' }]}>{a.status}</Text>
                      </View>
                      <Text style={s.agentInsight}>{a.insight}</Text>
                    </View>
                  </View>
                ))}
              </Section>
            )}

            {/* Patterns */}
            {data.patterns?.length > 0 && (
              <Section title="🔍 Patterns comportementaux" color="#38bdf8">
                {data.patterns.map((p, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#38bdf840', backgroundColor: '#38bdf812' }]}>
                    <Text style={s.patternDot}>◆</Text>
                    <Text style={s.itemText}>{p}</Text>
                  </View>
                ))}
              </Section>
            )}

            {/* Recommandations */}
            {data.recommendations?.length > 0 && (
              <Section title="✅ Recommandations" color="#a78bfa">
                {[...data.recommendations].sort((a, b) => (a.priority || 5) - (b.priority || 5)).map((rec, i) => (
                  <View key={i} style={[s.recCard, { borderLeftColor: PRI_COLOR[rec.priority] || '#64748b' }]}>
                    <View style={s.recHeader}>
                      <Text style={[s.recPri, { color: PRI_COLOR[rec.priority], borderColor: PRI_COLOR[rec.priority] + '40' }]}>{PRI_LABEL[rec.priority] || 'P?'}</Text>
                      {rec.category && <Text style={s.recCat}>{rec.category}</Text>}
                    </View>
                    <Text style={s.recAction}>{rec.action}</Text>
                    {rec.impact && <Text style={s.recImpact}>→ {rec.impact}</Text>}
                  </View>
                ))}
              </Section>
            )}

            {/* Opportunités */}
            {data.growth_opportunities?.length > 0 && (
              <Section title="🌱 Opportunités de croissance" color="#6ee7b7">
                {data.growth_opportunities.map((g, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#10b98140', backgroundColor: '#10b98112' }]}>
                    <Text style={[s.itemText, { color: '#6ee7b7' }]}>{g}</Text>
                  </View>
                ))}
              </Section>
            )}

            {data.generated_at && (
              <Text style={s.footer}>Analyse sur {data.period_days}j · {new Date(data.generated_at + 'Z').toLocaleString('fr-FR')}</Text>
            )}
          </>
        )}
      </ScrollView>
    </View>
  );
}

function TabHealth({ period, setPeriod }) {
  const [data,    setData]    = useState(null);
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [r1, r2] = await Promise.all([
        apiFetch(`/api/observe/report?days=${period}`),
        apiFetch('/api/observe/stats'),
      ]);
      if (r1.ok) setData(await r1.json());
      if (r2.ok) setStats(await r2.json());
    } catch (_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return (
    <View style={{ flex: 1 }}>
      <View style={s.ctrlBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {PERIODS.map(p => (
            <TouchableOpacity key={p} style={[s.periodBtn, period === p && s.periodBtnActive]} onPress={() => setPeriod(p)}>
              <Text style={[s.periodText, period === p && s.periodTextActive]}>{p}j</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        <TouchableOpacity style={s.smallRefresh} onPress={() => load()}><Text style={s.smallBtnText}>↻</Text></TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={s.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
      >
        {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} /> : (
          <>
            {stats && (
              <View style={s.statsGrid}>
                {[
                  { label: 'Actions', value: stats.actions, icon: '⚡', color: '#a78bfa' },
                  { label: 'Savoir', value: stats.knowledge_entries, icon: '📚', color: '#38bdf8' },
                  { label: 'Apprentissages', value: stats.learning_events, icon: '🧠', color: '#6ee7b7' },
                  { label: 'Objectifs', value: stats.goals_active, icon: '🎯', color: '#f59e0b' },
                  { label: 'Habitudes', value: stats.habits_active, icon: '🔄', color: '#fb7185' },
                ].map(st => (
                  <View key={st.label} style={s.statCard}>
                    <Text style={s.statIcon}>{st.icon}</Text>
                    <Text style={[s.statVal, { color: st.color }]}>{st.value ?? '—'}</Text>
                    <Text style={s.statLbl}>{st.label}</Text>
                  </View>
                ))}
              </View>
            )}

            {data?.healthy?.length > 0 && (
              <Section title="✅ Points positifs" color="#6ee7b7">
                {data.healthy.map((item, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#10b98140', backgroundColor: '#10b98112' }]}>
                    <Text style={[s.itemText, { color: '#6ee7b7' }]}>{item}</Text>
                  </View>
                ))}
              </Section>
            )}

            {data?.issues?.length > 0 && (
              <Section title="⚠️ Problèmes" color="#f87171">
                {data.issues.map((item, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#ef444440', backgroundColor: '#ef444412' }]}>
                    <Text style={[s.itemText, { color: '#f87171' }]}>{item}</Text>
                  </View>
                ))}
              </Section>
            )}

            {data?.suggestions?.length > 0 && (
              <Section title="💡 Suggestions" color="#f59e0b">
                {data.suggestions.map((item, i) => (
                  <View key={i} style={[s.itemRow, { borderColor: '#f59e0b40', backgroundColor: '#f59e0b12' }]}>
                    <Text style={[s.itemText, { color: '#f59e0b' }]}>{item}</Text>
                  </View>
                ))}
              </Section>
            )}

            {data?.stats && (
              <Section title="📊 Statistiques période">
                {[
                  ['Actions totales', data.stats.total_actions],
                  ['Erreurs', data.stats.total_errors],
                  ['Taux d\'erreur', data.stats.error_rate !== undefined ? `${(data.stats.error_rate * 100).toFixed(1)}%` : '—'],
                ].map(([k, v]) => (
                  <View key={k} style={s.statRow}>
                    <Text style={s.statRowKey}>{k}</Text>
                    <Text style={s.statRowVal}>{v}</Text>
                  </View>
                ))}
              </Section>
            )}
          </>
        )}
      </ScrollView>
    </View>
  );
}

function TabActions() {
  const [actions, setActions]   = useState([]);
  const [filter,  setFilter]    = useState('all');
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { const d = await apiJSON('/api/observe/actions?limit=100'); setActions(d.actions || []); }
    catch (_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const visible = filter === 'all' ? actions : actions.filter(a => a.status === filter);

  return (
    <View style={{ flex: 1 }}>
      <View style={s.ctrlBar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {['all', 'success', 'error', 'skipped'].map(f => (
            <TouchableOpacity key={f} style={[s.periodBtn, filter === f && s.periodBtnActive]} onPress={() => setFilter(f)}>
              <Text style={[s.periodText, filter === f && s.periodTextActive, f !== 'all' && { color: STATUS_STYLE[f]?.color || colors.textMuted }]}>
                {f === 'all' ? 'Tout' : f}
              </Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
        <Text style={s.countBadge}>{visible.length}</Text>
        <TouchableOpacity style={s.smallRefresh} onPress={() => load()}><Text style={s.smallBtnText}>↻</Text></TouchableOpacity>
      </View>

      <ScrollView
        contentContainerStyle={s.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
      >
        {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} />
          : visible.length === 0 ? <Text style={s.empty}>Aucune action.</Text>
          : visible.map(a => {
          const st = STATUS_STYLE[a.status] || STATUS_STYLE.skipped;
          return (
            <View key={a.id} style={s.actionRow}>
              <View style={[s.actionBadge, { backgroundColor: st.bg, borderColor: st.border }]}>
                <Text style={[s.actionBadgeText, { color: st.color }]}>{st.label}</Text>
              </View>
              <View style={{ flex: 1 }}>
                <View style={s.actionMeta}>
                  <Text style={s.actionAgent}>{a.agent}</Text>
                  <Text style={s.actionType}>{a.action_type}</Text>
                </View>
                {a.description && <Text style={s.actionDesc} numberOfLines={2}>{a.description}</Text>}
              </View>
              <Text style={s.actionTime}>{timeAgo(a.executed_at)}</Text>
            </View>
          );
        })}
      </ScrollView>
    </View>
  );
}

function TabReport({ period }) {
  const [report,  setReport]  = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await apiFetch(`/api/observe/report?days=${period}`);
      if (r.ok) { const d = await r.json(); setReport(d.report || ''); }
    } catch (_) {}
    finally { setLoading(false); }
  }, [period]);

  useEffect(() => { load(); }, [load]);

  return (
    <View style={{ flex: 1 }}>
      <View style={[s.ctrlBar, { justifyContent: 'flex-end' }]}>
        <TouchableOpacity style={s.aiBtn} onPress={load} disabled={loading}>
          <Text style={s.aiBtnText}>{loading ? '⏳ …' : '↺ Regénérer'}</Text>
        </TouchableOpacity>
      </View>
      <ScrollView contentContainerStyle={s.list}>
        {loading ? (
          <View style={s.emptyWrap}>
            <ActivityIndicator size="large" color={colors.accent} />
            <Text style={s.empty}>Génération du rapport…</Text>
          </View>
        ) : report ? (
          <Text style={s.reportPre}>{report}</Text>
        ) : (
          <View style={s.emptyWrap}>
            <Text style={s.emptyIcon}>📄</Text>
            <Text style={s.empty}>Aucun rapport disponible.</Text>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

function Section({ title, color, children }) {
  return (
    <View style={sec.wrap}>
      <Text style={[sec.title, color && { color }]}>{title}</Text>
      {children}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 14, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  ctrlBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8, padding: 10,
    backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  periodBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  periodBtnActive: { borderColor: colors.accent, backgroundColor: colors.accent + '18' },
  periodText: { color: colors.textMuted, fontSize: 12 },
  periodTextActive: { color: colors.accent, fontWeight: '700' },
  aiBtn: { backgroundColor: colors.accent, borderRadius: 8, paddingHorizontal: 16, paddingVertical: 8 },
  aiBtnText: { color: colors.bg, fontSize: 12, fontWeight: '700' },
  smallRefresh: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  smallBtnText: { color: colors.accent, fontSize: 12 },
  countBadge: { color: colors.accent, fontSize: 11, fontWeight: '700', backgroundColor: colors.accent + '18', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 10 },
  list: { padding: 12, gap: 10, paddingBottom: 32 },
  error: { color: colors.red, fontSize: 13, padding: 12 },
  emptyWrap: { alignItems: 'center', marginTop: 60, gap: 12 },
  emptyIcon: { fontSize: 36 },
  empty: { color: colors.textMuted, textAlign: 'center', fontSize: 14 },
  scoreCard: {
    flexDirection: 'row', gap: 16, backgroundColor: colors.bgCard,
    borderRadius: 14, padding: 16, borderWidth: 1, borderColor: colors.border, alignItems: 'center',
  },
  healthLabel: { fontSize: 16, fontWeight: '800', marginBottom: 6 },
  summary: { color: colors.textMuted, fontSize: 13, lineHeight: 19 },
  itemRow: { flexDirection: 'row', gap: 8, padding: 12, borderRadius: 10, borderWidth: 1, alignItems: 'flex-start' },
  itemText: { flex: 1, color: colors.text, fontSize: 13, lineHeight: 18 },
  patternDot: { color: '#38bdf8', fontWeight: '800' },
  agentCard: { flexDirection: 'row', gap: 10, backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, alignItems: 'flex-start' },
  agentDot: { width: 10, height: 10, borderRadius: 5, marginTop: 4, flexShrink: 0 },
  agentHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  agentName: { color: colors.text, fontSize: 12, fontWeight: '700', textTransform: 'uppercase' },
  agentStatus: { fontSize: 10, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 4, borderWidth: 1, fontWeight: '600' },
  agentInsight: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  recCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 3, gap: 6 },
  recHeader: { flexDirection: 'row', gap: 6 },
  recPri: { fontSize: 11, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  recCat: { fontSize: 11, color: '#a78bfa', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4, backgroundColor: '#8b5cf618', borderWidth: 1, borderColor: '#8b5cf630' },
  recAction: { color: colors.text, fontSize: 13, fontWeight: '600' },
  recImpact: { color: colors.textDim, fontSize: 12, fontStyle: 'italic' },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 8 },
  statCard: { width: '30%', backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4, alignItems: 'center' },
  statIcon: { fontSize: 20 },
  statVal: { fontSize: 20, fontWeight: '800' },
  statLbl: { color: colors.textDim, fontSize: 10, textAlign: 'center' },
  statRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border },
  statRowKey: { color: colors.textMuted, fontSize: 13 },
  statRowVal: { color: colors.text, fontSize: 13, fontWeight: '600' },
  actionRow: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  actionBadge: { width: 24, height: 24, borderRadius: 6, borderWidth: 1, justifyContent: 'center', alignItems: 'center', flexShrink: 0 },
  actionBadgeText: { fontSize: 12, fontWeight: '700' },
  actionMeta: { flexDirection: 'row', gap: 6, alignItems: 'center', marginBottom: 2 },
  actionAgent: { color: '#a78bfa', fontSize: 12, fontWeight: '700' },
  actionType: { color: '#38bdf8', fontSize: 12 },
  actionDesc: { color: colors.textMuted, fontSize: 12 },
  actionTime: { color: colors.textDim, fontSize: 11, flexShrink: 0 },
  reportPre: { color: colors.text, fontSize: 12, lineHeight: 19, fontFamily: 'monospace', backgroundColor: colors.bgCard, padding: 14, borderRadius: 10, borderWidth: 1, borderColor: colors.border },
  footer: { color: colors.textDim, fontSize: 11, textAlign: 'center', paddingBottom: 8 },
});

const sec = StyleSheet.create({
  wrap: { gap: 8 },
  title: { color: colors.textMuted, fontSize: 12, fontWeight: '700', letterSpacing: 1, textTransform: 'uppercase', marginBottom: 2 },
});

const hr = StyleSheet.create({
  wrap: {
    width: 80, height: 80, borderRadius: 40, borderWidth: 5,
    justifyContent: 'center', alignItems: 'center', flexShrink: 0,
    shadowOpacity: 0.6, shadowRadius: 8, shadowOffset: { width: 0, height: 0 },
    elevation: 6,
  },
  score: { fontSize: 26, fontWeight: '800', lineHeight: 28 },
  of: { color: colors.textDim, fontSize: 10 },
});
