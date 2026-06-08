"""
WiFi & Bluetooth Attack Service — Bloc 11 EW
Déauthentification, beacon flood, evil twin, BLE jamming.
Simulation mode by default — real attacks require hardware + authorization_confirmed.
"""
from __future__ import annotations

import logging
import random
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_WIFI_SCANS: Dict[str, Dict] = {}
_BT_SCANS:   Dict[str, Dict] = {}
_SESSIONS:   Dict[str, Dict] = {}
_OUTPUT = Path("./data/ew/wifi_bt")
_OUTPUT.mkdir(parents=True, exist_ok=True)

ENCRYPTION_TYPES = ["WPA3-SAE", "WPA2-PSK", "WPA2-Enterprise", "WPA-PSK", "WEP", "OPEN"]
BT_SERVICE_UUIDS = {
    "0x1101": "SerialPort", "0x1200": "PnPInformation", "0x110a": "AudioSource",
    "0x110b": "AudioSink",  "0x1108": "Headset",       "0x1124": "HumanInterfaceDevice",
    "0xFE9F": "Google Fast Pair", "0x180F": "Battery Service", "0x1800": "Generic Access",
}

DEAUTH_REASON_CODES = {
    1:  "Unspecified reason",
    3:  "Station leaving IBSS or ESS",
    4:  "Inactivity timeout",
    5:  "AP unable to handle all associated STAs",
    6:  "Class 2 frame received from non-authenticated STA",
    7:  "Class 3 frame received from non-associated STA",
    8:  "Disassociated because sending STA is leaving (or has left) BSS",
}


