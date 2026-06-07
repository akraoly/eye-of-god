import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, RefreshControl, Modal,
  Alert,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

const PRI_LABEL = { 1: '🔴 Critique', 2: '🟠 Haute', 3: '🟡 Moyenne', 4: '🟢 Basse' };
const PRI_COLOR = { 1: '#ff2244', 2: '#ff6b35', 3: '#ffd700', 4: '#00ff88' };
const FREQ_LABEL = { daily: 'Quotidien', weekly: 'Hebdo', monthly: 'Mensuel' };

export default function LifeScreen() {
  const [tab, setTab]     = useState('goals');
  const [dash, setDash]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { setDash(await apiJSON('/api/life/dashboard')); }
    catch (e) { console.log('Life error:', e.message); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const goals   = dash?.goals?.active   || [];
  const habits  = dash?.habits?.active  || [];
  const doneG   = dash?.goals?.done     || 0;
  const totalG  = dash?.goals?.total    || 0;
  const rate    = totalG > 0 ? Math.round((doneG / totalG) * 100) : 0;
  const topStreak = dash?.habits?.top_streak;

  return (
    <View style={s.container}>
      {/* Stats bar */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.statsBar} contentContainerStyle={s.statsContent}>
        <StatPill icon="🎯" label="Actifs"     value={goals.length} color="#6ee7b7" />
        <StatPill icon="✅" label="Complétés"  value={`${doneG}/${totalG} (${rate}%)`} color="#38bdf8" />
        <StatPill icon="🔥" label="Top série"  value={topStreak ? `${topStreak.name} · ${topStreak.streak}j` : '—'} color="#f97316" />
        <StatPill icon="🌀" label="Habitudes"  value={habits.length} color="#a78bfa" />
      </ScrollView>

      {/* Tabs */}
      <View style={s.tabs}>
        {[
          { id: 'goals',  label: '🎯 Objectifs' },
          { id: 'habits', label: '🔥 Habitudes' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 40 }} />
      ) : (
        <ScrollView
          contentContainerStyle={s.list}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
        >
          {tab === 'goals'  && <GoalsTab  goals={goals}  onRefresh={load} />}
          {tab === 'habits' && <HabitsTab habits={habits} onRefresh={load} />}
        </ScrollView>
      )}
    </View>
  );
}

function GoalsTab({ goals, onRefresh }) {
  const [showForm, setShowForm] = useState(false);

  const updateProgress = async (id, val) => {
    try {
      await apiFetch(`/api/life/goals/${id}`, { method: 'PUT', body: JSON.stringify({ progress: val }) });
      onRefresh();
    } catch (e) { Alert.alert('Erreur', e.message); }
  };

  const del = async (id) => {
    Alert.alert('Supprimer', 'Confirmer la suppression ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Supprimer', style: 'destructive', onPress: async () => {
        try { await apiFetch(`/api/life/goals/${id}`, { method: 'DELETE' }); onRefresh(); }
        catch (e) { Alert.alert('Erreur', e.message); }
      }},
    ]);
  };

  return (
    <View>
      <TouchableOpacity style={s.addBtn} onPress={() => setShowForm(v => !v)}>
        <Text style={s.addBtnText}>{showForm ? '✕ Annuler' : '+ Nouvel objectif'}</Text>
      </TouchableOpacity>
      {showForm && <GoalForm onSaved={() => { setShowForm(false); onRefresh(); }} />}

      {goals.length === 0 && <Text style={s.empty}>Aucun objectif actif. Crée-en un !</Text>}
      {goals.map(g => {
        const pri = g.priority || 3;
        return (
          <View key={g.id} style={[s.card, { borderLeftColor: PRI_COLOR[pri] }]}>
            <View style={s.cardHeader}>
              <Text style={s.cardTitle} numberOfLines={1}>{g.title}</Text>
              <Text style={[s.priBadge, { color: PRI_COLOR[pri] }]}>{PRI_LABEL[pri]}</Text>
              <TouchableOpacity onPress={() => del(g.id)} style={s.delBtn}>
                <Text style={s.delText}>✕</Text>
              </TouchableOpacity>
            </View>
            {g.description ? <Text style={s.cardDesc} numberOfLines={2}>{g.description}</Text> : null}
            {/* Progress bar + controls */}
            <View style={s.progressRow}>
              <View style={s.progressTrack}>
                <View style={[s.progressFill, { width: `${g.progress || 0}%`, backgroundColor: PRI_COLOR[pri] }]} />
              </View>
              <Text style={[s.progressPct, { color: PRI_COLOR[pri] }]}>{g.progress || 0}%</Text>
            </View>
            <View style={s.progressBtns}>
              {[0, 25, 50, 75, 100].map(p => (
                <TouchableOpacity key={p} style={[s.pBtn, (g.progress || 0) === p && s.pBtnActive]} onPress={() => updateProgress(g.id, p)}>
                  <Text style={[s.pBtnText, (g.progress || 0) === p && { color: colors.bg }]}>{p}%</Text>
                </TouchableOpacity>
              ))}
            </View>
            {g.deadline && (
              <Text style={s.deadline}>📅 {new Date(g.deadline).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })}</Text>
            )}
          </View>
        );
      })}
    </View>
  );
}

