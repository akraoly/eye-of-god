/**
 * SDRScreen — Software Defined Radio control for mobile.
 * Hardware status, animated waterfall, frequency/mod/gain controls, action grid, recordings list.
 */
import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  TextInput,
  ActivityIndicator,
  FlatList,
  Alert,
} from 'react-native';
import { colors } from '../../utils/theme';
import { apiJSON, apiFetch } from '../../utils/api';

const MODULATIONS = ['FM', 'AM', 'LSB', 'USB', 'NFM'];

// ── Animated Waterfall ────────────────────────────────────────────────────────
function WaterfallView({ startMhz, endMhz, peaks }) {
  const NUM_COLS = 16;
  const NUM_ROWS = 8;
  const [grid, setGrid] = useState(() =>
    Array.from({ length: NUM_ROWS }, () => Array(NUM_COLS).fill(0))
  );
  const intervalRef = useRef(null);

  function powerToColor(norm) {
    if (norm < 0.33) {
      const t = norm / 0.33;
      return `rgb(0, ${Math.round(t * 80)}, ${Math.round(80 + t * 175)})`;
    } else if (norm < 0.66) {
      const t = (norm - 0.33) / 0.33;
      return `rgb(${Math.round(t * 255)}, ${Math.round(80 + t * 175)}, ${Math.round(255 - t * 200)})`;
    } else {
      const t = (norm - 0.66) / 0.34;
      return `rgb(255, ${Math.round(255 - t * 150)}, ${Math.round(55 - t * 55)})`;
    }
  }

  useEffect(() => {
    const span = endMhz - startMhz || 1;
    const knownPeaks = peaks?.length
      ? peaks.map(p => p.frequency_mhz)
      : [88.0, 92.1, 95.3, 98.7, 103.4, 107.9];

    intervalRef.current = setInterval(() => {
      setGrid(prev => {
        const newRow = Array.from({ length: NUM_COLS }, (_, c) => {
          const freq = startMhz + (c / NUM_COLS) * span;
          let power = Math.random() * 0.15;
          for (const p of knownPeaks) {
            const d = Math.abs(freq - p);
            if (d < 0.3) power = Math.max(power, 0.6 + (1 - d / 0.3) * 0.35 + Math.random() * 0.05);
            else if (d < 1) power = Math.max(power, 0.3 + (1 - d) * 0.25 + Math.random() * 0.05);
          }
          return Math.min(1, power);
        });
        return [...prev.slice(1), newRow];
      });
    }, 200);

    return () => clearInterval(intervalRef.current);
  }, [startMhz, endMhz, peaks]);

  return (
    <View style={s.waterfall}>
      {grid.map((row, ri) => (
        <View key={ri} style={s.waterfallRow}>
          {row.map((val, ci) => (
            <View
              key={ci}
              style={[s.waterfallCell, { backgroundColor: powerToColor(val) }]}
            />
          ))}
        </View>
      ))}
      <View style={s.waterfallLabels}>
        <Text style={s.waterfallLabel}>{startMhz.toFixed(1)}</Text>
        <Text style={s.waterfallLabel}>{((startMhz + endMhz) / 2).toFixed(1)} MHz</Text>
        <Text style={s.waterfallLabel}>{endMhz.toFixed(1)}</Text>
      </View>
    </View>
  );
}