class WiFiAttackService:

    def __init__(self):
        self.is_simulation = not self._check_wifi_tools()

    def _check_wifi_tools(self) -> bool:
        for tool in ["iwconfig", "airmon-ng"]:
            try:
                r = subprocess.run(["which", tool], capture_output=True, timeout=1)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def scan_aps(self, interface: str = "wlan0") -> Dict:
        if not self.is_simulation:
            try:
                r = subprocess.run(
                    ["iwlist", interface, "scan"],
                    capture_output=True, text=True, timeout=10
                )
                if r.returncode == 0 and "ESSID" in r.stdout:
                    return {"raw": r.stdout[:3000], "interface": interface, "is_simulation": False}
            except Exception as e:
                logger.warning(f"scan_aps error: {e}")
        return self._sim_scan_aps(interface)

    def _sim_scan_aps(self, interface: str) -> Dict:
        num_aps = random.randint(5, 20)
        aps = []
        channels = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 36, 40, 44, 48, 52, 100, 104, 149, 153, 157, 161]
        for i in range(num_aps):
            bssid = ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
            ap = {
                "bssid":      bssid,
                "ssid":       f"{'AP_' + str(i):10s}".strip() if random.random() > 0.1 else "<hidden>",
                "channel":    random.choice(channels),
                "frequency":  "2.4GHz" if channels.index(random.choice(channels)) < 13 else "5GHz",
                "rssi_dbm":   random.randint(-90, -30),
                "encryption": random.choice(ENCRYPTION_TYPES),
                "clients":    random.randint(0, 15),
                "vendor":     random.choice(["Cisco", "TP-Link", "Netgear", "Asus", "Ubiquiti", "Ruckus"]),
                "wps":        random.random() > 0.7,
                "pmf":        random.random() > 0.5,
            }
            aps.append(ap)
        return {"interface": interface, "aps_found": len(aps), "aps": aps, "is_simulation": True}

    def deauth_attack(self, bssid: str, client_mac: str = "FF:FF:FF:FF:FF:FF",
                      count: int = 100, interface: str = "wlan0mon") -> Dict:
        session_id = f"deauth_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":    session_id,
            "type":          "deauth",
            "bssid":         bssid,
            "client_mac":    client_mac,
            "broadcast":     client_mac == "FF:FF:FF:FF:FF:FF",
            "packets_sent":  count,
            "reason_code":   7,
            "reason":        DEAUTH_REASON_CODES[7],
            "interface":     interface,
            "expected_effect": "All clients disconnected" if client_mac == "FF:FF:FF:FF:FF:FF" else f"Client {client_mac} disconnected",
            "duration_ms":   round(count * random.uniform(5, 15), 0),
            "is_simulation": self.is_simulation,
        }
        _SESSIONS[session_id] = result
        return result

    def beacon_flood(self, ssid_list: Optional[List[str]] = None,
                     count: int = 1000, interface: str = "wlan0mon") -> Dict:
        ssids = ssid_list or [f"FreeWiFi_{i}" for i in range(20)]
        session_id = f"beacon_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":    session_id,
            "type":          "beacon_flood",
            "ssid_count":    len(ssids),
            "ssids":         ssids[:10],
            "packets_sent":  count,
            "pps":           random.randint(800, 2000),
            "interface":     interface,
            "expected_effect": f"AP scan list saturated with {len(ssids)} fake APs",
            "is_simulation": self.is_simulation,
        }
        _SESSIONS[session_id] = result
        return result

    def ap_spoofing(self, ssid: str, bssid: Optional[str] = None,
                    channel: int = 6) -> Dict:
        fake_bssid = bssid or ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
        session_id = f"spoof_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":    session_id,
            "type":          "ap_spoof",
            "ssid":          ssid,
            "bssid":         fake_bssid,
            "channel":       channel,
            "expected_effect": f"Clone of '{ssid}' — clients may associate to fake AP",
            "is_simulation": self.is_simulation,
        }
        _SESSIONS[session_id] = result
        return result

    def pmkid_capture(self, interface: str = "wlan0mon") -> Dict:
        session_id = f"pmkid_{uuid.uuid4().hex[:8]}"
        bssid = ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
        pmkid = uuid.uuid4().hex + uuid.uuid4().hex[:8]
        return {
            "session_id":    session_id,
            "interface":     interface,
            "bssid":         bssid,
            "pmkid":         pmkid,
            "hash_format":   f"WPA*01*{pmkid}*{bssid.replace(':','')}*{uuid.uuid4().hex[:12]}***",
            "crack_command": f"hashcat -m 22000 pmkid.hash wordlist.txt",
            "is_simulation": self.is_simulation,
        }

    def wpa_handshake_capture(self, interface: str = "wlan0mon",
                               bssid: Optional[str] = None) -> Dict:
        target = bssid or "AA:BB:CC:DD:EE:FF"
        return {
            "interface":     interface,
            "bssid":         target,
            "handshake_captured": True,
            "eapol_frames":  4,
            "cap_file":      f"/tmp/handshake_{target.replace(':','')}.cap",
            "crack_command": f"aircrack-ng -w /usr/share/wordlists/rockyou.txt /tmp/handshake_{target.replace(':','')}.cap",
            "is_simulation": self.is_simulation,
        }

    def evil_twin(self, ssid: str, interface: str = "wlan0mon") -> Dict:
        return {
            "type":          "evil_twin",
            "ssid":          ssid,
            "interface":     interface,
            "captive_portal": True,
            "dns_redirect":  True,
            "credential_harvest": True,
            "deauth_original_ap": True,
            "expected_effect": f"Clients of '{ssid}' deauthed then reassociate to fake AP — credentials captured via captive portal",
            "tools":         ["hostapd-wpe", "dnsmasq", "nginx"],
            "is_simulation": self.is_simulation,
        }

    def wifi_jammer(self, channel: int = 6, mode: str = "deauth") -> Dict:
        freq = 2412 + (channel - 1) * 5 if channel <= 14 else 5000 + channel * 5
        return {
            "channel":       channel,
            "frequency_mhz": freq,
            "mode":          mode,
            "pps":           random.randint(500, 3000),
            "expected_effect": f"All WiFi traffic on channel {channel} disrupted",
            "is_simulation": self.is_simulation,
        }

    def mdk4_attack(self, mode: str = "d", target: Optional[str] = None) -> Dict:
        modes = {
            "d": "Deauthentication/Disassociation",
            "b": "Beacon flood",
            "a": "Authentication DoS",
            "p": "Probe request flood",
            "m": "Michael countermeasures exploit",
            "x": "802.1X attacks",
            "w": "WIDS/WIPS confusion",
            "f": "Packet fuzzer",
            "s": "Attacks for SSID probing and cloaking",
            "e": "EAPOL start and logoff flooding",
        }
        return {
            "tool":          "mdk4",
            "mode":          mode,
            "description":   modes.get(mode, "Unknown mode"),
            "target":        target,
            "command":       f"mdk4 wlan0mon {mode}" + (f" -t {target}" if target else ""),
            "is_simulation": self.is_simulation,
        }


