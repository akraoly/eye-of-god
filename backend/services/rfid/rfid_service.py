"""
RFIDService — Communication avec Proxmark3 via subprocess.

Modes:
  - PM3 réel   : `pm3 --script /tmp/pm3_cmd.txt`
  - Simulation : données réalistes générées si PM3 absent
"""
from __future__ import annotations

import asyncio
import glob
import logging
import os
import random
import shutil
import string
import tempfile
import time
import uuid
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constantes simulation ─────────────────────────────────────────────────────

_SIM_UID        = "04:A3:F2:11:22:33"
_SIM_TYPE       = "hf_mifare_classic"
_SIM_KEYS       = ["FFFFFFFFFFFF", "A0A1A2A3A4A5"]
_SIM_SITE_CODE  = "14"
_SIM_BADGE_NUM  = "2341"

_DEFAULT_KEYS = [
    "FFFFFFFFFFFF",
    "A0A1A2A3A4A5",
    "D3F7D3F7D3F7",
    "000000000000",
    "B0B1B2B3B4B5",
]

# ── RFIDService ───────────────────────────────────────────────────────────────

class RFIDService:
    """
    Wraps Proxmark3 CLI (pm3 / proxmark3).
    Falls back to simulation mode when no device is found.
    """

    def __init__(self):
        self._pm3_bin: Optional[str]  = None
        self._port: Optional[str]     = None
        self._simulation_mode: bool   = True
        self._initialized: bool       = False

    # ── Initialisation ─────────────────────────────────────────────────────────

    async def _ensure_init(self) -> None:
        if not self._initialized:
            await self.detect_proxmark()

    # ── Détection ──────────────────────────────────────────────────────────────

    async def detect_proxmark(self) -> dict:
        """
        Cherche l'exécutable pm3 / proxmark3 et un port série.
        Retourne {connected, port, firmware, serial, simulation_mode}.
        """
        self._initialized = True

        # Cherche l'exécutable
        bin_name = shutil.which("pm3") or shutil.which("proxmark3")
        self._pm3_bin = bin_name

        # Cherche un port série
        port = None
        for pattern in ("/dev/ttyACM*", "/dev/ttyUSB*"):
            matches = glob.glob(pattern)
            if matches:
                port = matches[0]
                break
        self._port = port

        connected = bool(bin_name and port)
        self._simulation_mode = not connected

        firmware = None
        serial   = None

        if connected:
            try:
                result = await self._run_pm3_command("hw version", timeout=5)
                output = result.get("output", "")
                for line in output.splitlines():
                    if "firmware" in line.lower():
                        firmware = line.strip()
                    if "serial" in line.lower():
                        serial = line.strip()
            except Exception as exc:
                logger.warning("Impossible de récupérer la version PM3: %s", exc)
                self._simulation_mode = True
                connected = False

        return {
            "connected":       connected,
            "port":            port,
            "firmware":        firmware or ("simulation" if self._simulation_mode else None),
            "serial":          serial,
            "simulation_mode": self._simulation_mode,
            "pm3_bin":         bin_name,
        }

    # ── Exécution commande PM3 ─────────────────────────────────────────────────

    async def _run_pm3_command(self, command: str, timeout: int = 10) -> dict:
        """
        Écrit la commande dans /tmp/pm3_cmd.txt, exécute pm3 --script, retourne la sortie.
        En mode simulation retourne immédiatement des données factices.
        """
        if self._simulation_mode:
            return {"success": True, "output": f"[SIM] {command}", "simulated": True}

        cmd_file = "/tmp/pm3_cmd.txt"
        try:
            with open(cmd_file, "w") as fh:
                fh.write(command + "\n")
                fh.write("quit\n")
        except OSError as exc:
            logger.error("Écriture fichier commande PM3: %s", exc)
            return {"success": False, "error": str(exc)}

        bin_path = self._pm3_bin or "pm3"
        args = [bin_path, "--script", cmd_file]
        if self._port:
            args = [bin_path, self._port, "--script", cmd_file]

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                proc.kill()
                return {"success": False, "error": "timeout"}

            output = stdout.decode(errors="replace")
            err    = stderr.decode(errors="replace")
            return {
                "success":   proc.returncode == 0,
                "output":    output,
                "stderr":    err,
                "returncode": proc.returncode,
            }
        except FileNotFoundError:
            # pm3 introuvable en cours d'exécution → basculer en simulation
            self._simulation_mode = True
            return {"success": True, "output": f"[SIM] {command}", "simulated": True}
        except Exception as exc:
            logger.error("Erreur exécution PM3: %s", exc)
            return {"success": False, "error": str(exc)}

    # ── Scan ──────────────────────────────────────────────────────────────────

    async def scan_card(self, timeout: int = 10) -> dict:
        """
        Recherche une carte HF ou LF.
        Retourne {uid, type, protocol, atqa, sak, simulated}.
        """
        await self._ensure_init()

        if self._simulation_mode:
            return {
                "success":   True,
                "uid":       _SIM_UID,
                "type":      _SIM_TYPE,
                "protocol":  "ISO14443A",
                "atqa":      "0004",
                "sak":       "08",
                "size":      1024,
                "simulated": True,
            }

        # Essaie d'abord HF, puis LF
        result = await self._run_pm3_command("hf search", timeout=timeout)
        output = result.get("output", "")

        uid      = None
        card_type = "unknown"
        protocol = None
        atqa     = None
        sak      = None

        for line in output.splitlines():
            line_l = line.lower()
            if "uid" in line_l:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "uid" and i + 1 < len(parts):
                        uid = parts[i + 1].strip(":").upper()
            if "mifare classic" in line_l:
                card_type = "hf_mifare_classic"
                protocol  = "ISO14443A"
            elif "mifare ultralight" in line_l:
                card_type = "hf_mifare_ultralight"
                protocol  = "ISO14443A"
            elif "ntag" in line_l:
                card_type = "hf_ntag"
                protocol  = "ISO14443A"
            elif "desfire" in line_l:
                card_type = "hf_desfire"
                protocol  = "ISO14443A"
            elif "iclass" in line_l:
                card_type = "hf_iclass"
                protocol  = "iCLASS"
            if "atqa" in line_l:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "atqa" and i + 1 < len(parts):
                        atqa = parts[i + 1]
            if "sak" in line_l:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p.lower() == "sak" and i + 1 < len(parts):
                        sak = parts[i + 1]

        if not uid:
            # Essaie LF
            result_lf = await self._run_pm3_command("lf search", timeout=timeout)
            lf_out = result_lf.get("output", "")
            for line in lf_out.splitlines():
                line_l = line.lower()
                if "uid" in line_l or "card id" in line_l:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if p.lower() in ("uid", "id") and i + 1 < len(parts):
                            uid = parts[i + 1].strip(":").upper()
                if "em4100" in line_l or "hitag" in line_l:
                    card_type = "lf_em4100"
                    protocol  = "EM4100"
                elif "hid" in line_l:
                    card_type = "lf_hid"
                    protocol  = "HID Prox"

        return {
            "success":   bool(uid),
            "uid":       uid,
            "type":      card_type,
            "protocol":  protocol,
            "atqa":      atqa,
            "sak":       sak,
            "simulated": False,
        }

    # ── Dump ──────────────────────────────────────────────────────────────────

    async def dump_card(self, card_type: str = "hf_mifare_classic") -> dict:
        """
        Effectue un dump complet de la carte.
        Retourne {blocks, data_hex, keys_found, simulated}.
        """
        await self._ensure_init()

        if self._simulation_mode:
            blocks = {}
            for i in range(64):
                if i % 4 == 3:
                    # Bloc secteur — clés + droits
                    blocks[i] = "FFFFFFFFFFFF" + "FF0780" + "FFFFFFFFFFFF"
                else:
                    blocks[i] = "".join(random.choices("0123456789ABCDEF", k=32))
            return {
                "success":     True,
                "blocks":      blocks,
                "blocks_count": 64,
                "data_hex":    " ".join(blocks.values()),
                "keys_found":  list(_SIM_KEYS),
                "simulated":   True,
            }

        if "lf" in card_type.lower():
            cmd = "lf em 4x05 dump"
        else:
            cmd = "hf mf dump"

        result = await self._run_pm3_command(cmd, timeout=30)
        output = result.get("output", "")

        blocks     = {}
        keys_found = []

        for line in output.splitlines():
            line = line.strip()
            if line.startswith("Block") or line.startswith("blk"):
                parts = line.split()
                try:
                    blk_num = int(parts[1].rstrip(":"))
                    data    = parts[-1].replace(" ", "")
                    blocks[blk_num] = data.upper()
                except (ValueError, IndexError):
                    pass
            if "key" in line.lower() and "found" in line.lower():
                parts = line.split()
                for p in parts:
                    if len(p) == 12 and all(c in "0123456789abcdefABCDEF" for c in p):
                        keys_found.append(p.upper())

        return {
            "success":      result.get("success", False),
            "blocks":       blocks,
            "blocks_count": len(blocks),
            "data_hex":     " ".join(blocks.values()),
            "keys_found":   list(set(keys_found)),
            "simulated":    False,
        }

    # ── Clone ─────────────────────────────────────────────────────────────────

    async def clone_card(self, source_uid: str, data_hex: str, card_type: str) -> dict:
        """
        Clone les données sur une carte cible (T55xx ou EM4305).
        """
        await self._ensure_init()

        if self._simulation_mode:
            return {
                "success":   True,
                "message":   f"[SIM] Clonage {source_uid} → {card_type}",
                "simulated": True,
            }

        uid_clean = source_uid.replace(":", "").replace(" ", "")

        if "lf" in card_type.lower() or "t55" in card_type.lower() or "em4305" in card_type.lower():
            cmd = f"lf t55 clone --uid {uid_clean}"
        else:
            cmd = f"hf mf cload --uid {uid_clean}"

        result = await self._run_pm3_command(cmd, timeout=30)
        return {
            "success":   result.get("success", False),
            "message":   result.get("output", "")[:200],
            "simulated": False,
        }

    # ── Write MIFARE block ────────────────────────────────────────────────────

    async def write_mifare_block(
        self, block: int, data: str, key: str, key_type: str = "A"
    ) -> dict:
        """Écrit un bloc MIFARE Classic."""
        await self._ensure_init()

        if self._simulation_mode:
            return {"success": True, "block": block, "simulated": True}

        kt = key_type.upper()
        cmd = f"hf mf wrbl --blk {block} -k{kt} -k {key} --data {data}"
        result = await self._run_pm3_command(cmd, timeout=15)
        return {
            "success":   result.get("success", False),
            "block":     block,
            "output":    result.get("output", "")[:200],
            "simulated": False,
        }

    # ── Read MIFARE block ─────────────────────────────────────────────────────

    async def read_mifare_block(self, block: int, key: str, key_type: str = "A") -> dict:
        """Lit un bloc MIFARE Classic."""
        await self._ensure_init()

        if self._simulation_mode:
            data = "".join(random.choices("0123456789ABCDEF", k=32))
            return {"success": True, "block": block, "data": data, "simulated": True}

        kt = key_type.upper()
        cmd = f"hf mf rdbl --blk {block} -k{kt} -k {key}"
        result = await self._run_pm3_command(cmd, timeout=10)

        data = None
        output = result.get("output", "")
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                candidate = parts[-1].replace(" ", "")
                if len(candidate) == 32 and all(c in "0123456789abcdefABCDEF" for c in candidate):
                    data = candidate.upper()
                    break

        return {
            "success":   result.get("success", False),
            "block":     block,
            "data":      data,
            "output":    output[:200],
            "simulated": False,
        }

    # ── Brute force clés ──────────────────────────────────────────────────────

    async def brute_force_keys(self, known_keys: list | None = None) -> dict:
        """
        Tente les clés par défaut + clés fournies.
        Retourne la liste des clés trouvées.
        """
        await self._ensure_init()

        keys_to_try = list(_DEFAULT_KEYS)
        if known_keys:
            for k in known_keys:
                k_clean = k.replace(":", "").replace(" ", "").upper()
                if k_clean not in keys_to_try:
                    keys_to_try.append(k_clean)

        if self._simulation_mode:
            return {
                "success":    True,
                "keys_found": list(_SIM_KEYS),
                "tested":     keys_to_try,
                "simulated":  True,
            }

        keys_str = " ".join(keys_to_try)
        cmd      = f"hf mf chk --dict {keys_str}"
        result   = await self._run_pm3_command(cmd, timeout=60)
        output   = result.get("output", "")

        keys_found = []
        for line in output.splitlines():
            if "found" in line.lower() or "valid" in line.lower():
                parts = line.split()
                for p in parts:
                    if len(p) == 12 and all(c in "0123456789abcdefABCDEF" for c in p):
                        keys_found.append(p.upper())

        return {
            "success":    result.get("success", False),
            "keys_found": list(set(keys_found)),
            "tested":     keys_to_try,
            "simulated":  False,
        }

    # ── Sniff ─────────────────────────────────────────────────────────────────

    async def sniff_rfid(self, duration: int = 30) -> dict:
        """
        Capture les échanges RFID pendant `duration` secondes.
        """
        await self._ensure_init()

        if self._simulation_mode:
            frames = []
            for i in range(10):
                ts = datetime.utcnow().isoformat()
                frames.append({
                    "id":        i + 1,
                    "timestamp": ts,
                    "direction": "reader" if i % 2 == 0 else "card",
                    "data":      "".join(random.choices("0123456789ABCDEF", k=8)),
                    "protocol":  "ISO14443A",
                })
            return {"success": True, "frames": frames, "count": len(frames), "simulated": True}

        cmd    = f"hf sniff -t {duration}"
        result = await self._run_pm3_command(cmd, timeout=duration + 10)
        output = result.get("output", "")

        frames = []
        for i, line in enumerate(output.splitlines()):
            if "data" in line.lower() or line.startswith("#"):
                frames.append({
                    "id":        i,
                    "timestamp": datetime.utcnow().isoformat(),
                    "raw":       line.strip(),
                })

        return {
            "success":   result.get("success", False),
            "frames":    frames,
            "count":     len(frames),
            "simulated": False,
        }

    # ── Simulate ──────────────────────────────────────────────────────────────

    async def simulate_card(
        self, uid: str, data_hex: str, card_type: str, duration: int = 30
    ) -> dict:
        """Émule une carte RFID pendant `duration` secondes."""
        await self._ensure_init()

        uid_clean = uid.replace(":", "").replace(" ", "")

        if self._simulation_mode:
            return {
                "success":   True,
                "message":   f"[SIM] Émulation {uid} ({card_type}) pendant {duration}s",
                "simulated": True,
            }

        if "lf" in card_type.lower() or "em" in card_type.lower():
            cmd = f"lf em 4x05 sim --id {uid_clean}"
        else:
            cmd = f"hf mf sim --uid {uid_clean} -n {duration}"

        result = await self._run_pm3_command(cmd, timeout=duration + 15)
        return {
            "success":   result.get("success", False),
            "message":   result.get("output", "")[:200],
            "simulated": False,
        }

    # ── Analyse type carte ────────────────────────────────────────────────────

    def analyze_card_type(self, raw_data: str) -> dict:
        """
        Analyse les bytes bruts pour identifier format HID, site_code, badge_number.
        """
        raw = raw_data.replace(":", "").replace(" ", "")
        try:
            data_int = int(raw, 16)
        except ValueError:
            return {"error": "Données hexadécimales invalides"}

        result: dict = {
            "raw_data":     raw,
            "format":       None,
            "site_code":    None,
            "badge_number": None,
            "facility_code": None,
            "bits":         len(raw) * 4,
        }

        # HID 26-bit — format le plus courant
        # Bit 0 = parity even, bits 1-8 = facility code, bits 9-24 = card number, bit 25 = parity odd
        if len(raw) >= 7:
            # Essaie 26-bit HID Prox
            try:
                val_26 = data_int & 0x3FFFFFF
                facility  = (val_26 >> 17) & 0xFF
                card_num  = (val_26 >> 1) & 0xFFFF
                if facility > 0 or card_num > 0:
                    result["format"]       = "HID 26-bit"
                    result["facility_code"] = str(facility)
                    result["site_code"]     = str(facility)
                    result["badge_number"]  = str(card_num)
            except Exception:
                pass

        # HID 35-bit Corporate 1000
        if len(raw) >= 9:
            try:
                val_35     = data_int & 0x7FFFFFFFF
                company    = (val_35 >> 22) & 0xFFF
                employee   = (val_35 >> 1) & 0x1FFFFF
                if company > 0:
                    result["format"]        = "HID 35-bit Corporate 1000"
                    result["site_code"]     = str(company)
                    result["badge_number"]  = str(employee)
            except Exception:
                pass

        # Fallback si toujours rien
        if not result["format"]:
            result["format"] = "Inconnu / Propriétaire"

        return result

    # ── Détection vulnérabilités ──────────────────────────────────────────────

    def detect_vulnerabilities(self, card_type: str) -> list:
        """
        Retourne la liste des vulnérabilités connues selon le type de carte.
        """
        ct = card_type.lower()
        vulns = []

        if "em4100" in ct or "em41" in ct:
            vulns.append({
                "id":          "EM4100-TRIVIAL-CLONE",
                "severity":    "CRITICAL",
                "title":       "EM4100 — Clonage trivial",
                "description": "Pas de crypto. UID lisible en clair. Clonable avec n'importe quel T55xx.",
                "cwe":         "CWE-287",
                "mitre":       "T1078",
            })
        if "lf_hid" in ct or "hid" in ct:
            vulns.append({
                "id":          "HID-PROX-CLONABLE",
                "severity":    "HIGH",
                "title":       "HID Prox — Protocole sans authentification",
                "description": "Les cartes HID 125 kHz (26-bit, 35-bit) n'ont aucune protection cryptographique.",
                "cwe":         "CWE-306",
                "mitre":       "T1212",
            })
        if "mifare_classic" in ct or "mifare classic" in ct:
            vulns.append({
                "id":          "MIFARE-CRYPTO1",
                "severity":    "HIGH",
                "title":       "MIFARE Classic — Crypto1 cassé (DARK side / nested)",
                "description": "L'algorithme Crypto1 propriétaire est cryptographiquement faible. Attaque dark-side ou nested en quelques secondes.",
                "cwe":         "CWE-327",
                "mitre":       "T1600",
            })
            vulns.append({
                "id":          "MIFARE-DEFAULT-KEYS",
                "severity":    "MEDIUM",
                "title":       "MIFARE Classic — Clés par défaut probables",
                "description": "Beaucoup de déploiements utilisent les clés FFFFFFFFFFFF ou A0A1A2A3A4A5.",
                "cwe":         "CWE-521",
                "mitre":       "T1110",
            })
        if "iclass" in ct:
            vulns.append({
                "id":          "ICLASS-DEFAULT-KEY",
                "severity":    "MEDIUM",
                "title":       "iCLASS — Clé de configuration par défaut",
                "description": "Les lecteurs iCLASS acceptent souvent la clé de diversification par défaut AA785A789B8F7BB5.",
                "cwe":         "CWE-521",
                "mitre":       "T1110",
            })
        if "desfire" in ct:
            vulns.append({
                "id":          "DESFIRE-VERSION-LEAK",
                "severity":    "LOW",
                "title":       "DESFire — Fuite de version UID",
                "description": "Les premières versions de DESFire EV1 ont un UID fixe non-randomisé, permettant le tracking.",
                "cwe":         "CWE-200",
                "mitre":       "T1592",
            })

        if not vulns:
            vulns.append({
                "id":          "UNKNOWN-CARD",
                "severity":    "INFO",
                "title":       "Type inconnu — analyse manuelle requise",
                "description": "Type de carte non identifié. Analyse manuelle recommandée.",
                "cwe":         None,
                "mitre":       None,
            })

        return vulns

    # ── Statut PM3 ────────────────────────────────────────────────────────────

    async def get_pm3_status(self) -> dict:
        """Retourne {battery, flash, connected, simulation_mode}."""
        await self._ensure_init()

        if self._simulation_mode:
            return {
                "connected":       False,
                "simulation_mode": True,
                "battery":         None,
                "flash":           None,
                "pm3_bin":         self._pm3_bin,
                "port":            self._port,
            }

        result = await self._run_pm3_command("hw status", timeout=8)
        output = result.get("output", "")

        battery = None
        flash   = None
        for line in output.splitlines():
            line_l = line.lower()
            if "battery" in line_l:
                battery = line.strip()
            if "flash" in line_l:
                flash = line.strip()

        return {
            "connected":       True,
            "simulation_mode": False,
            "battery":         battery,
            "flash":           flash,
            "pm3_bin":         self._pm3_bin,
            "port":            self._port,
        }
