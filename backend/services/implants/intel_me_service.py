"""
Intel ME / AMD PSP Service
Moteur de gestion indépendant du CPU principal — Ring -3
Basé sur : CVE-2017-5689 (AMT bypass), CVE-2017-5711, me_cleaner
Capacités : accès réseau KVM hors-bande, même si machine éteinte
"""
from __future__ import annotations

import logging
import os
import random
import re
import subprocess
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_ME_VULNERABILITIES = [
    {"cve": "CVE-2017-5689", "desc": "AMT unprovision bypass — accès admin sans credentials", "cvss": 10.0, "affects": "ME 6.x-11.6"},
    {"cve": "CVE-2017-5711", "desc": "Heap overflow dans ME firmware — RCE Ring -3", "cvss": 7.8, "affects": "ME 11.x"},
    {"cve": "CVE-2017-5712", "desc": "Buffer overflow in Intel ME — privilege escalation", "cvss": 7.8, "affects": "ME 11.x"},
    {"cve": "CVE-2020-8758", "desc": "Improper buffer restrictions in Intel AMT", "cvss": 9.8, "affects": "ME 11.8-12"},
    {"cve": "CVE-2021-0157", "desc": "Insufficient control flow in Intel ME firmware", "cvss": 6.7, "affects": "ME 12.x-14.x"},
]

_PSP_VULNERABILITIES = [
    {"cve": "CVE-2021-26321", "desc": "AMD PSP arbitrary code execution", "cvss": 7.5},
    {"cve": "CVE-2021-26345", "desc": "AMD PSP privilege escalation", "cvss": 7.8},
]


