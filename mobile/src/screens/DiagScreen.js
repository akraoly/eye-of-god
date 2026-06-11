import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, RefreshControl, ActivityIndicator, Alert,
} from 'react-native';
import { apiJSON, getApiBase, clearApiBase, triggerLogout } from '../utils/api';
import { colors } from '../utils/theme';

function Gauge({ value, label, color }) {
  const pct = Math.min(100, Math.max(0, value || 0));
  const barColor = pct > 80 ? colors.red : pct > 60 ? colors.yellow : color || colors.green;
  return (
    <View style={g.wrap}>
      <Text style={[g.value, { color: barColor }]}>{Math.round(pct)}%</Text>
      <View style={g.track}>
        <View style={[g.fill, { width: `${pct}%`, backgroundColor: barColor }]} />
      </View>
      <Text style={g.label}>{label}</Text>
    </View>
  );
}

function StatusDot({ status }) {
  const ok = status === 'online' || status === 'ready';
  return (
    <View style={[d.dot, { backgroundColor: ok ? colors.green : colors.red }]} />
  );
}

export default function DiagScreen() {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [serverUrl,  setServerUrl]  = useState('');

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const d = await apiJSON('/api/system/diagnostic');
      setData(d);
    } catch (e) {
      console.log('Diag error:', e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    getApiBase().then(u => setServerUrl(u || 'non configuré'));
    const t = setInterval(() => load(true), 10000);
    return () => clearInterval(t);
  }, [load]);

  const resetServer = () => {
    Alert.alert(
      'Reconfigurer le serveur',
      'Cela efface l\'URL enregistrée et te déconnecte.\nUtile quand tu changes de réseau WiFi.',
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'Reconfigurer',
          style: 'destructive',
          onPress: async () => {
            await clearApiBase();
            triggerLogout(); // → App.js affiche LoginScreen avec config ouverte
          },
        },
      ]
    );
  };

  if (loading && !data) {
    return <ActivityIndicator size="large" color={colors.accent} style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  const sys = data?.system || {};

  return (
    <ScrollView
      style={s.container}
      contentContainerStyle={s.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />
      }
    >
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>🩺 Diagnostic Système</Text>
        <Text style={s.headerSub}>
          Uptime système : {sys.sys_uptime || '—'}  ·  Backend : {sys.app_uptime || '—'}
        </Text>
      </View>

      {/* Gauges */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>⚙️ Ressources</Text>
        <View style={s.gaugeRow}>
          <Gauge value={sys.cpu_percent} label="CPU" />
          <Gauge value={sys.ram_percent} label="RAM" color={colors.accent} />
          <Gauge value={sys.disk_percent} label="Disque" color={colors.yellow} />
        </View>
        <View style={s.metricsRow}>
          <MetricBox label="RAM" value={`${sys.ram_used_gb}/${sys.ram_total_gb} Go`} />
          <MetricBox label="Disque" value={`${sys.disk_used_gb}/${sys.disk_total_gb} Go`} />
          <MetricBox label="CPUs" value={sys.cpu_count || '—'} />
        </View>
        <Text style={s.load}>Load avg : {(sys.load_avg || []).join(' / ')}</Text>
      </View>

      {/* Services */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>🔌 Services</Text>
        {(data?.services || []).map(svc => (
          <View key={svc.name} style={s.serviceRow}>
            <StatusDot status={svc.status} />
            <View style={{ flex: 1 }}>
              <Text style={s.svcName}>{svc.name}</Text>
              <Text style={s.svcDetail}>{svc.detail}</Text>
            </View>
            <Text style={[s.svcStatus, { color: svc.status === 'online' ? colors.green : colors.red }]}>
              {svc.status.toUpperCase()}
            </Text>
          </View>
        ))}
      </View>

      {/* Agents */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>🤖 Agents IA</Text>
        <View style={s.agentsGrid}>
          {(data?.agents || []).map(a => (
            <View key={a.name} style={s.agentCard}>
              <StatusDot status={a.status} />
              <Text style={s.agentName}>{a.name.toUpperCase()}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* DB Stats */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>💾 Base de données</Text>
        <View style={s.dbGrid}>
          {(data?.db_stats || []).filter(r => r.count > 0).map(r => (
            <View key={r.table} style={s.dbCell}>
              <Text style={s.dbCount}>{r.count}</Text>
              <Text style={s.dbLabel}>{r.label}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Top Processes */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>📊 Top Processus</Text>
        {(data?.top_processes || []).slice(0, 6).map(p => (
          <View key={p.pid} style={s.procRow}>
            <Text style={s.procName}>{p.name}</Text>
            <Text style={[s.procCpu, { color: p.cpu > 50 ? colors.red : colors.accent }]}>
              CPU {p.cpu}%
            </Text>
            <Text style={s.procMem}>MEM {p.mem}%</Text>
          </View>
        ))}
      </View>

      {/* Serveur */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>🌐 Serveur</Text>
        <View style={s.serverRow}>
          <Text style={s.serverLabel}>URL</Text>
          <Text style={s.serverUrl} numberOfLines={1}>{serverUrl}</Text>
        </View>
        <TouchableOpacity style={s.resetBtn} onPress={resetServer} activeOpacity={0.8}>
          <Text style={s.resetBtnText}>🔄  Reconfigurer (changement de réseau)</Text>
        </TouchableOpacity>
        <Text style={s.serverHint}>
          Appuie ici si tu as changé de WiFi et que l'app ne répond plus.
        </Text>
      </View>
    </ScrollView>
  );
}

function MetricBox({ label, value }) {
  return (
    <View style={mb.box}>
      <Text style={mb.value}>{value}</Text>
      <Text style={mb.label}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  header: { marginBottom: 20 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: colors.accent, marginBottom: 4 },
  headerSub: { fontSize: 11, color: colors.textMuted },
  section: {
    backgroundColor: colors.bgCard,
    borderRadius: 12,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
    borderColor: colors.border,
  },
  sectionTitle: { fontSize: 13, color: colors.accent, fontWeight: '700', marginBottom: 12, letterSpacing: 1 },
  gaugeRow: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: 12 },
  metricsRow: { flexDirection: 'row', gap: 8, marginBottom: 8 },
  load: { color: colors.textMuted, fontSize: 11, textAlign: 'center' },
  serviceRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 1, borderBottomColor: colors.border + '50',
  },
  svcName: { color: colors.text, fontSize: 13, fontWeight: '600' },
  svcDetail: { color: colors.textMuted, fontSize: 11 },
  svcStatus: { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  agentsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  agentCard: {
    backgroundColor: colors.bgCardLight,
    borderWidth: 1, borderColor: colors.border,
    borderRadius: 8,
    padding: 10,
    flexDirection: 'row', alignItems: 'center', gap: 6,
    minWidth: '30%',
  },
  agentName: { color: colors.accent, fontSize: 11, fontWeight: '700' },
  dbGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  dbCell: {
    backgroundColor: colors.bgCardLight,
    borderRadius: 8, padding: 10, minWidth: '28%',
    alignItems: 'center',
  },
  dbCount: { color: colors.accent, fontSize: 18, fontWeight: '700' },
  dbLabel: { color: colors.textMuted, fontSize: 10, textAlign: 'center' },
  procRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: colors.border + '40',
  },
  procName: { flex: 1, color: colors.text, fontSize: 13 },
  procCpu:  { fontSize: 12, fontWeight: '600', marginRight: 12 },
  procMem:  { color: colors.textMuted, fontSize: 12 },
  serverRow:   { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 12 },
  serverLabel: { color: colors.textDim, fontSize: 11, fontWeight: '700', letterSpacing: 1, width: 30 },
  serverUrl:   { flex: 1, color: colors.accent, fontSize: 12, fontFamily: 'monospace' },
  resetBtn: {
    borderWidth: 1,
    borderColor: colors.yellow,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    backgroundColor: colors.yellow + '15',
    marginBottom: 8,
  },
  resetBtnText: { color: colors.yellow, fontWeight: '800', fontSize: 13 },
  serverHint:   { color: colors.textDim, fontSize: 11, lineHeight: 15 },
});

const g = StyleSheet.create({
  wrap: { alignItems: 'center', flex: 1 },
  value: { fontSize: 22, fontWeight: '700', marginBottom: 6 },
  track: { width: '80%', height: 6, backgroundColor: colors.border, borderRadius: 3, overflow: 'hidden' },
  fill: { height: '100%', borderRadius: 3 },
  label: { color: colors.textMuted, fontSize: 11, marginTop: 4 },
});

const d = StyleSheet.create({
  dot: { width: 8, height: 8, borderRadius: 4 },
});

const mb = StyleSheet.create({
  box: { flex: 1, backgroundColor: colors.bgCardLight, borderRadius: 8, padding: 10, alignItems: 'center' },
  value: { color: colors.text, fontSize: 13, fontWeight: '600' },
  label: { color: colors.textMuted, fontSize: 10 },
});
