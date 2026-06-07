import 'react-native-gesture-handler';
import React, { useState, useEffect } from 'react';
import { StatusBar, View, ActivityIndicator, StyleSheet } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { SafeAreaProvider } from 'react-native-safe-area-context';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { getToken } from './src/utils/api';
import LoginScreen from './src/screens/LoginScreen';
import AppNavigator from './src/navigation/AppNavigator';
import { colors } from './src/utils/theme';

export default function App() {
  const [token, setToken] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    getToken().then(t => {
      setToken(t);
      setChecking(false);
    });
  }, []);

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
          <LoginScreen onLogin={t => setToken(t)} />
        )}
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

const s = StyleSheet.create({
  loading: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.bg },
});
