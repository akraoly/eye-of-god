"""Utilitaires Docker — déploiement et gestion des containers C2."""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def get_docker_client():
    """Retourne un client Docker ou lève ImportError si docker-py absent."""
    try:
        import docker  # type: ignore
        return docker.from_env()
    except ImportError as exc:
        raise ImportError("pip install docker") from exc
    except Exception as exc:
        raise RuntimeError(f"Docker non disponible : {exc}") from exc


def container_running(name: str) -> bool:
    """Vérifie si un container tourne."""
    try:
        client = get_docker_client()
        c = client.containers.get(name)
        return c.status == "running"
    except Exception:
        return False


def start_container(
    name: str,
    image: str,
    ports: dict[str, Any] | None = None,
    environment: dict[str, str] | None = None,
    volumes: dict[str, Any] | None = None,
    detach: bool = True,
    remove: bool = False,
    network: str | None = None,
) -> str:
    """Démarrer un container Docker. Retourne le container ID."""
    client = get_docker_client()
    kwargs: dict[str, Any] = {
        "name":        name,
        "image":       image,
        "detach":      detach,
        "remove":      remove,
        "ports":       ports or {},
        "environment": environment or {},
        "volumes":     volumes or {},
    }
    if network:
        kwargs["network"] = network

    logger.info("Docker : démarrage container %s (%s)", name, image)
    container = client.containers.run(**kwargs)
    return container.id if hasattr(container, "id") else str(container)


def stop_container(name: str, timeout: int = 10) -> bool:
    """Arrêter un container."""
    try:
        client = get_docker_client()
        c = client.containers.get(name)
        c.stop(timeout=timeout)
        logger.info("Docker : container %s arrêté", name)
        return True
    except Exception as exc:
        logger.error("Docker stop %s : %s", name, exc)
        return False


def get_container_logs(name: str, tail: int = 100) -> str:
    """Lire les logs d'un container."""
    try:
        client = get_docker_client()
        c = client.containers.get(name)
        return c.logs(tail=tail).decode(errors="replace")
    except Exception as exc:
        return f"Erreur logs : {exc}"


def pull_image(image: str) -> bool:
    """Pull une image Docker."""
    try:
        client = get_docker_client()
        logger.info("Docker : pull %s", image)
        client.images.pull(image)
        return True
    except Exception as exc:
        logger.error("Docker pull %s : %s", image, exc)
        return False


# ── Presets Mythic ────────────────────────────────────────────────────────────

MYTHIC_COMPOSE_ENV = {
    "MYTHIC_SERVER_HOST": "127.0.0.1",
    "MYTHIC_SERVER_PORT": "7443",
    "POSTGRES_PASSWORD":  "mythic_password",
    "JWT_SECRET":         "mythic_jwt_secret_change_me",
    "RABBITMQ_PASSWORD":  "mythic_rabbitmq_password",
}


def start_mythic_stack(mythic_dir: str = "/opt/Mythic") -> dict[str, Any]:
    """Démarrer la stack Mythic via docker-compose."""
    import subprocess
    result = subprocess.run(
        ["python3", "mythic-cli", "start"],
        cwd=mythic_dir,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return {
        "success": result.returncode == 0,
        "stdout":  result.stdout,
        "stderr":  result.stderr,
    }
