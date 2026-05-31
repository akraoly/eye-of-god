const BASE = import.meta.env.VITE_API_URL || '/api'

export async function sendMessage(message, sessionId = 'default') {
  const res = await fetch(`${BASE}/chat/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getMemories(type = null) {
  const url = type ? `${BASE}/memory/get?memory_type=${type}` : `${BASE}/memory/get`
  const res = await fetch(url)
  return res.json()
}

export async function saveMemory(key, value, type = 'user', importance = 0.8) {
  const res = await fetch(`${BASE}/memory/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ memory_type: type, key, value, importance }),
  })
  return res.json()
}

export async function getHealth() {
  const res = await fetch(`${BASE}/system/health`)
  return res.json()
}
