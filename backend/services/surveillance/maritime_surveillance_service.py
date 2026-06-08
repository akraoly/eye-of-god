"""
Maritime Surveillance Service — Bloc 12 Surveillance Stratégique
AIS, navires militaires, détection anomalies, ZEE.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_VESSELS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/surveillance/maritime")
_OUTPUT.mkdir(parents=True, exist_ok=True)

MILITARY_MMSI_RANGES = {
    "US":     [(338000000,339999999),(366000000,369999999),(303000000,304999999)],
    "France": [(226000000,227999999),(228000000,229999999)],
    "UK":     [(232000000,235999999)],
    "Russia": [(273000000,274999999)],
    "China":  [(412000000,413999999),(414000000,415999999)],
    "India":  [(419000000,419999999)],
    "Germany":[(211000000,211999999)],
    "NATO_MCM": [(255000000,255999999)],
}

VESSEL_TYPES = {
    20: "Wing in ground",
    30: "Fishing",
    31: "Towing",
    36: "Sailing",
    37: "Pleasure craft",
    51: "Search and rescue",
    52: "Tug",
    60: "Passenger",
    70: "Cargo",
    80: "Tanker",
    35: "Military ops",
    55: "Law enforcement",
    58: "Medical transport",
}

MILITARY_VESSEL_NAMES = {
    "France": ["Jeanne d'Arc","Charles de Gaulle","Suffren","Duguay-Trouin","Mistral","Tonnerre","Dixmude"],
    "US":     ["USS Gerald Ford","USS Ronald Reagan","USS Nimitz","USS Stout","USS Ross","USNS Mercy"],
    "UK":     ["HMS Queen Elizabeth","HMS Prince of Wales","HMS Dragon","HMS Duncan"],
    "Russia": ["Admiral Kuznetsov","Marshal Ustinov","Slava","Moskva"],
}

FLAGS = ["France","Germany","Italy","Spain","Netherlands","Norway","Denmark","UK","US","Russia","China",
         "Japan","South Korea","Singapore","Greece","Malta","Panama","Liberia","Marshall Islands"]

CARGO_TYPES = ["General cargo","Containers","Bulk carrier","Oil tanker","Chemical tanker",
               "LNG","LPG","Ro-Ro","Vehicle carrier","Heavy lift","Refrigerated"]

NAV_STATUS = {0:"Under way using engine",1:"At anchor",2:"Not under command",3:"Restricted manoeuvrability",
              5:"Moored",7:"Engaged in fishing",8:"Under way sailing",15:"Not defined"}


class MaritimeSurveillanceService:

    def __init__(self):
        self.hardware = self._detect_hardware()
        self.is_simulation = True

    def _detect_hardware(self) -> Optional[Dict]:
        import subprocess
        for cmd, hw in [
            (["rtl_ais", "--version"], "rtl_ais"),
            (["rtl_test","-t"], "rtlsdr"),
        ]:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=2)
                if r.returncode == 0:
                    return {"type": hw}
            except Exception:
                pass
        return None

    def ais_receiver_start(self, lat: float = 48.85, lon: float = 2.35,
                            radius_km: float = 100) -> Dict:
        self._populate_vessels(lat, lon, radius_km)
        return {"status": "running", "vessels": len(_VESSELS),
                "observer_lat": lat, "observer_lon": lon,
                "radius_km": radius_km, "is_simulation": True}

    def ais_receiver_stop(self) -> Dict:
        return {"status": "stopped"}

    def _populate_vessels(self, clat: float, clon: float, radius_km: float,
                           count: int = 40) -> None:
        _VESSELS.clear()
        for _ in range(count):
            is_mil = random.random() < 0.10
            angle = random.uniform(0, 360)
            dist  = random.uniform(0, radius_km) * 1000
            lat = clat + (dist / 111000) * math.cos(math.radians(angle))
            lon = clon + (dist / 111000) * math.sin(math.radians(angle))

            if is_mil:
                country = random.choice(list(MILITARY_MMSI_RANGES.keys()))
                ranges = MILITARY_MMSI_RANGES[country]
                rng = random.choice(ranges)
                mmsi = random.randint(*rng)
                names = MILITARY_VESSEL_NAMES.get(country, [f"HMS_VESSEL_{random.randint(1,99)}"])
                name = random.choice(names)
                vtype = 35
                flag = country
            else:
                mmsi = random.randint(200000000, 799999999)
                name = f"MV {''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=6))}"
                vtype = random.choice([70, 80, 60, 30, 37, 51, 52])
                flag = random.choice(FLAGS)

            nav_status_code = random.choice(list(NAV_STATUS.keys()))
            speed = round(random.uniform(0, 22), 1) if nav_status_code == 0 else 0.0
            vessel = {
                "mmsi":          mmsi,
                "vessel_name":   name,
                "vessel_type":   vtype,
                "vessel_type_desc": VESSEL_TYPES.get(vtype, "Unknown"),
                "flag_country":  flag,
                "callsign":      f"F{''.join(random.choices('ABCDEFGHIJ', k=3))}",
                "lat":           round(lat, 5),
                "lon":           round(lon, 5),
                "speed_kts":     speed,
                "heading":       round(random.uniform(0, 360), 0),
                "nav_status":    nav_status_code,
                "nav_status_desc": NAV_STATUS[nav_status_code],
                "destination":   random.choice(["FRFOS","GBLON","DEHAM","NLRTM","ESMAD","ITGOA",""]),
                "cargo_type":    random.choice(CARGO_TYPES) if vtype in [70,80] else None,
                "draught_m":     round(random.uniform(3, 22), 1),
                "ais_class":     "A" if vtype in [70,80,60] else "B",
                "ais_active":    True,
                "military_flag": is_mil,
                "suspicious_flag": False,
                "source":        "ais_terrestrial",
                "first_seen":    datetime.utcnow().isoformat(),
                "last_seen":     datetime.utcnow().isoformat(),
                "is_simulation": True,
            }
            _VESSELS[str(mmsi)] = vessel

    def ais_vessels(self) -> Dict:
        return {"vessels": list(_VESSELS.values()), "total": len(_VESSELS), "is_simulation": True}

    def ais_ship_detail(self, mmsi: int) -> Dict:
        v = _VESSELS.get(str(mmsi), {})
        if not v:
            return {"error": "not_found", "mmsi": mmsi}
        v["imo"] = random.randint(7000000, 9999999)
        v["length_m"] = random.randint(50, 400)
        v["beam_m"]   = random.randint(10, 60)
        return v

    def ais_filter_military(self) -> Dict:
        mil = [v for v in _VESSELS.values() if v.get("military_flag")]
        return {"military_vessels": mil, "count": len(mil), "is_simulation": True}

    def ais_filter_suspicious(self) -> Dict:
        suspicious = []
        for v in _VESSELS.values():
            reasons = []
            if v.get("speed_kts", 0) > 20 and v.get("vessel_type") == 80:
                reasons.append("Tanker exceeding max speed")
            if random.random() < 0.05:
                reasons.append("AIS gap > 2 hours detected")
                v["suspicious_flag"] = True
            if reasons:
                suspicious.append({**v, "suspicion_reasons": reasons})
        return {"suspicious_vessels": suspicious, "count": len(suspicious), "is_simulation": True}

    def ais_anomaly_detect(self, vessel_id: str) -> Dict:
        vessel = _VESSELS.get(vessel_id, {})
        anomalies = []
        if random.random() < 0.4:
            anomalies.append({"type": "loitering", "desc": "Vessel circling same 2km area > 4 hours"})
        if random.random() < 0.2:
            anomalies.append({"type": "dark_ship", "desc": "AIS off for 6h, reappears 50km away"})
        if random.random() < 0.15:
            anomalies.append({"type": "sts_transfer", "desc": "Ship-to-ship transfer detected (AIS proximity)"})
        return {
            "vessel_id":  vessel_id,
            "vessel_name": vessel.get("vessel_name", "Unknown"),
            "anomalies":  anomalies,
            "risk_level": "HIGH" if len(anomalies) > 1 else ("MEDIUM" if anomalies else "LOW"),
            "is_simulation": True,
        }

    def vessel_trajectory_prediction(self, vessel_id: str, hours: int = 12) -> Dict:
        vessel = _VESSELS.get(vessel_id, {})
        if not vessel:
            return {"error": "not_found"}
        predictions = []
        lat, lon = vessel.get("lat", 48.85), vessel.get("lon", 2.35)
        spd = vessel.get("speed_kts", 12)
        hdg = vessel.get("heading", 90)
        for i in range(1, hours+1):
            dist_nm = spd * i
            dist_m  = dist_nm * 1852
            plat = lat + (dist_m / 111000) * math.cos(math.radians(hdg))
            plon = lon + (dist_m / 111000) * math.sin(math.radians(hdg))
            predictions.append({"t_plus_hours": i, "lat": round(plat, 5), "lon": round(plon, 5),
                                 "confidence": round(max(0.2, 1 - i * 0.05), 2)})
        return {"vessel_id": vessel_id, "predictions": predictions, "is_simulation": True}

    def exclusive_economic_zone_monitor(self, eez_name: str = "French_EEZ") -> Dict:
        entering = [v for v in _VESSELS.values() if random.random() < 0.05]
        for v in entering:
            v["suspicious_flag"] = True
        return {
            "eez":          eez_name,
            "vessels_in_zone": len(_VESSELS),
            "recent_entries": len(entering),
            "military_in_zone": len([v for v in _VESSELS.values() if v.get("military_flag")]),
            "alerts":        [{"mmsi": v["mmsi"], "name": v["vessel_name"], "flag": v["flag_country"]}
                               for v in entering[:5]],
            "is_simulation": True,
        }
