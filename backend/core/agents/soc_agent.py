"""
SocAgent — Agent SOC pour L'Œil de Dieu.
Gère alertes, incidents, SIEM, SOAR, MITRE via le chat naturel.
"""
from __future__ import annotations
import re
from typing import Optional
from core.agents.base_agent import BaseAgent
from core.soc.alert_engine    import alert_engine, SEVERITIES, CATEGORIES
from core.soc.incident_engine import incident_engine
from core.soc.siem_engine     import siem_engine, BUILTIN_RULES as SIEM_BUILTIN_RULES
from core.soc.soar_engine     import soar_engine
from core.soc.mitre_engine    import mitre_engine

_KEYWORDS = [
    # Alertes
    "alerte", "alert", "alertes", "sécurité", "soc", "intrusion",
    "brute force", "port scan", "malware", "ransomware", "phishing",
    "exfiltration", "c2", "lateral", "privilege",
    # Incidents
    "incident", "incidents", "breach", "compromis", "attaque",
    # SIEM
    "siem", "corrélation", "règle", "event", "événement", "timeline",
    "log", "logs",
    # SOAR
    "soar", "playbook", "réponse automatique", "playbooks", "response",
    # MITRE
    "mitre", "att&ck", "attack", "technique", "tactique", "tactic",
    # Stats
    "tableau de bord soc", "soc dashboard", "menaces", "threats",
]


