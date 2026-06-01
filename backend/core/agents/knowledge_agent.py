"""
KnowledgeAgent — Piliers 3 & 5 : gestion de la base de connaissances.
Ingère, catégorise et recherche dans la mémoire long terme.
"""
from __future__ import annotations

import json
from typing import Optional
from sqlalchemy.orm import Session

from core.agents.base_agent import BaseAgent
from core.learning.learning_engine import learning_engine, VALID_CATEGORIES


_KEYWORDS = [
    "apprends", "apprendre", "mémorise", "mémoriser", "connaissance",
    "note", "notes", "résumé", "résume", "sais-tu", "sais tu",
    "document", "documenter", "ingère", "ingérer", "enregistre",
    "enregistrer", "sauvegarde", "sauvegarder", "retiens",
    "base de connaissances", "knowledge", "que sais-tu", "que sais tu",
    "recherche dans", "cherche dans ta mémoire", "qu'est-ce que tu sais",
]


class KnowledgeAgent(BaseAgent):
    name = "knowledge"
    description = "Gestion de la base de connaissances — ingestion, recherche, catégorisation"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return any(kw in t for kw in _KEYWORDS)

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        """
        Dispatch selon l'intention :
        - ingestion si le contexte contient du contenu à mémoriser
        - recherche sinon
        """
        ctx = context or {}
        db: Optional[Session] = ctx.get("db")
        t = task.lower().strip()

        # ── Ingestion explicite ───────────────────────────────────────────────
        if any(kw in t for kw in ["apprends", "mémorise", "mémoriser", "ingère", "enregistre",
                                   "retiens", "sauvegarde", "note que", "document"]):
            content = ctx.get("content") or self._extract_content(task)
            if not content:
                return self._result(
                    False,
                    "Fournis le contenu à mémoriser. Ex : 'Apprends que Python utilise l'indentation...'"
                )

            category = ctx.get("category") or self._detect_category(task, content)
            title = ctx.get("title") or ""
            tags = ctx.get("tags") or []
            importance = float(ctx.get("importance", 0.5))

            if db:
                result = learning_engine.ingest_text(
                    db=db,
                    text=content,
                    source="agent_knowledge",
                    category=category,
                    title=title,
                    tags=tags,
                    importance=importance,
                )
                self._log_action(db, "ingest", task, result)
                if result.get("success"):
                    return self._result(
                        True,
                        f"Connaissance enregistrée (ID {result['entry_id']}) :\n"
                        f"Titre    : {result['title']}\n"
                        f"Catégorie: {result['category']}\n"
                        f"Résumé   : {result.get('summary', '')[:200]}",
                        result,
                    )
                return self._result(False, f"Erreur lors de l'ingestion : {result.get('error')}")
            return self._result(False, "Base de données non disponible.")

        # ── Recherche dans la base ────────────────────────────────────────────
        if any(kw in t for kw in ["sais-tu", "sais tu", "que sais", "recherche", "cherche",
                                   "connais-tu", "connais tu"]):
            query = self._extract_query(task)
            if not query:
                query = task

            if db:
                results = learning_engine.search_knowledge(db=db, query=query, limit=5)
                self._log_action(db, "search", task, {"query": query, "results": len(results)})
                if results:
                    lines = [f"Trouvé {len(results)} entrée(s) pour '{query}' :"]
                    for i, r in enumerate(results, 1):
                        lines.append(f"\n[{i}] {r['title']} ({r['category']})")
                        lines.append(f"    {r.get('summary', r.get('content_preview', ''))[:200]}")
                    return self._result(True, "\n".join(lines), {"results": results})
                return self._result(
                    True,
                    f"Aucune connaissance trouvée pour '{query}'. "
                    "Tu peux m'en apprendre davantage en disant 'Apprends que...'",
                    {"results": []},
                )
            return self._result(False, "Base de données non disponible.")

        # ── Résumé de la base ─────────────────────────────────────────────────
        if any(kw in t for kw in ["résumé", "statistiques", "stats", "base de connaissances"]):
            if db:
                summary = learning_engine.get_learning_summary(db=db)
                lines = ["Base de connaissances :"]
                lines.append(f"  Total : {summary.get('total_entries', 0)} entrées")
                for cat, count in summary.get("by_category", {}).items():
                    lines.append(f"  {cat}: {count}")
                return self._result(True, "\n".join(lines), summary)
            return self._result(False, "Base de données non disponible.")

        # ── Fallback : recherche générale ─────────────────────────────────────
        if db:
            results = learning_engine.search_knowledge(db=db, query=task, limit=3)
            if results:
                lines = [f"Connaissances relatives à ta demande :"]
                for r in results:
                    lines.append(f"  - {r['title']}: {r.get('summary', '')[:150]}")
                return self._result(True, "\n".join(lines), {"results": results})

        return self._result(
            False,
            "Je n'ai pas pu traiter cette demande. Utilise 'Apprends que...' pour m'enseigner quelque chose."
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_content(self, task: str) -> str:
        """Extrait le contenu à mémoriser après les mots-clés déclencheurs."""
        import re
        patterns = [
            r"(?:apprends?|mémorise?|enregistre?|retiens?|note que?|sache que?|ingère?)\s*:?\s*(.+)",
            r"(?:que|:)\s+(.+)",
        ]
        for pat in patterns:
            m = re.search(pat, task, re.IGNORECASE | re.DOTALL)
            if m:
                return m.group(1).strip()
        return task

    def _extract_query(self, task: str) -> str:
        """Extrait la requête de recherche."""
        import re
        patterns = [
            r"(?:sais-tu|sais tu|connais-tu|connais tu|que sais tu de|recherche?)\s+(?:sur\s+|quoi que\s+)?(.+)",
            r"(?:cherche dans|trouve dans)\s+(?:ta mémoire\s+)?(.+)",
        ]
        for pat in patterns:
            m = re.search(pat, task, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        # Retirer les mots-clés déclencheurs et retourner le reste
        for kw in _KEYWORDS:
            task = task.lower().replace(kw, "").strip()
        return task.strip() or task

    def _detect_category(self, task: str, content: str) -> str:
        """Détecte automatiquement la catégorie basée sur les mots-clés."""
        text = (task + " " + content).lower()
        category_keywords = {
            "cyber": ["hack", "exploit", "vulnérabilité", "cve", "sécurité", "pentest", "malware",
                      "nmap", "metasploit", "ctf", "payload", "injection", "xss", "sqli"],
            "programmation": ["python", "javascript", "code", "fonction", "classe", "algorithme",
                               "api", "framework", "library", "développement", "dev", "git",
                               "bash", "script", "rust", "go", "java", "c++", "typescript"],
            "ai": ["ia", "ai", "intelligence artificielle", "llm", "gpt", "claude", "machine learning",
                   "deep learning", "neural", "transformer", "rag", "embedding", "prompt"],
            "sciences": ["physique", "chimie", "biologie", "mathématiques", "statistique",
                         "quantum", "relativity", "formule", "théorème"],
            "business": ["business", "startup", "marketing", "finance", "stratégie", "client",
                         "revenue", "croissance", "product"],
            "projets": ["projet", "aegis", "oeil de dieu", "backend", "frontend", "architecture",
                        "déploiement", "production"],
        }
        scores = {}
        for cat, kws in category_keywords.items():
            score = sum(1 for kw in kws if kw in text)
            if score > 0:
                scores[cat] = score
        if scores:
            return max(scores, key=scores.get)
        return "general"

    def _log_action(self, db, action_type: str, task: str, result: dict) -> None:
        """Journalise silencieusement l'action."""
        try:
            from core.self.self_observer import log_action
            log_action(
                db=db,
                agent_name=self.name,
                action_type=action_type,
                description=task[:200],
                input_data={"task": task[:500]},
                output_data=result,
                status="success" if result.get("success", True) else "error",
            )
        except Exception:
            pass


knowledge_agent = KnowledgeAgent()
