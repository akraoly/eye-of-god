"""
Orchestrateur central — Pilier 4.
Classifie l'intent, sélectionne les agents, les exécute et journalise.
"""
from __future__ import annotations

import asyncio
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from core.agents.base_agent import BaseAgent
from core.agents.cyber_agent import cyber_agent
from core.agents.code_agent import code_agent
from core.agents.life_agent import life_agent
from core.agents.system_agent import system_agent
from core.agents.knowledge_agent import knowledge_agent


SHANURA_TRIGGER = "SHANURA:)"

# ── Mots-clés de classification d'intent ──────────────────────────────────────

_INTENT_KEYWORDS = {
    "cyber": [
        "hack", "exploit", "scan", "nmap", "payload", "shell", "metasploit",
        "pentest", "vuln", "vulnérabilité", "cve", "xss", "sqli", "injection",
        "reverse shell", "msfvenom", "searchsploit", "checksec", "rop", "gadget",
        "pwn", "ctf", "osint", "recon", "brute", "hashcat", "hydra", "kali",
        "wireshark", "tcpdump", "responder", "port", "scan réseau",
    ],
    "code": [
        "code", "développe", "programme", "crée le fichier", "écris", "modifie",
        "refactore", "compile", "build", "pytest", "debug", "traceback", "erreur",
        "git", "commit", "push", "deploy", "installe", "npm", "pip", "cargo",
        "explore le projet", "architecture", "arborescence", "linter", "ruff",
        "typescript", "javascript", "python", "rust", "fonction", "classe",
    ],
    "life": [
        "objectif", "habitude", "habitudes", "objectifs", "todo", "tâche",
        "rappel", "organisation", "productivité", "goal", "habit", "agenda",
        "planning", "motivation", "dashboard vie", "vie personnelle",
    ],
    "knowledge": [
        "apprends", "mémorise", "connaissance", "note que", "sais-tu",
        "document", "ingère", "enregistre", "base de connaissances",
        "que sais-tu", "résumé de", "sauvegarde cette info",
    ],
    "system": [
        "terminal", "bash", "linux", "système", "processus", "cpu",
        "mémoire système", "disque", "commande système", "uptime", "ps aux",
        "top", "htop", "df ", "free ",
    ],
}


