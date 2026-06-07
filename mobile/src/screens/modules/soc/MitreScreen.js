/**
 * MitreScreen — MITRE ATT&CK mobile (React Native / Expo)
 */
import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  FlatList, StyleSheet, ActivityIndicator, Alert,
  Dimensions,
} from 'react-native';
import { apiJSON } from '../../../utils/api';
import { colors } from '../../../utils/theme';

const { width: SCREEN_W } = Dimensions.get('window');

// ── Palette score ─────────────────────────────────────────────────────────────
function scoreColor(score) {
  if (!score || score === 0) return '#0a0a0a';
  if (score <= 2) return '#166534';
  if (score <= 4) return '#9a3412';
  return '#7f1d1d';
}
function scoreBorderColor(score) {
  if (!score || score === 0) return '#1a1a1a';
  if (score <= 2) return '#16a34a';
  if (score <= 4) return '#ea580c';
  return '#ef4444';
}

// ── Phase colors ─────────────────────────────────────────────────────────────
const PHASE_COLORS = {
  Recon: '#6366f1',
  'Resource Dev': '#8b5cf6',
  'Initial Access': '#ec4899',
  Execution: '#f43f5e',
  Persistence: '#f97316',
  'Priv Esc': '#eab308',
  'Defense Evasion': '#84cc16',
  'Cred Access': '#22c55e',
  Collection: '#14b8a6',
  Exfil: '#06b6d4',
  C2: '#3b82f6',
};

const PRIORITY_COLOR = {
  haute: '#ef4444',
  moyenne: '#f97316',
  faible: '#22c55e',
};

const TABS = [
  { id: 'heatmap',      label: 'Heatmap' },
  { id: 'graph',        label: 'Attack Graph' },
  { id: 'killchain',    label: 'Kill Chain' },
  { id: 'stats',        label: 'Stats' },
  { id: 'reco',         label: 'Recommandations' },
];

// ── Shared Loading / Empty ────────────────────────────────────────────────────
function Loading() {
  return (
    <View style={s.centered}>
      <ActivityIndicator color={colors.accent} size="small" />
      <Text style={s.mutedText}>Chargement…</Text>
    </View>
  );
}

function Empty({ msg }) {
  return (
    <View style={s.centered}>
      <Text style={s.mutedText}>{msg || 'Aucune donnée.'}</Text>
    </View>
  );
}

// ── Tab: Heatmap ─────────────────────────────────────────────────────────────
function HeatmapTab({ campaignId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    setLoading(true);
    apiJSON(`/api/mitre/campaign/${campaignId}/heatmap`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (!campaignId) return <Empty msg="Entrez un Campaign ID." />;
  if (loading) return <Loading />;
  if (!data?.heatmap?.length) return <Empty msg="Aucune donnée heatmap." />;

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 20 }}>
      {data.heatmap.map((row) => {
        const techniques = Object.entries(row.techniques || {});
        const phaseColor = PHASE_COLORS[row.phase] || colors.textMuted;
        return (
          <View key={row.tactic_id} style={s.heatmapRow}>
            <View style={s.heatmapHeader}>
              <View style={[s.phaseDot, { backgroundColor: phaseColor }]} />
              <Text style={[s.heatmapPhaseLabel, { color: phaseColor }]}>
                {row.phase}
              </Text>
              <Text style={s.heatmapHits}>
                {row.total_hits > 0 ? `${row.total_hits} hits` : '—'}
              </Text>
            </View>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View style={s.heatmapTiles}>
                {techniques.length === 0 ? (
                  <View style={[s.heatmapTile, { backgroundColor: '#0a0a0a', borderColor: '#1a1a1a' }]}>
                    <Text style={{ color: '#334155', fontSize: 8 }}>—</Text>
                  </View>
                ) : (
                  techniques.map(([tid, count]) => (
                    <View
                      key={tid}
                      style={[
                        s.heatmapTile,
                        {
                          backgroundColor: scoreColor(Math.min(count * 2, 5)),
                          borderColor: scoreBorderColor(Math.min(count * 2, 5)),
                        },
                      ]}
                    >
                      <Text style={s.heatmapTileText}>{count}</Text>
                    </View>
                  ))
                )}
              </View>
            </ScrollView>
          </View>
        );
      })}
    </ScrollView>
  );
}

