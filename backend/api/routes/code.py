"""
Routes /api/code — assistant de programmation autonome.
Explore, lit, écrit, teste, débogue, git.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from core.tools.project_explorer import project_explorer
from core.tools.code_editor import code_editor
from core.tools.dev_runner import dev_runner
from core.tools.git_manager import git_manager
from core.agents.code_agent import code_agent, _session

router = APIRouter()


# ── Exploration ───────────────────────────────────────────────────────────────

class PathRequest(BaseModel):
    path: str
    max_depth: int = 6


@router.post("/explore")
def explore_project(req: PathRequest):
    try:
        pm = project_explorer.explore(req.path, max_depth=req.max_depth)
        return {
            "root": pm.root,
            "summary": pm.summary,
            "languages": pm.languages,
            "frameworks": pm.frameworks,
            "entry_points": pm.entry_points,
            "config_files": pm.config_files,
            "test_files": pm.test_files,
            "dependencies": pm.dependencies,
            "total_files": pm.total_files,
            "total_lines": pm.total_lines,
        }
    except FileNotFoundError as e:
        return {"error": str(e)}


@router.post("/tree")
def get_tree(req: PathRequest):
    try:
        tree = project_explorer.tree_text(req.path, max_depth=req.max_depth)
        return {"tree": tree}
    except Exception as e:
        return {"error": str(e)}


@router.post("/read")
def read_file(req: PathRequest):
    return code_editor.read(req.path)


class ReadLinesRequest(BaseModel):
    path: str
    start: int = 1
    end: Optional[int] = None


@router.post("/read/lines")
def read_file_lines(req: ReadLinesRequest):
    return code_editor.read_lines(req.path, req.start, req.end)


# ── Édition ───────────────────────────────────────────────────────────────────

class WriteRequest(BaseModel):
    path: str
    content: str
    backup: bool = True


@router.post("/write")
def write_file(req: WriteRequest):
    return code_editor.write(req.path, req.content, backup=req.backup)


class PatchRequest(BaseModel):
    path: str
    old: str
    new: str
    backup: bool = True


@router.post("/patch")
def patch_file(req: PatchRequest):
    return code_editor.patch(req.path, req.old, req.new, backup=req.backup)


class MultiWriteRequest(BaseModel):
    changes: list[dict]


@router.post("/multi-write")
def multi_write(req: MultiWriteRequest):
    return code_editor.multi_write(req.changes)


class DiffRequest(BaseModel):
    path: str
    new_content: str


@router.post("/diff")
def preview_diff(req: DiffRequest):
    return code_editor.preview_diff(req.path, req.new_content)


class ListDirRequest(BaseModel):
    path: str
    recursive: bool = False


@router.post("/ls")
def list_dir(req: ListDirRequest):
    return code_editor.list_dir(req.path, req.recursive)


# ── Dev commands ──────────────────────────────────────────────────────────────

class RunRequest(BaseModel):
    command: str
    cwd: Optional[str] = None
    timeout: int = 120
    env: Optional[dict] = None


@router.post("/run")
def run_command(req: RunRequest):
    return dev_runner.run(req.command, cwd=req.cwd, timeout=req.timeout, env_extra=req.env)


class ProjectPathRequest(BaseModel):
    path: str
    command: Optional[str] = None


@router.post("/install")
def install_deps(req: ProjectPathRequest):
    return dev_runner.install_deps(req.path)


@router.post("/test")
def run_tests(req: ProjectPathRequest):
    return dev_runner.run_tests(req.path, test_cmd=req.command)


@router.post("/lint")
def run_lint(req: ProjectPathRequest):
    return dev_runner.lint(req.path)


# ── Git ───────────────────────────────────────────────────────────────────────

class GitRequest(BaseModel):
    path: str


@router.post("/git/status")
def git_status(req: GitRequest):
    return git_manager.status(req.path)


@router.post("/git/diff")
def git_diff(req: GitRequest):
    return git_manager.diff(req.path)


@router.post("/git/log")
def git_log(req: GitRequest):
    return git_manager.log(req.path)


class GitCommitRequest(BaseModel):
    path: str
    message: str
    add_all: bool = True


@router.post("/git/commit")
def git_commit(req: GitCommitRequest):
    return git_manager.commit(req.path, req.message, add_all=req.add_all)


class GitPushRequest(BaseModel):
    path: str
    remote: str = "origin"
    branch: str = ""


@router.post("/git/push")
def git_push(req: GitPushRequest):
    return git_manager.push(req.path, req.remote, req.branch)


@router.post("/git/pull")
def git_pull(req: GitRequest):
    return git_manager.pull(req.path)


@router.post("/git/summary")
def git_summary(req: GitRequest):
    return {"summary": git_manager.summary(req.path)}


# ── Agent code dispatch ───────────────────────────────────────────────────────

class AgentCodeRequest(BaseModel):
    task: str
    context: Optional[dict] = None


@router.post("/agent")
async def run_code_agent(req: AgentCodeRequest):
    return await code_agent.run(req.task, req.context)


# ── Session / tâches ─────────────────────────────────────────────────────────

@router.get("/tasks")
def list_tasks():
    return {"summary": _session.summary(), "tasks": [
        {"id": t.id, "title": t.title, "status": t.status, "steps": t.steps}
        for t in _session.tasks
    ]}


class SetProjectRequest(BaseModel):
    path: str


@router.post("/project")
def set_project(req: SetProjectRequest):
    _session.root = req.path
    return {"project": req.path, "message": f"Projet courant : {req.path}"}


@router.get("/project")
def get_project():
    return {"project": _session.root}
