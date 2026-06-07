import React from 'react';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createStackNavigator } from '@react-navigation/stack';
import { Text } from 'react-native';

import ChatScreen      from '../screens/ChatScreen';
import SocScreen       from '../screens/SocScreen';
import DiagScreen      from '../screens/DiagScreen';
import MemoryScreen    from '../screens/MemoryScreen';
import ModulesScreen   from '../screens/ModulesScreen';
import KnowledgeScreen from '../screens/KnowledgeScreen';
import LifeScreen      from '../screens/LifeScreen';
import AutonomyScreen  from '../screens/AutonomyScreen';
import ObserveScreen   from '../screens/ObserveScreen';
import VisionScreen    from '../screens/VisionScreen';
import OffensiveScreen from '../screens/OffensiveScreen';
import CodeScreen      from '../screens/CodeScreen';

import { colors } from '../utils/theme';

const Tab   = createBottomTabNavigator();
const Stack = createStackNavigator();

const TABS = [
  { name: 'Chat',    component: ChatScreen,    icon: '💬', label: 'Chat'   },
  { name: 'SOC',     component: SocScreen,     icon: '🔴', label: 'SOC'    },
  { name: 'Diag',    component: DiagScreen,    icon: '🩺', label: 'Diag'   },
  { name: 'Mémoire', component: MemoryScreen,  icon: '🧠', label: 'Mémoire'},
  { name: 'Modules', component: ModulesScreen, icon: '⚡', label: 'Modules'},
];

const HEADER = {
  headerStyle: {
    backgroundColor: colors.bgCard,
    borderBottomColor: colors.border,
    borderBottomWidth: 1,
    elevation: 0,
    shadowOpacity: 0,
  },
  headerTintColor: colors.accent,
  headerTitleStyle: { fontWeight: '700', fontSize: 15, letterSpacing: 1 },
  headerBackTitleVisible: false,
  cardStyle: { backgroundColor: colors.bg },
};

function TabNavigator() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        ...HEADER,
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
          return (
            <Text style={{ fontSize: focused ? 22 : 18, opacity: focused ? 1 : 0.55 }}>
              {tab?.icon}
            </Text>
          );
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

export default function AppNavigator() {
  return (
    <Stack.Navigator screenOptions={HEADER}>
      <Stack.Screen name="Main"      component={TabNavigator}   options={{ headerShown: false }} />
      <Stack.Screen name="Knowledge" component={KnowledgeScreen} options={{ title: '📚 Base de Savoir' }} />
      <Stack.Screen name="Life"      component={LifeScreen}      options={{ title: '🎯 Life Manager' }} />
      <Stack.Screen name="Autonomy"  component={AutonomyScreen}  options={{ title: '🤖 Autonomie' }} />
      <Stack.Screen name="Observe"   component={ObserveScreen}   options={{ title: '🔭 Observe' }} />
      <Stack.Screen name="Vision"    component={VisionScreen}    options={{ title: '👁 Vision IA' }} />
      <Stack.Screen name="Offensive" component={OffensiveScreen} options={{ title: '⚔️ Offensive Red Team' }} />
      <Stack.Screen name="Code"      component={CodeScreen}      options={{ title: '💻 Code & Shell' }} />
    </Stack.Navigator>
  );
}
