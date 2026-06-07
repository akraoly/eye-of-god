import base64
import logging
from sqlalchemy.orm import Session
from core.llm.client import llm_client
from core.llm.context import context_builder
from core.memory.memory_engine import memory_engine
from core.orchestrator import orchestrator

logger = logging.getLogger(__name__)

# Mots-clés qui déclenchent une capture d'écran automatique
_VISION_KEYWORDS = [
    "regarde mon écran", "regarde l'écran", "analyse l'écran",
    "capture l'écran", "que vois-tu", "ce que tu vois",
    "vois-tu", "tu vois", "mon écran", "analyse cette image",
    "regarde ça", "décris mon écran", "qu'est-ce que tu vois",
    "look at my screen", "analyze my screen",
]

def _detect_vision_intent(message: str) -> bool:
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in _VISION_KEYWORDS)


def _inject_image_in_messages(messages: list, image_b64: str, media_type: str) -> list:
    """Remplace le content du dernier message user par un bloc multimodal [image, texte]."""
    for i in range(len(messages) - 1, -1, -1):
        if messages[i]["role"] == "user":
            text = messages[i]["content"]
            if isinstance(text, str):
                messages[i] = {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {"type": "text", "text": text},
                    ],
                }
            break
    return messages


class ChatService:
    async def chat(self, db: Session, message: str, session_id: str = "default",
                   vocal_input: bool = False, voice_energy: str = "normal", voice_duration: float = 0.0,
                   image_b64: str = "", media_type: str = "image/png") -> dict:
        # ── Mémoire cross-session : recharge l'historique si le cache est vide ──
        context_builder.warm_from_db(db=db, session_id=session_id)

        # Extraire les infos importantes + apprendre le style de communication
        memory_engine.extract_and_save(db=db, message=message)
        memory_engine.learn_communication_style(db=db, message=message)

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

        # Mode vocal : l'IA répond comme à voix haute, adapte selon énergie détectée
        if vocal_input:
            from core.llm.prompts import VOCAL_MODE_PROMPT, VOCAL_STYLE_LEARNING_PROMPT
            energy_hint = ""
            if voice_energy == "intense":
                energy_hint = "\nTon vocal détecté : INTENSE/URGENT — Mr Vitch parle avec force et urgence. Réponds avec la même énergie, sois direct et percutant."
            elif voice_energy == "calme":
                energy_hint = "\nTon vocal détecté : CALME/POSÉ — Mr Vitch parle doucement. Réponds avec sérénité, prends le temps."
            system = system + VOCAL_MODE_PROMPT + energy_hint + VOCAL_STYLE_LEARNING_PROMPT
            memory_engine.track_vocal_usage(db=db)

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

        # Construire les messages — historique court en vocal (plus rapide)
        messages = context_builder.build_messages(session_id, message, max_turns=4 if vocal_input else 12)

        # Vision : auto-screenshot si mot-clé détecté, sinon image fournie
        vision_b64 = image_b64
        vision_type = media_type or "image/png"
        if not vision_b64 and _detect_vision_intent(message):
            try:
                from core.vision.vision_engine import capture_screenshot
                img_data, img_type = capture_screenshot()
                vision_b64 = base64.standard_b64encode(img_data).decode()
                vision_type = img_type
                system += "\n\n[VISION ACTIVE] Mr Vitch a demandé une analyse visuelle. Une capture d'écran a été jointe au message — décris et analyse ce que tu vois sur l'écran."
                logger.info("[VISION] Auto-screenshot injecté dans le message")
            except Exception as e:
                system += f"\n\n[VISION] Capture d'écran demandée mais échouée : {e}"
                logger.warning(f"[VISION] Capture échouée : {e}")
        elif vision_b64:
            system += "\n\n[VISION ACTIVE] Mr Vitch a joint une image à ce message — analyse-la en détail en relation avec sa question."

        if vision_b64:
            messages = _inject_image_in_messages(messages, vision_b64, vision_type)

        # Tokens réduits en vocal : réponse courte = latence divisée par 3
        max_tok = 600 if vocal_input else 2048

        # Appel Claude
        response = await llm_client.complete(messages=messages, system=system, max_tokens=max_tok)

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

    async def stream(self, db: Session, message: str, session_id: str = "default",
                     vocal_input: bool = False, voice_energy: str = "normal", voice_duration: float = 0.0,
                     image_b64: str = "", media_type: str = "image/png"):
        """Génère la réponse token par token via streaming."""
        context_builder.warm_from_db(db=db, session_id=session_id)
        memory_engine.extract_and_save(db=db, message=message)
        memory_engine.learn_communication_style(db=db, message=message)

        memories = memory_engine.get_relevant_memories(db=db, query=message)
        profile  = memory_engine.get_user_profile(db=db)
        system   = context_builder.build_system(user_memories=memories, user_profile=profile)

        orchestration  = await orchestrator.process(db=db, message=message, session_id=session_id)
        shanura_mode   = orchestration.get("shanura_mode", False)
        system_context = orchestration.get("system_context", "")

        if vocal_input:
            from core.llm.prompts import VOCAL_MODE_PROMPT, VOCAL_STYLE_LEARNING_PROMPT
            energy_hint = ""
            if voice_energy == "intense":
                energy_hint = "\nTon vocal : INTENSE — réponds avec la même énergie, direct et percutant."
            elif voice_energy == "calme":
                energy_hint = "\nTon vocal : CALME — réponds avec sérénité, prends le temps."
            system += VOCAL_MODE_PROMPT + energy_hint + VOCAL_STYLE_LEARNING_PROMPT
            memory_engine.track_vocal_usage(db=db)

        if shanura_mode:
            from core.llm.prompts import SHANURA_MODE_PROMPT
            system += SHANURA_MODE_PROMPT

        if system_context:
            system += system_context

        messages = context_builder.build_messages(session_id, message, max_turns=4 if vocal_input else 12)

        # Vision : auto-screenshot si mot-clé détecté, sinon image fournie
        vision_b64 = image_b64
        vision_type = media_type or "image/png"
        if not vision_b64 and _detect_vision_intent(message):
            try:
                from core.vision.vision_engine import capture_screenshot
                img_data, img_type = capture_screenshot()
                vision_b64 = base64.standard_b64encode(img_data).decode()
                vision_type = img_type
                system += "\n\n[VISION ACTIVE] Mr Vitch a demandé une analyse visuelle. Une capture d'écran a été jointe au message — décris et analyse ce que tu vois sur l'écran."
                logger.info("[VISION] Auto-screenshot injecté (stream)")
            except Exception as e:
                system += f"\n\n[VISION] Capture d'écran demandée mais échouée : {e}"
        elif vision_b64:
            system += "\n\n[VISION ACTIVE] Mr Vitch a joint une image à ce message — analyse-la en détail en relation avec sa question."

        if vision_b64:
            messages = _inject_image_in_messages(messages, vision_b64, vision_type)

        max_tok  = 600 if vocal_input else 2048

        full_response = ""
        async for chunk in llm_client.stream(messages=messages, system=system, max_tokens=max_tok):
            full_response += chunk
            yield chunk

        # Sauvegarder après stream complet
        context_builder.add_message(session_id, "user", message)
        context_builder.add_message(session_id, "assistant", full_response)
        memory_engine.save_exchange(db=db, session_id=session_id,
                                    user_message=message, assistant_response=full_response)

    def clear_session(self, session_id: str):
        context_builder.clear_session(session_id)


chat_service = ChatService()
