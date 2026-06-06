"""
Mythic C2 — Intégration GraphQL + WebSocket complète.

Protocole : GraphQL (Hasura, port 443 par défaut) + WebSocket subscriptions
Auth      : JWT via mutation userLogin
Stacks    : Docker containers (Hasura + Postgres + RabbitMQ + agents)

Méthodes disponibles :
  - userLogin mutation → JWT
  - Queries : callback_stream, task_stream, payload_stream
  - Mutations : createPayload, createTask, createListener
  - Subscriptions : callbackFeed, taskFeed (WebSocket)

Doc Mythic GraphQL : https://docs.mythic-c2.net/operational-pieces/graphql-api
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

import httpx

from c2_manager.interfaces import RestC2Interface, C2AuthError, C2ConnectionError
from c2_manager.models import C2Config, C2Status, Listener, Implant, Task, PayloadConfig

logger = logging.getLogger(__name__)


_Q_LOGIN = """
mutation Login($username: String!, $password: String!) {
  userLogin(input: {username: $username, password: $password}) {
    access_token
    refresh_token
    user {
      id
      username
      current_operation { id name }
    }
  }
}
"""

_Q_CALLBACKS = """
query GetCallbacks {
  callback(where: {active: {_eq: true}}) {
    id
    agent_callback_id
    init_callback
    last_checkin
    user
    host
    pid
    ip
    os
    architecture
    integrity_level
    process_name
    registered_payload { payloadtype { name } }
    callbackc2profiles { c2profile { name } }
  }
}
"""

_Q_LISTENERS = """
query GetC2Profiles {
  c2profile(where: {running: {_eq: true}}) {
    id
    name
    description
    running
    is_p2p
    container_name
  }
}
"""

_M_CREATE_TASK = """
mutation CreateTask($callbackId: Int!, $command: String!, $params: String!) {
  createTask(input: {
    callback_id: $callbackId,
    command: $command,
    params: $params
  }) {
    id
    status
    timestamp
  }
}
"""

_Q_TASK_RESULT = """
query GetTaskResult($taskId: Int!) {
  task(where: {id: {_eq: $taskId}}) {
    id
    status
    completed
    operator { username }
    responses { id response timestamp }
    command
    params
  }
}
"""

_M_CREATE_PAYLOAD = """
mutation CreatePayload($payload: PayloadInput!) {
  createPayload(payloadDefinition: $payload) {
    uuid
    build_phase
    file_id
    tag
  }
}
"""


class MythicC2(RestC2Interface):
    """Intégration Mythic via GraphQL Hasura + WebSocket."""

    CAPABILITIES = [
        "list_agents", "send_task", "create_listener", "generate_payload",
        "file_download", "file_upload", "screenshot", "keylog",
        "port_forward", "socks5", "token_manipulation",
    ]

    def __init__(self) -> None:
        super().__init__()
        self._operation_id: int | None = None
        self._ws_task: asyncio.Task | None = None
        self._agent_cache: dict[str, Implant] = {}

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _authenticate(self, config: C2Config) -> str:
        """Login Mythic via mutation GraphQL."""
        gql_endpoint = config.extra.get("graphql_url", f"{config.base_url}/graphql")
        async with httpx.AsyncClient(verify=False, timeout=15.0) as client:
            resp = await client.post(
                gql_endpoint,
                json={
                    "query": _Q_LOGIN,
                    "variables": {
                        "username": config.username or "mythic_admin",
                        "password": config.password or "",
                    },
                },
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                raise C2AuthError(
                    f"Mythic login échoué [{resp.status_code}]: {resp.text[:200]}"
                )
            data = resp.json()
            errors = data.get("errors")
            if errors:
                raise C2AuthError(f"Mythic GraphQL login erreur : {errors}")

            login_data = data["data"]["userLogin"]
            token = login_data.get("access_token")
            if not token:
                raise C2AuthError("Token Mythic absent")

            user = login_data.get("user", {})
            op = user.get("current_operation")
            if op:
                self._operation_id = op.get("id")
                logger.info("Mythic : opération courante = %s (id=%s)", op.get("name"), op.get("id"))

            return token

    async def _gql(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        """Exécuter une requête GraphQL."""
        self._require_connected()
        gql_endpoint = self._config.extra.get(
            "graphql_url", f"{self._config.base_url}/graphql"
        )
        resp = await self._client.post(
            gql_endpoint,
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()
        errors = data.get("errors")
        if errors:
            raise C2ConnectionError(f"Mythic GraphQL erreur : {errors}")
        return data.get("data", {})

    async def get_status(self) -> C2Status:
        if not self._client:
            return C2Status.DISCONNECTED
        try:
            data = await self._gql("query { callback(limit: 1) { id } }")
            return C2Status.CONNECTED
        except Exception:
            return C2Status.ERROR

    # ── Listeners (C2 Profiles) ───────────────────────────────────────────────

    async def create_listener(self, config: dict[str, Any]) -> Listener:
        """
        Dans Mythic, les 'listeners' sont des C2 Profiles (http, smb, tcp…).
        La création se fait via l'API REST /api/v1.4/c2profiles/
        ou via les containers Docker.
        Cette méthode démarre le container C2 profile via l'API.
        """
        self._require_connected()
        profile_name = config.get("profile", config.get("protocol", "http"))
        port         = int(config.get("bind_port", 443))

        resp = await self._client.post(
            "/api/v1.4/c2profiles/start",
            json={"c2_profile_name": profile_name},
        )
        # Mythic retourne 200 même si déjà démarré
        data = resp.json() if resp.content else {}

        return Listener(
            id=str(data.get("id", uuid.uuid4())),
            name=profile_name,
            c2_type=self._config.c2_type,
            bind_host=config.get("bind_host", "0.0.0.0"),
            bind_port=port,
            protocol=profile_name,
            status="running",
        )

    async def remove_listener(self, listener_id: str) -> bool:
        self._require_connected()
        try:
            await self._client.post(
                "/api/v1.4/c2profiles/stop",
                json={"c2_profile_name": listener_id},
            )
            return True
        except Exception as exc:
            logger.error("Mythic stop C2 profile échoué : %s", exc)
            return False

    async def list_listeners(self) -> list[Listener]:
        self._require_connected()
        data = await self._gql(_Q_LISTENERS)
        return [
            Listener(
                id=str(p.get("id", uuid.uuid4())),
                name=p.get("name", ""),
                c2_type=self._config.c2_type,
                bind_host="0.0.0.0",
                bind_port=443,
                protocol=p.get("name", "http"),
                status="running" if p.get("running") else "stopped",
            )
            for p in data.get("c2profile", [])
        ]

    # ── Agents (Callbacks) ────────────────────────────────────────────────────

    async def list_agents(self) -> list[Implant]:
        self._require_connected()
        data = await self._gql(_Q_CALLBACKS)

        agents = []
        for cb in data.get("callback", []):
            checkin = cb.get("last_checkin", "")
            try:
                checkin_dt = datetime.fromisoformat(checkin.replace("Z", "+00:00"))
            except (ValueError, TypeError, AttributeError):
                checkin_dt = datetime.utcnow()

            first = cb.get("init_callback", "")
            try:
                first_dt = datetime.fromisoformat(first.replace("Z", "+00:00"))
            except (ValueError, TypeError, AttributeError):
                first_dt = datetime.utcnow()

            c2_profiles = [
                c["c2profile"]["name"]
                for c in cb.get("callbackc2profiles", [])
                if c.get("c2profile")
            ]
            agent_type = ""
            if cb.get("registered_payload", {}).get("payloadtype"):
                agent_type = cb["registered_payload"]["payloadtype"]["name"]

            integrity_map = {4: "SYSTEM", 3: "ADMIN", 2: "USER", 1: "LOW"}
            integrity = integrity_map.get(cb.get("integrity_level", 2), "USER")

            agents.append(Implant(
                id=str(cb.get("id")),
                name=cb.get("agent_callback_id", str(cb.get("id"))),
                c2_type=self._config.c2_type,
                listener_id=",".join(c2_profiles),
                external_ip=cb.get("ip", ""),
                internal_ip="",
                hostname=cb.get("host", ""),
                username=cb.get("user", ""),
                os=cb.get("os", ""),
                arch=cb.get("architecture", ""),
                pid=int(cb.get("pid", 0)),
                process_name=cb.get("process_name", ""),
                integrity=integrity,
                last_checkin=checkin_dt,
                first_seen=first_dt,
                active=True,
            ))

        self._agent_cache = {a.id: a for a in agents}
        return agents

    # ── Tâches ───────────────────────────────────────────────────────────────

    async def send_task(
        self,
        agent_id: str,
        command: str,
        args: list[str] | None = None,
    ) -> Task:
        self._require_connected()
        params = " ".join(args) if args else ""
        if command == "shell":
            params_data = json.dumps({"command": params})
        else:
            params_data = params or "{}"

        data = await self._gql(
            _M_CREATE_TASK,
            variables={
                "callbackId": int(agent_id),
                "command":    command,
                "params":     params_data,
            },
        )
        task_data = data.get("createTask", {})
        return Task(
            id=str(task_data.get("id", uuid.uuid4())),
            agent_id=agent_id,
            c2_type=str(self._config.c2_type),
            command=command,
            args=args or [],
            status=task_data.get("status", "sent"),
        )

    async def get_task_result(self, task_id: str) -> dict[str, Any]:
        self._require_connected()
        data = await self._gql(
            _Q_TASK_RESULT,
            variables={"taskId": int(task_id)},
        )
        tasks = data.get("task", [])
        if not tasks:
            return {"task_id": task_id, "status": "not_found"}
        t = tasks[0]
        responses = t.get("responses", [])
        output = "\n".join(
            r.get("response", "") for r in responses if r.get("response")
        )
        return {
            "task_id": task_id,
            "status":  "completed" if t.get("completed") else t.get("status"),
            "result":  output,
            "command": t.get("command"),
            "params":  t.get("params"),
        }

    # ── Payload ──────────────────────────────────────────────────────────────

    async def generate_payload(self, config: PayloadConfig) -> bytes:
        self._require_connected()
        payload_type = config.extra.get("payload_type", "apollo")
        c2_profile   = config.listener_id or "http"

        os_map = {"windows": "Windows", "linux": "Linux", "macos": "macOS"}
        arch_map = {"x64": "x64", "x86": "x86"}

        payload_def = {
            "payload_type": payload_type,
            "selected_os":  os_map.get(config.os, "Windows"),
            "filename":     f"{config.name}.{config.format}",
            "tag":          config.name,
            "c2_profiles": [{
                "c2_profile": c2_profile,
                "c2_profile_parameters": config.extra.get("c2_params", {}),
            }],
            "build_parameters": [{
                "name":  "architecture",
                "value": arch_map.get(config.arch, "x64"),
            }],
            "commands": config.extra.get("commands", []),
        }

        data = await self._gql(_M_CREATE_PAYLOAD, variables={"payload": payload_def})
        payload_data = data.get("createPayload", {})
        file_id = payload_data.get("file_id")

        if not file_id:
            logger.warning("Mythic createPayload : file_id absent, build en cours ?")
            return b""

        # Télécharger le payload généré
        resp = await self._client.get(f"/api/v1.4/files/download/{file_id}")
        if resp.status_code == 200:
            return resp.content
        logger.error("Mythic download payload échoué [%d]", resp.status_code)
        return b""

    # ── WebSocket subscription (real-time agent events) ───────────────────────

    async def start_callback_stream(self, callback: Any = None) -> None:
        """Démarre une subscription WebSocket pour les nouveaux callbacks."""
        try:
            import websockets  # type: ignore
        except ImportError:
            logger.warning("websockets non installé (pip install websockets)")
            return

        ws_url = self._config.ws_url + "/graphql"
        token  = self._token

        async def _listen() -> None:
            subscription = """
            subscription CallbackFeed {
              callback_stream(
                batch_size: 10,
                cursor: {initial_value: {last_checkin: "now()"}}
              ) {
                id agent_callback_id host user os last_checkin active
              }
            }
            """
            headers = {"Authorization": f"Bearer {token}"}
            async with websockets.connect(
                ws_url,
                extra_headers=headers,
                subprotocols=["graphql-ws"],
            ) as ws:
                await ws.send(json.dumps({"type": "connection_init", "payload": {"headers": headers}}))
                await ws.send(json.dumps({"id": "1", "type": "start", "payload": {"query": subscription}}))
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("type") == "data" and callback:
                        await callback(data["payload"]["data"]["callback_stream"])

        self._ws_task = asyncio.create_task(_listen())
        logger.info("Mythic : WebSocket subscription démarrée")

    async def get_capabilities(self) -> list[str]:
        return self.CAPABILITIES
