"""
Compliance Engine — 40 contrôles CIS-like sur 8 catégories.
Portage depuis AEGIS AI v3.0.
"""
from __future__ import annotations
import json
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from database.models import ComplianceControl, ComplianceAssessment
import logging

log = logging.getLogger("SOC.Compliance")

# ── Framework : AEGIS Security Baseline (inspiré CIS Controls v8) ─────────────
BASELINE_CONTROLS = [
    # Access Control
    {"id":"AC-1","cat":"Access Control",       "sev":"CRITICAL","title":"Séparation des privilèges admin",            "desc":"Les comptes admin ne doivent pas être utilisés pour les tâches courantes.","req":"Comptes distincts pour tâches admin et courantes."},
    {"id":"AC-2","cat":"Access Control",       "sev":"HIGH",    "title":"Revue trimestrielle des accès",              "desc":"Droits d'accès revus tous les 3 mois.","req":"Documenter et valider les accès chaque trimestre."},
    {"id":"AC-3","cat":"Access Control",       "sev":"HIGH",    "title":"Désactivation des comptes inactifs",         "desc":"Comptes inutilisés depuis 90j désactivés.","req":"Processus de désactivation automatique après 90j."},
    {"id":"AC-4","cat":"Access Control",       "sev":"MEDIUM",  "title":"Principe de moindre privilège",              "desc":"Chaque utilisateur a uniquement les droits nécessaires.","req":"Appliquer POLP sur tous les systèmes."},
    {"id":"AC-5","cat":"Access Control",       "sev":"HIGH",    "title":"Contrôle des accès physiques",               "desc":"Accès salles serveurs restreint et journalisé.","req":"Badge + caméra + journal conservé 1 an."},
    # Audit & Logging
    {"id":"AL-1","cat":"Audit & Logging",      "sev":"CRITICAL","title":"Centralisation des journaux (SIEM)",         "desc":"Journaux d'authentification centralisés.","req":"SIEM avec rétention minimum 12 mois."},
    {"id":"AL-2","cat":"Audit & Logging",      "sev":"HIGH",    "title":"Alertes sur échecs d'authentification",      "desc":"5 échecs en 10 min → alerte.","req":"Règle brute-force dans le SIEM."},
    {"id":"AL-3","cat":"Audit & Logging",      "sev":"HIGH",    "title":"Journalisation des accès privilégiés",       "desc":"Toute action admin journalisée.","req":"sudo logging + Event 4672 Windows."},
    {"id":"AL-4","cat":"Audit & Logging",      "sev":"MEDIUM",  "title":"Intégrité des journaux",                     "desc":"Logs protégés contre modification.","req":"Stockage immuable ou signature crypto."},
    {"id":"AL-5","cat":"Audit & Logging",      "sev":"MEDIUM",  "title":"Synchronisation NTP",                        "desc":"Horloges systèmes synchronisées.","req":"NTP sur tous les équipements. Tolérance 2s."},
    # Configuration Management
    {"id":"CM-1","cat":"Config Management",    "sev":"HIGH",    "title":"Inventaire actualisé des actifs",            "desc":"CMDB exhaustif et à jour.","req":"CMDB mis à jour mensuellement."},
    {"id":"CM-2","cat":"Config Management",    "sev":"HIGH",    "title":"Hardening des configurations",               "desc":"Configurations par défaut durcies.","req":"CIS Benchmarks pour chaque OS/app."},
    {"id":"CM-3","cat":"Config Management",    "sev":"MEDIUM",  "title":"Gestion des changements",                    "desc":"Tout changement documenté et approuvé.","req":"Change Management avec validation avant prod."},
    {"id":"CM-4","cat":"Config Management",    "sev":"CRITICAL","title":"Suppression des services inutiles",          "desc":"Services/ports non nécessaires désactivés.","req":"Audit surface d'attaque périodique."},
    {"id":"CM-5","cat":"Config Management",    "sev":"HIGH",    "title":"Gestion des assets cloud",                   "desc":"Assets cloud inventoriés et taggués.","req":"CSPM avec découverte automatique."},
    # Data Protection
    {"id":"DP-1","cat":"Data Protection",      "sev":"CRITICAL","title":"Chiffrement des données au repos",           "desc":"Données sensibles chiffrées sur disque.","req":"AES-256 pour données CRITICAL/HIGH."},
    {"id":"DP-2","cat":"Data Protection",      "sev":"CRITICAL","title":"Chiffrement des données en transit",         "desc":"Données sensibles chiffrées en transit.","req":"TLS 1.2+ obligatoire. TLS 1.0/1.1 désactivé."},
    {"id":"DP-3","cat":"Data Protection",      "sev":"HIGH",    "title":"Classification des données",                 "desc":"Données classifiées par sensibilité.","req":"Schéma de classification : PUBLIC/INTERNE/CONFIDENTIEL/SECRET."},
    {"id":"DP-4","cat":"Data Protection",      "sev":"HIGH",    "title":"Politique de sauvegarde 3-2-1",              "desc":"3 copies, 2 supports, 1 hors site.","req":"Tests de restauration trimestriels."},
    {"id":"DP-5","cat":"Data Protection",      "sev":"MEDIUM",  "title":"Gestion du cycle de vie des données",        "desc":"Données détruites selon politique de rétention.","req":"Politique de rétention documentée et appliquée."},
    # Identity & Authentication
    {"id":"IA-1","cat":"Identity & Auth",      "sev":"CRITICAL","title":"MFA obligatoire pour les admins",            "desc":"Tous les comptes admin ont le MFA actif.","req":"MFA FIDO2 ou TOTP pour tous les comptes privilégiés."},
    {"id":"IA-2","cat":"Identity & Auth",      "sev":"HIGH",    "title":"Politique de mot de passe forte",            "desc":"Mots de passe ≥12 caractères, complexes.","req":"Politique : 12+ chars, MAJ+min+chiffres+spéciaux."},
    {"id":"IA-3","cat":"Identity & Auth",      "sev":"HIGH",    "title":"SSO centralisé",                             "desc":"Authentification centralisée via IdP.","req":"SAML 2.0 ou OIDC pour les applications critiques."},
    {"id":"IA-4","cat":"Identity & Auth",      "sev":"MEDIUM",  "title":"Gestion des identités machines",             "desc":"Certificats machines gérés par PKI interne.","req":"PKI interne avec rotation automatique des certs."},
    {"id":"IA-5","cat":"Identity & Auth",      "sev":"HIGH",    "title":"Révocation immédiate des accès",             "desc":"Accès révoqués dans l'heure suivant le départ.","req":"Processus offboarding automatisé et testé."},
    # Incident Response
    {"id":"IR-1","cat":"Incident Response",    "sev":"CRITICAL","title":"Plan de réponse aux incidents documenté",    "desc":"PRI formalisé, testé et à jour.","req":"PRI mis à jour annuellement, exercice tabletop semestriel."},
    {"id":"IR-2","cat":"Incident Response",    "sev":"HIGH",    "title":"Équipe SOC ou MSSP disponible 24/7",         "desc":"Capacité de réponse permanente.","req":"SOC interne ou MSSP avec SLA < 4h."},
    {"id":"IR-3","cat":"Incident Response",    "sev":"HIGH",    "title":"Playbooks de réponse par type d'attaque",    "desc":"Procédures documentées par type d'incident.","req":"Playbooks pour : ransomware, phishing, BEC, intrusion, DDoS."},
    {"id":"IR-4","cat":"Incident Response",    "sev":"MEDIUM",  "title":"Communication de crise documentée",          "desc":"Contacts et procédures de communication en cas de crise.","req":"Plan de communication incluant direction, juridique, communication."},
    {"id":"IR-5","cat":"Incident Response",    "sev":"MEDIUM",  "title":"Retours d'expérience (REx) post-incident",  "desc":"Bilan réalisé après chaque incident CRITICAL.","req":"REx dans les 2 semaines suivant tout incident HIGH/CRITICAL."},
    # Network Security
    {"id":"NS-1","cat":"Network Security",     "sev":"CRITICAL","title":"Segmentation réseau",                        "desc":"Réseau segmenté en zones de sécurité.","req":"VLAN distincts : DMZ/Production/Bureautique/OT."},
    {"id":"NS-2","cat":"Network Security",     "sev":"HIGH",    "title":"Pare-feu et règles de filtrage",             "desc":"Règles de firewall revues et durcies.","req":"Politique deny-all par défaut. Revue semestrielle des règles."},
    {"id":"NS-3","cat":"Network Security",     "sev":"HIGH",    "title":"VPN pour accès distants",                    "desc":"Accès distants uniquement via VPN.","req":"VPN avec MFA. Interdiction d'accès RDP direct depuis Internet."},
    {"id":"NS-4","cat":"Network Security",     "sev":"MEDIUM",  "title":"Monitoring des flux réseau (NTA)",           "desc":"Trafic réseau analysé en continu.","req":"NTA ou NDR avec détection C2 et exfiltration."},
    {"id":"NS-5","cat":"Network Security",     "sev":"HIGH",    "title":"Protection anti-DDoS",                       "desc":"Mitigation DDoS en place pour les services exposés.","req":"CDN ou anti-DDoS pour assets Internet-facing."},
    # Patch Management
    {"id":"PM-1","cat":"Patch Management",     "sev":"CRITICAL","title":"Correctifs critiques dans les 72h",          "desc":"Vulnérabilités critiques patchées en < 72h.","req":"Processus d'urgence pour CVSS ≥ 9.0."},
    {"id":"PM-2","cat":"Patch Management",     "sev":"HIGH",    "title":"Cycle de patching mensuel",                  "desc":"Patchs HIGH appliqués sous 30 jours.","req":"Patch Tuesday + test en préprod avant prod."},
    {"id":"PM-3","cat":"Patch Management",     "sev":"HIGH",    "title":"Inventaire des vulnérabilités",              "desc":"Scan de vulnérabilités hebdomadaire.","req":"Scanner (OpenVAS/Nessus) avec rapport hebdomadaire."},
    {"id":"PM-4","cat":"Patch Management",     "sev":"MEDIUM",  "title":"Gestion des dépendances tierces",            "desc":"Bibliothèques tierces suivies et mises à jour.","req":"SCA (Software Composition Analysis) dans le pipeline CI/CD."},
    {"id":"PM-5","cat":"Patch Management",     "sev":"MEDIUM",  "title":"Décommissionnement des systèmes EOL",        "desc":"Systèmes en fin de vie remplacés ou isolés.","req":"Inventaire EOL. Plan de migration documenté."},
]

