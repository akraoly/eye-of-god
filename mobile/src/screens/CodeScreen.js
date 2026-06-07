import React, { useState, useCallback } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator,
} from 'react-native';
import { apiJSON, apiFetch } from '../utils/api';
import { colors } from '../utils/theme';

export default function CodeScreen() {
  const [tab, setTab] = useState('shell');

  return (
    <View style={s.container}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabContent}>
        {[
          { id: 'shell',   label: '🖥 Shell' },
          { id: 'explore', label: '📂 Explorer' },
          { id: 'git',     label: '🌿 Git' },
        ].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {tab === 'shell'   && <ShellTab />}
      {tab === 'explore' && <ExploreTab />}
      {tab === 'git'     && <GitTab />}
    </View>
  );
}

function ShellTab() {
  const [cmd,     setCmd]    = useState('');
  const [cwd,     setCwd]    = useState('/home/kali/eye-of-god');
  const [output,  setOutput] = useState('');
  const [loading, setLoading] = useState(false);
  const [history, setHistory] = useState([]);

  const PRESETS = [
    'ls -la', 'pwd', 'df -h', 'free -h', 'ps aux | head -20',
    'uname -a', 'ip a', 'netstat -tlnp', 'systemctl status',
    'cat /etc/os-release',
  ];

  const run = useCallback(async (command = cmd) => {
    if (!command.trim()) return;
    setLoading(true);
    const entry = `${cwd} $ ${command}`;
    try {
      const d = await apiJSON('/api/code/run', {
        method: 'POST',
        body: JSON.stringify({ command, cwd }),
      });
      const result = d.stdout || d.stderr || d.error || '(pas de sortie)';
      setOutput(prev => `${prev}\n${entry}\n${result}\n`);
      setHistory(h => [command, ...h.filter(c => c !== command)].slice(0, 20));
      if (d.new_cwd) setCwd(d.new_cwd);
    } catch (e) {
      setOutput(prev => `${prev}\n${entry}\n[ERREUR] ${e.message}\n`);
    } finally {
      setLoading(false);
      setCmd('');
    }
  }, [cmd, cwd]);

  return (
    <View style={{ flex: 1 }}>
      <View style={s.cwdBar}>
        <Text style={s.cwdText}>📂 {cwd}</Text>
      </View>

      {/* Sortie */}
      <ScrollView style={s.termOutput} contentContainerStyle={s.termOutputContent}>
        {output ? (
          <Text style={s.termText}>{output.trim()}</Text>
        ) : (
          <Text style={s.termHint}>Tape une commande ou sélectionne un préset ci-dessous…</Text>
        )}
        {loading && <ActivityIndicator size="small" color={colors.green} style={{ marginTop: 8 }} />}
      </ScrollView>

      {/* Présets */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.presetsBar} contentContainerStyle={s.presetsContent}>
        {PRESETS.map(p => (
          <TouchableOpacity key={p} style={s.presetChip} onPress={() => run(p)} disabled={loading}>
            <Text style={s.presetChipText}>{p}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Historique */}
      {history.length > 0 && (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.histBar} contentContainerStyle={s.presetsContent}>
          {history.slice(0, 8).map(h => (
            <TouchableOpacity key={h} style={[s.presetChip, { borderColor: '#ffd70040', backgroundColor: '#ffd70012' }]} onPress={() => setCmd(h)}>
              <Text style={[s.presetChipText, { color: colors.yellow }]}>↑ {h}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      )}

      {/* Input */}
      <View style={s.cmdRow}>
        <Text style={s.prompt}>$</Text>
        <TextInput
          style={s.cmdInput}
          value={cmd}
          onChangeText={setCmd}
          placeholder="commande…"
          placeholderTextColor={colors.textDim}
          onSubmitEditing={() => run()}
          returnKeyType="send"
          autoCapitalize="none"
          autoCorrect={false}
        />
        <TouchableOpacity style={[s.runBtn, loading && s.runBtnOff]} onPress={() => run()} disabled={loading || !cmd.trim()}>
          <Text style={s.runBtnText}>{loading ? '…' : '▶'}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={s.clearBtn} onPress={() => setOutput('')}>
          <Text style={s.clearBtnText}>⌫</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function ExploreTab() {
  const [path,    setPath]    = useState('/home/kali/eye-of-god');
  const [entries, setEntries] = useState([]);
  const [content, setContent] = useState('');
  const [viewing, setViewing] = useState('');
  const [loading, setLoading] = useState(false);

  const explore = useCallback(async (p = path) => {
    setLoading(true); setContent(''); setViewing('');
    try {
      const d = await apiJSON('/api/code/ls', { method: 'POST', body: JSON.stringify({ path: p }) });
      setEntries(d.entries || []);
      setPath(p);
    } catch (e) {
      setEntries([]);
    } finally { setLoading(false); }
  }, [path]);

  const readFile = async (filePath) => {
    setLoading(true);
    try {
      const d = await apiJSON('/api/code/read', { method: 'POST', body: JSON.stringify({ path: filePath, lines: 100 }) });
      setContent(d.content || '(vide)');
      setViewing(filePath);
    } catch (e) { setContent(`Erreur: ${e.message}`); }
    finally { setLoading(false); }
  };

  const goUp = () => {
    const parent = path.split('/').slice(0, -1).join('/') || '/';
    explore(parent);
  };

  return (
    <View style={{ flex: 1 }}>
      <View style={s.pathBar}>
        <TouchableOpacity onPress={goUp} style={s.upBtn}>
          <Text style={s.upBtnText}>↑</Text>
        </TouchableOpacity>
        <TextInput
          style={s.pathInput}
          value={path}
          onChangeText={setPath}
          onSubmitEditing={() => explore()}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="go"
        />
        <TouchableOpacity style={s.goBtn} onPress={() => explore()}>
          <Text style={s.goBtnText}>Go</Text>
        </TouchableOpacity>
      </View>

      {viewing ? (
        <View style={{ flex: 1 }}>
          <View style={s.fileHeader}>
            <TouchableOpacity onPress={() => { setViewing(''); setContent(''); }}>
              <Text style={s.backBtn}>← Retour</Text>
            </TouchableOpacity>
            <Text style={s.fileName} numberOfLines={1}>{viewing.split('/').pop()}</Text>
          </View>
          <ScrollView style={s.fileContent}>
            <Text style={s.fileText}>{content}</Text>
          </ScrollView>
        </View>
      ) : (
        <ScrollView contentContainerStyle={s.list}>
          {loading ? <ActivityIndicator size="large" color={colors.accent} style={{ marginTop: 20 }} /> :
            entries.length === 0 ? (
              <View style={s.emptyExplore}>
                <TouchableOpacity style={s.exploreLoadBtn} onPress={() => explore()}>
                  <Text style={s.exploreLoadBtnText}>📂 Charger {path}</Text>
                </TouchableOpacity>
              </View>
            ) : entries.map((e, i) => (
              <TouchableOpacity key={i} style={s.entryRow} onPress={() => e.type === 'dir' ? explore(`${path}/${e.name}`) : readFile(`${path}/${e.name}`)}>
                <Text style={s.entryIcon}>{e.type === 'dir' ? '📁' : getFileIcon(e.name)}</Text>
                <View style={{ flex: 1 }}>
                  <Text style={[s.entryName, e.type === 'dir' && s.entryDir]}>{e.name}</Text>
                  {e.size ? <Text style={s.entrySize}>{formatSize(e.size)}</Text> : null}
                </View>
                <Text style={s.entryArrow}>{e.type === 'dir' ? '›' : '›'}</Text>
              </TouchableOpacity>
            ))
          }
        </ScrollView>
      )}
    </View>
  );
}

function GitTab() {
  const [cwd,    setCwd]    = useState('/home/kali/eye-of-god');
  const [output, setOutput] = useState('');
  const [loading, setLoading] = useState(false);

  const gitCmd = async (endpoint, extra = {}) => {
    setLoading(true);
    try {
      const d = await apiJSON(endpoint, { method: 'POST', body: JSON.stringify({ cwd, ...extra }) });
      setOutput(d.output || d.summary || d.diff || d.log || JSON.stringify(d, null, 2));
    } catch (e) { setOutput(`Erreur: ${e.message}`); }
    finally { setLoading(false); }
  };

  const ACTIONS = [
    { label: '📋 Status', fn: () => gitCmd('/api/code/git/status') },
    { label: '📝 Diff',   fn: () => gitCmd('/api/code/git/diff') },
    { label: '📜 Log',    fn: () => gitCmd('/api/code/git/log') },
    { label: '📊 Summary', fn: () => gitCmd('/api/code/git/summary') },
    { label: '⬇️ Pull',   fn: () => gitCmd('/api/code/git/pull') },
  ];

  return (
    <View style={{ flex: 1 }}>
      <View style={s.cwdBar}>
        <Text style={s.cwdLabel}>Repo :</Text>
        <TextInput style={s.cwdInput} value={cwd} onChangeText={setCwd} autoCapitalize="none" autoCorrect={false} />
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.presetsBar} contentContainerStyle={s.presetsContent}>
        {ACTIONS.map(a => (
          <TouchableOpacity key={a.label} style={s.gitBtn} onPress={a.fn} disabled={loading}>
            <Text style={s.gitBtnText}>{a.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <ScrollView style={s.termOutput} contentContainerStyle={s.termOutputContent}>
        {loading ? <ActivityIndicator size="small" color={colors.green} /> :
          output ? <Text style={s.termText}>{output}</Text> :
          <Text style={s.termHint}>Sélectionne une action git…</Text>
        }
      </ScrollView>
    </View>
  );
}

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const map = { py: '🐍', js: '📜', jsx: '⚛️', ts: '📘', tsx: '📘', json: '📋', md: '📝', sh: '🔧', txt: '📄', log: '📊', env: '🔑', sql: '🗃️', yml: '⚙️', yaml: '⚙️' };
  return map[ext] || '📄';
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)}MB`;
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabContent: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 16, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.green },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.green, fontWeight: '700' },
  cwdBar: { flexDirection: 'row', alignItems: 'center', padding: 10, backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, gap: 6 },
  cwdText: { color: colors.textMuted, fontSize: 11, fontFamily: 'monospace', flex: 1 },
  cwdLabel: { color: colors.textDim, fontSize: 11 },
  cwdInput: { flex: 1, color: colors.textMuted, fontSize: 11, fontFamily: 'monospace' },
  termOutput: { flex: 1, backgroundColor: '#00000060', borderRadius: 0 },
  termOutputContent: { padding: 12, paddingBottom: 20 },
  termText: { color: '#7fffb0', fontSize: 12, fontFamily: 'monospace', lineHeight: 18 },
  termHint: { color: colors.textDim, fontSize: 12, fontFamily: 'monospace' },
  presetsBar: { backgroundColor: colors.bgCard, borderTopWidth: 1, borderTopColor: colors.border, flexGrow: 0 },
  presetsContent: { flexDirection: 'row', padding: 8, gap: 6 },
  presetChip: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bg },
  presetChipText: { color: colors.textMuted, fontSize: 11, fontFamily: 'monospace' },
  histBar: { flexGrow: 0, backgroundColor: colors.bgCardLight },
  cmdRow: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    padding: 10, paddingBottom: 16, backgroundColor: colors.bgCard,
    borderTopWidth: 1, borderTopColor: colors.border,
  },
  prompt: { color: colors.green, fontSize: 16, fontFamily: 'monospace', fontWeight: '700' },
  cmdInput: {
    flex: 1, color: colors.green, fontSize: 13, fontFamily: 'monospace',
    backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border,
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 8,
  },
  runBtn: { width: 38, height: 38, backgroundColor: colors.green, borderRadius: 8, justifyContent: 'center', alignItems: 'center' },
  runBtnOff: { backgroundColor: colors.textDim },
  runBtnText: { color: colors.bg, fontSize: 14, fontWeight: '700' },
  clearBtn: { width: 38, height: 38, borderRadius: 8, borderWidth: 1, borderColor: colors.border, justifyContent: 'center', alignItems: 'center' },
  clearBtnText: { color: colors.textMuted, fontSize: 14 },
  pathBar: { flexDirection: 'row', alignItems: 'center', gap: 6, padding: 10, backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  upBtn: { width: 34, height: 34, borderRadius: 8, borderWidth: 1, borderColor: colors.border, justifyContent: 'center', alignItems: 'center' },
  upBtnText: { color: colors.accent, fontSize: 14, fontWeight: '700' },
  pathInput: { flex: 1, color: colors.textMuted, fontSize: 11, fontFamily: 'monospace', borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 8, paddingVertical: 6 },
  goBtn: { paddingHorizontal: 12, paddingVertical: 8, backgroundColor: colors.accent, borderRadius: 8 },
  goBtnText: { color: colors.bg, fontSize: 12, fontWeight: '700' },
  list: { padding: 8, paddingBottom: 32 },
  entryRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, paddingHorizontal: 12, borderBottomWidth: 1, borderBottomColor: colors.border + '60' },
  entryIcon: { fontSize: 18, width: 24 },
  entryName: { color: colors.text, fontSize: 13 },
  entryDir: { color: colors.accent },
  entrySize: { color: colors.textDim, fontSize: 10 },
  entryArrow: { color: colors.textDim, fontSize: 14 },
  emptyExplore: { padding: 20, alignItems: 'center' },
  exploreLoadBtn: { backgroundColor: colors.accent, borderRadius: 10, padding: 14 },
  exploreLoadBtnText: { color: colors.bg, fontWeight: '700' },
  fileHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border },
  backBtn: { color: colors.accent, fontSize: 13 },
  fileName: { flex: 1, color: colors.text, fontSize: 12, fontFamily: 'monospace' },
  fileContent: { flex: 1 },
  fileText: { color: '#7fffb0', fontSize: 11, fontFamily: 'monospace', padding: 12, lineHeight: 17 },
  gitBtn: { paddingHorizontal: 12, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.green + '50', backgroundColor: colors.green + '12' },
  gitBtnText: { color: colors.green, fontSize: 12 },
});
