"""
DevRunner — exécution de commandes de développement.
npm/pip/pytest/cargo/make + interprétation intelligente des résultats.
"""
from __future__ import annotations

import re
import subprocess
import shlex
import os
from pathlib import Path
from typing import Optional
from core.tools.logger import get_logger

logger = get_logger(__name__)

# ── Commandes dev autorisées (complément à security.py) ──────────────────────
_DEV_COMMANDS = {
    # Package managers
    "npm", "npx", "yarn", "pnpm", "bun",
    "pip", "pip3", "uv", "poetry", "pipenv", "conda",
    "cargo", "rustc", "rustup",
    "mvn", "gradle", "ant",
    "go",
    "composer",

    # Test runners
    "pytest", "py.test",
    "jest", "vitest", "mocha", "jasmine",
    "go", "cargo",

    # Build
    "make", "cmake", "ninja", "meson",
    "tsc", "babel", "webpack", "rollup", "esbuild",
    "vite",

    # Linters / formatters
    "eslint", "tslint", "prettier",
    "pylint", "flake8", "ruff", "black", "isort", "mypy", "pyright",
    "rubocop", "golangci-lint", "clippy",

    # Git (déjà dans security mais répété pour clarté)
    "git",

    # Docker
    "docker", "docker-compose", "docker compose",

    # Autres utilitaires dev
    "which", "env", "printenv",
}

_DESTROY_BLOCKED = [
    r"rm\s+.*-[rf]",
    r"git\s+push\s+--force",
    r"git\s+reset\s+--hard",
    r"git\s+clean\s+-fd",
    r"docker\s+system\s+prune",
    r"npm\s+publish",
    r"pip\s+uninstall",
]
_DESTROY_RE = [re.compile(p, re.IGNORECASE) for p in _DESTROY_BLOCKED]


