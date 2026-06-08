"""
Disinformation & Document Forgery — Bloc 9 Guerre de l'Information
Campagnes de désinformation, falsification de métadonnées,
contenu synthétique, contre-mesures de détection.
Simulation défensive — usage légal uniquement (red team, recherche).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_RESULTS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/influence/disinfo")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_DISINFO_ARCHETYPES = {
    "fabricated_quote": {
        "name": "Citation fabriquée",
        "believability": 0.85,
        "spread_velocity": "VERY_HIGH",
        "detection_difficulty": "HIGH",
        "real_examples": ["Fausses citations de personnalités politiques sur Twitter"],
        "mitigation": "Vérification en sources primaires, reverse image search",
    },
    "manipulated_image": {
        "name": "Image manipulée (deepfake/photomontage)",
        "believability": 0.90,
        "spread_velocity": "VERY_HIGH",
        "detection_difficulty": "MEDIUM",
        "tools": ["GIMP", "Photoshop", "Deepfake models"],
        "mitigation": "FotoForensics, InVID, reverse image search",
    },
    "misleading_context": {
        "name": "Contexte trompeur (vraie image, faux contexte)",
        "believability": 0.95,
        "spread_velocity": "HIGH",
        "detection_difficulty": "VERY_HIGH",
        "note": "Image réelle d'un événement passé présentée comme actuelle",
        "mitigation": "Vérification date EXIF, reverse image search avec date",
    },
    "fabricated_document": {
        "name": "Document officiel falsifié",
        "believability": 0.80,
        "spread_velocity": "MEDIUM",
        "detection_difficulty": "HIGH",
        "targets": ["Lettres gouvernementales", "Rapport d'expertise", "Déclaration officielle"],
        "mitigation": "Vérification via canal officiel, analyse forensique PDF",
    },
    "synthetic_video": {
        "name": "Vidéo synthétique (IA)",
        "believability": 0.75,
        "spread_velocity": "VERY_HIGH",
        "detection_difficulty": "MEDIUM",
        "tools": ["DeepFaceLab", "Wav2Lip", "Sora-like models"],
        "mitigation": "Deepfake detectors, physiological cues analysis",
    },
    "impersonation_website": {
        "name": "Site d'usurpation (lookalike)",
        "believability": 0.85,
        "spread_velocity": "MEDIUM",
        "detection_difficulty": "MEDIUM",
        "technique": "Typosquatting + design clone + faux contenu",
        "mitigation": "DMARC, certificate transparency, user education",
    },
    "network_propaganda": {
        "name": "Propagande de réseau (info vraie + biais)",
        "believability": 0.98,
        "spread_velocity": "MEDIUM",
        "detection_difficulty": "VERY_HIGH",
        "technique": "Sélection et encadrement sélectif de faits réels",
        "mitigation": "Média literacy, fact-checking multi-sources",
    },
    "hack_and_leak": {
        "name": "Hack & Leak (fuites sélectives)",
        "believability": 0.97,
        "spread_velocity": "HIGH",
        "detection_difficulty": "VERY_HIGH",
        "real_examples": ["Macron Leaks (2017)", "DNC hack (2016)"],
        "mitigation": "Analyse complète du corpus, pas seulement les extraits diffusés",
    },
}

_METADATA_FIELDS = {
    "image_exif": {
        "GPS_latitude":   "Coordonnées GPS intégrées",
        "GPS_longitude":  "Coordonnées GPS intégrées",
        "DateTime":       "Date/heure de prise de vue",
        "DateTimeOriginal": "Date originale",
        "Make":           "Fabricant appareil (Apple/Samsung/Canon...)",
        "Model":          "Modèle précis",
        "Software":       "Logiciel utilisé",
        "GPSAltitude":    "Altitude",
        "LensModel":      "Objectif utilisé",
        "Artist":         "Auteur",
        "Copyright":      "Droits",
    },
    "pdf_metadata": {
        "Author":         "Auteur du document",
        "Creator":        "Logiciel créateur",
        "Producer":       "Convertisseur PDF",
        "CreationDate":   "Date de création",
        "ModDate":        "Date de modification",
        "Title":          "Titre",
        "Subject":        "Sujet",
        "Keywords":       "Mots-clés",
    },
    "office_metadata": {
        "Author":         "Auteur",
        "LastModifiedBy": "Dernier modificateur",
        "Company":        "Entreprise",
        "Template":       "Modèle utilisé",
        "Created":        "Date création",
        "Modified":       "Date modification",
        "AppVersion":     "Version Office",
        "Revision":       "Numéro de révision",
    },
    "video_metadata": {
        "encoder":        "Codec vidéo",
        "creation_time":  "Timestamp de création",
        "handler_name":   "Gestionnaire de stream",
        "location":       "Localisation GPS encodée",
        "com.apple.quicktime.location.ISO6709": "Location iOS",
    },
}

_DETECTION_METHODS = {
    "ela_analysis": {
        "name": "Error Level Analysis (ELA)",
        "targets": ["Images JPEG manipulées"],
        "tools": ["FotoForensics.com", "GIMP ELA plugin"],
        "principle": "Les zones re-compressées ont un ELA différent des zones originales",
        "accuracy": 0.75,
    },
    "metadata_inconsistency": {
        "name": "Détection d'incohérence de métadonnées",
        "targets": ["Images", "Documents PDF/Office", "Vidéos"],
        "tools": ["ExifTool", "pdf-parser", "olevba"],
        "principle": "Dates/logiciels/GPS incohérents avec le contenu revendiqué",
        "accuracy": 0.85,
    },
    "reverse_image_search": {
        "name": "Recherche image inversée",
        "targets": ["Images présentées hors contexte"],
        "tools": ["Google Images", "TinEye", "Yandex Images", "InVID"],
        "principle": "Retrouver la source originale et vérifier le contexte",
        "accuracy": 0.90,
    },
    "deepfake_detector": {
        "name": "Détecteur de deepfake",
        "targets": ["Vidéos synthétiques", "Face swap images"],
        "tools": ["Deepware Scanner", "Microsoft Video Authenticator", "FakeCatcher (Intel)"],
        "principle": "Artefacts de génération, manque de rPPG, incohérences physiologiques",
        "accuracy": 0.82,
    },
    "pdf_forensics": {
        "name": "Forensique PDF",
        "targets": ["Documents PDF falsifiés"],
        "tools": ["pdfid.py", "pdf-parser.py", "peepdf", "PDFStreamDumper"],
        "principle": "Structure PDF, objets JS, métadonnées, streams suspects",
        "accuracy": 0.88,
    },
    "nlp_authorship": {
        "name": "Analyse stylistique (NLP)",
        "targets": ["Textes attribués à une personne"],
        "tools": ["JGAAP", "LIWC", "custom LLM analysis"],
        "principle": "Comparaison du style d'écriture, vocabulaire, structure",
        "accuracy": 0.70,
    },
}


class DisinfoService:

    def list_archetypes(self) -> Dict:
        return {k: {"name": v["name"], "believability": v["believability"],
                    "detection_difficulty": v["detection_difficulty"]}
                for k, v in _DISINFO_ARCHETYPES.items()}

    def get_archetype_detail(self, archetype: str) -> Dict:
        return _DISINFO_ARCHETYPES.get(archetype, {"error": "not_found"})

    def list_metadata_fields(self, file_type: str = "image_exif") -> Dict:
        return _METADATA_FIELDS.get(file_type, _METADATA_FIELDS["image_exif"])

    def list_detection_methods(self) -> Dict:
        return {k: {"name": v["name"], "accuracy": v["accuracy"], "tools": v["tools"]}
                for k, v in _DETECTION_METHODS.items()}

    def simulate_metadata_forge(
        self,
        file_type: str,
        target_date: Optional[str],
        target_location: Optional[str],
        target_author: Optional[str],
        target_device: Optional[str],
    ) -> Dict:
        result_id = str(uuid.uuid4())
        fields_map = _METADATA_FIELDS.get(file_type, _METADATA_FIELDS["image_exif"])

        forged = {}
        if file_type == "image_exif":
            forged["DateTime"]        = target_date or (datetime.utcnow() - timedelta(days=random.randint(1,365))).strftime("%Y:%m:%d %H:%M:%S")
            forged["DateTimeOriginal"]= forged["DateTime"]
            forged["Make"]            = (target_device or "Apple").split()[0]
            forged["Model"]           = target_device or "iPhone 14 Pro"
            forged["Software"]        = "16.5.1"
            if target_location:
                coords = {"Paris": (48.8566, 2.3522), "London": (51.5074, -0.1278), "Berlin": (52.5200, 13.4050)}
                c = coords.get(target_location, (48.8566, 2.3522))
                forged["GPS_latitude"]  = c[0]
                forged["GPS_longitude"] = c[1]
        elif file_type == "pdf_metadata":
            forged["Author"]      = target_author or "Jean Dupont"
            forged["Creator"]     = "Microsoft Word 2016"
            forged["Producer"]    = "Adobe PDF Library 15.0"
            forged["CreationDate"]= target_date or "D:20231015094523+02'00'"
            forged["ModDate"]     = target_date or "D:20231015094523+02'00'"
            forged["Company"]     = "Ministère de l'Intérieur"
        elif file_type == "office_metadata":
            forged["Author"]         = target_author or "Admin"
            forged["LastModifiedBy"] = target_author or "Admin"
            forged["Company"]        = "Direction Générale"
            forged["Created"]        = target_date or datetime.utcnow().isoformat()

        detection_tips = [
            "ExifTool révèle les champs modifiés si les timestamps internes sont incohérents",
            "Les hash SHA256 du fichier changeront — impossible à falsifier sans re-génération complète",
            "Les signatures numériques (PDF signés) seront invalides après modification",
        ]

        result = {
            "result_id":    result_id,
            "file_type":    file_type,
            "forged_metadata": forged,
            "fields_available": list(fields_map.keys()),
            "tool_commands": {
                "read":   f"exiftool -all {'{file}'}",
                "write":  f"exiftool -DateTime='{forged.get('DateTime','...')}' -Make='{forged.get('Make','Apple')}' {'{file}'}",
                "strip":  f"exiftool -all= {'{file}'}",
            },
            "detection_tips": detection_tips,
            "simulated":    True,
        }
        _RESULTS[result_id] = result
        return result

    def analyze_document_authenticity(self, metadata_json: str) -> Dict:
        try:
            meta = json.loads(metadata_json)
        except Exception:
            meta = {}

        findings = []
        risk_score = 0

        author = str(meta.get("Author","")).lower()
        creator = str(meta.get("Creator",""))
        created = str(meta.get("CreationDate","") or meta.get("Created",""))
        modified = str(meta.get("ModDate","") or meta.get("Modified",""))

        if author in ["admin","administrator","user","unknown",""]:
            findings.append({"severity":"HIGH","issue":f"Auteur générique/vide: '{author}'"})
            risk_score += 30

        if created and modified and created > modified:
            findings.append({"severity":"CRITICAL","issue":"Date de création postérieure à la modification — impossible normalement"})
            risk_score += 50

        if "word" in creator.lower() and "pdf" in str(meta.get("Producer","")).lower():
            pass
        elif creator and "adobe" in creator.lower() and "word" not in creator.lower():
            findings.append({"severity":"MEDIUM","issue":"Créateur Adobe Direct — document créé directement en PDF (pas converti)"})
            risk_score += 10

        revision = meta.get("Revision","")
        if str(revision) == "1" and created:
            findings.append({"severity":"LOW","issue":"Révision 1 — document jamais modifié ou metadata réinitialisée"})
            risk_score += 5

        grade = "SUSPICIOUS" if risk_score >= 50 else ("QUESTIONABLE" if risk_score >= 20 else "LIKELY_AUTHENTIC")

        return {
            "metadata_analyzed": meta,
            "findings": findings,
            "risk_score": risk_score,
            "verdict": grade,
            "recommendation": "Vérifier via canal officiel" if grade != "LIKELY_AUTHENTIC" else "Métadonnées cohérentes",
            "simulated": True,
        }

    def detect_synthetic_content(
        self,
        content_type: str,
        indicators: List[str],
    ) -> Dict:
        methods = []
        confidence = 0.0

        for indicator in indicators:
            for method_id, method in _DETECTION_METHODS.items():
                if any(t.lower() in indicator.lower() for t in ["image","video","pdf","texte","doc"]):
                    methods.append({"method": method_id, "name": method["name"], "accuracy": method["accuracy"]})
                    confidence = max(confidence, method["accuracy"])

        if not methods:
            methods = list(_DETECTION_METHODS.items())[:2]
            confidence = 0.75

        return {
            "content_type":  content_type,
            "indicators":    indicators,
            "detection_methods": methods,
            "confidence":    round(confidence, 2),
            "verdict":       "SYNTHETIC" if confidence > 0.8 else ("SUSPICIOUS" if confidence > 0.6 else "AUTHENTIC"),
            "simulated":     True,
        }

    def get_result(self, result_id: str) -> Dict:
        return _RESULTS.get(result_id, {"error": "not_found"})
