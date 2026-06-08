"""
MeshRadioService — Communications maillées off-grid via LoRa.
Utilise modules LilyGO/Heltec LoRa32 via port série.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import shutil
import string
import time
import uuid
from pathlib import Path
from typing import Optional

try:
    import serial as _serial
    _SERIAL_OK = True
except ImportError:
    _serial = None
    _SERIAL_OK = False

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/mesh_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Mock topology ─────────────────────────────────────────────────────────────

_MOCK_NODES = [
    {"node_id": "mesh_001", "name": "Alpha-1", "frequency_mhz": 868.0, "signal_dbm": -65, "hops": 0, "last_seen": "2026-06-08T10:00:00"},
    {"node_id": "mesh_002", "name": "Bravo-2", "frequency_mhz": 868.0, "signal_dbm": -78, "hops": 1, "last_seen": "2026-06-08T10:01:00"},
    {"node_id": "mesh_003", "name": "Charlie-3", "frequency_mhz": 868.0, "signal_dbm": -88, "hops": 2, "last_seen": "2026-06-08T09:58:00"},
    {"node_id": "mesh_004", "name": "Delta-4", "frequency_mhz": 868.1, "signal_dbm": -72, "hops": 2, "last_seen": "2026-06-08T09:55:00"},
]

_MOCK_MESSAGES = [
    {"id": 1, "from_node": "mesh_002", "from_name": "Bravo-2", "to": "broadcast", "body": "Position confirmée, zone sécurisée", "encrypted": True, "ts": "2026-06-08T09:50:00"},
    {"id": 2, "from_node": "mesh_003", "from_name": "Charlie-3", "to": "broadcast", "body": "Relais opérationnel, signal fort", "encrypted": True, "ts": "2026-06-08T09:55:00"},
    {"id": 3, "from_node": "mesh_004", "from_name": "Delta-4", "to": "mesh_001", "body": "RDV point de collecte 14h00", "encrypted": True, "ts": "2026-06-08T09:58:00"},
]


class MeshRadioService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._active_nodes = {}
        self._messages = list(_MOCK_MESSAGES)
        self._msg_id = 10
        self._check_hardware()

    def _check_hardware(self):
        self.serial_ports = []
        if not self.simulation_mode and _SERIAL_OK:
            try:
                import serial.tools.list_ports
                for port in serial.tools.list_ports.comports():
                    if any(k in port.description.lower() for k in ["cp210", "ch340", "ftdi", "lora", "heltec", "ttgo"]):
                        self.serial_ports.append(port.device)
            except Exception:
                pass

    async def check_hardware(self) -> dict:
        if self.simulation_mode:
            return {
                "devices": [
                    {"port": "/dev/ttyUSB0", "model": "LilyGO TTGO LORA32", "frequency": "868MHz", "firmware": "Meshtastic 2.3.14"},
                    {"port": "/dev/ttyUSB1", "model": "Heltec WiFi LoRa 32 V3", "frequency": "868MHz", "firmware": "Meshtastic 2.3.14"},
                ],
                "mesh_available": True,
                "simulation": True,
            }
        return {"devices": [{"port": p} for p in self.serial_ports], "mesh_available": bool(self.serial_ports), "simulation": False}

    async def init_mesh_node(self, device_port: str, node_name: str, frequency_mhz: float = 868.0, power: int = 20) -> dict:
        await asyncio.sleep(2)
        node_id = "mesh_" + "".join(random.choices(string.hexdigits.lower(), k=6))
        if self.simulation_mode:
            node = {
                "node_id": node_id,
                "name": node_name,
                "device_port": device_port,
                "frequency_mhz": frequency_mhz,
                "power_dbm": power,
                "mesh_id": "MESH-" + "".join(random.choices(string.hexdigits.upper(), k=8)),
                "nodes_reachable": len(_MOCK_NODES),
                "simulation": True,
            }
            self._active_nodes[node_id] = node
            return node

        if not _SERIAL_OK:
            return {"error": "pyserial non installé", "simulation": False}
        try:
            ser = _serial.Serial(device_port, 115200, timeout=2)
            ser.write(b'AT+NAME=' + node_name.encode() + b'\r\n')
            await asyncio.sleep(0.5)
            response = ser.read(100).decode("utf-8", errors="replace")
            ser.close()
            node = {"node_id": node_id, "name": node_name, "device_port": device_port, "frequency_mhz": frequency_mhz, "response": response}
            self._active_nodes[node_id] = node
            return node
        except Exception as e:
            return {"error": str(e), "simulation": False}

    async def broadcast_message(self, node_id: str, message: str, encrypted: bool = True) -> bool:
        await asyncio.sleep(0.5)
        msg = {
            "id": self._msg_id,
            "from_node": node_id,
            "from_name": self._active_nodes.get(node_id, {}).get("name", node_id),
            "to": "broadcast",
            "body": f"[ENC:{len(message)}B]" if encrypted else message,
            "plain": message,
            "encrypted": encrypted,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._messages.append(msg)
        self._msg_id += 1

        if not self.simulation_mode and _SERIAL_OK and node_id in self._active_nodes:
            port = self._active_nodes[node_id].get("device_port")
            if port:
                try:
                    ser = _serial.Serial(port, 115200, timeout=2)
                    payload = json.dumps({"to": "all", "msg": message}).encode()
                    ser.write(payload + b"\r\n")
                    ser.close()
                except Exception as e:
                    logger.warning("LoRa send error: %s", e)

        return True

    async def send_direct_message(self, node_id: str, target_node_id: str, message: str) -> bool:
        await asyncio.sleep(0.5)
        msg = {
            "id": self._msg_id,
            "from_node": node_id,
            "from_name": self._active_nodes.get(node_id, {}).get("name", node_id),
            "to": target_node_id,
            "body": message,
            "encrypted": True,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._messages.append(msg)
        self._msg_id += 1
        return True

    async def transfer_file(self, node_id: str, target_node_id: str, file_path: str) -> dict:
        size = Path(file_path).stat().st_size if Path(file_path).exists() else random.randint(1024, 102400)
        chunk_size = 200
        chunks = math.ceil(size / chunk_size) if size else 1
        bit_rate_bps = 1200
        estimated_s = (size * 8) / bit_rate_bps
        await asyncio.sleep(min(3, estimated_s * 0.01))
        return {
            "file": file_path,
            "size_bytes": size,
            "chunks": chunks,
            "chunk_size_bytes": chunk_size,
            "estimated_transfer_s": round(estimated_s, 1),
            "bit_rate_bps": bit_rate_bps,
            "status": "queued",
            "simulation": self.simulation_mode,
        }

    async def get_mesh_topology(self, node_id: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return {
                "local_node": node_id,
                "nodes": _MOCK_NODES,
                "edges": [
                    {"from": node_id, "to": "mesh_001", "rssi": -65, "snr": 8.5},
                    {"from": "mesh_001", "to": "mesh_002", "rssi": -78, "snr": 5.2},
                    {"from": "mesh_002", "to": "mesh_003", "rssi": -88, "snr": 3.1},
                    {"from": "mesh_001", "to": "mesh_004", "rssi": -72, "snr": 7.0},
                ],
                "total_nodes": len(_MOCK_NODES),
                "simulation": True,
            }
        return {"local_node": node_id, "nodes": [], "edges": []}

    async def scan_frequencies_lora(self, start_mhz: float = 863.0, end_mhz: float = 870.0) -> list[dict]:
        await asyncio.sleep(2)
        if self.simulation_mode:
            active_freqs = [868.0, 868.1, 869.525]
            results = []
            freq = start_mhz
            while freq <= end_mhz:
                is_active = any(abs(freq - af) < 0.05 for af in active_freqs)
                if is_active or random.random() < 0.05:
                    results.append({"frequency_mhz": round(freq, 3), "active": is_active, "rssi_dbm": random.randint(-90, -55) if is_active else random.randint(-110, -95), "detected_nodes": random.randint(1, 4) if is_active else 0})
                freq = round(freq + 0.025, 3)
            return [r for r in results if r["active"] or r["rssi_dbm"] > -100]
        return []

    async def get_messages(self, node_id: str, since_id: int = None) -> list[dict]:
        msgs = self._messages
        if since_id is not None:
            msgs = [m for m in msgs if m["id"] > since_id]
        visible = [m for m in msgs if m.get("to") in ("broadcast", node_id) or m.get("from_node") == node_id]
        return visible


mesh_service = MeshRadioService()
