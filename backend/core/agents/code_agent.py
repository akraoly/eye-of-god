"""
CodeAgent — assistant de programmation autonome.
Explore, planifie, édite, exécute, débogue — du début à la fin d'un projet.
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from core.agents.base_agent import BaseAgent
from core.tools.project_explorer import project_explorer
from core.tools.code_editor import code_editor
from core.tools.dev_runner import dev_runner
from core.tools.git_manager import git_manager
from core.tools.logger import get_logger

logger = get_logger(__name__)

_CODE_KEYWORDS = [
    # Exploration
    "explore le projet", "explore le code", "analyse le projet", "analyse le code",
    "comprends le projet", "lis le fichier", "lire le fichier",
    "ouvre le fichier", "montre le code", "affiche le contenu",
    "structure du projet", "arborescence", "architecture du projet",
    # Edition
    "crée le fichier", "créer le fichier", "écris le code", "écris dans",
    "modifie le fichier", "modifie le code", "édite le fichier",
    "ajoute la fonction", "ajouter la fonction", "supprime la fonction",
    "refactore", "renomme", "implémente", "implémenter",
    "développe", "programme",
    # Exécution
    "lance la commande", "lancer la commande", "exécute la commande",
    "exécute le script", "installe les dépendances", "installe le paquet",
    "npm install", "pip install", "cargo build",
    "compile le projet", "build le projet", "démarre le serveur",
    # Tests
    "lance les tests", "exécute les tests", "pytest", "jest", "unittest",
    "teste le code", "tests unitaires", "tests d'intégration",
    # Debug
    "debug", "débug", "traceback", "stack trace",
    "corrige l'erreur", "corrige le bug", "fixe le bug", "répare le code",
    "analyse l'erreur", "explique l'erreur",
    # Git
    "git status", "git diff", "git log", "git commit", "git push",
    "git pull", "git branch", "commit les changements",
    # Planification code
    "plan de développement", "planifie le code", "étapes de développement",
    "liste les tâches de code",
    # Lint / qualité
    "lint", "linter", "ruff check", "eslint", "pylint", "mypy",
    "format le code", "qualité du code",
]


@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"   # pending | in_progress | done | failed
    result: str = ""
    steps: list[str] = field(default_factory=list)


@dataclass
class ProjectSession:
    """Contexte de projet courant — persiste pendant la session."""
    root: Optional[str] = None
    tasks: list[Task] = field(default_factory=list)
    _task_counter: int = 0

    def add_task(self, title: str, steps: list[str] = None) -> Task:
        self._task_counter += 1
        t = Task(id=self._task_counter, title=title, steps=steps or [])
        self.tasks.append(t)
        return t

    def pending_tasks(self) -> list[Task]:
        return [t for t in self.tasks if t.status == "pending"]

    def summary(self) -> str:
        if not self.tasks:
            return "Aucune tâche en cours."
        lines = [f"Tâches ({len(self.tasks)}) :"]
        icons = {"pending": "⏳", "in_progress": "🔄", "done": "✅", "failed": "❌"}
        for t in self.tasks[-10:]:
            lines.append(f"  {icons.get(t.status, '?')} #{t.id} {t.title}")
        return "\n".join(lines)


# Session globale (une par backend process — suffit pour usage mono-utilisateur)
_session = ProjectSession()


class CodeAgent(BaseAgent):
    name = "code"
    description = "Assistant programmation autonome — explore, code, teste, débogue, git"

    def can_handle(self, task: str) -> bool:
        t = task.lower()
        return any(kw in t for kw in _CODE_KEYWORDS)

    async def run(self, task: str, context: Optional[dict] = None) -> dict:
        t = task.lower().strip()
        ctx = context or {}

        # ── Exploration de projet ─────────────────────────────────────────────
        if any(kw in t for kw in ["explore", "analyse le projet", "structure", "arborescence", "architecture du projet"]):
            path = self._extract_path(task) or _session.root or "."
            return self._explore(path)

        # ── Lecture de fichier ────────────────────────────────────────────────
        if any(kw in t for kw in ["lis le fichier", "lire le fichier", "ouvre le fichier", "montre le code", "affiche le contenu"]):
            path = self._extract_path(task)
            if not path:
                return self._result(True,
                    "📂 Lis le fichier — Exemples :\n\n"
                    "  lis le fichier /home/kali/eye-of-god/backend/app/main.py\n"
                    "  montre le code backend/core/orchestrator.py\n"
                    "  affiche le contenu requirements.txt lignes 1 à 20")
            return self._read_file(path, task)

        # ── Écriture / création de fichier ────────────────────────────────────
        if any(kw in t for kw in ["crée le fichier", "créer le fichier", "écris dans", "write to"]):
            path = self._extract_path(task)
            if not path:
                return self._result(True, "📝 Crée le fichier — Spécifie le chemin :\n  crée le fichier /tmp/mon_script.py")
            content = ctx.get("content", "")
            if not content:
                return self._result(True, f"📝 Fichier cible : {path}\nFournis le contenu dans le contexte (context.content).")
            return self._write_file(path, content)

        # ── Modification (patch) ──────────────────────────────────────────────
        if any(kw in t for kw in ["modifie le fichier", "modifie le code", "édite le fichier", "remplace", "patch"]):
            path = self._extract_path(task)
            if path and ctx.get("old") and ctx.get("new"):
                r = code_editor.patch(path, ctx["old"], ctx["new"])
                return self._result(r["success"], r.get("diff") or r.get("error", ""), r)
            if path:
                return self._result(True, f"📝 Fichier : {path}\nFournis context.old (texte à remplacer) et context.new (nouveau texte).")
            return self._result(True, "📝 Modification — Spécifie le fichier :\n  modifie le fichier /chemin/fichier.py")

        # ── Listing de répertoire ─────────────────────────────────────────────
        if any(kw in t for kw in ["liste les fichiers", "arborescence"]):
            path = self._extract_path(task) or _session.root or "."
            r = code_editor.list_dir(path, recursive="recursive" in t or "-r" in t)
            if r["success"]:
                return self._result(True, "\n".join(r["entries"][:80]))
            return self._result(True, f"📂 Impossible de lister {path} : {r['error']}")

        # ── Exécution / installation ──────────────────────────────────────────
        if any(kw in t for kw in ["installe", "installer", "install", "npm install", "pip install"]):
            path = self._extract_path(task) or _session.root or "."
            cmd = self._extract_command(task)
            if cmd:
                r = dev_runner.run(cmd, cwd=path)
            else:
                r = dev_runner.install_deps(path)
            return self._format_dev_result(r, "Installation")

        if any(kw in t for kw in ["lance la commande", "lancer la commande", "exécute la commande", "exécute le script", "démarre le serveur"]):
            cmd = self._extract_command(task)
            path = self._extract_path(task) or _session.root or "."
            if not cmd:
                return self._result(True,
                    "⚡ Exécution — Exemples :\n\n"
                    "  lance la commande `python3 script.py`\n"
                    "  exécute le script /tmp/test.sh\n"
                    "  démarre le serveur `uvicorn app.main:app --port 8080`")
            r = dev_runner.run(cmd, cwd=path, timeout=60)
            return self._format_dev_result(r, "Exécution")

        # ── Tests ──────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["lance les tests", "exécute les tests", "pytest", "jest", "unittest",
                                   "teste le code", "tests unitaires", "tests d'intégration"]):
            path = self._extract_path(task) or _session.root or "."
            cmd = None
            if "pytest" in t:
                cmd = "pytest -v --tb=short"
            elif "jest" in t:
                cmd = "npx jest --watchAll=false"
            r = dev_runner.run_tests(path, test_cmd=cmd)
            # "Aucun test détecté" n'est pas une erreur, c'est un guide
            if not r.get("success") and "aucun test" in (r.get("error","") + r.get("stderr","")).lower():
                return self._result(True,
                    "🧪 Aucun test détecté dans ce répertoire.\n\n"
                    "Pour créer des tests :\n"
                    "  Python  : pytest + fichiers test_*.py\n"
                    "  JS/TS   : jest + fichiers *.test.js\n"
                    "  Rust    : cargo test\n\n"
                    "Spécifie le répertoire avec les tests ou lance `pytest /chemin/tests/`")
            return self._format_dev_result(r, "Tests")

        # ── Compilation / build ───────────────────────────────────────────────
        if any(kw in t for kw in ["compile le projet", "build le projet", "construis"]):
            cmd = self._extract_command(task)
            path = self._extract_path(task) or _session.root or "."
            if not cmd:
                p = Path(path)
                if (p / "Makefile").exists():
                    cmd = "make"
                elif (p / "Cargo.toml").exists():
                    cmd = "cargo build"
                elif (p / "package.json").exists():
                    cmd = "npm run build"
                elif (p / "pyproject.toml").exists() or (p / "setup.py").exists():
                    cmd = "pip install -e ."
                else:
                    return self._result(True,
                        f"🏗️  Build — Aucun système détecté dans {path}\n\n"
                        "Spécifie la commande :\n"
                        "  compile le projet `make`\n"
                        "  build le projet `cargo build`\n"
                        "  build le projet `npm run build`")
            r = dev_runner.run(cmd, cwd=path, timeout=180)
            return self._format_dev_result(r, "Build")

        # ── Lint / qualité ────────────────────────────────────────────────────
        if any(kw in t for kw in ["lint", "linter", "ruff check", "eslint", "pylint", "mypy",
                                   "format le code", "qualité du code"]):
            path = self._extract_path(task) or _session.root or "."
            r = dev_runner.lint(path)
            if not r.get("success") and "aucun linter" in (r.get("error","") + r.get("stderr","")).lower():
                return self._result(True,
                    f"🔍 Lint — Aucun linter configuré dans {path}\n\n"
                    "Linters disponibles :\n"
                    "  Python : ruff check . --fix   (ou pylint, flake8, mypy)\n"
                    "  JS/TS  : npx eslint . --ext .js,.ts\n"
                    "  Rust   : cargo clippy\n"
                    "  Go     : golangci-lint run\n\n"
                    "Lance directement : `ruff check /chemin/`")
            return self._format_dev_result(r, "Lint")

        # ── Git ────────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["git status", "statut git", "git diff", "git log",
                                   "git commit", "commit les changements", "git push", "git pull", "git branch"]):
            return self._handle_git(task)

        # ── Debug ──────────────────────────────────────────────────────────────
        if any(kw in t for kw in ["debug", "débug", "traceback", "stack trace",
                                   "corrige l'erreur", "corrige le bug", "fixe le bug",
                                   "répare le code", "analyse l'erreur", "explique l'erreur"]):
            error = ctx.get("error", task)
            return self._debug(error, ctx)

        # ── Plan multi-étapes ─────────────────────────────────────────────────
        if any(kw in t for kw in ["plan de développement", "planifie le code",
                                   "étapes de développement", "liste les tâches de code"]):
            return self._make_plan(task, ctx)

        # ── État des tâches ────────────────────────────────────────────────────
        if any(kw in t for kw in ["tâches", "todo", "tasks"]):
            return self._result(True, _session.summary())

        # ── Définir le projet courant ──────────────────────────────────────────
        if any(kw in t for kw in ["projet courant", "set project", "projet ="]):
            path = self._extract_path(task)
            if path:
                _session.root = path
                return self._result(True, f"Projet courant défini : {path}")

        return self._result(True,
            "🛠️  Code Agent — Commandes disponibles\n\n"
            "EXPLORATION :\n"
            "  explore le projet /chemin/         → analyse complète\n"
            "  lis le fichier /chemin/fichier.py  → afficher le contenu\n"
            "  arborescence /chemin/              → arbre de fichiers\n\n"
            "ÉDITION :\n"
            "  crée le fichier /chemin/nouveau.py → créer un fichier\n"
            "  modifie le fichier /chemin/...     → modifier du code\n\n"
            "EXÉCUTION :\n"
            "  lance la commande `python3 script.py`\n"
            "  installe les dépendances /projet/  → pip/npm auto-détecté\n"
            "  compile le projet /projet/         → make/cargo/npm build\n\n"
            "TESTS & QUALITÉ :\n"
            "  lance les tests /projet/           → pytest/jest auto\n"
            "  lint /projet/                      → ruff/eslint\n\n"
            "GIT :\n"
            "  git status /projet/\n"
            "  git commit les changements 'message'\n"
            "  git push /projet/\n\n"
            "DEBUG :\n"
            "  debug TypeError: ... (colle ton erreur)\n"
            "  analyse l'erreur <traceback>")

    # ── Handlers spécialisés ──────────────────────────────────────────────────

    def _explore(self, path: str) -> dict:
        try:
            pm = project_explorer.explore(path)
            tree = project_explorer.tree_text(path, max_depth=3)
            output = f"=== EXPLORATION DE {pm.root} ===\n\n"
            output += pm.summary + "\n\n"
            output += "=== ARBORESCENCE ===\n" + tree
            if pm.entry_points:
                output += f"\n\n=== POINTS D'ENTRÉE ===\n" + "\n".join("  " + e for e in pm.entry_points)
            if pm.test_files:
                output += f"\n\n=== TESTS ({len(pm.test_files)}) ===\n" + "\n".join("  " + f for f in pm.test_files[:10])
            _session.root = path
            return self._result(True, output, {
                "files": pm.total_files,
                "lines": pm.total_lines,
                "languages": pm.languages,
                "frameworks": pm.frameworks,
            })
        except Exception as e:
            return self._result(False, f"Erreur exploration : {e}")

    def _read_file(self, path: str, original_task: str) -> dict:
        # Détecter si on veut un segment (lignes X à Y)
        m = re.search(r"lignes?\s+(\d+)(?:\s*[àa-]\s*(\d+))?", original_task.lower())
        if m:
            start, end = int(m.group(1)), int(m.group(2)) if m.group(2) else None
            r = code_editor.read_lines(path, start, end)
        else:
            r = code_editor.read(path)

        if not r["success"]:
            return self._result(False, r["error"])
        return self._result(True, r["content"], {"path": path, "lines": r.get("lines", 0)})

    def _write_file(self, path: str, content: str) -> dict:
        r = code_editor.write(path, content)
        if not r["success"]:
            return self._result(False, r["error"])
        msg = f"Fichier {'créé' if r['created'] else 'mis à jour'} : {path} ({r['lines']} lignes)"
        if r["diff"]:
            msg += f"\n\nDiff :\n{r['diff'][:3000]}"
        return self._result(True, msg, r)

    def _handle_git(self, task: str) -> dict:
        t = task.lower()
        path = self._extract_path(task) or _session.root or "."

        if "status" in t or "statut" in t:
            r = git_manager.status(path)
            if r["success"]:
                s = r
                lines = [f"Branche: {s['branch']} | Propre: {'oui' if s['clean'] else 'non'}"]
                for cat, files in [("Modifiés", s["modified"]), ("Ajoutés", s["added"]),
                                   ("Supprimés", s["deleted"]), ("Non suivis", s["untracked"])]:
                    if files:
                        lines.append(f"{cat}: {', '.join(files[:5])}")
                return self._result(True, "\n".join(lines), r)
            return self._result(False, r.get("error", "git status échoué"))

        if "diff" in t:
            staged = "staged" in t or "--cached" in t
            r = git_manager.diff(path, staged=staged)
            return self._result(r["success"], r.get("stdout", r.get("error", "")), r)

        if "log" in t:
            r = git_manager.log(path, n=10)
            out = r.get("stdout", "")
            return self._result(r["success"], out, r)

        if "commit" in t:
            # Extraire le message de commit
            m = re.search(r"""commit\s+(?:-m\s+)?['""]?(.+?)['""]?\s*$""", task, re.IGNORECASE)
            msg = m.group(1).strip() if m else "chore: mise à jour automatique via L'Œil de Dieu"
            r = git_manager.commit(path, msg, add_all=True)
            return self._result(r["success"], r.get("stdout", r.get("error", "")), r)

        if "push" in t:
            r = git_manager.push(path)
            return self._result(r["success"], r.get("stdout", r.get("stderr", r.get("error", ""))), r)

        if "pull" in t:
            r = git_manager.pull(path)
            return self._result(r["success"], r.get("stdout", r.get("error", "")), r)

        # Résumé complet
        summary = git_manager.summary(path)
        return self._result(True, summary)

    def _debug(self, error: str, ctx: dict) -> dict:
        """Analyse une erreur et propose un correctif structuré."""
        file_path = ctx.get("file") or self._extract_path(error)

        analysis = ["=== ANALYSE D'ERREUR ===", ""]
        analysis.append(f"Erreur : {error[:500]}")
        analysis.append("")

        # Identifier le type d'erreur
        error_type = self._classify_error(error)
        analysis.append(f"Type : {error_type}")
        analysis.append("")

        # Lire le fichier si mentionné
        if file_path:
            r = code_editor.read(file_path)
            if r["success"]:
                # Trouver les lignes pertinentes
                line_match = re.search(r"line (\d+)|ligne (\d+)|:(\d+):", error)
                if line_match:
                    ln = int(next(x for x in line_match.groups() if x))
                    excerpt = code_editor.read_lines(file_path, max(1, ln - 3), ln + 3)
                    analysis.append(f"=== Contexte ({file_path} l.{ln}) ===")
                    analysis.append(excerpt.get("content", ""))
                    analysis.append("")

        # Suggestions selon le type
        suggestions = self._suggest_fix(error_type, error)
        analysis.append("=== SUGGESTIONS ===")
        analysis += suggestions

        return self._result(True, "\n".join(analysis), {"error_type": error_type, "file": file_path})

    def _classify_error(self, error: str) -> str:
        e = error.lower()
        if "syntaxerror" in e or "syntax error" in e:
            return "SyntaxError"
        if "importerror" in e or "modulenotfounderror" in e or "cannot find module" in e:
            return "ImportError"
        if "typeerror" in e:
            return "TypeError"
        if "attributeerror" in e:
            return "AttributeError"
        if "keyerror" in e or "indexerror" in e:
            return "KeyError/IndexError"
        if "nameerror" in e:
            return "NameError"
        if "filenotfounderror" in e or "no such file" in e or "enoent" in e:
            return "FileNotFoundError"
        if "permissionerror" in e or "permission denied" in e:
            return "PermissionError"
        if "connectionerror" in e or "connection refused" in e or "econnrefused" in e:
            return "ConnectionError"
        if "validationerror" in e:
            return "ValidationError"
        if "traceback" in e:
            return "RuntimeError"
        return "UnknownError"

    def _suggest_fix(self, error_type: str, error: str) -> list[str]:
        tips = {
            "SyntaxError": [
                "→ Vérifier les parenthèses, guillemets et indentations",
                "→ Utiliser un linter : ruff check . ou eslint .",
            ],
            "ImportError": [
                "→ Vérifier que le module est installé : pip list | grep <module>",
                "→ Installer si manquant : pip install <module>",
                "→ Vérifier le PYTHONPATH ou sys.path",
            ],
            "TypeError": [
                "→ Vérifier les types des arguments passés à la fonction",
                "→ Ajouter des annotations de type et utiliser mypy",
            ],
            "AttributeError": [
                "→ Vérifier que l'objet n'est pas None avant d'accéder à l'attribut",
                "→ Utiliser getattr(obj, 'attr', default) pour les accès optionnels",
            ],
            "FileNotFoundError": [
                "→ Vérifier que le chemin existe : Path(path).exists()",
                "→ Utiliser des chemins absolus ou relatifs au bon répertoire",
            ],
            "ConnectionError": [
                "→ Vérifier que le service est démarré",
                "→ Vérifier l'host, le port et les paramètres réseau",
                "→ Tester avec curl ou netcat",
            ],
        }
        return tips.get(error_type, ["→ Analyser la stack trace ligne par ligne", "→ Ajouter des logs pour isoler le problème"])

    def _make_plan(self, task: str, ctx: dict) -> dict:
        """Crée un plan de tâches multi-étapes."""
        project = ctx.get("project", _session.root or ".")
        t = _session.add_task(task)

        steps = [
            "1. Explorer l'architecture du projet",
            "2. Identifier les fichiers à créer/modifier",
            "3. Implémenter les changements (multi-fichiers)",
            "4. Exécuter les tests pour valider",
            "5. Lancer le linter/formatter",
            "6. Committer les changements",
        ]
        t.steps = steps
        t.status = "pending"

        output = f"Plan créé (tâche #{t.id}) :\n"
        output += "\n".join(steps)
        output += f"\n\nProjet : {project}"
        output += "\n\nValide le plan, puis dis 'exécute le plan' pour lancer."

        return self._result(True, output, {"task_id": t.id, "steps": steps})

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_dev_result(self, r: dict, label: str) -> dict:
        if r.get("blocked"):
            return self._result(False, f"{label} bloqué : {r['error']}")
        if not r.get("success"):
            err = r.get("stderr") or r.get("error") or "Erreur inconnue"
            return self._result(False, f"{label} échoué :\n{err[:2000]}")

        out = r.get("stdout", "")
        parsed = r.get("parsed", {})

        summary = f"{label} : OK (exit {r.get('returncode', 0)})\n"
        if parsed.get("passed") is not None:
            summary += f"Tests : {parsed['passed']} passés"
            if parsed.get("failed"):
                summary += f", {parsed['failed']} échoués"
        if parsed.get("installed"):
            summary += f"Installés : {', '.join(parsed['installed'][:5])}"
        if parsed.get("compile_errors"):
            summary += f"Erreurs compilation : {len(parsed['compile_errors'])}\n"
            summary += "\n".join(parsed["compile_errors"][:3])

        if out and len(summary) < 200:
            summary += "\n" + out[:3000]

        return self._result(True, summary, r)

    def _extract_path(self, task: str) -> Optional[str]:
        # Chemin absolu
        m = re.search(r"(/[\w/\-_.]+)", task)
        if m and Path(m.group(1)).exists():
            return m.group(1)
        # Chemin relatif ./ ou ../
        m = re.search(r"(\.\.?/[\w/\-_.]*)", task)
        if m:
            return m.group(1)
        # Nom de fichier avec extension
        m = re.search(r"\b([\w\-_.]+\.(?:py|js|ts|jsx|tsx|rs|go|c|cpp|h|json|yaml|yml|toml|md|txt|sh|env))\b", task)
        if m:
            return m.group(1)
        return None

    def _extract_command(self, task: str) -> Optional[str]:
        # Commandes entre backticks
        m = re.search(r"`([^`]+)`", task)
        if m:
            return m.group(1)
        # npm/pip/cargo/etc. explicites
        m = re.search(
            r"\b(npm\s+\S+.*|pip\s+\S+.*|pytest\s*.*|cargo\s+\S+.*|make\s*\S*|go\s+\S+.*|yarn\s+\S+.*)\b",
            task, re.IGNORECASE
        )
        return m.group(1).strip() if m else None


code_agent = CodeAgent()
