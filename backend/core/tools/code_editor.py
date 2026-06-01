"""
CodeEditor — lecture/écriture multi-fichiers pour l'agent de programmation.
Backup automatique, diff avant application, patch partiel.
"""
from __future__ import annotations

import os
import re
import shutil
import difflib
from pathlib import Path
from datetime import datetime
from typing import Optional
from core.tools.logger import get_logger

logger = get_logger(__name__)

_BACKUP_DIR = Path("/tmp/eye_backups")
_MAX_READ_SIZE = 500_000  # 500 Ko


class CodeEditor:

    def read(self, path: str) -> dict:
        """Lit un fichier entier."""
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Fichier introuvable : {path}"}
        if p.is_dir():
            return {"success": False, "error": f"C'est un répertoire : {path}"}
        size = p.stat().st_size
        if size > _MAX_READ_SIZE:
            return {"success": False, "error": f"Fichier trop volumineux ({size} octets)"}
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            return {
                "success": True,
                "path": str(p.resolve()),
                "content": content,
                "lines": len(lines),
                "size": size,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_lines(self, path: str, start: int = 1, end: Optional[int] = None) -> dict:
        """Lit un segment de fichier (lignes start..end)."""
        result = self.read(path)
        if not result["success"]:
            return result
        lines = result["content"].splitlines()
        s = max(0, start - 1)
        e = end if end else len(lines)
        excerpt = "\n".join(f"{i+s+1:4} | {l}" for i, l in enumerate(lines[s:e]))
        return {"success": True, "path": path, "content": excerpt, "total_lines": len(lines)}

    def write(self, path: str, content: str, backup: bool = True) -> dict:
        """Écrit un fichier complet (crée les répertoires si nécessaire)."""
        p = Path(path)
        old_content = None

        if p.exists() and backup:
            old_content = p.read_text(encoding="utf-8", errors="replace")
            self._backup(p, old_content)

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            logger.info(f"[WRITE] {path} ({len(content)} chars)")

            diff = ""
            if old_content is not None:
                diff = self._diff(old_content, content, path)

            return {
                "success": True,
                "path": str(p.resolve()),
                "lines": content.count("\n") + 1,
                "diff": diff,
                "created": old_content is None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def patch(self, path: str, old_str: str, new_str: str, backup: bool = True) -> dict:
        """Remplace old_str par new_str dans le fichier (patch précis)."""
        result = self.read(path)
        if not result["success"]:
            return result

        content = result["content"]
        if old_str not in content:
            # Essai avec normalisation des espaces
            norm_content = re.sub(r"\s+", " ", content)
            norm_old = re.sub(r"\s+", " ", old_str)
            if norm_old not in norm_content:
                return {"success": False, "error": f"Pattern introuvable dans {path}"}

        if backup:
            self._backup(Path(path), content)

        new_content = content.replace(old_str, new_str, 1)
        diff = self._diff(content, new_content, path)

        try:
            Path(path).write_text(new_content, encoding="utf-8")
            logger.info(f"[PATCH] {path}")
            return {"success": True, "path": path, "diff": diff}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def insert_after(self, path: str, marker: str, insertion: str, backup: bool = True) -> dict:
        """Insère du texte après la première occurrence de marker."""
        result = self.read(path)
        if not result["success"]:
            return result
        content = result["content"]
        idx = content.find(marker)
        if idx == -1:
            return {"success": False, "error": f"Marker introuvable : {marker!r}"}

        if backup:
            self._backup(Path(path), content)

        new_content = content[:idx + len(marker)] + insertion + content[idx + len(marker):]
        diff = self._diff(content, new_content, path)
        try:
            Path(path).write_text(new_content, encoding="utf-8")
            return {"success": True, "path": path, "diff": diff}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete(self, path: str, backup: bool = True) -> dict:
        """Supprime un fichier (avec backup optionnel)."""
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Fichier introuvable : {path}"}
        if backup:
            self._backup(p, p.read_text(encoding="utf-8", errors="replace"))
        try:
            p.unlink()
            logger.info(f"[DELETE] {path}")
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def preview_diff(self, path: str, new_content: str) -> dict:
        """Affiche le diff sans appliquer le changement."""
        result = self.read(path)
        old = result.get("content", "") if result["success"] else ""
        diff = self._diff(old, new_content, path)
        return {"path": path, "diff": diff, "applied": False}

    def multi_write(self, changes: list[dict]) -> dict:
        """
        Applique plusieurs modifications en une fois.
        Chaque élément : {"path": str, "content": str} ou {"path": str, "old": str, "new": str}
        """
        results = []
        errors = []
        for change in changes:
            p = change.get("path", "")
            if "content" in change:
                r = self.write(p, change["content"])
            elif "old" in change and "new" in change:
                r = self.patch(p, change["old"], change["new"])
            else:
                r = {"success": False, "error": "Format invalide (besoin de 'content' ou 'old'+'new')"}
            results.append({"path": p, **r})
            if not r["success"]:
                errors.append(f"{p}: {r.get('error', '?')}")

        return {
            "success": len(errors) == 0,
            "applied": len(results) - len(errors),
            "errors": errors,
            "results": results,
        }

    def list_dir(self, path: str, recursive: bool = False) -> dict:
        """Liste le contenu d'un répertoire."""
        p = Path(path)
        if not p.exists():
            return {"success": False, "error": f"Répertoire introuvable : {path}"}
        if not p.is_dir():
            return {"success": False, "error": f"Ce n'est pas un répertoire : {path}"}
        try:
            if recursive:
                files = [str(f.relative_to(p)) for f in p.rglob("*") if f.is_file()]
            else:
                files = [e.name + ("/" if e.is_dir() else "") for e in sorted(p.iterdir())]
            return {"success": True, "path": str(p), "entries": files}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Internals ─────────────────────────────────────────────────────────────

    def _backup(self, path: Path, content: str):
        try:
            _BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_name = str(path).replace("/", "_").lstrip("_")
            backup_path = _BACKUP_DIR / f"{ts}_{safe_name}"
            backup_path.write_text(content, encoding="utf-8")
            logger.debug(f"[BACKUP] {backup_path}")
        except Exception:
            pass

    def _diff(self, old: str, new: str, path: str) -> str:
        old_lines = old.splitlines(keepends=True)
        new_lines = new.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"a/{path}", tofile=f"b/{path}",
            n=3,
        )
        return "".join(diff)


code_editor = CodeEditor()
