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

from database.models import ActionLog, KnowledgeEntry, LearningEvent, LifeGoal, LifeHabit


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
