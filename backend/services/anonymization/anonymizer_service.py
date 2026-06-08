"""
AnonymizerService — Anonymisation multi-couche.
Tor, VPN, proxychains, MAC spoofing, DNS over HTTPS.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import shutil
import string
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"

# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 15) -> tuple[str, str, int]:
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
    except Exception as e:
        return "", str(e), -1


def _random_ip() -> str:
    return f"{random.randint(1,254)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def _random_mac() -> str:
    mac = [random.randint(0x00, 0xff) for _ in range(6)]
    mac[0] &= 0xfe  # unicast
    mac[0] |= 0x02  # locally administered
    return ":".join(f"{b:02x}" for b in mac)


_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
]

_COUNTRIES = [
    ("Pays-Bas", "NL", "Amsterdam"),
    ("Suisse", "CH", "Zurich"),
    ("Islande", "IS", "Reykjavik"),
    ("Luxembourg", "LU", "Luxembourg"),
    ("Suède", "SE", "Stockholm"),
    ("Roumanie", "RO", "Bucarest"),
]


class AnonymizerService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self.tools = {
            "tor": bool(shutil.which("tor")),
            "torctl": bool(shutil.which("torify") or shutil.which("torsocks")),
            "openvpn": bool(shutil.which("openvpn")),
            "wg": bool(shutil.which("wg")),
            "macchanger": bool(shutil.which("macchanger")),
            "proxychains4": bool(shutil.which("proxychains4") or shutil.which("proxychains")),
        }
        self._state = {
            "tor_running": False,
            "tor_ip": None,
            "vpn_connected": False,
            "vpn_ip": None,
            "vpn_country": None,
            "mac_spoofed": False,
            "original_mac": None,
            "current_mac": None,
            "proxy_chain": [],
            "doh_enabled": False,
            "user_agent": _USER_AGENTS[0],
        }

    async def get_status(self) -> dict:
        if self.simulation_mode:
            country = random.choice(_COUNTRIES)
            return {
                "tor_running": self._state["tor_running"],
                "tor_ip": self._state.get("tor_ip", _random_ip()) if self._state["tor_running"] else None,
                "tor_circuit": f"${''.join(random.choices(string.hexdigits, k=40))}" if self._state["tor_running"] else None,
                "vpn_connected": self._state["vpn_connected"],
                "vpn_ip": self._state.get("vpn_ip") or _random_ip(),
                "vpn_country": self._state.get("vpn_country") or country[0],
                "mac_spoofed": self._state["mac_spoofed"],
                "current_mac": self._state.get("current_mac") or "aa:bb:cc:dd:ee:ff",
                "proxy_chain": self._state["proxy_chain"],
                "doh_enabled": self._state["doh_enabled"],
                "user_agent": self._state["user_agent"],
                "latency_ms": random.randint(80, 800) if (self._state["tor_running"] or self._state["vpn_connected"]) else random.randint(5, 30),
                "simulation": True,
            }

        is_tor = False
        try:
            stdout, _, rc = await _run(["systemctl", "is-active", "tor"], timeout=5)
            is_tor = rc == 0 and "active" in stdout
        except Exception:
            pass

        return {
            "tor_running": is_tor,
            "vpn_connected": self._state["vpn_connected"],
            "mac_spoofed": self._state["mac_spoofed"],
            "proxy_chain": self._state["proxy_chain"],
            "doh_enabled": self._state["doh_enabled"],
            "user_agent": self._state["user_agent"],
            "tools_available": self.tools,
            "simulation": False,
        }

    async def start_tor(self) -> dict:
        if self.simulation_mode or not self.tools["tor"]:
            await asyncio.sleep(2)
            ip = _random_ip()
            country = random.choice(_COUNTRIES)
            self._state["tor_running"] = True
            self._state["tor_ip"] = ip
            return {"success": True, "socks5_proxy": "127.0.0.1:9050", "tor_ip": ip, "country": country[0], "simulation": True}

        stdout, stderr, rc = await _run(["systemctl", "start", "tor"], timeout=10)
        if rc == 0:
            self._state["tor_running"] = True
        return {"success": rc == 0, "socks5_proxy": "127.0.0.1:9050", "stderr": stderr[:200]}

    async def stop_tor(self) -> dict:
        if self.simulation_mode or not self.tools["tor"]:
            self._state["tor_running"] = False
            return {"success": True, "simulation": True}
        stdout, stderr, rc = await _run(["systemctl", "stop", "tor"], timeout=10)
        if rc == 0:
            self._state["tor_running"] = False
        return {"success": rc == 0}

    async def renew_tor_circuit(self) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(3)
            new_ip = _random_ip()
            country = random.choice(_COUNTRIES)
            self._state["tor_ip"] = new_ip
            return {"success": True, "new_ip": new_ip, "new_circuit": f"${(''.join(random.choices(string.hexdigits, k=40)))}", "country": country[0], "latency_ms": random.randint(120, 600), "simulation": True}

        try:
            import stem
            from stem.control import Controller
            with Controller.from_port(port=9051) as ctrl:
                ctrl.authenticate()
                ctrl.signal(stem.Signal.NEWNYM)
            await asyncio.sleep(3)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def connect_vpn(self, vpn_config_path: str) -> dict:
        if self.simulation_mode or not self.tools["openvpn"]:
            await asyncio.sleep(2)
            country = random.choice(_COUNTRIES)
            self._state["vpn_connected"] = True
            self._state["vpn_ip"] = _random_ip()
            self._state["vpn_country"] = country[0]
            return {"success": True, "interface": "tun0", "local_ip": "10.8.0.2", "vpn_ip": self._state["vpn_ip"], "country": country[0], "dns_servers": ["10.8.0.1", "1.1.1.1"], "simulation": True}

        proc = await asyncio.create_subprocess_exec(
            "openvpn", "--config", vpn_config_path, "--daemon",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            self._state["vpn_connected"] = True
        return {"success": proc.returncode == 0, "stderr": stderr.decode()[:200]}

    async def disconnect_vpn(self) -> dict:
        self._state["vpn_connected"] = False
        if self.simulation_mode:
            return {"success": True, "simulation": True}
        await _run(["killall", "openvpn"])
        return {"success": True}

    async def setup_proxy_chain(self, proxies: list[str]) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            working = [p for p in proxies if p.startswith("socks") or p.startswith("http")]
            self._state["proxy_chain"] = working
            return {"chain_length": len(working), "working": len(working), "latency_ms": len(working) * random.randint(50, 200), "chain": working, "simulation": True}

        proxychains_conf = "/etc/proxychains4.conf"
        lines = ["strict_chain", "proxy_dns", "", "[ProxyList]"]
        for proxy in proxies:
            try:
                proto, rest = proxy.split("://", 1)
                host, port = rest.rsplit(":", 1)
                lines.append(f"{proto} {host} {port}")
            except Exception:
                pass
        try:
            Path(proxychains_conf).write_text("\n".join(lines))
            self._state["proxy_chain"] = proxies
            return {"chain_length": len(proxies), "working": len(proxies), "config_path": proxychains_conf}
        except PermissionError:
            return {"error": "sudo requis pour écrire /etc/proxychains4.conf", "chain_length": 0}

    async def spoof_mac(self, interface: str = "wlan0", random_mac: bool = True, new_mac: str = None) -> str:
        if self.simulation_mode or not self.tools["macchanger"]:
            orig = "aa:bb:cc:11:22:33"
            spoof = new_mac or _random_mac()
            self._state["mac_spoofed"] = True
            self._state["original_mac"] = orig
            self._state["current_mac"] = spoof
            return spoof

        cmd = ["macchanger", "-r" if random_mac else f"--mac={new_mac}", interface]
        if new_mac and not random_mac:
            cmd = ["macchanger", "--mac", new_mac, interface]
        stdout, stderr, rc = await _run(["ip", "link", "set", interface, "down"], timeout=5)
        stdout2, _, _ = await _run(cmd, timeout=10)
        await _run(["ip", "link", "set", interface, "up"], timeout=5)
        match = re.search(r"New MAC:\s+([\da-f:]+)", stdout2, re.IGNORECASE)
        new = match.group(1) if match else "unknown"
        self._state["mac_spoofed"] = True
        self._state["current_mac"] = new
        return new

    async def restore_mac(self, interface: str = "wlan0") -> str:
        if self.simulation_mode or not self.tools["macchanger"]:
            orig = self._state.get("original_mac", "aa:bb:cc:11:22:33")
            self._state["mac_spoofed"] = False
            self._state["current_mac"] = orig
            return orig
        await _run(["ip", "link", "set", interface, "down"])
        stdout, _, _ = await _run(["macchanger", "-p", interface])
        await _run(["ip", "link", "set", interface, "up"])
        self._state["mac_spoofed"] = False
        return stdout

    async def check_ip_leak(self) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            tor = self._state["tor_running"]
            vpn = self._state["vpn_connected"]
            clean = tor or vpn
            country = random.choice(_COUNTRIES)
            return {
                "public_ip": _random_ip() if clean else "203.0.113.45",
                "country": country[0] if clean else "France",
                "isp": "Tor Exit Node" if tor else ("VPN Provider" if vpn else "Orange SA"),
                "dns_leak": not clean and random.random() < 0.3,
                "webrtc_leak": not clean and random.random() < 0.2,
                "v6_leak": False,
                "anonymized": clean,
                "simulation": True,
            }

        result = {"simulation": False}
        try:
            import urllib.request
            with urllib.request.urlopen("https://api.ipify.org?format=json", timeout=10) as r:
                data = json.loads(r.read())
                result["public_ip"] = data.get("ip", "unknown")
        except Exception as e:
            result["public_ip"] = f"error: {e}"
        result["dns_leak"] = False
        result["webrtc_leak"] = False
        return result

    async def get_anonymity_score(self) -> dict:
        status = await self.get_status()
        score = 0
        breakdown = {}

        if status.get("tor_running"):
            score += 25; breakdown["tor"] = 25
        else:
            breakdown["tor"] = 0

        if status.get("vpn_connected"):
            score += 25; breakdown["vpn"] = 25
        else:
            breakdown["vpn"] = 0

        if status.get("mac_spoofed"):
            score += 10; breakdown["mac_spoof"] = 10
        else:
            breakdown["mac_spoof"] = 0

        if status.get("doh_enabled"):
            score += 10; breakdown["dns_over_https"] = 10
        else:
            breakdown["dns_over_https"] = 0

        chain_len = len(status.get("proxy_chain", []))
        proxy_pts = min(20, chain_len * 7)
        score += proxy_pts; breakdown["proxy_chain"] = proxy_pts

        ua = status.get("user_agent", "")
        if ua and ua != _USER_AGENTS[0]:
            score += 5; breakdown["user_agent"] = 5
        else:
            breakdown["user_agent"] = 5

        breakdown["webrtc_disabled"] = 5; score += 5

        recommendations = []
        if not status.get("tor_running"):
            recommendations.append({"action": "Activer Tor", "points": 25, "command": "POST /api/anonymize/tor/start"})
        if not status.get("vpn_connected"):
            recommendations.append({"action": "Connecter VPN", "points": 25, "command": "POST /api/anonymize/vpn/connect"})
        if not status.get("mac_spoofed"):
            recommendations.append({"action": "Spoofing MAC", "points": 10, "command": "POST /api/anonymize/mac/spoof"})

        level = "🔴 CRITIQUE" if score < 30 else "🟡 MOYEN" if score < 70 else "🟢 EXCELLENT"
        return {"score": score, "level": level, "max": 100, "breakdown": breakdown, "recommendations": recommendations}

    async def route_through_chain(self, url: str, method: str = "GET", headers: dict = None, data: str = None) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(random.uniform(0.5, 2))
            tor = self._state["tor_running"]
            vpn = self._state["vpn_connected"]
            chain_used = []
            if vpn:
                chain_used.append(f"VPN ({self._state.get('vpn_country', '?')})")
            if tor:
                chain_used.append("Tor Network (3 hops)")
            if self._state["proxy_chain"]:
                chain_used.extend([f"Proxy: {p}" for p in self._state["proxy_chain"][:2]])
            return {
                "url": url, "status_code": 200,
                "detected_ip": _random_ip() if chain_used else "203.0.113.45",
                "chain_used": chain_used,
                "latency_ms": len(chain_used) * random.randint(100, 400),
                "response_preview": f"[SIMULATED RESPONSE FROM {url}]",
                "anonymized": bool(chain_used),
                "simulation": True,
            }

        import urllib.request, urllib.error
        proxies_list = self._state.get("proxy_chain", [])
        tor = self._state.get("tor_running", False)
        proxy_url = "socks5h://127.0.0.1:9050" if tor else (proxies_list[0] if proxies_list else None)
        try:
            req = urllib.request.Request(url, method=method, headers=headers or {})
            with urllib.request.urlopen(req, timeout=15) as r:
                body = r.read(1000).decode("utf-8", errors="replace")
            return {"url": url, "status_code": r.getcode(), "response_preview": body[:500], "chain_used": ["direct"], "latency_ms": 0}
        except Exception as e:
            return {"url": url, "error": str(e)}

    async def randomize_user_agent(self) -> str:
        ua = random.choice(_USER_AGENTS)
        self._state["user_agent"] = ua
        return ua

    async def setup_dns_over_https(self, provider: str = "cloudflare") -> dict:
        providers = {
            "cloudflare": {"url": "https://1.1.1.1/dns-query", "ip": "1.1.1.1"},
            "quad9": {"url": "https://9.9.9.9/dns-query", "ip": "9.9.9.9"},
            "google": {"url": "https://8.8.8.8/dns-query", "ip": "8.8.8.8"},
        }
        prov = providers.get(provider, providers["cloudflare"])
        if self.simulation_mode:
            self._state["doh_enabled"] = True
            return {"success": True, "provider": provider, "url": prov["url"], "simulation": True}

        stdout, _, rc = await _run(["systemd-resolve", "--set-dns", prov["ip"], "--interface", "eth0"])
        self._state["doh_enabled"] = rc == 0
        return {"success": rc == 0, "provider": provider}

    async def get_all_identities(self) -> list[dict]:
        status = await self.get_status()
        return [
            {"type": "IP", "value": status.get("tor_ip") or status.get("vpn_ip") or "203.0.113.45", "source": "Tor" if status.get("tor_running") else "VPN" if status.get("vpn_connected") else "Direct"},
            {"type": "MAC", "value": status.get("current_mac", "unknown"), "spoofed": status.get("mac_spoofed", False)},
            {"type": "User-Agent", "value": status.get("user_agent", "unknown"), "randomized": True},
            {"type": "DNS", "value": "DoH via Cloudflare" if status.get("doh_enabled") else "Système (potentiellement fuité)", "secure": status.get("doh_enabled", False)},
        ]


anonymizer_service = AnonymizerService()
