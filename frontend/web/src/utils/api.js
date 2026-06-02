import { apiFetch } from './auth'

export async function sendMessage(message, sessionId = 'default') {
  const res = await apiFetch('/chat/', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getMemories(type = null) {
  const url = type ? `/memory/get?memory_type=${type}` : '/memory/get'
  const res = await apiFetch(url)
  return res.json()
}

export async function saveMemory(key, value, type = 'user', importance = 0.8) {
  const res = await apiFetch('/memory/save', {
    method: 'POST',
    body: JSON.stringify({ memory_type: type, key, value, importance }),
  })
  return res.json()
}

export async function getHealth() {
  const res = await apiFetch('/system/health')
  return res.json()
}

export async function loadHistory(sessionId, limit = 30) {
  const res = await apiFetch(`/chat/history/${sessionId}?limit=${limit}`)
  if (!res.ok) return []
  const data = await res.json()
  return data.messages || []
}

export function resetSession() {
  const id = crypto.randomUUID()
  localStorage.setItem('eye_session_id', id)
  return id
}
