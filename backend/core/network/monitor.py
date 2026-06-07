"""
NetworkMonitor — surveillance réseau passive temps réel.
Utilise psutil pour capturer connexions, débits, et détecter anomalies.
"""
from __future__ import annotations

import asyncio
import time
import psutil
from datetime import datetime
from typing import Any
from collections import defaultdict


# ── Ports suspects ─────────────────────────────────────────────────────────────
_SUSPICIOUS_PORTS = {
    4444, 4445, 1337, 6666, 6667, 6668, 9999, 31337,
    8888, 8889, 2222, 5555, 7777, 1234, 12345, 54321,
    # Metasploit handlers
    4443, 443, 80, 8080,
}

_PRIVATE_PREFIXES = ('10.', '192.168.', '172.16.', '172.17.', '172.18.',
                     '172.19.', '172.20.', '172.21.', '172.22.', '172.23.',
                     '172.24.', '172.25.', '172.26.', '172.27.', '172.28.',
                     '172.29.', '172.30.', '172.31.', '127.', '::1', 'localhost')

_SCAN_THRESHOLD  = 10   # connexions depuis la même IP en < 10 s = scan
_FLOOD_THRESHOLD = 50   # connexions totales en 1 s = flood


class NetworkMonitor:
    """
    Capture passive du trafic réseau via psutil.
    Détecte : nouvelles connexions, scans de ports, ports suspects, débits anormaux.
    """

    def __init__(self):
        self._prev_conns:  set[tuple]  = set()
        self._prev_io:     dict        = {}
        self._ip_timeline: dict[str, list[float]] = defaultdict(list)
        self._running      = False
        self._subscribers: list        = []   # coroutines / queues WebSocket
        self._events_history: list[dict] = []
        self._max_history  = 200

    # ── API publique ───────────────────────────────────────────────────────────

    def subscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.append(queue)

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue) if hasattr(self._subscribers, 'discard') else None
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    def get_history(self, n: int = 50) -> list[dict]:
        return self._events_history[-n:]

    def get_snapshot(self) -> dict:
        """Snapshot instantané de l'état réseau."""
        try:
            conns   = psutil.net_connections(kind='inet')
            io      = psutil.net_io_counters(pernic=True)
            stats   = psutil.net_if_stats()
        except (psutil.AccessDenied, Exception):
            conns, io, stats = [], {}, {}

        conn_list = []
        for c in conns:
            if c.status in ('ESTABLISHED', 'LISTEN', 'TIME_WAIT', 'CLOSE_WAIT'):
                entry = {
                    'laddr': f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else '',
                    'raddr': f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else '',
                    'status': c.status,
                    'pid': c.pid,
                    'suspicious': bool(c.raddr and c.raddr.port in _SUSPICIOUS_PORTS),
                }
                conn_list.append(entry)

        interfaces = {}
        for iface, counters in io.items():
            up = stats.get(iface)
            if up and up.isup:
                interfaces[iface] = {
                    'bytes_sent':  counters.bytes_sent,
                    'bytes_recv':  counters.bytes_recv,
                    'packets_sent': counters.packets_sent,
                    'packets_recv': counters.packets_recv,
                    'errin':  counters.errin,
                    'errout': counters.errout,
                }

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'connections': conn_list,
            'conn_count':  len(conn_list),
            'established': sum(1 for c in conn_list if c['status'] == 'ESTABLISHED'),
            'listening':   sum(1 for c in conn_list if c['status'] == 'LISTEN'),
            'interfaces':  interfaces,
        }

    # ── Boucle principale ─────────────────────────────────────────────────────

    async def run(self) -> None:
        """Boucle de surveillance — appelée une fois au démarrage du serveur."""
        self._running = True
        while self._running:
            try:
                events = await asyncio.to_thread(self._tick)
                for event in events:
                    self._events_history.append(event)
                    if len(self._events_history) > self._max_history:
                        self._events_history.pop(0)
                    await self._broadcast(event)
            except Exception:
                pass
            await asyncio.sleep(1.5)

    def stop(self) -> None:
        self._running = False

    # ── Tick synchrone (exécuté en thread) ────────────────────────────────────

    def _tick(self) -> list[dict]:
        events: list[dict] = []
        now = time.time()

        # ── Connexions actives ─────────────────────────────────────────────────
        try:
            raw_conns = psutil.net_connections(kind='inet')
        except psutil.AccessDenied:
            return events

        current: set[tuple] = set()
        for c in raw_conns:
            if c.laddr and c.raddr:
                key = (c.laddr.ip, c.laddr.port, c.raddr.ip, c.raddr.port, c.status)
                current.add(key)

        new_conns = current - self._prev_conns
        for (lip, lport, rip, rport, status) in new_conns:
            if status not in ('ESTABLISHED', 'SYN_SENT', 'SYN_RECV'):
                continue

            is_suspicious = rport in _SUSPICIOUS_PORTS or lport in _SUSPICIOUS_PORTS
            is_external   = rip and not any(rip.startswith(p) for p in _PRIVATE_PREFIXES)

            # Suivi timeline par IP source
            self._ip_timeline[rip].append(now)
            # Purger les vieux timestamps (> 10s)
            self._ip_timeline[rip] = [t for t in self._ip_timeline[rip] if now - t < 10]
            conn_rate = len(self._ip_timeline[rip])

            severity = 'INFO'
            category = 'NEW_CONNECTION'
            title    = f"Nouvelle connexion {lip}:{lport} ↔ {rip}:{rport}"
            desc     = f"Status: {status}"

            if is_suspicious:
                severity = 'HIGH'
                category = 'SUSPICIOUS_PORT'
                title    = f"Port suspect {rport} détecté ({rip})"
                desc     = f"Connexion vers port connu C2/backdoor: {rport}"
            elif conn_rate >= _SCAN_THRESHOLD:
                severity = 'CRITICAL'
                category = 'PORT_SCAN'
                title    = f"Scan de ports détecté depuis {rip}"
                desc     = f"{conn_rate} connexions en < 10s depuis {rip}"
            elif is_external and rport in (22, 23, 3389, 5900):
                severity = 'MEDIUM'
                category = 'REMOTE_ACCESS'
                title    = f"Accès distant {rip}:{rport}"
                desc     = f"Connexion vers service d'accès distant (port {rport})"

            events.append({
                'type':      'network_event',
                'timestamp': datetime.utcnow().isoformat(),
                'severity':  severity,
                'category':  category,
                'title':     title,
                'description': desc,
                'source_ip':  rip,
                'dest_ip':    lip,
                'source_port': rport,
                'dest_port':   lport,
                'is_external': is_external,
                'is_suspicious': is_suspicious,
            })

        self._prev_conns = current

        # ── Débits réseau ──────────────────────────────────────────────────────
        try:
            io_now = psutil.net_io_counters(pernic=False)
            if self._prev_io:
                dt = 1.5
                bytes_sent_rate = max(0, io_now.bytes_sent - self._prev_io.bytes_sent) / dt
                bytes_recv_rate = max(0, io_now.bytes_recv - self._prev_io.bytes_recv) / dt
                if bytes_recv_rate > 10_000_000:   # > 10 MB/s
                    events.append({
                        'type':      'network_event',
                        'timestamp': datetime.utcnow().isoformat(),
                        'severity':  'HIGH',
                        'category':  'HIGH_BANDWIDTH',
                        'title':     f"Débit entrant élevé : {bytes_recv_rate/1e6:.1f} MB/s",
                        'description': 'Possible exfiltration ou download massif',
                        'bytes_recv_rate': bytes_recv_rate,
                        'bytes_sent_rate': bytes_sent_rate,
                    })
            self._prev_io = io_now
        except Exception:
            pass

        # ── Événement stats périodique (toutes les ~10s via l'historique) ─────
        if not self._events_history or (
            datetime.fromisoformat(self._events_history[-1]['timestamp'])
            if self._events_history and self._events_history[-1].get('type') == 'stats'
            else datetime.min
        ).timestamp() + 5 < now:
            try:
                io_all = psutil.net_io_counters(pernic=False)
                events.append({
                    'type':      'stats',
                    'timestamp': datetime.utcnow().isoformat(),
                    'conn_total':  len(current),
                    'new_conns':   len(new_conns),
                    'bytes_sent':  io_all.bytes_sent,
                    'bytes_recv':  io_all.bytes_recv,
                    'packets_sent': io_all.packets_sent,
                    'packets_recv': io_all.packets_recv,
                })
            except Exception:
                pass

        return events

    async def _broadcast(self, event: dict) -> None:
        dead = []
        for q in self._subscribers:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass
            except Exception:
                dead.append(q)
        for q in dead:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass


network_monitor = NetworkMonitor()
