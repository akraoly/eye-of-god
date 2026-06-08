"""
RF Jamming Service — Bloc 11 Guerre Électronique
Brouillage large spectre, protocoles, bandes prédéfinies.
Simulation mode by default — real TX requires hardware + authorization_confirmed.
"""
from __future__ import annotations

import logging
import math
import random
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ACTIVE_JAMS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/ew/jamming")
_OUTPUT.mkdir(parents=True, exist_ok=True)

PREDEFINED_BANDS: Dict[str, Dict] = {
    "2.4ghz_wifi":        {"center": 2450,    "bandwidth": 80,   "protocol": "wifi"},
    "5ghz_wifi":          {"center": 5250,    "bandwidth": 160,  "protocol": "wifi"},
    "gsm900":             {"center": 925,     "bandwidth": 35,   "protocol": "gsm"},
    "gsm1800":            {"center": 1840,    "bandwidth": 75,   "protocol": "gsm"},
    "gps_l1":             {"center": 1575.42, "bandwidth": 2,    "protocol": "gps"},
    "gps_l2":             {"center": 1227.6,  "bandwidth": 2,    "protocol": "gps"},
    "ism_433":            {"center": 433.92,  "bandwidth": 1.74, "protocol": "ism"},
    "ism_868":            {"center": 868,     "bandwidth": 2,    "protocol": "ism"},
    "cellular_lte_band3": {"center": 1840,    "bandwidth": 20,   "protocol": "lte"},
    "cellular_lte_band7": {"center": 2655,    "bandwidth": 20,   "protocol": "lte"},
    "radar_x":            {"center": 9500,    "bandwidth": 200,  "protocol": "radar"},
    "radar_s":            {"center": 3200,    "bandwidth": 300,  "protocol": "radar"},
    "military_uhf":       {"center": 450,     "bandwidth": 50,   "protocol": "military"},
    "military_vhf":       {"center": 160,     "bandwidth": 20,   "protocol": "military"},
    "satcom_c":           {"center": 4000,    "bandwidth": 500,  "protocol": "satcom"},
    "satcom_ku":          {"center": 12000,   "bandwidth": 1000, "protocol": "satcom"},
}

WAVEFORMS = ["noise", "chirp", "sweep", "pulse", "fm_noise", "custom_iq"]
JAM_MODES  = ["continuous", "duty_cycled", "reactive"]

PROTOCOL_JAM_PARAMS = {
    "wifi":     {"waveform": "chirp",    "duty_cycle": 0.9, "note": "Targets beacon frames + probe responses"},
    "gsm":      {"waveform": "noise",    "duty_cycle": 1.0, "note": "RACH flood on BCCH"},
    "gps":      {"waveform": "fm_noise", "duty_cycle": 1.0, "note": "C/A code noise injection"},
    "lte":      {"waveform": "sweep",    "duty_cycle": 0.95,"note": "PDCCH + PBCH disruption"},
    "ism":      {"waveform": "pulse",    "duty_cycle": 0.7, "note": "FSK/OOK disruption"},
    "radar":    {"waveform": "noise",    "duty_cycle": 1.0, "note": "Noise barrage on PRF"},
    "military": {"waveform": "custom_iq","duty_cycle": 1.0, "note": "Adaptive waveform"},
    "satcom":   {"waveform": "noise",    "duty_cycle": 1.0, "note": "Uplink disruption"},
}