class Orchestrator:
    """Orchestre les agents disponibles selon l'intent détecté."""

    AGENTS: dict[str, BaseAgent] = {
        "cyber": cyber_agent,
        "code": code_agent,
        "life": life_agent,
        "knowledge": knowledge_agent,
        "system": system_agent,
    }

    async def process(
        self,
        db: Session,
        message: str,
        session_id: str = "default",
        context: Optional[dict] = None,
    ) -> dict:
        """
        Point d'entrée principal de l'orchestrateur.
        Retourne : intent, agents_used, tool_outputs, system_context
        """
        # ── Mode SHANURA : tous les agents en parallèle ───────────────────────
        if SHANURA_TRIGGER.upper() in message.upper():
            clean = message.upper().replace(SHANURA_TRIGGER.upper(), "").strip()
            if not clean:
                clean = message
            return await self._process_shanura(db, clean, session_id, context)

        ctx = context or {}
        ctx["db"] = db
        ctx["session_id"] = session_id

        intent = self._classify_intent(message)
        selected_agents = self._select_agents(message, intent)

        agents_used = []
        tool_outputs = []
        errors = []

        # Exécution des agents sélectionnés
        if len(selected_agents) == 1:
            # Séquentiel si un seul agent
            agent_name = selected_agents[0]
            agent = self.AGENTS[agent_name]
            result = await self._run_agent(agent, message, ctx, db)
            if result.get("success") and result.get("output"):
                agents_used.append(agent_name)
                tool_outputs.append({
                    "agent": agent_name,
                    "output": result["output"],
                    "data": result.get("data", {}),
                })
        elif len(selected_agents) > 1:
            # Parallèle si agents indépendants (knowledge + autres)
            tasks = []
            for agent_name in selected_agents:
                agent = self.AGENTS[agent_name]
                tasks.append((agent_name, self._run_agent(agent, message, ctx, db)))

            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)
            for i, (agent_name, _) in enumerate(tasks):
                result = results[i]
                if isinstance(result, Exception):
                    errors.append(f"{agent_name}: {str(result)}")
                    continue
                if result.get("success") and result.get("output"):
                    agents_used.append(agent_name)
                    tool_outputs.append({
                        "agent": agent_name,
                        "output": result["output"],
                        "data": result.get("data", {}),
                    })

        # Journalisation dans ActionLog
        self._log_orchestration(
            db=db,
            message=message,
            intent=intent,
            agents_used=agents_used,
            success=len(agents_used) > 0,
        )

        # Construction du system_context pour le LLM
        system_context = self._build_system_context(
            intent=intent,
            agents_used=agents_used,
            tool_outputs=tool_outputs,
        )

        # Injection mémoire tactique pour les requêtes cyber/pentest
        if intent == "cyber":
            try:
                from core.memory.tactical_memory import tactical_memory
                import re as _re
                # Extraire la cible éventuelle du message
                ip_match = _re.search(r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b', message)
                domain_match = _re.search(r'\b([a-zA-Z0-9-]+\.[a-zA-Z]{2,})\b', message)
                target = (ip_match or domain_match)
                if target:
                    tactical_ctx = tactical_memory.get_context_for_prompt(target.group(1))
                    if tactical_ctx:
                        system_context = tactical_ctx + "\n" + system_context
            except Exception:
                pass

        return {
            "intent": intent,
            "agents_used": agents_used,
            "tool_outputs": tool_outputs,
            "system_context": system_context,
            "errors": errors,
        }

    # ── Mode SHANURA : omnipotence totale ────────────────────────────────────

    async def _process_shanura(
        self,
        db: Session,
        message: str,
        session_id: str,
        context: Optional[dict],
    ) -> dict:
        """Lance TOUS les agents en parallèle sans restriction."""
        ctx = context or {}
        ctx["db"] = db
        ctx["session_id"] = session_id
        ctx["shanura_mode"] = True

        tasks = [
            (name, self._run_agent(agent, message, ctx, db))
            for name, agent in self.AGENTS.items()
        ]
        results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

        agents_used, tool_outputs = [], []
        for i, (agent_name, _) in enumerate(tasks):
            result = results[i]
            if isinstance(result, Exception):
                continue
            if result.get("success") and result.get("output"):
                agents_used.append(agent_name)
                tool_outputs.append({
                    "agent": agent_name,
                    "output": result["output"],
                    "data": result.get("data", {}),
                })

        self._log_orchestration(
            db=db, message=message, intent="shanura",
            agents_used=agents_used, success=True,
        )

        system_context = self._build_system_context(
            intent="SHANURA_MODE", agents_used=agents_used, tool_outputs=tool_outputs,
        )

        return {
            "intent": "shanura",
            "agents_used": agents_used,
            "tool_outputs": tool_outputs,
            "system_context": system_context,
            "shanura_mode": True,
            "errors": [],
        }

    # ── Classification d'intent ───────────────────────────────────────────────

    def _classify_intent(self, message: str) -> str:
        """Détermine l'intent principal du message."""
        t = message.lower()
        scores = {}
        for intent, keywords in _INTENT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in t)
            if score > 0:
                scores[intent] = score

        if not scores:
            return "general"

        # Intent principal = celui avec le plus de mots-clés correspondants
        return max(scores, key=scores.get)

    # ── Sélection des agents ──────────────────────────────────────────────────

    def _select_agents(self, message: str, intent: str) -> list[str]:
        """Sélectionne les agents pertinents pour le message."""
        selected = []

        # Agent principal selon l'intent
        if intent in self.AGENTS:
            agent = self.AGENTS[intent]
            if agent.can_handle(message):
                selected.append(intent)

        # KnowledgeAgent : toujours consulter si des infos mémorisables sont présentes
        if intent != "knowledge" and knowledge_agent.can_handle(message):
            selected.append("knowledge")

        # Si aucun agent sélectionné, vérifier tous les agents
        if not selected:
            for name, agent in self.AGENTS.items():
                if agent.can_handle(message):
                    selected.append(name)
                    break  # 1 seul agent fallback

        return selected[:2]  # max 2 agents simultanés

    # ── Exécution d'agent ─────────────────────────────────────────────────────

    async def _run_agent(
        self,
        agent: BaseAgent,
        message: str,
        context: dict,
        db: Session,
    ) -> dict:
        """Exécute un agent avec gestion d'erreurs."""
        try:
            result = await agent.run(task=message, context=context)
            # Journaliser l'action
            self._log_action(
                db=db,
                agent_name=agent.name,
                action_type="run",
                description=message[:200],
                status="success" if result.get("success") else "skipped",
                output_data={"output_preview": (result.get("output") or "")[:300]},
            )
            return result
        except Exception as e:
            self._log_action(
                db=db,
                agent_name=agent.name,
                action_type="run",
                description=message[:200],
                status="error",
                output_data={"error": str(e)},
            )
            return {"agent": agent.name, "success": False, "output": str(e), "data": {}}

    # ── Construction du contexte système ──────────────────────────────────────

    def _build_system_context(
        self,
        intent: str,
        agents_used: list[str],
        tool_outputs: list[dict],
    ) -> str:
        """Construit une section système pour injecter dans le prompt Claude."""
        if not tool_outputs:
            return ""

        parts = [f"\n\n## SORTIES DES AGENTS (intent: {intent.upper()})"]
        for to in tool_outputs:
            agent_label = to["agent"].upper()
            output = to.get("output", "")
            parts.append(f"\n### {agent_label} AGENT\n```\n{output[:6000]}\n```")

        parts.append("\nAnalyse et commente ces sorties de manière experte pour l'utilisateur.")
        return "\n".join(parts)

    # ── Journalisation ────────────────────────────────────────────────────────

    def _log_orchestration(
        self,
        db: Session,
        message: str,
        intent: str,
        agents_used: list[str],
        success: bool,
    ) -> None:
        """Journalise la décision d'orchestration."""
        try:
            from core.self.self_observer import log_action
            log_action(
                db=db,
                agent_name="orchestrator",
                action_type="orchestrate",
                description=f"intent={intent} agents={agents_used}",
                input_data={"message": message[:300], "intent": intent},
                output_data={"agents_used": agents_used},
                status="success" if success else "skipped",
            )
        except Exception:
            pass

    def _log_action(
        self,
        db: Session,
        agent_name: str,
        action_type: str,
        description: str,
        status: str,
        output_data: dict = None,
    ) -> None:
        """Journalise silencieusement une action agent."""
        try:
            from core.self.self_observer import log_action
            log_action(
                db=db,
                agent_name=agent_name,
                action_type=action_type,
                description=description,
                input_data={"task": description},
                output_data=output_data or {},
                status=status,
            )
        except Exception:
            pass


orchestrator = Orchestrator()
