/**
 * OmniscienceScreen — Dashboard global mobile
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  FlatList, ActivityIndicator, Alert,
} from 'react-native';
import { colors } from '../utils/theme';
import { apiJSON } from '../utils/api';

const SEV_COLOR = {
  CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#fbbf24', LOW: '#4ade80', INFO: '#38bdf8',
};

function StatCard({ icon, label, value, color }) {
  return (
    <View style={[s.statCard, { borderColor: (color || colors.accent) + '40' }]}>
      <Text style={s.statIcon}>{icon}</Text>
      <Text style={[s.statVal, { color: color || colors.accent }]}>{value ?? '—'}</Text>
      <Text style={s.statLabel}>{label}</Text>
    </View>
  );
}

function ActivityItem({ item }) {
  const sev = item.severity || 'INFO';
  return (
    <View style={[s.actItem, { borderLeftColor: SEV_COLOR[sev] || colors.accent }]}>
      <Text style={s.actTime}>{item.timestamp?.slice(11, 19) || '--:--:--'}</Text>
      <Text style={s.actTitle} numberOfLines={2}>{item.title || item.message || item.type}</Text>
    </View>
  );
}

function AlertGroup({ severity, count }) {
  const color = SEV_COLOR[severity] || colors.accent;
  return (
    <View style={s.alertGroup}>
      <Text style={[s.alertSev, { color }]}>{severity}</Text>
      <View style={s.alertBar}>
        <View style={[s.alertFill, { flex: count, backgroundColor: color }]} />
        <View style={[s.alertFill, { flex: Math.max(10 - count, 0), backgroundColor: 'transparent' }]} />
      </View>
      <Text style={[s.alertCount, { color }]}>{count}</Text>
    </View>
  );
}

export default function OmniscienceScreen() {
  const [stats,        setStats]        = useState(null);
  const [activities,   setActivities]   = useState([]);
  const [alerts,       setAlerts]       = useState([]);
  const [reportLoading,setReportLoading]= useState(false);
  const [report,       setReport]       = useState(null);

  const loadAll = () => {
    apiJSON('/omniscience/stats').then(setStats).catch(() => {});
    apiJSON('/omniscience/activity?limit=20').then(d => setActivities(d.events || [])).catch(() => {});
    apiJSON('/soc/alerts?limit=30').then(d => setAlerts(d.alerts || [])).catch(() => {});
  };

  useEffect(() => {
    loadAll();
    const t = setInterval(loadAll, 8000);
    return () => clearInterval(t);
  }, []);

  const generateReport = async () => {
    setReportLoading(true);
    try {
      const d = await apiJSON('/omniscience/report');
      setReport(JSON.stringify(d, null, 2));
    } catch { Alert.alert('Erreur', 'Impossible de générer le rapport'); }
    setReportLoading(false);
  };

  // Alerts by severity
  const alertsBySev = Object.entries(
    alerts.reduce((acc, a) => { acc[a.severity] = (acc[a.severity] || 0) + 1; return acc; }, {})
  ).sort(([a], [b]) => {
    const order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    return order.indexOf(a) - order.indexOf(b);
  });

  const STATS = [
    { icon: '📡', label: 'BEACONS',  key: 'beacons',    color: '#ef4444' },
    { icon: '📷', label: 'CAMERAS',  key: 'cameras',    color: '#4ade80' },
    { icon: '🚨', label: 'ALERTES',  key: 'alerts',     color: '#fbbf24' },
    { icon: '🔍', label: 'CVEs',     key: 'cves',       color: '#f97316' },
  ];

  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.icon}>🌍</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.title}>OMNISCIENCE</Text>
          <Text style={s.subtitle}>Vue globale · Temps réel</Text>
        </View>
        <TouchableOpacity onPress={generateReport} disabled={reportLoading} style={s.reportBtn}>
          {reportLoading
            ? <ActivityIndicator color={colors.accent} size="small" />
            : <Text style={s.reportBtnText}>📊 Rapport</Text>}
        </TouchableOpacity>
      </View>

      {/* Stat cards - 2x2 grid */}
      <View style={s.statsGrid}>
        {STATS.map(st => (
          <StatCard key={st.key} icon={st.icon} label={st.label} value={stats?.[st.key]} color={st.color} />
        ))}
      </View>

      {/* Alerts by severity */}
      {alertsBySev.length > 0 && (
        <View style={s.card}>
          <Text style={s.cardLabel}>ALERTES PAR SÉVÉRITÉ</Text>
          {alertsBySev.map(([sev, count]) => (
            <AlertGroup key={sev} severity={sev} count={count} />
          ))}
        </View>
      )}

      {/* Activity feed */}
      <View style={s.card}>
        <Text style={s.cardLabel}>ACTIVITÉ RÉCENTE ({activities.length})</Text>
        {activities.length === 0 ? (
          <Text style={s.empty}>Aucune activité</Text>
        ) : (
          activities.map((evt, i) => <ActivityItem key={i} item={evt} />)
        )}
      </View>

      {/* Report */}
      {report && (
        <View style={s.card}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <Text style={s.cardLabel}>RAPPORT</Text>
            <TouchableOpacity onPress={() => setReport(null)}>
              <Text style={{ color: colors.textMuted, fontSize: 16 }}>✕</Text>
            </TouchableOpacity>
          </View>
          <ScrollView horizontal>
            <Text style={s.reportText}>{report}</Text>
          </ScrollView>
        </View>
      )}
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
  reportBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.accent, backgroundColor: colors.accent + '15' },
  reportBtnText: { color: colors.accent, fontSize: 12, fontWeight: '700' },
  statsGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 14 },
  statCard: { width: '47%', backgroundColor: colors.bgCard, borderRadius: 12, borderWidth: 1, padding: 14, gap: 4, alignItems: 'flex-start' },
  statIcon: { fontSize: 20 },
  statVal: { fontSize: 22, fontWeight: '800' },
  statLabel: { fontSize: 9, color: colors.textMuted, letterSpacing: 1.5, fontWeight: '700' },
  card: { backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 14 },
  cardLabel: { fontSize: 10, color: colors.textDim, letterSpacing: 1.5, fontWeight: '700', marginBottom: 10 },
  alertGroup: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 8 },
  alertSev: { fontSize: 11, fontWeight: '700', minWidth: 64 },
  alertBar: { flex: 1, flexDirection: 'row', height: 6, borderRadius: 3, overflow: 'hidden', backgroundColor: colors.border },
  alertFill: { height: '100%', borderRadius: 3 },
  alertCount: { fontSize: 13, fontWeight: '800', minWidth: 24, textAlign: 'right' },
  actItem: { borderLeftWidth: 3, paddingLeft: 10, marginBottom: 8, paddingVertical: 4 },
  actTime: { color: colors.textMuted, fontSize: 10 },
  actTitle: { color: colors.text, fontSize: 13, marginTop: 2, lineHeight: 18 },
  empty: { color: colors.textMuted, fontSize: 13, textAlign: 'center', paddingVertical: 12 },
  reportText: { color: colors.text, fontFamily: 'monospace', fontSize: 11 },
});
