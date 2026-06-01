"""
GitManager — opérations Git pour l'agent de programmation.
Status, diff, log, add, commit, push, pull, branch.
"""
from __future__ import annotations

import re
import subprocess
import shlex
from pathlib import Path
from typing import Optional
from core.tools.logger import get_logger

logger = get_logger(__name__)

_SAFE_GIT_CMDS = {
    "status", "diff", "log", "show", "branch", "remote",
    "fetch", "pull", "push", "add", "commit", "checkout",
    "merge", "rebase", "stash", "tag", "describe", "rev-parse",
    "ls-files", "blame", "shortlog", "config",
}

_BLOCKED_GIT = {
    "push --force", "push -f",
    "reset --hard",
    "clean -fd", "clean -f",
    "checkout -- .",
}


class GitManager:

    def _run(self, args: list[str], cwd: str, timeout: int = 30) -> dict:
        cmd_str = " ".join(args)
        # Vérifier sous-commande
        subcmd = args[1] if len(args) > 1 else ""
        if subcmd not in _SAFE_GIT_CMDS:
            return {"success": False, "error": f"git {subcmd} non autorisé"}

        # Bloquer les options dangereuses
        full = " ".join(args[1:])
        for blocked in _BLOCKED_GIT:
            if blocked in full:
                return {"success": False, "error": f"git {blocked} bloqué (destructeur)"}

        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"git timeout ({timeout}s)"}
        except FileNotFoundError:
            return {"success": False, "error": "git non installé"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def status(self, repo_path: str) -> dict:
        r = self._run(["git", "status", "--porcelain", "-b"], cwd=repo_path)
        if not r["success"]:
            return r
        out = r["stdout"]
        lines = out.splitlines()
        branch_line = lines[0] if lines else ""
        m = re.match(r"## (.+?)(?:\.\.\.|\s|$)", branch_line)
        branch = m.group(1) if m else "unknown"

        modified, added, deleted, untracked = [], [], [], []
        for line in lines[1:]:
            if len(line) < 3:
                continue
            xy = line[:2]
            fname = line[3:]
            if xy.strip() in ("M", "MM"):
                modified.append(fname)
            elif xy.strip() in ("A", "AM"):
                added.append(fname)
            elif xy.strip() in ("D", "DM"):
                deleted.append(fname)
            elif xy == "??":
                untracked.append(fname)

        return {
            "success": True,
            "branch": branch,
            "modified": modified,
            "added": added,
            "deleted": deleted,
            "untracked": untracked,
            "clean": not (modified or added or deleted or untracked),
        }

    def diff(self, repo_path: str, staged: bool = False, file: Optional[str] = None) -> dict:
        args = ["git", "diff"]
        if staged:
            args.append("--cached")
        if file:
            args += ["--", file]
        r = self._run(args, cwd=repo_path, timeout=15)
        return r

    def log(self, repo_path: str, n: int = 10, oneline: bool = True) -> dict:
        args = ["git", "log", f"-{n}"]
        if oneline:
            args += ["--oneline", "--graph", "--decorate"]
        r = self._run(args, cwd=repo_path)
        if not r["success"]:
            return r
        commits = []
        for line in r["stdout"].splitlines():
            m = re.match(r"[*|\s]*([a-f0-9]{6,}) (.+)", line)
            if m:
                commits.append({"hash": m.group(1), "message": m.group(2)})
        r["commits"] = commits
        return r

    def add(self, repo_path: str, files: list[str] | str = ".") -> dict:
        if isinstance(files, str):
            files = [files]
        args = ["git", "add"] + files
        return self._run(args, cwd=repo_path)

    def commit(self, repo_path: str, message: str, add_all: bool = False) -> dict:
        if add_all:
            r = self.add(repo_path, ".")
            if not r["success"]:
                return r
        args = ["git", "commit", "-m", message]
        return self._run(args, cwd=repo_path, timeout=30)

    def push(self, repo_path: str, remote: str = "origin", branch: str = "") -> dict:
        args = ["git", "push", remote]
        if branch:
            args.append(branch)
        return self._run(args, cwd=repo_path, timeout=60)

    def pull(self, repo_path: str) -> dict:
        return self._run(["git", "pull"], cwd=repo_path, timeout=60)

    def branch_list(self, repo_path: str) -> dict:
        r = self._run(["git", "branch", "-a"], cwd=repo_path)
        if r["success"]:
            branches = [b.strip().lstrip("* ") for b in r["stdout"].splitlines()]
            r["branches"] = branches
        return r

    def create_branch(self, repo_path: str, branch_name: str, checkout: bool = True) -> dict:
        if checkout:
            args = ["git", "checkout", "-b", branch_name]
        else:
            args = ["git", "branch", branch_name]
        return self._run(args, cwd=repo_path)

    def is_git_repo(self, path: str) -> bool:
        r = self._run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
        return r.get("stdout", "").strip() == "true"

    def init(self, path: str) -> dict:
        try:
            result = subprocess.run(
                ["git", "init"],
                capture_output=True, text=True, timeout=15, cwd=path,
            )
            return {"success": result.returncode == 0, "stdout": result.stdout.strip()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def summary(self, repo_path: str) -> str:
        """Résumé complet de l'état git pour l'IA."""
        s = self.status(repo_path)
        l = self.log(repo_path, n=5)
        lines = [f"Dépôt Git : {repo_path}"]

        if s["success"]:
            lines.append(f"Branche  : {s['branch']}")
            lines.append(f"Propre   : {'oui' if s['clean'] else 'non'}")
            if s["modified"]:
                lines.append(f"Modifiés : {', '.join(s['modified'][:5])}")
            if s["added"]:
                lines.append(f"Ajoutés  : {', '.join(s['added'][:5])}")
            if s["untracked"]:
                lines.append(f"Non suivi: {', '.join(s['untracked'][:5])}")
        else:
            lines.append(f"Git: {s.get('error', 'erreur')}")

        if l["success"] and l.get("commits"):
            lines.append("Derniers commits :")
            for c in l["commits"][:5]:
                lines.append(f"  {c['hash']} {c['message']}")

        return "\n".join(lines)


git_manager = GitManager()
