import React from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, ScrollView,
} from 'react-native';
import { colors } from '../utils/theme';

const MODULES = [
  { name: 'Knowledge',   icon: '📚', label: 'Base de Savoir', desc: 'Recherche & ingestion',    color: '#38bdf8' },
  { name: 'Life',        icon: '🎯', label: 'Life Manager',   desc: 'Objectifs & habitudes',    color: '#6ee7b7' },
  { name: 'Autonomy',    icon: '🤖', label: 'Autonomie',      desc: 'Tâches & moniteurs',       color: '#f59e0b' },
  { name: 'Observe',     icon: '🔭', label: 'Observe',        desc: 'Analyse IA du système',    color: '#a78bfa' },
  { name: 'Vision',      icon: '👁',  label: 'Vision IA',    desc: 'Capture & analyse image',  color: '#00d4ff' },
  { name: 'Offensive',   icon: '⚔️', label: 'Offensive',    desc: '4 niveaux Red Team + C2',  color: '#f97316' },
  { name: 'Code',        icon: '💻', label: 'Code & Shell',  desc: 'Explorateur + terminal',   color: '#10b981' },
  { name: 'Omniscience', icon: '🌍', label: 'Omniscience',   desc: 'Dashboard global',         color: '#8b5cf6' },
  { name: 'AudioCapture',icon: '🎤', label: 'Audio Capture', desc: 'Enregistrement & détection',color: '#ec4899' },
  { name: 'CameraScan',  icon: '📷', label: 'Caméras IP',    desc: 'ONVIF + CVE scan',         color: '#f59e0b' },
  { name: 'NetworkSniffer',icon:'📡',label: 'Network Sniffer',desc: 'Capture & analyse réseau', color: '#14b8a6' },
  { name: 'BLEScanner',  icon: '🔵', label: 'BLE Scanner',   desc: 'Bluetooth & trackers',     color: '#3b82f6' },
  { name: 'SDR',         icon: '📻', label: 'SDR Control',   desc: 'HackRF · RTL-SDR · Replay',color: '#6366f1' },
  { name: 'RFID',        icon: '💳', label: 'RFID Badge',    desc: 'Proxmark3 · Clone · Dump', color: '#d946ef' },
  { name: 'Mitre',       icon: '🎯', label: 'MITRE ATT&CK',  desc: 'Graphe d\'attaque + heatmap',color: '#ef4444' },
  { name: 'Reports',     icon: '📋', label: 'Rapports Audit',desc: 'PDF · HTML · DOCX',        color: '#22c55e' },
];

export default function ModulesScreen({ navigation }) {
  return (
    <ScrollView style={s.container} contentContainerStyle={s.content}>
      <View style={s.header}>
        <Text style={s.eyeIcon}>👁️</Text>
        <Text style={s.title}>L'ŒEIL DE DIEU</Text>
        <Text style={s.sub}>Modules opérationnels</Text>
      </View>

      <View style={s.grid}>
        {MODULES.map(m => (
          <TouchableOpacity
            key={m.name}
            style={[s.card, { borderColor: m.color + '55' }]}
            onPress={() => navigation.navigate(m.name)}
            activeOpacity={0.75}
          >
            <View style={[s.iconWrap, { backgroundColor: m.color + '18' }]}>
              <Text style={s.icon}>{m.icon}</Text>
            </View>
            <Text style={[s.cardLabel, { color: m.color }]}>{m.label}</Text>
            <Text style={s.cardDesc}>{m.desc}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <View style={s.footer}>
        <Text style={s.footerText}>AEGIS AI · v8.0.0</Text>
      </View>
    </ScrollView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, paddingBottom: 32 },
  header: { alignItems: 'center', marginBottom: 24, paddingTop: 8 },
  eyeIcon: { fontSize: 42, marginBottom: 6 },
  title: { fontSize: 18, fontWeight: '800', color: colors.accent, letterSpacing: 3 },
  sub: { fontSize: 11, color: colors.textMuted, letterSpacing: 2, marginTop: 4 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  card: {
    width: '47%',
    backgroundColor: colors.bgCard,
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    gap: 8,
  },
  iconWrap: {
    width: 44, height: 44, borderRadius: 12,
    justifyContent: 'center', alignItems: 'center',
    marginBottom: 4,
  },
  icon: { fontSize: 22 },
  cardLabel: { fontSize: 13, fontWeight: '700', letterSpacing: 0.5 },
  cardDesc: { fontSize: 11, color: colors.textMuted, lineHeight: 15 },
  footer: { alignItems: 'center', marginTop: 24 },
  footerText: { fontSize: 10, color: colors.textDim, letterSpacing: 2 },
});
