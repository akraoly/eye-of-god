/**
 * EyeOfGod — Neural Sovereign Eye avec anneaux 3D CSS + géométrie sacrée.
 * États : idle | listening | thinking | responding
 * 3D via CSS perspective + transform rotateX sur des anneaux CSS
 */

const CX = 100, CY = 100

function SeedOfLife({ orbitR, circleR, opacity = 0.07, stroke = '#00d4ff' }) {
  return (
    <g>
      {Array.from({ length: 6 }, (_, i) => {
        const a = (i * 60 - 30) * Math.PI / 180
        return (
          <circle key={i}
            cx={CX + Math.cos(a) * orbitR} cy={CY + Math.sin(a) * orbitR}
            r={circleR} fill="none" stroke={stroke} strokeWidth="0.4" opacity={opacity} />
        )
      })}
      <circle cx={CX} cy={CY} r={circleR} fill="none" stroke={stroke} strokeWidth="0.4" opacity={opacity} />
    </g>
  )
}

function Ring({ r, speed, direction = 1, dashArray, tickCount = 0,
                stroke, strokeWidth = 0.7, opacity = 0.5, tickLen = 3 }) {
  const dir = direction > 0 ? 'ring-cw' : 'ring-ccw'
  return (
    <g style={{ transformOrigin: `${CX}px ${CY}px`, animation: `${dir} ${speed}s linear infinite` }}>
      <circle cx={CX} cy={CY} r={r}
        fill="none" stroke={stroke} strokeWidth={strokeWidth}
        strokeDasharray={dashArray || 'none'} opacity={opacity} />
      {tickCount > 0 && Array.from({ length: tickCount }, (_, i) => {
        const a  = (i / tickCount) * Math.PI * 2
        const x1 = CX + Math.cos(a) * (r - tickLen / 2)
        const y1 = CY + Math.sin(a) * (r - tickLen / 2)
        const x2 = CX + Math.cos(a) * (r + tickLen / 2)
        const y2 = CY + Math.sin(a) * (r + tickLen / 2)
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2}
          stroke={stroke} strokeWidth={strokeWidth + 0.3} opacity={opacity + 0.1} />
      })}
    </g>
  )
}