// ── Tab: Attack Graph ─────────────────────────────────────────────────────────
function AttackGraphTab({ campaignId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    setLoading(true);
    apiJSON(`/api/mitre/campaign/${campaignId}/graph`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (!campaignId) return <Empty msg="Entrez un Campaign ID." />;
  if (loading) return <Loading />;
  if (!data?.nodes?.length) return <Empty msg="Aucun noeud graphe." />;

  // Grouper par phase
  const byPhase = {};
  for (const n of data.nodes) {
    const key = n.phase || n.tactic || '?';
    if (!byPhase[key]) byPhase[key] = [];
    byPhase[key].push(n);
  }
  const phases = Object.keys(byPhase);

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 20 }}>
      <View style={s.progressRow}>
        <Text style={s.progressLabel}>Kill Chain Progress</Text>
        <View style={s.progressBar}>
          <View style={[s.progressFill, { width: `${data.kill_chain_progress || 0}%` }]} />
        </View>
        <Text style={s.progressPct}>{data.kill_chain_progress || 0}%</Text>
      </View>

      {phases.map((phase, pi) => {
        const phaseColor = PHASE_COLORS[phase] || colors.textMuted;
        const nodes = byPhase[phase];
        return (
          <View key={phase} style={s.graphPhaseBlock}>
            <Text style={[s.graphPhaseTitle, { color: phaseColor }]}>{phase}</Text>
            <FlatList
              data={nodes}
              scrollEnabled={false}
              keyExtractor={(n) => n.technique_id}
              renderItem={({ item: node, index }) => (
                <View style={s.graphNodeRow}>
                  {index > 0 && (
                    <Text style={[s.graphArrow, { color: phaseColor }]}>→</Text>
                  )}
                  <View style={[s.graphNode, { borderColor: phaseColor }]}>
                    <Text style={[s.graphNodeTech, { color: phaseColor }]}>
                      {node.technique_id}
                    </Text>
                    <Text style={s.graphNodeName} numberOfLines={1}>
                      {node.name}
                    </Text>
                    <Text style={s.graphNodeScore}>
                      score {node.score} · {node.count}×
                    </Text>
                  </View>
                </View>
              )}
            />
            {pi < phases.length - 1 && (
              <Text style={s.graphPhaseArrow}>↓</Text>
            )}
          </View>
        );
      })}
    </ScrollView>
  );
}

// ── Tab: Kill Chain ───────────────────────────────────────────────────────────
const KILL_SEGMENTS = [
  { id: 'TA0043', label: 'Recon',     phase: 'Recon' },
  { id: 'TA0042', label: 'Res Dev',   phase: 'Resource Dev' },
  { id: 'TA0001', label: 'Init Acc',  phase: 'Initial Access' },
  { id: 'TA0002', label: 'Exec',      phase: 'Execution' },
  { id: 'TA0003', label: 'Persist',   phase: 'Persistence' },
  { id: 'TA0004', label: 'PrivEsc',   phase: 'Priv Esc' },
  { id: 'TA0005', label: 'Def Ev',    phase: 'Defense Evasion' },
  { id: 'TA0006', label: 'Cred',      phase: 'Cred Access' },
  { id: 'TA0009', label: 'Collect',   phase: 'Collection' },
  { id: 'TA0010', label: 'Exfil',     phase: 'Exfil' },
  { id: 'TA0011', label: 'C2',        phase: 'C2' },
];

