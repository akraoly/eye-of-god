import React, { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator, Alert,
} from 'react-native';
import { API_BASE, setToken } from '../utils/api';
import { colors, fonts } from '../utils/theme';

export default function LoginScreen({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  async function handleLogin() {
    if (!username || !password) {
      Alert.alert('Erreur', 'Identifiant et mot de passe requis');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/login`, {
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

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      style={s.container}
    >
      <View style={s.inner}>
        {/* Logo */}
        <View style={s.logoWrap}>
          <Text style={s.logoEye}>👁️</Text>
          <Text style={s.logoTitle}>L'Œil de Dieu</Text>
          <Text style={s.logoSub}>Plateforme IA Personnelle</Text>
        </View>

        {/* Form */}
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
          <TouchableOpacity
            style={[s.btn, loading && s.btnDisabled]}
            onPress={handleLogin}
            disabled={loading}
            activeOpacity={0.8}
          >
            {loading
              ? <ActivityIndicator color={colors.bg} />
              : <Text style={s.btnText}>CONNEXION</Text>
            }
          </TouchableOpacity>
        </View>

        <Text style={s.footer}>v8.1 · FastAPI · Claude Sonnet 4.6</Text>
      </View>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  inner: { flex: 1, justifyContent: 'center', paddingHorizontal: 32 },
  logoWrap: { alignItems: 'center', marginBottom: 48 },
  logoEye: { fontSize: 64, marginBottom: 12 },
  logoTitle: { fontSize: 26, fontWeight: '700', color: colors.accent, letterSpacing: 2, fontFamily: fonts?.mono },
  logoSub: { fontSize: 12, color: colors.textMuted, marginTop: 4, letterSpacing: 1 },
  form: { gap: 8 },
  label: { fontSize: 10, color: colors.accent, letterSpacing: 2, marginBottom: 4, marginTop: 8 },
  input: {
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 8,
    padding: 14,
    color: colors.text,
    fontSize: 16,
    fontFamily: 'monospace',
  },
  btn: {
    backgroundColor: colors.accent,
    borderRadius: 8,
    padding: 16,
    alignItems: 'center',
    marginTop: 20,
  },
  btnDisabled: { opacity: 0.6 },
  btnText: { color: colors.bg, fontWeight: '800', fontSize: 15, letterSpacing: 2 },
  footer: { textAlign: 'center', color: colors.textDim, fontSize: 11, marginTop: 48 },
});