class SocAgent(BaseAgent):
    name = "soc"
    description = "Agent SOC — alertes, incidents, SIEM, SOAR, MITRE ATT&CK"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return any(kw in t for kw in _KEYWORDS)

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        t = task.lower().strip()
        ctx = context or {}
        db  = ctx.get("db")  # injecté par chat_service si disponible

        # ── MITRE ────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["mitre", "att&ck", "attack", "technique", "tactique"]):
            return self._handle_mitre(t, task)

        # ── SOAR / Playbooks ────────────────────────────────────────────────
        if any(kw in t for kw in ["soar", "playbook", "réponse automatique"]):
            return self._handle_soar(t, task)

        # ── SIEM ─────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["siem", "corrélation", "règle", "timeline"]):
            if db:
                return self._handle_siem(t, db)
            return self._result(True, self._siem_info())

        # ── Alertes ──────────────────────────────────────────────────────────
        if any(kw in t for kw in ["alerte", "alert", "alertes", "nouvelle alerte"]):
            if db:
                return self._handle_alerts(t, task, db)
            return self._result(True, self._alerts_info())

        # ── Incidents ────────────────────────────────────────────────────────
        if any(kw in t for kw in ["incident", "incidents", "breach"]):
            if db:
                return self._handle_incidents(t, task, db)
            return self._result(True, self._incidents_info())

        # ── Stats SOC générales ──────────────────────────────────────────────
        if any(kw in t for kw in ["soc dashboard", "tableau de bord soc", "menaces", "threats"]):
            if db:
                return self._soc_summary(db)
            return self._result(True, "Connecte-toi via /api/soc/dashboard pour les stats en direct.")

        return self._result(
            True,
            "SOC L'Œil de Dieu opérationnel.\n"
            "Capacités : alertes · incidents · SIEM (8 règles) · SOAR (6 playbooks) · MITRE ATT&CK v14\n\n"
            "Exemples : 'montre les alertes CRITICAL' · 'playbooks disponibles' · "
            "'techniques MITRE pour brute force' · 'stats SIEM'"
        )

    # ── MITRE handler ─────────────────────────────────────────────────────
    def _handle_mitre(self, t: str, task: str) -> dict:
        # Recherche par ID (T1110, TA0006…)
        m = re.search(r'\b(T[A]?\d{4}(?:\.\d{3})?)\b', task.upper())
        if m:
            tech = mitre_engine.get_technique(m.group(1))
            if tech:
                tools = ", ".join(tech.get("tools", [])) or "aucun"
                return self._result(True,
                    f"**{tech['id']} — {tech['name']}**\n"
                    f"Tactique : {tech.get('tactic_name', tech['tactic'])}\n"
                    f"Plateformes : {', '.join(tech.get('platforms', []))}\n"
                    f"Sévérité : {tech.get('severity', '?')}\n"
                    f"Outils L'Œil de Dieu : {tools}", tech)

        # Stats de couverture
        if any(kw in t for kw in ["couverture", "coverage", "stats"]):
            stats = mitre_engine.stats()
            cov   = mitre_engine.get_coverage()
            lines = [f"**MITRE ATT&CK — Couverture L'Œil de Dieu**",
                     f"Techniques couvertes : {stats['techniques_covered']}/{stats['total_techniques']} ({stats['coverage_pct']}%)\n"]
            for tid, data in cov.items():
                pct = data['pct']
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                lines.append(f"{data['tactic']:30} [{bar}] {pct}%")
            return self._result(True, "\n".join(lines), {"stats": stats, "coverage": cov})

        # Recherche textuelle
        query = re.sub(r'mitre|att&ck|attack|technique|tactique|cherche|search', '', t).strip()
        if len(query) > 2:
            results = mitre_engine.search(query)
            if results:
                lines = [f"**{len(results)} technique(s) MITRE pour '{query}':**"]
                for r in results[:8]:
                    tools = ", ".join(r.get("tools", [])) or "—"
                    lines.append(f"• **{r['id']}** {r['name']} ({r.get('tactic_name','')}) — outils: {tools}")
                return self._result(True, "\n".join(lines), {"results": results})

        # Matrice complète
        matrix = mitre_engine.get_matrix()
        lines  = [f"**MITRE ATT&CK Enterprise v14 — {matrix['total_tactics']} tactiques, {matrix['total_techniques']} techniques**\n"]
        for tac in matrix["tactics"]:
            lines.append(f"**{tac['id']} {tac['name']}** — {tac['technique_count']} techniques")
        return self._result(True, "\n".join(lines))

    # ── SOAR handler ──────────────────────────────────────────────────────
    def _handle_soar(self, t: str, task: str) -> dict:
        # Exécuter une étape
        m_exec = re.search(r'exécute?\s+(?:étape\s+)?(\d+)\s+(?:du\s+)?playbook\s+(\w+)', t)
        if m_exec:
            step_n, pb_id = int(m_exec.group(1)), m_exec.group(2)
            result = soar_engine.execute_step(pb_id, step_n)
            return self._result(result["success"], str(result), result)

        # Recommandation pour une catégorie
        m_cat = re.search(r'recommande?\s+(?:pour\s+)?(\w+)', t)
        if m_cat:
            cat = m_cat.group(1).upper()
            sev = "HIGH"
            for s in ["critical", "high", "medium", "low"]:
                if s in t: sev = s.upper(); break
            rec = soar_engine.recommend(cat, sev)
            if rec:
                steps = "\n".join(f"  {s['order']}. [{s['action']}] {s['description']}" for s in rec["steps"])
                return self._result(True,
                    f"**Playbook recommandé : {rec['name']}**\n"
                    f"Durée estimée : {rec['estimated_duration']}\n"
                    f"Impact financier évité : ${rec['financial_impact_usd']:,}\n\n"
                    f"Étapes :\n{steps}", rec)

        # Liste des playbooks
        pbs = soar_engine.list_playbooks()
        lines = [f"**{len(pbs)} playbooks SOAR disponibles :**\n"]
        for pb in pbs:
            lines.append(f"**{pb['id']}** — {pb['name']}")
            lines.append(f"  Catégories : {', '.join(pb['attack_categories'])} | Durée : {pb['estimated_duration']}")
            lines.append(f"  Impact évité : ${pb['financial_impact_usd']:,} | {pb['estimated_duration']}\n")
        return self._result(True, "\n".join(lines), {"playbooks": pbs})

    # ── SIEM handler ──────────────────────────────────────────────────────
    def _handle_siem(self, t: str, db) -> dict:
        if "règle" in t or "rule" in t:
            rules = siem_engine.get_rules(db)
            lines = [f"**{len(rules)} règles SIEM actives :**\n"]
            for r in rules:
                icon = "✅" if r["enabled"] else "⏸"
                lines.append(f"{icon} **{r['name']}** [{r['severity']}] hits:{r['hit_count']}")
                lines.append(f"   {r['mitre_tactic']} / {r['mitre_technique']}\n")
            return self._result(True, "\n".join(lines), {"rules": rules})
        if "timeline" in t:
            tl = siem_engine.timeline(db, hours=24)
            return self._result(True, f"Timeline SIEM (24h) : {len(tl)} entrées", {"timeline": tl})
        events = siem_engine.get_events(db, hours=24)
        return self._result(True,
            f"**SIEM — {events['total']} événements (24h)**\n"
            f"Règles actives : {len(siem_engine.get_rules(db))}",
            events)

    def _siem_info(self) -> str:
        return (f"**SIEM L'Œil de Dieu**\n"
                f"{len(SIEM_BUILTIN_RULES)} règles de corrélation intégrées "
                f"(Brute Force, Recon→Exploit, Lateral Movement, Exfiltration, etc.)\n"
                f"Accès en direct : /api/soc/siem/events · /api/soc/siem/rules")

    # ── Alertes handler ───────────────────────────────────────────────────
    def _handle_alerts(self, t: str, task: str, db) -> dict:
        sev  = next((s for s in ["critical","high","medium","low"] if s in t), None)
        stat = next((s.upper() for s in ["new","acknowledged","resolved","in_progress"] if s in t), None)
        result = alert_engine.list(db, severity=sev.upper() if sev else None,
                                   status=stat, per_page=10)
        stats = alert_engine.stats(db, hours=24)
        lines = [f"**Alertes SOC** — {result['total']} total\n",
                 f"CRITICAL ouverts : {stats['critical_open']}"]
        for a in result["alerts"][:8]:
            icon = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(a["severity"],"⚪")
            lines.append(f"{icon} [{a['severity']}] **{a['title']}** — {a['status']}")
            if a.get("source_ip"): lines.append(f"   Source : {a['source_ip']}")
        return self._result(True, "\n".join(lines), {"alerts": result, "stats": stats})

    def _alerts_info(self) -> str:
        return ("**Alertes SOC** disponibles via /api/soc/alerts\n"
                "Sévérités : LOW · MEDIUM · HIGH · CRITICAL\n"
                "Catégories : PORT_SCAN · BRUTE_FORCE · INTRUSION · MALWARE · C2 · …")

    # ── Incidents handler ─────────────────────────────────────────────────
    def _handle_incidents(self, t: str, task: str, db) -> dict:
        result = incident_engine.list(db, per_page=10)
        stats  = incident_engine.stats(db)
        lines  = [f"**Incidents SOC** — {result['total']} total | {stats['open']} ouverts\n"]
        for inc in result["incidents"][:6]:
            icon = {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(inc["severity"],"⚪")
            lines.append(f"{icon} [{inc['severity']}] **{inc['title']}** — {inc['status']}")
        return self._result(True, "\n".join(lines), {"incidents": result, "stats": stats})

    def _incidents_info(self) -> str:
        return "**Incidents SOC** via /api/soc/incidents — OPEN·INVESTIGATING·CONTAINED·RESOLVED·CLOSED"

    # ── Dashboard SOC ─────────────────────────────────────────────────────
    def _soc_summary(self, db) -> dict:
        alert_stats = alert_engine.stats(db, hours=24)
        inc_stats   = incident_engine.stats(db)
        mitre_stats = mitre_engine.stats()
        nb_pbs      = len(soar_engine.list_playbooks())
        summary = (
            f"**🔴 SOC L'Œil de Dieu — Tableau de bord**\n\n"
            f"**Alertes (24h)**\n"
            f"  Total : {alert_stats['total']} | CRITICAL ouverts : {alert_stats['critical_open']}\n"
            f"  HIGH: {alert_stats['by_severity']['HIGH']} · MEDIUM: {alert_stats['by_severity']['MEDIUM']} · LOW: {alert_stats['by_severity']['LOW']}\n\n"
            f"**Incidents**\n"
            f"  Total : {inc_stats['total']} | Ouverts : {inc_stats['open']}\n\n"
            f"**MITRE ATT&CK**\n"
            f"  Couverture : {mitre_stats['techniques_covered']}/{mitre_stats['total_techniques']} techniques ({mitre_stats['coverage_pct']}%)\n\n"
            f"**SOAR** : {nb_pbs} playbooks | **SIEM** : {len(SIEM_BUILTIN_RULES)} règles actives"
        )
        return self._result(True, summary, {
            "alerts": alert_stats, "incidents": inc_stats,
            "mitre": mitre_stats, "soar_playbooks": nb_pbs,
        })


soc_agent = SocAgent()
