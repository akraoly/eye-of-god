"""
Routes /api/offensive — 4 niveaux Red Team + pipeline fuzzing→exploit.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.tools.offensive_engine import offensive, LEVELS

router = APIRouter()


# ── Catalogue ─────────────────────────────────────────────────────────────────

@router.get("/levels")
def get_all_levels():
    return {"levels": offensive.get_all_levels()}


@router.get("/level/{n}")
def get_level(n: int):
    lvl = offensive.get_level(n)
    if not lvl:
        return {"error": f"Niveau {n} inexistant (1-4)"}
    return {
        "number": lvl.number,
        "name": lvl.name,
        "icon": lvl.icon,
        "color": lvl.color,
        "impact": lvl.impact,
        "description": lvl.description,
        "tools": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "commands": t.commands,
                "needs_root": t.needs_root,
            }
            for t in lvl.tools
        ],
    }


@router.get("/summary")
def get_summary():
    return {
        "total_tools": sum(len(lvl.tools) for lvl in LEVELS.values()),
        "levels": [
            {
                "number": lvl.number,
                "name": lvl.name,
                "icon": lvl.icon,
                "color": lvl.color,
                "impact": lvl.impact,
                "tools_count": len(lvl.tools),
            }
            for lvl in LEVELS.values()
        ],
        "pipeline": ["fuzz", "analyse_crash", "reverse", "exploit_template"],
    }


# ── Exécution d'outils ────────────────────────────────────────────────────────

class RunToolRequest(BaseModel):
    level: int
    tool: str
    params: dict = {}


@router.post("/run/tool")
def run_level_tool(req: RunToolRequest):
    return offensive.run_level_tool(req.level, req.tool, req.params)


# ── Pipeline fuzzing → exploit ────────────────────────────────────────────────

class FuzzRequest(BaseModel):
    binary: str
    corpus: str = "/tmp/corpus"
    output: str = "/tmp/fuzz_out"
    timeout: int = 30


@router.post("/pipeline/fuzz")
def run_fuzzing(req: FuzzRequest):
    return offensive.run_pipeline(
        "fuzz",
        binary=req.binary,
        corpus=req.corpus,
        output=req.output,
        timeout=req.timeout,
    )


class CrashRequest(BaseModel):
    binary: str
    crash: str


@router.post("/pipeline/analyse-crash")
def analyse_crash(req: CrashRequest):
    return offensive.run_pipeline("analyse_crash", binary=req.binary, crash=req.crash)


class ReverseRequest(BaseModel):
    binary: str


@router.post("/pipeline/reverse")
def reverse_analysis(req: ReverseRequest):
    return offensive.run_pipeline("reverse", binary=req.binary)


class ExploitTemplateRequest(BaseModel):
    binary: str
    offset: int = 0
    lhost: str = "127.0.0.1"
    lport: int = 4444


@router.post("/pipeline/exploit-template")
def generate_exploit(req: ExploitTemplateRequest):
    return offensive.run_pipeline(
        "exploit_template",
        binary=req.binary,
        offset=req.offset,
        lhost=req.lhost,
        lport=req.lport,
    )


# ── Dispatch IA ──────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    task: str
    context: Optional[dict] = None


@router.post("/dispatch")
async def dispatch_offensive(req: DispatchRequest):
    """Détecte automatiquement le niveau et dispatch la tâche."""
    level = offensive.detect_level(req.task)
    lvl_obj = offensive.get_level(level)
    return {
        "detected_level": level,
        "level_name": lvl_obj.name,
        "level_icon": lvl_obj.icon,
        "task": req.task,
        "available_tools": [t.name for t in lvl_obj.tools],
        "hint": f"Utilise /api/offensive/run/tool avec level={level} et l'outil approprié.",
    }
