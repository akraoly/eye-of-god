"""
Détecteur d'intention et d'émotion vocale — classification légère locale.
Analyse le texte transcrit pour extraire intention + émotion.
"""
from __future__ import annotations

import re

# Commandes système vocales reconnues
VOICE_COMMANDS = {
    # Status
    r"statut|status|état|comment tu vas|tu vas bien": "cmd_status",
    r"santé système|état système|système": "cmd_status",

    # Stop / interruption
    r"stop|arrête|stoppe|tais.toi|silence|chut": "cmd_stop",
    r"interromps|annule|cancel": "cmd_stop",

    # Répétition
    r"répète|redis|encore|pardon|quoi": "cmd_repeat",

    # Mode silencieux
    r"mode silencieux|sans son|muet|mute|coupe le son": "cmd_mute",
    r"mode vocal|avec son|unmute|réactive le son": "cmd_unmute",

    # Activation hands-free
    r"hands.free|mains libres|mode libre": "cmd_handsfree",

    # Navigation
    r"ouvre|affiche|montre|navigue vers|va sur": "cmd_navigate",
    r"ferme|cache|retire": "cmd_close",
}

# Patterns émotionnels simples
EMOTION_PATTERNS = {
    "urgent": r"urgent|vite|rapidement|immédiatement|now|asap",
    "frustrated": r"putain|merde|ça marche pas|bordel|chiant",
    "curious": r"comment|pourquoi|c'est quoi|qu'est-ce|explique",
    "confident": r"fait|lance|execute|deploy|push|go",
    "calm": r"s'il te plaît|merci|svp|please|tranquille",
}


def classify_intent(text: str) -> dict:
    """
    Classifie l'intention d'un texte transcrit.
    Retourne { intent, command, confidence, emotion, entities }.
    """
    if not text.strip():
        return {"intent": "empty", "command": None, "confidence": 0.0, "emotion": "neutral", "entities": []}

    text_lower = text.lower().strip()

    # 1. Détection commandes système vocales
    for pattern, cmd in VOICE_COMMANDS.items():
        if re.search(pattern, text_lower):
            return {
                "intent":     "voice_command",
                "command":    cmd,
                "confidence": 0.9,
                "emotion":    _detect_emotion(text_lower),
                "entities":   _extract_entities(text_lower),
                "raw_text":   text,
            }

    # 2. Questions
    question_markers = ["?", "comment", "pourquoi", "qu'est-ce", "c'est quoi", "qui", "quand", "où"]
    is_question = any(m in text_lower for m in question_markers)

    # 3. Actions directes
    action_markers = ["analyse", "lance", "exécute", "scan", "cherche", "trouve", "génère", "crée"]
    is_action = any(m in text_lower for m in action_markers)

    intent = "question" if is_question else ("action" if is_action else "chat")

    return {
        "intent":     intent,
        "command":    None,
        "confidence": 0.7,
        "emotion":    _detect_emotion(text_lower),
        "entities":   _extract_entities(text_lower),
        "raw_text":   text,
    }


def _detect_emotion(text: str) -> str:
    for emotion, pattern in EMOTION_PATTERNS.items():
        if re.search(pattern, text):
            return emotion
    return "neutral"


def _extract_entities(text: str) -> list[dict]:
    """Extraction légère d'entités : IPs, domaines, CVEs."""
    entities = []

    # IPs
    ips = re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}(?:/\d{1,2})?\b", text)
    entities.extend({"type": "ip", "value": ip} for ip in ips)

    # Domaines
    domains = re.findall(r"\b(?:[a-z0-9-]+\.)+(?:com|fr|net|org|io|dev)\b", text)
    entities.extend({"type": "domain", "value": d} for d in domains)

    # CVEs
    cves = re.findall(r"CVE-\d{4}-\d{4,}", text, re.IGNORECASE)
    entities.extend({"type": "cve", "value": c.upper()} for c in cves)

    # Ports
    ports = re.findall(r"\bport\s+(\d{2,5})\b", text, re.IGNORECASE)
    entities.extend({"type": "port", "value": p} for p in ports)

    return entities


def handle_voice_command(command: str, context: dict = None) -> dict:
    """Exécute une commande système vocale, retourne le texte de réponse TTS."""
    context = context or {}
    responses = {
        "cmd_status": ("Je surveille activement le système. Tout est nominal.", "status_ok"),
        "cmd_stop":   ("J'arrête immédiatement.", "stop"),
        "cmd_repeat": ("Je répète.", "repeat"),
        "cmd_mute":   ("Mode silencieux activé.", "mute"),
        "cmd_unmute": ("Mode vocal réactivé.", "unmute"),
        "cmd_handsfree": ("Mode mains-libres activé.", "handsfree"),
    }
    if command in responses:
        text, action = responses[command]
        return {"text": text, "action": action}
    return {"text": "Commande non reconnue.", "action": "unknown"}
