import re
from core.agents.base_agent import BaseAgent
from core.tools.terminal import terminal

# ── Mots-clés déclencheurs ────────────────────────────────────────────────────
_KEYWORDS = [
    "terminal", "commande", "bash", "linux", "système", "processus",
    "cpu", "mémoire", "disque", "santé", "diagnostic", "service",
    "log", "uptime", "ram", "kernel", "process", "memory", "disk",
    "système", "monitor", "monitoring", "install", "update", "upgrade",
    "restart", "reboot", "kill", "chmod", "chown", "rm ", "sudo",
    "systemctl", "apt", "pip", "npm", "port", "réseau", "network",
    "firewall", "iptables", "crontab", "cron", "patch", "fix",
    "réparer", "corriger", "modifier", "supprimer", "installer",
]

# ── Commandes de lecture seule (toujours autorisées) ──────────────────────────
_READONLY_CMDS = re.compile(
    r"^\s*(ps|top|htop|free|df|du|uptime|uname|id|whoami|env|ls|cat|grep|find|"
    r"stat|file|strings|ldd|lsof|ss|netstat|ping|nmap|tcpdump|tail|head|less|"
    r"journalctl|dmesg|iostat|vmstat|ifconfig|ip |hostname|date|which|type|"
    r"echo|pwd|history|last|who|w |lscpu|lsmem|lsblk|mount|fdisk -l|"
    r"systemctl status|service.*status|apt list|pip list|pip show|"
    r"dpkg -l|rpm -q|curl -s.*localhost|wget -q.*localhost)\b",
    re.IGNORECASE,
)

# ── Commandes qui modifient l'état du système ─────────────────────────────────
_MODIFY_PATTERNS = re.compile(
    r"\b(rm\s|mv\s|cp\s.*\/|chmod|chown|dd\s|mkfs|fdisk\s|"
    r"apt\s+(install|remove|purge|upgrade|dist-upgrade)|"
    r"pip\s+(install|uninstall)|npm\s+(install|uninstall|update)|"
    r"systemctl\s+(start|stop|restart|enable|disable|mask)|"
    r"service\s+\S+\s+(start|stop|restart)|"
    r"sed\s+-i|awk.*>\s*\/|echo\s+.*>\s*\/|tee\s+\/|"
    r"git\s+(commit|push|reset|rebase)|"
    r"crontab\s+-[rl]|reboot|shutdown|halt|poweroff|"
    r"useradd|userdel|usermod|passwd|visudo|"
    r"iptables\s+-[AI]|ufw\s+(allow|deny|delete)|"
    r"mount\s+|umount\s+|ln\s+-s)",
    re.IGNORECASE,
)

# ── Commandes de diagnostic système utiles ───────────────────────────────────
_DIAG_COMMANDS = [
    "uname -a",
    "uptime",
    "free -h",
    "df -h /",
    "ps aux --sort=-%cpu | head -8",
    "ss -tlnp 2>/dev/null | head -10",
    "systemctl list-units --state=failed --no-pager 2>/dev/null | head -5",
    "last -n 3 2>/dev/null | head -4",
    "dmesg --level=err,warn 2>/dev/null | tail -5",
]


def _is_modification(task: str) -> bool:
    return bool(_MODIFY_PATTERNS.search(task))


def _is_diagnostic_request(task: str) -> bool:
    diag_words = ["diagnostic", "santé", "health", "status", "état", "check", "analyser", "surveiller", "monitorer"]
    return any(w in task.lower() for w in diag_words)


def _run_diagnostics() -> str:
    results = []
    for cmd in _DIAG_COMMANDS:
        r = terminal.run(cmd)
        if r.get("success") and r.get("stdout", "").strip():
            results.append(f"$ {cmd}\n{r['stdout'].strip()}")
    return "\n\n".join(results) if results else "Diagnostic partiel — certaines commandes indisponibles."


class SystemAgent(BaseAgent):
    name = "system"
    description = (
        "Médecin de la plateforme — monitoring Linux, diagnostic système, "
        "sécurité OS, CVE awareness. Demande toujours permission avant modification."
    )

    async def run(self, task: str, context: dict = None) -> dict:
        ctx = context or {}

        # ── Mode SHANURA : pas de restriction permission ──────────────────────
        if ctx.get("shanura_mode"):
            result = terminal.run(task)
            output = result.get("stdout", "") or result.get("error", "")
            return self._result(result["success"], output, {
                "shanura": True, "returncode": result.get("returncode", -1)
            })

        # ── Diagnostic global demandé ─────────────────────────────────────────
        if _is_diagnostic_request(task):
            diag_output = _run_diagnostics()
            return self._result(True, diag_output, {
                "type": "diagnostic",
                "permission_required": False,
                "readonly": True,
            })

        # ── Commande de modification détectée → demande de permission ─────────
        if _is_modification(task):
            proposal = self._build_permission_request(task)
            return self._result(True, proposal, {
                "type": "permission_request",
                "permission_required": True,
                "pending_action": task,
                "readonly": False,
            })

        # ── Commande lecture seule → exécution directe ────────────────────────
        result = terminal.run(task)
        output = result.get("stdout", "") or result.get("error", "Aucune sortie.")
        return self._result(result["success"], output, {
            "type": "readonly_exec",
            "permission_required": False,
            "returncode": result.get("returncode", -1),
        })

    def _build_permission_request(self, task: str) -> str:
        return (
            f"🩺 PRESCRIPTION SYSTÈME — APPROBATION REQUISE\n\n"
            f"📋 Action proposée : {task.strip()}\n"
            f"🎯 Objectif : Modification du système détectée — nécessite validation\n"
            f"⚙️  Commande(s) : {task.strip()}\n"
            f"⚠️  Impact : Modification persistante de l'état du système\n"
            f"🔄 Réversibilité : Variable selon l'action\n\n"
            f"➡️  Mr Vitch, accordez-vous la permission d'exécuter cette action ?\n"
            f"   Répondez OUI pour procéder ou NON pour annuler."
        )

    def can_handle(self, task: str) -> bool:
        return any(kw in task.lower() for kw in _KEYWORDS)


system_agent = SystemAgent()
