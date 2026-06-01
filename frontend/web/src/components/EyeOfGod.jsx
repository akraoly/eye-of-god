import { useEffect, useRef } from 'react'

/**
 * L'Œil vivant — réagit aux états : idle | listening | thinking | responding
 */
export default function EyeOfGod({ state = 'idle', size = 220 }) {
  const eyeRef = useRef(null)

  const stateClass = {
    idle:       'eye-idle',
    listening:  'eye-listening',
    thinking:   'eye-thinking',
    responding: 'eye-responding',
  }[state] || 'eye-idle'

  return (
    <div className={`eye-container ${stateClass}`} ref={eyeRef} style={{ width: size, height: size }}>
      {/* Halo externe */}
      <div className="eye-halo eye-halo-1" />
      <div className="eye-halo eye-halo-2" />
      <div className="eye-halo eye-halo-3" />

      {/* Anneaux orbitaux */}
      <div className="eye-ring eye-ring-1" />
      <div className="eye-ring eye-ring-2" />
      <div className="eye-ring eye-ring-3" />

      {/* Particules */}
      {Array.from({ length: 8 }, (_, i) => (
        <div key={i} className="eye-particle" style={{ '--i': i }} />
      ))}

      {/* SVG principal */}
      <svg
        className="eye-svg"
        viewBox="0 0 200 200"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <radialGradient id="irisGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#4c1d95" />
            <stop offset="40%"  stopColor="#7c3aed" />
            <stop offset="70%"  stopColor="#4f46e5" />
            <stop offset="100%" stopColor="#1e1b4b" />
          </radialGradient>
          <radialGradient id="pupilGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#7c3aed" stopOpacity="0.9" />
            <stop offset="60%"  stopColor="#312e81" stopOpacity="0.5" />
            <stop offset="100%" stopColor="#000010" stopOpacity="1" />
          </radialGradient>
          <radialGradient id="glowGrad" cx="50%" cy="35%" r="50%">
            <stop offset="0%"  stopColor="#a78bfa" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
          </radialGradient>
          <filter id="eyeBlur">
            <feGaussianBlur stdDeviation="1.5" />
          </filter>
          <filter id="glowFilter">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <clipPath id="eyeShape">
            <path d="M 10 100 Q 100 30 190 100 Q 100 170 10 100 Z" />
          </clipPath>
        </defs>

        {/* Aura externe */}
        <circle cx="100" cy="100" r="95" fill="none"
          stroke="#7c3aed" strokeWidth="0.5" opacity="0.3" />
        <circle cx="100" cy="100" r="88" fill="none"
          stroke="#4f46e5" strokeWidth="0.3" opacity="0.2" />

        {/* Forme œil — blanc */}
        <path d="M 10 100 Q 100 30 190 100 Q 100 170 10 100 Z"
          fill="#05010a" />

        {/* Iris */}
        <circle cx="100" cy="100" r="48"
          fill="url(#irisGrad)"
          clipPath="url(#eyeShape)"
          filter="url(#glowFilter)" />

        {/* Détail iris — stries */}
        {Array.from({ length: 12 }, (_, i) => {
          const angle = (i / 12) * Math.PI * 2
          const x1 = 100 + Math.cos(angle) * 26
          const y1 = 100 + Math.sin(angle) * 26
          const x2 = 100 + Math.cos(angle) * 44
          const y2 = 100 + Math.sin(angle) * 44
          return (
            <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
              stroke="#a78bfa" strokeWidth="0.5" opacity="0.4"
              clipPath="url(#eyeShape)" />
          )
        })}

        {/* Pupille */}
        <circle cx="100" cy="100" r="22"
          fill="url(#pupilGrad)"
          clipPath="url(#eyeShape)" />

        {/* Cœur lumineux */}
        <circle cx="100" cy="100" r="10"
          fill="#7c3aed" opacity="0.7"
          clipPath="url(#eyeShape)" />
        <circle cx="100" cy="100" r="5"
          fill="#c4b5fd" opacity="0.9"
          clipPath="url(#eyeShape)" />

        {/* Reflets */}
        <ellipse cx="115" cy="86" rx="7" ry="4"
          fill="url(#glowGrad)" opacity="0.6"
          clipPath="url(#eyeShape)" />
        <circle cx="87" cy="112" r="3"
          fill="white" opacity="0.2"
          clipPath="url(#eyeShape)" />

        {/* Contour paupières */}
        <path d="M 10 100 Q 100 30 190 100"
          fill="none" stroke="#7c3aed" strokeWidth="1" opacity="0.6" />
        <path d="M 10 100 Q 100 170 190 100"
          fill="none" stroke="#4f46e5" strokeWidth="1" opacity="0.6" />

        {/* Cils supérieurs */}
        {[20, 50, 80, 100, 120, 150, 180].map((x, i) => {
          const y = i < 3 ? 100 - (x / 190) * 50 + 10
                         : i === 3 ? 50
                         : 100 - ((190 - x) / 190) * 50 + 10
          return (
            <line key={i}
              x1={x} y1={y}
              x2={x + (x < 100 ? -3 : 3)} y2={y - 6}
              stroke="#7c3aed" strokeWidth="0.8" opacity="0.5" />
          )
        })}
      </svg>

      {/* Label état */}
      <div className="eye-state-label">
        {{ idle: '', listening: '👂 écoute', thinking: '⚡ réflexion', responding: '✨ réponse' }[state]}
      </div>
    </div>
  )
}
