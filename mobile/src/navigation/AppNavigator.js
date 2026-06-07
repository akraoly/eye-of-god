import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { Text } from 'react-native';
import ChatScreen      from '../screens/ChatScreen';
import SocScreen       from '../screens/SocScreen';
import DiagScreen      from '../screens/DiagScreen';
import KnowledgeScreen from '../screens/KnowledgeScreen';
import MemoryScreen    from '../screens/MemoryScreen';
import { colors } from '../utils/theme';

const Tab = createBottomTabNavigator();

const TABS = [
  { name: 'Chat',       component: ChatScreen,      icon: '💬', label: 'Chat' },
  { name: 'SOC',        component: SocScreen,       icon: '🔴', label: 'SOC' },
  { name: 'Diag',       component: DiagScreen,      icon: '🩺', label: 'Diag' },
  { name: 'Knowledge',  component: KnowledgeScreen, icon: '📚', label: 'Know' },
  { name: 'Memory',     component: MemoryScreen,    icon: '🧠', label: 'Mémoire' },
];

export default function AppNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerStyle: { backgroundColor: colors.bgCard, borderBottomColor: colors.border, borderBottomWidth: 1 },
        headerTintColor: colors.accent,
        headerTitleStyle: { fontWeight: '700', fontSize: 16, letterSpacing: 1 },
        tabBarStyle: {
          backgroundColor: colors.bgCard,
          borderTopColor: colors.border,
          borderTopWidth: 1,
          height: 60,
          paddingBottom: 8,
        },
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textDim,
        tabBarLabelStyle: { fontSize: 10, marginTop: 2 },
        tabBarIcon: ({ focused }) => {
          const tab = TABS.find(t => t.name === route.name);
          return <Text style={{ fontSize: focused ? 22 : 18, opacity: focused ? 1 : 0.6 }}>{tab?.icon}</Text>;
        },
      })}
    >
      {TABS.map(t => (
        <Tab.Screen
          key={t.name}
          name={t.name}
          component={t.component}
          options={{ title: t.label }}
        />
      ))}
    </Tab.Navigator>
  );
}
