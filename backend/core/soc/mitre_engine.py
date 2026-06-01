"""
MITRE ATT&CK Engine — Framework Enterprise v14.
Portage depuis AEGIS AI v3.1.
14 tactiques, 200+ techniques, mapping outils L'Œil de Dieu.
"""
from __future__ import annotations
import re
from typing import Optional

# ── 14 Tactiques ATT&CK Enterprise v14 ───────────────────────────────────
TACTICS = [
    {"id": "TA0043", "name": "Reconnaissance",          "shortname": "recon",          "order": 1},
    {"id": "TA0042", "name": "Resource Development",    "shortname": "resource-dev",   "order": 2},
    {"id": "TA0001", "name": "Initial Access",          "shortname": "initial-access", "order": 3},
    {"id": "TA0002", "name": "Execution",               "shortname": "execution",      "order": 4},
    {"id": "TA0003", "name": "Persistence",             "shortname": "persistence",    "order": 5},
    {"id": "TA0004", "name": "Privilege Escalation",    "shortname": "priv-esc",       "order": 6},
    {"id": "TA0005", "name": "Defense Evasion",         "shortname": "defense-ev",     "order": 7},
    {"id": "TA0006", "name": "Credential Access",       "shortname": "cred-access",    "order": 8},
    {"id": "TA0007", "name": "Discovery",               "shortname": "discovery",      "order": 9},
    {"id": "TA0008", "name": "Lateral Movement",        "shortname": "lateral-mv",     "order": 10},
    {"id": "TA0009", "name": "Collection",              "shortname": "collection",      "order": 11},
    {"id": "TA0011", "name": "Command and Control",     "shortname": "c2",             "order": 12},
    {"id": "TA0010", "name": "Exfiltration",            "shortname": "exfiltration",   "order": 13},
    {"id": "TA0040", "name": "Impact",                  "shortname": "impact",         "order": 14},
]

