import { useEffect, useRef } from 'react'

export default function StarField({ theme = 'galactic' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const resize = () => {
      canvas.width  = window.innerWidth
      canvas.height = window.innerHeight
    }
    resize()
    window.addEventListener('resize', resize)

    // Générer les étoiles — 3 couleurs : thème / bleu électrique / or
    const N = 260
    const stars = Array.from({ length: N }, () => {
      const rng = Math.random()
      let color
      if (rng < 0.65)      color = themeStarColor(theme)      // 65% couleur thème
      else if (rng < 0.87) color = '56, 189, 248'             // 22% bleu électrique
      else                 color = '253, 230, 138'             // 13% blanc-or
      return {
        x:    Math.random() * canvas.width,
        y:    Math.random() * canvas.height,
        r:    Math.random() * 1.6 + 0.2,
        speed: Math.random() * 0.12 + 0.02,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: Math.random() * 0.025 + 0.005,
        color,
      }
    })

    // Nébuleuses
    const nebulae = [
      { x: canvas.width * 0.2,  y: canvas.height * 0.3, r: 280, color: nebulaColor(theme, 0) },
      { x: canvas.width * 0.75, y: canvas.height * 0.6, r: 220, color: nebulaColor(theme, 1) },
      { x: canvas.width * 0.5,  y: canvas.height * 0.15, r: 160, color: nebulaColor(theme, 2) },
    ]

    let raf
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Fond profond
      const bg = ctx.createRadialGradient(
        canvas.width / 2, canvas.height / 2, 0,
        canvas.width / 2, canvas.height / 2, Math.max(canvas.width, canvas.height)
      )
      const [bgC1, bgC2] = themeBg(theme)
      bg.addColorStop(0, bgC1)
      bg.addColorStop(1, bgC2)
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Nébuleuses
      nebulae.forEach(n => {
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r)
        g.addColorStop(0,   n.color.replace(')', ', 0.07)').replace('rgb', 'rgba'))
        g.addColorStop(0.5, n.color.replace(')', ', 0.04)').replace('rgb', 'rgba'))
        g.addColorStop(1,   n.color.replace(')', ', 0)').replace('rgb', 'rgba'))
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fill()
      })

      // Étoiles
      stars.forEach(s => {
        s.twinkle += s.twinkleSpeed
        const opacity = 0.4 + Math.sin(s.twinkle) * 0.5
        ctx.beginPath()
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
        ctx.fillStyle = `rgba(${s.color}, ${opacity})`
        ctx.fill()

        // Étoiles brillantes avec croix lumineuse
        if (s.r > 1.3) {
          ctx.strokeStyle = `rgba(${s.color}, ${opacity * 0.4})`
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(s.x - s.r * 3, s.y)
          ctx.lineTo(s.x + s.r * 3, s.y)
          ctx.moveTo(s.x, s.y - s.r * 3)
          ctx.lineTo(s.x, s.y + s.r * 3)
          ctx.stroke()
        }

        // Dérive lente vers le bas
        s.y += s.speed
        if (s.y > canvas.height + 2) {
          s.y = -2
          s.x = Math.random() * canvas.width
        }
      })

      raf = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', resize)
    }
  }, [theme])

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed', inset: 0,
        width: '100vw', height: '100vh',
        zIndex: 0, pointerEvents: 'none',
      }}
    />
  )
}

function themeStarColor(theme) {
  const map = {
    galactic:  '200, 180, 255',
    divine:    '255, 240, 180',
    cyberpunk: '180, 255, 200',
    alien:     '150, 255, 220',
    temple:    '255, 180, 120',
  }
  return map[theme] || map.galactic
}

function nebulaColor(theme, idx) {
  const map = {
    galactic:  ['rgb(124,58,237)', 'rgb(79,70,229)', 'rgb(55,48,163)'],
    divine:    ['rgb(234,179,8)',   'rgb(251,191,36)', 'rgb(245,158,11)'],
    cyberpunk: ['rgb(16,185,129)',  'rgb(236,72,153)', 'rgb(99,102,241)'],
    alien:     ['rgb(6,182,212)',   'rgb(16,185,129)', 'rgb(245,158,11)'],
    temple:    ['rgb(239,68,68)',   'rgb(249,115,22)', 'rgb(124,58,237)'],
  }
  return (map[theme] || map.galactic)[idx]
}

function themeBg(theme) {
  const map = {
    galactic:  ['#07051a', '#020108'],
    divine:    ['#1a1408', '#070501'],
    cyberpunk: ['#021a0c', '#000802'],
    alien:     ['#011a1a', '#000508'],
    temple:    ['#1a0505', '#080101'],
  }
  return map[theme] || map.galactic
}
