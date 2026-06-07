import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

const C2_META = {
  sliver:   { icon: '🐍', color: '#10b981', label: 'Sliver C2',  port: 31337 },
  havoc:    { icon: '🔥', color: '#f97316', label: 'Havoc C2',   port: 40056 },
  gophish:  { icon: '🎣', color: '#38bdf8', label: 'Gophish',    port: 3333  },
  evilginx: { icon: '👁',  color: '#a78bfa', label: 'Evilginx',  port: 443   },
};

const LVL_COLORS = {
  1: '#38bdf8',
  2: '#a78bfa',
  3: '#f97316',
  4: '#10b981',
};

const PIPELINE_STAGES = [
  { id: 'fuzz',    icon: '🐛', label: 'Fuzzing',  endpoint: '/api/offensive/pipeline/fuzz' },
  { id: 'crash',   icon: '💢', label: 'Crash',    endpoint: '/api/offensive/pipeline/analyse-crash' },
  { id: 'reverse', icon: '🔬', label: 'Reverse',  endpoint: '/api/offensive/pipeline/reverse' },
  { id: 'exploit', icon: '💥', label: 'Exploit',  endpoint: '/api/offensive/pipeline/exploit-template' },
];

export default function OffensiveScreen() {
  const [tab,      setTab]      = useState('levels');
  const [levels,   setLevels]   = useState({});
  const [c2Status, setC2Status] = useState({});
  const [target,   setTarget]   = useState('');
  const [binary,   setBinary]   = useState('');
  const [terminal, setTerminal] = useState('L\'Œil de Dieu — Terminal offensif\nSélectionne un niveau ou lance le pipeline...\n');
  const [running,  setRunning]  = useState(false);
  const [activeLevel, setActive] = useState(null);
  const [c2Loading, setC2Loading] = useState({});
  const termRef = useRef(null);

  useEffect(() => {
    apiJSON('/api/offensive/levels').then(d => setLevels(d.levels || {})).catch(() => {});
    refreshC2();
  }, []);

  const refreshC2 = useCallback(async () => {
    try {
      const d = await apiJSON('/api/c2/');
      const map = {};
      (d.c2s || []).forEach(s => { map[s.name] = s; });
      setC2Status(map);
    } catch (_) {}
  }, []);

  useEffect(() => {
    const t = setInterval(refreshC2, 5000);
    return () => clearInterval(t);
  }, [refreshC2]);

  const log = (msg) => setTerminal(prev => prev + '\n' + msg);

  const runTool = async (level, tool, params = {}) => {
    setRunning(true);
    log(`\n[+] Lancement ${tool} (N${level})…`);
    try {
      const p = { ...params };
      if (target) p.target = target;
      if (binary) p.binary = binary;
      const d = await apiJSON('/api/offensive/run/tool', {
        method: 'POST',
        body: JSON.stringify({ level, tool, params: p }),
      });
      log(d.output || d.error || '(pas de sortie)');
      if (d.next_step) log(`\n[→] ${d.next_step}`);
    } catch (e) { log(`[!] ${e.message}`); }
    finally { setRunning(false); }
  };

  const runPipeline = async (stage) => {
    if (!binary && (stage !== 'fuzz')) { log('[!] Renseigne le binaire.'); return; }
    setRunning(true);
    log(`\n[+] Pipeline — stage: ${stage}${binary ? ` sur ${binary}` : ''}`);
    const ep = PIPELINE_STAGES.find(p => p.id === stage)?.endpoint;
    try {
      const body = stage === 'fuzz'
        ? { binary: binary || './target', corpus: '/tmp/corpus', output: '/tmp/fuzz_out', timeout: 20 }
        : stage === 'crash'
        ? { binary, crash: '/tmp/fuzz_out/default/crashes/id:000000' }
        : stage === 'exploit'
        ? { binary, offset: 0, lhost: target || '127.0.0.1', lport: 4444 }
        : { binary };
      const d = await apiJSON(ep, { method: 'POST', body: JSON.stringify(body) });
      log(d.output || d.gdb_trace || d.main_disasm || d.exploit_template || d.error || JSON.stringify(d, null, 2));
      if (d.next_step) log(`\n[→] ${d.next_step}`);
    } catch (e) { log(`[!] ${e.message}`); }
    finally { setRunning(false); }
  };

  const startC2 = async (name) => {
    setC2Loading(prev => ({ ...prev, [name]: true }));
    try {
      const d = await apiJSON('/api/c2/start', { method: 'POST', body: JSON.stringify({ name }) });
      log(`\n[C2] ${name.toUpperCase()}: ${d.message || d.error}`);
      refreshC2();
    } catch (e) { log(`[!] ${e.message}`); }
    setC2Loading(prev => ({ ...prev, [name]: false }));
  };

  const stopC2 = async (name) => {
    setC2Loading(prev => ({ ...prev, [name]: true }));
    try {
      const d = await apiJSON(`/api/c2/stop/${name}`, { method: 'POST' });
      log(`\n[C2] ${name.toUpperCase()}: ${d.message || d.error}`);
      refreshC2();
    } catch (e) { log(`[!] ${e.message}`); }
    setC2Loading(prev => ({ ...prev, [name]: false }));
  };

  return (
    <View style={s.container}>
      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {[
          { id: 'levels',   label: '⚔️ Niveaux' },
          { id: 'c2',       label: '🧠 C2' },
          { id: 'pipeline', label: '⚡ Pipeline' },
          { id: 'terminal', label: '🖥 Terminal' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Inputs globaux */}
      <View style={s.globalInputs}>
        <TextInput style={s.inputSmall} value={target} onChangeText={setTarget} placeholder="Cible (IP/domaine)" placeholderTextColor={colors.textDim} />
        <TextInput style={s.inputSmall} value={binary} onChangeText={setBinary} placeholder="Binaire (./target)" placeholderTextColor={colors.textDim} />
      </View>

      <ScrollView contentContainerStyle={s.list}>

        {/* ── NIVEAUX ── */}
        {tab === 'levels' && (
          <>
            {[1, 2, 3, 4].map(n => {
              const lvl = levels[n];
              if (!lvl) return <ActivityIndicator key={n} size="small" color={colors.accent} />;
              const col = LVL_COLORS[n];
              const isActive = activeLevel === n;
              return (
                <TouchableOpacity key={n} style={[s.lvlCard, { borderColor: isActive ? col : colors.border, backgroundColor: isActive ? col + '18' : colors.bgCard }]}
                  onPress={() => setActive(isActive ? null : n)}>
                  <View style={s.lvlHeader}>
                    <Text style={s.lvlIcon}>{lvl.icon}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[s.lvlName, { color: col }]}>{lvl.name}</Text>
                      <Text style={s.lvlImpact}>{lvl.impact}</Text>
                    </View>
                    <View style={[s.lvlBadge, { backgroundColor: col + '30', borderColor: col + '60' }]}>
                      <Text style={[s.lvlBadgeText, { color: col }]}>N{n}</Text>
                    </View>
                  </View>
                  {isActive && (
                    <View style={s.toolsWrap}>
                      <Text style={s.toolsLabel}>OUTILS ({lvl.tools_count}) — tap pour lancer</Text>
                      <View style={s.toolsList}>
                        {(lvl.tools || []).map(t => (
                          <TouchableOpacity key={t.name} style={[s.toolChip, { borderColor: col + '50', backgroundColor: col + '12' }]}
                            onPress={() => { setTab('terminal'); runTool(n, t.name); }} disabled={running}>
                            <Text style={[s.toolChipText, { color: col }]}>{t.name}</Text>
                          </TouchableOpacity>
                        ))}
                      </View>
                    </View>
                  )}
                </TouchableOpacity>
              );
            })}
          </>
        )}

        {/* ── C2 ── */}
        {tab === 'c2' && (
          <>
            <View style={s.c2Header}>
              <Text style={s.c2Title}>🧠 C2 FRAMEWORKS</Text>
              <Text style={s.c2Sub}>Contrôle en temps réel</Text>
            </View>
            {Object.entries(C2_META).map(([name, meta]) => {
              const status = c2Status[name] || {};
              const isRunning = status.running;
              const isLoading = c2Loading[name];
              return (
                <View key={name} style={[s.c2Card, { borderColor: isRunning ? meta.color : colors.border, backgroundColor: isRunning ? meta.color + '12' : colors.bgCard }]}>
                  <View style={s.c2CardTop}>
                    <Text style={s.c2Icon}>{meta.icon}</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[s.c2Name, { color: meta.color }]}>{meta.label}</Text>
                      <Text style={s.c2Port}>{isRunning ? `PID ${status.pid} · port ${meta.port}` : `port ${meta.port}`}</Text>
                    </View>
                    <View style={[s.c2Dot, { backgroundColor: isRunning ? '#10b981' : colors.textDim }]} />
                  </View>
                  <View style={s.c2Actions}>
                    {!isRunning ? (
                      <TouchableOpacity style={[s.c2Btn, { borderColor: meta.color }]} onPress={() => startC2(name)} disabled={isLoading}>
                        <Text style={[s.c2BtnText, { color: meta.color }]}>{isLoading ? '…' : '▶ Start'}</Text>
                      </TouchableOpacity>
                    ) : (
                      <TouchableOpacity style={[s.c2Btn, { borderColor: colors.red }]} onPress={() => stopC2(name)} disabled={isLoading}>
                        <Text style={[s.c2BtnText, { color: colors.red }]}>{isLoading ? '…' : '■ Stop'}</Text>
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity style={s.c2LogBtn} onPress={() => { setTab('terminal'); }}>
                      <Text style={s.c2LogBtnText}>📋 Logs</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              );
            })}
          </>
        )}

        {/* ── PIPELINE ── */}
        {tab === 'pipeline' && (
          <>
            <View style={s.pipeHeader}>
              <Text style={s.pipeTitle}>⚡ PIPELINE EXPLOITATION</Text>
              <Text style={s.pipeSub}>Fuzzing → Crash → Reverse → Exploit</Text>
            </View>
            {PIPELINE_STAGES.map((stage, i) => (
              <View key={stage.id} style={s.pipeStageWrap}>
                <TouchableOpacity
                  style={[s.pipeStage, running && s.pipeStageOff]}
                  onPress={() => { setTab('terminal'); runPipeline(stage.id); }}
                  disabled={running}
                >
                  <Text style={s.pipeIcon}>{stage.icon}</Text>
                  <View style={{ flex: 1 }}>
                    <Text style={s.pipeLabel}>{stage.label}</Text>
                    <Text style={s.pipeDesc}>{stage.endpoint.split('/').pop()}</Text>
                  </View>
                  <Text style={s.pipeArrow}>▶</Text>
                </TouchableOpacity>
                {i < PIPELINE_STAGES.length - 1 && (
                  <View style={s.pipeConnector}>
                    <Text style={s.pipeConnectorText}>↓</Text>
                  </View>
                )}
              </View>
            ))}
            {!binary && (
              <View style={s.pipeHint}>
                <Text style={s.pipeHintText}>⚠️ Renseigne le chemin du binaire dans les champs ci-dessus.</Text>
              </View>
            )}
          </>
        )}

        {/* ── TERMINAL ── */}
        {tab === 'terminal' && (
          <View style={s.termWrap}>
            <View style={s.termHeader}>
              <Text style={s.termLabel}>TERMINAL</Text>
              {running && <Text style={s.termRunning}>● EN COURS</Text>}
              <TouchableOpacity style={s.clearBtn} onPress={() => setTerminal('Terminal effacé.\n')}>
                <Text style={s.clearBtnText}>Effacer</Text>
              </TouchableOpacity>
            </View>
            <ScrollView style={s.termScroll} ref={termRef} onContentSizeChange={() => termRef.current?.scrollToEnd({ animated: true })}>
              <Text style={s.termText}>{terminal}</Text>
            </ScrollView>
          </View>
        )}
      </ScrollView>
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 14, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: '#f97316' },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: '#f97316', fontWeight: '700' },
  globalInputs: {
    flexDirection: 'row', gap: 8, padding: 10,
    backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  inputSmall: {
    flex: 1, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border,
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8,
    color: colors.text, fontSize: 12, fontFamily: 'monospace',
  },
  list: { padding: 12, gap: 10, paddingBottom: 32 },
  // Levels
  lvlCard: { borderRadius: 12, padding: 14, borderWidth: 1, gap: 10 },
  lvlHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  lvlIcon: { fontSize: 22 },
  lvlName: { fontSize: 14, fontWeight: '700', letterSpacing: 0.5 },
  lvlImpact: { color: colors.textDim, fontSize: 11, marginTop: 2 },
  lvlBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, borderWidth: 1 },
  lvlBadgeText: { fontSize: 11, fontWeight: '700' },
  toolsWrap: { gap: 6 },
  toolsLabel: { color: colors.textDim, fontSize: 10, letterSpacing: 1, textTransform: 'uppercase' },
  toolsList: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  toolChip: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 10, borderWidth: 1 },
  toolChipText: { fontSize: 11, fontFamily: 'monospace', fontWeight: '600' },
  // C2
  c2Header: { padding: 12, backgroundColor: '#6d28d918', borderRadius: 12, borderWidth: 1, borderColor: '#6d28d940', marginBottom: 4 },
  c2Title: { color: '#a78bfa', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  c2Sub: { color: colors.textDim, fontSize: 11, marginTop: 2 },
  c2Card: { borderRadius: 12, padding: 14, borderWidth: 1, gap: 10 },
  c2CardTop: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  c2Icon: { fontSize: 24 },
  c2Name: { fontSize: 13, fontWeight: '700' },
  c2Port: { color: colors.textDim, fontSize: 11 },
  c2Dot: { width: 10, height: 10, borderRadius: 5 },
  c2Actions: { flexDirection: 'row', gap: 8 },
  c2Btn: { flex: 1, paddingVertical: 8, borderRadius: 8, borderWidth: 1, alignItems: 'center' },
  c2BtnText: { fontSize: 12, fontWeight: '700', fontFamily: 'monospace' },
  c2LogBtn: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  c2LogBtnText: { color: colors.textMuted, fontSize: 12 },
  // Pipeline
  pipeHeader: { backgroundColor: '#f9731618', borderRadius: 12, padding: 12, borderWidth: 1, borderColor: '#f9731630' },
  pipeTitle: { color: '#f97316', fontSize: 13, fontWeight: '700', letterSpacing: 2 },
  pipeSub: { color: colors.textDim, fontSize: 11, marginTop: 2 },
  pipeStageWrap: { gap: 0 },
  pipeStage: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    backgroundColor: '#f9731618', borderRadius: 12, padding: 14,
    borderWidth: 1, borderColor: '#f9731640',
  },
  pipeStageOff: { opacity: 0.4 },
  pipeIcon: { fontSize: 24 },
  pipeLabel: { color: '#f97316', fontSize: 14, fontWeight: '700' },
  pipeDesc: { color: colors.textDim, fontSize: 11, fontFamily: 'monospace' },
  pipeArrow: { color: '#f97316', fontSize: 16 },
  pipeConnector: { alignItems: 'center', paddingVertical: 4 },
  pipeConnectorText: { color: '#f9731650', fontSize: 18 },
  pipeHint: { backgroundColor: '#ffd70018', borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#ffd70040' },
  pipeHintText: { color: colors.yellow, fontSize: 12 },
  // Terminal
  termWrap: { gap: 8 },
  termHeader: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  termLabel: { color: colors.textDim, fontSize: 11, letterSpacing: 2, fontWeight: '700' },
  termRunning: { color: '#f97316', fontSize: 11 },
  clearBtn: { marginLeft: 'auto', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6, borderWidth: 1, borderColor: colors.border },
  clearBtnText: { color: colors.textMuted, fontSize: 11 },
  termScroll: { backgroundColor: '#00000080', borderRadius: 10, borderWidth: 1, borderColor: '#ffffff10', maxHeight: 400 },
  termText: { color: '#7fffb0', fontSize: 12, fontFamily: 'monospace', padding: 12, lineHeight: 18 },
});