// ── Gain Stepper ──────────────────────────────────────────────────────────────
function GainStepper({ value, onChange }) {
  return (
    <View style={s.gainRow}>
      <Text style={s.gainLabel}>Gain: {value} dB</Text>
      <View style={{ flexDirection: 'row', gap: 6 }}>
        <TouchableOpacity
          style={s.gainBtn}
          onPress={() => onChange(Math.max(0, value - 5))}
        >
          <Text style={s.gainBtnText}>−5</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={s.gainBtn}
          onPress={() => onChange(Math.max(0, value - 1))}
        >
          <Text style={s.gainBtnText}>−1</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={s.gainBtn}
          onPress={() => onChange(Math.min(60, value + 1))}
        >
          <Text style={s.gainBtnText}>+1</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={s.gainBtn}
          onPress={() => onChange(Math.min(60, value + 5))}
        >
          <Text style={s.gainBtnText}>+5</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

// ── Hardware Badge ────────────────────────────────────────────────────────────
function HardwareBadge({ hw }) {
  if (!hw) return <Text style={[s.hwBadge, { color: colors.textMuted }]}>⬜ …</Text>;
  if (hw.hackrf)  return <Text style={[s.hwBadge, { color: colors.green }]}>🟢 HackRF</Text>;
  if (hw.rtlsdr)  return <Text style={[s.hwBadge, { color: colors.yellow }]}>🟡 RTL-SDR</Text>;
  return <Text style={[s.hwBadge, { color: colors.red }]}>🔴 Simulation</Text>;
}

// ── Recording Item ─────────────────────────────────────────────────────────────
function RecordingItem({ rec, onReplay }) {
  return (
    <View style={s.recItem}>
      <View style={{ flex: 1 }}>
        <Text style={s.recFreq}>{rec.frequency_mhz} MHz</Text>
        <Text style={s.recMeta}>
          {rec.modulation?.toUpperCase() || '—'} · {rec.duration ?? '—'}s · {rec.protocol || 'no protocol'}
        </Text>
        {rec.simulated && <Text style={s.recSim}>SIM</Text>}
      </View>
      <TouchableOpacity style={s.replayBtn} onPress={() => onReplay(rec)}>
        <Text style={s.replayBtnText}>▶</Text>
      </TouchableOpacity>
    </View>
  );
}

// ── Main Screen ────────────────────────────────────────────────────────────────
export default function SDRScreen() {
  const [hw,          setHw]          = useState(null);
  const [freqMhz,     setFreqMhz]     = useState('100.3');
  const [span,        setSpan]        = useState(20);
  const [gain,        setGain]        = useState(40);
  const [modulation,  setModulation]  = useState('FM');
  const [status,      setStatus]      = useState('');
  const [loading,     setLoading]     = useState(false);
  const [activeAction,setActiveAction]= useState(null);
  const [peaks,       setPeaks]       = useState([]);
  const [recordings,  setRecordings]  = useState([]);
  const [recsLoading, setRecsLoading] = useState(false);
  const [gateResult,  setGateResult]  = useState(null);

  const centerMhz = parseFloat(freqMhz) || 100.3;
  const startMhz  = Math.max(0.1, centerMhz - span / 2);
  const endMhz    = centerMhz + span / 2;

  useEffect(() => {
    fetchHardware();
    fetchRecordings();
  }, []);

  async function fetchHardware() {
    try {
      const d = await apiJSON('/api/sdr/hardware');
      setHw(d);
    } catch {
      setHw({ simulation_mode: true });
    }
  }

  async function fetchRecordings() {
    setRecsLoading(true);
    try {
      const d = await apiJSON('/api/sdr/recordings?limit=20');
      setRecordings(d.recordings || []);
    } catch {
      setRecordings([]);
    } finally {
      setRecsLoading(false);
    }
  }

  const runAction = useCallback(async (action) => {
    setLoading(true);
    setActiveAction(action);
    setStatus(`${action}…`);
    try {
      switch (action) {
        case 'Scan': {
          const d = await apiJSON('/api/sdr/scan', {
            method: 'POST',
            body: JSON.stringify({ start_mhz: startMhz, end_mhz: endMhz, step_hz: 10000, gain }),
          });
          setPeaks(d.peaks || []);
          setStatus(`Scan: ${d.signals?.length ?? 0} samples, ${d.peaks?.length ?? 0} peaks`);
          break;
        }
        case 'Listen': {
          const d = await apiJSON('/api/sdr/listen', {
            method: 'POST',
            body: JSON.stringify({ frequency_mhz: centerMhz, modulation: modulation.toLowerCase(), duration: 10, gain }),
          });
          setStatus(`Listen OK — ${d.simulated ? 'simulated' : (d.file_size ? Math.round(d.file_size / 1024) + ' KB' : 'done')}`);
          await fetchRecordings();
          break;
        }
        case 'Capture IQ': {
          const d = await apiJSON('/api/sdr/capture-iq', {
            method: 'POST',
            body: JSON.stringify({ frequency_mhz: centerMhz, sample_rate: 2000000, duration: 5 }),
          });
          setStatus(`IQ captured — ${d.simulated ? 'simulated' : Math.round((d.file_size || 0) / 1024) + ' KB'}`);
          await fetchRecordings();
          break;
        }
        case 'Decode': {
          if (!recordings.length) { setStatus('No recordings to decode'); break; }
          const rec = recordings[0];
          const d = await apiJSON(`/api/sdr/recordings/${rec.id}/decode?protocol=automatic`, { method: 'POST' });
          setStatus(`Decoded ${d.count} messages (${d.protocol})`);
          await fetchRecordings();
          break;
        }
        case 'Gate Detect': {
          const d = await apiJSON('/api/sdr/gate-detect', {
            method: 'POST',
            body: JSON.stringify({ frequency_mhz: 433.92 }),
          });
          setGateResult(d);
          setStatus(`Gate codes: ${(d.captured_codes || []).join(', ') || 'none'}`);
          break;
        }
        case 'Replay': {
          if (!recordings.length) { setStatus('No recordings to replay'); break; }
          const rec = recordings[0];
          const d = await apiJSON(`/api/sdr/recordings/${rec.id}/replay`, {
            method: 'POST',
            body: JSON.stringify({ frequency_mhz: rec.frequency_mhz, repeat: 1 }),
          });
          setStatus(d.simulated ? 'Replay simulated (no HackRF)' : 'Replay transmitted');
          break;
        }
        default:
          setStatus(`Unknown action: ${action}`);
      }
    } catch (e) {
      setStatus(`${action} failed: ${e.message}`);
    } finally {
      setLoading(false);
      setActiveAction(null);
    }
  }, [startMhz, endMhz, gain, centerMhz, modulation, recordings]);

  const handleReplay = useCallback(async (rec) => {
    try {
      const d = await apiJSON(`/api/sdr/recordings/${rec.id}/replay`, {
        method: 'POST',
        body: JSON.stringify({ frequency_mhz: rec.frequency_mhz, repeat: 1 }),
      });
      Alert.alert('Replay', d.simulated ? 'Simulation only — no HackRF' : 'Signal transmitted');
    } catch (e) {
      Alert.alert('Error', e.message);
    }
  }, []);

  const ACTION_GRID = [
    { label: 'Scan',        color: colors.accent },
    { label: 'Listen',      color: colors.green },
    { label: 'Capture IQ',  color: '#a78bfa' },
    { label: 'Decode',      color: '#38bdf8' },
    { label: 'Gate Detect', color: colors.cyber },
    { label: 'Replay',      color: colors.yellow },
  ];

  return (
    <ScrollView style={s.container} contentContainerStyle={{ paddingBottom: 40 }}>
      {/* Header */}
      <View style={s.header}>
        <Text style={s.headerTitle}>SDR CONTROL</Text>
        <HardwareBadge hw={hw} />
      </View>

      {/* Simulation banner */}
      {hw?.simulation_mode && (
        <View style={s.simBanner}>
          <Text style={s.simBannerText}>
            ⚠ No SDR hardware detected — simulation mode. Connect RTL-SDR or HackRF for live signals.
          </Text>
        </View>
      )}

      {/* Waterfall */}
      <WaterfallView startMhz={startMhz} endMhz={endMhz} peaks={peaks} />

      {/* Frequency + Span */}
      <View style={s.row}>
        <View style={s.fieldGroup}>
          <Text style={s.fieldLabel}>Frequency (MHz)</Text>
          <TextInput
            style={s.input}
            value={freqMhz}
            onChangeText={setFreqMhz}
            keyboardType="numeric"
            placeholderTextColor={colors.textDim}
          />
        </View>
        <View style={s.fieldGroup}>
          <Text style={s.fieldLabel}>Span (MHz)</Text>
          <View style={s.spanRow}>
            {[5, 10, 20, 50].map(v => (
              <TouchableOpacity
                key={v}
                style={[s.spanBtn, span === v && s.spanBtnActive]}
                onPress={() => setSpan(v)}
              >
                <Text style={[s.spanBtnText, span === v && s.spanBtnTextActive]}>{v}</Text>
              </TouchableOpacity>
            ))}
          </View>
        </View>
      </View>

      {/* Gain Stepper */}
      <GainStepper value={gain} onChange={setGain} />

      {/* Modulation Chips */}
      <View style={s.modRow}>
        {MODULATIONS.map(m => (
          <TouchableOpacity
            key={m}
            style={[s.modChip, modulation === m && s.modChipActive]}
            onPress={() => setModulation(m)}
          >
            <Text style={[s.modChipText, modulation === m && s.modChipTextActive]}>{m}</Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Status */}
      {status ? (
        <View style={s.statusBar}>
          <Text style={s.statusText}>› {status}</Text>
        </View>
      ) : null}

      {/* Action Grid 2×3 */}
      <View style={s.actionGrid}>
        {ACTION_GRID.map(({ label, color }) => (
          <TouchableOpacity
            key={label}
            style={[s.actionBtn, { borderColor: color + '60', backgroundColor: color + '18' }]}
            onPress={() => runAction(label)}
            disabled={loading}
          >
            {loading && activeAction === label ? (
              <ActivityIndicator size="small" color={color} />
            ) : (
              <Text style={[s.actionBtnText, { color }]}>{label}</Text>
            )}
          </TouchableOpacity>
        ))}
      </View>

      {/* Gate Detect Result */}
      {gateResult && (
        <View style={s.card}>
          <Text style={s.cardTitle}>Gate / Remote Capture</Text>
          <Text style={s.cardLine}>Protocol: {gateResult.protocol_detected}</Text>
          <Text style={s.cardLine}>Rolling code: {gateResult.rolling_code ? 'Yes' : 'No'}</Text>
          <Text style={s.cardLine}>Modulation: {gateResult.modulation}</Text>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginTop: 6 }}>
            {(gateResult.captured_codes || []).map((code, i) => (
              <View key={i} style={s.codeBadge}>
                <Text style={s.codeText}>{code}</Text>
              </View>
            ))}
          </View>
          {gateResult.simulated && (
            <Text style={[s.cardLine, { color: colors.yellow, marginTop: 4 }]}>⚠ Simulated data</Text>
          )}
        </View>
      )}

      {/* Top 5 Signals */}
      {peaks.length > 0 && (
        <View style={s.card}>
          <Text style={s.cardTitle}>Top Signals</Text>
          {peaks.slice(0, 5).map((p, i) => (
            <View key={i} style={s.peakRow}>
              <View style={[s.peakBadge, { backgroundColor: colors.accent + '22', borderColor: colors.accent + '60' }]}>
                <Text style={[s.peakBadgeText, { color: colors.accent }]}>{p.frequency_mhz} MHz</Text>
              </View>
              <Text style={s.peakPower}>{p.power_dbm} dBm</Text>
            </View>
          ))}
        </View>
      )}

      {/* Recordings */}
      <View style={s.section}>
        <View style={s.sectionHeader}>
          <Text style={s.sectionTitle}>RECORDINGS ({recordings.length})</Text>
          <TouchableOpacity onPress={fetchRecordings}>
            <Text style={s.refreshBtn}>↺ Refresh</Text>
          </TouchableOpacity>
        </View>
        {recsLoading ? (
          <ActivityIndicator color={colors.accent} style={{ marginTop: 10 }} />
        ) : recordings.length === 0 ? (
          <Text style={s.emptyText}>No recordings yet.</Text>
        ) : (
          <FlatList
            data={recordings}
            keyExtractor={item => String(item.id)}
            renderItem={({ item }) => <RecordingItem rec={item} onReplay={handleReplay} />}
            scrollEnabled={false}
          />
        )}
      </View>

      {/* Export Button */}
      <TouchableOpacity
        style={s.exportBtn}
        onPress={() => Alert.alert('Export', 'Export recordings to file — feature coming soon.')}
      >
        <Text style={s.exportBtnText}>Export Recordings</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const s = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
    paddingHorizontal: 14,
    paddingTop: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  headerTitle: {
    color: colors.accent,
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 1.5,
    fontFamily: 'monospace',
  },
  hwBadge: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  simBanner: {
    backgroundColor: '#eab30818',
    borderWidth: 1,
    borderColor: '#eab30840',
    borderRadius: 6,
    padding: 8,
    marginBottom: 10,
  },
  simBannerText: {
    color: colors.yellow,
    fontSize: 11,
  },
  waterfall: {
    backgroundColor: '#000',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
    marginBottom: 10,
  },
  waterfallRow: {
    flexDirection: 'row',
    height: 12,
  },
  waterfallCell: {
    flex: 1,
  },
  waterfallLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingHorizontal: 6,
    paddingVertical: 3,
    backgroundColor: '#000',
  },
  waterfallLabel: {
    color: colors.textMuted,
    fontSize: 9,
    fontFamily: 'monospace',
  },
  row: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 10,
  },
  fieldGroup: {
    flex: 1,
  },
  fieldLabel: {
    color: colors.textMuted,
    fontSize: 11,
    marginBottom: 4,
  },
  input: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    color: colors.text,
    fontSize: 14,
    padding: 8,
    fontFamily: 'monospace',
  },
  spanRow: {
    flexDirection: 'row',
    gap: 4,
  },
  spanBtn: {
    flex: 1,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 5,
    paddingVertical: 7,
    alignItems: 'center',
  },
  spanBtnActive: {
    backgroundColor: colors.accent + '22',
    borderColor: colors.accent,
  },
  spanBtnText: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  spanBtnTextActive: {
    color: colors.accent,
    fontWeight: '700',
  },
  gainRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
    backgroundColor: colors.bgCard,
    borderRadius: 6,
    padding: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  gainLabel: {
    color: colors.text,
    fontSize: 12,
    fontFamily: 'monospace',
  },
  gainBtn: {
    backgroundColor: colors.bg,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 4,
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  gainBtnText: {
    color: colors.accent,
    fontSize: 11,
    fontFamily: 'monospace',
    fontWeight: '700',
  },
  modRow: {
    flexDirection: 'row',
    gap: 6,
    marginBottom: 10,
    flexWrap: 'wrap',
  },
  modChip: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 16,
    paddingVertical: 5,
    paddingHorizontal: 14,
  },
  modChipActive: {
    backgroundColor: colors.accent + '22',
    borderColor: colors.accent,
  },
  modChipText: {
    color: colors.textMuted,
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: '600',
  },
  modChipTextActive: {
    color: colors.accent,
  },
  statusBar: {
    backgroundColor: colors.bgCard,
    borderRadius: 5,
    padding: 6,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: colors.border,
  },
  statusText: {
    color: colors.textMuted,
    fontSize: 11,
    fontFamily: 'monospace',
  },
  actionGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  actionBtn: {
    width: '30%',
    flex: 1,
    minWidth: '30%',
    borderWidth: 1,
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  actionBtnText: {
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'monospace',
    textAlign: 'center',
  },
  card: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
  },
  cardTitle: {
    color: colors.accent,
    fontSize: 12,
    fontWeight: '700',
    fontFamily: 'monospace',
    marginBottom: 6,
  },
  cardLine: {
    color: colors.text,
    fontSize: 11,
    fontFamily: 'monospace',
    marginBottom: 2,
  },
  codeBadge: {
    backgroundColor: colors.cyber + '20',
    borderWidth: 1,
    borderColor: colors.cyber + '60',
    borderRadius: 4,
    paddingVertical: 3,
    paddingHorizontal: 8,
  },
  codeText: {
    color: colors.cyber,
    fontSize: 11,
    fontFamily: 'monospace',
    fontWeight: '700',
  },
  peakRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 5,
  },
  peakBadge: {
    borderWidth: 1,
    borderRadius: 4,
    paddingVertical: 2,
    paddingHorizontal: 8,
  },
  peakBadgeText: {
    fontSize: 11,
    fontFamily: 'monospace',
    fontWeight: '700',
  },
  peakPower: {
    color: colors.textMuted,
    fontSize: 11,
    fontFamily: 'monospace',
  },
  section: {
    marginBottom: 12,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  sectionTitle: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
  },
  refreshBtn: {
    color: colors.accent,
    fontSize: 12,
  },
  emptyText: {
    color: colors.textDim,
    fontSize: 12,
    fontStyle: 'italic',
    fontFamily: 'monospace',
  },
  recItem: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 6,
    padding: 10,
    marginBottom: 6,
    flexDirection: 'row',
    alignItems: 'center',
  },
  recFreq: {
    color: colors.accent,
    fontSize: 13,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  recMeta: {
    color: colors.textMuted,
    fontSize: 10,
    fontFamily: 'monospace',
    marginTop: 2,
  },
  recSim: {
    color: colors.yellow,
    fontSize: 9,
    marginTop: 2,
  },
  replayBtn: {
    backgroundColor: colors.accent + '22',
    borderWidth: 1,
    borderColor: colors.accent + '60',
    borderRadius: 6,
    width: 34,
    height: 34,
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: 8,
  },
  replayBtnText: {
    color: colors.accent,
    fontSize: 14,
    fontWeight: '700',
  },
  exportBtn: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    marginTop: 4,
    marginBottom: 20,
  },
  exportBtnText: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: '600',
    fontFamily: 'monospace',
  },
});
