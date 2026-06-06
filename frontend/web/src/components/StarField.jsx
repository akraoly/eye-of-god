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

    // ── Étoiles (3 couches de profondeur) ─────────────────────────
    const N = 420
    const stars = Array.from({ length: N }, () => {
      const rng   = Math.random()
      const layer = Math.floor(Math.random() * 3)  // 0=far, 1=mid, 2=near
      let color
      if (rng < 0.60)      color = themeStarColor(theme)
      else if (rng < 0.82) color = '0, 212, 255'      // cyan
      else if (rng < 0.94) color = '139, 92, 246'     // violet
      else                 color = '245, 158, 11'      // gold
      return {
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        r: layer === 2 ? Math.random() * 2.2 + 0.6
           : layer === 1 ? Math.random() * 1.4 + 0.3
           : Math.random() * 0.8 + 0.1,
        speed: layer === 2 ? Math.random() * 0.18 + 0.06
               : layer === 1 ? Math.random() * 0.1 + 0.03
               : Math.random() * 0.05 + 0.01,
        twinkle: Math.random() * Math.PI * 2,
        twinkleSpeed: Math.random() * 0.03 + 0.005,
        color, layer,
      }
    })

    // ── Étoiles filantes ───────────────────────────────────────────
    let shootingStars = []
    const spawnShootingStar = () => {
      if (shootingStars.length >= 3) return
      shootingStars.push({
        x:     Math.random() * canvas.width * 0.7,
        y:     Math.random() * canvas.height * 0.4,
        vx:    Math.random() * 6 + 4,
        vy:    Math.random() * 3 + 1,
        life:  0,
        maxLife: Math.random() * 60 + 40,
        len:   Math.random() * 80 + 60,
        color: Math.random() < 0.6 ? '0, 212, 255' : '200, 180, 255',
      })
    }
    const shootInterval = setInterval(spawnShootingStar, 3200)

    // ── Nébuleuses ─────────────────────────────────────────────────
    const nebulae = [
      { x: canvas.width * 0.18, y: canvas.height * 0.28, r: 320, color: nebulaColor(theme, 0) },
      { x: canvas.width * 0.78, y: canvas.height * 0.62, r: 260, color: nebulaColor(theme, 1) },
      { x: canvas.width * 0.52, y: canvas.height * 0.12, r: 200, color: nebulaColor(theme, 2) },
      { x: canvas.width * 0.88, y: canvas.height * 0.18, r: 150, color: nebulaColor(theme, 0), alpha: 0.04 },
      { x: canvas.width * 0.08, y: canvas.height * 0.78, r: 180, color: nebulaColor(theme, 2), alpha: 0.03 },
    ]

    // ── Grille hex subtile ─────────────────────────────────────────
    const drawHexGrid = () => {
      const hexSize = 55
      const hexW = hexSize * 2
      const hexH = Math.sqrt(3) * hexSize
      const cols = Math.ceil(canvas.width  / hexW) + 2
      const rows = Math.ceil(canvas.height / hexH) + 2
      ctx.strokeStyle = `rgba(0, 212, 255, 0.018)`
      ctx.lineWidth = 0.5

      for (let row = -1; row < rows; row++) {
        for (let col = -1; col < cols; col++) {
          const offsetX = (row % 2) * hexSize
          const cx = col * hexW + offsetX
          const cy = row * hexH
          ctx.beginPath()
          for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 6
            const px = cx + hexSize * Math.cos(angle)
            const py = cy + hexSize * Math.sin(angle)
            i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py)
          }
          ctx.closePath()
          ctx.stroke()
        }
      }
    }

    let raf
    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height)

      // Fond espace profond
      const bg = ctx.createRadialGradient(
        canvas.width * 0.5, canvas.height * 0.35, 0,
        canvas.width * 0.5, canvas.height * 0.5,
        Math.max(canvas.width, canvas.height) * 0.85,
      )
      const [bgC1, bgC2] = themeBg(theme)
      bg.addColorStop(0, bgC1)
      bg.addColorStop(1, bgC2)
      ctx.fillStyle = bg
      ctx.fillRect(0, 0, canvas.width, canvas.height)

      // Grille hexagonale
      drawHexGrid()

      // Nébuleuses
      nebulae.forEach(n => {
        const alpha = n.alpha ?? 0.06
        const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r)
        g.addColorStop(0,   n.color.replace(')', `, ${alpha})`).replace('rgb', 'rgba'))
        g.addColorStop(0.5, n.color.replace(')', `, ${alpha * 0.6})`).replace('rgb', 'rgba'))
        g.addColorStop(1,   n.color.replace(')', ', 0)').replace('rgb', 'rgba'))
        ctx.fillStyle = g
        ctx.beginPath()
        ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2)
        ctx.fill()
      })

      // Étoiles par couche (loin → près)
      for (let layer = 0; layer <= 2; layer++) {
        stars.filter(s => s.layer === layer).forEach(s => {
          s.twinkle += s.twinkleSpeed
          const flicker = 0.35 + Math.sin(s.twinkle) * 0.55
          const alpha   = Math.max(0.05, Math.min(1, flicker))
          ctx.beginPath()
          ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2)
          ctx.fillStyle = `rgba(${s.color}, ${alpha})`
          ctx.fill()

          // Croix lumineuse sur les étoiles proches brillantes
          if (layer === 2 && s.r > 1.4) {
            const cx = s.r * 4.5
            ctx.strokeStyle = `rgba(${s.color}, ${alpha * 0.35})`
            ctx.lineWidth = 0.5
            ctx.beginPath()
            ctx.moveTo(s.x - cx, s.y); ctx.lineTo(s.x + cx, s.y)
            ctx.moveTo(s.x, s.y - cx); ctx.lineTo(s.x, s.y + cx)
            ctx.stroke()
          }

          // Dérive vers le bas (parallaxe selon couche)
          s.y += s.speed
          if (s.y > canvas.height + 3) {
            s.y = -3; s.x = Math.random() * canvas.width
          }
        })
      }

      // Étoiles filantes
      shootingStars = shootingStars.filter(s => s.life < s.maxLife)
      shootingStars.forEach(s => {
        const progress = s.life / s.maxLife
        const alpha    = progress < 0.2 ? progress / 0.2 : 1 - (progress - 0.2) / 0.8
        const grad     = ctx.createLinearGradient(
          s.x, s.y,
          s.x - s.vx * (s.len / s.vx), s.y - s.vy * (s.len / s.vx)
        )
        grad.addColorStop(0,   `rgba(${s.color}, ${alpha})`)
        grad.addColorStop(0.3, `rgba(${s.color}, ${alpha * 0.6})`)
        grad.addColorStop(1,   `rgba(${s.color}, 0)`)
        ctx.strokeStyle = grad
        ctx.lineWidth   = 1.5
        ctx.beginPath()
        ctx.moveTo(s.x, s.y)
        ctx.lineTo(s.x - s.vx * (s.len / 8), s.y - s.vy * (s.len / 8))
        ctx.stroke()
        s.x += s.vx; s.y += s.vy; s.life++
      })

      raf = requestAnimationFrame(draw)
    }
    draw()

    return () => {
      cancelAnimationFrame(raf)
      clearInterval(shootInterval)
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
    galactic:  '180, 220, 255',
    divine:    '255, 240, 180',
    cyberpunk: '160, 255, 180',
    alien:     '140, 255, 240',
    temple:    '255, 180, 120',
  }
  return map[theme] || map.galactic
}

function nebulaColor(theme, idx) {
  const map = {
    galactic:  ['rgb(0,212,255)',    'rgb(139,92,246)',  'rgb(79,70,229)'],
    divine:    ['rgb(251,191,36)',   'rgb(245,158,11)',  'rgb(234,179,8)'],
    cyberpunk: ['rgb(0,255,128)',    'rgb(255,0,128)',   'rgb(99,102,241)'],
    alien:     ['rgb(0,240,220)',    'rgb(0,200,180)',   'rgb(245,158,11)'],
    temple:    ['rgb(255,60,0)',     'rgb(249,115,22)',  'rgb(139,92,246)'],
  }
  return (map[theme] || map.galactic)[idx]
}

function themeBg(theme) {
  const map = {
    galactic:  ['#020616', '#000208'],
    divine:    ['#180c02', '#060200'],
    cyberpunk: ['#011205', '#000301'],
    alien:     ['#011412', '#000304'],
    temple:    ['#180202', '#060000'],
  }
  return map[theme] || map.galactic
}
