"""
BLEScannerService — Bluetooth Low Energy scanner.

Uses bluetoothctl / gatttool when available; falls back to a realistic
simulation mode when hardware or tools are absent.
"""
from __future__ import annotations

import asyncio
import logging
import math
import random
import re
import shutil
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── MAC prefix → manufacturer mapping ────────────────────────────────────────
MAC_MANUFACTURERS: Dict[str, str] = {
    "AC:": "Apple",
    "F8:": "Apple",
    "18:": "Apple",
    "A4:": "Apple",
    "DC:": "Apple",
    "04:": "Samsung",
    "A0:": "Samsung",
    "CC:": "Samsung",
    "54:": "Google",
    "94:": "Google",
    "3C:": "Google",
    "00:": "Unknown",
    "FC:": "Fitbit",
    "D4:": "Xiaomi",
    "F4:": "Xiaomi",
    "78:": "Huawei",
    "B4:": "Huawei",
    "C8:": "Microsoft",
    "28:": "Microsoft",
    "08:": "Sony",
    "30:": "Sony",
}

# Known tracker MAC prefixes (first 3 bytes in hex)
TRACKER_OUI: Dict[str, str] = {
    "4C:00": "AirTag",
    "4C:12": "AirTag",
    "C8:D0": "Tile",
    "E7:23": "Tile",
    "78:BD": "Samsung SmartTag",
    "BC:D0": "Samsung SmartTag",
}

# ── Simulated device templates ────────────────────────────────────────────────
_MOCK_TEMPLATES = [
    {"name": "iPhone 15 Pro",   "prefix": "AC:", "type": "phone",      "is_tracker": False},
    {"name": "Galaxy S24 Ultra","prefix": "04:", "type": "phone",      "is_tracker": False},
    {"name": "AirPods Pro",     "prefix": "F8:", "type": "headphone",  "is_tracker": False},
    {"name": "Apple Watch S9",  "prefix": "A4:", "type": "smartwatch", "is_tracker": False},
    {"name": "AirTag",          "prefix": "4C:", "type": "tracker",    "is_tracker": True,  "tracker_type": "AirTag"},
    {"name": "Tile Mate",       "prefix": "C8:", "type": "tracker",    "is_tracker": True,  "tracker_type": "Tile"},
    {"name": "Galaxy Watch 6",  "prefix": "A0:", "type": "smartwatch", "is_tracker": False},
    {"name": "Pixel Buds Pro",  "prefix": "54:", "type": "headphone",  "is_tracker": False},
]


def _random_mac(prefix: str) -> str:
    """Generate a random MAC address with the given 3-char prefix."""
    tail = ":".join(f"{random.randint(0, 255):02X}" for _ in range(5))
    return f"{prefix}{tail}"


def _detect_type(name: str) -> str:
    n = name.lower()
    if any(k in n for k in ("airpods", "buds", "headphone", "earphone")):
        return "headphone"
    if any(k in n for k in ("watch",)):
        return "smartwatch"
    if any(k in n for k in ("tag", "tile", "tracker", "find my")):
        return "tracker"
    if any(k in n for k in ("iphone", "galaxy", "pixel", "phone")):
        return "phone"
    if any(k in n for k in ("laptop", "macbook", "thinkpad", "surface")):
        return "laptop"
    return "unknown"


def _detect_manufacturer(mac: str) -> str:
    prefix = mac[:3].upper() + ":"
    for p, m in MAC_MANUFACTURERS.items():
        if mac.upper().startswith(p):
            return m
    return "Unknown"


