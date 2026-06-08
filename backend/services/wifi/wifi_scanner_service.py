"""
WiFiScannerService — Scan, reconnaissance et monitor mode.

Utilise airmon-ng / airodump-ng / iw quand disponibles.
Fallback simulation réaliste si interface absente.
"""
from __future__ import annotations

import asyncio
import csv
import io
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── OUI vendors (extrait) ─────────────────────────────────────────────────────
OUI_MAP: Dict[str, str] = {
    "00:50:F2": "Microsoft", "00:1A:2B": "Cisco", "FC:FB:FB": "Cisco",
    "00:26:B9": "Dell",      "A4:C3:F0": "Apple", "3C:22:FB": "Apple",
    "DC:A6:32": "Raspberry", "B8:27:EB": "Raspberry",
    "00:11:22": "Netgear",   "C0:C1:C0": "Netgear",
    "18:0F:76": "TP-Link",   "50:C7:BF": "TP-Link",
    "74:DA:38": "ASUS",      "2C:FD:A1": "ASUS",
    "00:18:4D": "Netopia",   "00:1D:7E": "Linksys",
    "20:AA:4B": "Ubiquiti",  "FC:EC:DA": "Ubiquiti",
    "00:17:F2": "Apple",     "00:1E:52": "Apple",
}

# ── Templates simulation ───────────────────────────────────────────────────────
_MOCK_NETWORKS = [
    {"ssid": "Freebox-4A2F",    "enc": "WPA2", "ch": 6,  "signal": -45, "wps": True,  "vendor": "Free"},
    {"ssid": "SFR_B342",        "enc": "WPA2", "ch": 11, "signal": -58, "wps": True,  "vendor": "SFR"},
    {"ssid": "LIVEBOX-C7D1",    "enc": "WPA2", "ch": 1,  "signal": -62, "wps": True,  "vendor": "Orange"},
    {"ssid": "BBOX-9F4A",       "enc": "WPA2", "ch": 6,  "signal": -55, "wps": False, "vendor": "Bouygues"},
    {"ssid": "TP-Link_Guest",   "enc": "WPA2", "ch": 3,  "signal": -70, "wps": True,  "vendor": "TP-Link"},
    {"ssid": "NETGEAR_5G",      "enc": "WPA3", "ch": 36, "signal": -50, "wps": False, "vendor": "Netgear"},
    {"ssid": "AndroidHotspot",  "enc": "WPA2", "ch": 8,  "signal": -65, "wps": False, "vendor": "Samsung"},
    {"ssid": "",                "enc": "WPA2", "ch": 11, "signal": -75, "wps": False, "vendor": "Cisco", "hidden": True},
    {"ssid": "Corp_WiFi",       "enc": "WPA2", "ch": 1,  "signal": -48, "wps": False, "vendor": "Cisco", "auth": "MGT"},
    {"ssid": "OpenWifi",        "enc": "OPN",  "ch": 6,  "signal": -60, "wps": False, "vendor": "Ubiquiti"},
]


def _random_bssid(prefix: str = "") -> str:
    octets = [random.randint(0, 255) for _ in range(6)]
    octets[0] &= 0xFE  # unicast
    if prefix:
        parts = prefix.split(":")
        for i, p in enumerate(parts[:3]):
            octets[i] = int(p, 16)
    return ":".join(f"{b:02X}" for b in octets)


def _oui_vendor(bssid: str) -> str:
    prefix = bssid[:8].upper()
    return OUI_MAP.get(prefix, "Unknown")