class DevRunner:

    def run(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 120,
        env_extra: Optional[dict] = None,
    ) -> dict:
        # Bloquer les commandes destructrices
        for pattern in _DESTROY_RE:
            if pattern.search(command):
                return {
                    "success": False,
                    "error": f"Commande bloquée (destructrice) : {command}",
                    "blocked": True,
                }

        # Vérifier que la commande de base est autorisée
        try:
            parts = shlex.split(command)
        except ValueError as e:
            return {"success": False, "error": f"Parsing échoué : {e}"}

        if not parts:
            return {"success": False, "error": "Commande vide"}

        base = parts[0].split("/")[-1]
        # Accepter si dans _DEV_COMMANDS ou dans la whitelist principale
        from core.tools.security import ALLOWED_COMMANDS
        if base not in _DEV_COMMANDS and base not in ALLOWED_COMMANDS:
            return {
                "success": False,
                "error": f"'{base}' non autorisé. Commandes dev disponibles : npm/pip/pytest/cargo/make/git/docker...",
            }

        work_dir = cwd if (cwd and Path(cwd).is_dir()) else str(Path.cwd())
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)

        logger.info(f"[DEV] cmd={command!r} cwd={work_dir}")
        try:
            result = subprocess.run(
                parts,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=work_dir,
                env=env,
            )
            stdout = result.stdout
            stderr = result.stderr
            success = result.returncode == 0

            # Parser les résultats
            parsed = self._parse_output(base, stdout, stderr, result.returncode)

            return {
                "success": success,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
                "parsed": parsed,
                "command": command,
                "cwd": work_dir,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"Timeout ({timeout}s)", "command": command}
        except FileNotFoundError:
            return {"success": False, "error": f"Commande introuvable : {base}. Installée ?"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_output(self, cmd: str, stdout: str, stderr: str, rc: int) -> dict:
        """Interprète la sortie selon la commande."""
        result = {"tool": cmd, "exit_code": rc}
        combined = stdout + stderr

        if cmd in ("pytest", "py.test"):
            m = re.search(r"(\d+) passed", combined)
            if m:
                result["passed"] = int(m.group(1))
            m = re.search(r"(\d+) failed", combined)
            if m:
                result["failed"] = int(m.group(1))
            m = re.search(r"(\d+) error", combined)
            if m:
                result["errors"] = int(m.group(1))
            result["status"] = "pass" if rc == 0 else "fail"

        elif cmd in ("jest", "vitest", "mocha"):
            m = re.search(r"(\d+)\s+(?:tests?|specs?)\s+passed", combined, re.IGNORECASE)
            if m:
                result["passed"] = int(m.group(1))
            m = re.search(r"(\d+)\s+(?:tests?|specs?)\s+failed", combined, re.IGNORECASE)
            if m:
                result["failed"] = int(m.group(1))

        elif cmd == "npm":
            if "npm warn" in combined.lower() or "npm error" in combined.lower():
                warns = re.findall(r"npm warn (.+)", combined, re.IGNORECASE)
                result["warnings"] = warns[:5]
            if rc == 0:
                result["status"] = "ok"

        elif cmd in ("pip", "pip3", "uv"):
            installs = re.findall(r"Successfully installed (.+)", combined)
            if installs:
                result["installed"] = installs[0].split()
            already = re.findall(r"already satisfied: (\S+)", combined)
            if already:
                result["already_installed"] = already[:5]

        elif cmd == "git":
            if "nothing to commit" in combined:
                result["status"] = "clean"
            elif "Changes not staged" in combined or "Changes to be committed" in combined:
                result["status"] = "dirty"
            files_changed = re.findall(r"modified:\s+(.+)", combined)
            if files_changed:
                result["modified_files"] = [f.strip() for f in files_changed]

        elif cmd in ("eslint", "ruff", "flake8", "pylint", "mypy"):
            errors = re.findall(r"error\s+(.+)", combined, re.IGNORECASE)
            warnings = re.findall(r"warning\s+(.+)", combined, re.IGNORECASE)
            result["errors"] = errors[:10]
            result["warnings"] = warnings[:10]
            result["status"] = "ok" if rc == 0 else "issues"

        elif cmd in ("gcc", "g++", "clang", "tsc", "cargo", "go"):
            errors = re.findall(r"error(?:\[.*?\])?:\s*(.+)", combined)
            warnings = re.findall(r"warning(?:\[.*?\])?:\s*(.+)", combined)
            result["compile_errors"] = errors[:10]
            result["compile_warnings"] = warnings[:5]
            result["status"] = "compiled" if rc == 0 else "failed"

        elif cmd == "docker":
            result["status"] = "ok" if rc == 0 else "error"

        return result

    def install_deps(self, project_dir: str) -> dict:
        """Détecte le gestionnaire de packages et installe les dépendances."""
        root = Path(project_dir)
        results = []

        if (root / "package.json").exists():
            r = self.run("npm install", cwd=project_dir, timeout=180)
            results.append({"manager": "npm", **r})

        if (root / "requirements.txt").exists():
            r = self.run(f"pip install -r requirements.txt", cwd=project_dir, timeout=120)
            results.append({"manager": "pip", **r})

        if (root / "pyproject.toml").exists() and not (root / "requirements.txt").exists():
            r = self.run("pip install -e .", cwd=project_dir, timeout=120)
            results.append({"manager": "pip (pyproject)", **r})

        if (root / "Cargo.toml").exists():
            r = self.run("cargo build", cwd=project_dir, timeout=300)
            results.append({"manager": "cargo", **r})

        if (root / "go.mod").exists():
            r = self.run("go mod download", cwd=project_dir, timeout=120)
            results.append({"manager": "go", **r})

        if not results:
            return {"success": False, "error": "Aucun gestionnaire de packages détecté"}

        return {
            "success": all(r.get("success", False) for r in results),
            "results": results,
        }

    def run_tests(self, project_dir: str, test_cmd: Optional[str] = None) -> dict:
        """Détecte et lance les tests du projet."""
        root = Path(project_dir)

        if test_cmd:
            return self.run(test_cmd, cwd=project_dir, timeout=120)

        # Auto-détection
        if (root / "pytest.ini").exists() or (root / "pyproject.toml").exists():
            cmd = "pytest -v --tb=short"
        elif (root / "package.json").exists():
            pkg = (root / "package.json").read_text()
            if '"test"' in pkg:
                cmd = "npm test -- --watchAll=false"
            else:
                cmd = "npx jest"
        elif (root / "Cargo.toml").exists():
            cmd = "cargo test"
        elif (root / "go.mod").exists():
            cmd = "go test ./..."
        elif (root / "Makefile").exists():
            cmd = "make test"
        else:
            return {"success": False, "error": "Aucun test détecté"}

        return self.run(cmd, cwd=project_dir, timeout=120)

    def lint(self, project_dir: str) -> dict:
        """Lance le linter approprié."""
        root = Path(project_dir)

        if (root / ".flake8").exists() or list(root.glob("**/*.py")):
            if shutil.which("ruff"):
                return self.run("ruff check .", cwd=project_dir)
            elif shutil.which("flake8"):
                return self.run("flake8 .", cwd=project_dir)

        if (root / ".eslintrc.js").exists() or (root / ".eslintrc.json").exists():
            return self.run("eslint . --ext .js,.ts,.jsx,.tsx", cwd=project_dir)

        return {"success": False, "error": "Aucun linter configuré"}


import shutil  # noqa: E402

dev_runner = DevRunner()
