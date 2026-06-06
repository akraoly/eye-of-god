"""
Cobalt Strike — External C2 Protocol complet.

Protocole External C2 (spec officielle) :
  Connexion TCP vers le port External C2 du Team Server (ex: 2222)
  Format des frames : [length:4 bytes big-endian][type:1 byte][data:variable]
  Types :
    0x00 FRAME_STAGE    — stage du beacon depuis le C2
    0x01 FRAME_TASK     — tâche pour le beacon (C2 → implant)
    0x02 FRAME_RESPONSE — réponse du beacon (implant → C2)
    0x03 FRAME_PING     — keepalive

Flow principal :
  1. Connexion TCP → teamserver External C2 port
  2. Demander le stage (FRAME_STAGE request avec beacon metadata)
  3. Transmettre le stage au beacon (via le canal de transport)
  4. Polling loop :
       - Beacon envoie ses sorties → FRAME_RESPONSE vers C2
       - C2 envoie les tâches → FRAME_TASK vers beacon

Aggressor Script / MSRPC :
  cs_connect(), agentscript(), aggressor_exec()
  via /api/v2 REST si teamserver_api activé (CS 4.7+)
"""
from __future__ import annotations

import asyncio
import logging
import struct
import uuid
from datetime import datetime
from typing import Any

from c2_manager.interfaces import (
    ExternalC2Interface, C2ConnectionError,
    FRAME_STAGE, FRAME_TASK, FRAME_RESPONSE, FRAME_PING,
    pack_frame, unpack_frame,
)
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


