import React, { useState, useEffect } from 'react';
import {
  View, Text, ScrollView, FlatList, StyleSheet,
  RefreshControl, ActivityIndicator,
} from 'react-native';
import { apiJSON } from '../utils/api';
import { colors } from '../utils/theme';

const TYPE_COLOR = {
  observation: colors.accent,
  reflection: '#a855f7',
  knowledge: '#22c55e',
  preference: '#fbbf24',
};

export default function MemoryScreen() {
  const [memories, setMemories] = useState([]);
  const [profile, setProfile]   = useState([]);
  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  async function load(silent = false) {
    if (!silent) setLoading(true);
    try {
      const [m, p, s] = await Promise.all([
        apiJSON('/api/memory/get'),
        apiJSON('/api/memory/profile'),
        apiJSON('/api/memory/vector/stats'),
      ]);
      setMemories(m.memories || m || []);
      setProfile(p.profile || []);
      setStats(s);
    } catch (e) {
      console.log('Memory error:', e.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => { load(); }, []);

  if (loading) {
    return <ActivityIndicator size="large" color={colors.accent} style={{ flex: 1, backgroundColor: colors.bg }} />;
  }

  return (
    <ScrollView
      style={s.container}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />
      }
    >
      {/* Stats */}
      {stats && (
        <View style={s.statsRow}>
          <StatPill label="Souvenirs" value={memories.length} />
          <StatPill label="Vectoriels" value={stats.total_vectors || 0} color={colors.accent} />
          <StatPill label="Profil" value={profile.length} color="#a855f7" />
        </View>
      )}

      {/* Profile */}
      {profile.length > 0 && (
        <View style={s.section}>
          <Text style={s.sectionTitle}>👤 Profil Mr Vitch</Text>
          {profile.map(p => (
            <View key={p.key} style={s.profileRow}>
              <Text style={s.profileKey}>{p.key}</Text>
              <Text style={s.profileVal}>{String(p.value)}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Memories */}
      <View style={s.section}>
        <Text style={s.sectionTitle}>🧠 Souvenirs ({memories.length})</Text>
        {memories.slice(0, 20).map(m => (
          <View key={m.id} style={s.memCard}>
            <View style={s.memHeader}>
              <Text style={[s.memType, { color: TYPE_COLOR[m.type] || colors.accent }]}>
                {m.type}
              </Text>
              <View style={s.importanceBar}>
                <View style={[s.importanceFill, { width: `${(m.importance || 0.5) * 100}%` }]} />
              </View>
              <Text style={s.memImportance}>{Math.round((m.importance || 0.5) * 100)}%</Text>
            </View>
            <Text style={s.memContent} numberOfLines={3}>{m.content}</Text>
          </View>
        ))}
        {memories.length === 0 && (
          <Text style={s.empty}>Aucun souvenir enregistré</Text>
        )}
      </View>
    </ScrollView>
  );
}

function StatPill({ label, value, color }) {
  return (
    <View style={sp.pill}>
      <Text style={[sp.value, color && { color }]}>{value}</Text>
      <Text style={sp.label}>{label}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  statsRow: { flexDirection: 'row', gap: 8, padding: 16 },
  section: {
    margin: 16, marginTop: 0,
    backgroundColor: colors.bgCard,
    borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.border,
    marginBottom: 12,
  },
  sectionTitle: { fontSize: 13, color: colors.accent, fontWeight: '700', marginBottom: 12, letterSpacing: 1 },
  profileRow: {
    flexDirection: 'row', gap: 8, paddingVertical: 8,
    borderBottomWidth: 1, borderBottomColor: colors.border + '40',
  },
  profileKey: { color: colors.textMuted, fontSize: 12, flex: 1 },
  profileVal: { color: colors.text, fontSize: 12, flex: 2 },
  memCard: { marginBottom: 12 },
  memHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  memType: { fontSize: 10, fontWeight: '700', letterSpacing: 1, width: 80 },
  importanceBar: { flex: 1, height: 4, backgroundColor: colors.border, borderRadius: 2, overflow: 'hidden' },
  importanceFill: { height: '100%', backgroundColor: colors.accent, borderRadius: 2 },
  memImportance: { color: colors.textDim, fontSize: 10, width: 30, textAlign: 'right' },
  memContent: { color: colors.textMuted, fontSize: 12, lineHeight: 18 },
  empty: { color: colors.textMuted, textAlign: 'center', paddingVertical: 20, fontSize: 13 },
});

const sp = StyleSheet.create({
  pill: {
    flex: 1, backgroundColor: colors.bgCard,
    borderRadius: 10, padding: 12, alignItems: 'center',
    borderWidth: 1, borderColor: colors.border,
  },
  value: { color: colors.green, fontSize: 22, fontWeight: '700' },
  label: { color: colors.textMuted, fontSize: 10, marginTop: 2 },
});
