"""
C2Manager — gestion asynchrone des frameworks C2 (Sliver, Havoc, Gophish, Evilginx).
Lance chaque C2 en subprocess non-bloquant, capture les logs en temps réel.
"""
import os
import shlex
import signal
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

from core.tools.logger import get_logger
from core.tools.security import security

logger = get_logger(__name__)

# ── Configs C2 ────────────────────────────────────────────────────────────────

C2_CONFIGS = {
    "sliver": {
        "cmd": "sliver-server",
        "description": "C2 Sliver — implants cross-platform MTLS/HTTP/DNS",
        "port": 31337,
        "color": "#10b981",
        "needs_sudo": False,
    },
    "havoc": {
        "cmd": "havoc server --profile /tmp/havoc.yaotl -v",
        "description": "Havoc C2 — Teamserver GUI (port 40056)",
        "port": 40056,
        "color": "#f97316",
        "needs_sudo": False,
    },
    "gophish": {
        "cmd": "gophish-start",
        "description": "Gophish — campagnes phishing (UI port 3333)",
        "port": 3333,
        "color": "#38bdf8",
        "needs_sudo": False,
    },
    "evilginx": {
        "cmd": "evilginx -p /usr/share/evilginx/phishlets",
        "description": "Evilginx — AiTM proxy MFA bypass (port 443/80)",
        "port": 443,
        "color": "#a78bfa",
        "needs_sudo": True,
    },
}

# Profil Havoc minimal généré automatiquement si absent
_HAVOC_PROFILE = """\
Teamserver {
    Host = "0.0.0.0"
    Port = 40056

    Build {
        Compiler64 = "x86_64-w64-mingw32-gcc"
        Nasm = "/usr/bin/nasm"
    }
}

Operators {
    operator "admin" {
        Password = "admin123!"
    }
}

Listeners {
    Http {
        Name         = "default"
        Hosts        = ["0.0.0.0"]
        Port         = 80
        Secure       = false
    }
}
"""


class C2Process:
    __slots__ = ("name", "process", "started_at", "logs", "_thread")

    def __init__(self, name: str):
        self.name = name
        self.process = None
        self.started_at: Optional[float] = None
        self.logs: deque = deque(maxlen=500)
        self._thread: Optional[threading.Thread] = None

    @property
    def pid(self) -> Optional[int]:
        return self.process.pid if self.process else None

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @property
    def uptime(self) -> Optional[str]:
        if not self.started_at or not self.running:
            return None
        secs = int(time.time() - self.started_at)
        h, r = divmod(secs, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"


class C2Manager:
    def __init__(self):
        self._procs: dict[str, C2Process] = {name: C2Process(name) for name in C2_CONFIGS}

    # ── Démarrage ─────────────────────────────────────────────────────────────

    def start(self, name: str) -> dict:
        cfg = C2_CONFIGS.get(name)
        if not cfg:
            return {"success": False, "error": f"C2 inconnu : {name}. Disponibles : {list(C2_CONFIGS)}"}

        c2 = self._procs[name]
        if c2.running:
            return {"success": False, "error": f"{name} tourne déjà (PID {c2.pid})"}

        # Pré-conditions spécifiques
        prep_err = self._prepare(name, cfg)
        if prep_err:
            return {"success": False, "error": prep_err}

        # Vérification sécurité
        base_cmd = cfg["cmd"].split()[0]
        check = security.check(base_cmd)
        if not check["allowed"]:
            return {"success": False, "error": f"Bloqué par security : {check['reason']}"}

        # Lancement
        try:
            cmd_parts = shlex.split(cfg["cmd"])
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            import subprocess
            proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
                cwd="/tmp",
                preexec_fn=os.setsid,
            )

            c2.process = proc
            c2.started_at = time.time()
            c2.logs.clear()
            c2._log_ts(f"[C2] {name} démarré — PID {proc.pid} — {datetime.now().strftime('%H:%M:%S')}")

            # Thread de capture des logs
            t = threading.Thread(target=self._capture, args=(c2,), daemon=True)
            t.start()
            c2._thread = t

            logger.info(f"[C2] {name} lancé PID={proc.pid}")
            return {"success": True, "name": name, "pid": proc.pid, "message": f"{name} démarré (PID {proc.pid})"}

        except FileNotFoundError:
            return {"success": False, "error": f"Binaire introuvable : {cfg['cmd'].split()[0]}. Installer avec apt."}
        except PermissionError as e:
            return {"success": False, "error": f"Permission refusée : {e}"}
        except Exception as e:
            logger.error(f"[C2] Erreur démarrage {name} : {e}")
            return {"success": False, "error": str(e)}

    # ── Arrêt ─────────────────────────────────────────────────────────────────

    def stop(self, name: str) -> dict:
        c2 = self._procs.get(name)
        if not c2:
            return {"success": False, "error": f"C2 inconnu : {name}"}
        if not c2.running:
            return {"success": False, "error": f"{name} n'est pas en cours d'exécution"}

        pid = c2.pid
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
            for _ in range(30):
                if not c2.running:
                    break
                time.sleep(0.1)
            if c2.running:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            c2._log_ts(f"[C2] {name} arrêté.")
            logger.info(f"[C2] {name} arrêté (PID {pid})")
            return {"success": True, "name": name, "message": f"{name} arrêté (PID {pid})"}
        except ProcessLookupError:
            return {"success": True, "name": name, "message": f"{name} déjà terminé"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self, name: str) -> dict:
        cfg = C2_CONFIGS.get(name)
        c2 = self._procs.get(name)
        if not cfg or not c2:
            return {"error": f"C2 inconnu : {name}"}
        return {
            "name": name,
            "running": c2.running,
            "pid": c2.pid,
            "uptime": c2.uptime,
            "port": cfg["port"],
            "description": cfg["description"],
            "color": cfg["color"],
            "needs_sudo": cfg["needs_sudo"],
            "returncode": c2.process.poll() if c2.process else None,
        }

    def list_all(self) -> list:
        return [self.status(name) for name in C2_CONFIGS]

    # ── Logs ──────────────────────────────────────────────────────────────────

    def logs(self, name: str, n: int = 100) -> dict:
        c2 = self._procs.get(name)
        if not c2:
            return {"error": f"C2 inconnu : {name}"}
        lines = list(c2.logs)[-n:]
        return {"name": name, "running": c2.running, "lines": lines, "total": len(c2.logs)}

    # ── Interne ───────────────────────────────────────────────────────────────

    def _capture(self, c2: C2Process):
        try:
            for line in c2.process.stdout:
                c2.logs.append(line.rstrip())
        except Exception:
            pass
        rc = c2.process.wait()
        c2._log_ts(f"[C2] {c2.name} terminé — code retour : {rc}")

    def _prepare(self, name: str, cfg: dict) -> Optional[str]:
        if name == "havoc":
            profile = "/tmp/havoc.yaotl"
            if not os.path.exists(profile):
                try:
                    with open(profile, "w") as f:
                        f.write(_HAVOC_PROFILE)
                except Exception as e:
                    return f"Impossible de créer le profil Havoc : {e}"
        return None


# Monkey-patch pour ajouter la méthode _log_ts sur C2Process
def _log_ts(self, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    self.logs.append(f"[{ts}] {msg}")

C2Process._log_ts = _log_ts  # type: ignore

c2_manager = C2Manager()