CATEGORIES = sorted(set(c["cat"] for c in BASELINE_CONTROLS))


class ComplianceEngine:

    def init_controls(self, db: Session) -> int:
        existing = db.query(ComplianceControl).count()
        if existing > 0: return existing
        for c in BASELINE_CONTROLS:
            ctrl = ComplianceControl(
                control_id=c["id"], category=c["cat"], severity=c["sev"],
                title=c["title"], description=c["desc"], requirement=c["req"],
                status="NOT_ASSESSED",
            )
            db.add(ctrl)
        db.commit()
        log.info(f"[Compliance] {len(BASELINE_CONTROLS)} contrôles initialisés")
        return len(BASELINE_CONTROLS)

    def run_assessment(self, db: Session, auto_pass: list = None) -> dict:
        """Lance une évaluation de conformité — auto-détection basée sur les données SOC."""
        self.init_controls(db)
        controls = db.query(ComplianceControl).all()

        # Déterminer l'état de chaque contrôle via les données SOC disponibles
        from database.models import Alert, SiemRule, ZeroTrustPolicy
        alert_count = db.query(Alert).count()
        siem_rules  = db.query(SiemRule).filter(SiemRule.enabled == True).count()
        zt_policies = db.query(ZeroTrustPolicy).filter(ZeroTrustPolicy.enabled == True).count()

        auto_status = {
            "AL-1": "PASS" if siem_rules > 0 else "FAIL",
            "AL-2": "PASS" if siem_rules >= 5 else "PARTIAL",
            "IR-3": "PASS" if zt_policies > 0 else "PARTIAL",
        }

        passed = failed = partial = 0
        for ctrl in controls:
            status = auto_pass[controls.index(ctrl)] if (auto_pass and controls.index(ctrl) < len(auto_pass)) else None
            if not status:
                status = auto_status.get(ctrl.control_id, "NOT_ASSESSED")
            ctrl.status     = status
            ctrl.last_checked = datetime.utcnow()
            ctrl.score      = 100 if status == "PASS" else (50 if status == "PARTIAL" else 0)
            if status == "PASS":    passed  += 1
            elif status == "FAIL":  failed  += 1
            elif status == "PARTIAL": partial += 1

        db.commit()

        score_pct = round((passed + partial * 0.5) / len(controls) * 100 if controls else 0, 1)
        assessment = ComplianceAssessment(
            total_controls=len(controls), passed=passed,
            failed=failed, partial=partial, score_pct=score_pct,
        )
        db.add(assessment); db.commit()
        log.info(f"[Compliance] Assessment: {score_pct}% ({passed}P/{failed}F/{partial}PA)")
        return {"passed": passed, "failed": failed, "partial": partial,
                "not_assessed": len(controls) - passed - failed - partial,
                "score_pct": score_pct, "total": len(controls)}

    def get_controls(self, db: Session, category: str = None,
                     status: str = None, severity: str = None) -> dict:
        self.init_controls(db)
        q = db.query(ComplianceControl)
        if category: q = q.filter(ComplianceControl.category == category)
        if status:   q = q.filter(ComplianceControl.status   == status)
        if severity: q = q.filter(ComplianceControl.severity == severity)
        controls = q.order_by(ComplianceControl.control_id).all()
        return {"total": len(controls), "categories": CATEGORIES,
                "controls": [self._ctrl_dict(c) for c in controls]}

    def update_control(self, db: Session, control_id: str, status: str,
                       evidence: str = None, remediation: str = None) -> Optional[dict]:
        ctrl = db.query(ComplianceControl).filter(ComplianceControl.control_id == control_id).first()
        if not ctrl: return None
        ctrl.status      = status
        ctrl.score       = 100 if status == "PASS" else (50 if status == "PARTIAL" else 0)
        ctrl.last_checked = datetime.utcnow()
        if evidence:    ctrl.evidence    = evidence
        if remediation: ctrl.remediation = remediation
        db.commit()
        return self._ctrl_dict(ctrl)

    def stats(self, db: Session) -> dict:
        self.init_controls(db)
        controls = db.query(ComplianceControl).all()
        total    = len(controls)
        passed   = sum(1 for c in controls if c.status == "PASS")
        failed   = sum(1 for c in controls if c.status == "FAIL")
        partial  = sum(1 for c in controls if c.status == "PARTIAL")
        score    = round((passed + partial * 0.5) / total * 100 if total else 0, 1)
        by_cat   = {}
        for c in controls:
            by_cat.setdefault(c.category, {"total": 0, "passed": 0})
            by_cat[c.category]["total"] += 1
            if c.status == "PASS": by_cat[c.category]["passed"] += 1
        return {"total": total, "passed": passed, "failed": failed, "partial": partial,
                "not_assessed": total - passed - failed - partial,
                "score_pct": score, "by_category": by_cat,
                "framework": "AEGIS Security Baseline v1.0"}

    def _ctrl_dict(self, c: ComplianceControl) -> dict:
        return {"id": c.control_id, "category": c.category, "severity": c.severity,
                "title": c.title, "description": c.description, "requirement": c.requirement,
                "status": c.status, "score": c.score, "evidence": c.evidence,
                "remediation": c.remediation,
                "last_checked": c.last_checked.isoformat() if c.last_checked else None}


compliance_engine = ComplianceEngine()
