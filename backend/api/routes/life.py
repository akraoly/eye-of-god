"""
Routes /api/life — Gestion vie personnelle (objectifs, habitudes).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.dependencies import get_db
from database.models import LifeGoal, LifeHabit

router = APIRouter()


# ── Schémas ───────────────────────────────────────────────────────────────────

class GoalCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: str = Field("", max_length=2000)
    category: str = Field("general")
    priority: int = Field(3, ge=1, le=4, description="1=critique, 2=haute, 3=moyenne, 4=basse")
    deadline: Optional[str] = Field(None, description="ISO date ou DD/MM/YYYY")


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = Field(None, description="active|paused|done|abandoned")
    priority: Optional[int] = Field(None, ge=1, le=4)
    progress: Optional[int] = Field(None, ge=0, le=100)
    deadline: Optional[str] = None


class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=300)
    description: str = Field("", max_length=1000)
    frequency: str = Field("daily", description="daily|weekly|monthly")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_deadline(deadline_str: Optional[str]) -> Optional[datetime]:
    if not deadline_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(deadline_str, fmt)
        except ValueError:
            continue
    return None


def _goal_to_dict(g: LifeGoal) -> dict:
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


def _habit_to_dict(h: LifeHabit) -> dict:
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


def _log(db, agent, action, desc, data):
    try:
        from core.self.self_observer import log_action
        log_action(db=db, agent_name=agent, action_type=action,
                   description=desc, input_data={}, output_data=data, status="success")
    except Exception:
        pass


# ── Objectifs ─────────────────────────────────────────────────────────────────

@router.get("/goals")
async def list_goals(
    status: Optional[str] = Query(None, description="active|paused|done|abandoned|all"),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Liste les objectifs de vie."""
    q = db.query(LifeGoal)
    if status and status != "all":
        q = q.filter(LifeGoal.status == status)
    if category:
        q = q.filter(LifeGoal.category == category)
    goals = q.order_by(LifeGoal.priority.asc(), LifeGoal.created_at.desc()).all()
    return {"goals": [_goal_to_dict(g) for g in goals], "count": len(goals)}


