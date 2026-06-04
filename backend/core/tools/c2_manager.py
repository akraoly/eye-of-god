"""
C2Manager — gestion asynchrone des frameworks C2 (Sliver, Havoc, Gophish, Evilginx).
- Sliver / Havoc / Evilginx : subprocess Popen non-bloquant + thread de capture logs
- Gophish : service systemd (systemctl start/stop/status + journalctl pour les logs)
"""
import os
import shlex
import signal
import subprocess
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

from core.tools.logger import get_logger
from core.tools.security import security

logger = get_logger(__name__)

# ── Configs C2 ────────────────────────────────────────────────────────────────
# "systemd" : nom du service systemd  (piloté via systemctl)
# "cmd"     : commande directe        (piloté via Popen)

C2_CONFIGS = {
    "sliver": {
        "cmd": "sliver-server",
        "description": "C2 Sliver — implants cross-platform MTLS/HTTP/DNS",
        "port": 31337,
        "color": "#10b981",
        "needs_sudo": False,
    },
    "havoc": {
        "cmd": "havoc server --profile /tmp/havoc.yaotl",
        "description": "Havoc C2 — Teamserver GUI (port 40056)",
        "port": 40056,
        "color": "#f97316",
        "needs_sudo": False,
    },
    "gophish": {
        "cmd": "/usr/lib/gophish/gophish --config /tmp/gophish_local/config.json",
        "cwd": "/usr/lib/gophish",     # les migrations sont relatives à ce répertoire
        "description": "Gophish — campagnes phishing (UI https://127.0.0.1:3334)",
        "port": 3334,
        "color": "#38bdf8",
        "needs_sudo": False,
    },
    "evilginx": {
        "cmd": "unbuffer evilginx -p /home/kali/.evilginx/phishlets -developer",
        "description": "Evilginx — AiTM proxy MFA bypass (port 443/80)",
        "port": 443,
        "color": "#a78bfa",
        "needs_sudo": True,
    },
}

# Config Gophish — lance en mode direct (sans systemd, sans sudo)
# Admin sur 3333 si libre, sinon 3334 pour éviter conflit avec le service système Kali
_GOPHISH_CONFIG = """\
{
  "admin_server": {
    "listen_url": "0.0.0.0:3334",
    "use_tls": true,
    "cert_path": "/tmp/gophish_local/gophish_admin.crt",
    "key_path": "/tmp/gophish_local/gophish_admin.key"
  },
  "phish_server": {
    "listen_url": "0.0.0.0:8080",
    "use_tls": false,
    "cert_path": "",
    "key_path": ""
  },
  "db_name": "sqlite3",
  "db_path": "/tmp/gophish_local/gophish.db",
  "migrations_prefix": "db/db_",
  "contact_address": "",
  "logging": {"filename": "", "level": ""}
}
"""

