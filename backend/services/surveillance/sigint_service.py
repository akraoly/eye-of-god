"""
SIGINT Service — Bloc 12 Surveillance Stratégique
Scan large bande, classification signaux, DF, géolocalisation.
"""
from __future__ import annotations

import logging
import math
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_CAPTURES: Dict[str, Dict] = {}
_EMITTERS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/surveillance/sigint")
_OUTPUT.mkdir(parents=True, exist_ok=True)

SUPPORTED_PROTOCOLS = [
    "AM","FM","SSB","NFM","WFM","BPSK","QPSK","8PSK","16QAM","64QAM","256QAM",
    "FSK","GMSK","OFDM","DMR","P25","TETRA","D-STAR","C4FM","LoRa",
    "AIS","ADS-B","ACARS","POCSAG","FLEX","APRS","NOAA-APT","Iridium","Inmarsat",
]

MODULATION_PARAMS = {
    "AM":     {"bandwidth_khz": 10,    "note": "Amplitude Modulation — HF/MF broadcast"},
    "FM":     {"bandwidth_khz": 200,   "note": "Frequency Modulation — VHF broadcast"},
    "SSB":    {"bandwidth_khz": 3,     "note": "Single Sideband — HF comms"},
    "NFM":    {"bandwidth_khz": 12.5,  "note": "Narrowband FM — land mobile"},
    "BPSK":   {"bandwidth_khz": 5,     "note": "Binary PSK — satellite data"},
    "QPSK":   {"bandwidth_khz": 20,    "note": "Quad PSK — cellular, satellite"},
    "OFDM":   {"bandwidth_khz": 5000,  "note": "WiFi, LTE, DAB/DVB"},
    "GMSK":   {"bandwidth_khz": 250,   "note": "GSM channels"},
    "DMR":    {"bandwidth_khz": 12.5,  "note": "Digital Mobile Radio ETSI"},
    "TETRA":  {"bandwidth_khz": 25,    "note": "Terrestrial Trunked Radio — emergency services"},
    "LoRa":   {"bandwidth_khz": 125,   "note": "Long Range IoT — 868/915 MHz"},
    "AIS":    {"bandwidth_khz": 12.5,  "note": "Maritime vessel tracking — 161.975/162.025 MHz"},
    "ADS-B":  {"bandwidth_mhz": 3,     "note": "Aircraft surveillance — 1090 MHz"},
}

FREQUENCY_ALLOCATIONS = {
    (0.1,   1.7):  "LF/MF — beacons, AM broadcast, maritime",
    (1.7,   30):   "HF — shortwave, military HF, amateur",
    (30,    300):  "VHF — FM broadcast, aircraft, emergency services",
    (300,   3000): "UHF — cellular, military, GPS, WiFi",
    (3000,  30000):"SHF/Microwave — radar, satellite, backhaul",
}

DF_METHODS = {
    "tdoa":    "Time Difference of Arrival — requires ≥3 synchronized stations, accuracy 50-200m",
    "aoa":     "Angle of Arrival — single station with directional antenna, accuracy ±2°",
    "rssi":    "RSS-based trilateration — coarse accuracy 100-500m",
    "doppler": "Doppler DF — moving platform, accuracy ±5°",
    "watson_watt": "Watson-Watt — simple 2-element array, accuracy ±5°",
}


