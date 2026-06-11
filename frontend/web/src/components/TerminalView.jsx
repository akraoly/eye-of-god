/**
 * TERMINAL — xterm.js connecté au PTY backend via WebSocket.
 */
import { useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import { WebLinksAddon } from '@xterm/addon-web-links'
import '@xterm/xterm/css/xterm.css'
import { auth } from '../utils/auth'

const TERM_THEME = {
  background:    '#000208',
  foreground:    '#c8e8ff',
  cursor:        '#00d4ff',
  cursorAccent:  '#000208',
  selectionBackground: 'rgba(0, 212, 255, 0.25)',
  black:         '#0a0e1a',
  red:           '#ff4466',
  green:         '#00e876',
  yellow:        '#f59e0b',
  blue:          '#00d4ff',
  magenta:       '#8b5cf6',
  cyan:          '#06b6d4',
  white:         '#c8e8ff',
  brightBlack:   '#1a3550',
  brightRed:     '#ff6680',
  brightGreen:   '#33f09b',
  brightYellow:  '#fbbf24',
  brightBlue:    '#38bdf8',
  brightMagenta: '#a78bfa',
  brightCyan:    '#22d3ee',
  brightWhite:   '#e2f4ff',
}

export default function TerminalView() {
  const containerRef = useRef(null)
  const termRef      = useRef(null)
  const fitRef       = useRef(null)
  const wsRef        = useRef(null)
  const mountedRef   = useRef(true)
  const [status, setStatus] = useState('disconnected')

  const connect = () => {
    const token = auth.getToken()
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url   = `${proto}//${window.location.host}/api/system/terminal-ws${token ? `?token=${token}` : ''}`

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws
    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      if (!mountedRef.current) return
      setStatus('connected')
      // Envoyer la taille initiale
      const { rows, cols } = termRef.current || { rows: 24, cols: 80 }
      ws.send(JSON.stringify({ type: 'resize', rows, cols }))
      termRef.current?.focus()
    }

    ws.onclose = (e) => {
      if (!mountedRef.current) return
      setStatus('disconnected')
      termRef.current?.write('\r\n\x1b[31m[Connexion fermée — cliquez Reconnecter]\x1b[0m\r\n')
    }

    ws.onerror = () => {
      if (!mountedRef.current) return
      setStatus('error')
      termRef.current?.write('\r\n\x1b[31m[Erreur WebSocket]\x1b[0m\r\n')
    }

    ws.onmessage = (e) => {
      if (!termRef.current) return
      if (e.data instanceof ArrayBuffer) {
        termRef.current.write(new Uint8Array(e.data))
      } else {
        termRef.current.write(e.data)
      }
    }
  }

  useEffect(() => {
    if (!containerRef.current) return

    const term = new Terminal({
      theme: TERM_THEME,
      fontFamily: '"JetBrains Mono", "Cascadia Code", "Fira Code", Consolas, monospace',
      fontSize: 14,
      lineHeight: 1.2,
      cursorBlink: true,
      cursorStyle: 'block',
      scrollback: 2000,
      allowTransparency: true,
      convertEol: false,
    })

    const fitAddon = new FitAddon()
    const linksAddon = new WebLinksAddon()

    term.loadAddon(fitAddon)
    term.loadAddon(linksAddon)

    termRef.current = term
    fitRef.current  = fitAddon

    // Defer open() until browser has laid out the container — avoids xterm
    // internal ResizeObserver firing before _renderService is initialized
    const rafId = requestAnimationFrame(() => {
      if (!containerRef.current) return
      term.open(containerRef.current)
      try { fitAddon.fit() } catch (_) {}

      term.write('\x1b[1;36m╔══════════════════════════════════════════╗\x1b[0m\r\n')
      term.write('\x1b[1;36m║  L\'Œil de Dieu — Terminal PTY            ║\x1b[0m\r\n')
      term.write('\x1b[1;36m╚══════════════════════════════════════════╝\x1b[0m\r\n\r\n')
    })

    // Clavier → WebSocket
    term.onData(data => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(data)
      }
    })

    // Binary → WebSocket
    term.onBinary(data => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        const buf = new Uint8Array(data.length)
        for (let i = 0; i < data.length; i++) buf[i] = data.charCodeAt(i)
        wsRef.current.send(buf.buffer)
      }
    })

    // Resize → backend
    const resizeObs = new ResizeObserver(() => {
      try { fitAddon.fit() } catch (_) {}
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({
          type: 'resize',
          rows: term.rows,
          cols: term.cols,
        }))
      }
    })
    if (containerRef.current) resizeObs.observe(containerRef.current)

    connect()

    return () => {
      mountedRef.current = false
      cancelAnimationFrame(rafId)
      resizeObs.disconnect()
      wsRef.current?.close()
      term.dispose()
    }
  }, [])

  const reconnect = () => {
    wsRef.current?.close()
    termRef.current?.clear()
    connect()
  }

  const STATUS_DOT_COLOR = {
    connected:    '#4ade80',
    connecting:   '#fbbf24',
    disconnected: '#64748b',
    error:        '#ef4444',
  }

  return (
    <div className="terminal-view">
      <div className="aegis-header">
        <div className="aegis-header-left">
          <span className="aegis-logo">💻</span>
          <div>
            <div className="aegis-title">TERMINAL</div>
            <div className="aegis-subtitle">Shell PTY interactif — WebSocket chiffré</div>
          </div>
        </div>
        <div className="aegis-header-right" style={{ gap: 10 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: STATUS_DOT_COLOR[status] || '#64748b', display: 'inline-block' }} />
          <span style={{ fontSize: '0.65rem', color: 'var(--text3)' }}>{status}</span>
          {status !== 'connected' && (
            <button className="aegis-launch-btn" onClick={reconnect} style={{ padding: '4px 12px', fontSize: '0.72rem' }}>
              ↺ Reconnecter
            </button>
          )}
          <button
            className="aegis-stop-btn"
            onClick={() => { termRef.current?.clear() }}
            style={{ padding: '4px 12px', fontSize: '0.72rem' }}
          >
            Clear
          </button>
        </div>
      </div>

      <div className="terminal-container" ref={containerRef} />
    </div>
  )
}