class CobaltStrikeC2(ExternalC2Interface):
    """
    Cobalt Strike — External C2 Protocol + REST API (CS 4.7+).

    Deux modes :
      mode "external_c2" — protocole External C2 raw TCP (défaut)
      mode "rest_api"    — API REST teamserver CS 4.7+ (config.extra["mode"]="rest_api")
    """

    CAPABILITIES = [
        "external_c2", "beacon_staging", "task_dispatch",
        "payload_generation", "aggressor_script",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._beacons: dict[str, dict[str, Any]] = {}   # beacon_id → metadata
        self._pending_tasks: asyncio.Queue[bytes] = asyncio.Queue()
        self._beacon_responses: asyncio.Queue[tuple[str, bytes]] = asyncio.Queue()
        self._mode = "external_c2"

    # ── Connexion ────────────────────────────────────────────────────────────

    async def connect(self, config: C2Config) -> bool:
        self._config = config
        self._mode   = config.extra.get("mode", "external_c2")

        if self._mode == "rest_api":
            return await self._connect_rest(config)
        return await self._connect_external_c2(config)

    async def _connect_external_c2(self, config: C2Config) -> bool:
        """Connexion TCP au port External C2 du teamserver."""
        logger.info(
            "CobaltStrike : connexion External C2 → %s:%d",
            config.host, config.port,
        )
        await self._tcp_connect(config.host, config.port)

        # Handshake : envoyer les métadonnées du canal externe
        channel_meta = config.extra.get("channel_name", "l-oeil-de-dieu").encode()
        await self._send_frame(FRAME_STAGE, channel_meta)

        # Lire la confirmation du teamserver
        ftype, data = await asyncio.wait_for(self._recv_frame(), timeout=10.0)
        if ftype == FRAME_STAGE:
            logger.info(
                "CobaltStrike : stage reçu (%d bytes), External C2 prêt",
                len(data),
            )
        else:
            logger.warning("CobaltStrike : frame inattendue type=0x%02x", ftype)

        # Démarrer la boucle de polling
        self._poll_task = asyncio.create_task(self._polling_loop())
        return True

    async def _connect_rest(self, config: C2Config) -> bool:
        """Connexion API REST CS 4.7+ via /api/v2."""
        try:
            import httpx  # type: ignore
        except ImportError as exc:
            raise C2ConnectionError("httpx requis pour le mode REST") from exc

        from c2_manager.interfaces import C2AuthError
        import httpx as _httpx

        scheme = "https" if config.ssl else "http"
        base_url = f"{scheme}://{config.host}:{config.port}"

        self._rest_client = _httpx.AsyncClient(base_url=base_url, verify=False, timeout=30.0)
        resp = await self._rest_client.post(
            "/api/v2/token",
            data={"username": config.username or "", "password": config.password or ""},
        )
        if resp.status_code not in (200, 201):
            raise C2AuthError(f"CS REST auth échouée [{resp.status_code}]")
        token = resp.json().get("access_token", "")
        self._rest_client.headers["Authorization"] = f"Bearer {token}"
        logger.info("CobaltStrike REST API connecté")
        return True

    # ── Boucle de polling External C2 ────────────────────────────────────────

    async def _polling_loop(self) -> None:
        """
        Boucle principale External C2 :
        - Lit les FRAME_RESPONSE des beacons
        - Envoie les FRAME_TASK depuis la queue
        """
        logger.info("CobaltStrike : polling loop démarrée")
        while True:
            try:
                # Envoyer les tâches en attente
                while not self._pending_tasks.empty():
                    task_frame = await self._pending_tasks.get()
                    await self._send_frame(FRAME_TASK, task_frame)
                    logger.debug("CobaltStrike : FRAME_TASK envoyé (%d bytes)", len(task_frame))

                # Keepalive
                await self._send_frame(FRAME_PING, b"\x00")

                # Lire les réponses (non-bloquant avec timeout court)
                try:
                    ftype, data = await asyncio.wait_for(self._recv_frame(), timeout=1.0)
                    if ftype == FRAME_RESPONSE:
                        beacon_id = self._extract_beacon_id(data)
                        await self._beacon_responses.put((beacon_id, data))
                        logger.debug(
                            "CobaltStrike : FRAME_RESPONSE beacon=%s (%d bytes)",
                            beacon_id, len(data),
                        )
                    elif ftype == FRAME_STAGE:
                        logger.debug("CobaltStrike : nouveau FRAME_STAGE reçu (%d bytes)", len(data))
                        self._register_beacon(data)
                except asyncio.TimeoutError:
                    pass

                await asyncio.sleep(0.1)

            except asyncio.CancelledError:
                logger.info("CobaltStrike : polling loop arrêtée")
                break
            except Exception as exc:
                logger.error("CobaltStrike polling error : %s", exc)
                self._status = C2Status.ERROR
                await asyncio.sleep(5.0)

    def _extract_beacon_id(self, data: bytes) -> str:
        """Extraire le beacon ID depuis un FRAME_RESPONSE (4 premiers bytes)."""
        if len(data) >= 4:
            bid = struct.unpack("<I", data[:4])[0]
            return str(bid)
        return "unknown"

    def _register_beacon(self, stage_data: bytes) -> None:
        """Enregistrer un nouveau beacon à partir du stage."""
        if len(stage_data) < 4:
            return
        bid = struct.unpack("<I", stage_data[:4])[0]
        beacon_id = str(bid)
        if beacon_id not in self._beacons:
            self._beacons[beacon_id] = {
                "id":         beacon_id,
                "first_seen": datetime.utcnow().isoformat(),
                "last_seen":  datetime.utcnow().isoformat(),
                "arch":       "x64" if len(stage_data) > 4 and stage_data[4] == 1 else "x86",
            }
            logger.info("CobaltStrike : nouveau beacon enregistré id=%s", beacon_id)

    # ── Listeners ────────────────────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        """
        CS : les listeners se créent via Aggressor Script ou l'API REST.
        En mode External C2, ce manager IS le listener.
        """
        listener_id = str(uuid.uuid4())
        protocol    = config.get("protocol", "external_c2")

        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            resp = await self._rest_client.post(
                "/api/v2/listeners",
                json={
                    "name":     config.get("name", f"cs-{protocol}"),
                    "type":     protocol,
                    "port":     config.get("bind_port", 80),
                    "host":     config.get("bind_host", "0.0.0.0"),
                },
            )
            data = resp.json()
            listener_id = str(data.get("id", listener_id))

        return Listener(
            id=listener_id,
            name=config.get("name", f"cs-{protocol}"),
            c2_type=self._config.c2_type,
            bind_host=config.get("bind_host", "0.0.0.0"),
            bind_port=int(config.get("bind_port", 80)),
            protocol=protocol,
            status="running",
        )

    async def remove_listener(self, listener_id: str) -> bool:
        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            try:
                resp = await self._rest_client.delete(f"/api/v2/listeners/{listener_id}")
                return resp.status_code in (200, 204)
            except Exception:
                return False
        return True

    async def list_listeners(self) -> list[Listener]:
        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            try:
                resp = await self._rest_client.get("/api/v2/listeners")
                items = resp.json().get("listeners", [])
                return [
                    Listener(
                        id=str(l.get("id", uuid.uuid4())),
                        name=l.get("name", ""),
                        c2_type=self._config.c2_type,
                        bind_host=l.get("host", "0.0.0.0"),
                        bind_port=int(l.get("port", 80)),
                        protocol=l.get("type", "http"),
                        status="running" if l.get("enabled") else "stopped",
                    )
                    for l in items
                ]
            except Exception:
                pass
        # External C2 : ce manager est le listener
        return [
            Listener(
                id="external_c2_main",
                name="External C2 Channel",
                c2_type=self._config.c2_type,
                bind_host=self._config.host,
                bind_port=self._config.port,
                protocol="external_c2",
                status="running" if self.is_connected else "stopped",
            )
        ]

    # ── Agents ───────────────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            try:
                resp = await self._rest_client.get("/api/v2/beacons")
                beacons = resp.json().get("beacons", [])
                return [self._beacon_to_implant(b) for b in beacons]
            except Exception:
                pass
        # External C2 : beacons enregistrés localement
        return [
            Implant(
                id=bid,
                name=f"beacon-{bid}",
                c2_type=self._config.c2_type,
                listener_id="external_c2_main",
                arch=meta.get("arch", "x64"),
                last_checkin=datetime.fromisoformat(meta.get("last_seen", datetime.utcnow().isoformat())),
                first_seen=datetime.fromisoformat(meta.get("first_seen", datetime.utcnow().isoformat())),
            )
            for bid, meta in self._beacons.items()
        ]

    def _beacon_to_implant(self, b: dict[str, Any]) -> Implant:
        return Implant(
            id=str(b.get("id", uuid.uuid4())),
            name=b.get("computer", str(b.get("id", ""))),
            c2_type=self._config.c2_type,
            listener_id=str(b.get("listener_id", "")),
            external_ip=b.get("external", ""),
            internal_ip=b.get("internal", ""),
            hostname=b.get("computer", ""),
            username=b.get("user", ""),
            os=b.get("os", ""),
            arch="x64" if b.get("arch") == 1 else "x86",
            pid=int(b.get("pid", 0)),
            process_name=b.get("process", ""),
            integrity="SYSTEM" if b.get("is_system") else ("ADMIN" if b.get("is_admin") else "USER"),
            last_checkin=datetime.fromisoformat(b.get("last", datetime.utcnow().isoformat())),
        )

    # ── Tâches ───────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        task_id = str(uuid.uuid4())
        full_cmd = (command + " " + " ".join(args or "")).strip()

        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            try:
                resp = await self._rest_client.post(
                    f"/api/v2/beacons/{agent_id}/tasks",
                    json={"command": full_cmd},
                )
                data = resp.json()
                return Task(
                    id=str(data.get("id", task_id)),
                    agent_id=agent_id,
                    c2_type=str(self._config.c2_type),
                    command=full_cmd,
                    args=args or [],
                    status="sent",
                )
            except Exception as exc:
                logger.error("CS REST task échoué : %s", exc)

        # External C2 : encoder la commande et l'enqueue
        beacon_id_int = int(agent_id) if agent_id.isdigit() else 0
        task_frame = struct.pack("<I", beacon_id_int) + full_cmd.encode()
        await self._pending_tasks.put(task_frame)
        logger.info("CobaltStrike : tâche enqueued pour beacon %s : %s", agent_id, full_cmd)

        return Task(
            id=task_id,
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=full_cmd,
            args=args or [],
            status="queued",
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        # Lire depuis la queue des réponses (non-bloquant)
        results = []
        while not self._beacon_responses.empty():
            try:
                bid, data = self._beacon_responses.get_nowait()
                results.append({"beacon_id": bid, "data_len": len(data), "preview": data[:64].hex()})
            except asyncio.QueueEmpty:
                break
        return {"task_id": task_id, "responses": results}

    # ── Payload (msfvenom-style via Aggressor) ───────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        """
        CS 4.7+ : POST /api/v2/artifacts pour générer un stager.
        Nécessite le mode rest_api.
        """
        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            arch_code = "x64" if config.arch == "x64" else "x86"
            format_map = {
                "exe":       "exe",
                "dll":       "dll",
                "ps1":       "powershell",
                "shellcode": "raw",
            }
            resp = await self._rest_client.post(
                "/api/v2/artifacts",
                json={
                    "listener_id": config.listener_id,
                    "arch":        arch_code,
                    "format":      format_map.get(config.format, "exe"),
                },
            )
            return resp.content if resp.status_code == 200 else b""

        logger.warning(
            "CobaltStrike generate_payload : mode rest_api requis pour la génération. "
            "Utilisez Aggressor Script pour générer des artifacts."
        )
        return b""

    async def get_status(self) -> C2Status:
        if self._mode == "rest_api" and hasattr(self, "_rest_client"):
            try:
                resp = await self._rest_client.get("/api/v2/beacons", timeout=5.0)
                return C2Status.CONNECTED if resp.status_code == 200 else C2Status.ERROR
            except Exception:
                return C2Status.ERROR
        # External C2 : check writer TCP
        return await super().get_status()

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