export default function EyeOfGod({ state = 'idle', size = 220 }) {
  const cls = {
    idle:       'eye-idle',
    listening:  'eye-listening',
    thinking:   'eye-thinking',
    responding: 'eye-responding',
  }[state] || 'eye-idle'

  return (
    <div className={`eye-container ${cls}`}
         style={{ width: size, height: size, position: 'relative' }}>

      {/* ── Anneaux 3D CSS orbitaux ──────────────────────────────────── */}
      <div className="eye-3d-rings">
        <div className="eye-3d-ring eye-3d-ring-1" />
        <div className="eye-3d-ring eye-3d-ring-2" />
        <div className="eye-3d-ring eye-3d-ring-3" />
      </div>

      {/* ── Halos CSS ───────────────────────────────────────────────── */}
      <div className="eye-halo eye-halo-1" />
      <div className="eye-halo eye-halo-2" />

      {/* ── SVG principal ─────────────────────────────────────────── */}
      <svg className="eye-svg" viewBox="0 0 200 200"
           xmlns="http://www.w3.org/2000/svg"
           style={{ width: '100%', height: '100%', overflow: 'visible' }}>
        <defs>
          {/* Iris : cyan → violet → nuit profonde */}
          <radialGradient id="eyeIrisGrad" cx="50%" cy="45%" r="55%">
            <stop offset="0%"   stopColor="#001a2a" />
            <stop offset="25%"  stopColor="#004466" />
            <stop offset="55%"  stopColor="#003355" />
            <stop offset="80%"  stopColor="#1a0840" />
            <stop offset="100%" stopColor="#050015" />
          </radialGradient>

          {/* Pupille : cyan brillant → violet → noir */}
          <radialGradient id="eyePupilGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#00f0ff" stopOpacity="0.98" />
            <stop offset="30%"  stopColor="#00a8cc" stopOpacity="0.85" />
            <stop offset="60%"  stopColor="#8b5cf6" stopOpacity="0.7"  />
            <stop offset="85%"  stopColor="#1a0840" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#020010" stopOpacity="1"    />
          </radialGradient>

          {/* Halo cyan sur l'iris */}
          <radialGradient id="eyeCyanHalo" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#00d4ff" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#00d4ff" stopOpacity="0"    />
          </radialGradient>

          {/* Reflet supérieur */}
          <radialGradient id="eyeShineGrad" cx="60%" cy="28%" r="50%">
            <stop offset="0%"  stopColor="#e0f8ff" stopOpacity="0.85" />
            <stop offset="100%" stopColor="#00d4ff" stopOpacity="0"   />
          </radialGradient>

          {/* Gold inner light */}
          <radialGradient id="eyeGoldGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#ffd700" stopOpacity="1"   />
            <stop offset="50%"  stopColor="#f59e0b" stopOpacity="0.9" />
            <stop offset="100%" stopColor="#f59e0b" stopOpacity="0"   />
          </radialGradient>

          {/* Glow filter iris */}
          <filter id="irisGlow" x="-25%" y="-25%" width="150%" height="150%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          {/* Glow fort pupille */}
          <filter id="pupilGlow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          {/* Glow cyan intense */}
          <filter id="cyanGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="5" result="blur" />
            <feColorMatrix in="blur" type="matrix"
              values="0 0 0 0 0   0 0.8 0 0 0   1 0 0 0 0   0 0 0 1 0" result="colorized" />
            <feMerge><feMergeNode in="colorized" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>

          {/* Forme de l'œil en amande */}
          <clipPath id="eyeClip">
            <path d="M 6 100 C 34 34, 166 34, 194 100 C 166 166, 34 166, 6 100 Z" />
          </clipPath>
          <clipPath id="irisClip">
            <circle cx={CX} cy={CY} r="48" />
          </clipPath>
        </defs>

        {/* ── GÉOMÉTRIE SACRÉE ──────────────────────────────────────── */}
        <SeedOfLife orbitR={80} circleR={21} opacity={0.05} stroke="#00d4ff" />

        {/* Hexagone */}
        {Array.from({ length: 6 }, (_, i) => {
          const a1 = ((i * 60 - 30) * Math.PI) / 180
          const a2 = (((i + 1) * 60 - 30) * Math.PI) / 180
          return (
            <line key={i}
              x1={CX + Math.cos(a1) * 80} y1={CY + Math.sin(a1) * 80}
              x2={CX + Math.cos(a2) * 80} y2={CY + Math.sin(a2) * 80}
              stroke="#00d4ff" strokeWidth="0.25" opacity="0.1" />
          )
        })}

        {/* ── ANNEAUX CONCENTRIQUES SVG ──────────────────────────────── */}
        {/* Anneau externe cyan — 12 secteurs */}
        <Ring r={92} speed={52} direction={-1}
              dashArray="1.5 8" tickCount={12} tickLen={4}
              stroke="#00d4ff" strokeWidth={0.7} opacity={0.55} />

        {/* Anneau médian violet — 6 secteurs */}
        <Ring r={76} speed={30} direction={1}
              dashArray="6 3 1.5 3" tickCount={6} tickLen={3}
              stroke="#8b5cf6" strokeWidth={0.75} opacity={0.5} />

        {/* Anneau gold rapide */}
        <Ring r={62} speed={18} direction={-1}
              dashArray="2 4" tickCount={0}
              stroke="#f59e0b" strokeWidth={0.5} opacity={0.4} />

        {/* Anneau intérieur blanc-cyan */}
        <Ring r={52} speed={10} direction={1}
              dashArray="none" tickCount={0}
              stroke="#c8f0ff" strokeWidth={0.35} opacity={0.25} />

        {/* ── SCLÈRE ─────────────────────────────────────────────────── */}
        <path d="M 6 100 C 34 34, 166 34, 194 100 C 166 166, 34 166, 6 100 Z"
          fill="#00010a" />

        {/* ── IRIS : fond + couches ───────────────────────────────────── */}
        <circle cx={CX} cy={CY} r="48"
          fill="url(#eyeIrisGrad)"
          clipPath="url(#eyeClip)"
          filter="url(#irisGlow)" />

        {/* Halo cyan sur iris */}
        <circle cx={CX} cy={CY} r="48"
          fill="url(#eyeCyanHalo)"
          clipPath="url(#eyeClip)" />

        {/* Stries iris tournant — 30 stries cyan */}
        <g clipPath="url(#eyeClip)"
           style={{ transformOrigin: `${CX}px ${CY}px`, animation: 'ring-cw 22s linear infinite' }}>
          {Array.from({ length: 30 }, (_, i) => {
            const a  = (i / 30) * Math.PI * 2
            return (
              <line key={i}
                x1={CX + Math.cos(a) * 24} y1={CY + Math.sin(a) * 24}
                x2={CX + Math.cos(a) * 45} y2={CY + Math.sin(a) * 45}
                stroke="#00d4ff" strokeWidth="0.4" opacity="0.3" />
            )
          })}
        </g>

        {/* Anneau intérieur iris */}
        <g clipPath="url(#eyeClip)">
          <circle cx={CX} cy={CY} r="46"
            fill="none" stroke="#00d4ff" strokeWidth="0.6" opacity="0.35"
            strokeDasharray="4 6" />
          <circle cx={CX} cy={CY} r="38"
            fill="none" stroke="#8b5cf6" strokeWidth="0.5" opacity="0.3"
            strokeDasharray="2 8" />
        </g>

        {/* ── PUPILLE ────────────────────────────────────────────────── */}
        <circle cx={CX} cy={CY} r="23"
          fill="url(#eyePupilGrad)"
          clipPath="url(#eyeClip)"
          filter="url(#pupilGlow)" />

        {/* Constellation — 6 étoiles microscopiques */}
        {[
          [104, 94, 1.1], [93, 107, 0.9], [109, 107, 0.8],
          [95, 92, 0.7],  [106, 102, 1.3], [98, 110, 0.7],
        ].map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r}
            fill="#e0f8ff" opacity={0.55 + i * 0.05}
            clipPath="url(#eyeClip)" />
        ))}

        {/* Cœur lumineux — violet */}
        <circle cx={CX} cy={CY} r="8"
          fill="#8b5cf6" opacity="0.9"
          clipPath="url(#eyeClip)"
          filter="url(#pupilGlow)" />

        {/* Point central cyan brillant */}
        <circle cx={CX} cy={CY} r="4.5"
          fill="#00f0ff" opacity="0.98"
          clipPath="url(#eyeClip)"
          filter="url(#cyanGlow)" />

        {/* Éclat or — le pixel le plus lumineux */}
        <circle cx={CX} cy={CY} r="2"
          fill="#ffd700" opacity="1"
          clipPath="url(#eyeClip)" />

        {/* ── REFLETS ────────────────────────────────────────────────── */}
        <ellipse cx="116" cy="82" rx="9" ry="5.5"
          fill="url(#eyeShineGrad)"
          clipPath="url(#eyeClip)"
          style={{ transform: 'rotate(-22deg)', transformOrigin: '116px 82px' }} />
        <circle cx="84" cy="116" r="2.2"
          fill="white" opacity="0.22"
          clipPath="url(#eyeClip)" />

        {/* ── PAUPIÈRES ──────────────────────────────────────────────── */}
        <path d="M 6 100 C 34 34, 166 34, 194 100"
          fill="none" stroke="#00d4ff" strokeWidth="1.3" opacity="0.6" />
        <path d="M 6 100 C 34 166, 166 166, 194 100"
          fill="none" stroke="#8b5cf6" strokeWidth="1.2" opacity="0.5" />

        {/* Liseret cyan supérieur */}
        <path d="M 18 100 C 44 50, 156 50, 182 100"
          fill="none" stroke="#00d4ff" strokeWidth="0.5" opacity="0.35" />

        {/* ── CILS ───────────────────────────────────────────────────── */}
        {[
          [28, 64, -9, -6], [52, 49, -5, -8], [78, 42, -2, -8],
          [100, 38, 0, -8],
          [122, 42, 2, -8], [148, 49, 5, -8], [172, 64, 9, -6],
        ].map(([x, y, dx, dy], i) => (
          <line key={i} x1={x} y1={y} x2={x + dx} y2={y + dy}
            stroke="#00d4ff" strokeWidth="0.85" opacity="0.4"
            strokeLinecap="round" />
        ))}

        {/* Ligne de scan animée sur l'œil */}
        <line x1="6" y1={CY} x2="194" y2={CY}
          stroke="#00d4ff" strokeWidth="0.3" opacity="0.15"
          clipPath="url(#eyeClip)" />
      </svg>

      {/* ── Label état ──────────────────────────────────────────────── */}
      <div className="eye-state-label">
        {{ idle: '', listening: '· écoute ·', thinking: '· analyse ·', responding: '· réponse ·' }[state]}
      </div>
    </div>
  )
}
