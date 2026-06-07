import AsyncStorage from '@react-native-async-storage/async-storage';

export const API_BASE = 'http://172.20.10.5:8000';

export async function getToken() {
  return await AsyncStorage.getItem('eye_token');
}

export async function setToken(token) {
  await AsyncStorage.setItem('eye_token', token);
}

export async function removeToken() {
  await AsyncStorage.removeItem('eye_token');
}

export async function apiFetch(path, options = {}) {
  const token = await getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    await removeToken();
    throw new Error('AUTH_EXPIRED');
  }
  return res;
}

export async function apiJSON(path, options = {}) {
  const res = await apiFetch(path, options);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  return res.json();
}
