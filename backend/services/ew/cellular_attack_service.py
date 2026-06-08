"""
Cellular Attack Service — Bloc 11 EW
IMSI catcher, BTS spoofing, SS7/Diameter attacks, downgrade.
Simulation uniquement — usage légal pentest autorisé uniquement.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_IMSI_CAPTURES: Dict[str, Dict] = {}
_BTS_CONTACTS:  Dict[str, Dict] = {}
_OUTPUT = Path("./data/ew/cellular")
_OUTPUT.mkdir(parents=True, exist_ok=True)

FREQUENCY_BANDS = {
    "gsm900":     {"uplink": (890,915),   "downlink": (935,960),   "gen": "2G"},
    "gsm1800":    {"uplink": (1710,1785), "downlink": (1805,1880), "gen": "2G"},
    "umts_2100":  {"uplink": (1920,1980), "downlink": (2110,2170), "gen": "3G"},
    "lte_band1":  {"uplink": (1920,1980), "downlink": (2110,2170), "gen": "4G"},
    "lte_band3":  {"uplink": (1710,1785), "downlink": (1805,1880), "gen": "4G"},
    "lte_band7":  {"uplink": (2500,2570), "downlink": (2620,2690), "gen": "4G"},
    "lte_band20": {"uplink": (832,862),   "downlink": (791,821),   "gen": "4G"},
    "nr_n78":     {"uplink": (3300,3800), "downlink": (3300,3800), "gen": "5G"},
}

SS7_ATTACKS = {
    "location_query":    "MAP ATI/SRI → Get subscriber location from HLR/VLR",
    "sms_intercept":     "MAP SRI-SM + SendRoutingInfoForSM → Intercept SMS via SMSC",
    "call_forwarding":   "MAP RegisterSS → Set unconditional call forward to attacker",
    "call_intercept":    "MAP manipulation → Insert attacker as STP for CAMEL intercept",
    "imsi_lookup":       "MAP SRI → Resolve MSISDN to IMSI",
}

DIAMETER_ATTACKS = {
    "location_query":   "S6a ULR/ULA → Get subscriber location from MME",
    "subscriber_info":  "S6a AIR → Get authentication vectors",
    "purge_ue":         "S6a PUR → Force UE purge from network (DoS)",
    "cancel_location":  "S6a CLR → Cancel location in HSS",
}

OPERATORS_FR = [
    {"name": "Orange",   "mcc": "208", "mnc": "01", "mnc2": "91"},
    {"name": "SFR",      "mcc": "208", "mnc": "10", "mnc2": "11"},
    {"name": "Bouygues", "mcc": "208", "mnc": "20"},
    {"name": "Free",     "mcc": "208", "mnc": "15", "mnc2": "16"},
]


class CellularAttackService:

    def __init__(self):
        self.is_simulation = True

    def detect_bts(self, frequency_band: str = "gsm900") -> Dict:
        band_info = FREQUENCY_BANDS.get(frequency_band, FREQUENCY_BANDS["gsm900"])
        num_bts = random.randint(3, 12)
        stations = []
        for i in range(num_bts):
            op = random.choice(OPERATORS_FR)
            dl_min, dl_max = band_info["downlink"]
            stations.append({
                "bts_id":       f"bts_{uuid.uuid4().hex[:8]}",
                "operator":     op["name"],
                "mcc":          op["mcc"],
                "mnc":          op.get("mnc", "01"),
                "cell_id":      random.randint(10000, 99999),
                "lac":          random.randint(100, 9999),
                "band":         frequency_band,
                "generation":   band_info["gen"],
                "downlink_mhz": round(random.uniform(dl_min, dl_max), 3),
                "arfcn":        random.randint(0, 1023),
                "rssi_dbm":     random.randint(-100, -50),
                "rx_level":     random.randint(0, 63),
                "type":         random.choice(["macro", "micro", "pico", "femto"]),
                "is_simulation": True,
            })
        _BTS_CONTACTS.update({s["bts_id"]: s for s in stations})
        return {"band": frequency_band, "bts_found": len(stations), "stations": stations, "is_simulation": True}

    def imsi_catcher_advanced(self, band: str = "gsm900", capture_mode: str = "passive") -> Dict:
        session_id = f"imsi_{uuid.uuid4().hex[:8]}"
        imsis_captured = []
        for _ in range(random.randint(5, 30)):
            mcc = "208"
            mnc = random.choice(["01","10","15","20"])
            msin = "".join(str(random.randint(0,9)) for _ in range(10))
            imsi = f"{mcc}{mnc}{msin}"
            imsis_captured.append({
                "imsi":       imsi,
                "msisdn":     f"+336{''.join(str(random.randint(0,9)) for _ in range(8))}",
                "tmsi":       f"{random.randint(0,0xFFFFFFFF):08X}",
                "rssi_dbm":   random.randint(-90, -40),
                "timestamp":  datetime.utcnow().isoformat(),
                "operator":   random.choice([o["name"] for o in OPERATORS_FR]),
                "device_type": random.choice(["Smartphone","Feature phone","IoT","Tablet","Modem"]),
            })
        result = {
            "session_id":     session_id,
            "band":           band,
            "capture_mode":   capture_mode,
            "imsi_count":     len(imsis_captured),
            "imsis":          imsis_captured,
            "duration_s":     random.randint(30, 300),
            "is_simulation":  True,
            "note":           "Simulation — IMSI catching is illegal without lawful intercept authority",
        }
        _IMSI_CAPTURES[session_id] = result
        return result

    def selective_jamming(self, imsi_list: List[str], band: str = "gsm900") -> Dict:
        return {
            "type":          "selective_jam",
            "imsi_targets":  imsi_list,
            "band":          band,
            "method":        "Spoof paging channel to prevent target UE from receiving calls/SMS while keeping others connected",
            "expected_effect": f"{len(imsi_list)} specific subscribers denied service",
            "is_simulation": True,
        }

    def bts_spoofing(self, mcc: str = "208", mnc: str = "01",
                     cell_id: int = 12345, band: str = "gsm900") -> Dict:
        band_info = FREQUENCY_BANDS.get(band, FREQUENCY_BANDS["gsm900"])
        dl_min, dl_max = band_info["downlink"]
        return {
            "type":          "fake_bts",
            "mcc":           mcc,
            "mnc":           mnc,
            "cell_id":       cell_id,
            "band":          band,
            "generation":    band_info["gen"],
            "downlink_mhz":  round(random.uniform(dl_min, dl_max), 3),
            "tx_power_dbm":  random.randint(10, 43),
            "expected_effect": "UEs within range re-register to fake BTS — traffic interception possible",
            "tools_needed":  ["YateBTS", "OpenBTS", "OsmocomBB", "HackRF"],
            "is_simulation": True,
        }

    def downgrade_attack(self, target_imsi: Optional[str] = None) -> Dict:
        downgrade_chain = ["5G-NR", "4G-LTE", "3G-UMTS", "2G-GSM"]
        return {
            "target_imsi":   target_imsi or "208010000000001",
            "downgrade_chain": downgrade_chain,
            "method":        "Jam 5G/4G frequencies — UE falls back to GSM (no encryption on A5/0, weak A5/1)",
            "vulnerability": "GSM A5/1 known-plaintext attack — Barkan-Biham-Keller",
            "success_probability": round(random.uniform(0.60, 0.85), 2),
            "is_simulation": True,
        }

    def ss7_attack(self, msisdn: str, attack_type: str = "location_query") -> Dict:
        desc = SS7_ATTACKS.get(attack_type, "Unknown attack")
        return {
            "target_msisdn": msisdn,
            "attack_type":   attack_type,
            "description":   desc,
            "protocol":      "SS7 MAP",
            "required_access": "SS7 Point Code (telco network access)",
            "result": {
                "location":   "Paris, France (lat: 48.85, lon: 2.35)" if "location" in attack_type else None,
                "imsi":       f"208010{''.join(str(random.randint(0,9)) for _ in range(10))}" if "imsi" in attack_type else None,
                "status":     "success",
            },
            "is_simulation": True,
        }

    def diameter_attack(self, imsi: str, attack_type: str = "location_query") -> Dict:
        desc = DIAMETER_ATTACKS.get(attack_type, "Unknown")
        return {
            "target_imsi":   imsi,
            "attack_type":   attack_type,
            "description":   desc,
            "protocol":      "Diameter S6a",
            "required_access": "Roaming partner / rogue HSS on IPX",
            "result":        {"status": "success", "data": "See simulation output"},
            "is_simulation": True,
        }

    def list_captures(self) -> Dict:
        return {"sessions": list(_IMSI_CAPTURES.keys()), "count": len(_IMSI_CAPTURES)}

    def get_capture(self, session_id: str) -> Dict:
        return _IMSI_CAPTURES.get(session_id, {"error": "not_found"})
