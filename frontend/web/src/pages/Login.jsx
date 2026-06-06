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
    setLoading(true); setError('')
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
      <Stars />

      <div className={`login-card ${shake ? 'shake' : ''}`}>
        {/* Œil 3D animé */}
        <div className="login-eye">
          <NeuralEye />
        </div>

        <div className="login-title">L'Œil de Dieu</div>
        <div className="login-subtitle">Neural Sovereign System</div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-field">
            <input
              ref={usernameRef}
              type="text"
              placeholder="IDENTIFIANT"
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
              placeholder="CLÉ D'ACCÈS"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="login-input"
              autoComplete="current-password"
              disabled={loading}
            />
          </div>
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="login-btn" disabled={loading || !username || !password}>
            {loading ? <span className="login-spinner" /> : 'INITIALISER'}
          </button>
        </form>
      </div>
    </div>
  )
}

function NeuralEye() {
  return (
    <div style={{ position: 'relative', width: 130, height: 88, marginBottom: 4 }}>
      {/* Anneaux 3D CSS */}
      <div style={{
        position: 'absolute', inset: '-30%',
        perspective: '300px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        pointerEvents: 'none',
      }}>
        <div style={{
          position: 'absolute', width: '100%', height: '100%', borderRadius: '50%',
          border: '1px solid rgba(0, 212, 255, 0.55)',
          transform: 'rotateX(72deg)',
          animation: 'ring3d-cw 14s linear infinite',
          boxShadow: '0 0 16px rgba(0,212,255,0.3)',
        }} />
        <div style={{
          position: 'absolute', width: '82%', height: '82%', borderRadius: '50%',
          border: '1px solid rgba(139, 92, 246, 0.45)',
          transform: 'rotateX(68deg) rotateZ(55deg)',
          animation: 'ring3d-ccw 20s linear infinite',
        }} />
      </div>

      {/* SVG Œil */}
      <svg viewBox="0 0 130 88" width="130" height="88"
           style={{ filter: 'drop-shadow(0 0 16px rgba(0,212,255,0.5))' }}>
        <defs>
          <radialGradient id="li-iris" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#00f0ff" stopOpacity="0.9" />
            <stop offset="40%"  stopColor="#0080cc" stopOpacity="0.8" />
            <stop offset="70%"  stopColor="#8b5cf6" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#020010" stopOpacity="1"   />
          </radialGradient>
          <radialGradient id="li-gold" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#ffd700" stopOpacity="1"   />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0"   />
          </radialGradient>
          <filter id="li-glow">
            <feGaussianBlur stdDeviation="3.5" result="b"/>
            <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <clipPath id="li-clip">
            <path d="M 5 44 C 32 10, 98 10, 125 44 C 98 78, 32 78, 5 44 Z" />
          </clipPath>
        </defs>

        {/* Sclère */}
        <path d="M 5 44 C 32 10, 98 10, 125 44 C 98 78, 32 78, 5 44 Z" fill="#00010a" />

        {/* Paupières */}
        <path d="M 5 44 C 32 10, 98 10, 125 44" fill="none" stroke="#00d4ff" strokeWidth="1.4" opacity="0.7" filter="url(#li-glow)" />
        <path d="M 5 44 C 32 78, 98 78, 125 44" fill="none" stroke="#8b5cf6" strokeWidth="1.2" opacity="0.6" />

        {/* Iris */}
        <circle cx="65" cy="44" r="26" fill="url(#li-iris)" clipPath="url(#li-clip)" filter="url(#li-glow)" />

        {/* Pupille noire */}
        <circle cx="65" cy="44" r="13" fill="#00030f" clipPath="url(#li-clip)" />

        {/* Cœur cyan */}
        <circle cx="65" cy="44" r="6"  fill="#00f0ff" opacity="0.95" clipPath="url(#li-clip)" filter="url(#li-glow)" />

        {/* Éclat or */}
        <circle cx="65" cy="44" r="2.5" fill="#ffd700" opacity="1" clipPath="url(#li-clip)" />

        {/* Reflet */}
        <ellipse cx="75" cy="36" rx="7" ry="4" fill="white" opacity="0.5"
          clipPath="url(#li-clip)"
          style={{ transform: 'rotate(-20deg)', transformOrigin: '75px 36px' }} />

        {/* Cils */}
        {[[14,24,-6,-5],[34,15,-3,-7],[55,11,0,-7],[76,11,0,-7],[97,15,3,-7],[116,24,6,-5]].map(([x,y,dx,dy],i) => (
          <line key={i} x1={x} y1={y} x2={x+dx} y2={y+dy}
            stroke="#00d4ff" strokeWidth="0.9" opacity="0.45" strokeLinecap="round" />
        ))}
      </svg>
    </div>
  )
}

function Stars() {
  const count = 120
  const stars = Array.from({ length: count }, () => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    r: Math.random() * 1.6 + 0.2,
    o: Math.random() * 0.6 + 0.15,
    d: Math.random() * 4 + 2,
    c: Math.random() < 0.7 ? 'white' : Math.random() < 0.5 ? '#00d4ff' : '#8b5cf6',
  }))
  return (
    <svg className="login-stars" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice">
      {stars.map((s, i) => (
        <circle key={i} cx={s.x} cy={s.y} r={s.r} fill={s.c} opacity={s.o}>
          <animate attributeName="opacity" values={`${s.o};${s.o * 0.15};${s.o}`}
            dur={`${s.d}s`} repeatCount="indefinite"/>
        </circle>
      ))}
    </svg>
  )
}
