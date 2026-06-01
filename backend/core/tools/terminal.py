import subprocess
import shlex
import os
from typing import Optional
from core.tools.logger import get_logger
from core.tools.security import security

logger = get_logger(__name__)

DEFAULT_CWD = "/tmp"


class Terminal:
    """
    Exécuteur de commandes système sécurisé.
    RÈGLE : ne jamais contourner security.check() — l'IA propose, security valide, on exécute.
    """

    def run(
        self,
        command: str,
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
        env_extra: Optional[dict] = None,
    ) -> dict:
        # 1. Validation sécurité OBLIGATOIRE
        check = security.check(command)
        if not check["allowed"]:
            return {"success": False, "error": check["reason"], "blocked": True}

        # 2. Timeout : auto-détecté si non fourni
        if timeout is None:
            timeout = security.get_timeout(command)

        # 3. Répertoire de travail
        work_dir = cwd if (cwd and os.path.isdir(cwd)) else DEFAULT_CWD

        # 4. Environnement
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)

        # 5. Parser la commande
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"success": False, "error": f"Parsing échoué : {e}"}

        # 6. Exécution sans shell=True
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
                env=env,
                shell=False,
            )
            logger.info(f"[EXEC] exit={result.returncode} cwd={work_dir} cmd={command!r}")
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
                "blocked": False,
                "cwd": work_dir,
                "timeout_used": timeout,
            }
        except subprocess.TimeoutExpired:
            logger.warning(f"[EXEC] Timeout ({timeout}s) : {command!r}")
            return {"success": False, "error": f"Timeout ({timeout}s) dépassé", "blocked": False}
        except FileNotFoundError:
            return {"success": False, "error": f"Commande introuvable : {parts[0]}", "blocked": False}
        except PermissionError:
            return {"success": False, "error": f"Permission refusée : {parts[0]}", "blocked": False}
        except Exception as e:
            logger.error(f"[EXEC] Erreur inattendue : {e}")
            return {"success": False, "error": str(e), "blocked": False}

    def run_pipe(
        self,
        commands: list[str],
        timeout: Optional[int] = None,
        cwd: Optional[str] = None,
    ) -> dict:
        """
        Exécute une pipeline de commandes (cmd1 | cmd2 | ...).
        Chaque commande est validée indépendamment avant exécution.
        """
        for cmd in commands:
            check = security.check(cmd)
            if not check["allowed"]:
                return {"success": False, "error": f"Pipeline bloqué sur '{cmd}': {check['reason']}", "blocked": True}

        work_dir = cwd if (cwd and os.path.isdir(cwd)) else DEFAULT_CWD
        timeout = timeout or 60

        try:
            procs = []
            for i, cmd in enumerate(commands):
                parts = shlex.split(cmd)
                stdin = procs[-1].stdout if procs else None
                p = subprocess.Popen(
                    parts,
                    stdin=stdin,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=work_dir,
                )
                if procs:
                    procs[-1].stdout.close()
                procs.append(p)

            stdout, stderr = procs[-1].communicate(timeout=timeout)
            returncode = procs[-1].returncode

            for p in procs[:-1]:
                p.wait()

            logger.info(f"[PIPE] exit={returncode} cmds={commands!r}")
            return {
                "success": returncode == 0,
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": returncode,
                "blocked": False,
            }
        except subprocess.TimeoutExpired:
            for p in procs:
                p.kill()
            return {"success": False, "error": f"Pipeline timeout ({timeout}s)", "blocked": False}
        except Exception as e:
            logger.error(f"[PIPE] Erreur : {e}")
            return {"success": False, "error": str(e), "blocked": False}


terminal = Terminal()
