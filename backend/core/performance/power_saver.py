"""
PowerSaverMode — Gestion de la consommation CPU.

Modes :
  performance  → intervalles normaux, toutes fonctions actives
  balanced     → léger throttle SSE
  powersave    → intervalles ralentis, animations off
  emergency    → scheduler quasi-arrêté, polling long
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

MODES: dict[str, dict] = {
    "performance": {
        "scheduler_interval": "normal",
        "sse_frequency_ms": 500,
        "animations": True,
        "websocket": True,
        "polling": False,
        "description": "Performances maximales",
        "color": "#00ff88",
        "icon": "⚡",
    },
    "balanced": {
        "scheduler_interval": "normal",
        "sse_frequency_ms": 2000,
        "animations": True,
        "websocket": True,
        "polling": False,
        "description": "Équilibre perf/conso",
        "color": "#ffcc00",
        "icon": "⚖️",
    },
    "powersave": {
        "scheduler_interval": "slow",
        "sse_frequency_ms": 5000,
        "animations": False,
        "websocket": False,
        "polling": True,
        "description": "Économie d'énergie",
        "color": "#ff8800",
        "icon": "🔋",
    },
    "emergency": {
        "scheduler_interval": "stopped",
        "sse_frequency_ms": 30000,
        "animations": False,
        "websocket": False,
        "polling": True,
        "description": "Mode urgence — CPU critique",
        "color": "#ff2200",
        "icon": "🪫",
    },
}

# Thresholds CPU% pour auto-détection
_THRESHOLDS = [
    (85, "emergency"),
    (70, "powersave"),
    (50, "balanced"),
    (0,  "performance"),
]


class PowerSaverMode:

    def __init__(self):
        self._current_mode = "balanced"
        self._changed_at = time.time()
        self._auto = False

    async def set_mode(self, mode: str) -> dict:
        if mode not in MODES:
            raise ValueError(f"Mode invalide. Valeurs : {list(MODES.keys())}")
        self._current_mode = mode
        self._changed_at = time.time()
        self._auto = False
        logger.info("PowerSaver: mode '%s' activé", mode)
        return self.get_current_mode()

    def get_current_mode(self) -> dict:
        cfg = MODES[self._current_mode].copy()
        cfg["mode"] = self._current_mode
        cfg["auto"] = self._auto
        cfg["changed_at"] = self._changed_at
        return cfg

    async def auto_detect(self) -> str:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        for threshold, mode in _THRESHOLDS:
            if cpu >= threshold:
                if self._current_mode != mode:
                    self._current_mode = mode
                    self._changed_at = time.time()
                    logger.info("PowerSaver auto: CPU %.1f%% → mode '%s'", cpu, mode)
                self._auto = True
                return mode
        return self._current_mode

    def get_all_modes(self) -> dict:
        return {name: {
            "description": m["description"],
            "color": m["color"],
            "icon": m["icon"],
        } for name, m in MODES.items()}


power_saver = PowerSaverMode()
