#!/usr/bin/env python3
"""
ONVIF Camera Scanner
WS-Discovery multicast + TCP port probing to find IP cameras on the LAN.

Usage:   python3 onvif_scan.py <subnet> [timeout]
Example: python3 onvif_scan.py 192.168.1.0/24
         python3 onvif_scan.py 192.168.1.0/24 3
"""

import sys
import socket
import ipaddress
import struct
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    import urllib3
    urllib3.disable_warnings()
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ONVIF / camera common ports
CAMERA_PORTS = [80, 443, 554, 8080, 8443, 8888, 37777]

# WS-Discovery multicast
WS_DISC_ADDR  = "239.255.255.250"
WS_DISC_PORT  = 3702
WS_DISC_PROBE = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"'
    ' xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing"'
    ' xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery"'
    ' xmlns:dn="http://www.onvif.org/ver10/network/wsdl">'
    '<soap:Header>'
    '<wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>'
    '<wsa:MessageID>urn:uuid:{msg_id}</wsa:MessageID>'
    '<wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>'
    '</soap:Header>'
    '<soap:Body><wsd:Probe>'
    '<wsd:Types>dn:NetworkVideoTransmitter</wsd:Types>'
    '</wsd:Probe></soap:Body></soap:Envelope>'
)

# Known camera HTTP banners / header fragments
CAMERA_SIGNATURES = [
    "hikvision", "dahua", "axis", "foscam", "reolink", "amcrest",
    "vivotek", "hanwha", "bosch", "pelco", "uniview", "nvr", "ipc",
    "onvif", "webcam", "camera", "rtsp", "h264", "video server",
]


def ws_discovery(timeout: float = 3.0) -> list[str]:
    """Broadcast WS-Discovery probe and collect responding IPs."""
    found = []
    probe = WS_DISC_PROBE.format(msg_id=str(uuid.uuid4()))

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)

    try:
        sock.sendto(probe.encode(), (WS_DISC_ADDR, WS_DISC_PORT))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, addr = sock.recvfrom(65535)
                ip = addr[0]
                if ip not in found:
                    found.append(ip)
                    print(f"[+] WS-Discovery response from {ip}")
            except socket.timeout:
                break
    except OSError as e:
        print(f"[!] WS-Discovery unavailable: {e}")
    finally:
        sock.close()

    return found


def check_port(ip: str, port: int, timeout: float) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def fingerprint(ip: str, port: int = 80, timeout: float = 5.0) -> dict:
    """HTTP banner grab to identify camera model."""
    info = {"ip": ip, "port": port, "manufacturer": "unknown", "model": "unknown",
            "server": "", "authenticated": False, "rtsp_url": ""}

    if not HAS_REQUESTS:
        return info

    for scheme in ("http", "https"):
        url = f"{scheme}://{ip}:{port}/"
        try:
            r = requests.get(url, timeout=timeout, verify=False,
                             allow_redirects=True)
            server  = r.headers.get("Server", "")
            content = r.text[:4000].lower()
            info["server"]  = server
            info["http_status"] = r.status_code

            low_server = server.lower()
            for sig in CAMERA_SIGNATURES:
                if sig in low_server or sig in content:
                    info["manufacturer"] = sig.capitalize()
                    break

            if "hikvision" in low_server or "hikvision" in content:
                info["manufacturer"] = "Hikvision"
                info["rtsp_url"]     = f"rtsp://{ip}:554/Streaming/Channels/101"
            elif "dahua" in low_server or "dahua" in content:
                info["manufacturer"] = "Dahua"
                info["rtsp_url"]     = f"rtsp://{ip}:554/cam/realmonitor?channel=1&subtype=0"
            elif "axis" in low_server or "axis" in content:
                info["manufacturer"] = "Axis"
                info["rtsp_url"]     = f"rtsp://{ip}:554/axis-media/media.amp"
            elif "foscam" in low_server or "foscam" in content:
                info["manufacturer"] = "Foscam"
                info["rtsp_url"]     = f"rtsp://{ip}:554/videoMain"

            break
        except Exception:
            continue

    return info


def scan_host(ip: str, timeout: float) -> dict | None:
    """Return camera info if the host looks like a camera, else None."""
    open_ports = [p for p in CAMERA_PORTS if check_port(ip, p, timeout)]
    if not open_ports:
        return None

    http_port = next((p for p in [80, 8080, 443, 8443] if p in open_ports), open_ports[0])
    info = fingerprint(ip, http_port, timeout)
    info["open_ports"] = open_ports

    if info["manufacturer"] == "unknown" and not any(
        p in open_ports for p in [554, 37777]
    ):
        return None  # Likely not a camera

    return info


def scan_network(subnet: str, timeout: float = 2.0, max_workers: int = 64) -> list[dict]:
    """Scan entire subnet for IP cameras."""
    print(f"[*] Scanning {subnet} (timeout={timeout}s, workers={max_workers})")

    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError as e:
        print(f"[-] Invalid subnet: {e}")
        sys.exit(1)

    hosts = [str(h) for h in net.hosts()]
    print(f"[*] {len(hosts)} host(s) to probe…\n")

    cameras = []
    disc = ws_discovery(timeout)
    for ip in disc:
        info = fingerprint(ip, 80, timeout)
        info["open_ports"]  = [p for p in CAMERA_PORTS if check_port(ip, p, 0.5)]
        info["discovered_via"] = "ws-discovery"
        cameras.append(info)

    already = {c["ip"] for c in cameras}

    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futs = {ex.submit(scan_host, ip, timeout): ip
                for ip in hosts if ip not in already}
        done = 0
        for fut in as_completed(futs):
            done += 1
            result = fut.result()
            if result:
                result["discovered_via"] = "tcp-scan"
                cameras.append(result)
                print(f"[+] Camera found: {result['ip']}:{result['open_ports'][0]}"
                      f"  [{result['manufacturer']}]")
            if done % 50 == 0:
                print(f"[*] Progress: {done}/{len(futs)} hosts scanned…")

    return cameras


def print_summary(cameras: list[dict]):
    print(f"\n{'='*60}")
    print(f"  FOUND {len(cameras)} CAMERA(S)")
    print(f"{'='*60}")
    for cam in cameras:
        print(f"\n  IP            : {cam['ip']}")
        print(f"  Manufacturer  : {cam['manufacturer']}")
        print(f"  Open ports    : {cam.get('open_ports', [])}")
        print(f"  Server        : {cam.get('server', '—')}")
        if cam.get("rtsp_url"):
            print(f"  RTSP URL      : {cam['rtsp_url']}")
        print(f"  Discovery     : {cam.get('discovered_via', '—')}")


def main():
    if len(sys.argv) < 2:
        print(f"Usage:   {sys.argv[0]} <subnet> [timeout]")
        print(f"Example: {sys.argv[0]} 192.168.1.0/24")
        print(f"         {sys.argv[0]} 10.0.0.0/16 1")
        sys.exit(1)

    subnet  = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0

    cameras = scan_network(subnet, timeout)
    print_summary(cameras)


if __name__ == "__main__":
    main()
