import subprocess
import shlex
from core.tools.logger import get_logger
from core.tools.security import security

logger = get_logger(__name__)


class Terminal:
    """
    Exécuteur de commandes système sécurisé.
    RÈGLE : ne jamais contourner security.check() — l'IA propose, security valide, on exécute.
    """

    def run(self, command: str, timeout: int = 30) -> dict:
        # 1. Validation sécurité OBLIGATOIRE avant toute exécution
        check = security.check(command)
        if not check["allowed"]:
            return {"success": False, "error": check["reason"], "blocked": True}

        # 2. Parser la commande (déjà validée)
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"success": False, "error": f"Parsing échoué : {e}"}

        # 3. Exécution sans shell=True (pas d'injection possible)
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd="/tmp",
                shell=False,        # explicitement désactivé
            )
            logger.info(f"[EXEC] exit={result.returncode} cmd={command!r}")
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "blocked": False,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"[EXEC] Timeout ({timeout}s) : {command!r}")
            return {"success": False, "error": f"Timeout ({timeout}s) dépassé", "blocked": False}
        except FileNotFoundError:
            return {"success": False, "error": f"Commande introuvable : {parts[0]}", "blocked": False}
        except Exception as e:
            logger.error(f"[EXEC] Erreur inattendue : {e}")
            return {"success": False, "error": str(e), "blocked": False}


terminal = Terminal()
