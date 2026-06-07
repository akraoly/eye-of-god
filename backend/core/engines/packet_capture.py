"""
PacketCaptureEngine — Capability 4: Network Sniffer.

Network packet capture using tcpdump.
Extracts credentials, analyzes protocols, provides live streaming.

All subprocess calls use asyncio.create_subprocess_exec.
Tools checked with shutil.which() before invocation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CAPTURES_DIR = Path("./data/captures")
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)


# ── Subprocess helper ──────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 60) -> tuple[str, bool]:
    """Run subprocess, return (stdout+stderr, success)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return out.decode("utf-8", errors="replace"), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]} exceeded {timeout}s", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False


# ── Engine ─────────────────────────────────────────────────────────────────────

class PacketCaptureEngine:
    """
    Network packet capture using tcpdump.
    Extracts credentials, analyzes protocols.
    """

    CAPTURES_DIR = CAPTURES_DIR

    # capture_id -> {process, file_path, interface, started_at, status, ...}
    _active_captures: dict = {}

    # stream_id -> {queue, interface, process}
    _live_streams: dict = {}

    # ── Interface listing ──────────────────────────────────────────────────────

    async def get_interfaces(self) -> list:
        """List all network interfaces via ip link show / ip addr."""
        interfaces = []
        ip_bin = shutil.which("ip")
        if ip_bin:
            out, ok = await _run([ip_bin, "link", "show"], timeout=10)
            if ok:
                # Parse: "2: eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>"
                for line in out.splitlines():
                    m = re.match(r"^\s*(\d+):\s+(\S+):\s+<([^>]*)>", line)
                    if m:
                        idx = m.group(1)
                        name = m.group(2).rstrip(":")
                        flags = m.group(3)
                        interfaces.append({
                            "index": int(idx),
                            "name": name,
                            "flags": flags.split(","),
                            "up": "UP" in flags,
                            "loopback": "LOOPBACK" in flags,
                        })
        # Fallback: /proc/net/dev
        if not interfaces:
            try:
                with open("/proc/net/dev") as f:
                    for line in f.readlines()[2:]:
                        iface = line.split(":")[0].strip()
                        if iface:
                            interfaces.append({"name": iface, "up": True, "loopback": iface == "lo"})
            except Exception:
                pass

        # Final fallback
        if not interfaces:
            interfaces = [
                {"name": "eth0", "up": True, "loopback": False, "note": "ip not found — assumed"},
                {"name": "lo", "up": True, "loopback": True},
            ]

        return interfaces

    # ── Start capture ──────────────────────────────────────────────────────────

    async def start_capture(
        self,
        interface: str,
        bpf_filter: str = "",
        max_packets: int = 10000,
        capture_id: Optional[str] = None,
    ) -> dict:
        """
        Start packet capture with tcpdump.
        tcpdump -i {interface} -w {file.pcap} -c {max_packets} {filter}
        Returns: {capture_id, file_path, status}
        """
        if not capture_id:
            capture_id = str(uuid.uuid4())[:12]

        tcpdump = shutil.which("tcpdump")
        if not tcpdump:
            return {
                "success": False,
                "error": "tcpdump not found. Install with: apt install tcpdump",
                "capture_id": capture_id,
            }

        pcap_path = CAPTURES_DIR / f"{capture_id}.pcap"

        cmd = [
            tcpdump,
            "-i", interface,
            "-w", str(pcap_path),
            "-c", str(max_packets),
            "-n",             # no DNS resolution
            "-U",             # packet-buffered output (immediate writes)
        ]
        if bpf_filter.strip():
            cmd.extend(bpf_filter.strip().split())

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except PermissionError:
            return {
                "success": False,
                "error": "Permission denied. Run with sudo or set CAP_NET_RAW capability.",
                "capture_id": capture_id,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "capture_id": capture_id}

        self._active_captures[capture_id] = {
            "process": proc,
            "file_path": str(pcap_path),
            "interface": interface,
            "bpf_filter": bpf_filter,
            "max_packets": max_packets,
            "status": "running",
            "packet_count": 0,
            "started_at": datetime.utcnow().isoformat(),
        }

        # Persist to DB
        await self._save_capture_to_db(capture_id, interface, bpf_filter, str(pcap_path))

        return {
            "success": True,
            "capture_id": capture_id,
            "file_path": str(pcap_path),
            "interface": interface,
            "bpf_filter": bpf_filter,
            "max_packets": max_packets,
            "status": "running",
        }

    # ── Stop capture ───────────────────────────────────────────────────────────

    async def stop_capture(self, capture_id: str) -> dict:
        """Kill tcpdump, finalize pcap file."""
        cap = self._active_captures.get(capture_id)
        if not cap:
            # Try DB lookup
            return await self._stop_from_db(capture_id)

        proc: asyncio.subprocess.Process = cap["process"]
        try:
            proc.terminate()
            await asyncio.wait_for(proc.communicate(), timeout=10)
        except (ProcessLookupError, asyncio.TimeoutError):
            try:
                proc.kill()
            except Exception:
                pass

        pcap_path = Path(cap["file_path"])
        file_size = pcap_path.stat().st_size if pcap_path.exists() else 0

        cap["status"] = "stopped"
        cap["stopped_at"] = datetime.utcnow().isoformat()
        cap["file_size"] = file_size
        self._active_captures.pop(capture_id, None)

        # Update DB
        await self._update_capture_db(capture_id, status="stopped", file_size=file_size)

        return {
            "success": True,
            "capture_id": capture_id,
            "file_path": str(pcap_path),
            "file_size": file_size,
            "status": "stopped",
        }

    async def _stop_from_db(self, capture_id: str) -> dict:
        """Stop a capture tracked only in DB (not in memory)."""
        try:
            from database.db import SessionLocal
            from database.models import PacketCapture as PCModel
            db = SessionLocal()
            try:
                rec = db.query(PCModel).filter(PCModel.capture_id == capture_id).first()
                if rec:
                    rec.status = "stopped"
                    rec.stopped_at = datetime.utcnow()
                    db.commit()
                    return {"success": True, "capture_id": capture_id, "status": "stopped",
                            "file_path": rec.pcap_file_path}
            finally:
                db.close()
        except Exception as e:
            logger.error(f"_stop_from_db error: {e}")
        return {"success": False, "error": f"Capture {capture_id} not found"}

    # ── Analyze capture ────────────────────────────────────────────────────────

    async def analyze_capture(self, capture_id: str, analysis_type: str = "all") -> dict:
        """
        Analyze pcap file using tshark or scapy.
        analysis_type: http | dns | smb | ftp | credentials | all
        """
        pcap_path = await self._get_pcap_path(capture_id)
        if not pcap_path or not Path(pcap_path).exists():
            return {"success": False, "error": f"PCAP file not found for capture {capture_id}"}

        result: dict = {
            "success": True,
            "capture_id": capture_id,
            "analysis_type": analysis_type,
        }

        tshark = shutil.which("tshark")

        if tshark:
            result["method"] = "tshark"

            # Protocol summary
            if analysis_type in ("all",):
                out, ok = await _run(
                    [tshark, "-r", pcap_path, "-q", "-z", "io,phs"],
                    timeout=60,
                )
                if ok:
                    result["protocol_hierarchy"] = out

            # HTTP analysis
            if analysis_type in ("http", "all"):
                out, ok = await _run(
                    [tshark, "-r", pcap_path, "-Y", "http",
                     "-T", "fields",
                     "-e", "ip.src", "-e", "ip.dst",
                     "-e", "http.request.method",
                     "-e", "http.request.uri",
                     "-e", "http.host",
                     "-e", "http.response.code"],
                    timeout=60,
                )
                if ok:
                    result["http_summary"] = self._parse_tshark_fields(out, ["src", "dst", "method", "uri", "host", "status"])

            # DNS analysis
            if analysis_type in ("dns", "all"):
                out, ok = await _run(
                    [tshark, "-r", pcap_path, "-Y", "dns",
                     "-T", "fields",
                     "-e", "ip.src",
                     "-e", "dns.qry.name",
                     "-e", "dns.resp.name"],
                    timeout=60,
                )
                if ok:
                    result["dns_queries"] = self._parse_tshark_fields(out, ["src", "query", "response"])

            # FTP
            if analysis_type in ("ftp", "all"):
                out, ok = await _run(
                    [tshark, "-r", pcap_path, "-Y", "ftp",
                     "-T", "fields",
                     "-e", "ip.src", "-e", "ip.dst",
                     "-e", "ftp.request.command",
                     "-e", "ftp.request.arg"],
                    timeout=60,
                )
                if ok:
                    result["ftp_commands"] = self._parse_tshark_fields(out, ["src", "dst", "command", "arg"])

            # SMB
            if analysis_type in ("smb", "all"):
                out, ok = await _run(
                    [tshark, "-r", pcap_path, "-Y", "smb || smb2",
                     "-T", "fields",
                     "-e", "ip.src", "-e", "ip.dst",
                     "-e", "smb.cmd", "-e", "smb2.cmd"],
                    timeout=60,
                )
                if ok:
                    result["smb_activity"] = self._parse_tshark_fields(out, ["src", "dst", "smb_cmd", "smb2_cmd"])

            # Credentials
            if analysis_type in ("credentials", "all"):
                result["credentials"] = await self.extract_credentials(capture_id)

        else:
            # Fallback: basic stats from file
            result["method"] = "basic_stats"
            pcap = Path(pcap_path)
            result["file_size"] = pcap.stat().st_size if pcap.exists() else 0
            result["note"] = "tshark not found — install wireshark-cli for full analysis"

        return result

    @staticmethod
    def _parse_tshark_fields(output: str, field_names: list) -> list:
        """Parse tshark -T fields tab-separated output into list of dicts."""
        rows = []
        for line in output.splitlines():
            parts = line.split("\t")
            row = {}
            for i, name in enumerate(field_names):
                row[name] = parts[i].strip() if i < len(parts) else ""
            if any(v for v in row.values()):
                rows.append(row)
        return rows

    # ── Extract credentials ────────────────────────────────────────────────────

    async def extract_credentials(self, capture_id: str) -> list:
        """
        Extract plaintext credentials from capture.
        Looks for HTTP Basic Auth, FTP USER/PASS, Telnet, POP3, SMTP.
        Returns: [{protocol, username, password, source_ip, dest_ip, timestamp}]
        """
        pcap_path = await self._get_pcap_path(capture_id)
        if not pcap_path or not Path(pcap_path).exists():
            return []

        creds = []
        tshark = shutil.which("tshark")

        if tshark:
            # HTTP Basic Auth
            out, ok = await _run(
                [
                    tshark, "-r", pcap_path,
                    "-Y", "http.authorization",
                    "-T", "fields",
                    "-e", "ip.src", "-e", "ip.dst",
                    "-e", "http.authorization",
                    "-e", "frame.time_epoch",
                ],
                timeout=60,
            )
            if ok:
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 3 and parts[2]:
                        auth = parts[2].strip()
                        # Decode Basic auth
                        if auth.lower().startswith("basic "):
                            try:
                                import base64 as _b64
                                decoded = _b64.b64decode(auth[6:]).decode("utf-8", errors="replace")
                                if ":" in decoded:
                                    user, pwd = decoded.split(":", 1)
                                    creds.append({
                                        "protocol": "HTTP_Basic",
                                        "username": user,
                                        "password": pwd,
                                        "source_ip": parts[0],
                                        "dest_ip": parts[1] if len(parts) > 1 else "",
                                        "timestamp": parts[3] if len(parts) > 3 else "",
                                    })
                            except Exception:
                                pass

            # FTP USER + PASS
            out, ok = await _run(
                [
                    tshark, "-r", pcap_path,
                    "-Y", "ftp.request.command == USER || ftp.request.command == PASS",
                    "-T", "fields",
                    "-e", "ip.src", "-e", "ip.dst",
                    "-e", "ftp.request.command",
                    "-e", "ftp.request.arg",
                    "-e", "frame.time_epoch",
                ],
                timeout=60,
            )
            if ok:
                ftp_sessions: dict = {}
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 4:
                        src, dst, cmd, arg = parts[0], parts[1], parts[2], parts[3]
                        ts = parts[4] if len(parts) > 4 else ""
                        key = f"{src}_{dst}"
                        if cmd.upper() == "USER":
                            ftp_sessions[key] = {"username": arg, "source_ip": src, "dest_ip": dst, "ts": ts}
                        elif cmd.upper() == "PASS" and key in ftp_sessions:
                            creds.append({
                                "protocol": "FTP",
                                "username": ftp_sessions[key]["username"],
                                "password": arg,
                                "source_ip": src,
                                "dest_ip": dst,
                                "timestamp": ts,
                            })

            # SMTP AUTH
            out, ok = await _run(
                [
                    tshark, "-r", pcap_path,
                    "-Y", "smtp",
                    "-T", "fields",
                    "-e", "ip.src", "-e", "ip.dst",
                    "-e", "smtp.req.parameter",
                    "-e", "frame.time_epoch",
                ],
                timeout=60,
            )
            if ok:
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 3 and parts[2]:
                        param = parts[2].strip()
                        if param:
                            try:
                                import base64 as _b64
                                decoded = _b64.b64decode(param).decode("utf-8", errors="replace")
                                if "\x00" in decoded:
                                    chunks = decoded.split("\x00")
                                    if len(chunks) >= 3:
                                        creds.append({
                                            "protocol": "SMTP_AUTH",
                                            "username": chunks[1],
                                            "password": chunks[2],
                                            "source_ip": parts[0],
                                            "dest_ip": parts[1],
                                            "timestamp": parts[3] if len(parts) > 3 else "",
                                        })
                            except Exception:
                                pass

            # POP3
            out, ok = await _run(
                [
                    tshark, "-r", pcap_path,
                    "-Y", 'pop.request.command == "USER" || pop.request.command == "PASS"',
                    "-T", "fields",
                    "-e", "ip.src", "-e", "ip.dst",
                    "-e", "pop.request.command",
                    "-e", "pop.request.parameter",
                    "-e", "frame.time_epoch",
                ],
                timeout=60,
            )
            if ok:
                pop_sessions: dict = {}
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 4:
                        src, dst, cmd, param = parts[0], parts[1], parts[2], parts[3]
                        ts = parts[4] if len(parts) > 4 else ""
                        key = f"{src}_{dst}"
                        if cmd.upper() == "USER":
                            pop_sessions[key] = {"username": param, "src": src, "dst": dst}
                        elif cmd.upper() == "PASS" and key in pop_sessions:
                            creds.append({
                                "protocol": "POP3",
                                "username": pop_sessions[key]["username"],
                                "password": param,
                                "source_ip": src,
                                "dest_ip": dst,
                                "timestamp": ts,
                            })

            # Telnet (look for common login prompts in payload)
            out, ok = await _run(
                [
                    tshark, "-r", pcap_path,
                    "-Y", "telnet",
                    "-T", "fields",
                    "-e", "ip.src", "-e", "ip.dst",
                    "-e", "telnet.data",
                ],
                timeout=60,
            )
            if ok:
                telnet_buffer: dict = {}
                for line in out.splitlines():
                    parts = line.split("\t")
                    if len(parts) >= 3:
                        src, dst, data = parts[0], parts[1], parts[2]
                        key = f"{src}_{dst}"
                        if key not in telnet_buffer:
                            telnet_buffer[key] = {"src": src, "dst": dst, "buf": ""}
                        telnet_buffer[key]["buf"] += data

                for key, session in telnet_buffer.items():
                    buf = session["buf"].lower()
                    # Look for login: / password: patterns
                    user_m = re.search(r"login:\s*(\S+)", buf)
                    pass_m = re.search(r"password:\s*(\S+)", buf)
                    if user_m or pass_m:
                        creds.append({
                            "protocol": "Telnet",
                            "username": user_m.group(1) if user_m else "",
                            "password": pass_m.group(1) if pass_m else "",
                            "source_ip": session["src"],
                            "dest_ip": session["dst"],
                            "timestamp": "",
                        })

        # Update DB creds_found count
        if creds:
            await self._update_capture_db(capture_id, creds_found=len(creds))

        return creds

    # ── Search packets ─────────────────────────────────────────────────────────

    async def search_packets(self, capture_id: str, query: str) -> list:
        """Search packets by string in payload using tshark."""
        pcap_path = await self._get_pcap_path(capture_id)
        if not pcap_path or not Path(pcap_path).exists():
            return []

        tshark = shutil.which("tshark")
        if not tshark:
            return [{"error": "tshark not found"}]

        # Use tshark display filter with frame contains
        safe_query = query.replace('"', '\\"')
        out, ok = await _run(
            [
                tshark, "-r", pcap_path,
                "-Y", f'frame contains "{safe_query}"',
                "-T", "fields",
                "-e", "frame.number",
                "-e", "frame.time",
                "-e", "ip.src",
                "-e", "ip.dst",
                "-e", "frame.protocols",
            ],
            timeout=60,
        )
        if not ok:
            return []

        return self._parse_tshark_fields(out, ["frame_number", "time", "src", "dst", "protocols"])

    # ── Live stats ─────────────────────────────────────────────────────────────

    async def get_live_stats(self, capture_id: str) -> dict:
        """Get current capture statistics: packets, bytes, protocols."""
        cap = self._active_captures.get(capture_id)
        pcap_path = await self._get_pcap_path(capture_id)

        stats: dict = {
            "capture_id": capture_id,
            "status": cap["status"] if cap else "stopped",
            "packets": 0,
            "file_size": 0,
        }

        if pcap_path and Path(pcap_path).exists():
            stats["file_size"] = Path(pcap_path).stat().st_size

        tshark = shutil.which("tshark")
        if tshark and pcap_path and Path(pcap_path).exists():
            out, ok = await _run(
                [tshark, "-r", pcap_path, "-q", "-z", "io,stat,0"],
                timeout=30,
            )
            if ok:
                # Parse packet count
                pkt_m = re.search(r"(\d+)\s+frames", out)
                if pkt_m:
                    stats["packets"] = int(pkt_m.group(1))
                stats["io_stats"] = out[:2000]
        else:
            # Count pcap records manually from file header
            if pcap_path and Path(pcap_path).exists():
                try:
                    import struct
                    with open(pcap_path, "rb") as f:
                        header = f.read(24)
                        if len(header) == 24:
                            magic = struct.unpack("<I", header[:4])[0]
                            little_endian = magic in (0xA1B2C3D4, 0xA1B23C4D)
                            pkt_count = 0
                            while True:
                                pkt_hdr = f.read(16)
                                if len(pkt_hdr) < 16:
                                    break
                                fmt = "<I" if little_endian else ">I"
                                caplen = struct.unpack(fmt, pkt_hdr[8:12])[0]
                                f.seek(caplen, 1)
                                pkt_count += 1
                            stats["packets"] = pkt_count
                except Exception:
                    pass

        return stats

    # ── DNS queries ────────────────────────────────────────────────────────────

    async def get_dns_queries(self, capture_id: str) -> list:
        """Extract all DNS queries from capture."""
        pcap_path = await self._get_pcap_path(capture_id)
        if not pcap_path or not Path(pcap_path).exists():
            return []

        tshark = shutil.which("tshark")
        if not tshark:
            return [{"error": "tshark not found — install wireshark-cli"}]

        out, ok = await _run(
            [
                tshark, "-r", pcap_path,
                "-Y", "dns",
                "-T", "fields",
                "-e", "frame.time",
                "-e", "ip.src",
                "-e", "ip.dst",
                "-e", "dns.qry.name",
                "-e", "dns.qry.type",
                "-e", "dns.resp.name",
                "-e", "dns.a",
            ],
            timeout=60,
        )
        if not ok:
            return []

        return self._parse_tshark_fields(out, ["time", "src", "dst", "query", "type", "response", "answer_ip"])

    # ── HTTP requests ──────────────────────────────────────────────────────────

    async def get_http_requests(self, capture_id: str) -> list:
        """Extract HTTP requests with headers."""
        pcap_path = await self._get_pcap_path(capture_id)
        if not pcap_path or not Path(pcap_path).exists():
            return []

        tshark = shutil.which("tshark")
        if not tshark:
            return [{"error": "tshark not found"}]

        out, ok = await _run(
            [
                tshark, "-r", pcap_path,
                "-Y", "http.request",
                "-T", "fields",
                "-e", "frame.time",
                "-e", "ip.src",
                "-e", "ip.dst",
                "-e", "http.request.method",
                "-e", "http.host",
                "-e", "http.request.uri",
                "-e", "http.user_agent",
                "-e", "http.authorization",
                "-e", "http.cookie",
            ],
            timeout=60,
        )
        if not ok:
            return []

        return self._parse_tshark_fields(
            out,
            ["time", "src", "dst", "method", "host", "uri", "user_agent", "authorization", "cookie"]
        )

    # ── List captures ──────────────────────────────────────────────────────────

    async def list_captures(self) -> list:
        """List all captures from DB, with filesystem fallback."""
        try:
            from database.db import SessionLocal
            from database.models import PacketCapture as PCModel
            db = SessionLocal()
            try:
                captures = db.query(PCModel).order_by(PCModel.started_at.desc()).all()
                return [
                    {
                        "capture_id": c.capture_id,
                        "interface": c.interface,
                        "bpf_filter": c.bpf_filter,
                        "status": c.status,
                        "packet_count": c.packet_count,
                        "pcap_file_path": c.pcap_file_path,
                        "file_size": c.file_size,
                        "creds_found": c.creds_found,
                        "started_at": c.started_at.isoformat() if c.started_at else None,
                        "stopped_at": c.stopped_at.isoformat() if c.stopped_at else None,
                    }
                    for c in captures
                ]
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"DB unavailable ({e}), scanning filesystem")
            result = []
            for f in sorted(CAPTURES_DIR.glob("*.pcap"), key=lambda x: x.stat().st_mtime, reverse=True):
                result.append({
                    "capture_id": f.stem,
                    "pcap_file_path": str(f),
                    "file_size": f.stat().st_size,
                    "status": "unknown",
                    "started_at": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
                })
            return result

    # ── Live packet stream (for WebSocket) ────────────────────────────────────

    async def start_live_stream(self, interface: str) -> str:
        """
        Start live packet stream via tcpdump piped output.
        Returns stream_id for WebSocket consumption.
        """
        stream_id = str(uuid.uuid4())[:12]
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)

        tcpdump = shutil.which("tcpdump")
        if not tcpdump:
            self._live_streams[stream_id] = {
                "queue": queue,
                "interface": interface,
                "error": "tcpdump not found",
            }
            return stream_id

        cmd = [
            tcpdump, "-i", interface,
            "-l",              # line-buffered
            "-n",              # no DNS
            "-q",              # quiet
            "--immediate-mode",
        ]
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            self._live_streams[stream_id] = {
                "queue": queue,
                "interface": interface,
                "process": proc,
            }

            async def _feed(p=proc, q=queue):
                try:
                    while True:
                        line = await p.stdout.readline()
                        if not line:
                            break
                        try:
                            q.put_nowait(line.decode("utf-8", errors="replace").rstrip())
                        except asyncio.QueueFull:
                            pass
                except Exception:
                    pass

            asyncio.create_task(_feed())
        except Exception as e:
            logger.warning(f"tcpdump live stream failed: {e}")
            self._live_streams[stream_id] = {"queue": queue, "interface": interface, "error": str(e)}

        return stream_id

    async def stop_live_stream(self, stream_id: str) -> bool:
        """Stop a live packet stream."""
        entry = self._live_streams.pop(stream_id, None)
        if not entry:
            return False
        proc = entry.get("process")
        if proc:
            try:
                proc.terminate()
                await asyncio.wait_for(proc.communicate(), timeout=5)
            except Exception:
                pass
        return True

    async def get_stream_packet(self, stream_id: str, timeout: float = 2.0) -> Optional[str]:
        """Get next packet line from a live stream (used by WebSocket)."""
        entry = self._live_streams.get(stream_id)
        if not entry:
            return None
        try:
            return await asyncio.wait_for(entry["queue"].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    # ── DB helpers ─────────────────────────────────────────────────────────────

    async def _get_pcap_path(self, capture_id: str) -> Optional[str]:
        """Resolve PCAP file path for a capture_id."""
        # Check in-memory first
        cap = self._active_captures.get(capture_id)
        if cap:
            return cap.get("file_path")
        # Try standard path
        p = CAPTURES_DIR / f"{capture_id}.pcap"
        if p.exists():
            return str(p)
        # Try DB
        try:
            from database.db import SessionLocal
            from database.models import PacketCapture as PCModel
            db = SessionLocal()
            try:
                rec = db.query(PCModel).filter(PCModel.capture_id == capture_id).first()
                if rec:
                    return rec.pcap_file_path
            finally:
                db.close()
        except Exception:
            pass
        return None

    async def _save_capture_to_db(
        self,
        capture_id: str,
        interface: str,
        bpf_filter: str,
        pcap_path: str,
    ):
        """Persist capture metadata to DB."""
        try:
            from database.db import SessionLocal
            from database.models import PacketCapture as PCModel
            db = SessionLocal()
            try:
                rec = PCModel(
                    capture_id=capture_id,
                    interface=interface,
                    bpf_filter=bpf_filter,
                    status="running",
                    pcap_file_path=pcap_path,
                    file_size=0,
                    creds_found=0,
                    packet_count=0,
                )
                db.add(rec)
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"_save_capture_to_db error: {e}")

    async def _update_capture_db(
        self,
        capture_id: str,
        status: Optional[str] = None,
        file_size: Optional[int] = None,
        creds_found: Optional[int] = None,
        packet_count: Optional[int] = None,
    ):
        """Update capture record in DB."""
        try:
            from database.db import SessionLocal
            from database.models import PacketCapture as PCModel
            db = SessionLocal()
            try:
                rec = db.query(PCModel).filter(PCModel.capture_id == capture_id).first()
                if rec:
                    if status is not None:
                        rec.status = status
                    if file_size is not None:
                        rec.file_size = file_size
                    if creds_found is not None:
                        rec.creds_found = creds_found
                    if packet_count is not None:
                        rec.packet_count = packet_count
                    if status == "stopped":
                        rec.stopped_at = datetime.utcnow()
                    db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.debug(f"_update_capture_db: {e}")


# Module-level singleton
packet_capture_engine = PacketCaptureEngine()
