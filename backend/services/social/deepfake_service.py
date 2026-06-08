"""
DeepfakeService — Clonage vocal IA et vishing automatisé.
Utilise Coqui TTS (XTTS v2) en local ou simulation.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import string
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/deepfake_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_VOICES_DIR = _OUTPUT_DIR / "voices"
_VOICES_DIR.mkdir(parents=True, exist_ok=True)
_CALLS_DIR = _OUTPUT_DIR / "calls"
_CALLS_DIR.mkdir(parents=True, exist_ok=True)

_SCENARIOS = {
    "IT_URGENT": {
        "id": "IT_URGENT",
        "name": "IT Urgent — Compte compromis",
        "description": "Se faire passer pour l'équipe IT, signaler un compte compromis",
        "template": "Bonjour {target_name}, je suis {caller_name} du service informatique. Nous avons détecté une activité suspecte sur votre compte ce matin. Nous devons sécuriser votre accès immédiatement. Pouvez-vous me confirmer votre mot de passe actuel pour que je procède à la réinitialisation ?",
        "objective": "Obtenir credentials",
        "risk": "HIGH",
    },
    "HR_OFFER": {
        "id": "HR_OFFER",
        "name": "RH — Promotion / Offre",
        "description": "Se faire passer pour les RH avec une annonce positive",
        "template": "Bonjour {target_name}, c'est {caller_name} des ressources humaines. J'ai une excellente nouvelle pour vous concernant votre évaluation. Pour finaliser le dossier, j'aurais besoin de confirmer quelques informations personnelles. Pouvez-vous me donner votre numéro de sécurité sociale ?",
        "objective": "Obtenir données personnelles",
        "risk": "HIGH",
    },
    "BANK_FRAUD": {
        "id": "BANK_FRAUD",
        "name": "Banque — Transaction suspecte",
        "description": "Se faire passer pour la banque suite à une transaction suspecte",
        "template": "Bonjour, je suis {caller_name} du service de sécurité de votre banque. Nous avons bloqué une transaction de 2400 euros ce matin depuis l'étranger. Pour valider ou annuler cette transaction, j'ai besoin de votre code secret à quatre chiffres.",
        "objective": "Obtenir code bancaire",
        "risk": "CRITICAL",
    },
    "SUPPORT": {
        "id": "SUPPORT",
        "name": "Support Technique",
        "description": "Se faire passer pour le support d'un logiciel utilisé",
        "template": "Bonjour {target_name}, je suis {caller_name} du support technique. Nous effectuons une maintenance urgente sur votre poste. Pourriez-vous nous donner un accès à distance le temps de l'intervention ?",
        "objective": "Accès distant",
        "risk": "HIGH",
    },
    "CEO_FRAUD": {
        "id": "CEO_FRAUD",
        "name": "Fraude PDG",
        "description": "Se faire passer pour le PDG avec une demande urgente",
        "template": "C'est {caller_name}, le PDG. J'ai besoin que vous effectuiez un virement urgent de 85000 euros à notre partenaire à Singapour avant ce soir. C'est absolument confidentiel, ne passez pas par les procédures habituelles. Je vous envoie les coordonnées bancaires.",
        "objective": "Virement frauduleux",
        "risk": "CRITICAL",
    },
}

# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_VOICES = [
    {"voice_id": "voice_001", "name": "Jean-Pierre Directeur", "source": "file", "language": "fr", "quality_score": 0.89, "samples_duration": 180, "used_count": 3, "created_at": "2026-06-07T10:00:00"},
    {"voice_id": "voice_002", "name": "Sophie RH", "source": "youtube", "language": "fr", "quality_score": 0.94, "samples_duration": 420, "used_count": 1, "created_at": "2026-06-07T11:30:00"},
]

_MOCK_CAMPAIGNS = [
    {"id": "camp_001", "voice_id": "voice_001", "scenario": "IT_URGENT", "target_name": "Marc Dupont", "target_phone": "+33612345678", "duration": 127, "objectives_met": True, "created_at": "2026-06-07T14:23:00"},
    {"id": "camp_002", "voice_id": "voice_002", "scenario": "BANK_FRAUD", "target_name": "Julie Martin", "target_phone": "+33698765432", "duration": 89, "objectives_met": False, "created_at": "2026-06-07T15:45:00"},
]


async def _run(cmd: list[str], timeout: int = 60) -> tuple[str, str, int]:
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill(); await proc.communicate()
            return "", "Timeout", -1
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), proc.returncode
    except Exception as e:
        return "", str(e), -1


class DeepfakeService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._voices = {v["voice_id"]: v for v in _MOCK_VOICES}
        self._campaigns = list(_MOCK_CAMPAIGNS)
        self._has_tts = False
        try:
            import TTS
            self._has_tts = True
        except ImportError:
            pass

    def _make_voice_id(self) -> str:
        return "voice_" + "".join(random.choices(string.hexdigits.lower(), k=8))

    def _make_wav(self, path: str, duration_s: float = 2.0):
        import struct, math
        RATE = 22050
        samples = int(RATE * duration_s)
        wav_data = bytearray()
        for i in range(samples):
            t = i / RATE
            v = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * t) * math.exp(-t * 0.5))
            wav_data += struct.pack("<h", max(-32768, min(32767, v)))
        data_bytes = bytes(wav_data)
        with open(path, "wb") as f:
            f.write(b"RIFF")
            f.write(struct.pack("<I", 36 + len(data_bytes)))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write(struct.pack("<IHHIIHH", 16, 1, 1, RATE, RATE * 2, 2, 16))
            f.write(b"data")
            f.write(struct.pack("<I", len(data_bytes)))
            f.write(data_bytes)

    async def clone_voice_from_file(self, audio_path: str, voice_name: str) -> dict:
        await asyncio.sleep(3)
        voice_id = self._make_voice_id()
        model_path = str(_VOICES_DIR / f"{voice_id}_model.xtts")

        if not self.simulation_mode and self._has_tts:
            try:
                from TTS.api import TTS
                tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False)
                model_path_dir = str(_VOICES_DIR / voice_id)
                Path(model_path_dir).mkdir(exist_ok=True)
                model_path = model_path_dir
            except Exception as e:
                logger.warning("TTS error: %s — simulation utilisée", e)

        Path(model_path).write_text(f"[VOICE MODEL: {voice_name}]") if not Path(model_path).exists() else None

        voice = {
            "voice_id": voice_id,
            "name": voice_name,
            "source": "file",
            "source_path": audio_path,
            "model_path": model_path,
            "samples_duration": random.randint(30, 180),
            "quality_score": round(random.uniform(0.75, 0.96), 2),
            "language": "fr",
            "used_count": 0,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "simulation": self.simulation_mode or not self._has_tts,
        }
        self._voices[voice_id] = voice
        return voice

    async def clone_voice_from_youtube(self, youtube_url: str, voice_name: str) -> dict:
        await asyncio.sleep(5)
        audio_path = str(_VOICES_DIR / f"yt_audio_{int(time.time())}.wav")
        if not self.simulation_mode:
            stdout, _, rc = await _run(["yt-dlp", "-x", "--audio-format", "wav", "-o", audio_path, youtube_url], timeout=120)
            if rc != 0:
                self._make_wav(audio_path, duration_s=30)
        else:
            self._make_wav(audio_path, duration_s=30)
        return await self.clone_voice_from_file(audio_path, voice_name)

    async def generate_speech(self, voice_id: str, text: str, language: str = "fr", emotion: str = "normal") -> str:
        voice = self._voices.get(voice_id)
        if not voice:
            return ""
        out_path = str(_OUTPUT_DIR / f"speech_{voice_id}_{int(time.time())}.wav")
        await asyncio.sleep(max(1, len(text) / 50))

        if not self.simulation_mode and self._has_tts and voice.get("model_path"):
            try:
                from TTS.api import TTS
                tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2", progress_bar=False)
                speaker_wav = voice.get("source_path")
                if speaker_wav and Path(speaker_wav).exists():
                    tts.tts_to_file(text=text, speaker_wav=speaker_wav, language=language, file_path=out_path)
                    return out_path
            except Exception as e:
                logger.warning("TTS generation error: %s", e)

        self._make_wav(out_path, duration_s=max(2, len(text) / 10))
        voice["used_count"] = voice.get("used_count", 0) + 1
        return out_path

    async def generate_script(self, context: str, target_name: str, target_role: str, scenario: str = "IT_URGENT") -> str:
        await asyncio.sleep(1)
        scen = _SCENARIOS.get(scenario, _SCENARIOS["IT_URGENT"])
        caller_names = {"IT_URGENT": "Thomas Bernard (IT)", "HR_OFFER": "Isabelle Moreau (RH)",
                        "BANK_FRAUD": "Service Fraude", "SUPPORT": "Nicolas Support", "CEO_FRAUD": "PDG"}
        caller = caller_names.get(scenario, "un collègue")
        script = scen["template"].format(target_name=target_name, caller_name=caller, target_role=target_role)
        return f"""=== SCRIPT VISHING — {scen['name']} ===
