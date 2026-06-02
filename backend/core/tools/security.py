import re
import shlex
import hashlib
import secrets
from core.tools.logger import get_logger

logger = get_logger(__name__)

# ── Whitelist complète — outils Kali + développement + analyse ───────────────
ALLOWED_COMMANDS = {
    # ── Navigation et fichiers ──────────────────────────────────────────────
    "ls", "pwd", "cat", "grep", "find", "head", "tail", "wc", "file", "stat",
    "tree", "du", "df", "diff", "locate", "which", "whereis", "type",
    "ln", "cp", "mv", "mkdir", "touch", "chmod", "chown",
    "tar", "gzip", "gunzip", "bzip2", "unzip", "zip", "7z", "xz",
    "base64", "xxd", "od", "hexdump", "strings", "file",

    # ── Texte et traitement ─────────────────────────────────────────────────
    "echo", "printf", "cut", "awk", "sed", "sort", "uniq", "tr", "wc",
    "xargs", "tee", "head", "tail", "less", "more", "column", "jq",

    # ── Identité et système ─────────────────────────────────────────────────
    "whoami", "id", "uname", "hostname", "uptime", "date", "env",
    "ps", "top", "htop", "pgrep", "pkill", "kill", "free", "lsof",
    "lscpu", "lsmem", "lsblk", "lsusb", "lspci", "dmesg",
    "systemctl", "service", "journalctl",

    # ── Réseau (lecture/audit) ──────────────────────────────────────────────
    "ip", "ifconfig", "netstat", "ss", "ping", "ping6", "traceroute", "tracepath",
    "nslookup", "dig", "host", "whois", "curl", "wget",
    "iptables", "ip6tables", "nftables", "route", "arp",

    # ── Scripting et langages ───────────────────────────────────────────────
    "python", "python2", "python3", "ruby", "perl", "lua", "node", "nodejs",
    "php", "bash", "sh", "zsh", "dash", "fish",
    "pip", "pip3", "gem", "npm",

    # ── Compilation et assemblage ───────────────────────────────────────────
    "gcc", "g++", "cc", "c++", "clang", "clang++",
    "make", "cmake", "ninja", "meson",
    "as", "ld", "objcopy", "objdump", "readelf", "nm", "ar", "ranlib",
    "nasm", "yasm", "fasm",
    "strip", "size", "addr2line", "c++filt",
    "patchelf", "ldd", "checksec",
    "musl-gcc", "musl-clang",

    # ── Analyse binaire et reverse engineering ──────────────────────────────
    "gdb", "gdbserver",
    "r2", "radare2", "r2pipe",
    "ltrace", "strace", "ptrace",
    "ROPgadget", "ropper",
    "binwalk",
    "exiftool",
    "foremost", "scalpel",
    "upx", "unupx",
    "pev", "readpe",
    "capstone",

    # ── Débogueurs et exploit tools ─────────────────────────────────────────
    "pwndbg", "peda", "gef",
    "pwntools",

    # ── Scan réseau et recon ────────────────────────────────────────────────
    "nmap", "masscan", "rustscan", "unicornscan",
    "arp-scan", "netdiscover",
    "hping3", "hping",
    "fping", "arping",

    # ── DNS et OSINT ────────────────────────────────────────────────────────
    "dnsenum", "dnsrecon", "fierce",
    "amass", "subfinder", "sublist3r",
    "theharvester", "theHarvester",
    "recon-ng",
    "shodan",
    "dmitry",

    # ── Scan Web et fuzzing ─────────────────────────────────────────────────
    "nikto",
    "gobuster", "dirb", "dirsearch",
    "ffuf", "wfuzz",
    "whatweb", "wafw00f",
    "wpscan", "joomscan", "droopescan",
    "sqlmap",
    "commix", "xsser",
    "cutycapt", "eyewitness",
    "httprobe",

    # ── Attaques par mot de passe ───────────────────────────────────────────
    "hydra", "medusa", "patator",
    "hashcat",
    "john", "johnny",
    "crackmapexec", "cme",
    "evil-winrm",
    "kerbrute",
    "spray",
    "brutespray",
    "ncrack",

    # ── SMB/Active Directory ────────────────────────────────────────────────
    "enum4linux", "enum4linux-ng",
    "smbclient", "smbmap",
    "rpcclient", "rpcinfo",
    "ldapsearch",
    "nbtscan",
    "onesixtyone",

    # ── Metasploit ──────────────────────────────────────────────────────────
    "msfconsole", "msfvenom", "msfdb",
    "msf", "msfrpc",
    "searchsploit",

    # ── Burp Suite / OWASP ZAP ─────────────────────────────────────────────
    "burpsuite", "zaproxy", "java",

    # ── Impacket ────────────────────────────────────────────────────────────
    "impacket-smbclient", "impacket-psexec", "impacket-wmiexec",
    "impacket-secretsdump", "impacket-ntlmrelayx", "impacket-smbserver",
    "impacket-ticketer", "impacket-lookupsid", "impacket-rpcdump",
    "impacket-dcomexec", "impacket-atexec", "impacket-reg",
    "impacket-samrdump", "impacket-getTGT", "impacket-getST",
    "secretsdump",

    # ── Post-exploitation et pivoting ───────────────────────────────────────
    "netcat", "nc", "ncat",
    "socat", "nohup",
    "proxychains", "proxychains4",
    "sshuttle",
    "chisel", "ligolo-ng",
    "meterpreter",

    # ── Réseau avancé / MITM ────────────────────────────────────────────────
    "tcpdump",
    "tshark", "wireshark",
    "ettercap", "bettercap",
    "responder",
    "dsniff", "arpspoof", "sslstrip",
    "mitmdump", "mitmproxy",
    "scapy",

    # ── Wireless ────────────────────────────────────────────────────────────
    "aircrack-ng", "airodump-ng", "aireplay-ng",
    "airbase-ng", "airmon-ng", "airtun-ng",
    "packetforge-ng", "airdecap-ng",
    "iwconfig", "iwlist", "iw",
    "wifi-honey", "wifite",

    # ── Cryptographie et stéganographie ────────────────────────────────────
    "openssl", "gpg", "gnupg",
    "steghide", "outguess", "stegcracker",
    "pngcheck", "zsteg",
    "hashid", "hash-identifier",

    # ── Forensics et analyse mémoire ────────────────────────────────────────
    "volatility", "volatility3",
    "bulk_extractor",
    "autopsy",
    "dd",   # utilisé avec params précis (pas vers /dev/)
    "dcfldd",
    "strings",

    # ── SSH et accès distant ────────────────────────────────────────────────
    "ssh", "scp", "sftp", "rsync",
    "ssh-keygen", "ssh-keyscan",
    "ftp", "tftp",
    "rdesktop", "xfreerdp", "freerdp",

    # ── Utilitaires divers ──────────────────────────────────────────────────
    "git", "svn",
    "screen", "tmux",
    "watch", "timeout",
    "at", "cron", "crontab",
    "mount", "umount",
    "stdbuf",
}

