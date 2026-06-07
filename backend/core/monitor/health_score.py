"""
Score de santé global (0-100).
100 = parfait, 0 = système en danger critique.
"""
from __future__ import annotations


def compute_health_score(
    cpu_pct: float = 0.0,
    ram_pct: float = 0.0,
    disk_pct: float = 0.0,
    swap_pct: float = 0.0,
    cpu_temp: float | None = None,
    security_event_count: int = 0,
    critical_events: int = 0,
) -> int:
    score = 100

    # CPU (poids 25%)
    if cpu_pct >= 95:     score -= 25
    elif cpu_pct >= 90:   score -= 20
    elif cpu_pct >= 80:   score -= 12
    elif cpu_pct >= 70:   score -= 5

    # RAM (poids 20%)
    if ram_pct >= 95:     score -= 20
    elif ram_pct >= 90:   score -= 15
    elif ram_pct >= 80:   score -= 8
    elif ram_pct >= 70:   score -= 3

    # Disque (poids 15%)
    if disk_pct >= 95:    score -= 15
    elif disk_pct >= 90:  score -= 10
    elif disk_pct >= 80:  score -= 5

    # Swap (poids 10%)
    if swap_pct >= 80:    score -= 10
    elif swap_pct >= 50:  score -= 5
    elif swap_pct >= 30:  score -= 2

    # Température (poids 15%)
    if cpu_temp is not None:
        if cpu_temp >= 90:   score -= 15
        elif cpu_temp >= 80: score -= 10
        elif cpu_temp >= 70: score -= 5

    # Événements de sécurité (poids 15%)
    if critical_events >= 3:  score -= 15
    elif critical_events >= 1: score -= 10
    elif security_event_count >= 10: score -= 5

    return max(0, min(100, score))


def score_to_status(score: int) -> str:
    if score >= 80:  return "green"
    if score >= 50:  return "orange"
    return "red"


def score_to_label(score: int) -> str:
    if score >= 90:  return "Excellent"
    if score >= 80:  return "Bon"
    if score >= 60:  return "Dégradé"
    if score >= 40:  return "Alerte"
    if score >= 20:  return "Critique"
    return "Danger"
