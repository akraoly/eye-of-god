from sqlalchemy.orm import Session
from core.llm.client import llm_client
from core.llm.context import context_builder
from core.memory.memory_engine import memory_engine
from core.agents.cyber_agent import cyber_agent


class ChatService:
    async def chat(self, db: Session, message: str, session_id: str = "default") -> dict:
        # Extraire les infos importantes du message
        memory_engine.extract_and_save(db=db, message=message)

        # Mémoires sémantiquement proches
        memories = memory_engine.get_relevant_memories(db=db, query=message)
        profile = memory_engine.get_user_profile(db=db)

        # Système enrichi
        system = context_builder.build_system(user_memories=memories, user_profile=profile)

        # Exécution automatique si le CyberAgent peut gérer la demande
        tool_output = None
        if cyber_agent.can_handle(message):
            try:
                agent_result = await cyber_agent.run(task=message)
                if agent_result.get("success") and agent_result.get("output"):
                    tool_output = agent_result["output"]
            except Exception:
                pass

        # Injecter la sortie outil dans le system prompt
        if tool_output:
            system = (
                system
                + f"\n\n## SORTIE OUTIL (exécution réelle sur Kali Linux)\n"
                + f"```\n{tool_output[:8000]}\n```\n"
                + "Analyse et commente cette sortie de manière experte pour l'utilisateur."
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
            "tool_executed": tool_output is not None,
            "vector_backend": vb,
        }

    def clear_session(self, session_id: str):
        context_builder.clear_session(session_id)


chat_service = ChatService()
