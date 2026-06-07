import React, { useState, useEffect, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, RefreshControl, Alert,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

const LVL_COLOR = { info: '#34d399', warning: '#fbbf24', error: '#f87171', critical: '#c026d3' };
const LVL_ICON  = { info: 'ℹ️', warning: '⚠️', error: '🔴', critical: '🚨' };

export default function AutonomyScreen() {
  const [tab, setTab] = useState('tasks');
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    const fetchUnread = async () => {
      try { const d = await apiJSON('/api/autonomy/alerts/count'); setUnread(d.unread || 0); }
      catch (_) {}
    };
    fetchUnread();
    const t = setInterval(fetchUnread, 15000);
    return () => clearInterval(t);
  }, []);

  return (
    <View style={s.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {[
          { id: 'tasks',    label: '⏰ Tâches' },
          { id: 'alerts',   label: `🔔 Alertes${unread > 0 ? ` (${unread})` : ''}` },
          { id: 'monitors', label: '🖥️ Moniteurs' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'tasks'    && <TasksTab />}
      {tab === 'alerts'   && <AlertsTab onRead={() => setUnread(0)} />}
      {tab === 'monitors' && <MonitorsTab />}
    </View>
  );
}

function TasksTab() {
  const [tasks,    setTasks]    = useState([]);
  const [showForm, setShowForm] = useState(false);
  const [loading,  setLoading]  = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { const d = await apiJSON('/api/autonomy/tasks'); setTasks(d.tasks || []); }
    catch (e) { console.log(e.message); }
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (id) => {
    try { await apiFetch(`/api/autonomy/tasks/${id}/toggle`, { method: 'PATCH' }); load(true); }
    catch (e) { Alert.alert('Erreur', e.message); }
  };

  const del = async (id) => {
    Alert.alert('Supprimer', 'Supprimer cette tâche planifiée ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Supprimer', style: 'destructive', onPress: async () => {
        try { await apiFetch(`/api/autonomy/tasks/${id}`, { method: 'DELETE' }); load(true); }
        catch (e) { Alert.alert('Erreur', e.message); }
      }},
    ]);
  };

  const runNow = async (id) => {
    try {
      await apiFetch(`/api/autonomy/tasks/${id}/run`, { method: 'POST' });
      Alert.alert('✅ Lancé', 'Tâche déclenchée.');
      load(true);
    } catch (e) { Alert.alert('Erreur', e.message); }
  };

  const fmtInterval = (t) => {
    if (t.schedule_type === 'cron') return `⏱ ${t.cron}`;
    if (t.schedule_type === 'once') return `🗓 une fois`;
    const s = t.interval_seconds || 3600;
    if (s < 60)   return `${s}s`;
    if (s < 3600) return `${Math.round(s / 60)}min`;
    return `${Math.round(s / 3600)}h`;
  };

  return (
    <ScrollView
      contentContainerStyle={s.list}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
    >
      <TouchableOpacity style={s.addBtn} onPress={() => setShowForm(v => !v)}>
        <Text style={s.addBtnText}>{showForm ? '✕ Annuler' : '+ Nouvelle tâche planifiée'}</Text>
      </TouchableOpacity>
      {showForm && <TaskForm onSaved={() => { setShowForm(false); load(); }} />}

      {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} />
        : tasks.length === 0 ? <Text style={s.empty}>Aucune tâche planifiée.</Text>
        : tasks.map(t => (
        <View key={t.id} style={[s.card, !t.enabled && s.cardDisabled]}>
          <View style={s.cardHeader}>
            <Text style={s.cardTitle} numberOfLines={1}>{t.name}</Text>
            <Text style={s.kindBadge}>{t.kind}</Text>
          </View>
          <Text style={s.cardCmd} numberOfLines={1}>{t.command || t.url || '—'}</Text>
          <View style={s.cardMeta}>
            <Text style={s.schedText}>{fmtInterval(t)}</Text>
            {t.run_count > 0 && <Text style={s.runCount}>{t.run_count}x</Text>}
          </View>
          {t.last_run && <Text style={s.timeText}>Dernier : {new Date(t.last_run).toLocaleString('fr-FR')}</Text>}
          {t.next_run && <Text style={s.timeText}>Prochain : {new Date(t.next_run).toLocaleString('fr-FR')}</Text>}
          <View style={s.actions}>
            <TouchableOpacity style={s.runBtn} onPress={() => runNow(t.id)}>
              <Text style={s.runBtnText}>▶ Run</Text>
            </TouchableOpacity>
            <TouchableOpacity style={[s.toggleBtn, t.enabled ? s.toggleOn : s.toggleOff]} onPress={() => toggle(t.id)}>
              <Text style={[s.toggleText, t.enabled ? s.toggleOnText : s.toggleOffText]}>{t.enabled ? '⏸ On' : '▶ Off'}</Text>
            </TouchableOpacity>
            <TouchableOpacity style={s.delBtn} onPress={() => del(t.id)}>
              <Text style={s.delText}>✕</Text>
            </TouchableOpacity>
          </View>
        </View>
      ))}
    </ScrollView>
  );
}