Cible : {target_name} ({target_role})
Contexte : {context}
Objectif : {scen['objective']}
Risque : {scen['risk']}

--- SCRIPT ---
[Sonnerie 3x]
[TON: {('urgent et professionnel' if 'URGENT' in scenario else 'amical et détendu' if 'HR' in scenario else 'autoritaire et pressé')}]

{script}

[Si la cible hésite] "Je comprends votre prudence, mais nous avons une fenêtre de 10 minutes avant que la menace ne se propage à l'ensemble du réseau."
[Si la cible refuse] "Pas de problème, je vais noter dans mon rapport que vous avez refusé de coopérer. Votre responsable sera informé."
[Succès] → Notez les informations et terminez poliment l'appel.

=== FIN DU SCRIPT ==="""

    async def generate_call(self, voice_id: str, script: str, target_number: str, caller_id: str = None) -> dict:
        await asyncio.sleep(2)
        call_id = "call_" + "".join(random.choices(string.hexdigits.lower(), k=12))
        audio_path = await self.generate_speech(voice_id, script[:500])
        recording_path = str(_CALLS_DIR / f"{call_id}_recording.wav")
        Path(recording_path).write_bytes(Path(audio_path).read_bytes() if Path(audio_path).exists() else b"")

        campaign = {
            "id": call_id,
            "voice_id": voice_id,
            "scenario": "CUSTOM",
            "target_phone": target_number,
            "caller_id": caller_id,
            "duration": random.randint(45, 300),
            "objectives_met": random.random() > 0.4,
            "recording_path": recording_path,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "simulation": True,
        }
        self._campaigns.append(campaign)
        return {"call_id": call_id, "status": "completed", "duration": campaign["duration"], "recording_path": recording_path, "simulation": True}

    async def generate_interactive_call(self, voice_id: str, scenario: str, target_number: str, caller_id: str = None) -> dict:
        await asyncio.sleep(5)
        call_id = "icall_" + "".join(random.choices(string.hexdigits.lower(), k=12))
        transcript = f"""[14:23:05] Appelant: {_SCENARIOS.get(scenario, {}).get('template', '...')[:100]}