class SigintService:

    def __init__(self):
        self.hardware = self._detect_hardware()
        self.is_simulation = self.hardware is None

    def _detect_hardware(self) -> Optional[Dict]:
        import subprocess
        for cmd, hw in [(["rtl_test","-t"],"rtlsdr"), (["hackrf_info"],"hackrf")]:
            try:
                r = subprocess.run(cmd, capture_output=True, timeout=2)
                if r.returncode == 0:
                    return {"type": hw}
            except Exception:
                pass
        return None

    def scanner_wideband(self, start_freq: float, stop_freq: float,
                          step_hz: float = 25000, rbw: float = 10000) -> Dict:
        signals = []
        freq = start_freq
        while freq <= stop_freq:
            if random.random() > 0.65:
                protocol = random.choice(SUPPORTED_PROTOCOLS[:15])
                bw_params = MODULATION_PARAMS.get(protocol, {"bandwidth_khz": 25})
                bw = bw_params.get("bandwidth_khz", 25) * 1000
                signals.append({
                    "frequency_hz":  freq,
                    "frequency_mhz": round(freq / 1e6, 4),
                    "power_dbm":     round(random.uniform(-90, -20), 1),
                    "bandwidth_hz":  bw,
                    "modulation":    random.choice(["FM","AM","FSK","PSK","OFDM","unknown"]),
                    "protocol_guess": protocol,
                    "snr_db":        round(random.uniform(5, 40), 1),
                })
            freq += step_hz * random.uniform(1, 20)
        return {
            "start_hz":     start_freq,
            "stop_hz":      stop_freq,
            "step_hz":      step_hz,
            "rbw_hz":       rbw,
            "signals_found": len(signals),
            "signals":      signals,
            "scan_time_s":  round((stop_freq - start_freq) / (step_hz * 100), 1),
            "is_simulation": True,
        }

    def automatic_signal_classification(self, snr_db: float = 20.0,
                                          freq_mhz: float = 433.0) -> Dict:
        candidates = []
        for protocol, params in MODULATION_PARAMS.items():
            score = random.uniform(0, 100) + (snr_db * 0.5)
            candidates.append({"protocol": protocol, "confidence": round(min(0.99, score/150), 2),
                                "note": params.get("note","")})
        candidates.sort(key=lambda x: -x["confidence"])
        return {
            "frequency_mhz": freq_mhz,
            "snr_db":        snr_db,
            "top_matches":   candidates[:5],
            "best_guess":    candidates[0],
            "is_simulation": True,
        }

    def demodulate(self, freq_mhz: float, modulation: str,
                    bandwidth_khz: float = 200) -> Dict:
        capture_id = f"cap_{uuid.uuid4().hex[:8]}"
        demod_output = {
            "AM":   f"News broadcast fragment... {uuid.uuid4().hex[:20]}",
            "FM":   "Music/voice audio content",
            "SSB":  "HF voice comms — partial: '...confirm coordinates...'",
            "NFM":  "Land mobile voice fragment",
            "FSK":  f"Hex data: {uuid.uuid4().hex[:32]}",
            "BPSK": f"Binary data stream: {uuid.uuid4().hex[:40]}",
        }
        result = {
            "capture_id":    capture_id,
            "frequency_mhz": freq_mhz,
            "modulation":    modulation,
            "bandwidth_khz": bandwidth_khz,
            "snr_db":        round(random.uniform(10, 35), 1),
            "rssi_dbm":      round(random.uniform(-80, -30), 1),
            "demodulated":   demod_output.get(modulation.upper(), f"Raw data: {uuid.uuid4().hex[:32]}"),
            "audio_available": modulation in ["AM","FM","SSB","NFM"],
            "is_simulation": True,
        }
        _CAPTURES[capture_id] = result
        return result

    def direction_finding(self, signal_freq_mhz: float,
                           station_data: Optional[List[Dict]] = None,
                           method: str = "tdoa") -> Dict:
        method_info = DF_METHODS.get(method, DF_METHODS["tdoa"])
        stations = station_data or [
            {"id": "S1", "lat": 48.85, "lon": 2.35, "bearing_deg": random.uniform(0,360), "tdoa_us": 0},
            {"id": "S2", "lat": 48.90, "lon": 2.45, "bearing_deg": random.uniform(0,360), "tdoa_us": random.uniform(-5,5)},
            {"id": "S3", "lat": 48.80, "lon": 2.30, "bearing_deg": random.uniform(0,360), "tdoa_us": random.uniform(-5,5)},
        ]
        center_lat = sum(s.get("lat",48.85) for s in stations) / len(stations)
        center_lon = sum(s.get("lon",2.35) for s in stations) / len(stations)
        return {
            "signal_freq_mhz": signal_freq_mhz,
            "method":          method,
            "method_desc":     method_info,
            "stations_used":   len(stations),
            "estimated_lat":   round(center_lat + random.uniform(-0.05,0.05), 5),
            "estimated_lon":   round(center_lon + random.uniform(-0.05,0.05), 5),
            "accuracy_m":      round(random.uniform(50, 500), 0),
            "confidence":      round(random.uniform(0.6, 0.95), 2),
            "is_simulation":   True,
        }

    def signal_geolocate(self, station_bearings: List[Dict]) -> Dict:
        if len(station_bearings) < 2:
            return {"error": "Need ≥2 stations for triangulation"}
        lat = sum(s.get("lat",48.85) for s in station_bearings) / len(station_bearings)
        lon = sum(s.get("lon",2.35) for s in station_bearings) / len(station_bearings)
        return {
            "estimated_lat":  round(lat + random.uniform(-0.02, 0.02), 5),
            "estimated_lon":  round(lon + random.uniform(-0.02, 0.02), 5),
            "accuracy_km":    round(random.uniform(0.5, 10), 2),
            "method":         "triangulation_bearing_intersection",
            "stations":       len(station_bearings),
            "is_simulation":  True,
        }

    def frequency_hopping_track(self, base_freq_mhz: float, hop_rate_hz: float = 100) -> Dict:
        hop_sequence = sorted(set(round(base_freq_mhz + random.uniform(-5, 5), 3) for _ in range(20)))
        return {
            "base_freq_mhz":  base_freq_mhz,
            "hop_rate_hz":    hop_rate_hz,
            "hop_sequence_mhz": hop_sequence,
            "hop_count":      len(hop_sequence),
            "dwell_time_ms":  round(1000 / hop_rate_hz, 2),
            "protocol_guess": "FHSS (TETRA/military/BT)" if hop_rate_hz > 1000 else "Adaptive FHSS",
            "is_simulation":  True,
        }

    def burst_detection(self, freq_mhz: float, window_s: float = 60) -> Dict:
        bursts = [
            {"t_offset_ms": round(random.uniform(0, window_s*1000), 0),
             "duration_ms": round(random.uniform(0.5, 50), 2),
             "power_dbm":   round(random.uniform(-70,-20), 1),
             "bandwidth_khz": round(random.uniform(5, 500), 1)}
            for _ in range(random.randint(2, 20))
        ]
        bursts.sort(key=lambda x: x["t_offset_ms"])
        return {
            "frequency_mhz": freq_mhz,
            "window_s":      window_s,
            "bursts_detected": len(bursts),
            "bursts":        bursts,
            "duty_cycle_pct": round(sum(b["duration_ms"] for b in bursts) / (window_s * 10), 2),
            "is_simulation": True,
        }

    def emitters_database_update(self, freq_mhz: float, modulation: str,
                                   power_dbm: float, location: Optional[Dict] = None) -> Dict:
        emitter_id = f"emit_{uuid.uuid4().hex[:8]}"
        entry = {
            "emitter_id":    emitter_id,
            "frequency_mhz": freq_mhz,
            "modulation":    modulation,
            "power_dbm":     power_dbm,
            "location":      location,
            "fingerprint":   uuid.uuid4().hex[:16],
            "first_seen":    datetime.utcnow().isoformat(),
            "is_simulation": True,
        }
        _EMITTERS[emitter_id] = entry
        return entry

    def list_protocols(self) -> List[str]:
        return SUPPORTED_PROTOCOLS

    def list_df_methods(self) -> Dict:
        return DF_METHODS

    def get_capture(self, capture_id: str) -> Dict:
        return _CAPTURES.get(capture_id, {"error": "not_found"})

    def list_emitters(self) -> Dict:
        return {"emitters": list(_EMITTERS.values()), "count": len(_EMITTERS)}
