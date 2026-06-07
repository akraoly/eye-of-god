from sqlalchemy.orm import Session
from core.llm.client import llm_client
from core.llm.context import context_builder
from core.memory.memory_engine import memory_engine
from core.orchestrator import orchestrator


class ChatService:
    async def chat(self, db: Session, message: str, session_id: str = "default") -> dict:
        # ── Mémoire cross-session : recharge l'historique si le cache est vide ──
        context_builder.warm_from_db(db=db, session_id=session_id)

        # Extraire les infos importantes du message
        memory_engine.extract_and_save(db=db, message=message)

        # Mémoires sémantiquement proches
        memories = memory_engine.get_relevant_memories(db=db, query=message)
        profile = memory_engine.get_user_profile(db=db)

        # Système enrichi avec profil et mémoires
        system = context_builder.build_system(user_memories=memories, user_profile=profile)

        # ── Orchestrateur : classify intent + dispatch agents ─────────────────
        orchestration = await orchestrator.process(
            db=db,
            message=message,
            session_id=session_id,
        )

        intent = orchestration.get("intent", "general")
        agents_used = orchestration.get("agents_used", [])
        tool_outputs = orchestration.get("tool_outputs", [])
        system_context = orchestration.get("system_context", "")
        shanura_mode = orchestration.get("shanura_mode", False)

        # Mode SHANURA : prompt omnipotence
        if shanura_mode:
            from core.llm.prompts import SHANURA_MODE_PROMPT
            system = system + SHANURA_MODE_PROMPT

        # SystemAgent actif : injecter le persona médecin
        if "system" in agents_used and not shanura_mode:
            from core.llm.prompts import SYSTEM_AGENT_PROMPT
            system = system + SYSTEM_AGENT_PROMPT

        # Injecter les sorties des agents dans le system prompt
        if system_context:
            system = system + system_context
        elif tool_outputs:
            # Fallback : construction manuelle si system_context vide
            for to in tool_outputs:
                agent_label = to.get("agent", "AGENT").upper()
                output = to.get("output", "")
                if output:
                    system = (
                        system
                        + f"\n\n## SORTIE {agent_label} (exécution réelle)\n"
                        + f"```\n{output[:8000]}\n```\n"
                        + "Analyse et commente cette sortie de manière experte."
                    )

        # Construire les messages (mémoire courte + nouveau message)
        messages = context_builder.build_messages(session_id, message)

        # Appel Claude
        response = await llm_client.complete(messages=messages, system=system)

        # Mettre à jour la mémoire courte
        context_builder.add_message(session_id, "user", message)
        context_builder.add_message(session_id, "assistant", response)

        # Sauvegarder l'échange en base
        memory_engine.save_exchange(
            db=db,
            session_id=session_id,
            user_message=message,
            assistant_response=response,
            context_used=len(memories),
        )

        # Résumé automatique si l'historique est trop long
        try:
            from core.memory.summarizer import summarizer
            import asyncio
            asyncio.create_task(summarizer.summarize_if_needed(db=db))
        except Exception:
            pass

        try:
            from core.memory.vector_store import vector_store
            vb = vector_store.backend
        except Exception:
            vb = "unknown"

        return {
            "response": response,
            "session_id": session_id,
            "memories_used": len(memories),
            "tool_executed": len(tool_outputs) > 0,
            "intent": intent,
            "agents_used": agents_used,
            "vector_backend": vb,
            "shanura_mode": shanura_mode,
        }

    def clear_session(self, session_id: str):
        context_builder.clear_session(session_id)


chat_service = ChatService()
