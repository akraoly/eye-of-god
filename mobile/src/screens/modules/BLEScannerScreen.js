/**
 * BLEScannerScreen — BLE Scanner module for L'Œil de Dieu mobile app
 * Tabs: Appareils · Trackers · Logs
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, StyleSheet, TouchableOpacity, FlatList,
  ActivityIndicator, Alert, Animated, Easing,
} from 'react-native';
import { apiJSON, apiFetch } from '../../utils/api';
import { colors } from '../../utils/theme';

// ── Constants ─────────────────────────────────────────────────────────────────

const DURATION_CHIPS = [5, 10, 30, 60];

const TYPE_ICONS = {
  phone: '📱',
  headphone: '🎧',
  smartwatch: '⌚',
  tracker: '🏷',
  laptop: '💻',
  unknown: '📡',
};

const TABS = [
  { id: 'devices', label: 'Appareils' },
  { id: 'trackers', label: 'Trackers' },
  { id: 'logs', label: 'Logs' },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function relTime(iso) {
  if (!iso) return '—';
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000);
  if (diff < 60) return `${diff}s`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}j`;
}

function maskMac(mac) {
  if (!mac) return '—';
  const parts = mac.split(':');
  return parts.map((p, i) => (i >= 3 ? '**' : p)).join(':');
}

function rssiToBars(rssi) {
  if (rssi >= -55) return 4;
  if (rssi >= -65) return 3;
  if (rssi >= -75) return 2;
  return 1;
}

function rssiColor(rssi) {
  if (rssi >= -55) return colors.green;
  if (rssi >= -65) return colors.yellow;
  return colors.red;
}

// ── Sub-components ────────────────────────────────────────────────────────────

function RSSIBars({ rssi }) {
  const bars = rssiToBars(rssi);
  const clr = rssiColor(rssi);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 2, height: 14 }}>
      {[1, 2, 3, 4].map(b => (
        <View key={b} style={{
          width: 3,
          height: 3 + b * 2,
          backgroundColor: b <= bars ? clr : colors.textDim,
          borderRadius: 1,
        }} />
      ))}
    </View>
  );
}

function Badge({ label, color }) {
  return (
    <View style={[s.badge, { borderColor: color + '80', backgroundColor: color + '20' }]}>
      <Text style={[s.badgeText, { color }]}>{label}</Text>
    </View>
  );
}

function ScanningPulse({ visible }) {
  const opacity = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    if (!visible) {
      opacity.setValue(1);
      return;
    }
    const anim = Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.2, duration: 600, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
        Animated.timing(opacity, { toValue: 1, duration: 600, useNativeDriver: true, easing: Easing.inOut(Easing.ease) }),
      ])
    );
    anim.start();
    return () => anim.stop();
  }, [visible, opacity]);

  if (!visible) return null;
  return <Animated.View style={[s.scanPulse, { opacity }]} />;
}

// ── Device item ───────────────────────────────────────────────────────────────

function DeviceItem({ item, onLongPress }) {
  const typeIcon = TYPE_ICONS[item.device_type] || '📡';
  const vulnCount = (item.vulns || []).length;
  const hasGATT = (item.gatt_services || []).length > 0;

  return (
    <TouchableOpacity
      style={s.deviceCard}
      onLongPress={() => onLongPress(item)}
      activeOpacity={0.7}
    >
      <View style={s.deviceRow}>
        <Text style={s.typeIcon}>{typeIcon}</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.deviceName} numberOfLines={1}>
            {item.name || maskMac(item.mac_address)}
          </Text>
          <Text style={s.deviceMac}>{maskMac(item.mac_address)}</Text>
        </View>
        <View style={{ alignItems: 'flex-end', gap: 4 }}>
          <RSSIBars rssi={item.rssi || -90} />
          <Text style={[s.rssiText, { color: rssiColor(item.rssi || -90) }]}>
            {item.rssi} dBm
          </Text>
        </View>
      </View>

      <View style={s.badgeRow}>
        {item.manufacturer ? <Badge label={item.manufacturer} color={colors.accent} /> : null}
        {vulnCount > 0 && <Badge label={`⚠ ${vulnCount} VULN`} color={colors.red} />}
        {hasGATT && <Badge label="GATT" color={colors.green} />}
        {item.simulated && <Badge label="SIM" color={colors.yellow} />}
        <Text style={s.lastSeen}>{relTime(item.last_seen)}</Text>
      </View>
    </TouchableOpacity>
  );
}

// ── Tracker item ──────────────────────────────────────────────────────────────

function TrackerItem({ item, onFind }) {
  return (
    <View style={[s.deviceCard, { borderColor: colors.red + '50' }]}>
      <View style={s.deviceRow}>
        <Text style={s.typeIcon}>🏷</Text>
        <View style={{ flex: 1 }}>
          <Text style={s.deviceName}>{item.tracker_type || 'Unknown Tracker'}</Text>
          <Text style={s.deviceMac}>{maskMac(item.mac_address)}</Text>
          <Text style={[s.deviceMac, { marginTop: 2 }]}>
            RSSI: {item.rssi} dBm · {relTime(item.last_seen)}
          </Text>
        </View>
        <RSSIBars rssi={item.rssi || -90} />
      </View>
      <TouchableOpacity style={s.findBtn} onPress={() => onFind(item)}>
        <Text style={s.findBtnText}>Find</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Log item ──────────────────────────────────────────────────────────────────

function LogItem({ item }) {
  return (
    <View style={s.logRow}>
      <Text style={[s.logAction, { color: item.success ? colors.green : colors.red }]}>
        {item.action}
      </Text>
      <Text style={s.logMac}>{maskMac(item.mac_address)}</Text>
      <Text style={s.logTime}>{relTime(item.timestamp)}</Text>
      <Badge label={item.success ? 'OK' : 'ERR'} color={item.success ? colors.green : colors.red} />
    </View>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function BLEScannerScreen() {
  const [tab, setTab] = useState('devices');
  const [devices, setDevices] = useState([]);
  const [trackers, setTrackers] = useState([]);
  const [logs, setLogs] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [duration, setDuration] = useState(10);
  const [simulation, setSimulation] = useState(false);
  const [loading, setLoading] = useState(false);

  // ── Data loading ──────────────────────────────────────────────────────────

  const loadDevices = useCallback(async () => {
    try {
      const d = await apiJSON('/api/ble/devices');
      setDevices(d.devices || []);
    } catch (_) {}
  }, []);

  const loadTrackers = useCallback(async () => {
    try {
      const d = await apiJSON('/api/ble/trackers');
      setTrackers(d.trackers || []);
    } catch (_) {}
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const d = await apiJSON('/api/ble/logs?limit=100');
      setLogs(d.logs || []);
    } catch (_) {}
  }, []);

  useEffect(() => {
    loadDevices();
    loadTrackers();
    loadLogs();
  }, [loadDevices, loadTrackers, loadLogs]);

  // ── Scan ──────────────────────────────────────────────────────────────────

  const doScan = async () => {
    setScanning(true);
    try {
      const d = await apiJSON(`/api/ble/scan?duration=${duration}`);
      setDevices(d.devices || []);
      setSimulation(!!d.simulation);
      loadTrackers();
      loadLogs();
    } catch (err) {
      Alert.alert('Erreur BLE', err.message || 'Scan failed');
    }
    setScanning(false);
  };

  // ── Long press actions ────────────────────────────────────────────────────

  const handleLongPress = (device) => {
    Alert.alert(
      device.name || device.mac_address,
      'Choisir une action',
      [
        {
          text: 'Fingerprint',
          onPress: () => doAction(device, 'fingerprint'),
        },
        {
          text: 'Vuln Scan',
          onPress: () => doAction(device, 'vuln-scan'),
        },
        {
          text: 'Track RSSI',
          onPress: () => doAction(device, 'track'),
        },
        {
          text: 'Locate',
          onPress: () => doLocate(device),
        },
        { text: 'Annuler', style: 'cancel' },
      ]
    );
  };

  const doAction = async (device, action) => {
    const mac = device.mac_address;
    setLoading(true);
    try {
      const d = await apiJSON(`/api/ble/devices/${mac}/${action}`, { method: 'POST' });
      const actionLabel = action === 'fingerprint' ? 'Fingerprint' : action === 'vuln-scan' ? 'Vuln Scan' : 'Track';

      if (action === 'fingerprint') {
        const gattCount = (d.gatt_services || []).length;
        Alert.alert(`${actionLabel} terminé`, `${gattCount} service(s) GATT trouvé(s).`);
      } else if (action === 'vuln-scan') {
        const count = d.count || 0;
        Alert.alert(`Vuln Scan terminé`, count > 0 ? `${count} vulnérabilité(s) détectée(s).` : 'Aucune vulnérabilité détectée.');
      } else if (action === 'track') {
        const dist = d.estimated_distance_m;
        const avgRSSI = d.avg_rssi;
        Alert.alert('Tracking RSSI', `Distance estimée: ${dist}m\nRSSI moyen: ${avgRSSI} dBm`);
      }
      loadDevices();
      loadLogs();
    } catch (err) {
      Alert.alert('Erreur', err.message);
    }
    setLoading(false);
  };

  const doLocate = async (device) => {
    const mac = device.mac_address;
    setLoading(true);
    try {
      const d = await apiJSON(`/api/ble/trackers/locate/${mac}`, { method: 'POST' });
      Alert.alert(
        'Localisation',
        `Distance estimée: ${d.estimated_distance_m}m\nRSSI moyen: ${d.avg_rssi} dBm\nMode: ${d.simulated ? 'Simulation' : 'Réel'}`
      );
      loadLogs();
    } catch (err) {
      Alert.alert('Erreur', err.message);
    }
    setLoading(false);
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <View style={s.container}>
      {/* Header */}
      <View style={s.header}>
        <View style={s.headerLeft}>
          <Text style={s.headerTitle}>BLE SCANNER</Text>
          <View style={s.statusDot}>
            <Text style={{ fontSize: 10 }}>{simulation ? '🔴' : '🟢'}</Text>
            <Text style={s.statusText}>{simulation ? 'Simulation' : 'BLE'}</Text>
          </View>
        </View>
        <ScanningPulse visible={scanning} />
      </View>

      {/* Scan section */}
      <View style={s.scanSection}>
        <View style={s.durationRow}>
          {DURATION_CHIPS.map(d => (
            <TouchableOpacity
              key={d}
              style={[s.durationChip, duration === d && s.durationChipActive]}
              onPress={() => setDuration(d)}
            >
              <Text style={[s.durationChipText, duration === d && s.durationChipTextActive]}>
                {d}s
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <TouchableOpacity
          style={[s.scanBtn, scanning && s.scanBtnDisabled]}
          onPress={doScan}
          disabled={scanning}
        >
          {scanning ? (
            <ActivityIndicator color={colors.accent} size="small" />
          ) : (
            <Text style={s.scanBtnText}>⚡ SCAN</Text>
          )}
        </TouchableOpacity>
      </View>

      {/* Loading overlay */}
      {loading && (
        <View style={s.loadingBanner}>
          <ActivityIndicator color={colors.accent} size="small" />
          <Text style={s.loadingText}>Action en cours…</Text>
        </View>
      )}

      {/* Tabs */}
      <View style={s.tabBar}>
        {TABS.map(t => (
          <TouchableOpacity
            key={t.id}
            style={[s.tabBtn, tab === t.id && s.tabBtnActive]}
            onPress={() => setTab(t.id)}
          >
            <Text style={[s.tabBtnText, tab === t.id && s.tabBtnTextActive]}>
              {t.label}
              {t.id === 'devices' && devices.length > 0 ? ` (${devices.length})` : ''}
              {t.id === 'trackers' && trackers.length > 0 ? ` (${trackers.length})` : ''}
              {t.id === 'logs' && logs.length > 0 ? ` (${logs.length})` : ''}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Tab: Appareils */}
      {tab === 'devices' && (
        <FlatList
          data={devices}
          keyExtractor={item => item.mac_address}
          renderItem={({ item }) => (
            <DeviceItem item={item} onLongPress={handleLongPress} />
          )}
          contentContainerStyle={s.listContent}
          ListEmptyComponent={
            <Text style={s.emptyText}>
              {scanning ? 'Scan en cours…' : 'Aucun appareil. Lance un scan pour découvrir les appareils BLE proches.'}
            </Text>
          }
        />
      )}

      {/* Tab: Trackers */}
      {tab === 'trackers' && (
        <FlatList
          data={trackers}
          keyExtractor={item => item.mac_address}
          renderItem={({ item }) => (
            <TrackerItem item={item} onFind={doLocate} />
          )}
          contentContainerStyle={s.listContent}
          ListEmptyComponent={
            <Text style={s.emptyText}>
              Aucun tracker détecté. Lance un scan pour trouver AirTags, Tiles ou SmartTags.
            </Text>
          }
        />
      )}

      {/* Tab: Logs */}
      {tab === 'logs' && (
        <FlatList
          data={logs}
          keyExtractor={item => String(item.id)}
          renderItem={({ item }) => <LogItem item={item} />}
          contentContainerStyle={s.listContent}
          ListEmptyComponent={
            <Text style={s.emptyText}>Aucun log.</Text>
          }
        />
      )}
    </View>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  headerTitle: {
    color: colors.accent,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 2,
    fontFamily: 'monospace',
  },
  statusDot: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.bgCard,
    borderRadius: 10,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderWidth: 1,
    borderColor: colors.border,
  },
  statusText: {
    color: colors.textMuted,
    fontSize: 10,
  },
  scanPulse: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.accent,
  },
  scanSection: {
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
    gap: 10,
  },
  durationRow: {
    flexDirection: 'row',
    gap: 8,
  },
  durationChip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.bgCard,
  },
  durationChipActive: {
    borderColor: colors.accent,
    backgroundColor: colors.accent + '20',
  },
  durationChipText: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: '600',
  },
  durationChipTextActive: {
    color: colors.accent,
  },
  scanBtn: {
    backgroundColor: colors.accent + '20',
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: 10,
    paddingVertical: 12,
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 44,
  },
  scanBtnDisabled: {
    backgroundColor: colors.bgCard,
    borderColor: colors.border,
  },
  scanBtnText: {
    color: colors.accent,
    fontWeight: '800',
    fontSize: 14,
    letterSpacing: 1,
  },
  loadingBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.bgCardLight,
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  loadingText: {
    color: colors.textMuted,
    fontSize: 12,
  },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tabBtn: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderBottomWidth: 2,
    borderBottomColor: 'transparent',
  },
  tabBtnActive: {
    borderBottomColor: colors.accent,
  },
  tabBtnText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  tabBtnTextActive: {
    color: colors.accent,
    fontWeight: '700',
  },
  listContent: {
    padding: 12,
    gap: 10,
    flexGrow: 1,
  },
  emptyText: {
    color: colors.textDim,
    textAlign: 'center',
    marginTop: 60,
    fontSize: 13,
    lineHeight: 20,
  },
  // Device card
  deviceCard: {
    backgroundColor: colors.bgCard,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 12,
    marginBottom: 8,
  },
  deviceRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 8,
  },
  typeIcon: {
    fontSize: 22,
  },
  deviceName: {
    color: colors.text,
    fontWeight: '700',
    fontSize: 14,
    marginBottom: 2,
  },
  deviceMac: {
    color: colors.textMuted,
    fontSize: 11,
    fontFamily: 'monospace',
  },
  rssiText: {
    fontSize: 10,
    fontFamily: 'monospace',
  },
  badgeRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    alignItems: 'center',
  },
  badge: {
    borderRadius: 4,
    borderWidth: 1,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '700',
  },
  lastSeen: {
    color: colors.textDim,
    fontSize: 10,
    marginLeft: 'auto',
  },
  // Find button
  findBtn: {
    marginTop: 8,
    backgroundColor: colors.red + '20',
    borderWidth: 1,
    borderColor: colors.red,
    borderRadius: 8,
    paddingVertical: 8,
    alignItems: 'center',
  },
  findBtnText: {
    color: colors.red,
    fontWeight: '700',
    fontSize: 13,
  },
  // Log row
  logRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.border + '40',
  },
  logAction: {
    width: 90,
    fontSize: 11,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  logMac: {
    flex: 1,
    color: colors.textMuted,
    fontSize: 10,
    fontFamily: 'monospace',
  },
  logTime: {
    color: colors.textDim,
    fontSize: 10,
    width: 30,
  },
});
