import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  RefreshControl, ActivityIndicator, ScrollView, TextInput, Alert,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

const SEV_COLOR = { critical: '#ff2244', high: '#ff6b35', medium: '#ffd700', low: '#00d4ff', info: '#6b8aaa' };
const SEV_ICON  = { critical: '🔴', high: '🟠', medium: '🟡', low: '🔵', info: '⚪' };

export default function SocScreen() {
  const [tab, setTab] = useState('alerts');

  const TABS = [
    { id: 'alerts',     label: '🚨 Alertes' },
    { id: 'incidents',  label: '📁 Incidents' },
    { id: 'mitre',      label: '🗺 MITRE' },
    { id: 'threatintel',label: '🕵️ Threat Intel' },
    { id: 'hunt',       label: '🎯 Hunt' },
    { id: 'stats',      label: '📊 Stats' },
  ];

  return (
    <View style={s.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {TABS.map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'alerts'      && <AlertsTab />}
      {tab === 'incidents'   && <IncidentsTab />}
      {tab === 'mitre'       && <MitreTab />}
      {tab === 'threatintel' && <ThreatIntelTab />}
      {tab === 'hunt'        && <HuntTab />}
      {tab === 'stats'       && <StatsTab />}
    </View>
  );
}

function AlertsTab() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { const d = await apiJSON('/api/soc/alerts?limit=50'); setAlerts(d.alerts || d || []); }
    catch (_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const updateStatus = async (id, status) => {
    try { await apiFetch(`/api/soc/alerts/${id}`, { method: 'PATCH', body: JSON.stringify({ status }) }); load(true); }
    catch (_) {}
  };

  const renderAlert = ({ item }) => {
    const sev = item.severity || 'info';
    return (
      <View style={[s.alertCard, { borderLeftColor: SEV_COLOR[sev] || colors.border }]}>
        <View style={s.alertHeader}>
          <Text style={s.alertIcon}>{SEV_ICON[sev] || '⚪'}</Text>
          <Text style={[s.alertSev, { color: SEV_COLOR[sev] || colors.textMuted }]}>{sev.toUpperCase()}</Text>
          <TouchableOpacity
            style={[s.statusBadge, item.status === 'closed' && s.statusClosed]}
            onPress={() => updateStatus(item.id, item.status === 'open' ? 'closed' : 'open')}
          >
            <Text style={s.statusText}>{item.status || 'open'}</Text>
          </TouchableOpacity>
        </View>
        <Text style={s.alertTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={s.alertMeta}>{item.category || 'unknown'} · {item.source || 'system'}</Text>
        {item.description ? <Text style={s.alertDesc} numberOfLines={2}>{item.description}</Text> : null}
        {item.mitre_technique && <Text style={s.mitreBadge}>MITRE: {item.mitre_technique}</Text>}
      </View>
    );
  };

  return loading ? (
    <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
  ) : (
    <FlatList
      data={alerts}
      keyExtractor={a => String(a.id)}
      renderItem={renderAlert}
      contentContainerStyle={s.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
      ListEmptyComponent={<Text style={s.empty}>Aucune alerte SOC</Text>}
    />
  );
}

function IncidentsTab() {
  const [incidents, setIncidents] = useState([]);
  const [loading,   setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showForm, setShowForm] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { const d = await apiJSON('/api/soc/incidents?limit=30'); setIncidents(d.incidents || []); }
    catch (_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <View style={{ flex: 1 }}>
      <View style={s.actionBar}>
        <TouchableOpacity style={s.actionBtn} onPress={() => setShowForm(v => !v)}>
          <Text style={s.actionBtnText}>{showForm ? '✕ Annuler' : '+ Créer incident'}</Text>
        </TouchableOpacity>
      </View>
      {showForm && <IncidentForm onSaved={() => { setShowForm(false); load(); }} />}
      {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} /> : (
        <FlatList
          data={incidents}
          keyExtractor={i => String(i.id)}
          contentContainerStyle={s.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
          ListEmptyComponent={<Text style={s.empty}>Aucun incident actif</Text>}
          renderItem={({ item }) => {
            const sev = item.severity || 'medium';
            return (
              <View style={[s.alertCard, { borderLeftColor: SEV_COLOR[sev] || colors.border }]}>
                <View style={s.alertHeader}>
                  <Text style={[s.alertSev, { color: SEV_COLOR[sev] }]}>{sev.toUpperCase()}</Text>
                  <Text style={[s.statusBadge, { color: colors.accent }]}>{item.status}</Text>
                </View>
                <Text style={s.alertTitle}>{item.title}</Text>
                <Text style={s.alertMeta}>{item.category} · {item.affected_assets?.length || 0} assets</Text>
                {item.description && <Text style={s.alertDesc} numberOfLines={2}>{item.description}</Text>}
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

function IncidentForm({ onSaved }) {
  const [title,    setTitle]    = useState('');
  const [severity, setSeverity] = useState('medium');
  const [category, setCategory] = useState('');
  const [loading,  setLoading]  = useState(false);

  const save = async () => {
    if (!title.trim()) return;
    setLoading(true);
    try {
      await apiFetch('/api/soc/incidents', {
        method: 'POST',
        body: JSON.stringify({ title, severity, category: category || 'general' }),
      });
      onSaved();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  return (
    <View style={s.form}>
      <TextInput style={s.input} value={title} onChangeText={setTitle} placeholder="Titre de l'incident *" placeholderTextColor={colors.textDim} />
      <TextInput style={s.input} value={category} onChangeText={setCategory} placeholder="Catégorie" placeholderTextColor={colors.textDim} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
        {['critical', 'high', 'medium', 'low'].map(sv => (
          <TouchableOpacity key={sv} style={[s.sevBtn, severity === sv && { borderColor: SEV_COLOR[sv], backgroundColor: SEV_COLOR[sv] + '18' }]} onPress={() => setSeverity(sv)}>
            <Text style={[s.sevBtnText, severity === sv && { color: SEV_COLOR[sv] }]}>{SEV_ICON[sv]} {sv}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <TouchableOpacity style={[s.saveBtn, !title.trim() && s.saveBtnOff]} onPress={save} disabled={loading || !title.trim()}>
        <Text style={s.saveBtnText}>{loading ? '…' : 'Créer l\'incident'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function MitreTab() {
  const [stats,    setStats]    = useState(null);
  const [query,    setQuery]    = useState('');
  const [results,  setResults]  = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    apiJSON('/api/soc/mitre/stats').then(d => setStats(d)).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    setSearching(true);
    try {
      const d = await apiJSON('/api/soc/mitre/search', {
        method: 'POST',
        body: JSON.stringify({ query }),
      });
      setResults(d.results || d.techniques || []);
    } catch (_) {}
    finally { setSearching(false); }
  };

  return (
    <ScrollView contentContainerStyle={s.list}>
      {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} /> : null}

      {stats && (
        <View style={s.mitreStats}>
          <Text style={s.mitreTitle}>🗺 MITRE ATT&CK Coverage</Text>
          <View style={s.mitreGrid}>
            <MitreCard label="Techniques" value={stats.techniques_covered || 0} color="#38bdf8" />
            <MitreCard label="Tactiques" value={stats.tactics || stats.tactics_count || 0} color="#a78bfa" />
            <MitreCard label="Alertes liées" value={stats.alerts_with_technique || 0} color="#f97316" />
            <MitreCard label="Couverture" value={`${stats.coverage_pct || 0}%`} color="#6ee7b7" />
          </View>
        </View>
      )}

      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Rechercher technique MITRE (ex: T1059, lateral)…"
          placeholderTextColor={colors.textDim}
          onSubmitEditing={search}
          returnKeyType="search"
        />
        <TouchableOpacity style={s.searchBtn} onPress={search} disabled={searching}>
          <Text style={s.searchBtnText}>{searching ? '…' : '🔍'}</Text>
        </TouchableOpacity>
      </View>

      {results.map((r, i) => (
        <View key={i} style={s.techniqueCard}>
          <View style={s.techniqueHeader}>
            <Text style={s.techniqueId}>{r.technique_id || r.id}</Text>
            <Text style={s.tactiqueBadge}>{r.tactic || r.tactic_name}</Text>
          </View>
          <Text style={s.techniqueName}>{r.name}</Text>
          {r.description && <Text style={s.techniqueDesc} numberOfLines={3}>{r.description}</Text>}
        </View>
      ))}
    </ScrollView>
  );
}

function MitreCard({ label, value, color }) {
  return (
    <View style={[s.mitreCard, { borderColor: color + '40' }]}>
      <Text style={[s.mitreVal, { color }]}>{value}</Text>
      <Text style={s.mitreLbl}>{label}</Text>
    </View>
  );
}

function ThreatIntelTab() {
  const [query,   setQuery]   = useState('');
  const [type,    setType]    = useState('ip');
  const [result,  setResult]  = useState(null);
  const [iocs,    setIocs]    = useState([]);
  const [loading, setLoading] = useState(false);
  const [loadingIocs, setLoadingIocs] = useState(true);

  useEffect(() => {
    apiJSON('/api/soc/threat-intel/iocs?limit=20').then(d => setIocs(d.iocs || [])).catch(() => {}).finally(() => setLoadingIocs(false));
  }, []);

  const check = async () => {
    if (!query.trim()) return;
    setLoading(true); setResult(null);
    try {
      const ep = type === 'ip' ? `/api/soc/threat-intel/check/ip/${encodeURIComponent(query)}` : `/api/soc/threat-intel/check/domain/${encodeURIComponent(query)}`;
      const d = await apiJSON(ep);
      setResult(d);
    } catch (e) { setResult({ error: e.message }); }
    finally { setLoading(false); }
  };

  return (
    <ScrollView contentContainerStyle={s.list}>
      <View style={s.intelHeader}>
        <Text style={s.intelTitle}>🕵️ THREAT INTELLIGENCE</Text>
        <Text style={s.intelSub}>Vérification IOC · IPs · Domaines</Text>
      </View>

      <View style={s.segRow}>
        {['ip', 'domain'].map(t => (
          <TouchableOpacity key={t} style={[s.seg, type === t && s.segActive]} onPress={() => setType(t)}>
            <Text style={[s.segText, type === t && s.segTextActive]}>{t === 'ip' ? '🌐 IP' : '🔗 Domaine'}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder={type === 'ip' ? 'Ex: 185.220.101.x' : 'Ex: malware.example.com'}
          placeholderTextColor={colors.textDim}
          autoCapitalize="none"
          onSubmitEditing={check}
        />
        <TouchableOpacity style={s.searchBtn} onPress={check} disabled={loading}>
          <Text style={s.searchBtnText}>{loading ? '…' : '🔍'}</Text>
        </TouchableOpacity>
      </View>

      {result && !result.error && (
        <View style={[s.resultBox, { borderColor: result.malicious ? colors.red + '60' : colors.green + '60', backgroundColor: result.malicious ? '#ff444412' : '#00ff8812' }]}>
          <Text style={[s.resultTitle, { color: result.malicious ? colors.red : colors.green }]}>
            {result.malicious ? '⚠️ MALVEILLANT' : '✅ PROPRE'}
          </Text>
          <Text style={s.resultVal}>{query}</Text>
          {result.hits > 0 && <Text style={s.resultMeta}>Correspondances : {result.hits} IOCs</Text>}
          {result.categories?.length > 0 && <Text style={s.resultMeta}>Catégories : {result.categories.join(', ')}</Text>}
        </View>
      )}
      {result?.error && <Text style={s.error}>{result.error}</Text>}

      <Text style={s.sectionTitle}>IOCs récents</Text>
      {loadingIocs ? <ActivityIndicator size="small" color={colors.accent} /> :
        iocs.map((ioc, i) => (
          <View key={i} style={s.iocRow}>
            <Text style={s.iocType}>{ioc.ioc_type || ioc.type}</Text>
            <Text style={s.iocVal} numberOfLines={1}>{ioc.value}</Text>
            <Text style={[s.iocConf, { color: ioc.confidence === 'high' ? colors.red : ioc.confidence === 'medium' ? colors.yellow : colors.textDim }]}>
              {ioc.confidence}
            </Text>
          </View>
        ))
      }
    </ScrollView>
  );
}

function HuntTab() {
  const [hunts,   setHunts]   = useState([]);
  const [loading, setLoading] = useState(true);
  const [query,   setQuery]   = useState('');
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { const d = await apiJSON('/api/soc/hunt'); setHunts(d.hunts || []); }
    catch (_) {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const createHunt = async () => {
    if (!query.trim()) return;
    setCreating(true);
    try {
      await apiFetch('/api/soc/hunt', {
        method: 'POST',
        body: JSON.stringify({ hypothesis: query, techniques: [], timeframe_hours: 24 }),
      });
      setQuery('');
      load();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setCreating(false); }
  };

  const delHunt = async (id) => {
    try { await apiFetch(`/api/soc/hunt/${id}`, { method: 'DELETE' }); load(); }
    catch (_) {}
  };

  return (
    <ScrollView contentContainerStyle={s.list}>
      <View style={s.huntHeader}>
        <Text style={s.huntTitle}>🎯 THREAT HUNTING</Text>
        <Text style={s.huntSub}>Recherche proactive de menaces</Text>
      </View>

      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Hypothèse de chasse (ex: persistance via cron)…"
          placeholderTextColor={colors.textDim}
          multiline
        />
        <TouchableOpacity style={s.searchBtn} onPress={createHunt} disabled={creating}>
          <Text style={s.searchBtnText}>{creating ? '…' : '+'}</Text>
        </TouchableOpacity>
      </View>

      {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} /> :
        hunts.length === 0 ? <Text style={s.empty}>Aucune chasse active. Lance-en une !</Text> :
        hunts.map(h => (
          <View key={h.id} style={s.huntCard}>
            <View style={s.huntCardHeader}>
              <Text style={[s.huntStatus, { color: h.status === 'completed' ? colors.green : h.status === 'running' ? colors.yellow : colors.accent }]}>
                {h.status === 'running' ? '● EN COURS' : h.status === 'completed' ? '✓ TERMINÉ' : '⏳ EN ATTENTE'}
              </Text>
              <TouchableOpacity onPress={() => delHunt(h.id)} style={s.delHuntBtn}>
                <Text style={s.delHuntText}>✕</Text>
              </TouchableOpacity>
            </View>
            <Text style={s.huntHypothesis}>{h.hypothesis}</Text>
            {h.findings?.length > 0 && (
              <View style={s.huntFindings}>
                <Text style={s.huntFindingsTitle}>Findings : {h.findings.length}</Text>
                {h.findings.slice(0, 2).map((f, i) => (
                  <Text key={i} style={s.huntFinding} numberOfLines={2}>• {f.description || JSON.stringify(f)}</Text>
                ))}
              </View>
            )}
            <Text style={s.huntMeta}>{new Date(h.created_at).toLocaleString('fr-FR')}</Text>
          </View>
        ))
      }
    </ScrollView>
  );
}

function StatsTab() {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      apiJSON('/api/soc/alerts/stats'),
      apiJSON('/api/soc/incidents/stats'),
    ]).then(([a, i]) => setStats({ alerts: a, incidents: i })).catch(() => {}).finally(() => setLoading(false));
  }, []);

  if (loading) return <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />;
  if (!stats) return <Text style={s.empty}>Données indisponibles</Text>;

  const a = stats.alerts;
  const inc = stats.incidents;

  return (
    <ScrollView contentContainerStyle={s.list}>
      <Text style={s.sectionTitle}>ALERTES</Text>
      <StatRow label="Total alertes" value={a?.total ?? '-'} />
      <StatRow label="Critiques" value={a?.by_severity?.critical ?? 0} color={SEV_COLOR.critical} />
      <StatRow label="Hautes" value={a?.by_severity?.high ?? 0} color={SEV_COLOR.high} />
      <StatRow label="Moyennes" value={a?.by_severity?.medium ?? 0} color={SEV_COLOR.medium} />
      <StatRow label="Ouvertes" value={a?.by_status?.open ?? 0} color={colors.accent} />
      <StatRow label="Fermées" value={a?.by_status?.closed ?? 0} color={colors.green} />

      <Text style={[s.sectionTitle, { marginTop: 16 }]}>INCIDENTS</Text>
      <StatRow label="Total incidents" value={inc?.total ?? '-'} />
      <StatRow label="Ouverts" value={inc?.by_status?.open ?? 0} color={colors.accent} />
      <StatRow label="En cours" value={inc?.by_status?.investigating ?? 0} color={colors.yellow} />
      <StatRow label="Résolus" value={inc?.by_status?.resolved ?? 0} color={colors.green} />
    </ScrollView>
  );
}

function StatRow({ label, value, color }) {
  return (
    <View style={sr.row}>
      <Text style={sr.label}>{label}</Text>
      <Text style={[sr.value, color && { color }]}>{value}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 14, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.red },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.red, fontWeight: '700' },
  list: { padding: 12, gap: 10, paddingBottom: 32 },
  alertCard: {
    backgroundColor: colors.bgCard, borderRadius: 10, padding: 14,
    borderLeftWidth: 4, borderWidth: 1, borderColor: colors.border, gap: 4,
  },
  alertHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  alertIcon: { fontSize: 14 },
  alertSev: { fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  statusBadge: { marginLeft: 'auto', fontSize: 10, color: colors.textMuted, backgroundColor: colors.bgCardLight, paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4 },
  statusClosed: { backgroundColor: '#00ff8818', color: '#00ff88' },
  statusText: { color: colors.textMuted, fontSize: 10 },
  alertTitle: { color: colors.text, fontSize: 14, fontWeight: '600' },
  alertMeta: { color: colors.textMuted, fontSize: 11 },
  alertDesc: { color: colors.textDim, fontSize: 12 },
  mitreBadge: { color: '#a78bfa', fontSize: 10, backgroundColor: '#8b5cf618', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, alignSelf: 'flex-start' },
  actionBar: { padding: 10, backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  actionBtn: { borderWidth: 1, borderColor: colors.accent, borderStyle: 'dashed', borderRadius: 8, padding: 10, alignItems: 'center' },
  actionBtnText: { color: colors.accent, fontSize: 13 },
  form: { backgroundColor: colors.bgCardLight, padding: 12, gap: 8 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, color: colors.text, fontSize: 13 },
  sevBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  sevBtnText: { color: colors.textMuted, fontSize: 12 },
  saveBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 12, alignItems: 'center', marginTop: 4 },
  saveBtnOff: { backgroundColor: colors.textDim },
  saveBtnText: { color: colors.bg, fontWeight: '700' },
  mitreStats: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: '#38bdf830', gap: 10 },
  mitreTitle: { color: '#38bdf8', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  mitreGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  mitreCard: { width: '47%', backgroundColor: colors.bg, borderRadius: 10, padding: 12, borderWidth: 1, alignItems: 'center', gap: 4 },
  mitreVal: { fontSize: 22, fontWeight: '800' },
  mitreLbl: { color: colors.textDim, fontSize: 10 },
  searchRow: { flexDirection: 'row', gap: 8 },
  searchInput: { flex: 1, backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, color: colors.text, fontSize: 13 },
  searchBtn: { width: 44, height: 44, backgroundColor: colors.accent, borderRadius: 10, justifyContent: 'center', alignItems: 'center' },
  searchBtnText: { color: colors.bg, fontSize: 16, fontWeight: '700' },
  techniqueCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#a78bfa30', gap: 4 },
  techniqueHeader: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  techniqueId: { color: '#38bdf8', fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  tactiqueBadge: { color: '#a78bfa', fontSize: 10, backgroundColor: '#8b5cf618', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  techniqueName: { color: colors.text, fontSize: 13, fontWeight: '600' },
  techniqueDesc: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  intelHeader: { backgroundColor: '#f9731618', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#f9731640' },
  intelTitle: { color: '#f97316', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  intelSub: { color: colors.textDim, fontSize: 11, marginTop: 2 },
  segRow: { flexDirection: 'row', gap: 6 },
  seg: { flex: 1, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: colors.border, alignItems: 'center' },
  segActive: { borderColor: colors.accent, backgroundColor: colors.accent + '18' },
  segText: { color: colors.textMuted, fontSize: 12 },
  segTextActive: { color: colors.accent, fontWeight: '700' },
  resultBox: { borderRadius: 12, padding: 14, borderWidth: 1, gap: 6 },
  resultTitle: { fontSize: 15, fontWeight: '800', letterSpacing: 1 },
  resultVal: { color: colors.text, fontSize: 14, fontFamily: 'monospace' },
  resultMeta: { color: colors.textMuted, fontSize: 12 },
  error: { color: colors.red, fontSize: 13 },
  sectionTitle: { color: colors.textMuted, fontSize: 11, letterSpacing: 2, fontWeight: '700', textTransform: 'uppercase' },
  iocRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.border + '40' },
  iocType: { color: '#a78bfa', fontSize: 10, fontWeight: '700', width: 55, backgroundColor: '#8b5cf618', paddingHorizontal: 4, paddingVertical: 2, borderRadius: 4, textAlign: 'center' },
  iocVal: { flex: 1, color: colors.text, fontSize: 12, fontFamily: 'monospace' },
  iocConf: { fontSize: 10, fontWeight: '700' },
  huntHeader: { backgroundColor: '#6ee7b718', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#6ee7b740' },
  huntTitle: { color: '#6ee7b7', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  huntSub: { color: colors.textDim, fontSize: 11, marginTop: 2 },
  huntCard: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 6 },
  huntCardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  huntStatus: { fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  delHuntBtn: { padding: 4 },
  delHuntText: { color: colors.red, fontSize: 14 },
  huntHypothesis: { color: colors.text, fontSize: 13, lineHeight: 18 },
  huntFindings: { backgroundColor: colors.bgCardLight, borderRadius: 8, padding: 10, gap: 4 },
  huntFindingsTitle: { color: colors.accent, fontSize: 11, fontWeight: '700' },
  huntFinding: { color: colors.textMuted, fontSize: 11 },
  huntMeta: { color: colors.textDim, fontSize: 11 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 60, fontSize: 14 },
});

const sr = StyleSheet.create({
  row: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: colors.bgCard, padding: 14, borderRadius: 10,
    borderWidth: 1, borderColor: colors.border,
  },
  label: { color: colors.textMuted, fontSize: 13 },
  value: { color: colors.accent, fontSize: 18, fontWeight: '700' },
});