function KillChainTab({ campaignId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    setLoading(true);
    apiJSON(`/api/mitre/campaign/${campaignId}/stats`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (!campaignId) return <Empty msg="Entrez un Campaign ID." />;
  if (loading) return <Loading />;

  const completed = new Set(data?.completed_phases || []);

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 20 }}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginBottom: 16 }}>
        <View style={s.killChainRow}>
          {KILL_SEGMENTS.map((seg, i) => {
            const active = completed.has(seg.phase);
            const color = PHASE_COLORS[seg.phase] || colors.textMuted;
            return (
              <View key={seg.id} style={s.killSegmentWrapper}>
                <View style={[
                  s.killSegment,
                  {
                    backgroundColor: active ? color : colors.bgCard,
                    borderColor: active ? color : colors.border,
                    shadowColor: active ? color : 'transparent',
                    shadowOpacity: active ? 0.5 : 0,
                    shadowRadius: 8,
                    elevation: active ? 4 : 0,
                  },
                ]}>
                  <Text style={[s.killSegmentNum, { color: active ? '#fff' : colors.textDim }]}>
                    {i + 1}
                  </Text>
                  <Text style={[s.killSegmentLabel, { color: active ? '#fff' : colors.textMuted }]}>
                    {seg.label}
                  </Text>
                </View>
                <Text style={[s.killSegmentStatus, { color: active ? colors.green : colors.textDim }]}>
                  {active ? 'DONE' : '—'}
                </Text>
              </View>
            );
          })}
        </View>
      </ScrollView>

      <View style={s.killSummary}>
        <View style={s.killSumItem}>
          <Text style={s.killSumValue}>{completed.size}</Text>
          <Text style={s.killSumLabel}>Phases OK</Text>
        </View>
        <View style={s.killSumItem}>
          <Text style={[s.killSumValue, { color: colors.accent }]}>
            {KILL_SEGMENTS.length}
          </Text>
          <Text style={s.killSumLabel}>Total</Text>
        </View>
        <View style={s.killSumItem}>
          <Text style={[s.killSumValue, { color: colors.cyber }]}>
            {Math.round(completed.size / KILL_SEGMENTS.length * 100)}%
          </Text>
          <Text style={s.killSumLabel}>Progress</Text>
        </View>
      </View>
    </ScrollView>
  );
}

