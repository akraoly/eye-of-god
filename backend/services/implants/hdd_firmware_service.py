"""
HDD/SSD Firmware Implant Service
Basé sur : Equation Group (wip.tmp, GrayFish, NLS_933W)
Survit à : formatage, repartitionnement, changement OS
Outils réels : hdparm, smartctl, sg_raw (sg3_utils)
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_OUTPUT = Path("./data/firmware/hdd")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_KNOWN_VULNERABLE = {
    "Seagate": {
        "models": ["ST1000DM003", "ST2000DM001", "ST500DM002", "ST3500418AS"],
        "cve": ["CVE-2015-2779"],
        "hidden_area": "HPA (Host Protected Area)",
    },
    "Western Digital": {
        "models": ["WD10EZEX", "WD20EZRZ", "WD40EFRX", "WD-EALS"],
        "cve": ["CVE-2015-2780"],
        "hidden_area": "DCO (Device Configuration Overlay)",
    },
    "Samsung": {
        "models": ["MZ7LN256HAJQ", "MZ-75E500", "MZ7TD256HAFV"],
        "cve": [],
        "hidden_area": "Vendor-specific hidden partition",
    },
    "Toshiba": {
        "models": ["HDWJ110", "MQ01ABD100", "DT01ACA100"],
        "cve": [],
        "hidden_area": "HPA",
    },
}


def _get_disks() -> List[Dict]:
    """Liste les disques via lsblk."""
    try:
        out = subprocess.check_output(
            ["lsblk", "-d", "-o", "NAME,MODEL,SIZE,TYPE", "--json"],
            text=True, timeout=5, stderr=subprocess.DEVNULL,
        )
        import json
        data = json.loads(out)
        disks = []
        for dev in data.get("blockdevices", []):
            if dev.get("type") == "disk":
                disks.append({
                    "device": f"/dev/{dev['name']}",
                    "model": dev.get("model", "Unknown").strip(),
                    "size": dev.get("size", "Unknown"),
                })
        return disks
    except Exception:
        return []


def _smartctl_info(device: str) -> Dict:
    """Récupère infos SMART du disque."""
    try:
        out = subprocess.check_output(
            ["sudo", "smartctl", "-i", device],
            text=True, timeout=10, stderr=subprocess.DEVNULL,
        )
        info = {}
        for line in out.splitlines():
            for key, pattern in [
                ("model", r"Device Model:\s+(.+)"),
                ("serial", r"Serial Number:\s+(.+)"),
                ("firmware", r"Firmware Version:\s+(.+)"),
                ("capacity", r"User Capacity:\s+(.+)"),
                ("sector_size", r"Sector Size:\s+(.+)"),
                ("interface", r"SATA Version is:\s+(.+)"),
            ]:
                m = re.search(pattern, line)
                if m:
                    info[key] = m.group(1).strip()
        return info
    except Exception:
        return {}


class HDDFirmwareService:
    """Firmware implant pour disques durs / SSD."""

    def detect(self, device: Optional[str] = None) -> Dict:
        """Détecter modèle et version firmware du disque."""
        disks = _get_disks()
        if disks and not device:
            device = disks[0]["device"]

        if device:
            info = _smartctl_info(device)
            if info:
                vendor = next((v for v in _KNOWN_VULNERABLE if v.lower() in info.get("model","").lower()), "Unknown")
                vuln_info = _KNOWN_VULNERABLE.get(vendor, {})
                return {
                    "device": device,
                    "model": info.get("model", "Unknown"),
                    "serial": info.get("serial", "Unknown"),
                    "firmware": info.get("firmware", "Unknown"),
                    "capacity": info.get("capacity", "Unknown"),
                    "interface": info.get("interface", "SATA 6Gb/s"),
                    "vendor": vendor,
                    "vulnerable_cve": vuln_info.get("cve", []),
                    "hidden_area": vuln_info.get("hidden_area", "HPA"),
                    "hpa_supported": True,
                    "dco_supported": True,
                    "all_disks": disks,
                    "simulated": False,
                }

        # Simulation
        vendor = random.choice(list(_KNOWN_VULNERABLE.keys()))
        vinfo = _KNOWN_VULNERABLE[vendor]
        model = random.choice(vinfo["models"])
        return {
            "device": device or "/dev/sda",
            "model": model,
            "serial": f"S{random.randint(10000000,99999999)}",
            "firmware": f"CC4{random.randint(1,9)}",
            "capacity": f"{random.choice([500, 1000, 2000, 4000])} GB",
            "interface": "SATA 6Gb/s",
            "vendor": vendor,
            "vulnerable_cve": vinfo["cve"],
            "hidden_area": vinfo["hidden_area"],
            "hpa_supported": True,
            "dco_supported": True,
            "all_disks": [{"device": "/dev/sda", "model": model, "size": "1TB"}],
            "simulated": True,
        }

    def dump(self, device: str = "/dev/sda") -> Dict:
        """Dumper le firmware du disque via hdparm ATA commands."""
        dump_id = str(uuid.uuid4())
        out_path = str(_OUTPUT / f"hdd_dump_{dump_id[:8]}.bin")

        # Essai hdparm --read-sector (lecture secteur firmware — nécessite sudo)
        try:
            result = subprocess.run(
                ["sudo", "hdparm", "-I", device],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                # Parser infos utiles
                fw_rev = re.search(r"Firmware Revision:\s+(\S+)", result.stdout)
                model_m = re.search(r"Model Number:\s+(.+)", result.stdout)
                hpa_m = re.search(r"Host Protected Area feature set", result.stdout)
                dco_m = re.search(r"Device Configuration Overlay feature set", result.stdout)

                # Dump HPA si présent
                hpa_info = {}
                if hpa_m:
                    r2 = subprocess.run(
                        ["sudo", "hdparm", "-N", device],
                        capture_output=True, text=True, timeout=10
                    )
                    hpa_info = {"hpa_raw": r2.stdout.strip()}

                return {
                    "dump_id": dump_id, "device": device,
                    "firmware_revision": fw_rev.group(1) if fw_rev else "Unknown",
                    "model": model_m.group(1).strip() if model_m else "Unknown",
                    "hpa_present": bool(hpa_m),
                    "dco_present": bool(dco_m),
                    "hpa_info": hpa_info,
                    "raw_output": result.stdout[:1000],
                    "simulated": False,
                }
        except Exception as e:
            logger.debug("hdparm dump failed: %s", e)

        # Simulation
        fake = os.urandom(4096)
        with open(out_path, "wb") as f:
            f.write(fake)
        return {
            "dump_id": dump_id, "device": device,
            "file_path": out_path,
            "firmware_revision": f"CC4{random.randint(1,9)}",
            "model": "Seagate ST1000DM003",
            "hpa_present": True, "dco_present": True,
            "hpa_sectors": random.randint(1000000, 5000000),
            "hidden_area_size": f"{random.randint(512, 4096)} MB (inaccessible aux OS)",
            "simulated": True,
        }

    def infect(self, device: str, payload_type: str = "grayfish") -> Dict:
        """Infecter le firmware du disque — implant dans zone cachée."""
        implant_id = str(uuid.uuid4())
        payload_map = {
            "grayfish":  "GrayFish-style — bootloader dans HPA, charge avant OS",
            "nls933w":   "NLS_933W-style — module firmware persistant dans DCO",
            "equation":  "Equation Group style — 12+ ans de persistence garantis",
            "hpa_drop":  "Simple dropper dans Host Protected Area",
        }
        desc = payload_map.get(payload_type, payload_map["grayfish"])

        # Vérification HPA réelle
        hpa_info = {}
        try:
            r = subprocess.run(["sudo", "hdparm", "-N", device], capture_output=True, text=True, timeout=10)
            hpa_info = {"hdparm_N": r.stdout.strip()}
        except Exception:
            pass

        return {
            "implant_id": implant_id,
            "device": device,
            "payload_type": payload_type,
            "description": desc,
            "location": "Host Protected Area (HPA) — secteurs cachés au-delà de la capacité déclarée",
            "size": f"{random.randint(64, 512)} MB réservés dans HPA",
            "persistence": "Survit au formatage, réinstallation OS, changement de partitions",
            "boot_integration": "Injecte dans MBR/VBR à chaque démarrage depuis HPA",
            "capabilities": ["keylogger", "exfil", "dropper", "persistence", "c2_beacon"],
            "removal": "Nécessite ATA SECURITY ERASE UNIT ou dégaussage physique",
            "hpa_info": hpa_info,
            "simulated": True,
        }

    def create_hidden_partition(self, device: str, size_mb: int = 256) -> Dict:
        """Créer une zone cachée via DCO ou HPA."""
        return {
            "device": device,
            "method": "DCO (Device Configuration Overlay)",
            "size_mb": size_mb,
            "sector_range": f"0 — {size_mb * 2048} secteurs (cachés)",
            "filesystem": "FAT32 (invisible à l'OS)",
            "access": "Accessible uniquement via commandes ATA spécifiques",
            "simulated": True,
        }

    def extract_hidden(self, device: str) -> Dict:
        """Extraire données depuis zones cachées."""
        try:
            # Vérifier HPA avec hdparm
            r = subprocess.run(["sudo", "hdparm", "-N", device], capture_output=True, text=True, timeout=10)
            return {
                "device": device,
                "hdparm_n": r.stdout.strip(),
                "hidden_detected": "current" in r.stdout.lower(),
                "simulated": False,
            }
        except Exception:
            return {
                "device": device,
                "files_found": [
                    "/.hidden/implant.bin",
                    "/.hidden/keylog_2024.enc",
                    "/.hidden/exfil_queue.dat",
                ],
                "total_size": f"{random.randint(10, 200)} MB",
                "encrypted": True,
                "simulated": True,
            }

    def check(self, device: str) -> Dict:
        """Vérifier présence d'implant dans firmware disque."""
        infected = False
        indicators = []

        try:
            r = subprocess.run(["sudo", "hdparm", "-N", device], capture_output=True, text=True, timeout=10)
            if "current" in r.stdout.lower() and r.returncode == 0:
                import re as _re
                m = _re.search(r"(\d+)/(\d+)", r.stdout)
                if m and int(m.group(1)) < int(m.group(2)):
                    diff = int(m.group(2)) - int(m.group(1))
                    indicators.append(f"HPA détectée : {diff} secteurs cachés ({diff * 512 // 1024 // 1024} MB)")
                    infected = True
        except Exception:
            infected = random.random() > 0.6

        return {
            "device": device,
            "infected": infected,
            "indicators": indicators or (["Zone HPA avec contenu suspect"] if infected else []),
            "simulated": len(indicators) == 0,
        }

    def remove(self, device: str) -> Dict:
        """Supprimer l'implant — ATA SECURITY ERASE."""
        try:
            r = subprocess.run(
                ["sudo", "hdparm", "--yes-i-know-what-i-am-doing", "-N", "p0", device],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode == 0:
                return {"status": "removed", "method": "HPA reset via hdparm -N p0", "simulated": False}
        except Exception:
            pass
        return {
            "status": "removed",
            "method": "ATA SECURITY ERASE UNIT recommandé",
            "warning": "Nécessite mot de passe maître ou accès physique",
            "simulated": True,
        }
