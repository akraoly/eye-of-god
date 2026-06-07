/**
 * RFIDScreen — RFID Badge Tool (Proxmark3)
 * Tabs: Scan · Dump · Clone · Analyse · Simulate · Logs
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
  TextInput, ActivityIndicator, FlatList, Alert, Animated,
} from 'react-native';
import { colors } from '../../utils/theme';
import { apiJSON } from '../../utils/api';

// ── Constantes ────────────────────────────────────────────────────────────────

const TABS = [
  { id: 'scan',     label: 'Scan' },
  { id: 'dump',     label: 'Dump' },
  { id: 'clone',    label: 'Clone' },
  { id: 'analyse',  label: 'Analyse' },
  { id: 'simulate', label: 'Simulate' },
  { id: 'logs',     label: 'Logs' },
];

const CARD_TYPES = [
  { value: 'hf_mifare_classic',    label: 'MIFARE Classic' },
  { value: 'hf_mifare_ultralight', label: 'MIFARE UL' },
  { value: 'hf_desfire',           label: 'DESFire' },
  { value: 'hf_iclass',            label: 'iCLASS' },
  { value: 'lf_em4100',            label: 'EM4100' },
  { value: 'lf_hid',               label: 'HID Prox' },
];

const TARGET_TYPES = [
  { value: 'lf_t55xx',            label: 'T55xx (LF)' },
  { value: 'lf_em4305',           label: 'EM4305 (LF)' },
  { value: 'hf_mifare_classic',   label: 'MIFARE Classic' },
];

const SEV_COLORS = {
  CRITICAL: colors.red,
  HIGH:     colors.cyber,
  MEDIUM:   colors.yellow,
  LOW:      colors.accent,
  INFO:     colors.textMuted,
};

// ── PulseAnim ──────────────────────────────────────────────────────────────────
function PulseCard({ active }) {
  const pulse = useRef(new Animated.Value(1)).current;
  useEffect(() => {
    if (active) {
      const anim = Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.12, duration: 600, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1.00, duration: 600, useNativeDriver: true }),
        ])
      );
      anim.start();
      return () => anim.stop();
    }
    pulse.setValue(1);
  }, [active, pulse]);

  return (
    <Animated.View style={[s.cardIcon, { transform: [{ scale: pulse }] }]}>
      <Text style={{ fontSize: 64 }}>💳</Text>
    </Animated.View>
  );
}

// ── ProgressBar ───────────────────────────────────────────────────────────────
function BlockProgress({ current, total = 64 }) {
  const pct = total > 0 ? Math.min((current / total) * 100, 100) : 0;
  return (
    <View>
      <View style={s.progressRow}>
        <Text style={s.progressLabel}>BLOCS LUS</Text>
        <Text style={s.progressVal}>{current} / {total}</Text>
      </View>
      <View style={s.progressTrack}>
        <View style={[s.progressFill, { width: `${pct}%` }]} />
      </View>
    </View>
  );
}

// ── Sévérité badge ────────────────────────────────────────────────────────────
function SevBadge({ sev }) {
  const c = SEV_COLORS[sev] || colors.textMuted;
  return (
    <View style={[s.sevBadge, { borderColor: c }]}>
      <Text style={[s.sevText, { color: c }]}>{sev}</Text>
    </View>
  );
}

// ── Composant principal ────────────────────────────────────────────────────────
export default function RFIDScreen() {
  const [tab,           setTab]           = useState('scan');
  const [pm3,           setPm3]           = useState(null);
  const [statusLoading, setStatusLoading] = useState(false);

  // Scan
  const [scanning,      setScanning]      = useState(false);
  const [scanResult,    setScanResult]    = useState(null);

  // Dump
  const [dumping,       setDumping]       = useState(false);
  const [dumpResult,    setDumpResult]    = useState(null);
  const [dumpType,      setDumpType]      = useState('hf_mifare_classic');
  const [dumpProgress,  setDumpProgress]  = useState(0);
  const dumpTimerRef = useRef(null);

  // Clone
  const [cloneUID,      setCloneUID]      = useState('');
  const [cloneTarget,   setCloneTarget]   = useState('lf_t55xx');
  const [cloning,       setCloning]       = useState(false);
  const [cloneOk,       setCloneOk]       = useState(null);

  // Analyse
  const [analyzeRaw,    setAnalyzeRaw]    = useState('');
  const [analyzeResult, setAnalyzeResult] = useState(null);
  const [vulnType,      setVulnType]      = useState('hf_mifare_classic');
  const [vulns,         setVulns]         = useState(null);

  // Simulate
  const [simUID,        setSimUID]        = useState('04A3F2112233');
  const [simType,       setSimType]       = useState('hf_mifare_classic');
  const [simDuration,   setSimDuration]   = useState(30);
  const [simulating,    setSimulating]    = useState(false);
  const [simTimer,      setSimTimer]      = useState(0);
  const simIntervalRef = useRef(null);

  // Logs
  const [logs,          setLogs]          = useState([]);
  const [logsLoading,   setLogsLoading]   = useState(false);

  // ── API helper ─────────────────────────────────────────────────────────────

  const api = useCallback(async (path, opts = {}) => {
    return apiJSON(`/api/rfid${path}`, opts);
  }, []);

  // ── Statut PM3 ─────────────────────────────────────────────────────────────

  const fetchStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const d = await api('/status');
      setPm3(d);
    } catch {
      setPm3({ connected: false, simulation_mode: true });
    }
    setStatusLoading(false);
  }, [api]);

  useEffect(() => { fetchStatus(); }, [fetchStatus]);

  // ── Logs ───────────────────────────────────────────────────────────────────

  const fetchLogs = useCallback(async () => {
    setLogsLoading(true);
    try {
      const d = await api('/logs?limit=50');
      setLogs(d.logs || []);
    } catch { /* ignore */ }
    setLogsLoading(false);
  }, [api]);

  useEffect(() => {
    if (tab === 'logs') fetchLogs();
  }, [tab, fetchLogs]);

  // ── Scan ───────────────────────────────────────────────────────────────────

  const handleScan = async () => {
    setScanning(true);
    setScanResult(null);
    try {
      const d = await api('/scan', { method: 'POST' });
      setScanResult(d.card);
    } catch (e) {
      Alert.alert('Scan', e.message);
    }
    setScanning(false);
  };

  // ── Dump ───────────────────────────────────────────────────────────────────

  const handleDump = async () => {
    setDumping(true);
    setDumpResult(null);
    setDumpProgress(0);
    dumpTimerRef.current = setInterval(() => {
      setDumpProgress(p => (p < 63 ? p + 1 : p));
    }, 200);
    try {
      const d = await api('/dump', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ card_type: dumpType }),
      });
      clearInterval(dumpTimerRef.current);
      setDumpProgress(d.blocks_count || 64);
      setDumpResult(d);
    } catch (e) {
      clearInterval(dumpTimerRef.current);
      Alert.alert('Dump', e.message);
    }
    setDumping(false);
  };

  useEffect(() => () => clearInterval(dumpTimerRef.current), []);

  // ── Clone ──────────────────────────────────────────────────────────────────

  const handleClone = () => {
    if (!cloneUID) { Alert.alert('Clone', 'Entrez un UID source'); return; }
    Alert.alert(
      'Confirmation',
      `Cloner ${cloneUID} vers ${cloneTarget} ?`,
      [
        { text: 'Annuler', style: 'cancel' },
        {
          text: 'CLONER', style: 'destructive',
          onPress: async () => {
            setCloning(true);
            setCloneOk(null);
            try {
              const d = await api('/clone', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ source_uid: cloneUID, data_hex: '', target_type: cloneTarget }),
              });
              setCloneOk(d.success);
              Alert.alert('Clone', d.success ? 'Clonage réussi !' : `Échec: ${d.message}`);
            } catch (e) {
              setCloneOk(false);
              Alert.alert('Clone', e.message);
            }
            setCloning(false);
          },
        },
      ]
    );
  };

  // ── Analyse ────────────────────────────────────────────────────────────────

  const handleAnalyze = async () => {
    if (!analyzeRaw) return;
    try {
      const d = await api('/analyze', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ raw_data: analyzeRaw }),
      });
      setAnalyzeResult(d);
    } catch (e) {
      Alert.alert('Analyse', e.message);
    }
  };

  const handleVulnScan = async () => {
    try {
      const d = await api('/vuln-scan', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ card_type: vulnType }),
      });
      setVulns(d.vulnerabilities || []);
    } catch (e) {
      Alert.alert('Vuln scan', e.message);
    }
  };

  // ── Simulate ───────────────────────────────────────────────────────────────

  const handleSimulate = async () => {
    setSimulating(true);
    setSimTimer(simDuration);
    simIntervalRef.current = setInterval(() => {
      setSimTimer(t => {
        if (t <= 1) { clearInterval(simIntervalRef.current); return 0; }
        return t - 1;
      });
    }, 1000);
    try {
      await api('/simulate', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ uid: simUID, data_hex: '', card_type: simType, duration: simDuration }),
      });
    } catch { /* ignore */ }
    clearInterval(simIntervalRef.current);
    setSimulating(false);
    setSimTimer(0);
  };

  useEffect(() => () => clearInterval(simIntervalRef.current), []);

  // ── Status indicator ───────────────────────────────────────────────────────

  const pm3Dot   = pm3?.connected ? colors.green : (pm3?.simulation_mode ? colors.yellow : colors.red);
  const pm3Label = pm3?.connected ? 'PM3' : (pm3?.simulation_mode ? 'SIM' : 'OFF');

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <View style={s.root}>

      {/* Header */}
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.title}>RFID BADGE TOOL</Text>
          <Text style={s.subtitle}>Proxmark3 · Clone · Analyse</Text>
        </View>
        <View style={s.headerRight}>
          <View style={[s.dot, { backgroundColor: pm3Dot }]} />
          <Text style={[s.pm3Label, { color: pm3Dot }]}>{pm3Label}</Text>
          {pm3?.battery && <Text style={s.battery}>{pm3.battery}</Text>}
          <TouchableOpacity onPress={fetchStatus} disabled={statusLoading}>
            <Text style={s.refreshBtn}>{statusLoading ? '…' : '⟳'}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Tabs */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={s.tabsScroll}>
        <View style={s.tabs}>
          {TABS.map(t => (
            <TouchableOpacity
              key={t.id}
              onPress={() => setTab(t.id)}
              style={[s.tab, tab === t.id && s.tabActive]}
            >
              <Text style={[s.tabText, tab === t.id && s.tabTextActive]}>{t.label}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      {/* Tab content */}
      <ScrollView style={s.content} contentContainerStyle={s.contentInner} keyboardShouldPersistTaps="handled">

        {/* ── TAB: SCAN ─────────────────────────────────────────────────────── */}
        {tab === 'scan' && (
          <View>
            <View style={s.card}>
              <Text style={s.cardLabel}>SCANNER UNE CARTE</Text>
              <PulseCard active={scanning} />
              <TouchableOpacity
                onPress={handleScan}
                disabled={scanning}
                style={[s.bigBtn, scanning && s.bigBtnDisabled]}
              >
                {scanning
                  ? <ActivityIndicator color={colors.bg} />
                  : <Text style={s.bigBtnText}>SCAN</Text>
                }
              </TouchableOpacity>
            </View>

            {scanResult && (
              <View style={s.card}>
                <Text style={s.cardLabel}>RÉSULTAT</Text>
                <InfoRow label="UID"      value={scanResult.uid} highlight />
                <InfoRow label="Type"     value={scanResult.card_type} />
                <InfoRow label="Protocol" value={scanResult.protocol} />
                {scanResult.atqa && <InfoRow label="ATQA" value={scanResult.atqa} />}
                {scanResult.sak  && <InfoRow label="SAK"  value={scanResult.sak} />}
                {scanResult.simulated && (
                  <Text style={s.simBadge}>MODE SIMULATION</Text>
                )}
                <TouchableOpacity
                  style={[s.btn, { marginTop: 12 }]}
                  onPress={() => { setCloneUID(scanResult.uid); setTab('clone'); }}
                >
                  <Text style={s.btnText}>Cloner cette carte</Text>
                </TouchableOpacity>
              </View>
            )}
          </View>
        )}

        {/* ── TAB: DUMP ─────────────────────────────────────────────────────── */}
        {tab === 'dump' && (
          <View>
            <View style={s.card}>
              <Text style={s.cardLabel}>TYPE DE CARTE</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={s.chipRow}>
                  {CARD_TYPES.map(ct => (
                    <TouchableOpacity
                      key={ct.value}
                      onPress={() => setDumpType(ct.value)}
                      style={[s.chip, dumpType === ct.value && s.chipActive]}
                    >
                      <Text style={[s.chipText, dumpType === ct.value && s.chipTextActive]}>
                        {ct.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>

              <TouchableOpacity
                onPress={handleDump}
                disabled={dumping}
                style={[s.bigBtn, { marginTop: 16 }, dumping && s.bigBtnDisabled]}
              >
                {dumping
                  ? <ActivityIndicator color={colors.bg} />
                  : <Text style={s.bigBtnText}>DUMP FULL</Text>
                }
              </TouchableOpacity>

              {(dumping || dumpResult) && (
                <View style={{ marginTop: 16 }}>
                  <BlockProgress current={dumpProgress} total={64} />
                </View>
              )}
            </View>

            {dumpResult && (
              <>
                {/* Clés trouvées */}
                {dumpResult.keys_found && dumpResult.keys_found.length > 0 && (
                  <View style={s.card}>
                    <Text style={s.cardLabel}>CLÉS TROUVÉES</Text>
                    <View style={s.chipRow}>
                      {dumpResult.keys_found.map((k, i) => (
                        <View key={i} style={[s.chip, s.chipActive]}>
                          <Text style={[s.chipText, s.chipTextActive]}>{k}</Text>
                        </View>
                      ))}
                    </View>
                  </View>
                )}

                {/* HexDump */}
                <View style={s.card}>
                  <Text style={s.cardLabel}>HEX DUMP ({dumpResult.blocks_count} blocs)</Text>
                  <ScrollView style={s.hexDumpScroll} nestedScrollEnabled>
                    {Object.entries(dumpResult.blocks || {}).map(([blk, data]) => {
                      const hex   = (data || '').toUpperCase();
                      const pairs = hex.match(/.{1,2}/g) || [];
                      const isKey = parseInt(blk) % 4 === 3;
                      return (
                        <View key={blk} style={s.hexRow}>
                          <Text style={s.hexBlk}>{String(blk).padStart(2, '0')}</Text>
                          <Text style={[s.hexData, isKey && { color: colors.cyber }]}>
                            {pairs.slice(0, 8).join(' ')}
                          </Text>
                        </View>
                      );
                    })}
                  </ScrollView>
                </View>
              </>
            )}
          </View>
        )}

        {/* ── TAB: CLONE ────────────────────────────────────────────────────── */}
        {tab === 'clone' && (
          <View>
            <View style={s.card}>
              <Text style={s.cardLabel}>UID SOURCE</Text>
              <View style={s.uidDisplay}>
                <Text style={s.uidText}>{cloneUID || '—'}</Text>
              </View>
              <TextInput
                value={cloneUID}
                onChangeText={setCloneUID}
                placeholder="04:A3:F2:11:22:33"
                placeholderTextColor={colors.textDim}
                style={s.input}
              />
            </View>

            <View style={s.card}>
              <Text style={s.cardLabel}>CARTE CIBLE</Text>
              <View style={s.chipRow}>
                {TARGET_TYPES.map(tt => (
                  <TouchableOpacity
                    key={tt.value}
                    onPress={() => setCloneTarget(tt.value)}
                    style={[s.chip, cloneTarget === tt.value && s.chipActive]}
                  >
                    <Text style={[s.chipText, cloneTarget === tt.value && s.chipTextActive]}>
                      {tt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>

              <TouchableOpacity
                onPress={handleClone}
                disabled={cloning || !cloneUID}
                style={[s.bigBtn, s.bigBtnDanger, (cloning || !cloneUID) && s.bigBtnDisabled, { marginTop: 16 }]}
              >
                {cloning
                  ? <ActivityIndicator color={colors.white} />
                  : <Text style={s.bigBtnText}>CLONE</Text>
                }
              </TouchableOpacity>

              {cloneOk !== null && (
                <View style={[s.resultBox, { borderColor: cloneOk ? colors.green : colors.red }]}>
                  <Text style={{ color: cloneOk ? colors.green : colors.red, fontWeight: '800', fontSize: 13 }}>
                    {cloneOk ? 'Clonage réussi' : 'Clonage échoué'}
                  </Text>
                </View>
              )}
            </View>
          </View>
        )}

        {/* ── TAB: ANALYSE ──────────────────────────────────────────────────── */}
        {tab === 'analyse' && (
          <View>
            <View style={s.card}>
              <Text style={s.cardLabel}>ANALYSE FORMAT BADGE</Text>
              <TextInput
                value={analyzeRaw}
                onChangeText={setAnalyzeRaw}
                placeholder="Données hex brutes…"
                placeholderTextColor={colors.textDim}
                style={s.input}
              />
              <TouchableOpacity
                onPress={handleAnalyze}
                disabled={!analyzeRaw}
                style={[s.btn, { marginTop: 10 }, !analyzeRaw && { opacity: 0.4 }]}
              >
                <Text style={s.btnText}>ANALYSER</Text>
              </TouchableOpacity>

              {analyzeResult && !analyzeResult.error && (
                <View style={{ marginTop: 14 }}>
                  <InfoRow label="Format"    value={analyzeResult.format}        highlight />
                  <InfoRow label="Site Code" value={analyzeResult.site_code}     />
                  <InfoRow label="Badge N°"  value={analyzeResult.badge_number}  />
                  <InfoRow label="Facility"  value={analyzeResult.facility_code} />
                  <InfoRow label="Bits"      value={String(analyzeResult.bits)} />
                </View>
              )}
              {analyzeResult?.error && (
                <Text style={{ color: colors.red, fontSize: 12, marginTop: 8 }}>{analyzeResult.error}</Text>
              )}
            </View>

            <View style={s.card}>
              <Text style={s.cardLabel}>VULNÉRABILITÉS</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={s.chipRow}>
                  {CARD_TYPES.map(ct => (
                    <TouchableOpacity
                      key={ct.value}
                      onPress={() => setVulnType(ct.value)}
                      style={[s.chip, vulnType === ct.value && s.chipActive]}
                    >
                      <Text style={[s.chipText, vulnType === ct.value && s.chipTextActive]}>
                        {ct.label}
                      </Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
              <TouchableOpacity onPress={handleVulnScan} style={[s.btn, { marginTop: 10 }]}>
                <Text style={s.btnText}>SCAN VULNS</Text>
              </TouchableOpacity>

              {vulns && vulns.map((v, i) => (
                <View key={i} style={[s.vulnCard, { borderLeftColor: SEV_COLORS[v.severity] || colors.textMuted }]}>
                  <View style={s.vulnHeader}>
                    <Text style={s.vulnTitle}>{v.title}</Text>
                    <SevBadge sev={v.severity} />
                  </View>
                  <Text style={s.vulnDesc}>{v.description}</Text>
                  {v.cwe && <Text style={s.vulnCwe}>{v.cwe} · {v.mitre}</Text>}
                </View>
              ))}
            </View>
          </View>
        )}

        {/* ── TAB: SIMULATE ─────────────────────────────────────────────────── */}
        {tab === 'simulate' && (
          <View>
            <View style={s.card}>
              <Text style={s.cardLabel}>PARAMÈTRES</Text>
              <Text style={s.fieldLabel}>UID</Text>
              <TextInput
                value={simUID}
                onChangeText={setSimUID}
                placeholder="04A3F2112233"
                placeholderTextColor={colors.textDim}
                style={s.input}
              />
              <Text style={[s.fieldLabel, { marginTop: 10 }]}>TYPE</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                <View style={s.chipRow}>
                  {CARD_TYPES.slice(0, 3).map(ct => (
                    <TouchableOpacity
                      key={ct.value}
                      onPress={() => setSimType(ct.value)}
                      style={[s.chip, simType === ct.value && s.chipActive]}
                    >
                      <Text style={[s.chipText, simType === ct.value && s.chipTextActive]}>{ct.label}</Text>
                    </TouchableOpacity>
                  ))}
                </View>
              </ScrollView>
              <Text style={[s.fieldLabel, { marginTop: 10 }]}>DURÉE (s)</Text>
              <View style={s.chipRow}>
                {[10, 30, 60, 120].map(d => (
                  <TouchableOpacity
                    key={d}
                    onPress={() => setSimDuration(d)}
                    style={[s.chip, simDuration === d && s.chipActive]}
                  >
                    <Text style={[s.chipText, simDuration === d && s.chipTextActive]}>{d}s</Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>

            <View style={s.card}>
              <Text style={s.cardLabel}>ÉMULATION</Text>
              <View style={s.simCenter}>
                <Text style={{ fontSize: 56 }}>{simulating ? '📡' : '💳'}</Text>
                {simulating && simTimer > 0 && (
                  <View style={s.timerBox}>
                    <Text style={s.timerText}>{simTimer}s</Text>
                  </View>
                )}
                <TouchableOpacity
                  onPress={handleSimulate}
                  disabled={simulating || !simUID}
                  style={[s.bigBtn, { marginTop: 16 }, (simulating || !simUID) && s.bigBtnDisabled]}
                >
                  {simulating
                    ? <ActivityIndicator color={colors.bg} />
                    : <Text style={s.bigBtnText}>SIMULATE</Text>
                  }
                </TouchableOpacity>
                {simulating && (
                  <Text style={s.simInstruction}>
                    Approchez le lecteur de la carte Proxmark3…
                  </Text>
                )}
              </View>
            </View>
          </View>
        )}

        {/* ── TAB: LOGS ─────────────────────────────────────────────────────── */}
        {tab === 'logs' && (
          <View style={s.card}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 12 }}>
              <Text style={s.cardLabel}>LOGS ({logs.length})</Text>
              <TouchableOpacity onPress={fetchLogs} disabled={logsLoading}>
                <Text style={{ color: colors.accent, fontSize: 12 }}>
                  {logsLoading ? '…' : 'Actualiser'}
                </Text>
              </TouchableOpacity>
            </View>
            {logs.length === 0 ? (
              <Text style={s.empty}>Aucun log</Text>
            ) : (
              <FlatList
                data={logs}
                keyExtractor={item => String(item.id)}
                scrollEnabled={false}
                renderItem={({ item }) => (
                  <View style={s.logRow}>
                    <Text style={{ fontSize: 16, marginRight: 8 }}>
                      {item.success ? '✅' : '❌'}
                    </Text>
                    <View style={{ flex: 1 }}>
                      <Text style={s.logAction}>{item.action}</Text>
                      {item.card_uid && (
                        <Text style={s.logUid}>{item.card_uid}</Text>
                      )}
                      <Text style={s.logTs}>
                        {item.timestamp ? item.timestamp.slice(0, 19).replace('T', ' ') : ''}
                      </Text>
                    </View>
                  </View>
                )}
              />
            )}
          </View>
        )}

      </ScrollView>
    </View>
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function InfoRow({ label, value, highlight }) {
  return (
    <View style={s.infoRow}>
      <Text style={s.infoLabel}>{label}</Text>
      <Text style={[s.infoValue, highlight && { color: colors.accent }]}>
        {value || '—'}
      </Text>
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  root:            { flex: 1, backgroundColor: colors.bg },
  header:          { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, paddingBottom: 8 },
  headerLeft:      {},
  headerRight:     { flexDirection: 'row', alignItems: 'center', gap: 6 },
  title:           { fontSize: 14, fontWeight: '800', color: colors.accent, letterSpacing: 2 },
  subtitle:        { fontSize: 10, color: colors.textMuted, letterSpacing: 1 },
  dot:             { width: 8, height: 8, borderRadius: 4 },
  pm3Label:        { fontSize: 10, fontWeight: '700', letterSpacing: 1 },
  battery:         { fontSize: 10, color: colors.textMuted },
  refreshBtn:      { fontSize: 16, color: colors.textMuted, paddingHorizontal: 4 },

  tabsScroll:      { flexGrow: 0 },
  tabs:            { flexDirection: 'row', paddingHorizontal: 12, paddingBottom: 0 },
  tab:             { paddingVertical: 8, paddingHorizontal: 14, borderBottomWidth: 2, borderBottomColor: 'transparent' },
  tabActive:       { borderBottomColor: colors.accent },
  tabText:         { fontSize: 11, fontWeight: '700', color: colors.textMuted, letterSpacing: 1 },
  tabTextActive:   { color: colors.accent },

  content:         { flex: 1 },
  contentInner:    { padding: 14, paddingBottom: 40 },

  card:            { backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 14 },
  cardLabel:       { fontSize: 10, color: colors.textDim, letterSpacing: 1.5, fontWeight: '700', marginBottom: 10 },
  fieldLabel:      { fontSize: 10, color: colors.textDim, letterSpacing: 1, marginBottom: 4 },

  cardIcon:        { alignItems: 'center', paddingVertical: 16 },

  bigBtn:          { backgroundColor: colors.accent, borderRadius: 10, paddingVertical: 14, alignItems: 'center' },
  bigBtnDanger:    { backgroundColor: colors.red },
  bigBtnDisabled:  { backgroundColor: colors.bgCardLight, opacity: 0.5 },
  bigBtnText:      { color: colors.bg, fontWeight: '900', fontSize: 15, letterSpacing: 2 },

  btn:             { backgroundColor: colors.accent + '20', borderRadius: 8, borderWidth: 1, borderColor: colors.accent + '40', paddingVertical: 10, alignItems: 'center' },
  btnText:         { color: colors.accent, fontWeight: '800', fontSize: 13 },

  input:           { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, color: colors.text, fontSize: 12, fontFamily: 'monospace' },

  chipRow:         { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 4 },
  chip:            { paddingVertical: 5, paddingHorizontal: 12, borderRadius: 20, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.bgCardLight },
  chipActive:      { borderColor: colors.accent, backgroundColor: colors.accent + '20' },
  chipText:        { color: colors.textMuted, fontSize: 11, fontWeight: '600' },
  chipTextActive:  { color: colors.accent },

  progressRow:     { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 },
  progressLabel:   { fontSize: 10, color: colors.textDim, letterSpacing: 1 },
  progressVal:     { fontSize: 10, color: colors.accent, fontWeight: '700' },
  progressTrack:   { height: 6, backgroundColor: colors.bgCardLight, borderRadius: 3, overflow: 'hidden' },
  progressFill:    { height: '100%', backgroundColor: colors.accent, borderRadius: 3 },

  hexDumpScroll:   { maxHeight: 220, backgroundColor: colors.bg, borderRadius: 8, padding: 8 },
  hexRow:          { flexDirection: 'row', gap: 8, paddingVertical: 1 },
  hexBlk:          { color: colors.textDim, fontSize: 10, minWidth: 20, fontFamily: 'monospace' },
  hexData:         { color: colors.textMuted, fontSize: 10, fontFamily: 'monospace', flex: 1 },

  uidDisplay:      { backgroundColor: colors.bg, borderRadius: 8, padding: 12, marginBottom: 10, alignItems: 'center' },
  uidText:         { color: colors.accent, fontWeight: '700', fontSize: 14, fontFamily: 'monospace', letterSpacing: 2 },

  resultBox:       { marginTop: 12, padding: 12, borderRadius: 8, borderWidth: 1, alignItems: 'center' },

  infoRow:         { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 5, borderBottomWidth: 1, borderBottomColor: colors.bgCardLight },
  infoLabel:       { fontSize: 11, color: colors.textMuted },
  infoValue:       { fontSize: 12, color: colors.text, fontWeight: '600', fontFamily: 'monospace' },

  simBadge:        { color: colors.yellow, fontSize: 10, fontWeight: '700', marginTop: 6, letterSpacing: 1 },
  simCenter:       { alignItems: 'center' },
  simInstruction:  { color: colors.textMuted, fontSize: 12, marginTop: 12, textAlign: 'center' },
  timerBox:        { marginTop: 8 },
  timerText:       { color: colors.accent, fontSize: 32, fontWeight: '900', fontFamily: 'monospace' },

  vulnCard:        { borderLeftWidth: 3, backgroundColor: colors.bgCardLight, borderRadius: 6, padding: 10, marginTop: 10 },
  vulnHeader:      { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 },
  vulnTitle:       { color: colors.text, fontSize: 12, fontWeight: '700', flex: 1, marginRight: 8 },
  vulnDesc:        { color: colors.textMuted, fontSize: 11, lineHeight: 16 },
  vulnCwe:         { color: colors.textDim, fontSize: 10, marginTop: 4 },
  sevBadge:        { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 4, borderWidth: 1 },
  sevText:         { fontSize: 9, fontWeight: '700', letterSpacing: 0.5 },

  logRow:          { flexDirection: 'row', alignItems: 'flex-start', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.bgCardLight },
  logAction:       { color: colors.text, fontSize: 12, fontWeight: '700' },
  logUid:          { color: colors.accent, fontSize: 11, fontFamily: 'monospace' },
  logTs:           { color: colors.textDim, fontSize: 10, marginTop: 2 },

  empty:           { color: colors.textMuted, fontSize: 13, textAlign: 'center', paddingVertical: 20 },
});