function GoalForm({ onSaved }) {
  const [title,    setTitle]    = useState('');
  const [desc,     setDesc]     = useState('');
  const [category, setCategory] = useState('general');
  const [priority, setPriority] = useState(3);
  const [loading,  setLoading]  = useState(false);

  const save = async () => {
    if (!title.trim()) return;
    setLoading(true);
    try {
      await apiFetch('/api/life/goals', {
        method: 'POST',
        body: JSON.stringify({ title, description: desc, category, priority: Number(priority) }),
      });
      onSaved();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  return (
    <View style={s.form}>
      <TextInput style={s.input} value={title} onChangeText={setTitle} placeholder="Titre de l'objectif *" placeholderTextColor={colors.textDim} />
      <TextInput style={s.input} value={desc} onChangeText={setDesc} placeholder="Description (optionnel)" placeholderTextColor={colors.textDim} multiline />
      <TextInput style={s.input} value={category} onChangeText={setCategory} placeholder="Catégorie" placeholderTextColor={colors.textDim} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.priorityRow}>
        {[1, 2, 3, 4].map(p => (
          <TouchableOpacity key={p} style={[s.priBtn, priority === p && { backgroundColor: PRI_COLOR[p] + '30', borderColor: PRI_COLOR[p] }]} onPress={() => setPriority(p)}>
            <Text style={[s.priBtnText, { color: priority === p ? PRI_COLOR[p] : colors.textMuted }]}>{PRI_LABEL[p]}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <TouchableOpacity style={[s.saveBtn, !title.trim() && s.saveBtnOff]} onPress={save} disabled={loading || !title.trim()}>
        <Text style={s.saveBtnText}>{loading ? '…' : 'Créer l\'objectif'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function HabitsTab({ habits, onRefresh }) {
  const [showForm, setShowForm] = useState(false);

  const done = async (id) => {
    try { await apiFetch(`/api/life/habits/${id}/done`, { method: 'POST' }); onRefresh(); }
    catch (e) { Alert.alert('Erreur', e.message); }
  };

  const del = async (id) => {
    Alert.alert('Supprimer', 'Supprimer cette habitude ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Supprimer', style: 'destructive', onPress: async () => {
        try { await apiFetch(`/api/life/habits/${id}`, { method: 'DELETE' }); onRefresh(); }
        catch (e) { Alert.alert('Erreur', e.message); }
      }},
    ]);
  };

  return (
    <View>
      <TouchableOpacity style={s.addBtn} onPress={() => setShowForm(v => !v)}>
        <Text style={s.addBtnText}>{showForm ? '✕ Annuler' : '+ Nouvelle habitude'}</Text>
      </TouchableOpacity>
      {showForm && <HabitForm onSaved={() => { setShowForm(false); onRefresh(); }} />}

      {habits.length === 0 && <Text style={s.empty}>Aucune habitude. Commence par en créer une !</Text>}
      {habits.map(h => (
        <View key={h.id} style={s.habitCard}>
          <View style={s.habitTop}>
            <Text style={s.habitName}>{h.name}</Text>
            <Text style={s.freqBadge}>{FREQ_LABEL[h.frequency] || h.frequency}</Text>
          </View>
          <View style={s.streakRow}>
            <Text style={s.streakText}>🔥 <Text style={s.streakNum}>{h.streak || 0}</Text> jours consécutifs</Text>
            {h.last_done && <Text style={s.lastDone}>{new Date(h.last_done).toLocaleDateString('fr-FR')}</Text>}
          </View>
          <View style={s.habitActions}>
            <TouchableOpacity style={s.doneBtn} onPress={() => done(h.id)}>
              <Text style={s.doneBtnText}>✓ Fait aujourd'hui</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.delBtn} onPress={() => del(h.id)}>
              <Text style={s.delText}>✕</Text>
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </View>
  );
}

function HabitForm({ onSaved }) {
  const [name,    setName]    = useState('');
  const [freq,    setFreq]    = useState('daily');
  const [desc,    setDesc]    = useState('');
  const [loading, setLoading] = useState(false);

  const save = async () => {
    if (!name.trim()) return;
    setLoading(true);
    try {
      await apiFetch('/api/life/habits', {
        method: 'POST',
        body: JSON.stringify({ name, description: desc, frequency: freq }),
      });
      onSaved();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  return (
    <View style={s.form}>
      <TextInput style={s.input} value={name} onChangeText={setName} placeholder="Nom de l'habitude *" placeholderTextColor={colors.textDim} />
      <TextInput style={s.input} value={desc} onChangeText={setDesc} placeholder="Description (optionnel)" placeholderTextColor={colors.textDim} />
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.priorityRow}>
        {[
          { id: 'daily', label: '📅 Quotidien' },
          { id: 'weekly', label: '📆 Hebdo' },
          { id: 'monthly', label: '🗓 Mensuel' },
        ].map(f => (
          <TouchableOpacity key={f.id} style={[s.priBtn, freq === f.id && s.priBtnSel]} onPress={() => setFreq(f.id)}>
            <Text style={[s.priBtnText, freq === f.id && { color: colors.accent }]}>{f.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
      <TouchableOpacity style={[s.saveBtn, !name.trim() && s.saveBtnOff]} onPress={save} disabled={loading || !name.trim()}>
        <Text style={s.saveBtnText}>{loading ? '…' : 'Créer l\'habitude'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function StatPill({ icon, label, value, color }) {
  return (
    <View style={[sp.pill, { borderColor: color + '40' }]}>
      <Text style={sp.icon}>{icon}</Text>
      <View>
        <Text style={[sp.val, { color }]}>{value}</Text>
        <Text style={sp.lbl}>{label}</Text>
      </View>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  statsBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  statsContent: { flexDirection: 'row', padding: 12, gap: 10 },
  tabs: { flexDirection: 'row', backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  tab: { flex: 1, paddingVertical: 14, alignItems: 'center' },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  list: { padding: 12, gap: 10, paddingBottom: 32 },
  addBtn: {
    borderWidth: 1, borderColor: colors.accent, borderStyle: 'dashed',
    borderRadius: 10, padding: 14, alignItems: 'center', marginBottom: 12,
  },
  addBtnText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  card: {
    backgroundColor: colors.bgCard, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.border, borderLeftWidth: 4, gap: 8,
  },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardTitle: { flex: 1, color: colors.text, fontSize: 14, fontWeight: '700' },
  cardDesc: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  priBadge: { fontSize: 11, fontWeight: '700' },
  delBtn: { padding: 4 },
  delText: { color: colors.red, fontSize: 14, fontWeight: '700' },
  progressRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  progressTrack: { flex: 1, height: 6, backgroundColor: colors.bgCardLight, borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 3 },
  progressPct: { fontSize: 12, fontWeight: '700', width: 36, textAlign: 'right' },
  progressBtns: { flexDirection: 'row', gap: 4 },
  pBtn: {
    flex: 1, paddingVertical: 5, borderRadius: 6,
    borderWidth: 1, borderColor: colors.border,
    alignItems: 'center',
  },
  pBtnActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pBtnText: { fontSize: 11, color: colors.textMuted },
  deadline: { color: colors.textDim, fontSize: 11 },
  habitCard: {
    backgroundColor: colors.bgCard, borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: colors.border, gap: 8,
  },
  habitTop: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  habitName: { flex: 1, color: colors.text, fontSize: 14, fontWeight: '700' },
  freqBadge: {
    fontSize: 10, color: colors.accent, backgroundColor: '#001a2e',
    paddingHorizontal: 8, paddingVertical: 2, borderRadius: 4,
    borderWidth: 1, borderColor: colors.accent,
  },
  streakRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  streakText: { color: colors.textMuted, fontSize: 12 },
  streakNum: { color: '#f97316', fontWeight: '800', fontSize: 16 },
  lastDone: { color: colors.textDim, fontSize: 11 },
  habitActions: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  doneBtn: { flex: 1, backgroundColor: '#00ff8818', borderWidth: 1, borderColor: '#00ff88', borderRadius: 8, padding: 10, alignItems: 'center' },
  doneBtnText: { color: '#00ff88', fontSize: 13, fontWeight: '700' },
  form: { backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 14, marginBottom: 12, gap: 10 },
  input: {
    backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border,
    borderRadius: 8, padding: 12, color: colors.text, fontSize: 13,
  },
  priorityRow: { gap: 6 },
  priBtn: {
    paddingHorizontal: 12, paddingVertical: 8,
    borderRadius: 8, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.bg,
  },
  priBtnSel: { borderColor: colors.accent, backgroundColor: colors.accent + '18' },
  priBtnText: { fontSize: 12, color: colors.textMuted },
  saveBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 14, alignItems: 'center' },
  saveBtnOff: { backgroundColor: colors.textDim },
  saveBtnText: { color: colors.bg, fontWeight: '700', fontSize: 14 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 40, fontSize: 14 },
});

const sp = StyleSheet.create({
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: colors.bgCardLight, borderRadius: 10,
    borderWidth: 1, paddingHorizontal: 12, paddingVertical: 8,
  },
  icon: { fontSize: 20 },
  val: { fontSize: 13, fontWeight: '700' },
  lbl: { fontSize: 10, color: colors.textDim },
});
