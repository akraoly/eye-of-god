"""
HoneypotEngine — Module 16 (DeceptionAgent)
High-interaction honeypots capturing attacker TTPs.
Each honeypot is an asyncio server listening on a port.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import uuid
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet

from app.config import settings
from database.db import SessionLocal
from database.models import HoneypotCapture, HoneypotConfig


# ── Encryption ────────────────────────────────────────────────────────────────

def _get_fernet() -> Fernet:
    """Derive a Fernet key from JWT_SECRET (padded/hashed to 32 bytes)."""
    import hashlib
    raw = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


def _encrypt(data: str) -> str:
    return _get_fernet().encrypt(data.encode()).decode()


def _decrypt(token: str) -> str:
    try:
        return _get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return token


# ── MITRE TTP mapping ─────────────────────────────────────────────────────────

MITRE_PATTERNS: list[tuple[str, str, str]] = [
    # (pattern, technique_id, technique_name)
    (r"(?i)USER\s+\w+|PASS\s+\w+|AUTH\s+\w+", "T1110", "Brute Force"),
    (r"(?i)ssh|sftp", "T1021.004", "Remote Services: SSH"),
    (r"(?i)ftp|vsftpd", "T1021.005", "Remote Services: FTP"),
    (r"(?i)smb|microsoft-ds|cifs|ntlmssp", "T1021.002", "Remote Services: SMB/Windows Admin Shares"),
    (r"(?i)telnet", "T1021.004", "Remote Services: Telnet"),
    (r"(?i)\.\.\/|\.\.\\\\|directory traversal|path traversal", "T1083", "File and Directory Discovery"),
    (r"(?i)cmd\.exe|powershell|/bin/sh|/bin/bash|exec\(|eval\(", "T1059", "Command and Scripting Interpreter"),
    (r"(?i)net user|net group|whoami|id\b|uname", "T1033", "System Owner/User Discovery"),
    (r"(?i)nmap|masscan|zmap|shodan|scanner", "T1595", "Active Scanning"),
    (r"(?i)wget|curl|fetch|download|http://|https://", "T1105", "Ingress Tool Transfer"),
    (r"(?i)base64|b64decode|frombase64", "T1027", "Obfuscated Files or Information"),
    (r"(?i)rm\s+-rf|format\s+c:|del\s+/f", "T1485", "Data Destruction"),
    (r"(?i)ping|tracert|traceroute", "T1018", "Remote System Discovery"),
    (r"(?i)nc\s|netcat|ncat\b|socat", "T1095", "Non-Application Layer Protocol"),
    (r"(?i)UNION\s+SELECT|OR\s+1=1|AND\s+1=1|DROP\s+TABLE|INSERT\s+INTO", "T1190", "Exploit Public-Facing Application"),
    (r"(?i)<script>|javascript:|onerror=|onload=", "T1190", "Exploit Public-Facing Application (XSS)"),
    (r"(?i)ldap|kerberos|AS-REP|TGT|TGS", "T1558", "Steal or Forge Kerberos Tickets"),
]


def _analyze_mitre(raw_data: str) -> list[dict]:
    """Map raw captured data to MITRE ATT&CK techniques."""
    found: dict[str, dict] = {}
    for pattern, tech_id, tech_name in MITRE_PATTERNS:
        if re.search(pattern, raw_data):
            found[tech_id] = {"technique_id": tech_id, "technique_name": tech_name}
    return list(found.values())


def _parse_credentials(raw_data: str, service: str) -> dict:
    """Extract credentials from captured data."""
    creds: dict = {"username": None, "password": None, "service": service}

    # FTP / SMTP pattern
    u = re.search(r"(?i)USER\s+(\S+)", raw_data)
    p = re.search(r"(?i)PASS\s+(\S+)", raw_data)
    if u:
        creds["username"] = u.group(1)
    if p:
        creds["password"] = p.group(1)

    # HTTP Basic auth
    b64 = re.search(r"(?i)Authorization:\s*Basic\s+([A-Za-z0-9+/=]+)", raw_data)
    if b64:
        try:
            decoded = base64.b64decode(b64.group(1)).decode(errors="replace")
            if ":" in decoded:
                creds["username"], _, creds["password"] = decoded.partition(":")
        except Exception:
            pass

    # HTTP form fields
    form_u = re.search(r"(?i)(?:username|user|login|email)=([^&\s]+)", raw_data)
    form_p = re.search(r"(?i)(?:password|pass|pwd)=([^&\s]+)", raw_data)
    if form_u and not creds["username"]:
        creds["username"] = form_u.group(1)
    if form_p and not creds["password"]:
        creds["password"] = form_p.group(1)

    return creds


def _classify_severity(techniques: list, raw_data: str) -> str:
    """Classify interaction severity."""
    critical_ids = {"T1059", "T1485", "T1190"}
    high_ids = {"T1110", "T1105", "T1558"}
    t_ids = {t["technique_id"] for t in techniques}

    if t_ids & critical_ids:
        return "critical"
    if t_ids & high_ids:
        return "high"
    if techniques:
        return "medium"
    return "low"


# ── Protocol handlers ─────────────────────────────────────────────────────────

FAKE_BANNERS: dict[str, bytes] = {
    "ssh": b"SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.4\r\n",
    "ftp": b"220 vsFTPd 3.0.3\r\n",
    "smtp": b"220 mail.company.local ESMTP Sendmail 8.15.2\r\n",
    "http": b"HTTP/1.1 200 OK\r\nServer: Apache/2.4.41 (Ubuntu)\r\nContent-Type: text/html\r\nContent-Length: 0\r\n\r\n",
    "telnet": b"\xff\xfb\x01\xff\xfb\x03\xff\xfd\x18\r\nUbuntu 20.04.6 LTS\r\nlogin: ",
    "smb": b"\x00\x00\x00\x00",
}

FAKE_RESPONSES: dict[str, dict[str, bytes]] = {
    "ftp": {
        b"USER": b"331 Password required for user.\r\n",
        b"PASS": b"530 Login incorrect.\r\n",
        b"QUIT": b"221 Goodbye.\r\n",
        b"LIST": b"150 Here comes the directory listing.\r\n226 Directory send OK.\r\n",
        b"PWD": b"257 \"/\" is the current directory\r\n",
        b"SYST": b"215 UNIX Type: L8\r\n",
    },
    "smtp": {
        b"EHLO": b"250-mail.company.local\r\n250-PIPELINING\r\n250 AUTH LOGIN PLAIN\r\n",
        b"HELO": b"250 mail.company.local\r\n",
        b"AUTH": b"535 5.7.8 Authentication credentials invalid\r\n",
        b"MAIL": b"250 2.1.0 Ok\r\n",
        b"QUIT": b"221 2.0.0 Bye\r\n",
    },
    "telnet": {
        b"": b"Password: ",
    },
    "ssh": {},
    "http": {},
    "smb": {},
}


class _HoneypotHandler:
    """Per-connection handler for a honeypot service."""

    def __init__(
        self,
        honeypot_id: str,
        port: int,
        service_type: str,
        fake_banner: Optional[bytes],
    ):
        self.honeypot_id = honeypot_id
        self.port = port
        self.service_type = service_type
        self.fake_banner = fake_banner or FAKE_BANNERS.get(service_type, b"Welcome\r\n")

    async def handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        peername = writer.get_extra_info("peername", ("0.0.0.0", 0))
        attacker_ip = peername[0]
        attacker_port = peername[1]
        raw_chunks: list[str] = []

        try:
            # Send banner
            writer.write(self.fake_banner)
            await writer.drain()
            raw_chunks.append(f"[BANNER_SENT] {self.fake_banner.decode(errors='replace')}")

            # Collect data for up to 30 seconds, max 8KB
            deadline = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < deadline:
                try:
                    chunk = await asyncio.wait_for(reader.read(1024), timeout=5.0)
                except asyncio.TimeoutError:
                    break
                if not chunk:
                    break

                decoded = chunk.decode(errors="replace")
                raw_chunks.append(decoded)

                # Send fake response
                response = self._get_response(chunk)
                if response:
                    writer.write(response)
                    await writer.drain()

                if len("\n".join(raw_chunks)) > 8192:
                    break

        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass

        raw_data = "\n".join(raw_chunks)
        if not raw_data.strip():
            return

        await self._save_capture(attacker_ip, attacker_port, raw_data)

    def _get_response(self, chunk: bytes) -> Optional[bytes]:
        """Return appropriate fake response for the service protocol."""
        service_responses = FAKE_RESPONSES.get(self.service_type, {})
        chunk_upper = chunk.upper()
        for keyword, response in service_responses.items():
            if keyword in chunk_upper:
                return response

        if self.service_type == "http":
            if chunk_upper.startswith(b"GET") or chunk_upper.startswith(b"POST"):
                return (
                    b"HTTP/1.1 401 Unauthorized\r\n"
                    b"Server: Apache/2.4.41 (Ubuntu)\r\n"
                    b"WWW-Authenticate: Basic realm=\"Admin\"\r\n"
                    b"Content-Length: 0\r\n\r\n"
                )
        return None

    async def _save_capture(
        self, attacker_ip: str, attacker_port: int, raw_data: str
    ):
        techniques = _analyze_mitre(raw_data)
        creds = _parse_credentials(raw_data, self.service_type)
        severity = _classify_severity(techniques, raw_data)

        fernet = _get_fernet()
        enc_creds = fernet.encrypt(json.dumps(creds).encode()).decode()

        db = SessionLocal()
        try:
            capture = HoneypotCapture(
                capture_id=str(uuid.uuid4()),
                honeypot_id=self.honeypot_id,
                attacker_ip=attacker_ip,
                attacker_port=attacker_port,
                timestamp=datetime.utcnow(),
                raw_data=raw_data[:4096],
                parsed_credentials=enc_creds,
                mitre_techniques=json.dumps(techniques),
                severity=severity,
            )
            db.add(capture)

            # Update captures_count
            hp = db.query(HoneypotConfig).filter_by(honeypot_id=self.honeypot_id).first()
            if hp:
                hp.captures_count = (hp.captures_count or 0) + 1

            db.commit()
        finally:
            db.close()


# ── HoneypotEngine ────────────────────────────────────────────────────────────

class HoneypotEngine:
    """
    High-interaction honeypots capturing attacker TTPs.
    Each honeypot is an asyncio server listening on a port.
    """

    _active_listeners: dict[int, asyncio.Server] = {}
    _handlers: dict[int, _HoneypotHandler] = {}

    def _create_fake_banner(self, service: str) -> bytes:
        return FAKE_BANNERS.get(service, b"Welcome\r\n")

    async def start_honeypot(
        self,
        port: int,
        service_type: str,
        fake_banner: Optional[str] = None,
    ) -> dict:
        """
        Start honeypot listener on given port.
        Supports: ssh, http, ftp, smb, telnet, smtp
        Returns: honeypot_id
        """
        if port in self._active_listeners:
            return {"error": f"Port {port} already has an active honeypot"}

        honeypot_id = str(uuid.uuid4())
        banner_bytes: Optional[bytes] = None
        if fake_banner:
            banner_bytes = fake_banner.encode()

        handler = _HoneypotHandler(honeypot_id, port, service_type, banner_bytes)
        self._handlers[port] = handler

        try:
            server = await asyncio.start_server(
                handler.handle,
                "0.0.0.0",
                port,
            )
            self._active_listeners[port] = server
        except OSError as e:
            return {"error": f"Cannot bind to port {port}: {e}"}

        # Save to DB
        db = SessionLocal()
        try:
            hp = HoneypotConfig(
                honeypot_id=honeypot_id,
                port=port,
                service_type=service_type,
                fake_banner=(fake_banner or self._create_fake_banner(service_type).decode(errors="replace")),
                is_active=True,
                captures_count=0,
                created_at=datetime.utcnow(),
            )
            db.add(hp)
            db.commit()
        finally:
            db.close()

        return {
            "honeypot_id": honeypot_id,
            "port": port,
            "service_type": service_type,
            "status": "listening",
            "message": f"Honeypot started on port {port} ({service_type})",
        }

    async def stop_honeypot(self, port: int) -> bool:
        """Stop honeypot on given port."""
        server = self._active_listeners.pop(port, None)
        if server:
            server.close()
            await server.wait_closed()

        self._handlers.pop(port, None)

        db = SessionLocal()
        try:
            hp = db.query(HoneypotConfig).filter_by(port=port, is_active=True).first()
            if hp:
                hp.is_active = False
                db.commit()
        finally:
            db.close()

        return server is not None

    async def list_honeypots(self) -> list:
        """List active honeypot listeners."""
        db = SessionLocal()
        try:
            hps = db.query(HoneypotConfig).filter_by(is_active=True).all()
            return [
                {
                    "honeypot_id": hp.honeypot_id,
                    "port": hp.port,
                    "service_type": hp.service_type,
                    "captures_count": hp.captures_count,
                    "is_running": hp.port in self._active_listeners,
                    "created_at": hp.created_at.isoformat() if hp.created_at else None,
                }
                for hp in hps
            ]
        finally:
            db.close()

    async def get_captures(
        self,
        honeypot_id: Optional[str] = None,
        limit: int = 100,
    ) -> list:
        """Get captured attacker interactions."""
        db = SessionLocal()
        try:
            q = db.query(HoneypotCapture)
            if honeypot_id:
                q = q.filter_by(honeypot_id=honeypot_id)
            captures = q.order_by(HoneypotCapture.timestamp.desc()).limit(limit).all()

            result = []
            for c in captures:
                # Decrypt credentials
                creds_raw = c.parsed_credentials
                try:
                    creds_raw = _decrypt(creds_raw)
                    creds = json.loads(creds_raw)
                except Exception:
                    creds = {}

                result.append({
                    "capture_id": c.capture_id,
                    "honeypot_id": c.honeypot_id,
                    "attacker_ip": c.attacker_ip,
                    "attacker_port": c.attacker_port,
                    "timestamp": c.timestamp.isoformat() if c.timestamp else None,
                    "severity": c.severity,
                    "raw_data_preview": (c.raw_data or "")[:256],
                    "credentials": creds,
                    "mitre_techniques": json.loads(c.mitre_techniques or "[]"),
                })
            return result
        finally:
            db.close()

    async def analyze_interaction(self, interaction: dict) -> dict:
        """
        MITRE ATT&CK TTP mapping of captured interaction.
        """
        raw = interaction.get("raw_data", "") + " " + str(interaction.get("data", ""))
        techniques = _analyze_mitre(raw)
        creds = _parse_credentials(raw, interaction.get("service_type", "unknown"))
        severity = _classify_severity(techniques, raw)

        # Heuristic threat actor profiling
        profile_hints = []
        if re.search(r"(?i)masscan|zmap|shodan", raw):
            profile_hints.append("automated_scanner")
        if re.search(r"(?i)metasploit|msf|exploit/", raw):
            profile_hints.append("metasploit_user")
        if re.search(r"(?i)cobalt|beacon|cobaltstrike", raw):
            profile_hints.append("cobalt_strike")
        if len(set(re.findall(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", raw))) > 3:
            profile_hints.append("multi_hop_routing")

        return {
            "mitre_techniques": techniques,
            "credentials_found": creds,
            "severity": severity,
            "threat_actor_hints": profile_hints,
            "raw_data_length": len(raw),
            "analysis_timestamp": datetime.utcnow().isoformat(),
        }

    async def get_analytics(self) -> dict:
        """Aggregate TTP analytics across all captures."""
        db = SessionLocal()
        try:
            captures = db.query(HoneypotCapture).all()
            tech_counts: dict = {}
            ip_counts: dict = {}
            sev_counts: dict = {"critical": 0, "high": 0, "medium": 0, "low": 0}

            for c in captures:
                ip_counts[c.attacker_ip] = ip_counts.get(c.attacker_ip, 0) + 1
                sev = c.severity or "low"
                sev_counts[sev] = sev_counts.get(sev, 0) + 1
                for t in json.loads(c.mitre_techniques or "[]"):
                    tid = t.get("technique_id", "?")
                    tech_counts[tid] = tech_counts.get(tid, 0) + 1

            top_ips = sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            top_techs = sorted(tech_counts.items(), key=lambda x: x[1], reverse=True)[:15]

            return {
                "total_captures": len(captures),
                "severity_breakdown": sev_counts,
                "top_attacker_ips": [{"ip": ip, "count": cnt} for ip, cnt in top_ips],
                "top_mitre_techniques": [
                    {"technique_id": tid, "count": cnt} for tid, cnt in top_techs
                ],
                "active_honeypots": len(self._active_listeners),
            }
        finally:
            db.close()
