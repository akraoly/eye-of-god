"""
AEGIS — Générateur de rapports de veille
Rapport hebdomadaire automatique chaque dimanche + à la demande.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

try:
    from core.tools.logger import get_logger
    logger = get_logger("aegis.reports")
except Exception:
    import logging
    logger = logging.getLogger(__name__)


async def generate_weekly_report(db) -> "AegisReport":
    """Génère le rapport hebdomadaire de veille AEGIS."""
    from database.models import AegisCVE, AegisExploit, AegisIntelLog, AegisReport

    end   = datetime.utcnow()
    start = end - timedelta(days=7)

    # Stats de la semaine
    cves = db.query(AegisCVE).filter(AegisCVE.ingested_at >= start).all()
    exploits = db.query(AegisExploit).filter(AegisExploit.added_at >= start).all()
    logs = db.query(AegisIntelLog).filter(AegisIntelLog.created_at >= start).all()

    critical_cves = [c for c in cves if c.cvss_score >= 9.0]
    high_cves     = [c for c in cves if 7.0 <= c.cvss_score < 9.0]

    stats = {
        "period": f"{start.strftime('%d/%m')} → {end.strftime('%d/%m/%Y')}",
        "total_cves": len(cves),
        "critical_cves": len(critical_cves),
        "high_cves": len(high_cves),
        "new_exploits": len(exploits),
        "intel_entries": len(logs),
    }

    # Synthèse pour Claude
    cve_list = "\n".join(
        f"- {c.cve_id} (CVSS {c.cvss_score}) — {(c.description or '')[:100]}"
        for c in critical_cves[:10]
    )
    exploit_list = "\n".join(
        f"- {e.repo_name} (CVE: {e.cve_id or '?'}) — {(e.description or '')[:80]}"
        for e in exploits[:10]
    )

    prompt = (
        f"Génère un rapport de veille cyber professionnel pour la semaine du {stats['period']}.\n\n"
        f"STATISTIQUES:\n"
        f"- {stats['total_cves']} nouveaux CVE dont {stats['critical_cves']} critiques (CVSS ≥ 9)\n"
        f"- {stats['new_exploits']} exploits publics détectés\n\n"
        f"CVE CRITIQUES:\n{cve_list or 'Aucun CVE critique cette semaine.'}\n\n"
        f"EXPLOITS DÉTECTÉS:\n{exploit_list or 'Aucun exploit détecté cette semaine.'}\n\n"
        "Structure du rapport:\n"
        "1. Résumé exécutif (3 phrases)\n"
        "2. CVE critiques — impact et priorité de mitigation\n"
        "3. Exploits publics — fiabilité et recommandations\n"
        "4. Recommandations prioritaires (5 points max)\n"
        "5. Conclusion\n\n"
        "Rédige en langage opérationnel, concis, sans blabla."
    )

    content = ""
    try:
        from core.llm.client import llm_client
        content = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system="Tu es un analyste SOC senior. Tes rapports sont directs, actionnables, sans fioriture.",
            max_tokens=1500,
        )
    except Exception as e:
        content = f"Erreur génération rapport: {e}\n\n---\n" + prompt

    report = AegisReport(
        report_type="weekly",
        period_start=start,
        period_end=end,
        title=f"Rapport de veille AEGIS — {stats['period']}",
        content=content,
        stats=json.dumps(stats),
    )
    db.add(report)
    try:
        db.commit()
        logger.info("aegis: rapport hebdomadaire généré")
    except Exception as e:
        db.rollback()
        logger.error("rapport commit error: %s", e)

    return report


async def generate_on_demand_report(db, hours: int = 24) -> "AegisReport":
    """Rapport de veille à la demande sur N heures."""
    from database.models import AegisCVE, AegisExploit, AegisIntelLog, AegisReport

    end   = datetime.utcnow()
    start = end - timedelta(hours=hours)

    cves     = db.query(AegisCVE).filter(AegisCVE.ingested_at >= start).all()
    exploits = db.query(AegisExploit).filter(AegisExploit.added_at >= start).all()

    stats = {
        "period_hours": hours,
        "total_cves": len(cves),
        "critical_cves": len([c for c in cves if c.cvss_score >= 9]),
        "new_exploits": len(exploits),
    }

    cve_summary = "\n".join(
        f"- {c.cve_id} CVSS {c.cvss_score} ({c.severity}): {(c.description or '')[:100]}"
        for c in sorted(cves, key=lambda x: x.cvss_score, reverse=True)[:15]
    )

    prompt = (
        f"Synthèse de veille AEGIS — {hours} dernières heures.\n\n"
        f"{stats['total_cves']} CVE | {stats['critical_cves']} critiques | "
        f"{stats['new_exploits']} exploits\n\n"
        f"CVE détectés:\n{cve_summary or 'Aucun CVE.'}\n\n"
        "Donne: 1) État de la menace actuelle 2) Points d'attention 3) Actions immédiates recommandées."
    )

    content = ""
    try:
        from core.llm.client import llm_client
        content = await llm_client.complete(
            messages=[{"role": "user", "content": prompt}],
            system="Tu es un analyste SOC. Sois direct et actionnable.",
            max_tokens=800,
        )
    except Exception as e:
        content = f"Analyse indisponible: {e}"

    report = AegisReport(
        report_type="on_demand",
        period_start=start,
        period_end=end,
        title=f"Rapport AEGIS — {hours}h",
        content=content,
        stats=json.dumps(stats),
    )
    db.add(report)
    try:
        db.commit()
    except Exception as e:
        db.rollback()

    return report


def generate_tactical_recommendation(cve: dict, exploits: list[dict]) -> str:
    """Fiche d'attaque recommandée pour une cible/technologie."""
    cve_id = cve.get("cve_id", "")
    score  = cve.get("cvss_score", 0)
    products = cve.get("affected_products", [])

    lines = [
        f"# Fiche tactique — {cve_id}",
        f"**CVSS:** {score} | **Sévérité:** {cve.get('severity', '?')}",
        f"**Produits affectés:** {', '.join(products[:5]) if products else 'Non spécifié'}",
        "",
        f"**Description:** {cve.get('description', '')[:300]}",
        "",
    ]
    if exploits:
        lines.append("## Exploits disponibles")
        for e in exploits[:3]:
            lines.append(f"- [{e.get('repo_name', '?')}]({e.get('repo_url', '')}) "
                        f"— Fiabilité: {e.get('reliability', 'unknown')}")
    lines += [
        "",
        "## Mitigation prioritaire",
        "1. Vérifier la version installée sur les systèmes affectés",
        "2. Appliquer le patch vendor si disponible",
        "3. Mettre en place les règles de détection IDS/EDR",
        "4. Documenter dans le journal de renseignement",
    ]
    return "\n".join(lines)
