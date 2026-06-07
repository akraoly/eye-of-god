import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, ScrollView, TouchableOpacity,
  TextInput, ActivityIndicator, Alert, FlatList,
} from 'react-native';
import { apiJSON, apiFetch } from '../../utils/api';
import { colors } from '../../utils/theme';

const PROTO_COLORS = {
  HTTP:    '#34d399',
  HTTPS:   '#34d399',
  DNS:     '#60a5fa',
  SMB:     '#f87171',
  FTP:     '#fbbf24',
  TELNET:  '#f97316',
  SMTP:    '#a78bfa',
  POP3:    '#a78bfa',
  IMAP:    '#a78bfa',
  ARP:     '#94a3b8',
  ICMP:    '#94a3b8',
  TCP:     '#64748b',
  UDP:     '#64748b',
};

const FILTER_PRESETS = [
  { label: 'HTTP', value: 'tcp port 80 or tcp port 443' },
  { label: 'DNS',  value: 'udp port 53' },
  { label: 'FTP',  value: 'tcp port 21' },
  { label: 'SMB',  value: 'tcp port 445 or tcp port 139' },
  { label: 'Telnet', value: 'tcp port 23' },
  { label: 'All',  value: '' },
];

const ANALYSIS_TABS = [
  { id: 'packets', label: '📦 Paquets' },
  { id: 'creds',   label: '🔑 Credentials' },
  { id: 'dns',     label: '🌐 DNS' },
  { id: 'http',    label: '🌍 HTTP' },
];

