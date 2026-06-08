"""
Attack Planner — Bloc 7 Automation Stratégique
Planification automatique de chemins d'attaque, modélisation kill chain,
graphe ATT&CK, scoring de risque, recommandations tactiques.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PLANS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/automation/plans")
_OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Profils de cibles ──────────────────────────────────────────────────────────
_TARGET_PROFILES = {
    "corporate_windows": {
        "name": "Entreprise Windows AD",
        "os": ["Windows Server 2019/2022", "Windows 10/11"],
        "infra": ["Active Directory", "Exchange", "SharePoint", "Azure AD"],
        "exposure": ["VPN", "OWA", "RDP exposed", "Email phishing surface"],
        "default_vectors": ["phishing", "vpn_exploit", "rdp_brute"],
        "avg_dwell_days": 21,
    },
    "government_network": {
        "name": "Réseau Gouvernemental",
        "os": ["Windows Server", "RHEL", "Cisco IOS"],
        "infra": ["DMZ", "SCIF", "Classified network", "PKI", "SIEM"],
        "exposure": ["Email gateway", "Web portal", "Supply chain"],
        "default_vectors": ["spear_phishing", "supply_chain", "watering_hole"],
        "avg_dwell_days": 180,
    },
    "critical_infrastructure": {
        "name": "Infrastructure Critique (ICS/SCADA)",
        "os": ["Windows XP/7 (OT)", "Linux embedded", "VxWorks", "QNX"],
        "infra": ["SCADA", "PLCs", "HMI", "Historian", "OPC-UA"],
        "exposure": ["IT/OT bridge", "Remote maintenance VPN", "USB drops"],
        "default_vectors": ["it_ot_pivot", "usb_drop", "supply_chain"],
        "avg_dwell_days": 365,
    },
    "financial_institution": {
        "name": "Institution Financière",
        "os": ["Windows", "AIX", "z/OS mainframe"],
        "infra": ["SWIFT", "Core banking", "Trading platform", "HSM"],
        "exposure": ["SWIFT gateway", "Online banking", "ATM network"],
        "default_vectors": ["swift_fraud", "insider_threat", "supply_chain"],
        "avg_dwell_days": 90,
    },
    "telecom_operator": {
        "name": "Opérateur Télécom",
        "os": ["Linux", "Solaris", "Cisco IOS-XE", "Nokia SR-OS"],
        "infra": ["SS7", "Diameter", "BGP", "5G core", "OSS/BSS"],
        "exposure": ["SS7 interconnect", "Roaming interface", "NMS"],
        "default_vectors": ["ss7_attack", "bgp_hijack", "supply_chain"],
        "avg_dwell_days": 120,
    },
    "cloud_saas": {
        "name": "Organisation Cloud-Native",
        "os": ["Linux containers", "Kubernetes"],
        "infra": ["AWS/Azure/GCP", "CI/CD pipeline", "GitHub", "Okta SSO"],
        "exposure": ["OAuth tokens", "S3 buckets", "Container registry", "API gateway"],
        "default_vectors": ["oauth_token_theft", "supply_chain_ci", "ssrf_imds"],
        "avg_dwell_days": 14,
    },
}

# ── Phases ATT&CK (kill chain étendue) ────────────────────────────────────────
_KILL_CHAIN_PHASES = {
    "reconnaissance": {
        "id": "TA0043",
        "techniques": [
            {"id": "T1595", "name": "Active Scanning", "tool": "nmap/masscan/shodan"},
            {"id": "T1589", "name": "Gather Victim Identity Info", "tool": "OSINT/HaveIBeenPwned"},
            {"id": "T1591", "name": "Gather Victim Org Info", "tool": "LinkedIn/WHOIS/Maltego"},
            {"id": "T1596", "name": "Search Open Technical Databases", "tool": "Shodan/Censys/Fofa"},
        ],
        "duration_days": "3-14",
        "stealth": "HIGH",
    },
    "resource_development": {
        "id": "TA0042",
        "techniques": [
            {"id": "T1587", "name": "Develop Capabilities", "tool": "Custom malware dev"},
            {"id": "T1583", "name": "Acquire Infrastructure", "tool": "VPS/domain purchase"},
            {"id": "T1588", "name": "Obtain Capabilities", "tool": "0day market/crimeware"},
            {"id": "T1608", "name": "Stage Capabilities", "tool": "C2 setup/payload staging"},
        ],
        "duration_days": "7-30",
        "stealth": "VERY_HIGH",
    },
    "initial_access": {
        "id": "TA0001",
        "techniques": [
            {"id": "T1566", "name": "Phishing", "tool": "Gophish/Evilginx2"},
            {"id": "T1190", "name": "Exploit Public-Facing Application", "tool": "Metasploit/custom"},
            {"id": "T1133", "name": "External Remote Services", "tool": "RDP/VPN exploit"},
            {"id": "T1195", "name": "Supply Chain Compromise", "tool": "SolarWinds-like"},
            {"id": "T1091", "name": "Replication Through Removable Media", "tool": "BadUSB/AutoRun"},
        ],
        "duration_days": "1-7",
        "stealth": "MEDIUM",
    },
    "execution": {
        "id": "TA0002",
        "techniques": [
            {"id": "T1059", "name": "Command & Scripting Interpreter", "tool": "PowerShell/Bash"},
            {"id": "T1203", "name": "Exploitation for Client Execution", "tool": "Browser/Office exploit"},
            {"id": "T1053", "name": "Scheduled Task/Job", "tool": "schtasks/cron"},
            {"id": "T1072", "name": "Software Deployment Tools", "tool": "SCCM/Ansible"},
        ],
        "duration_days": "0-1",
        "stealth": "LOW",
    },
    "persistence": {
        "id": "TA0003",
        "techniques": [
            {"id": "T1547", "name": "Boot/Logon Autostart Execution", "tool": "Registry Run keys"},
            {"id": "T1505", "name": "Server Software Component", "tool": "Webshell/IIS module"},
            {"id": "T1098", "name": "Account Manipulation", "tool": "Golden ticket/SSH key"},
            {"id": "T1542", "name": "Pre-OS Boot", "tool": "UEFI bootkit"},
        ],
        "duration_days": "0-2",
        "stealth": "MEDIUM",
    },
    "privilege_escalation": {
        "id": "TA0004",
        "techniques": [
            {"id": "T1068", "name": "Exploitation for Privilege Escalation", "tool": "PrintSpoofer/Dirty Pipe"},
            {"id": "T1134", "name": "Access Token Manipulation", "tool": "Incognito/token impersonation"},
            {"id": "T1484", "name": "Domain Policy Modification", "tool": "GPO abuse"},
            {"id": "T1548", "name": "Abuse Elevation Control Mechanism", "tool": "UAC bypass"},
        ],
        "duration_days": "0-3",
        "stealth": "LOW",
    },
    "defense_evasion": {
        "id": "TA0005",
        "techniques": [
            {"id": "T1562", "name": "Impair Defenses", "tool": "AMSI bypass/EDR kill"},
            {"id": "T1055", "name": "Process Injection", "tool": "Shellcode injection/DLL sideload"},
            {"id": "T1070", "name": "Indicator Removal", "tool": "Log clearing/timestomp"},
            {"id": "T1027", "name": "Obfuscated Files/Information", "tool": "Packer/encryptor"},
            {"id": "T1036", "name": "Masquerading", "tool": "LOLBins/signed binary abuse"},
        ],
        "duration_days": "ongoing",
        "stealth": "HIGH",
    },
    "credential_access": {
        "id": "TA0006",
        "techniques": [
            {"id": "T1003", "name": "OS Credential Dumping", "tool": "Mimikatz/pypykatz"},
            {"id": "T1552", "name": "Unsecured Credentials", "tool": "LaZagne/trufflehog"},
            {"id": "T1558", "name": "Steal or Forge Kerberos Tickets", "tool": "Rubeus/Impacket"},
            {"id": "T1111", "name": "MFA Interception", "tool": "Evilginx2/Modlishka"},
        ],
        "duration_days": "0-1",
        "stealth": "MEDIUM",
    },
    "discovery": {
        "id": "TA0007",
        "techniques": [
            {"id": "T1082", "name": "System Information Discovery", "tool": "systeminfo/uname"},
            {"id": "T1018", "name": "Remote System Discovery", "tool": "BloodHound/net view"},
            {"id": "T1046", "name": "Network Service Discovery", "tool": "nmap/rustscan"},
            {"id": "T1087", "name": "Account Discovery", "tool": "BloodHound/ldapsearch"},
        ],
        "duration_days": "1-5",
        "stealth": "MEDIUM",
    },
    "lateral_movement": {
        "id": "TA0008",
        "techniques": [
            {"id": "T1021", "name": "Remote Services", "tool": "PsExec/RDP/SSH"},
            {"id": "T1550", "name": "Use Alternate Auth Material", "tool": "Pass-the-Hash/Ticket"},
            {"id": "T1534", "name": "Internal Spearphishing", "tool": "Email/Teams/Slack"},
            {"id": "T1570", "name": "Lateral Tool Transfer", "tool": "SMB/WMI"},
        ],
        "duration_days": "2-14",
        "stealth": "LOW",
    },
    "collection": {
        "id": "TA0009",
        "techniques": [
            {"id": "T1560", "name": "Archive Collected Data", "tool": "7zip/rar encryption"},
            {"id": "T1119", "name": "Automated Collection", "tool": "PowerShell scripts"},
            {"id": "T1213", "name": "Data from Information Repositories", "tool": "SharePoint/Confluence"},
            {"id": "T1056", "name": "Input Capture", "tool": "Keylogger"},
        ],
        "duration_days": "1-7",
        "stealth": "MEDIUM",
    },
    "exfiltration": {
        "id": "TA0010",
        "techniques": [
            {"id": "T1041", "name": "Exfil Over C2 Channel", "tool": "HTTPS C2"},
            {"id": "T1048", "name": "Exfil Over Alternative Protocol", "tool": "DNS/ICMP tunnel"},
            {"id": "T1567", "name": "Exfil Over Web Service", "tool": "OneDrive/Dropbox/GitHub"},
            {"id": "T1537", "name": "Transfer Data to Cloud Account", "tool": "Rclone/s3cp"},
        ],
        "duration_days": "1-3",
        "stealth": "MEDIUM",
    },
    "impact": {
        "id": "TA0040",
        "techniques": [
            {"id": "T1486", "name": "Data Encrypted for Impact", "tool": "Ransomware"},
            {"id": "T1485", "name": "Data Destruction", "tool": "Wiper malware"},
            {"id": "T1499", "name": "Endpoint Denial of Service", "tool": "DDoS"},
            {"id": "T1490", "name": "Inhibit System Recovery", "tool": "Shadow copy deletion"},
            {"id": "T1496", "name": "Resource Hijacking", "tool": "Cryptominer"},
        ],
        "duration_days": "0-1",
        "stealth": "VERY_LOW",
    },
}

# ── Objectifs stratégiques ─────────────────────────────────────────────────────
_STRATEGIC_OBJECTIVES = {
    "intelligence_gathering": {
        "name": "Collecte de renseignement",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "persistence","privilege_escalation","defense_evasion","credential_access",
                   "discovery","lateral_movement","collection","exfiltration"],
        "impact_phase": False,
        "dwell_target_days": 180,
        "noise_level": "LOW",
    },
    "ransomware_deployment": {
        "name": "Déploiement ransomware",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "persistence","privilege_escalation","defense_evasion","credential_access",
                   "discovery","lateral_movement","collection","exfiltration","impact"],
        "impact_phase": True,
        "dwell_target_days": 21,
        "noise_level": "HIGH",
    },
    "sabotage_ics": {
        "name": "Sabotage ICS/SCADA (type Stuxnet)",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "persistence","privilege_escalation","defense_evasion","discovery",
                   "lateral_movement","impact"],
        "impact_phase": True,
        "dwell_target_days": 365,
        "noise_level": "VERY_LOW",
    },
    "supply_chain_compromise": {
        "name": "Compromission chaîne d'approvisionnement",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "persistence","defense_evasion","lateral_movement","collection","exfiltration"],
        "impact_phase": False,
        "dwell_target_days": 90,
        "noise_level": "VERY_LOW",
    },
    "destructive_wiper": {
        "name": "Destruction de données (wiper)",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "privilege_escalation","defense_evasion","lateral_movement","impact"],
        "impact_phase": True,
        "dwell_target_days": 7,
        "noise_level": "HIGH",
    },
    "financial_fraud": {
        "name": "Fraude financière (SWIFT/BEC)",
        "phases": ["reconnaissance","resource_development","initial_access","execution",
                   "persistence","defense_evasion","credential_access","collection","impact"],
        "impact_phase": True,
        "dwell_target_days": 60,
        "noise_level": "LOW",
    },
}


class AttackPlannerService:

    def list_target_profiles(self) -> Dict:
        return {k: {"name": v["name"], "os": v["os"], "infra": v["infra"]} for k, v in _TARGET_PROFILES.items()}

    def list_objectives(self) -> Dict:
        return {k: {"name": v["name"], "dwell_target_days": v["dwell_target_days"], "noise_level": v["noise_level"]}
                for k, v in _STRATEGIC_OBJECTIVES.items()}

    def list_kill_chain(self) -> Dict:
        return {k: {"mitre_ta": v["id"], "techniques_count": len(v["techniques"]), "stealth": v["stealth"]}
                for k, v in _KILL_CHAIN_PHASES.items()}

    def generate_attack_plan(
        self,
        target_profile: str,
        objective: str,
        operator_skill: str = "expert",
        time_budget_days: int = 90,
        stealth_priority: str = "high",
    ) -> Dict:
        profile = _TARGET_PROFILES.get(target_profile, _TARGET_PROFILES["corporate_windows"])
        obj     = _STRATEGIC_OBJECTIVES.get(objective, _STRATEGIC_OBJECTIVES["intelligence_gathering"])

        plan_id = str(uuid.uuid4())
        phases  = []

        timeline_day = 0
        for phase_name in obj["phases"]:
            phase = _KILL_CHAIN_PHASES[phase_name]
            techs = random.sample(phase["techniques"], min(2, len(phase["techniques"])))
            duration = random.randint(1, 5)
            phases.append({
                "phase":       phase_name,
                "mitre_ta":    phase["id"],
                "day_start":   timeline_day,
                "day_end":     timeline_day + duration,
                "stealth":     phase["stealth"],
                "techniques":  techs,
                "tools":       [t["tool"] for t in techs],
            })
            timeline_day += duration

        total_days = min(timeline_day, time_budget_days)
        risk_score = round(random.uniform(7.5, 9.8), 1)

        # Vecteurs initiaux selon profil
        initial_vectors = profile["default_vectors"]

        plan = {
            "plan_id":       plan_id,
            "created_at":    datetime.utcnow().isoformat(),
            "target_profile": target_profile,
            "target_info":   profile["name"],
            "objective":     objective,
            "objective_name":obj["name"],
            "operator_skill":operator_skill,
            "stealth_priority": stealth_priority,
            "estimated_days":total_days,
            "dwell_target":  obj["dwell_target_days"],
            "noise_level":   obj["noise_level"],
            "risk_score":    risk_score,
            "initial_vectors": initial_vectors,
            "phases":        phases,
            "total_phases":  len(phases),
            "total_techniques": sum(len(p["techniques"]) for p in phases),
            "critical_path": [p["phase"] for p in phases if p["stealth"] in ["LOW","VERY_LOW"]],
            "recommendations": self._gen_recommendations(target_profile, objective, stealth_priority),
            "simulated":     True,
        }

        _PLANS[plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> Dict:
        return _PLANS.get(plan_id, {"error": "plan_not_found"})

    def list_plans(self) -> Dict:
        return {"plans": [{"plan_id": k, "target": v["target_profile"], "objective": v["objective"],
                           "risk_score": v["risk_score"], "created_at": v["created_at"]}
                          for k, v in _PLANS.items()]}

    def build_attack_graph(self, plan_id: str) -> Dict:
        plan = _PLANS.get(plan_id)
        if not plan:
            return {"error": "plan_not_found"}
        nodes = []
        edges = []
        for i, p in enumerate(plan["phases"]):
            nodes.append({"id": i, "phase": p["phase"], "mitre_ta": p["mitre_ta"],
                          "stealth": p["stealth"], "day": p["day_start"]})
            if i > 0:
                edges.append({"from": i-1, "to": i, "type": "sequential"})
        return {
            "plan_id":  plan_id,
            "nodes":    nodes,
            "edges":    edges,
            "critical_nodes": [n for n in nodes if n["stealth"] in ["LOW","VERY_LOW"]],
            "simulated": True,
        }

    def assess_detection_risk(self, plan_id: str) -> Dict:
        plan = _PLANS.get(plan_id)
        if not plan:
            return {"error": "plan_not_found"}
        risky_phases = [p for p in plan["phases"] if p["stealth"] in ["LOW","VERY_LOW"]]
        return {
            "plan_id":        plan_id,
            "overall_risk":   plan["risk_score"],
            "detection_probability": round(random.uniform(0.15, 0.45), 2),
            "risky_phases":   [p["phase"] for p in risky_phases],
            "edr_bypass_needed": True,
            "siem_evasion_techniques": [
                "Slow and low — opérations étalées sur plusieurs jours",
                "LOLBins — utilisation de binaires système légitimes",
                "Masquerade — processus malveillants nommés comme processus système",
                "Encrypted C2 — trafic C2 via HTTPS/DNS-over-HTTPS",
                "Living off the land — no custom tools",
            ],
            "simulated": True,
        }

    def _gen_recommendations(self, target_profile: str, objective: str, stealth: str) -> List[str]:
        rec = [
            f"Prioriser les vecteurs d'entrée de {_TARGET_PROFILES[target_profile]['exposure'][0]}",
            "Établir la persistance avant d'élever les privilèges",
            "Utiliser des implants memory-only pour éviter la détection antivirus",
            "Chiffrer les communications C2 avec TLS 1.3 + certificate pinning",
        ]
        if stealth == "high":
            rec.append("Respecter les heures de bureau locales pour se fondre dans le trafic normal")
            rec.append("Limiter les connexions C2 à 1-2 beacons/heure minimum")
        if objective == "ransomware_deployment":
            rec.append("Exfiltrer avant chiffrement (double extorsion)")
            rec.append("Cibler les sauvegardes et shadow copies en priorité")
        return rec
