"""GrpcC2Interface — base pour les C2 gRPC (Sliver, DeimosC2)."""
from __future__ import annotations

import json
import logging
import ssl
from pathlib import Path
from typing import Any

from c2_manager.interfaces.base import BaseC2Interface, C2ConnectionError
from c2_manager.models import C2Config, C2Status

logger = logging.getLogger(__name__)


class GrpcC2Interface(BaseC2Interface):
    """
    Base pour les C2 gRPC avec mTLS.
    Charge le certificat client, crée un channel sécurisé.
    Attend que grpcio soit installé.
    """

    def __init__(self) -> None:
        super().__init__()
        self._channel: Any = None
        self._stub:    Any = None

    def _load_operator_config(self, cfg_path: str) -> dict[str, Any]:
        """
        Charge un fichier .cfg Sliver (JSON) contenant :
        lhost, lport, ca_certificate, certificate, private_key, token, operator
        """
        path = Path(cfg_path)
        if not path.exists():
            raise FileNotFoundError(f"Operator config introuvable : {cfg_path}")
        with path.open() as f:
            return json.load(f)

    def _build_grpc_channel(
        self,
        host: str,
        port: int,
        ca_cert: bytes,
        client_cert: bytes,
        client_key: bytes,
    ) -> Any:
        """Crée un channel gRPC sécurisé (mTLS)."""
        try:
            import grpc  # type: ignore
        except ImportError as exc:
            raise C2ConnectionError(
                "grpcio non installé. Faites : pip install grpcio grpcio-tools"
            ) from exc

        credentials = grpc.ssl_channel_credentials(
            root_certificates=ca_cert,
            private_key=client_key,
            certificate_chain=client_cert,
        )
        return grpc.aio.secure_channel(f"{host}:{port}", credentials)

    async def disconnect(self) -> None:
        await self.stop_healthcheck()
        if self._channel:
            try:
                await self._channel.close()
            except Exception:
                pass
            self._channel = None
        self._stub = None
        self._status = C2Status.DISCONNECTED

    async def get_status(self) -> C2Status:
        if not self._channel or not self._stub:
            return C2Status.DISCONNECTED
        try:
            import grpc  # type: ignore
            state = self._channel.get_state(try_to_connect=True)
            if state == grpc.ChannelConnectivity.READY:
                return C2Status.CONNECTED
            if state == grpc.ChannelConnectivity.TRANSIENT_FAILURE:
                return C2Status.ERROR
            return C2Status.CONNECTING
        except Exception:
            return C2Status.ERROR
