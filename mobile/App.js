import 'react-native-gesture-handler';
import React, { useState, useEffect, useCallback } from 'react';
import { StatusBar, View, ActivityIndicator, StyleSheet } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { getToken, removeToken, isTokenValid, setLogoutCallback, initApiBase } from './src/utils/api';
import LoginScreen from './src/screens/LoginScreen';
import AppNavigator from './src/navigation/AppNavigator';
import { colors } from './src/utils/theme';

export default function App() {
  const [token, setTokenState] = useState(null);
  const [checking, setChecking] = useState(true);

  const logout = useCallback(() => {
    setTokenState(null);
  }, []);

  useEffect(() => {
    // Enregistrer le callback de logout global (pour 401 dans apiFetch / voice)
    setLogoutCallback(logout);

    // Charger l'URL serveur sauvegardée (WiFi hôtel, hotspot, etc.)
    initApiBase();

    // Valider le token au démarrage — si expiré, vider et montrer le login
    getToken().then(t => {
      if (isTokenValid(t)) {
        setTokenState(t);
      } else {
        removeToken();
        setTokenState(null);
      }
      setChecking(false);
    });
  }, [logout]);

  function handleLogin(t) {
    setTokenState(t);
  }

  if (checking) {
    return (
      <View style={s.loading}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <GestureHandlerRootView style={{ flex: 1 }}>
      <SafeAreaProvider>
        <StatusBar barStyle="light-content" backgroundColor={colors.bg} />
        {token ? (
          <NavigationContainer>
            <AppNavigator />
          </NavigationContainer>
        ) : (
          <LoginScreen onLogin={handleLogin} />
        )}
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const s = StyleSheet.create({
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.bg },
});
