import { useState, useEffect, useRef } from 'react'
import { login } from '../utils/auth'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)
  const [shake,    setShake]    = useState(false)
  const usernameRef = useRef(null)

  useEffect(() => { usernameRef.current?.focus() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setLoading(true)
    setError('')
    try {
      await login(username.trim(), password)
      onLogin()
    } catch (err) {
      setError(err.message)
      setShake(true)
      setTimeout(() => setShake(false), 600)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-bg">
      {/* Étoiles simulées */}
      <Stars />

      <div className={`login-card ${shake ? 'shake' : ''}`}>
        {/* Œil animé */}
        <div className="login-eye">
          <svg viewBox="0 0 120 80" width="110" height="74">
            <defs>
              <radialGradient id="iris-g" cx="50%" cy="50%" r="50%">
                <stop offset="0%"   stopColor="#a78bfa" />
                <stop offset="60%"  stopColor="#7c3aed" />
                <stop offset="100%" stopColor="#1e1b4b" />
              </radialGradient>
              <filter id="glow-l">
                <feGaussianBlur stdDeviation="3" result="b"/>
                <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
              </filter>
            </defs>
            <ellipse cx="60" cy="40" rx="55" ry="28" fill="none" stroke="#7c3aed" strokeWidth="1.5" filter="url(#glow-l)" opacity="0.6"/>
            <circle  cx="60" cy="40" r="18"  fill="url(#iris-g)" filter="url(#glow-l)"/>
            <circle  cx="60" cy="40" r="9"   fill="#0a0a1a"/>
            <circle  cx="65" cy="35" r="3"   fill="white" opacity="0.8"/>
          </svg>
        </div>

        <div className="login-title">L'Œil de Dieu</div>
        <div className="login-subtitle">Compagnon numérique personnel</div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <input
              ref={usernameRef}
              type="text"
              placeholder="Identifiant"
              value={username}
              onChange={e => setUsername(e.target.value)}
              className="login-input"
              autoComplete="username"
              disabled={loading}
            />
          </div>
          <div className="login-field">
            <input
              type="password"
              placeholder="Mot de passe"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="login-input"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>

          {error && <div className="login-error">{error}</div>}

          <button type="submit" className="login-btn" disabled={loading || !username || !password}>
            {loading ? <span className="login-spinner" /> : 'Entrer'}
          </button>
        </form>
      </div>
    </div>
  )
}

function Stars() {
  const count = 80
  const stars = Array.from({ length: count }, (_, i) => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    r: Math.random() * 1.5 + 0.3,
    o: Math.random() * 0.7 + 0.2,
    d: Math.random() * 3 + 2,
  }))
  return (
    <svg className="login-stars" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill="white" opacity={s.o}>
          <animate attributeName="opacity" values={`${s.o};${s.o * 0.2};${s.o}`} dur={`${s.d}s`} repeatCount="indefinite"/>
        </circle>
      ))}
    </svg>
  )
}
