"""
ProjectExplorer — cartographie intelligente d'un codebase.
Détecte langage, framework, architecture, dépendances, points d'entrée.
"""
from __future__ import annotations

import os
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from core.tools.logger import get_logger

logger = get_logger(__name__)

# Fichiers / dossiers à ignorer lors du scan
_IGNORE_DIRS = {
    "__pycache__", ".git", ".svn", "node_modules", ".venv", "venv",
    "env", ".env", "dist", "build", ".next", ".nuxt", "target",
    ".cache", ".idea", ".vscode", "coverage", ".pytest_cache",
    "__snapshots__", ".mypy_cache", ".ruff_cache",
}
_IGNORE_EXTS = {
    ".pyc", ".pyo", ".class", ".o", ".a", ".so", ".dll", ".exe",
    ".jpg", ".jpeg", ".png", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".mp3", ".mp4", ".avi", ".zip", ".tar", ".gz",
    ".lock",  # package-lock.json gardé à part
}
_MAX_FILE_SIZE = 200_000  # 200 Ko max pour lire un fichier
_MAX_FILES = 500


@dataclass
class FileInfo:
    path: str
    language: str
    size: int
    lines: int = 0
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)


@dataclass
class ProjectMap:
    root: str
    languages: dict[str, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    files: list[FileInfo] = field(default_factory=list)
    structure: dict = field(default_factory=dict)
    dependencies: dict = field(default_factory=dict)
    config_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    summary: str = ""


# ── Détection de langage ──────────────────────────────────────────────────────

_EXT_LANG = {
    ".py": "Python", ".pyw": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".jsx": "JavaScript",
    ".rs": "Rust",
    ".go": "Go",
    ".c": "C", ".h": "C",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".java": "Java", ".kt": "Kotlin",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "CSS", ".sass": "CSS",
    ".json": "JSON", ".jsonc": "JSON",
    ".yaml": "YAML", ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown", ".rst": "Markdown",
    ".sql": "SQL",
    ".dockerfile": "Docker", ".Dockerfile": "Docker",
    ".asm": "Assembly", ".s": "Assembly", ".nasm": "Assembly",
}

_FRAMEWORK_MARKERS = {
    "FastAPI": ["from fastapi", "FastAPI()", "APIRouter"],
    "Flask": ["from flask", "Flask(__name__)", "app.route"],
    "Django": ["django.setup()", "from django", "INSTALLED_APPS"],
    "React": ["from 'react'", "from \"react\"", "React.createElement", "useState", "useEffect"],
    "Vue": ["createApp", "defineComponent", "from 'vue'"],
    "Next.js": ["next/router", "getServerSideProps", "getStaticProps"],
    "Express": ["require('express')", "express()", "app.get(", "app.post("],
    "SQLAlchemy": ["from sqlalchemy", "declarative_base", "Column"],
    "Pydantic": ["from pydantic", "BaseModel", "BaseSettings"],
    "Pytest": ["import pytest", "def test_", "@pytest.fixture"],
    "Jest": ["describe(", "test(", "expect(", "jest."],
    "Docker": ["FROM ", "RUN ", "COPY ", "EXPOSE "],
    "Makefile": ["Makefile"],
    "Vite": ["from 'vite'", "defineConfig", "vite.config"],
    "Anthropic/Claude": ["from anthropic", "import anthropic", "claude-"],
}

_ENTRY_POINTS = {
    "main.py", "app.py", "server.py", "index.py", "run.py", "manage.py",
    "index.js", "index.ts", "main.js", "main.ts", "app.js", "app.ts",
    "index.jsx", "index.tsx", "main.jsx", "main.tsx",
    "main.rs", "main.go", "Main.java", "Program.cs",
}

_CONFIG_FILES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg",
    "requirements.txt", "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "Makefile", "CMakeLists.txt", "Dockerfile", "docker-compose.yml",
    ".env.example", ".env.template", "vite.config.js", "vite.config.ts",
    "tsconfig.json", "webpack.config.js", "jest.config.js", "pytest.ini",
    "pyproject.toml", ".flake8", ".eslintrc.js", ".prettierrc",
    "README.md", "README.rst",
}