class JammingService:

    def __init__(self):
        self.hardware = self._detect_hardware()
        self.is_simulation = self.hardware is None
        logger.info(f"JammingService init — simulation={self.is_simulation}, hw={self.hardware}")

    # ── Hardware detection ────────────────────────────────────────────────────

    def _detect_hardware(self) -> Optional[Dict]:
        checks = [
            (["hackrf_info"], "hackrf"),
            (["bladeRF-cli", "-v"], "bladerf"),
            (["uhd_find_devices"], "usrp"),
            (["LimeSuite", "--find"], "limesdr"),
            (["rtl_test", "-t"], "rtlsdr"),
        ]
        for cmd, hw_type in checks:
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=2)
                if r.returncode == 0:
                    return {"type": hw_type, "info": r.stdout.strip()[:100]}
            except Exception:
                pass
        return None

    def detect_hardware(self) -> Dict:
        hw = self._detect_hardware()
        self.hardware = hw
        self.is_simulation = hw is None
        return {"hardware": hw, "is_simulation": self.is_simulation,
                "capable_tx": hw is not None and hw["type"] in ["hackrf","bladerf","usrp","limesdr"]}

    # ── Spectrum scan ─────────────────────────────────────────────────────────

    def scan_spectrum(self, start_freq: float, end_freq: float, bandwidth: float = 1.0) -> Dict:
        if self.is_simulation:
            return self._sim_spectrum_scan(start_freq, end_freq, bandwidth)
        try:
            result = subprocess.run(
                ["rtl_power", "-f", f"{int(start_freq*1e6)}:{int(end_freq*1e6)}:{int(bandwidth*1e6)}",
                 "-g", "40", "-e", "5s", "-"],
                capture_output=True, text=True, timeout=10
            )
            return {"raw": result.stdout[:2000], "is_simulation": False}
        except Exception as e:
            logger.warning(f"scan_spectrum fallback: {e}")
            return self._sim_spectrum_scan(start_freq, end_freq, bandwidth)

    def _sim_spectrum_scan(self, start: float, end: float, bw: float) -> Dict:
        occupied = []
        freq = start
        while freq < end:
            if random.random() > 0.6:
                signal = {
                    "freq_mhz": round(freq, 3),
                    "power_dbm": round(random.uniform(-90, -20), 1),
                    "bandwidth_mhz": round(random.uniform(0.2, bw), 2),
                    "modulation": random.choice(["FM", "AM", "FSK", "OFDM", "unknown"]),
                }
                occupied.append(signal)
            freq += bw * random.uniform(0.8, 2.5)
        return {"start_mhz": start, "end_mhz": end, "occupied_bands": occupied,
                "total_signals": len(occupied), "scan_time_ms": random.randint(200, 2000),
                "is_simulation": True}

    # ── Jam operations ────────────────────────────────────────────────────────

    def jam_frequency(self, freq: float, bandwidth: float = 10.0, power: float = 10.0,
                      waveform: str = "noise", mode: str = "continuous",
                      target_lat: Optional[float] = None, target_lon: Optional[float] = None) -> Dict:
        if not self.is_simulation:
            logger.warning("Real TX not implemented — falling back to simulation")
        return self._simulate_jam(freq, bandwidth, power, waveform, mode, target_lat, target_lon)

    def _simulate_jam(self, freq, bandwidth, power, waveform, mode,
                      target_lat=None, target_lon=None, band_name=None, protocol=None) -> Dict:
        channel_id = f"jam_{uuid.uuid4().hex[:8]}"
        jam = {
            "channel_id":       channel_id,
            "frequency_mhz":    freq,
            "bandwidth_mhz":    bandwidth,
            "power_dbm":        power,
            "waveform":         waveform,
            "mode":             mode,
            "band_name":        band_name,
            "protocol":         protocol,
            "status":           "active",
            "start_time":       datetime.utcnow().isoformat(),
            "target_lat":       target_lat,
            "target_lon":       target_lon,
            "is_simulation":    True,
            "effectiveness_pct": round(random.uniform(70, 99), 1),
            "noise_floor_dbm":  round(power - random.uniform(10, 30), 1),
        }
        _ACTIVE_JAMS[channel_id] = jam
        logger.info(f"Jam started: {channel_id} @ {freq} MHz, {bandwidth} MHz BW, {power} dBm")
        return jam

    def jam_band(self, band_name: str, power: float = 20.0, mode: str = "continuous") -> Dict:
        band = PREDEFINED_BANDS.get(band_name)
        if not band:
            return {"error": f"Unknown band: {band_name}", "available": list(PREDEFINED_BANDS.keys())}
        params = PROTOCOL_JAM_PARAMS.get(band["protocol"], {})
        waveform = params.get("waveform", "noise")
        return self._simulate_jam(band["center"], band["bandwidth"], power, waveform, mode,
                                   band_name=band_name, protocol=band["protocol"])

    def sweep_jam(self, start_freq: float, end_freq: float, step: float = 10.0,
                  dwell_time: float = 0.1, power: float = 20.0) -> Dict:
        channel_id = f"sweep_{uuid.uuid4().hex[:8]}"
        steps_count = int((end_freq - start_freq) / step)
        jam = {
            "channel_id":   channel_id,
            "type":         "sweep",
            "start_mhz":    start_freq,
            "end_mhz":      end_freq,
            "step_mhz":     step,
            "dwell_time_s": dwell_time,
            "power_dbm":    power,
            "sweep_rate_mhz_s": round(step / dwell_time, 1),
            "total_steps":  steps_count,
            "cycle_time_s": round(steps_count * dwell_time, 2),
            "status":       "active",
            "start_time":   datetime.utcnow().isoformat(),
            "is_simulation": True,
        }
        _ACTIVE_JAMS[channel_id] = jam
        return jam

    def protocol_aware_jam(self, protocol: str, power: float = 20.0) -> Dict:
        params = PROTOCOL_JAM_PARAMS.get(protocol.lower())
        if not params:
            return {"error": f"Unknown protocol: {protocol}"}
        matching_bands = {k: v for k, v in PREDEFINED_BANDS.items() if v["protocol"] == protocol.lower()}
        results = []
        for band_name, band in matching_bands.items():
            j = self._simulate_jam(band["center"], band["bandwidth"], power,
                                    params["waveform"], "continuous",
                                    band_name=band_name, protocol=protocol)
            results.append(j)
        if not results:
            results.append(self._simulate_jam(433.92, 10, power, params["waveform"], "continuous",
                                               protocol=protocol))
        return {"protocol": protocol, "jams_started": len(results), "channels": results,
                "note": params.get("note",""), "is_simulation": True}

    def stop_jam(self, channel_id: str) -> Dict:
        jam = _ACTIVE_JAMS.pop(channel_id, None)
        if not jam:
            return {"error": "not_found", "channel_id": channel_id}
        jam["status"] = "stopped"
        jam["end_time"] = datetime.utcnow().isoformat()
        return jam

    def stop_all_jams(self) -> Dict:
        stopped = []
        for cid in list(_ACTIVE_JAMS.keys()):
            j = _ACTIVE_JAMS.pop(cid)
            j["status"] = "stopped"
            j["end_time"] = datetime.utcnow().isoformat()
            stopped.append(cid)
        return {"stopped_channels": stopped, "count": len(stopped)}

    def get_jam_status(self) -> Dict:
        return {
            "active_jams": len(_ACTIVE_JAMS),
            "channels": list(_ACTIVE_JAMS.values()),
            "hardware": self.hardware,
            "is_simulation": self.is_simulation,
        }

    # ── Utility ───────────────────────────────────────────────────────────────

    def calculate_power_requirement(self, range_meters: float, freq_mhz: float) -> Dict:
        freq_hz = freq_mhz * 1e6
        wavelength = 3e8 / freq_hz
        # Friis + jamming margin 30dB
        path_loss_db = 20 * math.log10(4 * math.pi * range_meters / wavelength)
        required_dbm = round(path_loss_db - 100 + 30, 1)
        return {
            "range_meters":    range_meters,
            "frequency_mhz":   freq_mhz,
            "path_loss_db":    round(path_loss_db, 1),
            "required_power_dbm": required_dbm,
            "required_power_w":   round(10 ** ((required_dbm - 30) / 10), 4),
            "hardware_capable": self.hardware is not None,
            "note": "Includes 30dB jamming margin over target receiver sensitivity (-100dBm)",
        }

    def select_waveform(self, jam_type: str) -> Dict:
        wf_map = {
            "broadband":  "noise",
            "spot":       "chirp",
            "sweep":      "sweep",
            "pulse":      "pulse",
            "fm":         "fm_noise",
            "smart":      "custom_iq",
            "protocol":   "chirp",
        }
        wf = wf_map.get(jam_type.lower(), "noise")
        return {"jam_type": jam_type, "recommended_waveform": wf,
                "all_waveforms": WAVEFORMS, "is_simulation": self.is_simulation}

    def list_bands(self) -> Dict:
        return PREDEFINED_BANDS

    def get_active_jams(self) -> List[Dict]:
        return list(_ACTIVE_JAMS.values())


class RFJammingEngine:
    """Low-level RF jamming engine — wraps JammingService with direct IQ output."""

    def __init__(self):
        self.svc = JammingService()

    def generate_noise_waveform(self, bandwidth_hz: float, sample_rate: float = 20e6) -> Dict:
        num_samples = int(sample_rate * 0.01)
        return {
            "waveform": "noise",
            "samples": num_samples,
            "bandwidth_hz": bandwidth_hz,
            "sample_rate_sps": sample_rate,
            "power_spectral_density_dbm_hz": round(-174 + 10 * math.log10(bandwidth_hz), 1),
            "is_simulation": True,
        }

    def generate_chirp_waveform(self, f_start: float, f_end: float, duration_s: float) -> Dict:
        chirp_rate = (f_end - f_start) / duration_s
        return {
            "waveform":       "chirp",
            "f_start_mhz":    f_start,
            "f_end_mhz":      f_end,
            "duration_s":     duration_s,
            "chirp_rate_mhz_s": round(chirp_rate / 1e6, 3),
            "is_simulation":  True,
        }
