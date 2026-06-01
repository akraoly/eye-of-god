/**
 * EyeOfGod — L'Œil vivant avec géométrie sacrée.
 * États : idle | listening | thinking | responding
 * Performance : SVG pur + CSS transforms (GPU), 0 canvas, 0 lib tierce.
 */

const CX = 100, CY = 100   // centre du viewBox 200×200

// Seed of Life : 6 cercles à 60° d'écart sur un rayon donné,
// chacun de même rayon que la distance → motif fleur.
function SeedOfLife({ orbitR, circleR, opacity = 0.07, stroke = '#818cf8' }) {
  return (
    <g>
      {Array.from({ length: 6 }, (_, i) => {
        const a = (i * 60 - 30) * Math.PI / 180
        const cx = CX + Math.cos(a) * orbitR
        const cy = CY + Math.sin(a) * orbitR
        return (
          <circle key={i} cx={cx} cy={cy} r={circleR}
            fill="none" stroke={stroke}
            strokeWidth="0.5" opacity={opacity} />
        )
      })}
      {/* Cercle central de la Graine */}
      <circle cx={CX} cy={CY} r={circleR}
        fill="none" stroke={stroke}
        strokeWidth="0.5" opacity={opacity} />
    </g>
  )
}

// Anneau SVG animé avec tirets, ticks et vitesse propre
function Ring({ r, speed, direction = 1, dashArray, tickCount = 0,
                stroke, strokeWidth = 0.7, opacity = 0.5, tickLen = 3 }) {
  const dir = direction > 0 ? 'ring-cw' : 'ring-ccw'
  const dur  = `${speed}s`
  return (
    <g style={{
      transformOrigin: `${CX}px ${CY}px`,
      animation: `${dir} ${dur} linear infinite`,
    }}>
      <circle cx={CX} cy={CY} r={r}
        fill="none" stroke={stroke} strokeWidth={strokeWidth}
        strokeDasharray={dashArray || 'none'}
        opacity={opacity} />
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

      {/* ── Halo externe (CSS, 3 couches) ─────────────────────────── */}
      <div className="eye-halo eye-halo-1" />
      <div className="eye-halo eye-halo-2" />

      {/* ── SVG principal ─────────────────────────────────────────── */}
      <svg className="eye-svg" viewBox="0 0 200 200"
           xmlns="http://www.w3.org/2000/svg"
           style={{ width: '100%', height: '100%', overflow: 'visible' }}>
        <defs>
          {/* Iris : radial violet → indigo → bleu nuit */}
          <radialGradient id="eyeIrisGrad" cx="50%" cy="45%" r="55%">
            <stop offset="0%"   stopColor="#2e1065" />
            <stop offset="30%"  stopColor="#6d28d9" />
            <stop offset="65%"  stopColor="#4338ca" />
            <stop offset="100%" stopColor="#0f0720" />
          </radialGradient>

          {/* Pupille : constellation sombre avec cœur lumineux */}
          <radialGradient id="eyePupilGrad" cx="50%" cy="50%" r="50%">
            <stop offset="0%"   stopColor="#a78bfa" stopOpacity="0.95" />
            <stop offset="35%"  stopColor="#4c1d95" stopOpacity="0.8"  />
            <stop offset="70%"  stopColor="#1e0540" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#030008" stopOpacity="1"    />
          </radialGradient>

          {/* Reflet supérieur */}
          <radialGradient id="eyeShineGrad" cx="60%" cy="30%" r="50%">
            <stop offset="0%"  stopColor="#e9d5ff" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
          </radialGradient>

          {/* Glow sur l'iris */}
          <filter id="irisGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Glow fort pour pupille */}
          <filter id="pupilGlow" x="-40%" y="-40%" width="180%" height="180%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>

          {/* Forme de l'œil en amande — plus dramatique */}
          <clipPath id="eyeClip">
            <path d="M 8 100 C 35 38, 165 38, 192 100
                     C 165 162, 35 162, 8 100 Z" />
          </clipPath>

          {/* Masque intérieur iris */}
          <clipPath id="irisClip">
            <circle cx={CX} cy={CY} r="47" />
          </clipPath>
        </defs>

        {/* ── GÉOMÉTRIE SACRÉE (derrière tout) ────────────────────── */}
        {/* Graine de Vie sur anneau extérieur, très discret */}
        <SeedOfLife orbitR={78} circleR={20} opacity={0.055} stroke="#818cf8" />
        {/* Hexagone intérieur — 6 traits reliant les points d'une graine */}
        {Array.from({ length: 6 }, (_, i) => {
          const a1 = ((i * 60 - 30) * Math.PI) / 180
          const a2 = (((i + 1) * 60 - 30) * Math.PI) / 180
          return (
            <line key={i}
              x1={CX + Math.cos(a1) * 78} y1={CY + Math.sin(a1) * 78}
              x2={CX + Math.cos(a2) * 78} y2={CY + Math.sin(a2) * 78}
              stroke="#6366f1" strokeWidth="0.3" opacity="0.12" />
          )
        })}

        {/* ── ANNEAUX CONCENTRIQUES ────────────────────────────────── */}
        {/*
          Ring 1 : extérieur, lent CCW, tirets espacés + 12 ticks (géométrie 12 secteurs)
          Ring 2 : moyen, CW, segments plus denses (Métatron reference)
          Ring 3 : intérieur, CCW rapide, trait continu très fin
        */}
        <Ring r={91} speed={48} direction={-1}
              dashArray="1.5 7.5" tickCount={12} tickLen={4}
              stroke="#4fc3f7" strokeWidth={0.6} opacity={0.45} />

        <Ring r={75} speed={28} direction={1}
              dashArray="6 3 1.5 3" tickCount={6} tickLen={3}
              stroke="#818cf8" strokeWidth={0.7} opacity={0.5} />

        <Ring r={60} speed={16} direction={-1}
              dashArray="none" tickCount={0}
              stroke="#c4b5fd" strokeWidth={0.5} opacity={0.35} />

        {/* ── BLANC DE L'ŒIL ──────────────────────────────────────── */}
        <path d="M 8 100 C 35 38, 165 38, 192 100 C 165 162, 35 162, 8 100 Z"
          fill="#04010e" />

        {/* ── IRIS : fond + rotation intérieure ───────────────────── */}
        <circle cx={CX} cy={CY} r="47"
          fill="url(#eyeIrisGrad)"
          clipPath="url(#eyeClip)"
          filter="url(#irisGlow)" />

        {/* Iris interne : anneau tournant avec 24 stries */}
        <g clipPath="url(#eyeClip)"
           style={{ transformOrigin: `${CX}px ${CY}px`,
                    animation: 'ring-cw 20s linear infinite' }}>
          {Array.from({ length: 24 }, (_, i) => {
            const a  = (i / 24) * Math.PI * 2
            const r1 = 26, r2 = 44
            return (
              <line key={i}
                x1={CX + Math.cos(a) * r1} y1={CY + Math.sin(a) * r1}
                x2={CX + Math.cos(a) * r2} y2={CY + Math.sin(a) * r2}
                stroke="#a78bfa" strokeWidth="0.45" opacity="0.35" />
            )
          })}
          {/* Anneau intérieur de l'iris */}
          <circle cx={CX} cy={CY} r="44"
            fill="none" stroke="#7c3aed" strokeWidth="0.8" opacity="0.4"
            strokeDasharray="3 5" />
        </g>

        {/* ── PUPILLE ──────────────────────────────────────────────── */}
        <circle cx={CX} cy={CY} r="22"
          fill="url(#eyePupilGrad)"
          clipPath="url(#eyeClip)"
          filter="url(#pupilGlow)" />

        {/* Constellation : 5 étoiles microscopiques dans la pupille */}
        {[
          [104, 95, 1.2], [93, 108, 1.0], [108, 107, 0.8],
          [96,  93, 0.7], [105, 103, 1.4],
        ].map(([x, y, r], i) => (
          <circle key={i} cx={x} cy={y} r={r}
            fill="#e9d5ff" opacity={0.6 + i * 0.06}
            clipPath="url(#eyeClip)" />
        ))}

        {/* Cœur lumineux — point central */}
        <circle cx={CX} cy={CY} r="7"
          fill="#7c3aed" opacity="0.85"
          clipPath="url(#eyeClip)"
          filter="url(#pupilGlow)" />
        <circle cx={CX} cy={CY} r="3.5"
          fill="#ddd6fe" opacity="1"
          clipPath="url(#eyeClip)" />

        {/* ── REFLETS ──────────────────────────────────────────────── */}
        {/* Reflet principal (blanc-or) */}
        <ellipse cx="116" cy="84" rx="8" ry="5"
          fill="url(#eyeShineGrad)"
          clipPath="url(#eyeClip)"
          style={{ transform: 'rotate(-20deg)', transformOrigin: '116px 84px' }} />
        {/* Micro-reflet secondaire */}
        <circle cx="86" cy="114" r="2.5"
          fill="white" opacity="0.18"
          clipPath="url(#eyeClip)" />

        {/* ── CONTOURS PAUPIÈRES ───────────────────────────────────── */}
        <path d="M 8 100 C 35 38, 165 38, 192 100"
          fill="none" stroke="#7c3aed" strokeWidth="1.2" opacity="0.65" />
        <path d="M 8 100 C 35 162, 165 162, 192 100"
          fill="none" stroke="#4f46e5" strokeWidth="1.2" opacity="0.55" />

        {/* Liseré lumineux sur paupière sup */}
        <path d="M 20 100 C 45 52, 155 52, 180 100"
          fill="none" stroke="#a78bfa" strokeWidth="0.4" opacity="0.3" />

        {/* ── CILS ─────────────────────────────────────────────────── */}
        {[
          [30, 66, -8, -5], [55, 51, -5, -7], [80, 43, -2, -7],
          [100, 40, 0, -7],
          [120, 43, 2, -7], [145, 51, 5, -7], [170, 66, 8, -5],
        ].map(([x, y, dx, dy], i) => (
          <line key={i} x1={x} y1={y} x2={x + dx} y2={y + dy}
            stroke="#818cf8" strokeWidth="0.9" opacity="0.45"
            strokeLinecap="round" />
        ))}
      </svg>

      {/* ── Label état ──────────────────────────────────────────────── */}
      <div className="eye-state-label">
        {{ idle: '', listening: '· écoute ·', thinking: '· réflexion ·', responding: '· réponse ·' }[state]}
      </div>
    </div>
  )
}