class WiFiScannerService:
    """Scanner WiFi — airmon-ng + airodump-ng avec fallback simulation."""

    def __init__(self):
        self._monitor_iface: Optional[str] = None
        self._hop_task: Optional[asyncio.Task] = None
        self._current_channel = 1

    # ── Outils disponibles ────────────────────────────────────────────────────

    @staticmethod
    def _has_tool(name: str) -> bool:
        return shutil.which(name) is not None

    def _get_wifi_interfaces(self) -> List[Dict]:
        """Liste les interfaces WiFi via iw dev."""
        ifaces = []
        try:
            out = subprocess.check_output(["iw", "dev"], text=True, stderr=subprocess.DEVNULL, timeout=5)
            current = {}
            for line in out.splitlines():
                line = line.strip()
                m = re.match(r"Interface\s+(\S+)", line)
                if m:
                    if current:
                        ifaces.append(current)
                    current = {"name": m.group(1), "type": "managed", "channel": None, "addr": None}
                if current:
                    if "type" in line:
                        current["type"] = line.split()[-1]
                    t = re.search(r"channel\s+(\d+)", line)
                    if t:
                        current["channel"] = int(t.group(1))
                    a = re.search(r"addr\s+([\da-f:]+)", line)
                    if a:
                        current["addr"] = a.group(1).upper()
            if current:
                ifaces.append(current)
        except Exception as e:
            logger.debug("iw dev failed: %s", e)
        return ifaces

    def get_interfaces(self) -> List[Dict]:
        real = self._get_wifi_interfaces()
        if real:
            return real
        # Simulation
        return [
            {"name": "wlan0", "type": "managed",  "channel": 6,  "addr": "AA:BB:CC:DD:EE:01", "simulated": True},
            {"name": "wlan1", "type": "monitor",  "channel": 11, "addr": "AA:BB:CC:DD:EE:02", "simulated": True},
        ]

    # ── Monitor mode ──────────────────────────────────────────────────────────

    def start_monitor(self, interface: str) -> Dict:
        if not self._has_tool("airmon-ng"):
            self._monitor_iface = f"{interface}mon"
            return {"monitor_interface": self._monitor_iface, "simulated": True}
        try:
            subprocess.run(["sudo", "airmon-ng", "check", "kill"], capture_output=True, timeout=10)
            out = subprocess.check_output(
                ["sudo", "airmon-ng", "start", interface],
                text=True, stderr=subprocess.STDOUT, timeout=15
            )
            mon = interface + "mon"
            m = re.search(r"monitor mode vif enabled.*?on\s+\[?(\w+)\]?", out, re.I)
            if m:
                mon = m.group(1)
            self._monitor_iface = mon
            return {"monitor_interface": mon, "simulated": False}
        except Exception as e:
            self._monitor_iface = f"{interface}mon"
            return {"monitor_interface": self._monitor_iface, "simulated": True, "error": str(e)}

    def stop_monitor(self, interface: str) -> Dict:
        if not self._has_tool("airmon-ng"):
            self._monitor_iface = None
            return {"status": "stopped", "simulated": True}
        try:
            subprocess.run(["sudo", "airmon-ng", "stop", interface], capture_output=True, timeout=15)
            subprocess.run(["sudo", "systemctl", "restart", "NetworkManager"], capture_output=True, timeout=15)
            self._monitor_iface = None
            return {"status": "stopped", "simulated": False}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    # ── Channel ───────────────────────────────────────────────────────────────

    def set_channel(self, interface: str, channel: int) -> Dict:
        self._current_channel = channel
        if not self._has_tool("iw"):
            return {"channel": channel, "interface": interface, "simulated": True}
        try:
            subprocess.run(["sudo", "iw", "dev", interface, "set", "channel", str(channel)],
                           capture_output=True, timeout=5)
            return {"channel": channel, "interface": interface, "simulated": False}
        except Exception as e:
            return {"channel": channel, "simulated": True, "error": str(e)}

    # ── Scan ──────────────────────────────────────────────────────────────────

    async def scan(self, interface: str, duration: int = 30, channels: Optional[List[int]] = None) -> Dict:
        """Lance airodump-ng et parse les résultats. Fallback simulation."""
        if not self._has_tool("airodump-ng"):
            return self._simulate_scan(duration)

        scan_id = str(uuid.uuid4())
        with tempfile.TemporaryDirectory() as tmpdir:
            prefix = os.path.join(tmpdir, "scan")
            cmd = ["sudo", "airodump-ng", "--write", prefix, "--output-format", "csv", "--write-interval", "1"]
            if channels:
                cmd += ["--channel", ",".join(str(c) for c in channels)]
            cmd.append(interface)

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.sleep(min(duration, 60))
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=3)
                except asyncio.TimeoutError:
                    proc.kill()

                csv_file = prefix + "-01.csv"
                if os.path.exists(csv_file):
                    networks, clients = self._parse_airodump_csv(csv_file)
                    return {
                        "scan_id": scan_id,
                        "networks": networks,
                        "clients": clients,
                        "simulated": False,
                        "duration": duration,
                    }
            except Exception as e:
                logger.warning("airodump-ng error: %s — fallback simulation", e)

        return self._simulate_scan(duration, scan_id=scan_id)

    def _parse_airodump_csv(self, path: str) -> tuple:
        """Parse le CSV airodump-ng — retourne (networks, clients)."""
        networks: List[Dict] = []
        clients: List[Dict] = []
        section = "ap"

        with open(path, "r", errors="replace") as f:
            content = f.read()

        sections = content.split("\r\n\r\n")
        for i, section_data in enumerate(sections):
            lines = [l.strip() for l in section_data.strip().splitlines() if l.strip()]
            if not lines:
                continue
            header = lines[0].lower()
            if "bssid" in header and "essid" in header:
                # Section AP
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 14:
                        continue
                    bssid = parts[0].upper()
                    if not re.match(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", bssid):
                        continue
                    try:
                        signal = int(parts[8])
                    except Exception:
                        signal = -70
                    enc = parts[5].strip() or "OPN"
                    cipher = parts[6].strip()
                    auth = parts[7].strip()
                    ssid = parts[13].strip() if len(parts) > 13 else ""
                    try:
                        ch = int(parts[3].strip())
                    except Exception:
                        ch = 0
                    networks.append({
                        "bssid": bssid,
                        "ssid": ssid,
                        "hidden": ssid == "",
                        "channel": ch,
                        "signal": signal,
                        "encryption": enc,
                        "cipher": cipher,
                        "auth": auth,
                        "vendor": _oui_vendor(bssid),
                        "beacon_count": 0,
                        "wps_enabled": False,
                        "simulated": False,
                    })
            elif "station mac" in header:
                # Section clients
                for line in lines[1:]:
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) < 6:
                        continue
                    mac = parts[0].upper()
                    if not re.match(r"([0-9A-F]{2}:){5}[0-9A-F]{2}", mac):
                        continue
                    bssid_ap = parts[5].strip().upper() if len(parts) > 5 else None
                    try:
                        sig = int(parts[3])
                    except Exception:
                        sig = -70
                    probed = [s.strip() for s in parts[6:] if s.strip()] if len(parts) > 6 else []
                    clients.append({
                        "mac": mac,
                        "bssid": bssid_ap,
                        "signal": sig,
                        "probed_ssids": probed,
                        "vendor": _oui_vendor(mac),
                    })

        return networks, clients

    def _simulate_scan(self, duration: int = 30, scan_id: Optional[str] = None) -> Dict:
        if not scan_id:
            scan_id = str(uuid.uuid4())
        n = random.randint(4, len(_MOCK_NETWORKS))
        selected = random.sample(_MOCK_NETWORKS, n)
        networks = []
        for tpl in selected:
            bssid = _random_bssid()
            networks.append({
                "bssid": bssid,
                "ssid": tpl.get("ssid", ""),
                "hidden": tpl.get("hidden", False),
                "channel": tpl.get("ch", 6),
                "frequency": 2.412 + (tpl.get("ch", 6) - 1) * 0.005,
                "signal": tpl.get("signal", -70) + random.randint(-5, 5),
                "quality": max(0, min(100, 100 + tpl.get("signal", -70) + random.randint(-5, 5))),
                "encryption": tpl.get("enc", "WPA2"),
                "cipher": "CCMP" if tpl.get("enc", "WPA2") in ("WPA2", "WPA3") else "TKIP",
                "auth": tpl.get("auth", "PSK"),
                "wps_enabled": tpl.get("wps", False),
                "wps_locked": False,
                "vendor": tpl.get("vendor", "Unknown"),
                "capabilities": [],
                "beacon_count": random.randint(10, 500),
                "data_count": random.randint(0, 1000),
                "clients": [],
                "simulated": True,
            })
        # Quelques clients simulés
        clients = []
        for net in networks[:3]:
            n_clients = random.randint(0, 3)
            for _ in range(n_clients):
                client_mac = _random_bssid()
                clients.append({
                    "mac": client_mac,
                    "bssid": net["bssid"],
                    "ssid": net["ssid"],
                    "signal": random.randint(-80, -40),
                    "probed_ssids": [net["ssid"]],
                    "vendor": random.choice(list(OUI_MAP.values())),
                    "simulated": True,
                })
                net["clients"].append(client_mac)

        return {
            "scan_id": scan_id,
            "networks": networks,
            "clients": clients,
            "simulated": True,
            "duration": duration,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── WPS Detection ─────────────────────────────────────────────────────────

    def detect_wps(self, interface: str, bssid: str) -> Dict:
        """Détecte WPS via wash si disponible."""
        if not shutil.which("wash"):
            return {"bssid": bssid, "wps": True, "wps_version": "2.0", "locked": False, "simulated": True}
        try:
            out = subprocess.check_output(
                ["sudo", "wash", "-i", interface, "-s", "-o"],
                text=True, stderr=subprocess.DEVNULL, timeout=15
            )
            for line in out.splitlines():
                if bssid.upper() in line.upper():
                    parts = line.split()
                    locked = "yes" in line.lower() or (len(parts) > 5 and parts[4].lower() == "yes")
                    return {"bssid": bssid, "wps": True, "wps_version": parts[2] if len(parts) > 2 else "2.0",
                            "locked": locked, "simulated": False}
            return {"bssid": bssid, "wps": False, "simulated": False}
        except Exception as e:
            return {"bssid": bssid, "wps": True, "wps_version": "2.0", "locked": False, "simulated": True}

    # ── Fingerprinting AP ─────────────────────────────────────────────────────

    def fingerprint_ap(self, bssid: str, ssid: str, vendor: str) -> Dict:
        """Tente de déterminer le modèle de l'AP."""
        model = "Unknown"
        firmware = "Unknown"
        ssid_lower = ssid.lower()

        if "freebox" in ssid_lower:
            model = "Freebox Delta/Pop"; firmware = "Freebox OS 4.x"
        elif "sfr" in ssid_lower:
            model = "SFR Box 8"; firmware = "SFR OS 3.x"
        elif "livebox" in ssid_lower:
            model = "Livebox 6"; firmware = "Orange OS 5.x"
        elif "bbox" in ssid_lower:
            model = "Bbox Must 3"; firmware = "Bouygues OS 2.x"
        elif "tp-link" in ssid_lower:
            model = "TP-Link Archer AX55"; firmware = "1.2.3"
        elif "netgear" in ssid_lower:
            model = "Netgear Nighthawk AX12"; firmware = "V12.0.4.116"
        elif vendor == "Cisco":
            model = "Cisco Aironet 1852"; firmware = "8.10.151.0"
        elif vendor == "Ubiquiti":
            model = "UniFi AP AC Pro"; firmware = "6.5.54"
        elif vendor == "ASUS":
            model = "ASUS RT-AX88U"; firmware = "3.0.0.4.386"

        return {
            "bssid": bssid,
            "ssid": ssid,
            "vendor": vendor,
            "model": model,
            "firmware": firmware,
            "default_creds": self._get_default_creds(vendor, model),
        }

    def _get_default_creds(self, vendor: str, model: str) -> List[Dict]:
        defaults = {
            "Netgear": [{"user": "admin", "pass": "password"}, {"user": "admin", "pass": "admin"}],
            "TP-Link": [{"user": "admin", "pass": "admin"}, {"user": "admin", "pass": ""}],
            "ASUS":    [{"user": "admin", "pass": "admin"}],
            "Linksys": [{"user": "admin", "pass": ""}, {"user": "", "pass": "admin"}],
            "D-Link":  [{"user": "admin", "pass": ""}, {"user": "admin", "pass": "admin"}],
            "Cisco":   [{"user": "cisco", "pass": "cisco"}, {"user": "admin", "pass": "cisco"}],
        }
        return defaults.get(vendor, [{"user": "admin", "pass": "admin"}])
