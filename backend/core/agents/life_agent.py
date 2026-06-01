"""
LifeAgent — Pilier 3 : assistant vie personnelle.
Gère objectifs, habitudes, productivité via LifeGoal et LifeHabit.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from core.agents.base_agent import BaseAgent
from database.models import LifeGoal, LifeHabit


_KEYWORDS = [
    "objectif", "objectifs", "habitude", "habitudes", "rappel",
    "tâche", "tâches", "todo", "organisation", "productivité",
    "goal", "goals", "habit", "habits", "agenda", "planning",
    "motivation", "progression", "suivi", "tracker",
    "vie personnelle", "dashboard vie",
]

GOAL_CATEGORIES = ["professionnel", "personnel", "sante", "finance", "apprentissage", "social", "projet", "general"]
PRIORITY_MAP = {"critique": 1, "élevée": 2, "haute": 2, "moyenne": 3, "basse": 4, "faible": 4}
STATUS_MAP_GOAL = {"actif": "active", "active": "active", "pause": "paused", "pausé": "paused",
                    "terminé": "done", "done": "done", "abandonné": "abandoned"}
FREQ_MAP = {"quotidien": "daily", "daily": "daily", "hebdomadaire": "weekly", "weekly": "weekly",
            "mensuel": "monthly", "monthly": "monthly"}


class LifeAgent(BaseAgent):
    name = "life"
    description = "Assistant vie personnelle — objectifs, habitudes, productivité, organisation"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return any(kw in t for kw in _KEYWORDS)

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        ctx = context or {}
        db: Optional[Session] = ctx.get("db")
        t = task.lower().strip()

        if not db:
            return self._result(False, "Base de données non disponible pour l'agent vie.")

        # ── Dashboard ────────────────────────────────────────────────────────
        if any(kw in t for kw in ["dashboard", "résumé", "vue d'ensemble", "bilan", "overview"]):
            return self._dashboard(db)

        # ── Objectifs ────────────────────────────────────────────────────────
        if any(kw in t for kw in ["objectif", "goal", "objectifs", "goals"]):
            if any(kw in t for kw in ["créer", "crée", "nouveau", "ajouter", "ajoute", "add", "new"]):
                return self._create_goal(db, task, ctx)
            if any(kw in t for kw in ["liste", "lister", "voir", "afficher", "show", "list"]):
                return self._list_goals(db, ctx)
            if any(kw in t for kw in ["mise à jour", "mettre à jour", "modifier", "update", "progresser", "avancer"]):
                return self._update_goal(db, task, ctx)
            if any(kw in t for kw in ["supprimer", "delete", "enlever", "remove"]):
                return self._delete_goal(db, ctx)
            # Par défaut : lister
            return self._list_goals(db, ctx)

        # ── Habitudes ────────────────────────────────────────────────────────
        if any(kw in t for kw in ["habitude", "habit", "habitudes", "habits"]):
            if any(kw in t for kw in ["créer", "crée", "nouveau", "ajouter", "ajoute", "add", "new"]):
                return self._create_habit(db, task, ctx)
            if any(kw in t for kw in ["fait", "done", "complété", "terminé", "check", "marquer"]):
                return self._mark_habit_done(db, ctx)
            if any(kw in t for kw in ["liste", "lister", "voir", "afficher", "list", "show"]):
                return self._list_habits(db)
            # Par défaut : lister
            return self._list_habits(db)

        # ── Productivité / Dashboard général ─────────────────────────────────
        if any(kw in t for kw in ["todo", "tâche", "rappel", "organisation", "productivité", "planning"]):
            return self._dashboard(db)

        return self._dashboard(db)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def _dashboard(self, db: Session) -> dict:
        try:
            goals = db.query(LifeGoal).filter(LifeGoal.status == "active").order_by(
                LifeGoal.priority.asc(), LifeGoal.created_at.desc()
            ).limit(10).all()

            habits = db.query(LifeHabit).filter(LifeHabit.active == 1).order_by(
                LifeHabit.streak.desc()
            ).all()

            lines = ["=== DASHBOARD VIE PERSONNELLE ===", ""]

            # Objectifs
            lines.append(f"OBJECTIFS ACTIFS ({len(goals)})")
            if goals:
                priority_labels = {1: "CRITIQUE", 2: "HAUTE", 3: "MOYENNE", 4: "BASSE"}
                for g in goals:
                    prio = priority_labels.get(g.priority, "")
                    deadline_str = ""
                    if g.deadline:
                        days_left = (g.deadline - datetime.utcnow()).days
                        if days_left < 0:
                            deadline_str = f" [EN RETARD de {abs(days_left)} jours]"
                        elif days_left <= 7:
                            deadline_str = f" [Dans {days_left} jours]"
                        else:
                            deadline_str = f" [Deadline: {g.deadline.strftime('%d/%m/%Y')}]"
                    lines.append(
                        f"  [{prio}] {g.title} — {g.progress}%{deadline_str}"
                    )
            else:
                lines.append("  Aucun objectif actif. Crée-en un avec 'Créer objectif : <titre>'")

            lines.append("")

            # Habitudes
            lines.append(f"HABITUDES ACTIVES ({len(habits)})")
            if habits:
                for h in habits:
                    last = ""
                    if h.last_done:
                        days_ago = (datetime.utcnow() - h.last_done).days
                        last = f" | Dernière fois : il y a {days_ago}j"
                    streak_icon = "🔥" if h.streak >= 3 else "  "
                    lines.append(f"  {streak_icon} {h.name} ({h.frequency}) — streak: {h.streak}{last}")
            else:
                lines.append("  Aucune habitude. Crée-en une avec 'Créer habitude : <nom>'")

            lines.append("")

            # Stats
            total_goals = db.query(LifeGoal).count()
            done_goals = db.query(LifeGoal).filter(LifeGoal.status == "done").count()
            lines.append(f"STATS : {done_goals}/{total_goals} objectifs complétés")

            output = "\n".join(lines)
            self._log_action(db, "dashboard", "dashboard", {"goals": len(goals), "habits": len(habits)})
            return self._result(True, output, {"goals": len(goals), "habits": len(habits)})
        except Exception as e:
            return self._result(False, f"Erreur dashboard : {e}")

    # ── Objectifs CRUD ─────────────────────────────────────────────────────────

    def _create_goal(self, db: Session, task: str, ctx: dict) -> dict:
        try:
            title = ctx.get("title") or self._extract_after_colon(task) or task
            description = ctx.get("description", "")
            category = ctx.get("category", "general")
            priority = int(ctx.get("priority", PRIORITY_MAP.get(
                self._extract_priority(task), 3
            )))
            deadline = self._parse_deadline(ctx.get("deadline", ""))

            goal = LifeGoal(
                title=title[:500],
                description=description,
                category=category if category in GOAL_CATEGORIES else "general",
                status="active",
                priority=max(1, min(4, priority)),
                progress=0,
                deadline=deadline,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(goal)
            db.commit()

            self._log_action(db, "create_goal", task, {"goal_id": goal.id, "title": title})
            return self._result(
                True,
                f"Objectif créé (ID {goal.id}) :\n"
                f"  Titre    : {goal.title}\n"
                f"  Catégorie: {goal.category}\n"
                f"  Priorité : {goal.priority}\n"
                f"  Deadline : {goal.deadline.strftime('%d/%m/%Y') if goal.deadline else 'Aucune'}",
                {"goal_id": goal.id, "title": goal.title},
            )
        except Exception as e:
            db.rollback()
            return self._result(False, f"Erreur création objectif : {e}")

    def _list_goals(self, db: Session, ctx: dict) -> dict:
        try:
            status_filter = ctx.get("status", "active")
            q = db.query(LifeGoal)
            if status_filter and status_filter != "all":
                q = q.filter(LifeGoal.status == status_filter)
            goals = q.order_by(LifeGoal.priority.asc(), LifeGoal.created_at.desc()).all()

            if not goals:
                return self._result(True, "Aucun objectif trouvé.", {"goals": []})

            lines = [f"Objectifs ({status_filter}) :"]
            for g in goals:
                deadline_str = g.deadline.strftime("%d/%m/%Y") if g.deadline else "—"
                lines.append(
                    f"  [{g.id}] {g.title} | {g.category} | priorité {g.priority} | "
                    f"{g.progress}% | deadline: {deadline_str} | {g.status}"
                )

            goals_data = [self._goal_to_dict(g) for g in goals]
            return self._result(True, "\n".join(lines), {"goals": goals_data})
        except Exception as e:
            return self._result(False, f"Erreur liste objectifs : {e}")

    def _update_goal(self, db: Session, task: str, ctx: dict) -> dict:
        try:
            goal_id = ctx.get("goal_id") or self._extract_id(task)
            if not goal_id:
                return self._result(False, "Précise l'ID de l'objectif à modifier.")

            goal = db.query(LifeGoal).filter(LifeGoal.id == int(goal_id)).first()
            if not goal:
                return self._result(False, f"Objectif ID {goal_id} introuvable.")

            if "progress" in ctx:
                goal.progress = max(0, min(100, int(ctx["progress"])))
                if goal.progress == 100:
                    goal.status = "done"
            if "title" in ctx:
                goal.title = ctx["title"][:500]
            if "description" in ctx:
                goal.description = ctx["description"]
            if "status" in ctx:
                goal.status = STATUS_MAP_GOAL.get(ctx["status"], ctx["status"])
            if "priority" in ctx:
                goal.priority = max(1, min(4, int(ctx["priority"])))
            if "deadline" in ctx:
                goal.deadline = self._parse_deadline(ctx["deadline"])

            goal.updated_at = datetime.utcnow()
            db.commit()

            self._log_action(db, "update_goal", task, {"goal_id": goal.id})
            return self._result(
                True,
                f"Objectif [{goal.id}] mis à jour : {goal.title} | {goal.progress}% | {goal.status}",
                self._goal_to_dict(goal),
            )
        except Exception as e:
            db.rollback()
            return self._result(False, f"Erreur mise à jour objectif : {e}")

    def _delete_goal(self, db: Session, ctx: dict) -> dict:
        try:
            goal_id = ctx.get("goal_id")
            if not goal_id:
                return self._result(False, "Précise l'ID de l'objectif à supprimer.")
            goal = db.query(LifeGoal).filter(LifeGoal.id == int(goal_id)).first()
            if not goal:
                return self._result(False, f"Objectif ID {goal_id} introuvable.")
            title = goal.title
            db.delete(goal)
            db.commit()
            self._log_action(db, "delete_goal", f"delete goal {goal_id}", {"goal_id": goal_id})
            return self._result(True, f"Objectif '{title}' supprimé.", {"deleted_id": goal_id})
        except Exception as e:
            db.rollback()
            return self._result(False, f"Erreur suppression : {e}")

    # ── Habitudes CRUD ─────────────────────────────────────────────────────────

    def _create_habit(self, db: Session, task: str, ctx: dict) -> dict:
        try:
            name = ctx.get("name") or self._extract_after_colon(task) or task
            description = ctx.get("description", "")
            freq_raw = ctx.get("frequency", "daily")
            frequency = FREQ_MAP.get(freq_raw.lower(), "daily")

            habit = LifeHabit(
                name=name[:300],
                description=description,
                frequency=frequency,
                streak=0,
                active=1,
                created_at=datetime.utcnow(),
            )
            db.add(habit)
            db.commit()

            self._log_action(db, "create_habit", task, {"habit_id": habit.id, "name": name})
            return self._result(
                True,
                f"Habitude créée (ID {habit.id}) :\n"
                f"  Nom       : {habit.name}\n"
                f"  Fréquence : {habit.frequency}\n"
                f"  Streak    : 0",
                {"habit_id": habit.id, "name": habit.name},
            )
        except Exception as e:
            db.rollback()
            return self._result(False, f"Erreur création habitude : {e}")

    def _list_habits(self, db: Session) -> dict:
        try:
            habits = db.query(LifeHabit).filter(LifeHabit.active == 1).order_by(
                LifeHabit.streak.desc()
            ).all()

            if not habits:
                return self._result(True, "Aucune habitude active.", {"habits": []})

            lines = [f"Habitudes actives ({len(habits)}) :"]
            for h in habits:
                last = h.last_done.strftime("%d/%m") if h.last_done else "jamais"
                lines.append(
                    f"  [{h.id}] {h.name} | {h.frequency} | streak: {h.streak} | dernier: {last}"
                )

            habits_data = [self._habit_to_dict(h) for h in habits]
            return self._result(True, "\n".join(lines), {"habits": habits_data})
        except Exception as e:
            return self._result(False, f"Erreur liste habitudes : {e}")

    def _mark_habit_done(self, db: Session, ctx: dict) -> dict:
        try:
            habit_id = ctx.get("habit_id")
            if not habit_id:
                return self._result(False, "Précise l'ID de l'habitude.")

            habit = db.query(LifeHabit).filter(LifeHabit.id == int(habit_id)).first()
            if not habit:
                return self._result(False, f"Habitude ID {habit_id} introuvable.")

            now = datetime.utcnow()
            # Incrémente le streak si fait dans la fenêtre correcte
            if habit.last_done:
                delta = (now - habit.last_done).days
                if habit.frequency == "daily" and delta <= 2:
                    habit.streak += 1
                elif habit.frequency == "weekly" and delta <= 9:
                    habit.streak += 1
                elif habit.frequency == "monthly" and delta <= 35:
                    habit.streak += 1
                else:
                    habit.streak = 1  # reset streak
            else:
                habit.streak = 1

            habit.last_done = now
            db.commit()

            self._log_action(db, "mark_habit_done", f"habit {habit_id}", {"habit_id": habit_id, "streak": habit.streak})
            return self._result(
                True,
                f"Habitude '{habit.name}' marquée comme faite !\n"
                f"  Streak actuel : {habit.streak} 🔥" if habit.streak >= 3 else
                f"  Streak actuel : {habit.streak}",
                self._habit_to_dict(habit),
            )
        except Exception as e:
            db.rollback()
            return self._result(False, f"Erreur : {e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _extract_after_colon(self, task: str) -> str:
        """Extrait le texte après ':' ou 'créer/ajouter <sujet>'."""
        m = re.search(r":\s*(.+)", task)
        if m:
            return m.group(1).strip()
        m = re.search(r"(?:créer|ajouter|nouveau|créer objectif|créer habitude)\s+(.+)", task, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return ""

    def _extract_id(self, task: str) -> Optional[str]:
        m = re.search(r"\b(?:id|#|numéro)\s*:?\s*(\d+)", task, re.IGNORECASE)
        if m:
            return m.group(1)
        m = re.search(r"\b(\d+)\b", task)
        return m.group(1) if m else None

    def _extract_priority(self, task: str) -> str:
        for kw, prio in PRIORITY_MAP.items():
            if kw in task.lower():
                return kw
        return "moyenne"

    def _parse_deadline(self, deadline_str: str) -> Optional[datetime]:
        if not deadline_str:
            return None
        try:
            # Format ISO
            return datetime.fromisoformat(deadline_str)
        except Exception:
            pass
        try:
            # Format DD/MM/YYYY
            return datetime.strptime(deadline_str, "%d/%m/%Y")
        except Exception:
            pass
        try:
            # "dans N jours"
            m = re.search(r"dans\s+(\d+)\s+(?:jours?|semaines?|mois)", deadline_str.lower())
            if m:
                n = int(m.group(1))
                if "semaine" in deadline_str.lower():
                    return datetime.utcnow() + timedelta(weeks=n)
                elif "mois" in deadline_str.lower():
                    return datetime.utcnow() + timedelta(days=n * 30)
                return datetime.utcnow() + timedelta(days=n)
        except Exception:
            pass
        return None

    def _goal_to_dict(self, g: LifeGoal) -> dict:
        return {
            "id": g.id,
            "title": g.title,
            "description": g.description or "",
            "category": g.category,
            "status": g.status,
            "priority": g.priority,
            "progress": g.progress,
            "deadline": g.deadline.isoformat() if g.deadline else None,
            "created_at": g.created_at.isoformat() if g.created_at else None,
            "updated_at": g.updated_at.isoformat() if g.updated_at else None,
        }

    def _habit_to_dict(self, h: LifeHabit) -> dict:
        return {
            "id": h.id,
            "name": h.name,
            "description": h.description or "",
            "frequency": h.frequency,
            "streak": h.streak,
            "last_done": h.last_done.isoformat() if h.last_done else None,
            "active": bool(h.active),
            "created_at": h.created_at.isoformat() if h.created_at else None,
        }

    def _log_action(self, db: Session, action_type: str, description: str, data: dict) -> None:
        try:
            from core.self.self_observer import log_action
            log_action(
                db=db,
                agent_name=self.name,
                action_type=action_type,
                description=description[:200],
                input_data={"task": description[:300]},
                output_data=data,
                status="success",
            )
        except Exception:
            pass


life_agent = LifeAgent()