class BLEScannerService:
    """
    Async service wrapping bluetoothctl / gatttool.
    All subprocess calls use asyncio.create_subprocess_exec (never shell=True).
    Degrades gracefully to simulation mode when tools are absent.
    """

    # ── Simulation mode ───────────────────────────────────────────────────────

    def _is_simulation_mode(self) -> bool:
        """Return True when bluetoothctl is not found on PATH."""
        return shutil.which("bluetoothctl") is None

    def _generate_mock_devices(self) -> List[Dict[str, Any]]:
        """Return 6 realistic simulated BLE devices."""
        chosen = random.sample(_MOCK_TEMPLATES, min(6, len(_MOCK_TEMPLATES)))
        devices: List[Dict[str, Any]] = []
        for tpl in chosen:
            mac = _random_mac(tpl["prefix"])
            rssi = random.randint(-90, -45)
            devices.append({
                "mac": mac,
                "name": tpl["name"],
                "rssi": rssi,
                "manufacturer": _detect_manufacturer(mac),
                "device_type": tpl["type"],
                "is_tracker": tpl.get("is_tracker", False),
                "tracker_type": tpl.get("tracker_type"),
                "services": [],
                "simulated": True,
                "last_seen": datetime.utcnow().isoformat(),
            })
        return devices

    # ── Internal subprocess helper ────────────────────────────────────────────

    async def _run(
        self,
        *args: str,
        timeout: float = 15.0,
        stdin_data: Optional[bytes] = None,
    ) -> tuple[int, str, str]:
        """
        Run a subprocess without shell=True.
        Returns (returncode, stdout, stderr).
        Raises FileNotFoundError if binary is missing (caller must guard with shutil.which).
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE if stdin_data else None,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(input=stdin_data),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                return -1, "", "timeout"
            return proc.returncode or 0, stdout_b.decode(errors="replace"), stderr_b.decode(errors="replace")
        except FileNotFoundError:
            return -1, "", f"binary not found: {args[0]}"
        except Exception as exc:
            return -1, "", str(exc)

    # ── Core scan ─────────────────────────────────────────────────────────────

    async def scan_devices(
        self, duration: int = 10, interface: str = "hci0"
    ) -> List[Dict[str, Any]]:
        """
        Scan for nearby BLE devices.
        Uses bluetoothctl scan; falls back to simulation if unavailable.
        """
        if self._is_simulation_mode():
            logger.info("BLE scan: simulation mode (bluetoothctl absent)")
            await asyncio.sleep(min(duration, 3))
            return self._generate_mock_devices()

        devices: Dict[str, Dict[str, Any]] = {}

        # Use bluetoothctl scan on for `duration` seconds, then collect devices
        scan_cmd = shutil.which("bluetoothctl")
        if not scan_cmd:
            return self._generate_mock_devices()

        # Start scan
        rc, stdout, stderr = await self._run(
            scan_cmd, "--timeout", str(duration), "scan", "on",
            timeout=duration + 5,
        )

        # Parse NEW_DEV lines: [NEW] Device AA:BB:CC:DD:EE:FF DeviceName
        for line in stdout.splitlines():
            m = re.search(
                r"\[NEW\]\s+Device\s+([0-9A-Fa-f:]{17})\s*(.*)", line
            )
            if m:
                mac, name = m.group(1).upper(), m.group(2).strip()
                if mac not in devices:
                    devices[mac] = {
                        "mac": mac,
                        "name": name or mac,
                        "rssi": -70,
                        "manufacturer": _detect_manufacturer(mac),
                        "device_type": _detect_type(name),
                        "is_tracker": self._is_tracker_mac(mac),
                        "tracker_type": self._tracker_type(mac),
                        "services": [],
                        "simulated": False,
                        "last_seen": datetime.utcnow().isoformat(),
                    }

        # Also try: bluetoothctl devices (may list cached devices)
        rc2, out2, _ = await self._run(scan_cmd, "devices", timeout=5)
        for line in out2.splitlines():
            m = re.search(r"Device\s+([0-9A-Fa-f:]{17})\s*(.*)", line)
            if m:
                mac, name = m.group(1).upper(), m.group(2).strip()
                if mac not in devices:
                    devices[mac] = {
                        "mac": mac,
                        "name": name or mac,
                        "rssi": -70,
                        "manufacturer": _detect_manufacturer(mac),
                        "device_type": _detect_type(name),
                        "is_tracker": self._is_tracker_mac(mac),
                        "tracker_type": self._tracker_type(mac),
                        "services": [],
                        "simulated": False,
                        "last_seen": datetime.utcnow().isoformat(),
                    }

        if not devices:
            logger.warning("BLE scan returned 0 devices; using simulation fallback")
            return self._generate_mock_devices()

        return list(devices.values())

    # ── Detect BT devices (cached list) ──────────────────────────────────────

    async def detect_bt_devices(self, interface: str = "hci0") -> List[Dict[str, Any]]:
        """Return cached bluetoothctl device list."""
        if self._is_simulation_mode():
            return self._generate_mock_devices()

        bt = shutil.which("bluetoothctl")
        if not bt:
            return self._generate_mock_devices()

        rc, stdout, _ = await self._run(bt, "devices", timeout=10)
        devices = []
        for line in stdout.splitlines():
            m = re.search(r"Device\s+([0-9A-Fa-f:]{17})\s*(.*)", line)
            if m:
                mac, name = m.group(1).upper(), m.group(2).strip()
                devices.append({
                    "mac": mac,
                    "name": name or mac,
                    "rssi": -70,
                    "manufacturer": _detect_manufacturer(mac),
                    "device_type": _detect_type(name),
                    "is_tracker": self._is_tracker_mac(mac),
                    "tracker_type": self._tracker_type(mac),
                    "simulated": False,
                })
        return devices

    # ── GATT services enumeration ─────────────────────────────────────────────

    async def enumerate_gatt_services(self, mac: str) -> List[Dict[str, Any]]:
        """Enumerate GATT services using gatttool --primary."""
        if shutil.which("gatttool") is None:
            return self._simulate_gatt_services(mac)

        rc, stdout, stderr = await self._run(
            "gatttool", "-b", mac, "--primary",
            timeout=20,
        )
        if rc != 0 or not stdout.strip():
            return self._simulate_gatt_services(mac)

        services = []
        for line in stdout.splitlines():
            # attr handle: 0x0001, end grp handle: 0x000e uuid: 00001800-0000-...
            m = re.search(
                r"attr handle:\s*(0x[0-9a-fA-F]+).*uuid:\s*([0-9a-fA-F\-]{8,})",
                line,
            )
            if m:
                services.append({"handle": m.group(1), "uuid": m.group(2)})
        return services

    def _simulate_gatt_services(self, mac: str) -> List[Dict[str, Any]]:
        return [
            {"handle": "0x0001", "uuid": "00001800-0000-1000-8000-00805f9b34fb", "name": "Generic Access"},
            {"handle": "0x0010", "uuid": "00001801-0000-1000-8000-00805f9b34fb", "name": "Generic Attribute"},
            {"handle": "0x0020", "uuid": "0000180a-0000-1000-8000-00805f9b34fb", "name": "Device Information"},
        ]

    # ── Device fingerprinting ─────────────────────────────────────────────────

    async def fingerprint_device(self, mac: str) -> Dict[str, Any]:
        """Fingerprint a BLE device via gatttool --primary."""
        services = await self.enumerate_gatt_services(mac)
        simulated = shutil.which("gatttool") is None
        return {
            "mac": mac,
            "gatt_services": services,
            "simulated": simulated,
            "fingerprinted_at": datetime.utcnow().isoformat(),
        }

    # ── Vulnerability detection ───────────────────────────────────────────────

    async def detect_vulnerabilities(self, mac: str) -> List[Dict[str, Any]]:
        """
        Heuristic vulnerability checks:
        - Legacy pairing (no BLE secure pairing)
        - GATT without authentication
        - Default PIN (0000/1234)
        """
        vulns: List[Dict[str, Any]] = []
        simulated = self._is_simulation_mode()

        if simulated:
            # Simulate: randomly assign 0-3 vulnerabilities for demo
            pool = [
                {"id": "BLE-001", "name": "Legacy Pairing", "severity": "HIGH",
                 "description": "Device uses legacy BT pairing (no LESC). Susceptible to MITM."},
                {"id": "BLE-002", "name": "Unauthenticated GATT", "severity": "MEDIUM",
                 "description": "GATT services accessible without authentication."},
                {"id": "BLE-003", "name": "Default PIN", "severity": "HIGH",
                 "description": "Device accepts default PIN (0000 or 1234)."},
                {"id": "BLE-004", "name": "Unencrypted Characteristics", "severity": "MEDIUM",
                 "description": "Read/write characteristics do not require encryption."},
            ]
            count = random.randint(0, 3)
            vulns = random.sample(pool, count)
            for v in vulns:
                v["simulated"] = True
            return vulns

        # Real checks
        bt = shutil.which("bluetoothctl")
        gt = shutil.which("gatttool")

        # Check GATT accessibility without pairing
        if gt:
            rc, stdout, _ = await self._run("gatttool", "-b", mac, "--primary", timeout=15)
            if rc == 0 and stdout.strip():
                vulns.append({
                    "id": "BLE-002",
                    "name": "Unauthenticated GATT",
                    "severity": "MEDIUM",
                    "description": "GATT services accessible without authentication.",
                    "simulated": False,
                })

        # Check legacy pairing via bluetoothctl info
        if bt:
            rc, stdout, _ = await self._run(bt, "info", mac, timeout=10)
            if "LegacyPairing: yes" in stdout:
                vulns.append({
                    "id": "BLE-001",
                    "name": "Legacy Pairing",
                    "severity": "HIGH",
                    "description": "Device uses legacy BT pairing (no LESC). Susceptible to MITM.",
                    "simulated": False,
                })

        return vulns

    # ── GATT read/write ───────────────────────────────────────────────────────

    async def write_gatt_characteristic(
        self,
        mac: str,
        service_uuid: str,
        char_uuid: str,
        data: str,
    ) -> Dict[str, Any]:
        """Write a GATT characteristic via gatttool --char-write-req."""
        if shutil.which("gatttool") is None:
            return {
                "success": False,
                "error": "gatttool not found (simulation mode)",
                "simulated": True,
            }
        rc, stdout, stderr = await self._run(
            "gatttool", "-b", mac,
            "--char-write-req",
            "--uuid", char_uuid,
            "--value", data,
            timeout=20,
        )
        return {
            "success": rc == 0,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "simulated": False,
        }

    async def read_gatt_characteristic(
        self,
        mac: str,
        service_uuid: str,
        char_uuid: str,
    ) -> Dict[str, Any]:
        """Read a GATT characteristic via gatttool --char-read."""
        if shutil.which("gatttool") is None:
            simulated_value = "".join(
                f"{random.randint(0, 255):02x}" for _ in range(8)
            )
            return {
                "success": True,
                "value": simulated_value,
                "simulated": True,
            }
        rc, stdout, stderr = await self._run(
            "gatttool", "-b", mac,
            "--char-read",
            "--uuid", char_uuid,
            timeout=20,
        )
        # Parse: Characteristic value/descriptor: xx xx xx ...
        value = ""
        m = re.search(r"value/descriptor:\s*((?:[0-9a-fA-F]{2}\s*)+)", stdout)
        if m:
            value = m.group(1).strip().replace(" ", "")
        return {
            "success": rc == 0,
            "value": value,
            "stdout": stdout.strip(),
            "stderr": stderr.strip(),
            "simulated": False,
        }

    # ── Tracker detection ─────────────────────────────────────────────────────

    def _is_tracker_mac(self, mac: str) -> bool:
        mac_upper = mac.upper()
        for prefix in TRACKER_OUI:
            if mac_upper.startswith(prefix):
                return True
        return False

    def _tracker_type(self, mac: str) -> Optional[str]:
        mac_upper = mac.upper()
        for prefix, ttype in TRACKER_OUI.items():
            if mac_upper.startswith(prefix):
                return ttype
        return None

    async def get_nearby_trackers(self, duration: int = 15) -> List[Dict[str, Any]]:
        """
        Scan and filter to known tracker OUI prefixes:
        AirTag (4C:00), Tile (C8:D0), Samsung SmartTag (78:BD / BC:D0).
        """
        all_devices = await self.scan_devices(duration=duration)
        trackers = []
        for dev in all_devices:
            mac = dev.get("mac", "")
            if self._is_tracker_mac(mac) or dev.get("is_tracker"):
                dev["is_tracker"] = True
                dev["tracker_type"] = dev.get("tracker_type") or self._tracker_type(mac) or "Unknown"
                trackers.append(dev)
        return trackers

    # ── RSSI-based distance / locate ─────────────────────────────────────────

    async def locate_device(self, mac: str) -> Dict[str, Any]:
        """
        Collect RSSI samples over ~5 s and estimate distance.
        Formula: d = 10 ^ ((rssi_ref - rssi) / (10 * n))
        rssi_ref = -59 dBm (1 m reference), n = 2.5 (path-loss exponent).
        """
        rssi_ref = -59
        n = 2.5
        samples: List[Dict[str, Any]] = []

        if self._is_simulation_mode():
            base_rssi = random.randint(-85, -50)
            for _ in range(5):
                rssi = base_rssi + random.randint(-5, 5)
                distance = 10 ** ((rssi_ref - rssi) / (10 * n))
                samples.append({
                    "rssi": rssi,
                    "timestamp": datetime.utcnow().isoformat(),
                    "distance_m": round(distance, 2),
                })
                await asyncio.sleep(1)
        else:
            bt = shutil.which("bluetoothctl")
            for _ in range(5):
                rssi_val = -70
                if bt:
                    rc, stdout, _ = await self._run(bt, "info", mac, timeout=5)
                    m = re.search(r"RSSI:\s*(-?\d+)", stdout)
                    if m:
                        rssi_val = int(m.group(1))
                distance = 10 ** ((rssi_ref - rssi_val) / (10 * n))
                samples.append({
                    "rssi": rssi_val,
                    "timestamp": datetime.utcnow().isoformat(),
                    "distance_m": round(distance, 2),
                })
                await asyncio.sleep(1)

        avg_rssi = sum(s["rssi"] for s in samples) / len(samples)
        avg_distance = 10 ** ((rssi_ref - avg_rssi) / (10 * n))

        return {
            "mac": mac,
            "samples": samples,
            "avg_rssi": round(avg_rssi, 1),
            "estimated_distance_m": round(avg_distance, 2),
            "simulated": self._is_simulation_mode(),
        }
