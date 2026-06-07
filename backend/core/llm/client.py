from __future__ import annotations

import asyncio
import re
import subprocess
from typing import AsyncGenerator, List, Optional

import anthropic
from app.config import settings

try:
    from core.tools.logger import get_logger
    logger = get_logger("llm.client")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


# ── Définition de l'outil terminal ───────────────────────────────────────────

TERMINAL_TOOL: dict = {
    "name": "terminal",
    "description": (
        "Exécute une commande bash sur la machine locale (Kali Linux) et retourne "
        "stdout + stderr. Utilise cet outil pour explorer le système, analyser des "
        "fichiers, lancer des diagnostics réseau/sécurité, faire du pentesting local, "
        "lire des logs, vérifier des services, etc. "
        "La commande s'exécute dans le répertoire courant de l'application."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "La commande bash à exécuter",
            }
        },
        "required": ["command"],
    },
}

# Commandes qui ne doivent jamais s'exécuter (protection minimale)
_BLOCKED: list[str] = [
    r"\brm\s+(?:-\S+\s+)*/(?:\s|$|&&|\|)",      # rm -rf / (racine uniquement)
    r"\bdd\s+.*of=/dev/[shx]d",                  # dd vers disque brut
    r":\s*\(\s*\)\s*\{.*\}\s*;",                  # fork bomb
    r"\bmkfs\b",                                  # formater un FS
    r">\s*/dev/[shx]d[a-z]",                      # écriture disque brut
    r"\bshutdown\b|\breboot\b|\bpoweroff\b",      # éteindre la machine
]
_BLOCKED_RE = [re.compile(p, re.IGNORECASE) for p in _BLOCKED]

_MAX_ITER    = 10    # iterations max de la boucle tool-use
_CMD_TIMEOUT = 30    # secondes par commande
_OUTPUT_MAX  = 8000  # octets max retournés à Claude


# ── Exécution subprocess ─────────────────────────────────────────────────────

def _run_command(command: str) -> str:
    """
    Exécute une commande bash locale et retourne stdout+stderr tronqués.
    Bloque les patterns dangereux irréversibles.
    """
    for pat in _BLOCKED_RE:
        if pat.search(command):
            return f"[BLOQUÉ] Commande refusée par politique de sécurité : {command!r}"

    logger.info("terminal: %s", command)
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_CMD_TIMEOUT,
        )
        out    = result.stdout or ""
        err    = result.stderr or ""
        code   = result.returncode
        combined = ""
        if out:
            combined += out
        if err:
            combined += ("\n[stderr]\n" if out else "") + err
        if not combined:
            combined = f"[exit {code}]"
        # Tronquer si trop long
        if len(combined) > _OUTPUT_MAX:
            combined = combined[:_OUTPUT_MAX] + f"\n[... tronqué — {len(combined)} octets total]"
        return combined
    except subprocess.TimeoutExpired:
        return f"[TIMEOUT] La commande n'a pas répondu en {_CMD_TIMEOUT}s."
    except Exception as e:
        return f"[ERREUR] {e}"


# ── Client LLM ───────────────────────────────────────────────────────────────

class LLMClient:
    def __init__(self):
        self._client: Optional[anthropic.AsyncAnthropic] = None

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        return self._client

    # ── Méthodes de base (inchangées, utilisées par AEGIS/memory/etc.) ────────

    async def complete(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        response = await self.client.messages.create(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
            system=system or "",
            messages=messages,
        )
        return response.content[0].text

    async def stream(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        async with self.client.messages.stream(
            model=settings.CLAUDE_MODEL,
            max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
            system=system or "",
            messages=messages,
        ) as s:
            async for text in s.text_stream:
                yield text

    # ── Tool use — boucle agentic avec terminal ────────────────────────────────

    async def complete_with_tools(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[str, list[dict]]:
        """
        Appelle Claude avec l'outil terminal et gère la boucle tool-use
        jusqu'à stop_reason == 'end_turn'.

        Retourne (texte_final, log_des_appels_outils).
        log_des_appels_outils : [{ "command": str, "output": str }, ...]
        """
        msgs       = list(messages)   # copie locale — on va l'enrichir
        tool_log   : list[dict] = []
        final_text : str        = ""

        for iteration in range(_MAX_ITER):
            response = await self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
                system=system or "",
                messages=msgs,
                tools=[TERMINAL_TOOL],
            )

            # Collecter le texte partiel de cette itération
            for block in response.content:
                if block.type == "text":
                    final_text = block.text   # on garde la dernière réponse texte

            # Fin de la conversation
            if response.stop_reason == "end_turn":
                break

            # Traiter les appels d'outils
            if response.stop_reason == "tool_use":
                # Ajouter le message assistant (avec les blocs tool_use)
                msgs.append({
                    "role": "assistant",
                    "content": response.content,   # liste de blocs SDK
                })

                # Exécuter chaque outil demandé et construire les tool_results
                tool_results: list[dict] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    command = block.input.get("command", "")
                    output  = await asyncio.get_event_loop().run_in_executor(
                        None, _run_command, command
                    )
                    logger.debug("tool[%s] → %d chars", command[:60], len(output))
                    tool_log.append({"command": command, "output": output})
                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     output,
                    })

                # Renvoyer les résultats à Claude
                msgs.append({
                    "role": "user",
                    "content": tool_results,
                })
                continue

            # stop_reason inattendu (max_tokens, etc.)
            logger.warning("tool loop: stop_reason inattendu '%s'", response.stop_reason)
            break

        else:
            logger.warning("tool loop: limite d'itérations atteinte (%d)", _MAX_ITER)

        return final_text, tool_log

    async def stream_with_tools(
        self,
        messages: List[dict],
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Version streaming : effectue d'abord la boucle tool-use (non-streaming),
        yield les blocs terminaux au fur et à mesure, puis yield la réponse finale.
        Cela permet au frontend SSE de recevoir les sorties en temps réel.
        """
        msgs       = list(messages)
        final_text : str = ""

        for iteration in range(_MAX_ITER):
            response = await self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=max_tokens or settings.CLAUDE_MAX_TOKENS,
                system=system or "",
                messages=msgs,
                tools=[TERMINAL_TOOL],
            )

            for block in response.content:
                if block.type == "text":
                    final_text = block.text

            if response.stop_reason == "end_turn":
                break

            if response.stop_reason == "tool_use":
                msgs.append({
                    "role": "assistant",
                    "content": response.content,
                })

                tool_results: list[dict] = []
                for block in response.content:
                    if block.type != "tool_use":
                        continue
                    command = block.input.get("command", "")

                    # Yield l'annonce d'exécution vers le client SSE
                    yield f"\n```bash\n$ {command}\n"

                    output = await asyncio.get_event_loop().run_in_executor(
                        None, _run_command, command
                    )

                    # Yield la sortie et fermer le bloc
                    yield output + "\n```\n"

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,
                        "content":     output,
                    })

                msgs.append({"role": "user", "content": tool_results})
                continue

            logger.warning("stream tool loop: stop_reason inattendu '%s'", response.stop_reason)
            break

        else:
            logger.warning("stream tool loop: limite d'itérations atteinte")

        # Yield la réponse textuelle finale
        if final_text:
            yield "\n" + final_text


llm_client = LLMClient()