// ── Tab: Stats ────────────────────────────────────────────────────────────────
function StatsTab({ campaignId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    setLoading(true);
    apiJSON(`/api/mitre/campaign/${campaignId}/stats`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (!campaignId) return <Empty msg="Entrez un Campaign ID." />;
  if (loading) return <Loading />;
  if (!data) return <Empty msg="Aucune stat." />;

  const kpis = [
    { label: 'Techniques',  value: data.total_techniques ?? 0,  color: '#6366f1' },
    { label: 'Tactiques',   value: data.total_tactics ?? 0,     color: '#8b5cf6' },
    { label: 'Score Total', value: data.total_score ?? 0,       color: '#f43f5e' },
    { label: 'Coverage',    value: `${data.coverage ?? 0}%`,    color: colors.green },
  ];

  return (
    <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 20 }}>
      <View style={s.statsGrid}>
        {kpis.map((k) => (
          <View key={k.label} style={[s.statsCard, { borderColor: k.color + '55', shadowColor: k.color }]}>
            <Text style={[s.statsValue, { color: k.color }]}>{k.value}</Text>
            <Text style={s.statsLabel}>{k.label}</Text>
          </View>
        ))}
      </View>

      {data.top_techniques?.length > 0 && (
        <View style={s.topSection}>
          <Text style={s.sectionTitle}>TOP TECHNIQUES</Text>
          {data.top_techniques.map((t, i) => (
            <View key={i} style={s.topRow}>
              <Text style={s.topTech}>{t.technique_id}</Text>
              <Text style={s.topTactic} numberOfLines={1}>{t.tactic_name}</Text>
              <Text style={s.topCount}>{t.count}×</Text>
              <Text style={[s.topScore, { color: '#f43f5e' }]}>{t.total_score}</Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

// ── Tab: Recommandations ──────────────────────────────────────────────────────
function RecoTab({ campaignId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!campaignId) return;
    setLoading(true);
    apiJSON(`/api/mitre/campaign/${campaignId}/recommendations`)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [campaignId]);

  if (!campaignId) return <Empty msg="Entrez un Campaign ID." />;
  if (loading) return <Loading />;
  if (!data?.recommendations?.length)
    return <Empty msg="Toutes les techniques sont couvertes !" />;

  const renderItem = ({ item }) => {
    const pColor = PRIORITY_COLOR[item.priority] || colors.textMuted;
    return (
      <View style={s.recoCard}>
        <View style={s.recoHeader}>
          <View style={[s.recoBadge, { borderColor: pColor + '55', backgroundColor: pColor + '22' }]}>
            <Text style={[s.recoBadgeText, { color: pColor }]}>
              {item.priority?.toUpperCase()}
            </Text>
          </View>
          <Text style={s.recoTech}>{item.technique_id}</Text>
          <Text style={s.recoPhase}>{item.phase}</Text>
        </View>
        <Text style={s.recoAction}>{item.action_type}</Text>
        <Text style={s.recoReason} numberOfLines={2}>{item.reason}</Text>
      </View>
    );
  };

  return (
    <FlatList
      data={data.recommendations.slice(0, 30)}
      keyExtractor={(item, i) => `${item.technique_id}-${i}`}
      renderItem={renderItem}
      contentContainerStyle={{ paddingBottom: 20 }}
      style={{ flex: 1 }}
    />
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────
export default function MitreScreen() {
  const [campaignId, setCampaignId] = useState('');
  const [inputVal, setInputVal] = useState('');
  const [activeTab, setActiveTab] = useState('heatmap');

  const submit = useCallback(() => {
    const v = inputVal.trim();
    if (!v) {
      Alert.alert('Campaign ID manquant', 'Entrez un identifiant de campagne.');
      return;
    }
    setCampaignId(v);
  }, [inputVal]);

  return (
    <View style={s.container}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>MITRE ATT&CK</Text>
        <Text style={s.headerSub}>Cartographie automatique</Text>
      </View>

      {/* Campaign ID input */}
      <View style={s.inputRow}>
        <TextInput
          style={s.input}
          value={inputVal}
          onChangeText={setInputVal}
          placeholder="Campaign ID…"
          placeholderTextColor={colors.textDim}
          onSubmitEditing={submit}
          returnKeyType="search"
          autoCapitalize="none"
        />
        <TouchableOpacity style={s.inputBtn} onPress={submit}>
          <Text style={s.inputBtnText}>OK</Text>
        </TouchableOpacity>
      </View>

      {campaignId ? (
        <View style={s.campaignBadge}>
          <Text style={s.campaignBadgeText}>{campaignId}</Text>
        </View>
      ) : null}

      {/* Tab bar */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={s.tabBar}
        contentContainerStyle={s.tabBarContent}
      >
        {TABS.map((tab) => (
          <TouchableOpacity
            key={tab.id}
            style={[s.tab, activeTab === tab.id && s.tabActive]}
            onPress={() => setActiveTab(tab.id)}
          >
            <Text style={[s.tabText, activeTab === tab.id && s.tabTextActive]}>
              {tab.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Tab content */}
      <View style={{ flex: 1, paddingHorizontal: 12 }}>
        {activeTab === 'heatmap'   && <HeatmapTab   campaignId={campaignId} />}
        {activeTab === 'graph'     && <AttackGraphTab campaignId={campaignId} />}
        {activeTab === 'killchain' && <KillChainTab  campaignId={campaignId} />}
        {activeTab === 'stats'     && <StatsTab      campaignId={campaignId} />}
        {activeTab === 'reco'      && <RecoTab       campaignId={campaignId} />}
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 16,
    paddingBottom: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '800',
    color: '#6366f1',
    letterSpacing: 2,
    fontFamily: 'monospace',
  },
  headerSub: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Input
  inputRow: {
    flexDirection: 'row',
    margin: 12,
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    color: colors.text,
    fontSize: 13,
  },
  inputBtn: {
    backgroundColor: '#4f46e5',
    borderRadius: 8,
    paddingHorizontal: 16,
    paddingVertical: 8,
    justifyContent: 'center',
  },
  inputBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 13,
  },
  campaignBadge: {
    marginHorizontal: 12,
    marginBottom: 8,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: '#1e3a5f',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 3,
    alignSelf: 'flex-start',
  },
  campaignBadgeText: {
    color: '#6366f1',
    fontSize: 11,
    fontFamily: 'monospace',
  },

  // Tabs
  tabBar: {
    maxHeight: 42,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tabBarContent: {
    paddingHorizontal: 8,
    alignItems: 'center',
  },
  tab: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabActive: {
    borderBottomColor: '#6366f1',
  },
  tabText: {
    fontSize: 12,
    color: colors.textMuted,
  },
  tabTextActive: {
    color: '#6366f1',
    fontWeight: '700',
  },

  // Shared
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingTop: 40,
  },
  mutedText: {
    color: colors.textDim,
    fontSize: 13,
    marginTop: 8,
  },

  // Heatmap
  heatmapRow: {
    marginBottom: 8,
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  heatmapHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 6,
  },
  phaseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  heatmapPhaseLabel: {
    fontSize: 11,
    fontWeight: '700',
    flex: 1,
  },
  heatmapHits: {
    fontSize: 10,
    color: colors.textDim,
  },
  heatmapTiles: {
    flexDirection: 'row',
    flexWrap: 'nowrap',
    gap: 3,
  },
  heatmapTile: {
    width: 30,
    height: 22,
    borderRadius: 3,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  heatmapTileText: {
    fontSize: 9,
    color: '#e2e8f0',
    fontFamily: 'monospace',
  },

  // Attack Graph
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  progressLabel: {
    fontSize: 11,
    color: colors.textMuted,
    minWidth: 110,
  },
  progressBar: {
    flex: 1,
    height: 6,
    backgroundColor: colors.bgCard,
    borderRadius: 3,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    backgroundColor: '#6366f1',
    borderRadius: 3,
  },
  progressPct: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.accent,
    minWidth: 36,
    textAlign: 'right',
  },
  graphPhaseBlock: {
    marginBottom: 12,
  },
  graphPhaseTitle: {
    fontSize: 11,
    fontWeight: '700',
    marginBottom: 6,
    letterSpacing: 1,
  },
  graphNodeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  graphArrow: {
    fontSize: 18,
    marginRight: 4,
    fontWeight: '700',
  },
  graphNode: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
  },
  graphNodeTech: {
    fontSize: 12,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  graphNodeName: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },
  graphNodeScore: {
    fontSize: 10,
    color: colors.textDim,
    marginTop: 2,
  },
  graphPhaseArrow: {
    textAlign: 'center',
    fontSize: 20,
    color: colors.textDim,
    marginVertical: 4,
  },

  // Kill Chain
  killChainRow: {
    flexDirection: 'row',
    gap: 6,
    paddingHorizontal: 4,
    paddingVertical: 8,
  },
  killSegmentWrapper: {
    alignItems: 'center',
  },
  killSegment: {
    width: 64,
    height: 60,
    borderRadius: 8,
    borderWidth: 2,
    alignItems: 'center',
    justifyContent: 'center',
  },
  killSegmentNum: {
    fontSize: 10,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  killSegmentLabel: {
    fontSize: 9,
    fontWeight: '600',
    marginTop: 2,
    textAlign: 'center',
  },
  killSegmentStatus: {
    fontSize: 8,
    fontWeight: '700',
    marginTop: 4,
  },
  killSummary: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    gap: 20,
    justifyContent: 'center',
  },
  killSumItem: {
    alignItems: 'center',
  },
  killSumValue: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.green,
  },
  killSumLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 2,
  },

  // Stats
  statsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 20,
    paddingTop: 8,
  },
  statsCard: {
    width: (SCREEN_W - 24 - 34) / 2,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderRadius: 10,
    padding: 16,
    alignItems: 'center',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.3,
    shadowRadius: 12,
    elevation: 3,
  },
  statsValue: {
    fontSize: 28,
    fontWeight: '900',
  },
  statsLabel: {
    fontSize: 11,
    color: colors.textMuted,
    marginTop: 4,
  },
  topSection: {
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 10,
    color: colors.textDim,
    fontWeight: '700',
    letterSpacing: 2,
    marginBottom: 8,
  },
  topRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 8,
  },
  topTech: {
    fontSize: 12,
    color: '#6366f1',
    fontFamily: 'monospace',
    fontWeight: '700',
    minWidth: 80,
  },
  topTactic: {
    flex: 1,
    fontSize: 11,
    color: colors.textMuted,
  },
  topCount: {
    fontSize: 11,
    color: colors.text,
    minWidth: 28,
    textAlign: 'right',
  },
  topScore: {
    fontSize: 11,
    fontWeight: '700',
    minWidth: 28,
    textAlign: 'right',
  },

  // Recommandations
  recoCard: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
  },
  recoHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 4,
  },
  recoBadge: {
    borderWidth: 1,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  recoBadgeText: {
    fontSize: 9,
    fontWeight: '700',
  },
  recoTech: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: '#6366f1',
    flex: 1,
  },
  recoPhase: {
    fontSize: 10,
    color: colors.textDim,
  },
  recoAction: {
    fontSize: 12,
    color: colors.text,
    marginBottom: 2,
  },
  recoReason: {
    fontSize: 10,
    color: colors.textMuted,
  },
});
