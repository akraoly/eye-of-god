import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { apiJSON } from '../utils/api';
import { colors } from '../utils/theme';

const SEV_COLOR = { critical: '#ff2244', high: '#ff6b35', medium: '#ffd700', low: '#00d4ff', info: '#6b8aaa' };
const SEV_ICON  = { critical: '🔴', high: '🟠', medium: '🟡', low: '🔵', info: '⚪' };

export default function SocScreen() {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [tab, setTab] = useState('alerts');

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [a, s] = await Promise.all([
        apiJSON('/api/soc/alerts?limit=50'),
        apiJSON('/api/soc/alerts/stats'),
      ]);
      setAlerts(a.alerts || a || []);
      setStats(s);
    } catch (e) {
      console.log('SOC error:', e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  function renderAlert({ item }) {
    const sev = item.severity || 'info';
    return (
      <View style={[s.alertCard, { borderLeftColor: SEV_COLOR[sev] || colors.border }]}>
        <View style={s.alertHeader}>
          <Text style={s.alertIcon}>{SEV_ICON[sev] || '⚪'}</Text>
          <Text style={[s.alertSev, { color: SEV_COLOR[sev] || colors.textMuted }]}>
            {sev.toUpperCase()}
          </Text>
          <Text style={s.alertStatus}>{item.status || 'open'}</Text>
        </View>
        <Text style={s.alertTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={s.alertMeta}>
          {item.category || 'unknown'} · {item.source || 'system'}
        </Text>
        {item.description ? (
          <Text style={s.alertDesc} numberOfLines={2}>{item.description}</Text>
        ) : null}
      </View>
    );
  }

  return (
    <View style={s.container}>
      {/* Tabs */}
      <View style={s.tabs}>
        {['alerts', 'stats'].map(t => (
          <TouchableOpacity
            key={t}
            style={[s.tab, tab === t && s.tabActive]}
            onPress={() => setTab(t)}
          >
            <Text style={[s.tabText, tab === t && s.tabTextActive]}>
              {t === 'alerts' ? '🚨 Alertes' : '📊 Stats'}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
      ) : tab === 'alerts' ? (
        <FlatList
          data={alerts}
          keyExtractor={a => String(a.id)}
          renderItem={renderAlert}
          contentContainerStyle={s.list}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => { setRefreshing(true); load(true); }}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <Text style={s.empty}>Aucune alerte SOC</Text>
          }
        />
      ) : (
        <View style={s.statsWrap}>
          {stats ? (
            <>
              <StatRow label="Total alertes" value={stats.total ?? '-'} />
              <StatRow label="Critiques" value={stats.by_severity?.critical ?? 0} color={SEV_COLOR.critical} />
              <StatRow label="Hautes" value={stats.by_severity?.high ?? 0} color={SEV_COLOR.high} />
              <StatRow label="Moyennes" value={stats.by_severity?.medium ?? 0} color={SEV_COLOR.medium} />
              <StatRow label="Ouvertes" value={stats.by_status?.open ?? 0} color={colors.accent} />
              <StatRow label="Fermées" value={stats.by_status?.closed ?? 0} color={colors.green} />
            </>
          ) : (
            <Text style={s.empty}>Stats indisponibles</Text>
          )}
        </View>
      )}
    </View>
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
  tabs: { flexDirection: 'row', backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  list: { padding: 12, gap: 10 },
  alertCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 10,
    padding: 14,
    borderLeftWidth: 4,
    borderWidth: 1,
    borderColor: colors.border,
  },
  alertHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 6, gap: 6 },
  alertIcon: { fontSize: 14 },
  alertSev: { fontSize: 11, fontWeight: '700', letterSpacing: 1 },
  alertStatus: {
    marginLeft: 'auto', fontSize: 10,
    color: colors.textMuted,
    backgroundColor: colors.bgCardLight,
    paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 4,
  },
  alertTitle: { color: colors.text, fontSize: 14, fontWeight: '600', marginBottom: 4 },
  alertMeta: { color: colors.textMuted, fontSize: 11, marginBottom: 4 },
  alertDesc: { color: colors.textDim, fontSize: 12 },
  statsWrap: { padding: 16, gap: 12 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 60, fontSize: 14 },
});

const sr = StyleSheet.create({
  row: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: colors.bgCard, padding: 16, borderRadius: 10,
    borderWidth: 1, borderColor: colors.border,
  },
  label: { color: colors.textMuted, fontSize: 14 },
  value: { color: colors.accent, fontSize: 18, fontWeight: '700' },
});
