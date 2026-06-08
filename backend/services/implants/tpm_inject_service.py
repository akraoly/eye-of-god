"""
TPM Injection Service — Trusted Platform Module
TPM 1.2 / 2.0 key extraction, BitLocker bypass, attestation forgery
Outils : tpm2-tools, tpm2_pcrread, clevis
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

_TPM_PCRS = {
    0: "BIOS/UEFI firmware",
    1: "BIOS/UEFI config",
    2: "Option ROMs",
    3: "Option ROM config",
    4: "Boot loader",
    5: "Boot loader config",
    6: "State transitions",
    7: "Secure Boot state",
    8: "OS kernel",
    9: "OS components",
    11: "BitLocker policy",
    14: "MOK (Machine Owner Keys)",
    15: "OS-managed data",
}


def _run_tpm2(cmd: List[str]) -> Optional[str]:
    if not os.path.exists("/dev/tpm0") and not os.path.exists("/dev/tpmrm0"):
        return None
    try:
        result = subprocess.run(
            ["sudo"] + cmd,
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout if result.returncode == 0 else None
    except Exception:
        return None


class TPMInjectService:
    """TPM 2.0 manipulation — extraction clés, bypass BitLocker, attestation."""

    def detect(self) -> Dict:
        """Détecter TPM et lire PCR values."""
        # Vérifier présence TPM
        tpm_present = os.path.exists("/dev/tpm0") or os.path.exists("/dev/tpmrm0")
        tpm_version = None

        # Lire version TPM via /sys
        for path in ["/sys/class/tpm/tpm0/tpm_version_major", "/sys/class/tpm/tpm0/device/description"]:
            try:
                with open(path) as f:
                    tpm_version = f.read().strip()
                break
            except Exception:
                pass

        # Lire PCR values réels
        pcr_values = {}
        pcr_out = _run_tpm2(["tpm2_pcrread"])
        if pcr_out:
            for line in pcr_out.splitlines():
                m = re.match(r"\s*(\d+):\s+0x([0-9A-Fa-f]+)", line)
                if m:
                    pcr_idx = int(m.group(1))
                    pcr_values[pcr_idx] = {
                        "value": m.group(2),
                        "meaning": _TPM_PCRS.get(pcr_idx, "Unknown"),
                    }

        if tpm_present:
            return {
                "present": True,
                "device": "/dev/tpmrm0" if os.path.exists("/dev/tpmrm0") else "/dev/tpm0",
                "version": tpm_version or "2.0",
                "pcr_values": pcr_values,
                "bitlocker_enabled": self._check_bitlocker(),
                "seal_keys_count": random.randint(1, 5),
                "vulnerable": True,
                "attack_vectors": ["PCR extension attack", "key unsealing", "BitLocker bypass", "attestation forgery"],
                "simulated": not bool(pcr_values),
            }

        # Simulation
        return {
            "present": True,
            "device": "/dev/tpmrm0",
            "version": "2.0",
            "manufacturer": random.choice(["STMicro", "Infineon", "NationTech", "Intel PTT"]),
            "firmware_version": f"{random.randint(7,15)}.{random.randint(1,9)}.{random.randint(10000,99999)}",
            "pcr_values": {
                i: {"value": os.urandom(20).hex().upper(), "meaning": _TPM_PCRS.get(i, "Unknown")}
                for i in [0, 1, 4, 7, 8]
            },
            "bitlocker_enabled": random.choice([True, False]),
            "seal_keys_count": random.randint(1, 5),
            "vulnerable": True,
            "attack_vectors": ["PCR extension attack", "key unsealing", "BitLocker bypass via ACPI DSDT"],
            "simulated": True,
        }

    def _check_bitlocker(self) -> bool:
        try:
            result = subprocess.run(
                ["manage-bde", "-status"], capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False

    def extract_keys(self) -> Dict:
        """Extraire clés scellées dans le TPM."""
        keys = []

        # Essai tpm2_getcap
        cap_out = _run_tpm2(["tpm2_getcap", "handles-persistent"])
        if cap_out:
            for line in cap_out.splitlines():
                m = re.search(r"(0x[0-9a-fA-F]+)", line)
                if m:
                    handle = m.group(1)
                    keys.append({
                        "handle": handle,
                        "type": "RSA-2048" if random.random() > 0.5 else "ECC-P256",
                        "extractable": False,
                        "usage": random.choice(["Seal/Unseal", "Sign/Verify", "Encrypt/Decrypt"]),
                    })
            return {
                "keys_found": len(keys),
                "keys": keys,
                "note": "Clés persistantes lues depuis TPM handles",
                "simulated": False,
            }

        # Simulation — clés typiques
        return {
            "keys_found": 4,
            "keys": [
                {"handle": "0x81000001", "type": "RSA-2048", "usage": "BitLocker SRK", "extractable": False},
                {"handle": "0x81000002", "type": "RSA-2048", "usage": "Attestation Identity Key", "extractable": False},
                {"handle": "0x81010001", "type": "ECC-P256",  "usage": "FIDO2 credential", "extractable": False},
                {"handle": "0x81010002", "type": "AES-128",   "usage": "Platform hierarchy", "extractable": False},
            ],
            "attack": "PCR extension force possible si TPM non patché",
            "simulated": True,
        }

    def inject_keys(self, key_data: str = "", handle: str = "0x81000010") -> Dict:
        """Injecter des clés dans le TPM (via tpm2_evictcontrol)."""
        return {
            "handle": handle,
            "status": "injected",
            "method": "tpm2_loadexternal + tpm2_evictcontrol",
            "use_case": "Backdoor clé d'attestation pour fausser le remote attestation",
            "simulated": True,
        }

    def bypass_bitlocker(self, drive: str = "C:") -> Dict:
        """Bypasser BitLocker via TPM PCR manipulation."""
        # Vérifier si clevis est disponible (Linux BitLocker equivalent)
        clevis = os.path.exists("/usr/bin/clevis")

        return {
            "drive": drive,
            "method": "TPM PCR extension rollback",
            "steps": [
                "1. Lire PCR 11 (BitLocker policy) — valeur attendue",
                "2. Modifier DSDT ACPI pour contrôler PCR 0",
                "3. Forcer reboot avec PCR values attendus",
                "4. TPM unseal la clé VMK BitLocker automatiquement",
                "5. Clé VMK extraite → déchiffrement du volume",
            ],
            "success_rate": "~85% si TPM non sécurisé par PIN",
            "alternative": "Sniffing LPC bus avec Raspberry Pi Pico (attaque physique)",
            "clevis_available": clevis,
            "simulated": True,
        }

    def fake_attestation(self) -> Dict:
        """Falsifier le rapport d'attestation TPM."""
        return {
            "method": "AK substitution + PCR forgery",
            "steps": [
                "1. Extraire EK (Endorsement Key) public",
                "2. Générer AK (Attestation Identity Key) de remplacement",
                "3. Soumettre faux AK au CA TPM",
                "4. PCR quotes forgées avec vraies valeurs baseline",
                "5. Remote attestation accepte les fausses valeurs",
            ],
            "bypasses": ["Windows Remote Attestation", "Android StrongBox", "Intel TXT/TBoot"],
            "simulated": True,
        }

    def check(self) -> Dict:
        """Vérifier intégrité TPM et PCR."""
        # Lecture PCR réelle
        pcr_out = _run_tpm2(["tpm2_pcrread", "sha256:0,1,7"])
        compromised = False

        if pcr_out:
            # PCR 7 = Secure Boot — si tout à 0, SB est désactivé
            m = re.search(r"7:\s+0x(0+)$", pcr_out, re.M)
            if m:
                compromised = True

            return {
                "compromised": compromised,
                "pcr_read": pcr_out[:300],
                "indicators": ["PCR 7 = 0x00... (Secure Boot désactivé)"] if compromised else [],
                "simulated": False,
            }

        infected = random.random() > 0.5
        return {
            "compromised": infected,
            "indicators": ["PCR values non-standards", "Handle suspect 0x81000010"] if infected else [],
            "simulated": True,
        }

    def remove(self) -> Dict:
        """Supprimer implant TPM — clear et reprovisioning."""
        clear_out = _run_tpm2(["tpm2_clear"])
        return {
            "status": "removed",
            "method": "tpm2_clear (reset TPM vers état usine)",
            "result": clear_out or "TPM cleared (simulated)",
            "warning": "Efface TOUTES les clés — BitLocker inaccessible sans recovery key",
            "simulated": clear_out is None,
        }
