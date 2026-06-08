"""
IMSICatcherService — Fausse antenne relais GSM pour capture IMSI.
Nécessite HackRF/BladeRF + YateBTS ou OpenBTS.
USAGE STRICTEMENT LÉGAL : test en laboratoire blindé, autorisation explicite requise.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import shutil
import string
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/imsi_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Mock data ─────────────────────────────────────────────────────────────────

_MANUFACTURERS = ["Samsung", "Apple", "Xiaomi", "OnePlus", "Google", "Huawei", "Sony", "Nokia"]

def _rand_imsi(mcc: str = "208", mnc: str = "01") -> str:
    return mcc + mnc + "".join(random.choices(string.digits, k=10))

def _rand_tmsi() -> str:
    return hex(random.randint(0x10000000, 0xFFFFFFFF))

def _rand_phone() -> str:
    return "+336" + "".join(random.choices(string.digits, k=8))


class IMSICatcherService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._active_sessions: dict[str, dict] = {}
        self._captured_phones: dict[str, list] = {}
        self._sms_captured: dict[str, list] = {}
        self._check_hardware_cache = None

    def _check_tools(self) -> dict:
        return {
            "hackrf": bool(shutil.which("hackrf_info")),
            "bladerf": bool(shutil.which("bladeRF-cli")),
            "yate": bool(shutil.which("yate")),
            "openbts": bool(shutil.which("OpenBTS")),
            "gnuradio": bool(shutil.which("gnuradio-companion")),
        }

    async def check_hardware(self) -> dict:
        tools = self._check_tools()
        hardware_ready = any([tools["hackrf"], tools["bladerf"]])
        bts_ready = any([tools["yate"], tools["openbts"]])

        if self.simulation_mode:
            return {
                "hardware_ready": True,
                "bts_software": "YateBTS (simulated)",
                "sdr_hardware": "HackRF One (simulated)",
                "gsm_antenna": "900MHz Whip (simulated)",
                "bands_supported": ["GSM900", "DCS1800"],
                "simulation": True,
            }
        return {
            "hardware_ready": hardware_ready,
            "bts_software": "YateBTS" if tools["yate"] else ("OpenBTS" if tools["openbts"] else None),
            "sdr_hardware": "HackRF" if tools["hackrf"] else ("BladeRF" if tools["bladerf"] else None),
            "gsm_antenna": "not_detected",
            "bands_supported": ["GSM900"] if hardware_ready else [],
            "tools": tools,
            "simulation": False,
        }

    async def start_fake_bts(self, band: str = "900", operator_mcc: str = "208", operator_mnc: str = "01") -> dict:
        if not self.simulation_mode:
            hw = await self.check_hardware()
            if not hw.get("hardware_ready"):
                return {"error": "Aucun hardware SDR détecté"}
            if not hw.get("bts_software"):
                return {"error": "YateBTS ou OpenBTS requis"}

        await asyncio.sleep(3)
        bts_id = "bts_" + "".join(random.choices(string.hexdigits.lower(), k=8))
        session = {
            "bts_id": bts_id,
            "band": f"GSM{band}",
            "frequency_mhz": 897.4 if band == "900" else 1842.6,
            "mcc": operator_mcc,
            "mnc": operator_mnc,
            "operator_name": f"CORP_BTS_{operator_mcc}{operator_mnc}",
            "cell_id": random.randint(10000, 65535),
            "lac": random.randint(1000, 9999),
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "phones_connected": 0,
            "simulation": self.simulation_mode,
        }
        self._active_sessions[bts_id] = session
        self._captured_phones[bts_id] = []
        self._sms_captured[bts_id] = []

        if self.simulation_mode:
            asyncio.create_task(self._simulate_phone_connections(bts_id))

        return session

    async def _simulate_phone_connections(self, bts_id: str):
        await asyncio.sleep(5)
        num_phones = random.randint(3, 12)
        for i in range(num_phones):
            await asyncio.sleep(random.uniform(2, 8))
            if bts_id not in self._active_sessions:
                break
            phone = {
                "imsi": _rand_imsi(),
                "tmsi": _rand_tmsi(),
                "msisdn": _rand_phone() if random.random() > 0.4 else None,
                "manufacturer": random.choice(_MANUFACTURERS),
                "signal_strength_dbm": random.randint(-80, -45),
                "location_area": str(self._active_sessions[bts_id]["lac"]),
                "connected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "id": str(i),
            }
            self._captured_phones.setdefault(bts_id, []).append(phone)
            self._active_sessions[bts_id]["phones_connected"] += 1

    async def stop_fake_bts(self, bts_id: str) -> dict:
        session = self._active_sessions.pop(bts_id, None)
        if not session:
            return {"error": "Session introuvable"}
        if not self.simulation_mode:
            await asyncio.create_subprocess_exec("killall", "yate", stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return {"success": True, "bts_id": bts_id, "phones_captured": len(self._captured_phones.get(bts_id, []))}

    async def get_connected_phones(self, bts_id: str) -> list[dict]:
        return self._captured_phones.get(bts_id, [])

    async def capture_sms(self, bts_id: str, target_imsi: str, duration: int = 60) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(min(duration * 0.1, 3))
            phone = next((p for p in self._captured_phones.get(bts_id, []) if p["imsi"] == target_imsi), None)
            msisdn = phone.get("msisdn", "+33600000000") if phone else "+33600000000"
            sms_list = [
                {"from": "BANQUE-PRO", "to": msisdn, "body": "Votre code OTP: 847291. Valide 2min.", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "MT"},
                {"from": "+33698765432", "to": msisdn, "body": "RDV demain 9h salle de conf", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "MT"},
                {"from": msisdn, "to": "+33144556677", "body": "Code accès parking: 2847", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "type": "MO"},
            ]
            self._sms_captured.setdefault(bts_id, []).extend(sms_list)
            return sms_list
        return []

    async def inject_sms(self, bts_id: str, target_imsi: str, message: str, spoof_from: str = None) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return {
                "success": True,
                "target_imsi": target_imsi,
                "message": message,
                "spoofed_from": spoof_from or "CORP-IT",
                "delivered_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "simulation": True,
            }
        return {"success": False, "error": "Injection SMS nécessite YateBTS configuré"}

    async def capture_call_metadata(self, bts_id: str, target_imsi: str, duration: int = 120) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(min(duration * 0.05, 2))
            return [
                {"direction": "MO", "called_number": "+33144556677", "duration": 127, "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")},
                {"direction": "MT", "calling_number": "+33600000000", "duration": 0, "status": "unanswered", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")},
            ]
        return []

    async def locate_phone(self, target_imsi: str, bts_id: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            base_lat = 48.8566 + random.uniform(-0.01, 0.01)
            base_lon = 2.3522 + random.uniform(-0.01, 0.01)
            return {
                "target_imsi": target_imsi,
                "estimated_lat": round(base_lat, 6),
                "estimated_lon": round(base_lon, 6),
                "accuracy_meters": random.randint(50, 500),
                "confidence": round(random.uniform(0.6, 0.9), 2),
                "method": "RSSI triangulation",
                "bts_used": 3,
                "simulation": True,
            }
        return {"error": "Triangulation nécessite plusieurs antennes calibrées"}

    async def detect_stingray(self) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            detected = random.random() < 0.2
            return {
                "stingray_detected": detected,
                "confidence": round(random.uniform(0.8, 0.95) if detected else 0.1, 2),
                "anomalies": [
                    {"type": "forced_downgrade", "description": "Antenne force downgrade 2G sur zone 4G", "severity": "HIGH"},
                    {"type": "signal_strength", "description": "Signal anormalement fort sur BTS inconnue", "severity": "MEDIUM"},
                ] if detected else [],
                "suspect_cell_id": str(random.randint(60000, 65535)) if detected else None,
                "suspect_lac": str(random.randint(50000, 60000)) if detected else None,
                "scan_duration_s": 30,
                "simulation": True,
            }
        return {"error": "Détection nécessite SDR + bases de données antennes légitimes"}

    async def get_sessions(self) -> list[dict]:
        return list(self._active_sessions.values())


imsi_service = IMSICatcherService()