@router.post("/goals", status_code=201)
async def create_goal(body: GoalCreate, db: Session = Depends(get_db)):
    """Crée un nouvel objectif."""
    goal = LifeGoal(
        title=body.title,
        description=body.description,
        category=body.category,
        status="active",
        priority=body.priority,
        progress=0,
        deadline=_parse_deadline(body.deadline),
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(goal)
    db.commit()
    _log(db, "life_api", "create_goal", body.title, {"goal_id": goal.id})
    return _goal_to_dict(goal)


@router.put("/goals/{goal_id}")
async def update_goal(
    goal_id: int,
    body: GoalUpdate,
    db: Session = Depends(get_db),
):
    """Met à jour un objectif (titre, description, status, progress, deadline...)."""
    goal = db.query(LifeGoal).filter(LifeGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Objectif {goal_id} introuvable.")

    if body.title is not None:
        goal.title = body.title
    if body.description is not None:
        goal.description = body.description
    if body.category is not None:
        goal.category = body.category
    if body.status is not None:
        valid_statuses = ("active", "paused", "done", "abandoned")
        if body.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Status invalide. Valeurs : {valid_statuses}")
        goal.status = body.status
    if body.priority is not None:
        goal.priority = body.priority
    if body.progress is not None:
        goal.progress = body.progress
        if body.progress == 100:
            goal.status = "done"
    if body.deadline is not None:
        goal.deadline = _parse_deadline(body.deadline)

    goal.updated_at = datetime.utcnow()
    db.commit()
    _log(db, "life_api", "update_goal", f"goal {goal_id}", {"goal_id": goal_id})
    return _goal_to_dict(goal)


@router.delete("/goals/{goal_id}")
async def delete_goal(goal_id: int, db: Session = Depends(get_db)):
    """Supprime un objectif."""
    goal = db.query(LifeGoal).filter(LifeGoal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail=f"Objectif {goal_id} introuvable.")
    title = goal.title
    db.delete(goal)
    db.commit()
    _log(db, "life_api", "delete_goal", f"goal {goal_id}", {"deleted_title": title})
    return {"deleted": True, "id": goal_id, "title": title}


# ── Habitudes ─────────────────────────────────────────────────────────────────

@router.get("/habits")
async def list_habits(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Liste les habitudes."""
    q = db.query(LifeHabit)
    if active_only:
        q = q.filter(LifeHabit.active == 1)
    habits = q.order_by(LifeHabit.streak.desc(), LifeHabit.created_at.desc()).all()
    return {"habits": [_habit_to_dict(h) for h in habits], "count": len(habits)}


@router.post("/habits", status_code=201)
async def create_habit(body: HabitCreate, db: Session = Depends(get_db)):
    """Crée une nouvelle habitude."""
    valid_freqs = ("daily", "weekly", "monthly")
    if body.frequency not in valid_freqs:
        raise HTTPException(status_code=400, detail=f"Fréquence invalide. Valeurs : {valid_freqs}")

    habit = LifeHabit(
        name=body.name,
        description=body.description,
        frequency=body.frequency,
        streak=0,
        active=1,
        created_at=datetime.utcnow(),
    )
    db.add(habit)
    db.commit()
    _log(db, "life_api", "create_habit", body.name, {"habit_id": habit.id})
    return _habit_to_dict(habit)


@router.post("/habits/{habit_id}/done")
async def mark_habit_done(habit_id: int, db: Session = Depends(get_db)):
    """Marque une habitude comme accomplie aujourd'hui et incrémente le streak."""
    habit = db.query(LifeHabit).filter(LifeHabit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail=f"Habitude {habit_id} introuvable.")

    now = datetime.utcnow()
    if habit.last_done:
        from datetime import timedelta
        delta = (now - habit.last_done).days
        freq_windows = {"daily": 2, "weekly": 9, "monthly": 35}
        window = freq_windows.get(habit.frequency, 2)
        if delta <= window:
            habit.streak += 1
        else:
            habit.streak = 1
    else:
        habit.streak = 1

    habit.last_done = now
    db.commit()
    _log(db, "life_api", "mark_done", f"habit {habit_id}", {"streak": habit.streak})
    return {**_habit_to_dict(habit), "message": f"Streak : {habit.streak}"}


@router.delete("/habits/{habit_id}")
async def delete_habit(habit_id: int, db: Session = Depends(get_db)):
    """Désactive (soft delete) une habitude."""
    habit = db.query(LifeHabit).filter(LifeHabit.id == habit_id).first()
    if not habit:
        raise HTTPException(status_code=404, detail=f"Habitude {habit_id} introuvable.")
    habit.active = 0
    db.commit()
    return {"deactivated": True, "id": habit_id, "name": habit.name}


# ── Dashboard ─────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def life_dashboard(db: Session = Depends(get_db)):
    """Vue d'ensemble complète de la vie personnelle."""
    active_goals = db.query(LifeGoal).filter(LifeGoal.status == "active").order_by(
        LifeGoal.priority.asc()
    ).all()

    done_goals = db.query(LifeGoal).filter(LifeGoal.status == "done").count()
    total_goals = db.query(LifeGoal).count()

    active_habits = db.query(LifeHabit).filter(LifeHabit.active == 1).order_by(
        LifeHabit.streak.desc()
    ).all()

    overdue = [
        _goal_to_dict(g) for g in active_goals
        if g.deadline and g.deadline < datetime.utcnow()
    ]

    top_streak_habit = active_habits[0] if active_habits else None

    return {
        "goals": {
            "active": [_goal_to_dict(g) for g in active_goals],
            "overdue": overdue,
            "total": total_goals,
            "done": done_goals,
            "completion_rate": round(done_goals / total_goals, 2) if total_goals > 0 else 0,
        },
        "habits": {
            "active": [_habit_to_dict(h) for h in active_habits],
            "total": len(active_habits),
            "top_streak": _habit_to_dict(top_streak_habit) if top_streak_habit else None,
        },
    }