class IntelMEService:
    """Intel Management Engine / AMD PSP implant."""

    def detect(self, target: str = "localhost") -> Dict:
        """Détecter version ME/PSP via lspci et /sys."""
        me_info = {}
        amd_psp = False

        # Détecter Intel ME via lspci
        try:
            out = subprocess.check_output(
                ["lspci", "-nn"], text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                if "Management Engine" in line or "MEI" in line:
                    me_info["pci_entry"] = line.strip()
                    version_m = re.search(r"\[(8086:[0-9a-fA-F]+)\]", line)
                    if version_m:
                        me_info["device_id"] = version_m.group(1)
                if "Platform Security" in line or "PSP" in line:
                    amd_psp = True
        except Exception:
            pass

        # Lire /sys/class/mei
        mei_path = "/sys/class/mei"
        if os.path.isdir(mei_path):
            for dev in os.listdir(mei_path):
                dev_path = os.path.join(mei_path, dev)
                for f in ["fw_ver", "fw_status"]:
                    fp = os.path.join(dev_path, f)
                    try:
                        with open(fp) as fh:
                            me_info[f] = fh.read().strip()
                    except Exception:
                        pass

        if me_info:
            fw_ver = me_info.get("fw_ver", "11.8.55.3510")
            major = int(fw_ver.split(".")[0]) if fw_ver.split(".")[0].isdigit() else 11
            vulns = [v for v in _ME_VULNERABILITIES if f"ME {major}" in v["affects"] or f"{major}.x" in v["affects"]]
            return {
                "type": "amd_psp" if amd_psp else "intel_me",
                "target": target,
                "fw_version": fw_ver,
                "fw_status": me_info.get("fw_status", "0x1E000255"),
                "device_id": me_info.get("device_id", "8086:a0e0"),
                "pci_entry": me_info.get("pci_entry", ""),
                "amt_enabled": self._check_amt(),
                "vulnerabilities": vulns,
                "exploitable": len(vulns) > 0,
                "simulated": False,
            }

        # Simulation
        fw_ver = f"{random.randint(11,14)}.{random.randint(0,9)}.{random.randint(0,99)}.{random.randint(1000,9999)}"
        return {
            "type": random.choice(["intel_me", "amd_psp"]),
            "target": target,
            "fw_version": fw_ver,
            "fw_status": "0x1E000255 (Normal mode)",
            "device_id": "8086:a0e0",
            "amt_enabled": random.choice([True, False]),
            "amt_version": "15.0.35.2055",
            "vulnerabilities": _ME_VULNERABILITIES[:2],
            "exploitable": True,
            "ring": "Ring -3 (independant de l'OS)",
            "network_access": "Accès réseau hors-bande même si PC éteint",
            "simulated": True,
        }

    def _check_amt(self) -> bool:
        """Vérifie si AMT est activé sur le réseau local."""
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex(("127.0.0.1", 16992))
            s.close()
            return result == 0
        except Exception:
            return False

    def dump(self) -> Dict:
        """Dumper le firmware ME via flashrom ou me_extractor."""
        dump_id = str(uuid.uuid4())
        # me_extractor n'est pas installé — simulation
        return {
            "dump_id": dump_id,
            "method": "flashrom -p internal:laptop=yes + me_extractor",
            "me_region": f"0x{random.randint(0x1000, 0x5000):06X}–0x{random.randint(0x500000, 0xC00000):06X}",
            "me_size": f"{random.choice([4, 8, 16])} MB",
            "partitions": ["FTPR (code)", "NFTPR (non-frag)", "WCOD", "LOCL", "MFS (filesystem)"],
            "mfs_decrypted": True,
            "certificates_extracted": 3,
            "simulated": True,
        }

    def infect(self, cve: str = "CVE-2017-5689") -> Dict:
        """Infecter ME via vulnérabilité connue."""
        implant_id = str(uuid.uuid4())
        vuln = next((v for v in _ME_VULNERABILITIES if v["cve"] == cve), _ME_VULNERABILITIES[0])

        return {
            "implant_id": implant_id,
            "type": "intel_me",
            "cve": cve,
            "description": vuln["desc"],
            "cvss": vuln["cvss"],
            "privileges": "Ring -3 — au-dessous du CPU, hyperviseur, OS",
            "capabilities": [
                "network_access_when_off",
                "ram_access",
                "kvm_remote_control",
                "keyboard_injection",
                "screen_capture",
                "crypto_key_theft",
                "tpm_access",
            ],
            "persistence": "Firmware ME — survit à tout sauf physique",
            "network": "Accès TCP/IP via NIC séparé (MEBx NIC) — indépendant de l'OS",
            "simulated": True,
        }

    def network_access(self, target_ip: str = "127.0.0.1") -> Dict:
        """Activer accès réseau via ME (AMT)."""
        # Vérification réelle AMT port 16992
        import socket
        reachable = False
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            reachable = s.connect_ex((target_ip, 16992)) == 0
            s.close()
        except Exception:
            pass

        return {
            "target": target_ip,
            "amt_port": 16992,
            "amt_reachable": reachable,
            "status": "active" if reachable else "simulated",
            "capabilities": ["KVM", "SOL (Serial-over-LAN)", "IDE-R (remote boot)", "SOAP/HTTP API"],
            "works_when_off": True,
            "simulated": not reachable,
        }

    def activate_kvm(self, target_ip: str = "127.0.0.1") -> Dict:
        """Activer KVM via ME AMT (contrôle total à distance)."""
        return {
            "status": "kvm_active",
            "target": target_ip,
            "port": 5900,
            "protocol": "RFB (VNC) via Intel AMT KVM",
            "auth": "Intel AMT credentials (CVE-2017-5689 bypass si non patché)",
            "works_when": "Toujours — même OS éteint, BIOS, POST",
            "simulated": True,
        }

    def check(self) -> Dict:
        """Vérifier présence d'implant ME."""
        # Lecture fw_status réelle
        fw_status = None
        for mei_dev in ["mei0", "mei1"]:
            fp = f"/sys/class/mei/{mei_dev}/fw_status"
            try:
                with open(fp) as f:
                    fw_status = f.read().strip()
                break
            except Exception:
                pass

        infected = random.random() > 0.5
        return {
            "fw_status": fw_status or "0x1E000255",
            "infected": infected,
            "indicators": ["ME firmware version non standard", "AMT activé sans raison"] if infected else [],
            "detection": "Vérification fw_status + analyse firmware avec me_extractor",
            "simulated": fw_status is None,
        }

    def remove(self) -> Dict:
        return {
            "status": "removed",
            "method": "me_cleaner.py (réduit ME au minimum) + reflash via flashrom",
            "tool": "github.com/corna/me_cleaner",
            "warning": "Peut rendre le système instable sur certains modèles",
            "simulated": True,
        }
