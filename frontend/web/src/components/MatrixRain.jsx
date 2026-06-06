import { useEffect, useRef } from 'react'

export default function MatrixRain({ active }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    if (!active) return
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')

    const fontSize = 13
    let drops = []
    let raf

    const init = () => {
      const w = canvas.parentElement?.clientWidth || 800
      const h = canvas.parentElement?.clientHeight || 600
      canvas.width = w
      canvas.height = h
      const cols = Math.floor(w / fontSize)
      drops = Array.from({ length: cols }, () => Math.floor(Math.random() * -(h / fontSize)))
    }

    const draw = () => {
      ctx.fillStyle = 'rgba(0, 2, 0, 0.045)'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
      ctx.font = `${fontSize}px 'Courier New', monospace`

      for (let i = 0; i < drops.length; i++) {
        const y = drops[i] * fontSize
        if (y < -fontSize) { drops[i]++; continue }

        const char = Math.random() < 0.5 ? '0' : '1'
        const isHead = Math.random() > 0.93

        if (isHead) {
          ctx.fillStyle = '#ccffdd'
          ctx.shadowBlur = 18
          ctx.shadowColor = '#00ff88'
        } else {
          const alpha = 0.12 + Math.random() * 0.6
          ctx.fillStyle = `rgba(0, 255, 136, ${alpha})`
          ctx.shadowBlur = 5
          ctx.shadowColor = '#00ff88'
        }

        ctx.fillText(char, i * fontSize, y)
        ctx.shadowBlur = 0

        if (y > canvas.height && Math.random() > 0.974) {
          drops[i] = 0
        }
        drops[i] += 0.38 + Math.random() * 0.18
      }

      raf = requestAnimationFrame(draw)
    }

    const onResize = () => { init() }
    window.addEventListener('resize', onResize)

    requestAnimationFrame(() => {
      init()
      draw()
    })

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('resize', onResize)
    }
  }, [active])

  return (
    <canvas
      ref={canvasRef}
      className={`matrix-rain-canvas ${active ? 'matrix-active' : ''}`}
    />
  )
}
