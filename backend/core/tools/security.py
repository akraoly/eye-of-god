import re
import shlex
import hashlib
import secrets
from core.tools.logger import get_logger

logger = get_logger(__name__)

# ── Whitelist explicite des commandes autorisées ─────────────────────────────
ALLOWED_COMMANDS = {
    # Navigation et fichiers (lecture seule)
    "ls", "pwd", "cat", "grep", "find", "head", "tail", "wc", "file", "stat",
    "tree", "du", "df", "diff",
    # Identité et système
    "whoami", "id", "uname", "hostname", "uptime", "date", "env", "echo",
    "ps", "top", "htop", "pgrep", "free",
    # Réseau (lecture)
    "ip", "ifconfig", "netstat", "ss", "ping", "traceroute",
    "nslookup", "dig", "whois", "curl", "wget",
    # Sécurité / audit
    "nmap", "netcat", "nc",
}

# ── Patterns destructeurs bloqués inconditionnellement ───────────────────────
_DESTROY_PATTERNS = [
    # Suppression massive
    r"rm\s+.*-[a-zA-Z]*r[a-zA-Z]*f",   # rm -rf / rm -fr
    r"rm\s+.*-[a-zA-Z]*f[a-zA-Z]*r",
    r"rmdir",
    # Effacement disque
    r"\bdd\b",
    r"mkfs",
    r"shred",
    r"wipefs",
    # Fork bomb
    r":\(\)\s*\{",
    r"forkbomb",
    # Redirection vers périphériques critiques
    r">\s*/dev/(sda|hda|vda|nvme|zero|null|random|urandom|mem)",
    r">\s*/boot/",
    r">\s*/etc/passwd",
    r">\s*/etc/shadow",
    # Shutdown / reboot
    r"\b(shutdown|reboot|halt|poweroff|init\s+0|init\s+6)\b",
    # Injection de commandes
    r";\s*(bash|sh|zsh|fish|dash)\s+-[ci]",
    r"\|\s*(bash|sh|zsh)\b",
    # Curl/wget pipe vers shell
    r"(curl|wget).*(bash|sh|python|perl|ruby)",
]
_DESTROY_RE = [re.compile(p, re.IGNORECASE) for p in _DESTROY_PATTERNS]


class CommandSecurity:
    """Gatekeeper central — toute commande passe par check() avant exécution."""

    def check(self, command: str) -> dict:
        """
        Retourne {"allowed": True} ou {"allowed": False, "reason": str}.
        L'IA propose, ce module valide, le terminal exécute si allowed.
        """
        if not command or not command.strip():
            return {"allowed": False, "reason": "Commande vide"}

        # 1. Bloquer les patterns destructeurs (priorité absolue)
        for pattern in _DESTROY_RE:
            if pattern.search(command):
                logger.warning(f"[SECURITY] Pattern destructeur bloqué : {command!r}")
                self._audit("BLOCKED_DESTRUCTIVE", command)
                return {"allowed": False, "reason": "Pattern destructeur détecté"}

        # 2. Parser et vérifier la commande de base
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"allowed": False, "reason": f"Commande mal formée : {e}"}

        if not parts:
            return {"allowed": False, "reason": "Commande vide après parsing"}

        base_cmd = parts[0].split("/")[-1]  # accepte /usr/bin/ls → ls

        # 3. Vérifier la whitelist
        if base_cmd not in ALLOWED_COMMANDS:
            logger.warning(f"[SECURITY] Commande hors whitelist refusée : {base_cmd!r}")
            self._audit("BLOCKED_WHITELIST", command)
            return {"allowed": False, "reason": f"'{base_cmd}' n'est pas dans la liste autorisée"}

        self._audit("ALLOWED", command)
        return {"allowed": True}

    def _audit(self, status: str, command: str):
        logger.info(f"[AUDIT] {status} | cmd={command!r}")

    # ── Utilitaires crypto (inchangés) ─────────────────────────────────────

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
