import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
  ScrollView,
} from 'react-native';
import {
  getApiBase, setApiBase, setToken,
  testServer, autoDiscover, isTokenValid,
} from '../utils/api';
import { colors, fonts } from '../utils/theme';

export default function LoginScreen({ onLogin, serverUnreachable = false, savedToken = null }) {
  const [username,     setUsername]    = useState('admin');
  const [password,     setPassword]    = useState('');
  const [serverUrl,    setServerUrl]   = useState('');
  const [loading,      setLoading]     = useState(false);
  const [showServer,   setShowServer]  = useState(false);
  const [scanning,     setScanning]    = useState(false);
  const [scanProgress, setScanProgress] = useState(0);
  // 'idle' | 'scanning' | 'found' | 'notfound'
  const [scanStatus,   setScanStatus]  = useState('idle');
  const cancelRef = useRef(false);

  useEffect(() => {
    getApiBase().then(url => {
      setServerUrl(url || '');
      // Auto-open server config if no URL is stored OR server is unreachable
      if (!url || serverUnreachable) setShowServer(true);
    });
  }, [serverUnreachable]);

  const handleAutoDetect = useCallback(async () => {
    cancelRef.current = false;
    setScanning(true);
    setScanStatus('scanning');
    setScanProgress(0);

    const found = await autoDiscover(8001, (p) => {
      if (!cancelRef.current) setScanProgress(p);
    });

    if (cancelRef.current) return;
    setScanning(false);

    if (found) {
      setScanStatus('found');
      setServerUrl(found);

      // Auto-reconnect if caller passed a still-valid JWT — no credentials needed
      if (savedToken && isTokenValid(savedToken)) {
        await setApiBase(found);
        onLogin(savedToken);
        return;
      }
    } else {
      setScanStatus('notfound');
    }
  }, [savedToken, onLogin]);

  // Cancel scan if user navigates away
  useEffect(() => () => { cancelRef.current = true; }, []);

  async function handleLogin() {
    if (!username || !password) {
      Alert.alert('Erreur', 'Identifiant et mot de passe requis');
      return;
    }
    const base = serverUrl.trim().replace(/\/$/, '');
    if (!base) {
      Alert.alert('Erreur', 'Configure d\'abord l\'URL du serveur (⚙️ Configurer le serveur)');
      setShowServer(true);
      return;
    }
    setLoading(true);
    try {
      await setApiBase(base);
      const res = await fetch(`${base}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Identifiants incorrects');
      await setToken(data.access_token);
      onLogin(data.access_token);
    } catch (e) {
      Alert.alert('Connexion échouée', e.message);
    } finally {
      setLoading(false);
    }
  }

  const scanStatusColor = scanStatus === 'found' ? colors.green : scanStatus === 'notfound' ? colors.red : colors.accent;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={s.container}
    >
      <ScrollView
        contentContainerStyle={s.scroll}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        {/* ── Logo ─────────────────────────────────────────────────────── */}
        <View style={s.logoWrap}>
          <Text style={s.logoEye}>👁️</Text>
          <Text style={s.logoTitle}>L'Œil de Dieu</Text>
          <Text style={s.logoSub}>Plateforme IA Personnelle</Text>
        </View>

        {/* ── Banner serveur inaccessible ───────────────────────────────── */}
        {serverUnreachable && (
          <View style={s.alertBanner}>
            <Text style={s.alertTitle}>⚠️  Serveur inaccessible</Text>
            <Text style={s.alertBody}>
              L'IP du serveur a changé (nouveau WiFi).{'\n'}
              Utilise la détection auto ou saisis la nouvelle URL.
            </Text>
          </View>
        )}

        {/* ── Formulaire ───────────────────────────────────────────────── */}
        <View style={s.form}>
          <Text style={s.label}>IDENTIFIANT</Text>
          <TextInput
            style={s.input}
            value={username}
            onChangeText={setUsername}
            placeholder="admin"
            placeholderTextColor={colors.textDim}
            autoCapitalize="none"
            autoCorrect={false}
          />
          <Text style={s.label}>MOT DE PASSE</Text>
          <TextInput
            style={s.input}
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••"
            placeholderTextColor={colors.textDim}
            secureTextEntry
          />

          {/* ── Section serveur ────────────────────────────────────────── */}
          <TouchableOpacity onPress={() => setShowServer(v => !v)} style={s.serverToggle}>
            <Text style={s.serverToggleText}>
              {showServer ? '▲ Masquer le serveur' : '⚙️ Configurer le serveur'}
            </Text>
          </TouchableOpacity>

          {showServer && (
            <View style={s.serverSection}>
              <Text style={s.label}>URL SERVEUR</Text>
              <TextInput
                style={[s.input, scanStatus === 'found' && s.inputFound, scanStatus === 'notfound' && s.inputNotFound]}
                value={serverUrl}
                onChangeText={(v) => { setServerUrl(v); setScanStatus('idle'); }}
                placeholder="http://192.168.x.x:8001"
                placeholderTextColor={colors.textDim}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="url"
              />

              {/* Statut scan */}
              {scanStatus !== 'idle' && (
                <Text style={[s.scanMsg, { color: scanStatusColor }]}>
                  {scanStatus === 'scanning' && `🔍 Scan en cours… ${scanProgress}%`}
                  {scanStatus === 'found'    && `✓ Serveur trouvé : ${serverUrl}`}
                  {scanStatus === 'notfound' && '✗ Aucun serveur trouvé — vérifie que tu es sur le même WiFi'}
                </Text>
              )}

              {/* Barre de progression */}
              {scanning && (
                <View style={s.progressTrack}>
                  <View style={[s.progressFill, { width: `${scanProgress}%` }]} />
                </View>
              )}

              {/* Bouton auto-detect */}
              <TouchableOpacity
                style={[s.scanBtn, scanning && s.scanBtnBusy]}
                onPress={handleAutoDetect}
                disabled={scanning}
                activeOpacity={0.8}
              >
                {scanning
                  ? <ActivityIndicator color={colors.accent} size="small" />
                  : <Text style={s.scanBtnText}>🔍  AUTO-DÉTECTER LE SERVEUR</Text>
                }
              </TouchableOpacity>

              {savedToken && isTokenValid(savedToken) && (
                <Text style={s.autoLoginHint}>
                  💡 Session précédente détectée — la reconnexion sera automatique après détection.
                </Text>
              )}

              <Text style={s.hint}>
                Assure-toi d'être sur le même WiFi que le serveur.{'\n'}
                La détection scanne automatiquement ton réseau local.
              </Text>
            </View>
          )}

          {/* ── Bouton connexion ─────────────────────────────────────────── */}
          <TouchableOpacity
            style={[s.btn, (loading || scanning) && s.btnDisabled]}
            onPress={handleLogin}
            disabled={loading || scanning}
            activeOpacity={0.8}
          >
            {loading
              ? <ActivityIndicator color={colors.bg} />
              : <Text style={s.btnText}>CONNEXION</Text>
            }
          </TouchableOpacity>
        </View>

        <Text style={s.footer}>v8.1 · FastAPI · Claude Sonnet 4.6</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container:  { flex: 1, backgroundColor: colors.bg },
  scroll:     { flexGrow: 1, justifyContent: 'center', paddingHorizontal: 28, paddingVertical: 40 },
  logoWrap:   { alignItems: 'center', marginBottom: 36 },
  logoEye:    { fontSize: 64, marginBottom: 12 },
  logoTitle:  { fontSize: 26, fontWeight: '700', color: colors.accent, letterSpacing: 2, fontFamily: fonts?.mono },
  logoSub:    { fontSize: 12, color: colors.textMuted, marginTop: 4, letterSpacing: 1 },

  alertBanner: {
    backgroundColor: '#ef444415',
    borderWidth: 1,
    borderColor: '#ef4444',
    borderRadius: 10,
    padding: 14,
    marginBottom: 20,
  },
  alertTitle: { color: '#ef4444', fontWeight: '800', fontSize: 14, marginBottom: 4 },
  alertBody:  { color: '#ef4444cc', fontSize: 12, lineHeight: 18 },

  form:         { gap: 8 },
  label:        { fontSize: 10, color: colors.accent, letterSpacing: 2, marginBottom: 2, marginTop: 10 },
  input: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 14,
    color: colors.text,
    fontSize: 15,
    fontFamily: 'monospace',
  },
  inputFound:    { borderColor: colors.green },
  inputNotFound: { borderColor: '#ef4444' },

  serverToggle:     { marginTop: 14, marginBottom: 2 },
  serverToggleText: { color: colors.accent, fontSize: 12, opacity: 0.8 },
  serverSection:    { gap: 8, marginTop: 4 },

  scanMsg: { fontSize: 12, lineHeight: 16 },

  progressTrack: {
    height: 3,
    backgroundColor: colors.border,
    borderRadius: 2,
    overflow: 'hidden',
    marginVertical: 4,
  },
  progressFill: {
    height: '100%',
    backgroundColor: colors.accent,
    borderRadius: 2,
  },

  scanBtn: {
    borderWidth: 1,
    borderColor: colors.accent,
    borderRadius: 8,
    padding: 12,
    alignItems: 'center',
    backgroundColor: colors.accent + '15',
    marginTop: 4,
    minHeight: 44,
    justifyContent: 'center',
  },
  scanBtnBusy:  { opacity: 0.6 },
  scanBtnText:  { color: colors.accent, fontWeight: '800', fontSize: 13, letterSpacing: 1 },

  autoLoginHint: {
    color: colors.accent,
    fontSize: 11,
    lineHeight: 16,
    opacity: 0.75,
    fontStyle: 'italic',
  },
  hint: { color: colors.textDim, fontSize: 11, lineHeight: 16 },

  btn: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 22,
  },
  btnDisabled: { opacity: 0.5 },
  btnText:     { color: colors.bg, fontWeight: '800', fontSize: 15, letterSpacing: 2 },

  footer: { textAlign: 'center', color: colors.textDim, fontSize: 11, marginTop: 36 },
});
