import subprocess
import shlex
from core.tools.logger import get_logger

logger = get_logger(__name__)

# Seules ces commandes peuvent être exécutées par les agents
COMMAND_WHITELIST = {
    "ls", "pwd", "whoami", "id", "uname", "df", "du", "free", "ps",
    "netstat", "ss", "ip", "ping", "nslookup", "dig",
    "cat", "grep", "find", "echo", "date", "uptime", "hostname",
    "nmap", "whois", "traceroute", "curl", "wget",
}


class Terminal:
    def run(self, command: str, timeout: int = 30) -> dict:
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"success": False, "error": f"Commande invalide: {e}"}

        if not parts:
            return {"success": False, "error": "Commande vide"}

        base_cmd = parts[0]
        if base_cmd not in COMMAND_WHITELIST:
            logger.warning(f"Commande refusée : {base_cmd}")
            return {"success": False, "error": f"'{base_cmd}' non autorisé"}

        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/tmp",
            )
            logger.info(f"CMD: {command} → exit {result.returncode}")
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout dépassé"}
        except Exception as e:
            return {"success": False, "error": str(e)}


terminal = Terminal()