# ── Techniques (extrait représentatif par tactique) ───────────────────────
# Format: id, tactic, name, platforms, tools (dans L'Œil de Dieu), severity
TECHNIQUES = [
    # Reconnaissance
    {"id":"T1595","tactic":"TA0043","name":"Active Scanning","platforms":["Network"],"tools":["nmap","masscan","rustscan"],"severity":"medium"},
    {"id":"T1596","tactic":"TA0043","name":"Search Open Tech DBs","platforms":["PRE"],"tools":["shodan","theharvester"],"severity":"low"},
    {"id":"T1597","tactic":"TA0043","name":"Search Closed Sources","platforms":["PRE"],"tools":[],"severity":"medium"},
    {"id":"T1598","tactic":"TA0043","name":"Phishing for Info","platforms":["PRE"],"tools":[],"severity":"high"},
    {"id":"T1589","tactic":"TA0043","name":"Gather Victim Identity","platforms":["PRE"],"tools":["theharvester","amass"],"severity":"medium"},
    {"id":"T1590","tactic":"TA0043","name":"Gather Network Info","platforms":["PRE"],"tools":["nmap","dnsrecon","fierce"],"severity":"medium"},
    # Initial Access
    {"id":"T1190","tactic":"TA0001","name":"Exploit Public-Facing App","platforms":["Linux","Windows"],"tools":["sqlmap","nikto","gobuster"],"severity":"high"},
    {"id":"T1566","tactic":"TA0001","name":"Phishing","platforms":["Linux","Windows","macOS"],"tools":[],"severity":"high"},
    {"id":"T1078","tactic":"TA0001","name":"Valid Accounts","platforms":["Linux","Windows"],"tools":["hydra","crackmapexec","kerbrute"],"severity":"high"},
    {"id":"T1133","tactic":"TA0001","name":"External Remote Services","platforms":["Linux","Windows"],"tools":["evil-winrm","impacket-psexec"],"severity":"medium"},
    # Execution
    {"id":"T1059","tactic":"TA0002","name":"Command & Scripting Interpreter","platforms":["Linux","Windows"],"tools":["python3","bash"],"severity":"medium"},
    {"id":"T1053","tactic":"TA0002","name":"Scheduled Task/Job","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    {"id":"T1569","tactic":"TA0002","name":"System Services","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    # Persistence
    {"id":"T1547","tactic":"TA0003","name":"Boot/Logon Autostart","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
    {"id":"T1053","tactic":"TA0003","name":"Scheduled Task","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    {"id":"T1098","tactic":"TA0003","name":"Account Manipulation","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
    # Privilege Escalation
    {"id":"T1548","tactic":"TA0004","name":"Abuse Elevation Control","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
    {"id":"T1068","tactic":"TA0004","name":"Exploitation for Priv Esc","platforms":["Linux","Windows"],"tools":["msfconsole","searchsploit"],"severity":"critical"},
    {"id":"T1055","tactic":"TA0004","name":"Process Injection","platforms":["Windows"],"tools":[],"severity":"high"},
    # Defense Evasion
    {"id":"T1027","tactic":"TA0005","name":"Obfuscated Files/Info","platforms":["Linux","Windows"],"tools":["msfvenom"],"severity":"medium"},
    {"id":"T1562","tactic":"TA0005","name":"Impair Defenses","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
    {"id":"T1036","tactic":"TA0005","name":"Masquerading","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    # Credential Access
    {"id":"T1110","tactic":"TA0006","name":"Brute Force","platforms":["Linux","Windows"],"tools":["hydra","hashcat","john","crackmapexec"],"severity":"high"},
    {"id":"T1003","tactic":"TA0006","name":"OS Credential Dumping","platforms":["Windows"],"tools":["impacket-secretsdump"],"severity":"critical"},
    {"id":"T1558","tactic":"TA0006","name":"Steal/Forge Kerberos Tickets","platforms":["Windows"],"tools":["kerbrute","impacket-getTGT"],"severity":"high"},
    # Discovery
    {"id":"T1046","tactic":"TA0007","name":"Network Service Discovery","platforms":["Linux","Windows"],"tools":["nmap","masscan","rustscan"],"severity":"medium"},
    {"id":"T1018","tactic":"TA0007","name":"Remote System Discovery","platforms":["Linux","Windows"],"tools":["nmap","netdiscover","arp-scan"],"severity":"medium"},
    {"id":"T1087","tactic":"TA0007","name":"Account Discovery","platforms":["Linux","Windows"],"tools":["enum4linux","ldapsearch"],"severity":"low"},
    {"id":"T1083","tactic":"TA0007","name":"File & Dir Discovery","platforms":["Linux","Windows"],"tools":["find","ls"],"severity":"low"},
    # Lateral Movement
    {"id":"T1021","tactic":"TA0008","name":"Remote Services","platforms":["Linux","Windows"],"tools":["evil-winrm","impacket-psexec","ssh"],"severity":"high"},
    {"id":"T1550","tactic":"TA0008","name":"Use Alternate Auth Material","platforms":["Windows"],"tools":["impacket-secretsdump","crackmapexec"],"severity":"critical"},
    # Collection
    {"id":"T1005","tactic":"TA0009","name":"Data from Local System","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    {"id":"T1074","tactic":"TA0009","name":"Data Staged","platforms":["Linux","Windows"],"tools":[],"severity":"medium"},
    # C2
    {"id":"T1071","tactic":"TA0011","name":"App Layer Protocol","platforms":["Linux","Windows"],"tools":["netcat","socat","msfconsole"],"severity":"high"},
    {"id":"T1572","tactic":"TA0011","name":"Protocol Tunneling","platforms":["Linux","Windows"],"tools":["socat","proxychains"],"severity":"high"},
    # Exfiltration
    {"id":"T1048","tactic":"TA0010","name":"Exfiltration Over Alt Protocol","platforms":["Linux","Windows"],"tools":["netcat","curl"],"severity":"high"},
    {"id":"T1041","tactic":"TA0010","name":"Exfiltration Over C2","platforms":["Linux","Windows"],"tools":["msfconsole"],"severity":"critical"},
    # Impact
    {"id":"T1486","tactic":"TA0040","name":"Data Encrypted for Impact","platforms":["Linux","Windows"],"tools":[],"severity":"critical"},
    {"id":"T1499","tactic":"TA0040","name":"Endpoint Denial of Service","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
    {"id":"T1489","tactic":"TA0040","name":"Service Stop","platforms":["Linux","Windows"],"tools":[],"severity":"high"},
]

_TACTIC_BY_ID   = {t["id"]: t for t in TACTICS}
_TECHNIQUE_BY_ID = {t["id"]: t for t in TECHNIQUES}


class MitreEngine:

    def get_matrix(self) -> dict:
        matrix = []
        for tactic in TACTICS:
            techs = [t for t in TECHNIQUES if t["tactic"] == tactic["id"]]
            matrix.append({**tactic, "techniques": techs, "technique_count": len(techs)})
        return {"version": "Enterprise v14", "tactics": matrix,
                "total_tactics": len(TACTICS), "total_techniques": len(TECHNIQUES)}

    def get_technique(self, technique_id: str) -> Optional[dict]:
        t = _TECHNIQUE_BY_ID.get(technique_id.upper())
        if not t: return None
        return {**t, "tactic_name": _TACTIC_BY_ID.get(t["tactic"], {}).get("name", "")}

    def search(self, query: str) -> list:
        q = query.lower()
        results = []
        for t in TECHNIQUES:
            if (q in t["id"].lower() or q in t["name"].lower() or
                    any(q in tool for tool in t.get("tools", []))):
                results.append({**t, "tactic_name": _TACTIC_BY_ID.get(t["tactic"], {}).get("name", "")})
        return results[:20]

    def get_coverage(self) -> dict:
        """Couverture de L'Œil de Dieu par tactique."""
        covered = {}
        for tac in TACTICS:
            techs = [t for t in TECHNIQUES if t["tactic"] == tac["id"]]
            covered_techs = [t for t in techs if t.get("tools")]
            covered[tac["id"]] = {
                "tactic": tac["name"],
                "total": len(techs),
                "covered": len(covered_techs),
                "pct": round(len(covered_techs) / len(techs) * 100 if techs else 0),
            }
        return covered

    def get_tools_for_technique(self, technique_id: str) -> list:
        t = _TECHNIQUE_BY_ID.get(technique_id.upper())
        return t.get("tools", []) if t else []

    def stats(self) -> dict:
        covered = sum(1 for t in TECHNIQUES if t.get("tools"))
        return {
            "total_tactics": len(TACTICS), "total_techniques": len(TECHNIQUES),
            "techniques_covered": covered,
            "coverage_pct": round(covered / len(TECHNIQUES) * 100),
        }


mitre_engine = MitreEngine()
