/**
 * CameraScanScreen — Découverte caméras réseau, détail, snapshot
 */
import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, FlatList,
  TextInput, ActivityIndicator, Image, Alert, ScrollView,
  Modal,
} from 'react-native';
import { colors } from '../../utils/theme';
import { apiJSON, apiFetch, API_BASE } from '../../utils/api';

const STATUS_COLOR = { online: colors.green, offline: colors.red, unknown: colors.yellow };

function StatusDot({ status }) {
  return (
    <View style={[s.dot, { backgroundColor: STATUS_COLOR[status || 'unknown'] }]} />
  );
}

function VulnBadge({ count }) {
  if (!count) return null;
  const color = count >= 3 ? colors.red : colors.yellow;
  return (
    <View style={[s.badge, { borderColor: color, backgroundColor: color + '20' }]}>
      <Text style={[s.badgeText, { color }]}>{count} CVE</Text>
    </View>
  );
}

function CameraItem({ cam, onPress }) {
  return (
    <TouchableOpacity onPress={() => onPress(cam)} style={s.camRow} activeOpacity={0.7}>
      <StatusDot status={cam.status} />
      <View style={{ flex: 1 }}>
        <Text style={s.camIp}>{cam.ip}</Text>
        {cam.model && <Text style={s.camModel}>{cam.manufacturer ? `${cam.manufacturer} · ` : ''}{cam.model}</Text>}
      </View>
      {cam.cve_count > 0 && <VulnBadge count={cam.cve_count} />}
      <Text style={s.chevron}>›</Text>
    </TouchableOpacity>
  );
}

function CameraDetailSheet({ cam, visible, onClose }) {
  const [snapshot, setSnapshot] = useState(null);
  const [snapLoading, setSnapLoading] = useState(false);
  const [credsResult, setCredsResult] = useState(null);
  const [credsLoading, setCredsLoading] = useState(false);

  const takeSnapshot = async () => {
    setSnapLoading(true);
    try {
      const d = await apiJSON('/api/cameras/snapshot', {
        method: 'POST', body: JSON.stringify({ ip: cam.ip, port: cam.port }),
      });
      setSnapshot(d.url || (d.data ? `data:image/jpeg;base64,${d.data}` : null));
    } catch { Alert.alert('Erreur', 'Snapshot impossible'); }
    setSnapLoading(false);
  };

  const testCreds = async () => {
    setCredsLoading(true);
    try {
      const d = await apiJSON('/api/cameras/test-creds', {
        method: 'POST', body: JSON.stringify({ ip: cam.ip, port: cam.port }),
      });
      setCredsResult(d);
    } catch { setCredsResult({ success: false }); }
    setCredsLoading(false);
  };

  const FIELDS = [
    ['IP', cam?.ip], ['Modèle', cam?.model], ['Fabricant', cam?.manufacturer],
    ['Firmware', cam?.firmware], ['Port', cam?.port?.toString()],
    ['RTSP', cam?.rtsp_url], ['Username', cam?.username], ['Password', cam?.password],
  ].filter(([, v]) => v);

  if (!cam) return null;
  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={s.sheet}>
        <View style={s.sheetHandle} />
        <View style={s.sheetHeader}>
          <Text style={s.sheetTitle}>📷 {cam.ip}</Text>
          <TouchableOpacity onPress={onClose}><Text style={s.sheetClose}>✕</Text></TouchableOpacity>
        </View>
        <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: 16 }}>

          {/* Snapshot */}
          <View style={[s.card, { marginBottom: 14 }]}>
            {snapshot ? (
              <Image source={{ uri: snapshot }} style={s.snapshotImg} resizeMode="cover" />
            ) : (
              <View style={s.snapshotPlaceholder}>
                <Text style={{ color: colors.textDim, fontSize: 13 }}>📸 Pas de snapshot</Text>
              </View>
            )}
            <TouchableOpacity onPress={takeSnapshot} disabled={snapLoading} style={[s.btn, { marginTop: 10 }]}>
              {snapLoading ? <ActivityIndicator color={colors.bg} /> : <Text style={s.btnText}>📸 Prendre un snapshot</Text>}
            </TouchableOpacity>
          </View>

          {/* Details */}
          <View style={s.card}>
            <Text style={s.cardLabel}>INFORMATIONS</Text>
            {FIELDS.map(([k, v]) => (
              <View key={k} style={s.detailRow}>
                <Text style={s.detailKey}>{k}</Text>
                <Text style={s.detailVal} selectable>{v}</Text>
              </View>
            ))}
          </View>

          {/* Test Creds */}
          <View style={s.card}>
            <Text style={s.cardLabel}>TEST CREDENTIALS</Text>
            <TouchableOpacity onPress={testCreds} disabled={credsLoading} style={[s.btn, { backgroundColor: '#fbbf2430', borderWidth: 1, borderColor: '#fbbf2460' }]}>
              {credsLoading
                ? <ActivityIndicator color={colors.yellow} />
                : <Text style={[s.btnText, { color: colors.yellow }]}>🔑 Tester les creds par défaut</Text>}
            </TouchableOpacity>
            {credsResult && (
              <View style={[s.credsResult, { borderColor: credsResult.success ? colors.green : colors.red }]}>
                <Text style={{ color: credsResult.success ? colors.green : colors.red, fontSize: 13 }}>
                  {credsResult.success
                    ? `✓ ${credsResult.username}:${credsResult.password}`
                    : '✗ Aucune credential valide'}
                </Text>
              </View>
            )}
          </View>
        </ScrollView>
      </View>
    </Modal>
  );
}