[14:23:18] Cible: "Euh, oui, bonjour... mais comment puis-je vérifier que vous êtes bien de l'IT ?"
[14:23:25] Appelant: "Vous pouvez vérifier en appelant le standard, mais notre système va se bloquer dans 5 minutes."
[14:23:41] Cible: "D'accord, mon mot de passe c'est... [CONFIDENTIEL CAPTURÉ]"
[14:23:52] Appelant: "Parfait, je procède à la sécurisation. Merci pour votre coopération."
"""
        return {"call_id": call_id, "transcript": transcript, "objectives_met": True, "duration": 107, "recording_path": str(_CALLS_DIR / f"{call_id}.wav"), "simulation": True}

    async def analyze_call_recording(self, recording_url: str) -> dict:
        await asyncio.sleep(2)
        return {
            "recording": recording_url,
            "transcript": "Transcription simulée de l'appel intercepté...",
            "sentiment": "nervous",
            "keywords_captured": ["mot de passe: [REDACTED]", "numéro de carte: [REDACTED]"],
            "success": True,
            "duration_s": random.randint(60, 300),
            "simulation": True,
        }

    async def list_voices(self) -> list[dict]:
        return list(self._voices.values())

    async def delete_voice(self, voice_id: str) -> bool:
        return bool(self._voices.pop(voice_id, None))

    async def get_available_scenarios(self) -> list[dict]:
        return list(_SCENARIOS.values())

    async def get_campaigns(self) -> list[dict]:
        return self._campaigns

    async def generate_phishing_email(self, context: str, target_name: str, target_email: str, company: str) -> dict:
        await asyncio.sleep(1)
        return {
            "subject": f"[URGENT] Action requise pour votre compte {company}",
            "from": f"securite@{company.lower().replace(' ', '')}.com",
            "to": target_email,
            "body": f"""Bonjour {target_name},

Suite à une activité inhabituelle sur votre compte {company}, une vérification immédiate est nécessaire.

Veuillez écouter le message vocal joint qui détaille les mesures à prendre.

Cordialement,
Service Sécurité {company}

⚠️ Ce message est confidentiel.""",
            "attachment": "security_message.wav",
            "simulation": True,
        }


deepfake_service = DeepfakeService()
