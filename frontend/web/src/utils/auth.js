const TOKEN_KEY = 'eye_token'
const USER_KEY  = 'eye_user'

export const auth = {
  getToken: ()  => localStorage.getItem(TOKEN_KEY),
  getUser:  ()  => { try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') } catch { return null } },

  save(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },

  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },

  isLoggedIn: () => !!localStorage.getItem(TOKEN_KEY),
}

const BASE = import.meta.env.VITE_API_URL || '/api'

// fetch authentifié — redirige vers /login si 401
export async function apiFetch(path, options = {}) {
  const token = auth.getToken()
  const headers = { 'Content-Type': 'application/json', ...options.headers }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE}${path}`, { ...options, headers })

  if (res.status === 401) {
    auth.clear()
    window.location.reload()
    throw new Error('Session expirée')
  }
  return res
}

export async function login(username, password) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err.detail || 'Erreur de connexion')
  }
  const data = await res.json()
  auth.save(data.access_token, { username: data.username, display_name: data.display_name })
  return data
}

export function logout() {
  auth.clear()
  window.location.reload()
}
