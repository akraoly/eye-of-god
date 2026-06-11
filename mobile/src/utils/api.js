import AsyncStorage from '@react-native-async-storage/async-storage';

const STORAGE_KEY_SERVER = 'eye_server_url';
// No hardcoded IP — forces server config on first run and avoids stale address when changing WiFi
const DEFAULT_BASE = '';

export let API_BASE = DEFAULT_BASE;

export async function initApiBase() {
  const stored = await AsyncStorage.getItem(STORAGE_KEY_SERVER);
  if (stored) API_BASE = stored;
  return API_BASE;
}

export async function getApiBase() {
  const stored = await AsyncStorage.getItem(STORAGE_KEY_SERVER);
  if (stored) API_BASE = stored;
  return API_BASE || DEFAULT_BASE;
}

export async function setApiBase(url) {
  const clean = url.trim().replace(/\/$/, '');
  await AsyncStorage.setItem(STORAGE_KEY_SERVER, clean);
  API_BASE = clean;
}

export async function clearApiBase() {
  await AsyncStorage.removeItem(STORAGE_KEY_SERVER);
  API_BASE = '';
}

// ─── Connectivity check ───────────────────────────────────────────────────────
// Returns true if the server at `url` responds within `timeoutMs`.
// A 4xx response still means the server is up — only network errors return false.
export async function testServer(url, timeoutMs = 3000) {
  if (!url) return false;
  try {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const res = await fetch(`${url.replace(/\/$/, '')}/`, { signal: controller.signal });
    clearTimeout(timer);
    return res.status < 500;
  } catch {
    return false;
  }
}

// ─── Auto-discover ────────────────────────────────────────────────────────────
// Scans private subnets in parallel using a pool of workers.
// `onProgress(0-100)` is called as work advances.
// Resolves with the first responding URL, or null after 20s.
export function autoDiscover(port = 8001, onProgress) {
  // Common subnets: home routers, hotel WiFi, iPhone hotspot, Android hotspot
  const subnets = [
    '192.168.1', '192.168.0', '192.168.2', '192.168.10',
    '192.168.50', '192.168.100', '192.168.43',
    '10.0.0', '10.0.1', '10.10.0', '10.8.0',
    '172.20.10', '172.16.0', '172.16.1',
  ];

  // Priority hosts: gateway (.1), common DHCP pool start (.100-.102), static (.2-.5)
  const priorityHosts = [1, 2, 3, 4, 5, 100, 101, 102, 10, 11, 50, 200, 254];

  const queue = [];
  for (const h of priorityHosts) {
    for (const s of subnets) queue.push(`http://${s}.${h}:${port}`);
  }
  // Full sweep of two most common subnets as fallback
  for (let i = 6; i <= 99; i++)    queue.push(`http://192.168.1.${i}:${port}`);
  for (let i = 6; i <= 99; i++)    queue.push(`http://192.168.0.${i}:${port}`);
  for (let i = 103; i <= 199; i++) queue.push(`http://192.168.1.${i}:${port}`);
  for (let i = 103; i <= 199; i++) queue.push(`http://192.168.0.${i}:${port}`);

  const total = queue.length;
  let done = 0;
  let idx = 0;

  return new Promise((resolve) => {
    let resolved = false;

    // Pool of 12 concurrent workers — prevents flooding the network stack
    async function worker() {
      while (idx < total && !resolved) {
        const url = queue[idx++];
        const ok = await testServer(url, 900);
        done++;
        onProgress?.(Math.round((done / total) * 100));
        if (ok && !resolved) {
          resolved = true;
          resolve(url);
          return;
        }
      }
      if (done >= total && !resolved) resolve(null);
    }

    const POOL = 12;
    for (let i = 0; i < POOL; i++) worker();

    // Hard timeout — never hang more than 20s
    setTimeout(() => {
      if (!resolved) { resolved = true; resolve(null); }
    }, 20_000);
  });
}

// ─── Logout global callback ───────────────────────────────────────────────────
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

export function decodeJwtPayload(token) {
  try {
    const part = token.split('.')[1];
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

export function isTokenValid(token) {
  if (!token) return false;
  const payload = decodeJwtPayload(token);
  if (!payload?.exp) return false;
  return payload.exp * 1000 > Date.now() + 30_000;
}

// ─── Authenticated fetch ──────────────────────────────────────────────────────
export async function apiFetch(path, options = {}) {
  const base = await getApiBase();
  const token = await getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${base}${path}`, { ...options, headers });
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