# Profil Havoc minimal généré automatiquement si absent
_HAVOC_PROFILE = """\
Teamserver {
    Host = "0.0.0.0"
    Port = 40056

    Build {
        Compiler64 = "/usr/bin/x86_64-w64-mingw32-gcc"
        Compiler86 = "/usr/bin/i686-w64-mingw32-gcc"
        Nasm = "/usr/bin/nasm"
    }
}

Operators {
    user "admin" {
        Password = "admin123!"
    }
}

Demon {
    Sleep = 2
    Jitter = 15

    TrustXForwardedFor = false

    Injection {
        Spawn64 = "C:\\\\Windows\\\\System32\\\\notepad.exe"
        Spawn32 = "C:\\\\Windows\\\\SysWOW64\\\\notepad.exe"
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

        if "systemd" in cfg:
            return self._start_systemd(name, cfg)
        return self._start_popen(name, cfg)

    def _start_systemd(self, name: str, cfg: dict) -> dict:
        svc = cfg["systemd"]
        if self._systemd_running(svc):
            pid = self._systemd_pid(svc)
            return {"success": False, "error": f"{name} tourne déjà (PID {pid})"}
        c2 = self._procs[name]
        c2.logs.clear()
        c2._log_ts(f"[C2] Démarrage du service systemd '{svc}'...")
        try:
            r = subprocess.run(
                ["systemctl", "start", svc],
                capture_output=True, text=True, timeout=30,
            )
            if r.returncode != 0:
                err = r.stderr.strip() or r.stdout.strip()
                c2._log_ts(f"[ERREUR] {err}")
                return {"success": False, "error": f"systemctl start {svc} : {err}"}
            # Attendre que le service soit actif (max 10s)
            for _ in range(20):
                if self._systemd_running(svc):
                    break
                time.sleep(0.5)
            pid = self._systemd_pid(svc)
            c2.started_at = time.time()
            c2._log_ts(f"[C2] {name} démarré — PID {pid}")
            # Thread de suivi des logs journalctl
            t = threading.Thread(target=self._capture_journalctl, args=(c2, svc), daemon=True)
            t.start()
            c2._thread = t
            logger.info(f"[C2] {name} (systemd) démarré PID={pid}")
            return {"success": True, "name": name, "pid": pid, "message": f"{name} démarré (PID {pid})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _start_popen(self, name: str, cfg: dict) -> dict:
        c2 = self._procs[name]
        if c2.running:
            return {"success": False, "error": f"{name} tourne déjà (PID {c2.pid})"}

        prep_err = self._prepare(name, cfg)
        if prep_err:
            return {"success": False, "error": prep_err}

        base_cmd = cfg["cmd"].split()[0]
        check = security.check(base_cmd)
        if not check["allowed"]:
            return {"success": False, "error": f"Bloqué par security : {check['reason']}"}

        try:
            cmd_parts = shlex.split(cfg["cmd"])
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"
            work_dir = cfg.get("cwd", "/tmp")
            proc = subprocess.Popen(
                cmd_parts,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                env=env,
                cwd=work_dir,
                preexec_fn=os.setsid,
            )
            c2.process = proc
            c2.started_at = time.time()
            c2.logs.clear()
            c2._log_ts(f"[C2] {name} démarré — PID {proc.pid} — {datetime.now().strftime('%H:%M:%S')}")
            t = threading.Thread(target=self._capture, args=(c2,), daemon=True)
            t.start()
            c2._thread = t
            logger.info(f"[C2] {name} lancé PID={proc.pid}")
            return {"success": True, "name": name, "pid": proc.pid, "message": f"{name} démarré (PID {proc.pid})"}
        except FileNotFoundError:
            return {"success": False, "error": f"Binaire introuvable : {base_cmd}. Installer avec apt."}
        except PermissionError as e:
            return {"success": False, "error": f"Permission refusée : {e}"}
        except Exception as e:
            logger.error(f"[C2] Erreur démarrage {name} : {e}")
            return {"success": False, "error": str(e)}

    # ── Arrêt ─────────────────────────────────────────────────────────────────

    def stop(self, name: str) -> dict:
        cfg = C2_CONFIGS.get(name)
        if not cfg:
            return {"success": False, "error": f"C2 inconnu : {name}"}
        if "systemd" in cfg:
            return self._stop_systemd(name, cfg)
        return self._stop_popen(name)

    def _stop_systemd(self, name: str, cfg: dict) -> dict:
        svc = cfg["systemd"]
        c2 = self._procs[name]
        if not self._systemd_running(svc):
            return {"success": False, "error": f"{name} n'est pas en cours d'exécution"}
        pid = self._systemd_pid(svc)
        try:
            r = subprocess.run(["systemctl", "stop", svc], capture_output=True, text=True, timeout=15)
            c2.started_at = None
            c2._log_ts(f"[C2] {name} arrêté.")
            logger.info(f"[C2] {name} (systemd) arrêté")
            return {"success": True, "name": name, "message": f"{name} arrêté (PID {pid})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _stop_popen(self, name: str) -> dict:
        c2 = self._procs[name]
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

        if "systemd" in cfg:
            svc = cfg["systemd"]
            running = self._systemd_running(svc)
            pid = self._systemd_pid(svc) if running else None
            uptime = self._systemd_uptime(c2) if running else None
        else:
            running = c2.running
            pid = c2.pid
            uptime = c2.uptime

        return {
            "name": name,
            "running": running,
            "pid": pid,
            "uptime": uptime,
            "port": cfg["port"],
            "description": cfg["description"],
            "color": cfg["color"],
            "needs_sudo": cfg.get("needs_sudo", False),
            "returncode": c2.process.poll() if (c2.process and "systemd" not in cfg) else None,
        }

    def list_all(self) -> list:
        return [self.status(name) for name in C2_CONFIGS]

    # ── Logs ──────────────────────────────────────────────────────────────────

    def logs(self, name: str, n: int = 100) -> dict:
        cfg = C2_CONFIGS.get(name)
        c2 = self._procs.get(name)
        if not cfg or not c2:
            return {"error": f"C2 inconnu : {name}"}

        if "systemd" in cfg:
            running = self._systemd_running(cfg["systemd"])
            # Journalctl en temps réel + ring buffer local
            fresh = self._journalctl_lines(cfg["systemd"], n)
            for line in fresh:
                if line not in c2.logs:
                    c2.logs.append(line)
            lines = list(c2.logs)[-n:]
        else:
            running = c2.running
            lines = list(c2.logs)[-n:]

        return {"name": name, "running": running, "lines": lines, "total": len(c2.logs)}

    # ── Helpers systemd ───────────────────────────────────────────────────────

    @staticmethod
    def _systemd_running(svc: str) -> bool:
        r = subprocess.run(
            ["systemctl", "is-active", "--quiet", svc],
            capture_output=True, timeout=5,
        )
        return r.returncode == 0

    @staticmethod
    def _systemd_pid(svc: str) -> Optional[int]:
        r = subprocess.run(
            ["systemctl", "show", "--property=MainPID", svc],
            capture_output=True, text=True, timeout=5,
        )
        for line in r.stdout.splitlines():
            if line.startswith("MainPID="):
                try:
                    pid = int(line.split("=", 1)[1])
                    return pid if pid > 0 else None
                except ValueError:
                    pass
        return None

    @staticmethod
    def _journalctl_lines(svc: str, n: int) -> list:
        r = subprocess.run(
            ["journalctl", "-u", svc, f"-n{n}", "--no-pager", "--output=short"],
            capture_output=True, text=True, timeout=10,
        )
        return [l for l in r.stdout.splitlines() if l.strip()]

    @staticmethod
    def _systemd_uptime(c2: "C2Process") -> Optional[str]:
        if not c2.started_at:
            return None
        secs = int(time.time() - c2.started_at)
        h, r = divmod(secs, 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # ── Helpers Popen ─────────────────────────────────────────────────────────

    def _capture(self, c2: C2Process):
        try:
            for line in c2.process.stdout:
                c2.logs.append(line.rstrip())
        except Exception:
            pass
        rc = c2.process.wait()
        c2._log_ts(f"[C2] {c2.name} terminé — code retour : {rc}")

    def _capture_journalctl(self, c2: C2Process, svc: str):
        """Suit les logs journalctl -f en live pour un service systemd."""
        try:
            proc = subprocess.Popen(
                ["journalctl", "-u", svc, "-f", "--no-pager", "--output=short"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, bufsize=1,
            )
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    c2.logs.append(stripped)
                # Arrêter si le service est stoppé
                if not self._systemd_running(svc):
                    break
            proc.terminate()
        except Exception:
            pass

    def _prepare(self, name: str, cfg: dict) -> Optional[str]:
        if name == "havoc":
            profile = "/tmp/havoc.yaotl"
            if not os.path.exists(profile):
                try:
                    with open(profile, "w") as f:
                        f.write(_HAVOC_PROFILE)
                except Exception as e:
                    return f"Impossible de créer le profil Havoc : {e}"
        if name == "gophish":
            config_dir = "/tmp/gophish_local"
            config_path = f"{config_dir}/config.json"
            os.makedirs(config_dir, exist_ok=True)
            if not os.path.exists(config_path):
                try:
                    with open(config_path, "w") as f:
                        f.write(_GOPHISH_CONFIG)
                except Exception as e:
                    return f"Impossible de créer la config Gophish : {e}"
        return None


# Monkey-patch pour ajouter la méthode _log_ts sur C2Process
def _log_ts(self, msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    self.logs.append(f"[{ts}] {msg}")

C2Process._log_ts = _log_ts  # type: ignore

c2_manager = C2Manager()