function TaskForm({ onSaved }) {
  const [name,     setName]     = useState('');
  const [kind,     setKind]     = useState('shell');
  const [command,  setCommand]  = useState('');
  const [url,      setUrl]      = useState('');
  const [schedType, setSchedType] = useState('interval');
  const [interval, setInterval] = useState('3600');
  const [cron,     setCron]     = useState('0 * * * *');
  const [loading,  setLoading]  = useState(false);

  const presets = [
    { label: 'Toutes les heures', type: 'interval', val: '3600' },
    { label: '30 min', type: 'interval', val: '1800' },
    { label: 'Chaque jour 8h', type: 'cron', val: '0 8 * * *' },
    { label: 'Lundi 9h', type: 'cron', val: '0 9 * * 1' },
  ];

  const save = async () => {
    if (!name.trim()) return;
    setLoading(true);
    try {
      const body = {
        name, kind,
        command: kind === 'shell' ? command : undefined,
        url: kind === 'http_check' ? url : undefined,
        schedule_type: schedType,
        interval_seconds: schedType === 'interval' ? Number(interval) : 3600,
        cron: schedType === 'cron' ? cron : undefined,
      };
      const res = await apiFetch('/api/autonomy/tasks', { method: 'POST', body: JSON.stringify(body) });
      const d = await res.json();
      if (!res.ok) { Alert.alert('Erreur', d.detail || 'Erreur'); return; }
      onSaved();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  return (
    <View style={s.form}>
      <TextInput style={s.input} value={name} onChangeText={setName} placeholder="Nom de la tâche *" placeholderTextColor={colors.textDim} />

      <View style={s.segRow}>
        {['shell', 'http_check'].map(k => (
          <TouchableOpacity key={k} style={[s.seg, kind === k && s.segActive]} onPress={() => setKind(k)}>
            <Text style={[s.segText, kind === k && s.segTextActive]}>{k === 'shell' ? '🖥️ Shell' : '🌐 HTTP'}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {kind === 'shell'      && <TextInput style={s.input} value={command} onChangeText={setCommand} placeholder="Commande (ex: df -h)" placeholderTextColor={colors.textDim} />}
      {kind === 'http_check' && <TextInput style={s.input} value={url} onChangeText={setUrl} placeholder="URL" placeholderTextColor={colors.textDim} />}

      <Text style={s.label}>Présets :</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.presetRow}>
        {presets.map((p, i) => (
          <TouchableOpacity key={i} style={s.presetBtn} onPress={() => { setSchedType(p.type); if (p.type === 'interval') setInterval(p.val); else setCron(p.val); }}>
            <Text style={s.presetText}>{p.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <View style={s.segRow}>
        {['interval', 'cron', 'once'].map(st => (
          <TouchableOpacity key={st} style={[s.seg, schedType === st && s.segActive]} onPress={() => setSchedType(st)}>
            <Text style={[s.segText, schedType === st && s.segTextActive]}>{st}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {schedType === 'interval' && (
        <TextInput style={s.input} value={interval} onChangeText={setInterval} placeholder="Secondes (ex: 3600)" placeholderTextColor={colors.textDim} keyboardType="numeric" />
      )}
      {schedType === 'cron' && (
        <TextInput style={s.input} value={cron} onChangeText={setCron} placeholder="Cron (ex: 0 * * * *)" placeholderTextColor={colors.textDim} />
      )}

      <TouchableOpacity style={[s.saveBtn, !name.trim() && s.saveBtnOff]} onPress={save} disabled={loading || !name.trim()}>
        <Text style={s.saveBtnText}>{loading ? '…' : 'Créer la tâche'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function AlertsTab({ onRead }) {
  const [alerts,  setAlerts]  = useState([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { const d = await apiJSON('/api/autonomy/alerts?limit=50'); setAlerts(d.alerts || []); }
    catch (_) {}
    finally { setLoading(false); setRefreshing(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const dismiss = async (id) => {
    try { await apiFetch(`/api/autonomy/alerts/${id}`, { method: 'DELETE' }); load(true); onRead?.(); }
    catch (_) {}
  };

  const readAll = async () => {
    try { await apiFetch('/api/autonomy/alerts/read-all', { method: 'POST' }); load(true); onRead?.(); }
    catch (_) {}
  };

  const clearAll = async () => {
    Alert.alert('Effacer tout', 'Supprimer toutes les alertes ?', [
      { text: 'Annuler', style: 'cancel' },
      { text: 'Effacer', style: 'destructive', onPress: async () => {
        try { await apiFetch('/api/autonomy/alerts', { method: 'DELETE' }); load(true); onRead?.(); }
        catch (_) {}
      }},
    ]);
  };

  return (
    <View style={{ flex: 1 }}>
      <View style={s.actionBar}>
        <TouchableOpacity style={s.smallBtn} onPress={readAll}><Text style={s.smallBtnText}>✓ Tout lire</Text></TouchableOpacity>
        <TouchableOpacity style={[s.smallBtn, { borderColor: colors.red }]} onPress={clearAll}><Text style={[s.smallBtnText, { color: colors.red }]}>✕ Effacer tout</Text></TouchableOpacity>
        <TouchableOpacity style={s.refreshBtnSmall} onPress={() => load(true)}><Text style={s.smallBtnText}>↻</Text></TouchableOpacity>
      </View>
      <ScrollView
        contentContainerStyle={s.list}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(true); }} tintColor={colors.accent} />}
      >
        {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} />
          : alerts.length === 0 ? (
            <View style={s.emptyWrap}>
              <Text style={s.emptyIcon}>🔔</Text>
              <Text style={s.empty}>Aucune alerte système.</Text>
            </View>
          )
          : alerts.map(a => (
          <View key={a.id} style={[s.alertCard, { borderLeftColor: LVL_COLOR[a.level] || colors.border }, !a.read && s.alertUnread]}>
            <View style={s.alertHeader}>
              <Text style={s.alertIcon}>{LVL_ICON[a.level] || 'ℹ️'}</Text>
              <Text style={[s.alertTitle, { color: LVL_COLOR[a.level] || colors.text }]} numberOfLines={1}>{a.title}</Text>
              <Text style={s.alertSrc}>{a.source}</Text>
              <TouchableOpacity onPress={() => dismiss(a.id)} style={s.delBtn}>
                <Text style={s.delText}>✕</Text>
              </TouchableOpacity>
            </View>
            {a.body ? <Text style={s.alertBody} numberOfLines={3}>{a.body}</Text> : null}
            <Text style={s.alertTs}>{new Date(a.ts).toLocaleString('fr-FR')}</Text>
          </View>
        ))}
      </ScrollView>
    </View>
  );
}

function MonitorsTab() {
  const [monitors, setMonitors] = useState([]);
  const [snap,     setSnap]     = useState(null);
  const [loading,  setLoading]  = useState(true);

  const load = useCallback(async () => {
    try {
      const [m, s] = await Promise.all([
        apiJSON('/api/autonomy/monitors'),
        apiJSON('/api/autonomy/snapshot'),
      ]);
      setMonitors(m.monitors || []);
      setSnap(s.error ? null : s);
    } catch (_) {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const bar = (pct, warn = 80, crit = 90) => {
    const color = pct >= crit ? '#f87171' : pct >= warn ? '#fbbf24' : '#34d399';
    return (
      <View style={mb.track}>
        <View style={[mb.fill, { width: `${Math.min(pct, 100)}%`, backgroundColor: color }]} />
      </View>
    );
  };

  return (
    <ScrollView contentContainerStyle={s.list}>
      {loading && <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} />}

      {snap && (
        <View style={s.snapGrid}>
          {[
            { label: 'CPU', val: `${snap.cpu_pct}%`, pct: snap.cpu_pct, sub: null },
            { label: 'RAM', val: `${snap.ram_pct}%`, pct: snap.ram_pct, sub: `${snap.ram_used_gb}GB / ${snap.ram_total_gb}GB` },
            { label: 'Disque', val: `${snap.disk_pct}%`, pct: snap.disk_pct, sub: `${snap.disk_free_gb}GB libres`, warn: 80, crit: 95 },
            { label: 'Processus', val: `${snap.processes}`, pct: null, sub: `↑${snap.net_sent_mb}MB ↓${snap.net_recv_mb}MB` },
          ].map(m => (
            <View key={m.label} style={s.snapCard}>
              <Text style={s.snapLabel}>{m.label}</Text>
              <Text style={s.snapVal}>{m.val}</Text>
              {m.pct !== null && bar(m.pct, m.warn, m.crit)}
              {m.sub && <Text style={s.snapSub}>{m.sub}</Text>}
            </View>
          ))}
        </View>
      )}

      <Text style={s.sectionTitle}>Moniteurs actifs</Text>
      {monitors.length === 0 && !loading && <Text style={s.empty}>Aucun moniteur.</Text>}
      {monitors.map(m => (
        <View key={m.id} style={s.monRow}>
          <View style={[s.monDot, { backgroundColor: m.enabled ? '#34d399' : colors.textDim }]} />
          <View style={{ flex: 1 }}>
            <Text style={s.monName}>{m.name}</Text>
            {m.description ? <Text style={s.monDesc}>{m.description}</Text> : null}
          </View>
          {m.next_run && (
            <Text style={s.monNext}>{new Date(m.next_run).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })}</Text>
          )}
        </View>
      ))}
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 16, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  list: { padding: 12, gap: 10, paddingBottom: 32 },
  addBtn: { borderWidth: 1, borderColor: colors.accent, borderStyle: 'dashed', borderRadius: 10, padding: 14, alignItems: 'center', marginBottom: 4 },
  addBtnText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  card: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 6 },
  cardDisabled: { opacity: 0.5 },
  cardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  cardTitle: { flex: 1, color: colors.text, fontSize: 14, fontWeight: '700' },
  kindBadge: { fontSize: 10, color: colors.accent, backgroundColor: '#001a2e', paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1, borderColor: colors.accent },
  cardCmd: { color: colors.textMuted, fontSize: 12, fontFamily: 'monospace' },
  cardMeta: { flexDirection: 'row', gap: 12 },
  schedText: { color: colors.accent, fontSize: 11, fontWeight: '600' },
  runCount: { color: colors.textDim, fontSize: 11 },
  timeText: { color: colors.textDim, fontSize: 11 },
  actions: { flexDirection: 'row', gap: 8, marginTop: 4 },
  runBtn: { paddingHorizontal: 14, paddingVertical: 7, backgroundColor: '#00d4ff18', borderWidth: 1, borderColor: colors.accent, borderRadius: 8 },
  runBtnText: { color: colors.accent, fontSize: 12, fontWeight: '700' },
  toggleBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1 },
  toggleOn: { borderColor: '#34d399', backgroundColor: '#34d39918' },
  toggleOff: { borderColor: colors.textDim },
  toggleText: { fontSize: 12, fontWeight: '600' },
  toggleOnText: { color: '#34d399' },
  toggleOffText: { color: colors.textDim },
  delBtn: { padding: 8, marginLeft: 'auto' },
  delText: { color: colors.red, fontSize: 14, fontWeight: '700' },
  form: { backgroundColor: colors.bgCardLight, borderRadius: 12, padding: 14, gap: 10, marginBottom: 10 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 12, color: colors.text, fontSize: 13, fontFamily: 'monospace' },
  label: { color: colors.textMuted, fontSize: 12 },
  segRow: { flexDirection: 'row', gap: 6 },
  seg: { flex: 1, padding: 10, borderRadius: 8, borderWidth: 1, borderColor: colors.border, alignItems: 'center' },
  segActive: { borderColor: colors.accent, backgroundColor: colors.accent + '18' },
  segText: { color: colors.textMuted, fontSize: 12 },
  segTextActive: { color: colors.accent, fontWeight: '700' },
  presetRow: { gap: 6 },
  presetBtn: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 8, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg },
  presetText: { color: colors.textMuted, fontSize: 11 },
  saveBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 14, alignItems: 'center' },
  saveBtnOff: { backgroundColor: colors.textDim },
  saveBtnText: { color: colors.bg, fontWeight: '700', fontSize: 14 },
  actionBar: { flexDirection: 'row', gap: 8, padding: 12, backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  smallBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.accent },
  smallBtnText: { color: colors.accent, fontSize: 12 },
  refreshBtnSmall: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  alertCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, borderLeftWidth: 4, gap: 4 },
  alertUnread: { backgroundColor: colors.bgCardLight },
  alertHeader: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  alertIcon: { fontSize: 14 },
  alertTitle: { flex: 1, fontSize: 13, fontWeight: '700' },
  alertSrc: { fontSize: 10, color: colors.textDim, backgroundColor: colors.bgCardLight, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4 },
  alertBody: { color: colors.textMuted, fontSize: 12, lineHeight: 17 },
  alertTs: { color: colors.textDim, fontSize: 11 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 40, fontSize: 14 },
  emptyWrap: { alignItems: 'center', marginTop: 60 },
  emptyIcon: { fontSize: 32, marginBottom: 8 },
  snapGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginBottom: 16 },
  snapCard: { width: '47%', backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4 },
  snapLabel: { color: colors.textMuted, fontSize: 11, letterSpacing: 1 },
  snapVal: { color: colors.accent, fontSize: 22, fontWeight: '800' },
  snapSub: { color: colors.textDim, fontSize: 10 },
  sectionTitle: { color: colors.textMuted, fontSize: 11, letterSpacing: 2, marginBottom: 8, marginTop: 4 },
  monRow: { flexDirection: 'row', alignItems: 'center', backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, marginBottom: 8, borderWidth: 1, borderColor: colors.border, gap: 10 },
  monDot: { width: 10, height: 10, borderRadius: 5 },
  monName: { color: colors.text, fontSize: 13, fontWeight: '600' },
  monDesc: { color: colors.textDim, fontSize: 11 },
  monNext: { color: colors.accent, fontSize: 12 },
});

const mb = StyleSheet.create({
  track: { height: 5, backgroundColor: colors.bgCardLight, borderRadius: 3, overflow: 'hidden', marginVertical: 3 },
  fill: { height: '100%', borderRadius: 3 },
});
