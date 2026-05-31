from sqlalchemy.orm import Session
from core.llm.client import llm_client
from core.llm.context import context_builder
from core.memory.memory_engine import memory_engine


class ChatService:
    async def chat(self, db: Session, message: str, session_id: str = "default") -> dict:
        # Extraire les infos importantes du message
        memory_engine.extract_and_save(db=db, message=message)

        # Récupérer les mémoires sémantiquement proches du message
        memories = memory_engine.get_relevant_memories(db=db, query=message)
        profile = memory_engine.get_user_profile(db=db)

        # Construire le prompt système enrichi
        system = context_builder.build_system(user_memories=memories, user_profile=profile)

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

        # Résumé automatique si l'historique est trop long (asynchrone, non bloquant)
        try:
            from core.memory.summarizer import summarizer
            import asyncio
            asyncio.create_task(summarizer.summarize_if_needed(db=db))
        except Exception:
            pass

        return {
            "response": response,
            "session_id": session_id,
            "memories_used": len(memories),
            "vector_backend": __import__("core.memory.vector_store", fromlist=["vector_store"]).vector_store.backend,
        }

    def clear_session(self, session_id: str):
        context_builder.clear_session(session_id)


chat_service = ChatService()
