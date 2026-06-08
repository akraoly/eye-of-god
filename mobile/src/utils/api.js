import AsyncStorage from '@react-native-async-storage/async-storage';

export const API_BASE = 'http://172.20.10.5:8001';

// ─── Logout global callback (enregistré par App.js) ──────────────────────────
let _logoutCallback = null;
export function setLogoutCallback(fn) { _logoutCallback = fn; }
export function triggerLogout() {
  removeToken();
  _logoutCallback?.();
}

// ─── Token JWT ────────────────────────────────────────────────────────────────
export async function getToken() {
  return await AsyncStorage.getItem('eye_token');
}
export async function setToken(token) {
  await AsyncStorage.setItem('eye_token', token);
}
export async function removeToken() {
  await AsyncStorage.removeItem('eye_token');
}

// Décode le payload JWT (sans vérification de signature)
export function decodeJwtPayload(token) {
  try {
    const part = token.split('.')[1];
    // React Native n'a pas atob — décodage manuel base64
    const base64 = part.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '=='.slice(0, (4 - base64.length % 4) % 4);
    const json = decodeURIComponent(
      Array.from(atob ? atob(padded) : Buffer.from(padded, 'base64').toString('binary'))
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(json);
  } catch {
    return null;
  }
}

// Retourne true si le token existe ET n'est pas expiré
export function isTokenValid(token) {
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  // exp en secondes UNIX
  return payload.exp * 1000 > Date.now() + 30_000; // 30s de marge
}

// ─── Fetch authentifié ────────────────────────────────────────────────────────
export async function apiFetch(path, options = {}) {
  const token = await getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    triggerLogout();
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