export default function NetworkSnifferScreen() {
  const [tab,         setTab]         = useState('capture');
  const [interfaces,  setInterfaces]  = useState([]);
  const [iface,       setIface]       = useState('');
  const [filter,      setFilter]      = useState('');
  const [maxPkts,     setMaxPkts]     = useState('500');
  const [capture,     setCapture]     = useState(null);   // {capture_id, status, ...}
  const [captures,    setCaptures]    = useState([]);
  const [selectedCap, setSelectedCap] = useState(null);
  const [analysisTab, setAnalysisTab] = useState('packets');
  const [packets,     setPackets]     = useState([]);
  const [creds,       setCreds]       = useState([]);
  const [dnsQ,        setDnsQ]        = useState([]);
  const [httpR,       setHttpR]       = useState([]);
  const [stats,       setStats]       = useState(null);
  const [loading,     setLoading]     = useState(false);
  const [analysing,   setAnalysing]   = useState(false);
  const pollRef = useRef(null);

  // Load interfaces on mount
  useEffect(() => {
    apiJSON('/api/capture/interfaces')
      .then(d => {
        const ifaces = d.interfaces || [];
        setInterfaces(ifaces);
        const eth = ifaces.find(i => !i.loopback && i.up);
        if (eth) setIface(eth.name);
      })
      .catch(() => {});
    loadCaptures();
  }, []);

  // Poll stats while a capture is running
  useEffect(() => {
    if (capture?.capture_id && capture.status === 'running') {
      pollRef.current = setInterval(async () => {
        try {
          const d = await apiJSON(`/api/capture/${capture.capture_id}/stats`);
          setStats(d);
          if (d.status !== 'running') {
            clearInterval(pollRef.current);
            setCapture(prev => ({ ...prev, status: d.status }));
          }
        } catch (_) {}
      }, 2000);
    }
    return () => clearInterval(pollRef.current);
  }, [capture?.capture_id, capture?.status]);

  const loadCaptures = useCallback(async () => {
    try {
      const d = await apiJSON('/api/capture/list');
      setCaptures(d.captures || []);
    } catch (_) {}
  }, []);

  const startCapture = async () => {
    if (!iface) { Alert.alert('Erreur', 'Sélectionne une interface.'); return; }
    setLoading(true);
    try {
      const d = await apiJSON('/api/capture/start', {
        method: 'POST',
        body: JSON.stringify({ interface: iface, bpf_filter: filter, max_packets: Number(maxPkts) || 500 }),
      });
      setCapture(d);
      setStats(null);
      loadCaptures();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  const stopCapture = async () => {
    if (!capture?.capture_id) return;
    setLoading(true);
    try {
      const d = await apiJSON(`/api/capture/stop/${capture.capture_id}`, { method: 'POST' });
      setCapture(prev => ({ ...prev, ...d }));
      clearInterval(pollRef.current);
      loadCaptures();
    } catch (e) { Alert.alert('Erreur', e.message); }
    finally { setLoading(false); }
  };

  const analyseCapture = async (capId) => {
    setSelectedCap(capId);
    setAnalysing(true);
    setPackets([]); setCreds([]); setDnsQ([]); setHttpR([]);
    try {
      const [allR, credsR, dnsR, httpR_] = await Promise.all([
        apiJSON(`/api/capture/${capId}/analyze?type=all`).catch(() => ({ packets: [] })),
        apiJSON(`/api/capture/${capId}/credentials`).catch(() => []),
        apiJSON(`/api/capture/${capId}/dns`).catch(() => []),
        apiJSON(`/api/capture/${capId}/analyze?type=http`).catch(() => ({ requests: [] })),
      ]);
      setPackets(allR.packets || allR.summary || []);
      setCreds(Array.isArray(credsR) ? credsR : credsR.credentials || []);
      setDnsQ(Array.isArray(dnsR) ? dnsR : dnsR.queries || []);
      setHttpR(httpR_?.requests || []);
      setTab('analyse');
    } catch (e) { Alert.alert('Erreur analyse', e.message); }
    finally { setAnalysing(false); }
  };

  const protoColor = (proto) => PROTO_COLORS[proto?.toUpperCase()] || colors.textDim;

  return (
    <View style={s.root}>
      {/* Top tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabRow}>
        {[{ id: 'capture', label: '📡 Capture' }, { id: 'captures', label: '📂 Historique' }, { id: 'analyse', label: '🔬 Analyse' }].map(t => (
          <TouchableOpacity key={t.id} style={[s.tab, tab === t.id && s.tabActive]} onPress={() => setTab(t.id)}>
            <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* ── CAPTURE TAB ── */}
      {tab === 'capture' && (
        <ScrollView contentContainerStyle={s.pad}>

          {/* Interface selector */}
          <Text style={s.label}>Interface réseau</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
            {interfaces.map(i => (
              <TouchableOpacity key={i.name} style={[s.chip, iface === i.name && s.chipActive]} onPress={() => setIface(i.name)}>
                <Text style={[s.chipText, iface === i.name && s.chipTextActive]}>
                  {i.loopback ? '🔄' : '🌐'} {i.name}
                </Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* BPF filter presets */}
          <Text style={s.label}>Filtre BPF</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chipRow}>
            {FILTER_PRESETS.map(f => (
              <TouchableOpacity key={f.label} style={[s.chip, filter === f.value && s.chipActive]} onPress={() => setFilter(f.value)}>
                <Text style={[s.chipText, filter === f.value && s.chipTextActive]}>{f.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
          <TextInput
            style={s.input}
            value={filter}
            onChangeText={setFilter}
            placeholder="ex: tcp port 80 or udp port 53"
            placeholderTextColor={colors.textDim}
          />

          {/* Max packets */}
          <Text style={s.label}>Max paquets</Text>
          <View style={s.chipRow}>
            {['100', '500', '1000', '5000'].map(n => (
              <TouchableOpacity key={n} style={[s.chip, maxPkts === n && s.chipActive]} onPress={() => setMaxPkts(n)}>
                <Text style={[s.chipText, maxPkts === n && s.chipTextActive]}>{n}</Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Start/Stop */}
          {!capture || capture.status !== 'running' ? (
            <TouchableOpacity style={[s.btn, s.btnGreen]} onPress={startCapture} disabled={loading}>
              {loading ? <ActivityIndicator color={colors.bg} size="small" />
                : <Text style={s.btnText}>▶ Démarrer capture</Text>}
            </TouchableOpacity>
          ) : (
            <TouchableOpacity style={[s.btn, s.btnRed]} onPress={stopCapture} disabled={loading}>
              {loading ? <ActivityIndicator color={colors.bg} size="small" />
                : <Text style={s.btnText}>■ Arrêter</Text>}
            </TouchableOpacity>
          )}

          {/* Live stats */}
          {capture && (
            <View style={s.statsBox}>
              <Text style={s.statsTitle}>CAPTURE EN COURS</Text>
              <View style={s.statsRow}>
                <StatItem label="ID" value={capture.capture_id?.slice(0, 8)} />
                <StatItem label="Interface" value={capture.interface} />
                <StatItem label="Statut" value={capture.status} color={capture.status === 'running' ? colors.green : colors.textMuted} />
                <StatItem label="Paquets" value={stats?.packet_count ?? '—'} color={colors.accent} />
              </View>
              {capture.status === 'stopped' && (
                <TouchableOpacity style={[s.btn, { marginTop: 10 }]} onPress={() => analyseCapture(capture.capture_id)}>
                  <Text style={s.btnText}>🔬 Analyser cette capture</Text>
                </TouchableOpacity>
              )}
            </View>
          )}
        </ScrollView>
      )}

      {/* ── HISTORIQUE TAB ── */}
      {tab === 'captures' && (
        <ScrollView contentContainerStyle={s.pad}>
          <TouchableOpacity style={s.refreshBtn} onPress={loadCaptures}>
            <Text style={s.refreshBtnText}>↻ Actualiser</Text>
          </TouchableOpacity>
          {captures.length === 0
            ? <Text style={s.empty}>Aucune capture.</Text>
            : captures.map(c => (
              <View key={c.capture_id} style={s.capCard}>
                <View style={s.capHeader}>
                  <Text style={s.capId}>{c.capture_id.slice(0, 12)}…</Text>
                  <View style={[s.statusDot, { backgroundColor: c.status === 'running' ? colors.green : colors.textDim }]} />
                  <Text style={s.capStatus}>{c.status}</Text>
                </View>
                <Text style={s.capMeta}>
                  {c.interface} · {c.packet_count ?? 0} paquets · {c.creds_found ?? 0} creds
                </Text>
                {c.bpf_filter ? <Text style={s.capFilter}>{c.bpf_filter}</Text> : null}
                <Text style={s.capTs}>{new Date(c.started_at).toLocaleString('fr-FR')}</Text>
                <TouchableOpacity
                  style={[s.btn, { marginTop: 8 }]}
                  onPress={() => analyseCapture(c.capture_id)}
                  disabled={analysing}
                >
                  <Text style={s.btnText}>{analysing ? '…' : '🔬 Analyser'}</Text>
                </TouchableOpacity>
              </View>
            ))
          }
        </ScrollView>
      )}

      {/* ── ANALYSE TAB ── */}
      {tab === 'analyse' && (
        <View style={{ flex: 1 }}>
          {analysing && (
            <View style={s.analysing}>
              <ActivityIndicator size="large" color={colors.accent} />
              <Text style={s.analysingText}>Analyse en cours…</Text>
            </View>
          )}

          {/* Creds alert banner */}
          {creds.length > 0 && (
            <View style={s.credsBanner}>
              <Text style={s.credsBannerText}>🔑 {creds.length} credential{creds.length > 1 ? 's' : ''} extrait{creds.length > 1 ? 's' : ''} !</Text>
            </View>
          )}

          {/* Analysis sub-tabs */}
          <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabBar} contentContainerStyle={s.tabRow}>
            {ANALYSIS_TABS.map(t => (
              <TouchableOpacity key={t.id} style={[s.tab, analysisTab === t.id && s.tabActive]} onPress={() => setAnalysisTab(t.id)}>
                <Text style={[s.tabText, analysisTab === t.id && s.tabTextActive]}>{t.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>

          {/* Packets */}
          {analysisTab === 'packets' && (
            <FlatList
              data={packets.slice(0, 200)}
              keyExtractor={(_, i) => String(i)}
              contentContainerStyle={{ padding: 8, paddingBottom: 32 }}
              ListEmptyComponent={<Text style={s.empty}>Aucun paquet extrait.</Text>}
              renderItem={({ item }) => {
                const proto = item.protocol || item.proto || 'TCP';
                const col = protoColor(proto);
                return (
                  <View style={s.pktRow}>
                    <View style={[s.protoBadge, { backgroundColor: col + '20', borderColor: col + '60' }]}>
                      <Text style={[s.protoText, { color: col }]}>{proto}</Text>
                    </View>
                    <Text style={s.pktSrc} numberOfLines={1}>{item.src || item.source || '—'}</Text>
                    <Text style={s.pktArrow}>→</Text>
                    <Text style={s.pktDst} numberOfLines={1}>{item.dst || item.dest || '—'}</Text>
                    {item.info && <Text style={s.pktInfo} numberOfLines={1}>{item.info}</Text>}
                  </View>
                );
              }}
            />
          )}

          {/* Credentials */}
          {analysisTab === 'creds' && (
            <ScrollView contentContainerStyle={s.pad}>
              {creds.length === 0
                ? <View style={s.emptyWrap}><Text style={s.emptyIcon}>🔑</Text><Text style={s.empty}>Aucune credential en clair.</Text></View>
                : creds.map((c, i) => (
                  <View key={i} style={s.credCard}>
                    <View style={s.credHeader}>
                      <Text style={s.credProto}>{c.protocol || '?'}</Text>
                      <Text style={s.credSrc}>{c.source_ip} → {c.dest_ip}</Text>
                    </View>
                    {c.username && <Text style={s.credField}>👤 {c.username}</Text>}
                    {c.password && <Text style={s.credField}>🔑 {c.password}</Text>}
                    {c.timestamp && <Text style={s.credTs}>{c.timestamp}</Text>}
                  </View>
                ))
              }
            </ScrollView>
          )}

          {/* DNS */}
          {analysisTab === 'dns' && (
            <FlatList
              data={dnsQ}
              keyExtractor={(_, i) => String(i)}
              contentContainerStyle={{ padding: 8, paddingBottom: 32 }}
              ListEmptyComponent={<Text style={s.empty}>Aucune requête DNS.</Text>}
              renderItem={({ item }) => (
                <View style={s.dnsRow}>
                  <Text style={s.dnsType}>{item.type || 'A'}</Text>
                  <Text style={s.dnsQuery} numberOfLines={1}>{item.query || item.name || '—'}</Text>
                  <Text style={s.dnsResp} numberOfLines={1}>{item.response || item.answer || ''}</Text>
                </View>
              )}
            />
          )}

          {/* HTTP */}
          {analysisTab === 'http' && (
            <FlatList
              data={httpR}
              keyExtractor={(_, i) => String(i)}
              contentContainerStyle={{ padding: 8, paddingBottom: 32 }}
              ListEmptyComponent={<Text style={s.empty}>Aucune requête HTTP.</Text>}
              renderItem={({ item }) => (
                <View style={s.httpRow}>
                  <View style={[s.methodBadge, { backgroundColor: item.method === 'POST' ? '#f8717120' : '#34d39920' }]}>
                    <Text style={[s.methodText, { color: item.method === 'POST' ? '#f87171' : '#34d399' }]}>
                      {item.method || 'GET'}
                    </Text>
                  </View>
                  <Text style={s.httpUrl} numberOfLines={2}>{item.url || item.uri || '—'}</Text>
                  {item.host && <Text style={s.httpHost}>{item.host}</Text>}
                </View>
              )}
            />
          )}
        </View>
      )}
    </View>
  );
}

function StatItem({ label, value, color }) {
  return (
    <View style={s.statItem}>
      <Text style={s.statLabel}>{label}</Text>
      <Text style={[s.statVal, color ? { color } : null]}>{value ?? '—'}</Text>
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  tabBar: { backgroundColor: colors.bgCard, borderBottomWidth: 1, borderBottomColor: colors.border, flexGrow: 0 },
  tabRow: { flexDirection: 'row', paddingHorizontal: 8, paddingVertical: 4 },
  tab: { paddingHorizontal: 16, paddingVertical: 12 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: colors.accent },
  tabText: { color: colors.textMuted, fontSize: 13 },
  tabTextActive: { color: colors.accent, fontWeight: '700' },
  pad: { padding: 14, gap: 10, paddingBottom: 40 },
  label: { color: colors.textMuted, fontSize: 11, letterSpacing: 1, textTransform: 'uppercase', marginBottom: 4 },
  chipRow: { flexDirection: 'row', gap: 6, marginBottom: 8 },
  chip: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bgCard },
  chipActive: { borderColor: colors.accent, backgroundColor: colors.accent + '20' },
  chipText: { color: colors.textMuted, fontSize: 12 },
  chipTextActive: { color: colors.accent, fontWeight: '700' },
  input: {
    backgroundColor: colors.bgCard, borderWidth: 1, borderColor: colors.border,
    borderRadius: 10, padding: 12, color: colors.text, fontSize: 12, fontFamily: 'monospace',
  },
  btn: { backgroundColor: colors.accent + '20', borderWidth: 1, borderColor: colors.accent, borderRadius: 10, padding: 14, alignItems: 'center' },
  btnGreen: { borderColor: colors.green, backgroundColor: colors.green + '20' },
  btnRed: { borderColor: colors.red, backgroundColor: colors.red + '20' },
  btnText: { color: colors.text, fontWeight: '700', fontSize: 13 },
  statsBox: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 8, marginTop: 4 },
  statsTitle: { color: colors.accent, fontSize: 11, fontWeight: '700', letterSpacing: 2 },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  statItem: { alignItems: 'center' },
  statLabel: { color: colors.textDim, fontSize: 10, letterSpacing: 1 },
  statVal: { color: colors.text, fontSize: 16, fontWeight: '700' },
  refreshBtn: { alignSelf: 'flex-end', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8, borderWidth: 1, borderColor: colors.border, marginBottom: 8 },
  refreshBtnText: { color: colors.textMuted, fontSize: 12 },
  capCard: { backgroundColor: colors.bgCard, borderRadius: 12, padding: 14, borderWidth: 1, borderColor: colors.border, gap: 4, marginBottom: 10 },
  capHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  capId: { color: colors.accent, fontSize: 12, fontFamily: 'monospace', flex: 1 },
  statusDot: { width: 8, height: 8, borderRadius: 4 },
  capStatus: { color: colors.textMuted, fontSize: 11 },
  capMeta: { color: colors.textMuted, fontSize: 12 },
  capFilter: { color: colors.textDim, fontSize: 11, fontFamily: 'monospace' },
  capTs: { color: colors.textDim, fontSize: 11 },
  analysing: { alignItems: 'center', padding: 24, gap: 12 },
  analysingText: { color: colors.textMuted, fontSize: 13 },
  credsBanner: { backgroundColor: '#fbbf2420', borderBottomWidth: 1, borderBottomColor: '#fbbf2440', padding: 12 },
  credsBannerText: { color: '#fbbf24', fontSize: 13, fontWeight: '700', textAlign: 'center' },
  pktRow: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: colors.border + '30' },
  protoBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, borderWidth: 1, minWidth: 48, alignItems: 'center' },
  protoText: { fontSize: 10, fontWeight: '700', fontFamily: 'monospace' },
  pktSrc: { color: colors.textMuted, fontSize: 11, flex: 1, fontFamily: 'monospace' },
  pktArrow: { color: colors.textDim, fontSize: 11 },
  pktDst: { color: colors.textMuted, fontSize: 11, flex: 1, fontFamily: 'monospace' },
  pktInfo: { color: colors.textDim, fontSize: 10, flex: 1 },
  credCard: { backgroundColor: colors.bgCard, borderRadius: 10, padding: 12, borderWidth: 1, borderLeftWidth: 3, borderColor: colors.border, borderLeftColor: '#fbbf24', gap: 4, marginBottom: 8 },
  credHeader: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  credProto: { color: '#fbbf24', fontSize: 11, fontWeight: '700', fontFamily: 'monospace' },
  credSrc: { color: colors.textDim, fontSize: 11, fontFamily: 'monospace' },
  credField: { color: colors.text, fontSize: 13, fontFamily: 'monospace' },
  credTs: { color: colors.textDim, fontSize: 10 },
  dnsRow: { flexDirection: 'row', gap: 8, alignItems: 'center', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border + '30' },
  dnsType: { color: '#60a5fa', fontSize: 10, fontWeight: '700', width: 28, fontFamily: 'monospace' },
  dnsQuery: { color: colors.text, fontSize: 12, fontFamily: 'monospace', flex: 1 },
  dnsResp: { color: colors.textDim, fontSize: 11, fontFamily: 'monospace', flex: 1 },
  httpRow: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.border + '30' },
  methodBadge: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, minWidth: 40, alignItems: 'center' },
  methodText: { fontSize: 10, fontWeight: '700', fontFamily: 'monospace' },
  httpUrl: { color: colors.text, fontSize: 11, fontFamily: 'monospace', flex: 1 },
  httpHost: { color: colors.textDim, fontSize: 10 },
  empty: { color: colors.textMuted, textAlign: 'center', marginTop: 40, fontSize: 14 },
  emptyWrap: { alignItems: 'center', marginTop: 60, gap: 8 },
  emptyIcon: { fontSize: 32 },
});