# ── Outils nécessitant un timeout long (secondes) ────────────────────────────
TOOL_TIMEOUTS = {
    # Scans réseau
    "nmap": 300, "masscan": 300, "rustscan": 120, "unicornscan": 300,
    # Password cracking
    "hashcat": 3600, "john": 3600, "hydra": 600, "medusa": 600,
    "crackmapexec": 300, "kerbrute": 300,
    # Web
    "gobuster": 300, "dirb": 300, "ffuf": 300, "wfuzz": 300,
    "nikto": 600, "sqlmap": 600, "wpscan": 300,
    # Compilation
    "gcc": 120, "g++": 120, "make": 300,
    # RE
    "binwalk": 120, "foremost": 300,
    # Recon
    "amass": 600, "sublist3r": 300, "theharvester": 300,
    # Forensics
    "volatility": 300, "volatility3": 300,
    # Metasploit
    "msfvenom": 120,
    # Wireless
    "airodump-ng": 300, "aireplay-ng": 300, "aircrack-ng": 3600, "airmon-ng": 30,
    # Web scanners
    "zaproxy": 600, "burpsuite": 0,
    # Metasploit console
    "msfconsole": 300,
}

DEFAULT_TIMEOUT = 60

# ── Patterns destructeurs bloqués inconditionnellement ───────────────────────
_DESTROY_PATTERNS = [
    # Suppression massive
    r"rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f",
    r"rm\s+.*-[a-zA-Z]*f[a-zA-Z]*r",
    r"rmdir\s",
    # Effacement disque (dd vers devices critiques)
    r"\bdd\b.*of\s*=\s*/dev/(sda|hda|vda|nvme|sdb|sdc|mmcblk)",
    r"mkfs",
    r"shred",
    r"wipefs",
    # Fork bomb
    r":\(\)\s*\{",
    r"forkbomb",
    # Redirection vers fichiers critiques
    r">\s*/dev/(sda|hda|vda|nvme|zero|mem)",
    r">\s*/boot/",
    r">\s*/etc/passwd",
    r">\s*/etc/shadow",
    # Shutdown / reboot
    r"\b(shutdown|reboot|halt|poweroff|init\s+0|init\s+6)\b",
    # Curl/wget pipe vers shell (exécution aveugle)
    r"(curl|wget).*\|\s*(bash|sh|zsh|python|python3|ruby|perl)",
    # Suppression de la base de données ou mémoire du projet
    r"rm\s+.*memory\.db",
    r"rm\s+.*\.env",
]
_DESTROY_RE = [re.compile(p, re.IGNORECASE) for p in _DESTROY_PATTERNS]