_TEST_PATTERNS = [
    re.compile(r"test_\w+\.py$"),
    re.compile(r"\w+\.test\.(js|ts|jsx|tsx)$"),
    re.compile(r"\w+\.spec\.(js|ts|jsx|tsx)$"),
    re.compile(r"tests?/"),
    re.compile(r"__tests__/"),
]


class ProjectExplorer:

    def explore(self, root_path: str, max_depth: int = 6) -> ProjectMap:
        root = Path(root_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Chemin introuvable : {root_path}")

        logger.info(f"[EXPLORE] Début exploration : {root}")
        pm = ProjectMap(root=str(root))
        files_scanned = 0

        for dirpath, dirnames, filenames in os.walk(root):
            # Calculer la profondeur
            depth = len(Path(dirpath).relative_to(root).parts)
            if depth > max_depth:
                dirnames.clear()
                continue

            # Filtrer les dossiers ignorés
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS]

            for fname in filenames:
                if files_scanned >= _MAX_FILES:
                    break
                fpath = Path(dirpath) / fname
                ext = fpath.suffix.lower()

                if ext in _IGNORE_EXTS:
                    continue

                rel = str(fpath.relative_to(root))
                lang = _EXT_LANG.get(ext, "other")
                size = fpath.stat().st_size if fpath.exists() else 0

                fi = FileInfo(path=rel, language=lang, size=size)

                # Lire le contenu pour analyse
                if size < _MAX_FILE_SIZE:
                    try:
                        content = fpath.read_text(encoding="utf-8", errors="ignore")
                        fi.lines = content.count("\n") + 1
                        pm.total_lines += fi.lines

                        # Détecter frameworks
                        for fw, markers in _FRAMEWORK_MARKERS.items():
                            if fw not in pm.frameworks:
                                if any(m in content for m in markers):
                                    pm.frameworks.append(fw)

                        # Analyser selon le langage
                        if lang == "Python":
                            fi.imports = self._py_imports(content)
                            fi.classes = re.findall(r"^class\s+(\w+)", content, re.MULTILINE)
                            fi.functions = re.findall(r"^def\s+(\w+)", content, re.MULTILINE)
                            fi.exports = fi.classes + fi.functions

                        elif lang in ("JavaScript", "TypeScript"):
                            fi.imports = self._js_imports(content)
                            fi.exports = re.findall(r"export\s+(?:default\s+)?(?:function|class|const|let|var)\s+(\w+)", content)
                            fi.functions = re.findall(r"(?:function|const|let)\s+(\w+)\s*[=(]", content)

                        elif lang == "Go":
                            fi.imports = re.findall(r'import\s+"([^"]+)"', content)
                            fi.functions = re.findall(r"^func\s+(\w+)", content, re.MULTILINE)

                        elif lang in ("C", "C++"):
                            fi.functions = re.findall(r"^\w[\w\s\*]+\s+(\w+)\s*\(", content, re.MULTILINE)

                        # Config files
                        if fname in _CONFIG_FILES:
                            pm.config_files.append(rel)
                            self._parse_dependencies(pm, fname, content)

                    except Exception:
                        pass

                # Entry points
                if fname in _ENTRY_POINTS:
                    pm.entry_points.append(rel)

                # Test files
                if any(p.search(rel) for p in _TEST_PATTERNS):
                    pm.test_files.append(rel)

                # Comptage langages
                pm.languages[lang] = pm.languages.get(lang, 0) + 1
                pm.files.append(fi)
                files_scanned += 1

        pm.total_files = files_scanned
        pm.structure = self._build_tree(root, max_depth=3)
        pm.summary = self._generate_summary(pm)
        logger.info(f"[EXPLORE] Terminé : {files_scanned} fichiers, {pm.total_lines} lignes")
        return pm

    def _py_imports(self, content: str) -> list[str]:
        imports = []
        for m in re.finditer(r"^(?:from|import)\s+([\w.]+)", content, re.MULTILINE):
            imports.append(m.group(1))
        return list(set(imports))

    def _js_imports(self, content: str) -> list[str]:
        imports = []
        for m in re.finditer(r"""(?:import|require)\s*(?:\{[^}]*\}\s*from\s*)?['"]([^'"]+)['"]""", content):
            imports.append(m.group(1))
        return list(set(imports))

    def _parse_dependencies(self, pm: ProjectMap, fname: str, content: str):
        try:
            if fname == "package.json":
                data = json.loads(content)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                pm.dependencies["npm"] = list(deps.keys())[:30]
            elif fname in ("requirements.txt",):
                pkgs = [l.split("==")[0].split(">=")[0].strip()
                        for l in content.splitlines() if l.strip() and not l.startswith("#")]
                pm.dependencies["pip"] = pkgs[:30]
            elif fname == "Cargo.toml":
                deps = re.findall(r"^\s*(\w+)\s*=", content, re.MULTILINE)
                pm.dependencies["cargo"] = deps[:30]
        except Exception:
            pass

    def _build_tree(self, root: Path, max_depth: int = 3) -> dict:
        def _recurse(path: Path, depth: int) -> dict:
            if depth > max_depth:
                return {}
            result = {}
            try:
                for item in sorted(path.iterdir()):
                    if item.name in _IGNORE_DIRS or item.name.startswith("."):
                        continue
                    if item.is_dir():
                        result[item.name + "/"] = _recurse(item, depth + 1)
                    else:
                        result[item.name] = item.stat().st_size
            except PermissionError:
                pass
            return result
        return _recurse(root, 0)

    def _generate_summary(self, pm: ProjectMap) -> str:
        lines = [f"Projet : {pm.root}"]
        lines.append(f"Fichiers : {pm.total_files} | Lignes : {pm.total_lines:,}")

        if pm.languages:
            top_langs = sorted(pm.languages.items(), key=lambda x: -x[1])[:5]
            lines.append("Langages : " + ", ".join(f"{l}({n})" for l, n in top_langs))

        if pm.frameworks:
            lines.append("Frameworks : " + ", ".join(pm.frameworks))

        if pm.entry_points:
            lines.append("Points d'entrée : " + ", ".join(pm.entry_points[:5]))

        if pm.dependencies:
            for mgr, pkgs in pm.dependencies.items():
                lines.append(f"Dépendances [{mgr}] : {', '.join(pkgs[:10])}{'...' if len(pkgs) > 10 else ''}")

        if pm.config_files:
            lines.append("Config : " + ", ".join(pm.config_files[:8]))

        if pm.test_files:
            lines.append(f"Tests : {len(pm.test_files)} fichiers")

        return "\n".join(lines)

    def quick_read(self, file_path: str) -> dict:
        """Lit un fichier et retourne son contenu + métadonnées."""
        p = Path(file_path)
        if not p.exists():
            return {"error": f"Fichier introuvable : {file_path}"}
        if p.stat().st_size > _MAX_FILE_SIZE:
            return {"error": f"Fichier trop volumineux ({p.stat().st_size} octets)"}
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
            return {
                "path": str(p),
                "language": _EXT_LANG.get(p.suffix.lower(), "other"),
                "lines": content.count("\n") + 1,
                "content": content,
            }
        except Exception as e:
            return {"error": str(e)}

    def tree_text(self, root_path: str, max_depth: int = 4) -> str:
        """Retourne une représentation texte de l'arborescence."""
        root = Path(root_path)
        lines = [str(root)]

        def _walk(path: Path, prefix: str, depth: int):
            if depth > max_depth:
                return
            try:
                items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name))
            except PermissionError:
                return
            items = [i for i in items if i.name not in _IGNORE_DIRS and not i.name.startswith(".")]
            for i, item in enumerate(items):
                connector = "└── " if i == len(items) - 1 else "├── "
                lines.append(prefix + connector + item.name + ("/" if item.is_dir() else ""))
                if item.is_dir():
                    extension = "    " if i == len(items) - 1 else "│   "
                    _walk(item, prefix + extension, depth + 1)

        _walk(root, "", 0)
        return "\n".join(lines)


project_explorer = ProjectExplorer()
