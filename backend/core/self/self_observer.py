"""
SelfObserver — Pilier 8 : auto-observation et introspection du système.
Analyse les ActionLog, identifie les patterns, génère un rapport de santé.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional
from collections import defaultdict
from sqlalchemy.orm import Session

from database.models import ActionLog, Conversation, KnowledgeEntry, LearningEvent, LifeGoal, LifeHabit, Memory


class SelfObserver:
    """Analyse le comportement du système et génère des rapports d'introspection."""

    # ── Analyse principale ────────────────────────────────────────────────────

    def analyze(self, db: Session, days: int = 7) -> dict:
        """
        Analyse les ActionLog des N derniers jours.
        Retourne : {"healthy": [...], "issues": [...], "suggestions": [...]}
        """
        try:
            since = datetime.utcnow() - timedelta(days=days)
            logs = db.query(ActionLog).filter(
                ActionLog.executed_at >= since
            ).order_by(ActionLog.executed_at.desc()).all()

            if not logs:
                return {
                    "healthy": ["Aucune activité enregistrée dans les {} derniers jours.".format(days)],
                    "issues": [],
                    "suggestions": ["Commencer à utiliser le système pour générer des métriques."],
                    "stats": self._empty_stats(),
                }

            # Statistiques par agent
            agent_stats = defaultdict(lambda: {"success": 0, "error": 0, "skipped": 0, "total": 0})
            action_types = defaultdict(int)
            errors = []

            for log in logs:
                agent_stats[log.agent_name]["total"] += 1
                agent_stats[log.agent_name][log.status] = agent_stats[log.agent_name].get(log.status, 0) + 1
                action_types[log.action_type] += 1
                if log.status == "error":
                    errors.append({
                        "agent": log.agent_name,
                        "action": log.action_type,
                        "description": log.description or "",
                        "at": log.executed_at.isoformat() if log.executed_at else "",
                    })

            # Analyse de santé
            healthy = []
            issues = []
            suggestions = []

            total_actions = len(logs)
            total_errors = sum(1 for l in logs if l.status == "error")
            error_rate = total_errors / total_actions if total_actions > 0 else 0

            if error_rate < 0.1:
                healthy.append(f"Taux d'erreur faible : {error_rate:.1%} ({total_errors}/{total_actions})")
            elif error_rate < 0.3:
                issues.append(f"Taux d'erreur modéré : {error_rate:.1%} ({total_errors}/{total_actions})")
                suggestions.append("Investiguer les erreurs fréquentes dans les logs d'action.")
            else:
                issues.append(f"Taux d'erreur élevé : {error_rate:.1%} — attention requise.")
                suggestions.append("Vérifier la configuration des agents défaillants.")

            # Agents les plus actifs
            most_active = sorted(agent_stats.items(), key=lambda x: x[1]["total"], reverse=True)
            if most_active:
                top_agent = most_active[0][0]
                healthy.append(f"Agent le plus actif : {top_agent} ({most_active[0][1]['total']} actions)")

            # Agents jamais utilisés
            known_agents = {"cyber", "code", "life", "knowledge", "system", "orchestrator"}
            used_agents = set(agent_stats.keys())
            unused = known_agents - used_agents
            if unused:
                suggestions.append(f"Agents non utilisés récemment : {', '.join(unused)}")

            # Volume d'apprentissage
            knowledge_count = db.query(KnowledgeEntry).count()
            if knowledge_count > 0:
                healthy.append(f"Base de connaissances : {knowledge_count} entrées")
            else:
                suggestions.append("Alimenter la base de connaissances avec /api/knowledge/ingest")

            # Objectifs de vie
            active_goals = db.query(LifeGoal).filter(LifeGoal.status == "active").count()
            if active_goals > 0:
                healthy.append(f"Objectifs actifs suivis : {active_goals}")
                overdue = db.query(LifeGoal).filter(
                    LifeGoal.status == "active",
                    LifeGoal.deadline < datetime.utcnow(),
                    LifeGoal.deadline.isnot(None),
                ).count()
                if overdue > 0:
                    issues.append(f"{overdue} objectif(s) en retard sur leur deadline.")
                    suggestions.append("Mettre à jour ou reprogrammer les objectifs en retard.")

            # Habitudes
            active_habits = db.query(LifeHabit).filter(LifeHabit.active == 1).count()
            if active_habits > 0:
                healthy.append(f"Habitudes trackées : {active_habits}")

            # Action types fréquents
            top_actions = sorted(action_types.items(), key=lambda x: x[1], reverse=True)[:3]
            if top_actions:
                healthy.append("Actions les plus fréquentes : " + ", ".join(
                    f"{a}({n})" for a, n in top_actions
                ))

            return {
                "healthy": healthy,
                "issues": issues,
                "suggestions": suggestions,
                "stats": {
                    "total_actions": total_actions,
                    "total_errors": total_errors,
                    "error_rate": round(error_rate, 3),
                    "agents": {k: dict(v) for k, v in agent_stats.items()},
                    "top_action_types": dict(top_actions),
                    "recent_errors": errors[:5],
                    "period_days": days,
                },
            }
        except Exception as e:
            return {
                "healthy": [],
                "issues": [f"Erreur lors de l'analyse : {str(e)}"],
                "suggestions": [],
                "stats": self._empty_stats(),
            }

    def generate_report(self, db: Session) -> str:
        """Rapport texte formaté pour l'IA."""
        try:
            analysis = self.analyze(db)
            stats = analysis.get("stats", {})
            lines = [
                "=" * 50,
                "  RAPPORT D'AUTO-OBSERVATION — L'OEIL DE DIEU",
                "=" * 50,
                f"  Période analysée : {stats.get('period_days', 7)} derniers jours",
                f"  Généré le : {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
                "",
                "── SANTÉ DU SYSTÈME ──────────────────────────",
            ]

            for item in analysis.get("healthy", []):
                lines.append(f"  [OK] {item}")

            if analysis.get("issues"):
                lines.append("")
                lines.append("── PROBLÈMES DÉTECTÉS ──────────────────────────")
                for item in analysis["issues"]:
                    lines.append(f"  [!]  {item}")

            if analysis.get("suggestions"):
                lines.append("")
                lines.append("── SUGGESTIONS D'AMÉLIORATION ─────────────────")
                for item in analysis["suggestions"]:
                    lines.append(f"  [>]  {item}")

            lines.append("")
            lines.append("── STATISTIQUES ───────────────────────────────")
            lines.append(f"  Actions totales  : {stats.get('total_actions', 0)}")
            lines.append(f"  Erreurs          : {stats.get('total_errors', 0)}")
            lines.append(f"  Taux d'erreur    : {stats.get('error_rate', 0):.1%}")

            agents = stats.get("agents", {})
            if agents:
                lines.append("")
                lines.append("── ACTIVITÉ PAR AGENT ─────────────────────────")
                for agent, data in sorted(agents.items(), key=lambda x: x[1].get("total", 0), reverse=True):
                    total = data.get("total", 0)
                    success = data.get("success", 0)
                    error = data.get("error", 0)
                    lines.append(f"  {agent:15} : {total:4} actions | {success:3} succès | {error:3} erreurs")

            lines.append("=" * 50)
            return "\n".join(lines)
        except Exception as e:
            return f"Erreur génération rapport : {e}"

    def get_recent_actions(self, db: Session, limit: int = 50) -> list:
        """Retourne les dernières actions journalisées."""
        try:
            logs = db.query(ActionLog).order_by(
                ActionLog.executed_at.desc()
            ).limit(limit).all()

            return [
                {
                    "id": l.id,
                    "agent": l.agent_name,
                    "action_type": l.action_type,
                    "description": l.description or "",
                    "status": l.status,
                    "executed_at": l.executed_at.isoformat() if l.executed_at else None,
                }
                for l in logs
            ]
        except Exception:
            return []

    def get_global_stats(self, db: Session) -> dict:
        """Statistiques globales toutes périodes confondues."""
        try:
            total_actions = db.query(ActionLog).count()
            total_knowledge = db.query(KnowledgeEntry).count()
            total_learning = db.query(LearningEvent).count()
            total_goals = db.query(LifeGoal).count()
            active_goals = db.query(LifeGoal).filter(LifeGoal.status == "active").count()
            total_habits = db.query(LifeHabit).filter(LifeHabit.active == 1).count()

            return {
                "actions": total_actions,
                "knowledge_entries": total_knowledge,
                "learning_events": total_learning,
                "goals_total": total_goals,
                "goals_active": active_goals,
                "habits_active": total_habits,
            }
        except Exception as e:
            return {"error": str(e)}

    # ── Analyse IA (Claude) ───────────────────────────────────────────────────

    async def ai_analysis(self, db: Session, days: int = 7) -> dict:
        """
        Analyse approfondie par Claude — détecte les patterns, évalue la santé
        globale et génère des recommandations priorisées.
        """
        from core.llm.client import LLMClient

        try:
            # Collecte des données brutes
            analysis = self.analyze(db=db, days=days)
            global_stats = self.get_global_stats(db=db)
            recent_actions = self.get_recent_actions(db=db, limit=100)
            stats = analysis.get("stats", {})

            # Erreurs récentes groupées par agent
            errors_by_agent: dict = defaultdict(list)
            for a in recent_actions:
                if a["status"] == "error":
                    errors_by_agent[a["agent"]].append(a["description"][:120])

            # Patterns de messages utilisateur (dernières conversations)
            try:
                convs = db.query(Conversation).order_by(
                    Conversation.timestamp.desc()
                ).limit(20).all()
                user_topics = [c.user_message[:100] for c in convs]
            except Exception:
                user_topics = []

            # Mémoires existantes
            try:
                memories = db.query(Memory).order_by(Memory.importance.desc()).limit(10).all()
                mem_keys = [f"{m.memory_type}:{m.key}" for m in memories]
            except Exception:
                mem_keys = []

            # Construction du contexte pour Claude
            agents_summary = []
            for agent, data in sorted(stats.get("agents", {}).items(),
                                       key=lambda x: x[1].get("total", 0), reverse=True):
                total = data.get("total", 0)
                errors = data.get("error", 0)
                skipped = data.get("skipped", 0)
                success = data.get("success", 0)
                rate = errors / total if total > 0 else 0
                agents_summary.append(
                    f"- {agent}: {total} actions, {success} succès, {errors} erreurs "
                    f"({rate:.0%}), {skipped} skippés"
                )

            errors_summary = []
            for agent, msgs in errors_by_agent.items():
                sample = msgs[:3]
                errors_summary.append(f"- {agent}: {', '.join(repr(m) for m in sample)}")

            prompt_data = f"""Tu es l'auto-analyste de L'Œil de Dieu, un assistant IA personnel sous Linux.
Voici les données du système sur les {days} derniers jours :

## STATISTIQUES GLOBALES
- Actions totales (toutes périodes) : {global_stats.get('actions', 0)}
- Base de connaissances : {global_stats.get('knowledge_entries', 0)} entrées
- Événements d'apprentissage : {global_stats.get('learning_events', 0)}
- Objectifs de vie actifs : {global_stats.get('goals_active', 0)}/{global_stats.get('goals_total', 0)}
- Habitudes trackées : {global_stats.get('habits_active', 0)}

## ACTIVITÉ SUR {days} JOURS
- Actions totales : {stats.get('total_actions', 0)}
- Erreurs : {stats.get('total_errors', 0)} ({stats.get('error_rate', 0):.1%})
- Types d'action : {stats.get('top_action_types', {})}

## PAR AGENT
{chr(10).join(agents_summary) or '(aucun)'}

## ERREURS RÉCENTES PAR AGENT
{chr(10).join(errors_summary) or '(aucune erreur)'}

## SUJETS ABORDÉS PAR L'UTILISATEUR (20 derniers)
{chr(10).join(f'- {t}' for t in user_topics[:15]) or '(aucun)'}

## MÉMOIRES IMPORTANTES
{chr(10).join(mem_keys) or '(aucune)'}

## ANALYSE RÈGLES (déjà calculée)
Points positifs : {analysis.get('healthy', [])}
Problèmes : {analysis.get('issues', [])}
Suggestions règles : {analysis.get('suggestions', [])}"""

            system = """Tu es l'introspection de L'Œil de Dieu, assistant IA personnel.
IMPORTANT : Réponds UNIQUEMENT avec du JSON valide, sans aucun texte avant ou après.
Pas de markdown, pas de commentaires, pas de trailing commas.

Format exact :
{"health_score":75,"health_label":"Bon","summary":"2-3 phrases sur l'état général.","agent_analysis":[{"agent":"orchestrator","status":"ok","insight":"Observation concrète sur cet agent."}],"patterns":["Pattern comportemental observé"],"critical_issues":["Problème critique si présent"],"recommendations":[{"priority":1,"category":"Performance","action":"Action concrète à faire","impact":"Bénéfice attendu"}],"growth_opportunities":["Opportunité non urgente"]}

Labels health_label : "Critique"(0-20) "Dégradé"(21-40) "Stable"(41-60) "Bon"(61-80) "Excellent"(81-100)
Status agents : "ok" "warning" "critical"
Priorité recommandations : 1=critique 2=élevé 3=moyen 4=faible 5=info
Catégories : Performance, Utilisation, Mémoire, Sécurité, Workflow, Apprentissage"""

            llm = LLMClient()
            raw = await llm.complete(
                messages=[{"role": "user", "content": prompt_data}],
                system=system,
                max_tokens=2000,
            )

            # Parser le JSON (stratégies progressives)
            import re as _re

            def _try_parse(text: str):
                """Tente de parser le JSON avec nettoyage progressif."""
                # 1. Parse direct
                try: return json.loads(text)
                except Exception: pass
                # 2. Nettoyer trailing commas
                cleaned = _re.sub(r',\s*([}\]])', r'\1', text)
                try: return json.loads(cleaned)
                except Exception: pass
                # 3. Enlever les retours à la ligne dans les strings
                cleaned2 = _re.sub(r'(?<=")([^"]*?)\n([^"]*?)(?=")', r'\1 \2', cleaned)
                try: return json.loads(cleaned2)
                except Exception: pass
                return None

            result = None
            # Chercher le JSON entre ```json ... ``` ou { ... }
            code_block = _re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', raw)
            if code_block:
                result = _try_parse(code_block.group(1))

            if not result:
                brace_match = _re.search(r'\{[\s\S]*\}', raw)
                if brace_match:
                    result = _try_parse(brace_match.group(0))

            if not result:
                # Fallback: extraire les champs critiques via regex
                result = {"health_score": 50, "health_label": "Analyse partielle",
                          "summary": "Format JSON invalide — données partielles extraites.",
                          "agent_analysis": [], "patterns": [], "critical_issues": [],
                          "recommendations": [], "growth_opportunities": []}
                for field, is_int in [("health_score", True), ("health_label", False)]:
                    m = _re.search(rf'"{field}"\s*:\s*"?([^",\n}}]+)"?', raw)
                    if m:
                        v = m.group(1).strip().strip('"')
                        result[field] = int(v) if is_int and v.isdigit() else v
                # Extraire summary entre guillemets
                sm = _re.search(r'"summary"\s*:\s*"([^"]{10,})"', raw)
                if sm: result["summary"] = sm.group(1)

            result["generated_at"] = datetime.utcnow().isoformat()
            result["period_days"] = days
            return result

        except Exception as e:
            return {
                "health_score": 0,
                "health_label": "Erreur",
                "summary": f"Erreur lors de l'analyse IA : {e}",
                "agent_analysis": [],
                "patterns": [],
                "critical_issues": [str(e)],
                "recommendations": [],
                "growth_opportunities": [],
                "generated_at": datetime.utcnow().isoformat(),
                "period_days": days,
            }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _empty_stats(self) -> dict:
        return {
            "total_actions": 0,
            "total_errors": 0,
            "error_rate": 0,
            "agents": {},
            "top_action_types": {},
            "recent_errors": [],
            "period_days": 7,
        }


# Utilitaire pour logger une action depuis n'importe quel agent
def log_action(
    db: Session,
    agent_name: str,
    action_type: str,
    description: str = "",
    input_data: dict = None,
    output_data: dict = None,
    status: str = "success",
) -> None:
    """Journalise une action dans ActionLog — sans lever d'exception."""
    try:
        entry = ActionLog(
            agent_name=agent_name,
            action_type=action_type,
            description=description[:500] if description else "",
            input_data=json.dumps(input_data or {}, ensure_ascii=False)[:2000],
            output_data=json.dumps(output_data or {}, ensure_ascii=False)[:2000],
            status=status,
            executed_at=datetime.utcnow(),
        )
        db.add(entry)
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


self_observer = SelfObserver()
