import { useState } from 'react'
import EyeOfGod from './EyeOfGod'

/**
 * WelcomeNodes — Constellation de nœuds inspirée du Cube de Métatron.
 * L'œil est au centre-haut ; 4 nœuds circulaires orbitent autour,
 * reliés par des lignes lumineuses à gradient.
 */

// ── Géométrie du conteneur ────────────────────────────────────────────────
const W = 560    // largeur conteneur (px)
const H = 390    // hauteur conteneur (px)
const EX = 280   // centre œil X
const EY = 115   // centre œil Y
const R  = 195   // rayon orbital (œil → nœud)
const EYE_SIZE = 170

// ── Nœuds : angle en degrés écran (0°=droite, 90°=bas) ───────────────────
// Les 4 angles forment un arc large en dessous de l'œil, symétrique.
const NODE_DEFS = [
  { icon: '🔍', title: 'Explorer',  sub: 'Cartographie', angle: 153,
    prompt: 'explore /home/kali/eye-of-god' },
  { icon: '⚔️', title: 'ROP chain', sub: 'Exploit dev',  angle: 108,
    prompt: 'Construis une ROP chain x64 pour appeler execve avec pwntools' },
  { icon: '🛡️', title: 'Checksec',  sub: 'Mitigations',  angle: 72,
    prompt: 'checksec /usr/bin/python3' },
  { icon: '🌌', title: 'Mémoire',   sub: 'Souvenirs',     angle: 27,
    prompt: "Qu'est-ce que tu te souviens de moi ?" },
]

// Calcule les positions réelles des nœuds
const NODES = NODE_DEFS.map((n, id) => {
  const rad = n.angle * Math.PI / 180
  return { ...n, id, x: EX + R * Math.cos(rad), y: EY + R * Math.sin(rad) }
})

// Rayon visuel du nœud
const NODE_R = 44   // px, correspond à width/height 88px

export default function WelcomeNodes({ eyeState, onSend }) {
  const [hovered, setHovered] = useState(null)

  return (
    <div className="wn-container" style={{ width: W, height: H }}>

      {/* ── Couche SVG : lignes + cercles de géométrie sacrée ──────── */}
      <svg
        className="wn-svg"
        viewBox={`0 0 ${W} ${H}`}
        width={W} height={H}
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          {/* Gradient de chaque ligne : lumineux côté œil, transparent côté nœud */}
          {NODES.map(n => (
            <linearGradient
              key={`lg-${n.id}`}
              id={`lg${n.id}`}
              x1={EX} y1={EY} x2={n.x} y2={n.y}
              gradientUnits="userSpaceOnUse"
            >
              <stop offset="0%"   stopColor="var(--accent)" stopOpacity={hovered === n.id ? 0.85 : 0.45} />
              <stop offset="55%"  stopColor="var(--accent)" stopOpacity={hovered === n.id ? 0.30 : 0.12} />
              <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
            </linearGradient>
          ))}

          {/* Glow filter pour lignes actives */}
          <filter id="lineGlow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Arc de géométrie sacrée en fond — cercle orbital discret */}
        <circle cx={EX} cy={EY} r={R}
          fill="none"
          stroke="var(--accent)"
          strokeWidth="0.3"
          strokeDasharray="2 14"
          opacity="0.15" />

        {/* Lignes œil → nœuds */}
        {NODES.map(n => (
          <line
            key={`line-${n.id}`}
            x1={EX} y1={EY}
            x2={n.x} y2={n.y}
            stroke={`url(#lg${n.id})`}
            strokeWidth={hovered === n.id ? 1.4 : 0.7}
            filter={hovered === n.id ? 'url(#lineGlow)' : undefined}
            style={{ transition: 'stroke-width 0.25s' }}
          />
        ))}

        {/* Hexagone léger reliant les 4 nœuds entre eux */}
        {NODES.map((n, i) => {
          const next = NODES[(i + 1) % NODES.length]
          return (
            <line
              key={`cross-${i}`}
              x1={n.x} y1={n.y} x2={next.x} y2={next.y}
              stroke="var(--accent)"
              strokeWidth="0.3"
              opacity={hovered !== null ? 0.18 : 0.08}
              strokeDasharray="3 8"
              style={{ transition: 'opacity 0.25s' }}
            />
          )
        })}

        {/* Diagonales croisées (Métatron) */}
        {[
          [NODES[0], NODES[2]],
          [NODES[1], NODES[3]],
          [NODES[0], NODES[3]],
          [NODES[1], NODES[2]],
        ].map(([a, b], i) => (
          <line
            key={`diag-${i}`}
            x1={a.x} y1={a.y} x2={b.x} y2={b.y}
            stroke="var(--accent)"
            strokeWidth="0.25"
            opacity="0.05"
          />
        ))}

        {/* Point d'ancrage au centre de l'œil */}
        <circle cx={EX} cy={EY} r="4"
          fill="var(--accent)"
          opacity={hovered !== null ? 0.5 : 0.2}
          style={{ transition: 'opacity 0.25s' }} />

        {/* Cercle de résonance au survol d'un nœud */}
        {hovered !== null && (
          <circle cx={EX} cy={EY} r={NODE_R + 6}
            fill="none"
            stroke="var(--accent)"
            strokeWidth="0.6"
            opacity="0.25"
            className="wn-resonance" />
        )}
      </svg>

      {/* ── Œil central ────────────────────────────────────────────── */}
      <div
        className="wn-eye"
        style={{
          left: EX - EYE_SIZE / 2,
          top:  EY - EYE_SIZE / 2,
          width: EYE_SIZE, height: EYE_SIZE,
        }}
      >
        <EyeOfGod state={eyeState} size={EYE_SIZE} />
      </div>

      {/* ── Nœuds ──────────────────────────────────────────────────── */}
      {NODES.map(n => (
        <button
          key={n.id}
          className={`wn-node ${hovered === n.id ? 'wn-node-active' : ''}`}
          style={{
            left: n.x - NODE_R,
            top:  n.y - NODE_R,
            width:  NODE_R * 2,
            height: NODE_R * 2,
          }}
          onMouseEnter={() => setHovered(n.id)}
          onMouseLeave={() => setHovered(null)}
          onClick={() => onSend(n.prompt)}
        >
          <span className="wn-node-icon">{n.icon}</span>
          <span className="wn-node-title">{n.title}</span>
          <span className="wn-node-sub">{n.sub}</span>
        </button>
      ))}
    </div>
  )
}