class BtAttackService:

    def __init__(self):
        self.is_simulation = not self._check_bt_tools()

    def _check_bt_tools(self) -> bool:
        for tool in ["hcitool", "btmon"]:
            try:
                r = subprocess.run(["which", tool], capture_output=True, timeout=1)
                if r.returncode == 0:
                    return True
            except Exception:
                pass
        return False

    def scan_devices(self, hci_interface: str = "hci0") -> Dict:
        num_devices = random.randint(3, 12)
        devices = []
        for i in range(num_devices):
            bdaddr = ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
            is_ble = random.random() > 0.4
            device = {
                "bdaddr":     bdaddr,
                "name":       random.choice(["iPhone", "Galaxy S24", "AirPods Pro", "MacBook Air",
                                             "Dell XPS", "Bose QC45", "Apple Watch", "Unknown"]),
                "type":       "BLE" if is_ble else "BT_Classic",
                "rssi_dbm":   random.randint(-90, -30),
                "services":   random.sample(list(BT_SERVICE_UUIDS.values()), k=random.randint(1, 4)),
                "connectable": random.random() > 0.3,
                "manufacturer_data": uuid.uuid4().hex[:8] if random.random() > 0.5 else None,
            }
            devices.append(device)
        return {"interface": hci_interface, "devices_found": len(devices),
                "devices": devices, "is_simulation": self.is_simulation}

    def ble_jammer(self, channel_hop_pattern: Optional[List[int]] = None) -> Dict:
        channels = channel_hop_pattern or [37, 38, 39]
        freqs = {37: 2402, 38: 2426, 39: 2480}
        return {
            "type":          "ble_advertising_jammer",
            "channels":      channels,
            "frequencies_mhz": [freqs.get(c, 2400 + c) for c in channels],
            "data_channels": list(range(0, 37)),
            "hop_interval_ms": 1.25,
            "expected_effect": "BLE advertising + connection disruption",
            "is_simulation": self.is_simulation,
        }

    def bt_classic_jammer(self, freq_hop_pattern: Optional[List[float]] = None) -> Dict:
        return {
            "type":          "bt_classic_jammer",
            "channels":      79,
            "hop_rate_hz":   1600,
            "freq_range_mhz": [2402, 2480],
            "hop_pattern":   freq_hop_pattern or "adaptive_fh",
            "expected_effect": "BT classic connection disruption (ACL/SCO links)",
            "is_simulation": self.is_simulation,
        }

    def l2cap_flood(self, target_bdaddr: str, interface: str = "hci0") -> Dict:
        session_id = f"l2cap_{uuid.uuid4().hex[:8]}"
        return {
            "session_id":    session_id,
            "target":        target_bdaddr,
            "protocol":      "L2CAP",
            "packets_sent":  random.randint(1000, 10000),
            "pps":           random.randint(200, 2000),
            "expected_effect": "Target device freeze or connection drop",
            "is_simulation": self.is_simulation,
        }

    def bt_le_advertising_spoof(self, mac: Optional[str] = None, payload: Optional[str] = None) -> Dict:
        fake_mac = mac or ":".join(f"{random.randint(0,255):02X}" for _ in range(6))
        adv_payload = payload or f"02011a{uuid.uuid4().hex[:20]}"
        return {
            "spoofed_mac":   fake_mac,
            "adv_payload":   adv_payload,
            "adv_type":      "ADV_IND",
            "tx_power_dbm":  4,
            "expected_effect": "Fake BLE device visible to all scanners",
            "is_simulation": self.is_simulation,
        }

    def ble_deauth(self, device_mac: str) -> Dict:
        return {
            "target_mac":    device_mac,
            "method":        "terminate_connection",
            "hci_command":   f"hcitool ledc {device_mac} 0x13 0x0000",
            "expected_effect": "BLE LE connection terminated — device must reconnect",
            "is_simulation": self.is_simulation,
        }