export default function CameraScanScreen() {
  const [subnet,    setSubnet]    = useState('192.168.1.0/24');
  const [scanning,  setScanning]  = useState(false);
  const [progress,  setProgress]  = useState(0);
  const [cameras,   setCameras]   = useState([]);
  const [selected,  setSelected]  = useState(null);
  const [error,     setError]     = useState('');
  const progressRef = useRef(null);

  const startScan = async () => {
    if (!subnet.trim()) return;
    setScanning(true); setProgress(0); setError(''); setCameras([]);
    progressRef.current = setInterval(() => setProgress(p => Math.min(p + Math.random() * 8, 88)), 400);
    try {
      const d = await apiJSON('/api/cameras/scan', {
        method: 'POST', body: JSON.stringify({ subnet: subnet.trim() }),
      });
      setCameras(d.cameras || []);
      setProgress(100);
    } catch (e) { setError(e.message || 'Échec du scan'); }
    clearInterval(progressRef.current);
    setScanning(false);
  };

  useEffect(() => () => clearInterval(progressRef.current), []);

  return (
    <View style={s.container}>
      <ScrollView contentContainerStyle={s.content} keyboardShouldPersistTaps="handled">
        {/* Header */}
        <View style={s.header}>
          <Text style={s.icon}>📷</Text>
          <View>
            <Text style={s.title}>CAMERA SCAN</Text>
            <Text style={s.subtitle}>Découverte · Snapshots · CVE</Text>
          </View>
        </View>

        {/* Scan input */}
        <View style={s.card}>
          <Text style={s.cardLabel}>RÉSEAU CIBLE</Text>
          <TextInput
            value={subnet} onChangeText={setSubnet} editable={!scanning}
            placeholder="192.168.1.0/24" placeholderTextColor={colors.textDim}
            style={s.input}
            autoCapitalize="none" keyboardType="numbers-and-punctuation"
          />
          <TouchableOpacity onPress={startScan} disabled={scanning} style={[s.btn, { marginTop: 10, opacity: scanning ? 0.6 : 1 }]}>
            {scanning
              ? <ActivityIndicator color={colors.bg} />
              : <Text style={s.btnText}>🔍 Scanner le réseau</Text>}
          </TouchableOpacity>

          {scanning && (
            <View style={{ marginTop: 12 }}>
              <View style={s.progressBar}>
                <View style={[s.progressFill, { width: `${progress}%` }]} />
              </View>
              <Text style={s.progressText}>{Math.round(progress)}%</Text>
            </View>
          )}
          {error !== '' && <Text style={s.errorText}>⚠ {error}</Text>}
        </View>

        {/* Results */}
        {cameras.length > 0 && (
          <View style={s.card}>
            <Text style={s.cardLabel}>{cameras.length} CAMÉRA(S) TROUVÉE(S)</Text>
            {cameras.map((cam, i) => (
              <CameraItem key={i} cam={cam} onPress={setSelected} />
            ))}
          </View>
        )}

        {!scanning && cameras.length === 0 && (
          <Text style={s.empty}>Aucune caméra — Lancez un scan</Text>
        )}
      </ScrollView>

      <CameraDetailSheet cam={selected} visible={!!selected} onClose={() => setSelected(null)} />
    </View>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 40 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 20 },
  icon: { fontSize: 32 },
  title: { fontSize: 16, fontWeight: '800', color: colors.accent, letterSpacing: 2 },
  subtitle: { fontSize: 11, color: colors.textMuted, letterSpacing: 1 },
  card: { backgroundColor: colors.bgCard, borderRadius: 14, borderWidth: 1, borderColor: colors.border, padding: 14, marginBottom: 14 },
  cardLabel: { fontSize: 10, color: colors.textDim, letterSpacing: 1.5, fontWeight: '700', marginBottom: 10 },
  btn: { backgroundColor: colors.accent, borderRadius: 8, padding: 11, alignItems: 'center' },
  btnText: { color: colors.bg, fontWeight: '800', fontSize: 14 },
  input: { backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 10, color: colors.text, fontSize: 14, fontFamily: 'monospace' },
  progressBar: { height: 4, backgroundColor: colors.border, borderRadius: 2, overflow: 'hidden' },
  progressFill: { height: '100%', backgroundColor: colors.accent, borderRadius: 2 },
  progressText: { color: colors.textMuted, fontSize: 11, textAlign: 'right', marginTop: 4 },
  errorText: { color: colors.red, fontSize: 12, marginTop: 8 },
  camRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.border },
  dot: { width: 8, height: 8, borderRadius: 4 },
  camIp: { color: colors.text, fontSize: 14, fontWeight: '700', fontFamily: 'monospace' },
  camModel: { color: colors.textMuted, fontSize: 12, marginTop: 2 },
  chevron: { color: colors.accent, fontSize: 20 },
  badge: { paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, borderWidth: 1 },
  badgeText: { fontSize: 10, fontWeight: '700' },
  empty: { color: colors.textMuted, textAlign: 'center', fontSize: 14, marginTop: 24 },
  sheet: { flex: 1, backgroundColor: colors.bg },
  sheetHandle: { width: 36, height: 4, borderRadius: 2, backgroundColor: colors.border, alignSelf: 'center', marginTop: 12 },
  sheetHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 16, borderBottomWidth: 1, borderBottomColor: colors.border },
  sheetTitle: { color: colors.accent, fontWeight: '700', fontSize: 16 },
  sheetClose: { color: colors.textMuted, fontSize: 20 },
  snapshotImg: { width: '100%', height: 180, borderRadius: 8 },
  snapshotPlaceholder: { width: '100%', height: 120, borderRadius: 8, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.border },
  detailRow: { flexDirection: 'row', gap: 10, marginBottom: 6 },
  detailKey: { color: colors.textMuted, fontSize: 12, minWidth: 70 },
  detailVal: { color: colors.text, fontSize: 12, flex: 1, fontFamily: 'monospace', flexWrap: 'wrap' },
  credsResult: { marginTop: 10, padding: 10, borderRadius: 8, borderWidth: 1 },
});