class CommandSecurity:
    """Gatekeeper central — toute commande passe par check() avant exécution."""

    def check(self, command: str) -> dict:
        if not command or not command.strip():
            return {"allowed": False, "reason": "Commande vide"}

        # 1. Bloquer les patterns destructeurs (priorité absolue)
        for pattern in _DESTROY_RE:
            if pattern.search(command):
                logger.warning(f"[SECURITY] Pattern destructeur bloqué : {command!r}")
                self._audit("BLOCKED_DESTRUCTIVE", command)
                return {"allowed": False, "reason": "Pattern destructeur détecté"}

        # 2. Parser la commande
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"allowed": False, "reason": f"Commande mal formée : {e}"}

        if not parts:
            return {"allowed": False, "reason": "Commande vide après parsing"}

        base_cmd = parts[0].split("/")[-1]

        # 3. Vérifier la whitelist
        if base_cmd not in ALLOWED_COMMANDS:
            logger.warning(f"[SECURITY] Commande hors whitelist refusée : {base_cmd!r}")
            self._audit("BLOCKED_WHITELIST", command)
            return {"allowed": False, "reason": f"'{base_cmd}' n'est pas dans la liste autorisée"}

        self._audit("ALLOWED", command)
        return {"allowed": True}

    def get_timeout(self, command: str) -> int:
        try:
            base_cmd = shlex.split(command)[0].split("/")[-1]
        except (ValueError, IndexError):
            return DEFAULT_TIMEOUT
        return TOOL_TIMEOUTS.get(base_cmd, DEFAULT_TIMEOUT)

    def _audit(self, status: str, command: str):
        logger.info(f"[AUDIT] {status} | cmd={command!r}")

    # ── Utilitaires crypto ──────────────────────────────────────────────────

    def generate_token(self, length: int = 32) -> str:
        return secrets.token_hex(length)

    def hash_password(self, password: str, salt: str = None) -> dict:
        salt = salt or secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return {"hash": hashed, "salt": salt}

    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(check, hashed)


security = CommandSecurity()
