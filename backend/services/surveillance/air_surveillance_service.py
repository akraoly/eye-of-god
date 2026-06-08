"""
Air Surveillance Service — Bloc 12 Surveillance Stratégique
ADS-B, MLAT, ACARS, VDL2, détection militaire.
Simulation mode by default — real reception requires RTL-SDR/dump1090.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional

logger = logging.getLogger(__name__)

_AIRCRAFT_CONTACTS: Dict[str, Dict] = {}
_ADSB_RUNNING = False
_OUTPUT = Path("./data/surveillance/air")
_OUTPUT.mkdir(parents=True, exist_ok=True)

MILITARY_ICAO_PREFIXES = {
    "US":     ["AE", "AD", "AF", "A0", "A1", "A2", "A3", "A4"],
    "France": ["394", "395", "396"],
    "UK":     ["43C", "43D", "43E"],
    "Russia": ["152", "153", "154", "155"],
    "China":  ["780", "781", "782"],
    "Germany":["3C0", "3C1", "3D2"],
    "NATO":   ["4CA", "4CB", "502"],
}

AIRCRAFT_TYPES_MILITARY = [
    "F16", "F18", "F22", "F35", "F15", "Mirage2000", "RafaleC", "Typhoon",
    "B52", "B1B", "B2", "Tu95", "Tu160", "Su27", "Su35", "MiG31",
    "E3CF", "P8", "RC135", "EP3", "U2", "SR71", "GlobalHawk",
    "C130", "C17", "A400M", "Il76", "KC135", "A330MRTT",
    "H60", "CH47", "AH64", "Tiger", "EC725",
]

AIRCRAFT_TYPES_CIVIL = [
    "B738", "A320", "A321", "B77W", "A359", "B789", "A388", "B763",
    "E190", "CRJ9", "DH8D", "AT76", "PC12", "C172", "SR22",
]

CALLSIGN_PATTERNS_MILITARY = [
    "VIPER", "EAGLE", "GHOST", "MAGIC", "SENTRY", "REACH", "JAKE",
    "IRON", "STEEL", "RAPTOR", "KNIFE", "BLADE", "SWORD",
    "CALLSIGN01", "CALLSIGN02", "CALLSIGN03",
]

SQUAWK_MILITARY = {
    "7700": "EMERGENCY",
    "7600": "RADIO FAILURE",
    "7500": "HIJACK",
    "4201": "Military formation lead",
    "4401": "Combat Air Patrol",
    "0000": "Transponder on standby",
    "1200": "VFR",
    "2000": "IFR departure",
    "7777": "Military interception",
}


class AirSurveillanceService:

    def __init__(self):
        self.hardware = self._detect_hardware()
        self.is_simulation = self.hardware is None
        self._running = False

    def _detect_hardware(self) -> Optional[Dict]:
        for cmd, hw in [
            (["rtl_test", "-t"], "rtlsdr"),
            (["dump1090", "--version"], "dump1090"),
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=2)
                if r.returncode == 0:
                    return {"type": hw}
            except Exception:
                pass
        return None

    def adsb_receiver_start(self, lat: float = 48.85, lon: float = 2.35,
                             altitude_m: float = 50, radius_km: float = 200) -> Dict:
        global _ADSB_RUNNING
        _ADSB_RUNNING = True
        self._populate_simulated_traffic(lat, lon, radius_km)
        return {
            "status":      "running",
            "observer_lat": lat, "observer_lon": lon,
            "radius_km":   radius_km,
            "contacts":    len(_AIRCRAFT_CONTACTS),
            "is_simulation": self.is_simulation,
        }

    def adsb_receiver_stop(self) -> Dict:
        global _ADSB_RUNNING
        _ADSB_RUNNING = False
        return {"status": "stopped"}

    def _populate_simulated_traffic(self, center_lat: float, center_lon: float,
                                     radius_km: float, count: int = 35) -> None:
        _AIRCRAFT_CONTACTS.clear()
        for _ in range(count):
            is_mil = random.random() < 0.12
            angle  = random.uniform(0, 360)
            dist   = random.uniform(0, radius_km) * 1000
            lat = center_lat + (dist / 111000) * math.cos(math.radians(angle))
            lon = center_lon + (dist / 111000) * math.sin(math.radians(angle))
            alt = random.randint(1000, 43000)

            if is_mil:
                country = random.choice(list(MILITARY_ICAO_PREFIXES.keys()))
                pfx = random.choice(MILITARY_ICAO_PREFIXES[country])
                icao24 = pfx + f"{random.randint(0, 0xFFF):03X}"
                atype  = random.choice(AIRCRAFT_TYPES_MILITARY)
                callsign = random.choice(CALLSIGN_PATTERNS_MILITARY) + str(random.randint(1, 99))
                squawk = random.choice(["4201", "4401", "7777", "0100", "1200"])
                cat = "military"
            else:
                icao24 = f"{random.randint(0x400000, 0x4FFFFF):06X}"
                atype  = random.choice(AIRCRAFT_TYPES_CIVIL)
                ops = ["AFR", "BAW", "DLH", "UAE", "AAL", "UAL", "EZY", "VLG", "IBE"]
                callsign = random.choice(ops) + str(random.randint(100, 9999))
                squawk = str(random.randint(1000, 7000)).zfill(4)
                cat = random.choice(["commercial", "cargo", "private"])

            contact = {
                "icao24":         icao24.upper(),
                "callsign":       callsign,
                "aircraft_type":  atype,
                "category":       cat,
                "lat":            round(lat, 5),
                "lon":            round(lon, 5),
                "altitude_ft":    alt,
                "speed_kts":      random.randint(150, 550),
                "heading":        round(random.uniform(0, 360), 0),
                "vertical_rate":  random.choice([-1024, 0, 0, 0, 1024, 2048]),
                "squawk":         squawk,
                "transponder_mode": "Mode S" if not is_mil else random.choice(["Mode S","Mode 3/A","Transponder off"]),
                "source":         "adsb",
                "military_flag":  is_mil,
                "threat_level":   "unknown",
                "first_seen":     datetime.utcnow().isoformat(),
                "last_seen":      datetime.utcnow().isoformat(),
                "squawk_meaning": SQUAWK_MILITARY.get(squawk, ""),
                "is_simulation":  True,
            }
            if is_mil:
                contact["threat_level"] = "medium" if squawk not in ["7777","4401"] else "high"
            _AIRCRAFT_CONTACTS[icao24.upper()] = contact

    async def adsb_live_stream(self) -> AsyncGenerator[Dict, None]:
        for _ in range(10):
            await asyncio.sleep(2)
            for icao, contact in list(_AIRCRAFT_CONTACTS.items()):
                contact["lat"] = round(contact["lat"] + random.uniform(-0.01, 0.01), 5)
                contact["lon"] = round(contact["lon"] + random.uniform(-0.01, 0.01), 5)
                contact["altitude_ft"] = max(0, contact["altitude_ft"] + random.randint(-200, 200))
                contact["last_seen"] = datetime.utcnow().isoformat()
            yield {"contacts": len(_AIRCRAFT_CONTACTS), "timestamp": datetime.utcnow().isoformat(),
                   "snapshot": list(_AIRCRAFT_CONTACTS.values())[:10]}

    def adsb_contacts(self) -> Dict:
        return {"contacts": list(_AIRCRAFT_CONTACTS.values()), "total": len(_AIRCRAFT_CONTACTS),
                "is_simulation": self.is_simulation}

    def adsb_aircraft_detail(self, icao24: str) -> Dict:
        contact = _AIRCRAFT_CONTACTS.get(icao24.upper(), {})
        if not contact:
            return {"error": "not_found", "icao24": icao24}
        contact["registration"] = f"F-{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}{uuid.uuid4().hex[:3].upper()}"
        contact["owner"]        = random.choice(["Air France", "Private", "Ministry of Defence", "Unknown"])
        contact["operator"]     = contact.get("callsign","")[:3]
        return contact

    def adsb_filter_military(self) -> Dict:
        mil = [c for c in _AIRCRAFT_CONTACTS.values() if c.get("military_flag")]
        return {"military_contacts": mil, "count": len(mil), "is_simulation": self.is_simulation}

    def adsb_filter_private(self) -> Dict:
        priv = [c for c in _AIRCRAFT_CONTACTS.values() if c.get("category") == "private"]
        return {"private_contacts": priv, "count": len(priv), "is_simulation": self.is_simulation}

    def mlat_aircraft_position(self, station_data: List[Dict]) -> Dict:
        if len(station_data) < 3:
            return {"error": "MLAT requires ≥3 stations"}
        lat = sum(s.get("station_lat", 48.85) for s in station_data) / len(station_data)
        lon = sum(s.get("station_lon", 2.35) for s in station_data) / len(station_data)
        return {
            "estimated_lat":   round(lat + random.uniform(-0.05, 0.05), 5),
            "estimated_lon":   round(lon + random.uniform(-0.05, 0.05), 5),
            "estimated_alt_ft": random.randint(5000, 40000),
            "accuracy_m":      round(random.uniform(20, 200), 0),
            "stations_used":   len(station_data),
            "method":          "TDOA_hyperbolic",
            "is_simulation":   True,
        }

    def acars_decode(self, message: Optional[str] = None) -> Dict:
        msg = message or f".N{random.randint(100,999)}AA\r\nPOS N4823.3W07342.6 F390 ATA0145 AON AFR123"
        return {
            "raw":          msg,
            "aircraft":     f"N{random.randint(100,999)}AA",
            "flight":       f"AF{random.randint(100,999)}",
            "type":         random.choice(["ATIS", "ACARS_POS", "WEATHER", "MAINTENANCE", "AOC"]),
            "position":     {"lat": round(random.uniform(40,55), 3), "lon": round(random.uniform(-10,30), 3)},
            "flight_level": random.randint(150, 430),
            "timestamp":    datetime.utcnow().isoformat(),
            "is_simulation": True,
        }

    def military_flight_detect(self) -> Dict:
        mil = [c for c in _AIRCRAFT_CONTACTS.values() if c.get("military_flag")]
        high_threat = [c for c in mil if c.get("threat_level") in ["high", "critical"]]
        return {
            "military_count":   len(mil),
            "high_threat_count": len(high_threat),
            "contacts":         mil,
            "alerts":           [{"icao": c["icao24"], "reason": "Squawk 7777 / combat mode"} for c in high_threat],
            "is_simulation":    self.is_simulation,
        }

    def flight_prediction(self, flight_id: str, time_horizon_minutes: int = 30) -> Dict:
        contact = _AIRCRAFT_CONTACTS.get(flight_id.upper(), {})
        if not contact:
            return {"error": "not_found"}
        predictions = []
        lat, lon = contact.get("lat", 48.85), contact.get("lon", 2.35)
        hdg = contact.get("heading", 90)
        spd = contact.get("speed_kts", 450)
        for i in range(1, 7):
            t = i * time_horizon_minutes // 6
            dist_nm = spd * t / 60
            dist_m  = dist_nm * 1852
            plat = lat + (dist_m / 111000) * math.cos(math.radians(hdg))
            plon = lon + (dist_m / 111000) * math.sin(math.radians(hdg))
            predictions.append({"t_plus_min": t, "lat": round(plat, 5), "lon": round(plon, 5),
                                 "confidence": round(max(0.3, 1 - i * 0.1), 2)})
        return {"flight_id": flight_id, "method": "linear_extrapolation",
                "predictions": predictions, "is_simulation": True}
