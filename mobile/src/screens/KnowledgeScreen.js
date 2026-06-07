import React, { useState, useEffect } from 'react';
import {
  View, Text, TextInput, FlatList, TouchableOpacity,
  StyleSheet, ActivityIndicator, Keyboard,
} from 'react-native';
import { apiJSON } from '../utils/api';
import { colors } from '../utils/theme';

const CAT_COLORS = {
  cyber: '#ff6b35', programmation: '#00d4ff', ai: '#a855f7',
  sciences: '#22c55e', business: '#fbbf24', projets: '#ec4899',
  utilisateur: '#06b6d4', general: '#6b7280',
};

export default function KnowledgeScreen() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [all, setAll] = useState([]);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    loadAll();
  }, []);

  async function loadAll() {
    setLoading(true);
    try {
      const [list, s] = await Promise.all([
        apiJSON('/api/knowledge/list?limit=100'),
        apiJSON('/api/knowledge/stats'),
      ]);
      setAll(list.entries || []);
      setStats(s);
    } catch (e) {
      console.log('Knowledge error:', e.message);
    } finally {
      setLoading(false);
    }
  }

  async function search() {
    if (!query.trim()) {
      setSearching(false);
      return;
    }
    Keyboard.dismiss();
    setLoading(true);
    setSearching(true);
    try {
      const r = await apiJSON(`/api/knowledge/search?q=${encodeURIComponent(query)}&limit=20`);
      setResults(r.results || []);
    } catch (e) {
      console.log('Search error:', e.message);
    } finally {
      setLoading(false);
    }
  }

  function clear() {
    setQuery('');
    setSearching(false);
    setResults([]);
  }

  const displayed = searching ? results : all;

  function renderEntry({ item }) {
    const catColor = CAT_COLORS[item.category] || colors.textMuted;
    return (
      <View style={s.card}>
        <View style={s.cardHeader}>
          <Text style={[s.catBadge, { color: catColor, borderColor: catColor }]}>
            {item.category}
          </Text>
          <Text style={s.importance}>★ {Math.round((item.importance || 0.5) * 100)}%</Text>
        </View>
        <Text style={s.title}>{item.title}</Text>
        {item.summary ? (
          <Text style={s.summary} numberOfLines={3}>{item.summary}</Text>
        ) : null}
        {item.tags?.length > 0 && (
          <View style={s.tags}>
            {item.tags.slice(0, 4).map(t => (
              <Text key={t} style={s.tag}>#{t}</Text>
            ))}
          </View>
        )}
      </View>
    );
  }

  return (
    <View style={s.container}>
      {/* Stats bar */}
      {stats && (
        <View style={s.statsBar}>
          <Text style={s.statItem}>📚 {stats.total_entries} entrées</Text>
          {Object.entries(stats.by_category || {}).slice(0, 3).map(([cat, n]) => (
            <Text key={cat} style={[s.statItem, { color: CAT_COLORS[cat] || colors.textMuted }]}>
              {cat} {n}
            </Text>
          ))}
        </View>
      )}

      {/* Search bar */}
      <View style={s.searchRow}>
        <TextInput
          style={s.searchInput}
          value={query}
          onChangeText={setQuery}
          placeholder="Rechercher dans la base…"
          placeholderTextColor={colors.textDim}
          returnKeyType="search"
          onSubmitEditing={search}
          autoCorrect={false}
        />
        <TouchableOpacity style={s.searchBtn} onPress={search}>
          <Text style={s.searchIcon}>🔍</Text>
        </TouchableOpacity>
        {searching && (
          <TouchableOpacity style={s.clearBtn} onPress={clear}>
            <Text style={s.clearIcon}>✕</Text>
          </TouchableOpacity>
        )}
      </View>

      {searching && (
        <Text style={s.resultCount}>
          {results.length} résultat{results.length !== 1 ? 's' : ''} pour "{query}"
        </Text>
      )}

      {loading ? (
        <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={displayed}
          keyExtractor={e => String(e.id)}
          renderItem={renderEntry}
          contentContainerStyle={s.list}
          ListEmptyComponent={
            <Text style={s.empty}>
              {searching ? 'Aucun résultat' : 'Base vide'}
            </Text>
          }
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  statsBar: {
    flexDirection: 'row', flexWrap: 'wrap', gap: 8,
    padding: 10, backgroundColor: colors.bgCard,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  statItem: { fontSize: 11, color: colors.textMuted },
  searchRow: {
    flexDirection: 'row', alignItems: 'center',
    padding: 12, gap: 8,
  },
  searchInput: {
    flex: 1, backgroundColor: colors.bgCard,
    borderWidth: 1, borderColor: colors.border,
    borderRadius: 10, padding: 12,
    color: colors.text, fontSize: 14,
  },
  searchBtn: {
    width: 44, height: 44, backgroundColor: colors.accentGlow,
    borderRadius: 10, justifyContent: 'center', alignItems: 'center',
  },
  searchIcon: { fontSize: 18 },
  clearBtn: {
    width: 36, height: 44, justifyContent: 'center', alignItems: 'center',
  },
  clearIcon: { color: colors.textMuted, fontSize: 18 },
  resultCount: {
    color: colors.textMuted, fontSize: 12,
    paddingHorizontal: 16, marginBottom: 4,
  },
  list: { padding: 12, gap: 10 },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.border,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 8, gap: 8 },
  catBadge: {
    fontSize: 10, fontWeight: '700', letterSpacing: 1,
    borderWidth: 1, paddingHorizontal: 8, paddingVertical: 2,
    borderRadius: 4,
  },
  importance: { marginLeft: 'auto', color: colors.textDim, fontSize: 11 },
  title: { color: colors.text, fontSize: 14, fontWeight: '600', marginBottom: 6 },
  summary: { color: colors.textMuted, fontSize: 12, lineHeight: 18, marginBottom: 8 },
  tags: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  tag: { color: colors.textDim, fontSize: 11 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 60, fontSize: 14 },
});
