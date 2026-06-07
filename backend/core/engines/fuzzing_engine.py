"""
FuzzingEngine — Module 13
Integrates AFL++, boofuzz, and ffuf for comprehensive fuzzing.
All tasks run in background via asyncio.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from database.db import SessionLocal
from database.models import FuzzingJob


WORK_DIR = Path("./data/fuzzing")

# ── Job registry (in-memory) ──────────────────────────────────────────────────
_active_processes: dict[str, asyncio.subprocess.Process] = {}
_job_tasks: dict[str, asyncio.Task] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _run_cmd(args: list[str], cwd: str = None, timeout: int = None) -> tuple[int, str, str]:
    """Run subprocess and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            return -1, "", "Timeout"
        return proc.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")
    except Exception as e:
        return -1, "", str(e)


def _db_session():
    return SessionLocal()


def _update_job(job_id: str, **kwargs):
    db = _db_session()
    try:
        job = db.query(FuzzingJob).filter_by(job_id=job_id).first()
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)
            job.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def _parse_afl_stats(output_dir: str) -> dict:
    """Parse AFL++ fuzzer_stats file."""
    result = {"crashes_found": 0, "hangs_found": 0, "execs_per_sec": 0.0, "total_paths": 0}
    for candidate in [
        Path(output_dir) / "default" / "fuzzer_stats",
        Path(output_dir) / "fuzzer_stats",
    ]:
        if candidate.exists():
            for line in candidate.read_text(errors="replace").splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    val = val.strip()
                    mapping = {
                        "unique_crashes": "crashes_found",
                        "unique_hangs": "hangs_found",
                        "paths_total": "total_paths",
                    }
                    if key in mapping:
                        try:
                            result[mapping[key]] = int(val)
                        except ValueError:
                            pass
                    elif key == "execs_per_sec":
                        try:
                            result["execs_per_sec"] = float(val)
                        except ValueError:
                            pass
            break
    return result


# ── FuzzingEngine ─────────────────────────────────────────────────────────────

class FuzzingEngine:
    """
    Integrates AFL++, boofuzz, and ffuf for comprehensive fuzzing.
    All tasks run in background via asyncio.
    """

    WORK_DIR = WORK_DIR

    def __init__(self):
        WORK_DIR.mkdir(parents=True, exist_ok=True)

    # ── AFL++ ─────────────────────────────────────────────────────────────────

    async def start_afl_fuzzing(
        self,
        binary_path: str,
        corpus_dir: Optional[str] = None,
        output_dir: Optional[str] = None,
        timeout_hours: int = 1,
    ) -> dict:
        """
        AFL++ binary fuzzing.
        1. Generate initial corpus if not provided
        2. afl-fuzz -i corpus -o output -- binary @@
        3. Monitor output/crashes/ every 30s in background
        Returns: job_id, starts background task
        """
        if not shutil.which("afl-fuzz"):
            return {"available": False, "message": "afl-fuzz not found — install AFL++"}

        job_id = str(uuid.uuid4())
        work = WORK_DIR / job_id
        work.mkdir(parents=True, exist_ok=True)

        # Corpus
        if corpus_dir and Path(corpus_dir).exists():
            corpus = corpus_dir
        else:
            corpus = str(work / "corpus")
            Path(corpus).mkdir(exist_ok=True)
            (Path(corpus) / "seed1").write_bytes(b"\x00" * 16)
            (Path(corpus) / "seed2").write_bytes(b"AAAA" * 8)
            (Path(corpus) / "seed3").write_bytes(b"\xff\xfe\xfd\xfc" * 4)

        if not output_dir:
            output_dir = str(work / "output")
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        crash_dir = str(Path(output_dir) / "default" / "crashes")

        db = _db_session()
        try:
            job = FuzzingJob(
                job_id=job_id,
                fuzzer_type="afl",
                target=binary_path,
                target_type="binary",
                status="running",
                crashes_found=0,
                hangs_found=0,
                execs_per_sec=0.0,
                total_paths=0,
                output_dir=output_dir,
                crash_dir=crash_dir,
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        task = asyncio.create_task(
            self._run_afl_background(job_id, binary_path, corpus, output_dir, timeout_hours)
        )
        _job_tasks[job_id] = task

        return {
            "job_id": job_id,
            "fuzzer": "afl++",
            "target": binary_path,
            "corpus_dir": corpus,
            "output_dir": output_dir,
            "crash_dir": crash_dir,
            "status": "running",
            "message": "AFL++ fuzzing started in background",
        }

    async def _run_afl_background(
        self,
        job_id: str,
        binary_path: str,
        corpus: str,
        output_dir: str,
        timeout_hours: int,
    ):
        env = os.environ.copy()
        env["AFL_SKIP_CPUFREQ"] = "1"
        env["AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES"] = "1"
        timeout_secs = timeout_hours * 3600

        try:
            proc = await asyncio.create_subprocess_exec(
                "afl-fuzz",
                "-i", corpus,
                "-o", output_dir,
                "--",
                binary_path, "@@",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
            _active_processes[job_id] = proc

            elapsed = 0
            while elapsed < timeout_secs:
                await asyncio.sleep(30)
                elapsed += 30
                if proc.returncode is not None:
                    break
                stats = _parse_afl_stats(output_dir)
                _update_job(job_id, **stats)

            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=10)
                except asyncio.TimeoutError:
                    proc.kill()

            final_stats = _parse_afl_stats(output_dir)
            _update_job(job_id, status="completed", stopped_at=datetime.utcnow(), **final_stats)
        except asyncio.CancelledError:
            _update_job(job_id, status="stopped", stopped_at=datetime.utcnow())
        except Exception:
            _update_job(job_id, status="stopped", stopped_at=datetime.utcnow())
        finally:
            _active_processes.pop(job_id, None)
            _job_tasks.pop(job_id, None)

    # ── boofuzz ───────────────────────────────────────────────────────────────

    async def fuzz_network_protocol(
        self,
        target_ip: str,
        target_port: int,
        protocol_name: str = "custom",
        request_template: Optional[bytes] = None,
    ) -> dict:
        """
        boofuzz network fuzzing.
        Generates a Python boofuzz script for the protocol and executes it.
        """
        rc, _, _ = await _run_cmd(["python3", "-c", "import boofuzz"], timeout=10)
        if rc != 0:
            return {"available": False, "message": "boofuzz not installed — pip install boofuzz"}

        job_id = str(uuid.uuid4())
        work = WORK_DIR / job_id
        work.mkdir(parents=True, exist_ok=True)
        output_dir = str(work)
        crash_dir = str(work / "crashes")
        Path(crash_dir).mkdir(exist_ok=True)

        if request_template:
            template_repr = repr(request_template)
        else:
            template_repr = repr(f"FUZZ {protocol_name.upper()} /\r\n\r\n".encode())

        script = f"""#!/usr/bin/env python3
import os, sys, json
from boofuzz import Session, Target, TCPSocketConnection, s_initialize, s_string, s_static, s_block, s_get

os.makedirs({repr(crash_dir)}, exist_ok=True)

session = Session(
    target=Target(connection=TCPSocketConnection({repr(target_ip)}, {target_port})),
    crash_threshold_request=1,
    crash_threshold_element=1,
    reuse_target_connection=False,
    fuzz_loggers=None,
    keep_web_open=False,
)

s_initialize("fuzz_request")
with s_block("header"):
    s_static({template_repr})
s_string("payload", default_value=b"A" * 100, fuzzable=True)

session.connect(s_get("fuzz_request"))

try:
    session.fuzz(max_depth=2)
except KeyboardInterrupt:
    pass
except Exception as e:
    with open(os.path.join({repr(crash_dir)}, "error.txt"), "w") as f:
        f.write(str(e))
"""
        script_path = work / "fuzz_script.py"
        script_path.write_text(script)

        db = _db_session()
        try:
            job = FuzzingJob(
                job_id=job_id,
                fuzzer_type="boofuzz",
                target=f"{target_ip}:{target_port}",
                target_type="network",
                status="running",
                crashes_found=0,
                hangs_found=0,
                execs_per_sec=0.0,
                total_paths=0,
                output_dir=output_dir,
                crash_dir=crash_dir,
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        task = asyncio.create_task(
            self._run_boofuzz_background(job_id, str(script_path), crash_dir)
        )
        _job_tasks[job_id] = task

        return {
            "job_id": job_id,
            "fuzzer": "boofuzz",
            "target": f"{target_ip}:{target_port}",
            "protocol": protocol_name,
            "output_dir": output_dir,
            "crash_dir": crash_dir,
            "script": str(script_path),
            "status": "running",
            "message": "boofuzz network fuzzing started in background",
        }

    async def _run_boofuzz_background(self, job_id: str, script_path: str, crash_dir: str):
        try:
            proc = await asyncio.create_subprocess_exec(
                "python3", script_path,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            _active_processes[job_id] = proc
            await asyncio.wait_for(proc.wait(), timeout=3600)
        except asyncio.TimeoutError:
            p = _active_processes.get(job_id)
            if p:
                p.kill()
        except asyncio.CancelledError:
            pass
        finally:
            crashes = len(list(Path(crash_dir).glob("*"))) if Path(crash_dir).exists() else 0
            _update_job(
                job_id,
                status="completed",
                crashes_found=crashes,
                stopped_at=datetime.utcnow(),
            )
            _active_processes.pop(job_id, None)
            _job_tasks.pop(job_id, None)

    # ── ffuf ──────────────────────────────────────────────────────────────────

    async def fuzz_web_endpoints(
        self,
        base_url: str,
        wordlist: Optional[str] = None,
        method: str = "GET",
        data: Optional[str] = None,
    ) -> dict:
        """
        ffuf intelligent web fuzzing.
        ffuf -u {url}/FUZZ -w wordlist -mc 200,204,301,302,307,401,403
        Parse and categorize results.
        """
        if not shutil.which("ffuf"):
            return {"available": False, "message": "ffuf not found — apt install ffuf"}

        # Resolve wordlist
        if wordlist and Path(wordlist).exists():
            wl = wordlist
        else:
            candidates = [
                "/usr/share/wordlists/dirb/common.txt",
                "/usr/share/wordlists/dirbuster/directory-list-2.3-small.txt",
                "/usr/share/seclists/Discovery/Web-Content/common.txt",
                "/usr/share/wordlists/wfuzz/general/common.txt",
            ]
            wl = next((c for c in candidates if Path(c).exists()), None)
            if not wl:
                wl_tmp = WORK_DIR / f"wordlist_{uuid.uuid4().hex[:8]}.txt"
                wl_tmp.write_text("\n".join([
                    "admin", "login", "api", "v1", "v2", "index", "home",
                    "dashboard", "upload", "config", "backup", "test", "dev",
                    "staging", ".git", ".env", "robots.txt", "sitemap.xml",
                    "phpinfo.php", "wp-admin", "wp-login.php",
                ]))
                wl = str(wl_tmp)

        job_id = str(uuid.uuid4())
        work = WORK_DIR / job_id
        work.mkdir(parents=True, exist_ok=True)
        output_dir = str(work)
        results_file = str(work / "results.json")

        fuzz_url = base_url.rstrip("/") + "/FUZZ"
        cmd = [
            "ffuf",
            "-u", fuzz_url,
            "-w", wl,
            "-mc", "200,204,301,302,307,401,403",
            "-o", results_file,
            "-of", "json",
            "-t", "50",
            "-timeout", "10",
            "-s",
        ]
        if method.upper() != "GET":
            cmd += ["-X", method.upper()]
        if data:
            cmd += ["-d", data]

        db = _db_session()
        try:
            job = FuzzingJob(
                job_id=job_id,
                fuzzer_type="ffuf",
                target=fuzz_url,
                target_type="web",
                status="running",
                crashes_found=0,
                hangs_found=0,
                execs_per_sec=0.0,
                total_paths=0,
                output_dir=output_dir,
                crash_dir="",
                started_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(job)
            db.commit()
        finally:
            db.close()

        task = asyncio.create_task(
            self._run_ffuf_background(job_id, cmd, results_file, output_dir)
        )
        _job_tasks[job_id] = task

        return {
            "job_id": job_id,
            "fuzzer": "ffuf",
            "target": fuzz_url,
            "wordlist": wl,
            "method": method,
            "output_dir": output_dir,
            "results_file": results_file,
            "status": "running",
            "message": "ffuf web fuzzing started in background",
        }

    async def _run_ffuf_background(
        self, job_id: str, cmd: list, results_file: str, output_dir: str
    ):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            _active_processes[job_id] = proc
            await asyncio.wait_for(proc.wait(), timeout=3600)
        except asyncio.TimeoutError:
            p = _active_processes.get(job_id)
            if p:
                p.kill()
        except asyncio.CancelledError:
            pass
        finally:
            paths_found = 0
            if Path(results_file).exists():
                try:
                    ffuf_data = json.loads(Path(results_file).read_text())
                    paths_found = len(ffuf_data.get("results", []))
                except Exception:
                    pass
            _update_job(
                job_id,
                status="completed",
                total_paths=paths_found,
                stopped_at=datetime.utcnow(),
            )
            _active_processes.pop(job_id, None)
            _job_tasks.pop(job_id, None)

    # ── Crash analysis ────────────────────────────────────────────────────────

    async def get_crash_analysis(self, crash_dir: str) -> list:
        """
        Analyze AFL++ crash files:
        1. Deduplicate by content hash
        2. Classify by type (segfault, heap, stack)
        3. Check exploitability with GDB if available
        Returns sorted list by severity
        """
        crash_path = Path(crash_dir)
        if not crash_path.exists():
            return []

        crashes = []
        seen_hashes: set = set()
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "unknown": 4}

        crash_files = [
            f for f in crash_path.iterdir()
            if f.is_file() and not f.name.startswith("README")
        ]

        for crash_file in crash_files:
            try:
                data = crash_file.read_bytes()
                content_hash = hashlib.md5(data).hexdigest()
                if content_hash in seen_hashes:
                    continue
                seen_hashes.add(content_hash)

                crash_info: dict = {
                    "file": str(crash_file),
                    "size": len(data),
                    "hash": content_hash,
                    "type": "unknown",
                    "severity": "medium",
                    "exploitability": "unknown",
                    "data_preview": data[:64].hex(),
                }

                if shutil.which("gdb"):
                    script_tmp = crash_path / f"_gdb_{crash_file.name}.gdb"
                    script_tmp.write_text(
                        f"run < {crash_file}\nbt\ninfo registers\nquit\n"
                    )
                    rc, stdout, stderr = await _run_cmd(
                        ["gdb", "-batch", "-x", str(script_tmp)],
                        timeout=15,
                    )
                    script_tmp.unlink(missing_ok=True)
                    combined = (stdout + stderr).lower()

                    if "sigsegv" in combined:
                        crash_info["type"] = "segfault"
                        crash_info["severity"] = "high"
                    elif "sigabrt" in combined:
                        crash_info["type"] = "abort"
                        crash_info["severity"] = "medium"
                    elif "heap" in combined:
                        crash_info["type"] = "heap_corruption"
                        crash_info["severity"] = "critical"
                    elif "stack" in combined and "overflow" in combined:
                        crash_info["type"] = "stack_overflow"
                        crash_info["severity"] = "critical"

                    crash_info["backtrace"] = (stdout + stderr)[:2000]

                    if "exploitable" in combined and "not exploitable" not in combined:
                        crash_info["exploitability"] = "exploitable"
                        crash_info["severity"] = "critical"
                    elif "probably exploitable" in combined:
                        crash_info["exploitability"] = "probably_exploitable"
                        crash_info["severity"] = "high"
                    elif "not exploitable" in combined:
                        crash_info["exploitability"] = "not_exploitable"
                        crash_info["severity"] = "low"

                crashes.append(crash_info)
            except Exception as e:
                crashes.append({"file": str(crash_file), "error": str(e), "severity": "unknown"})

        crashes.sort(key=lambda x: severity_order.get(x.get("severity", "unknown"), 4))
        return crashes

    # ── Job management ────────────────────────────────────────────────────────

    async def monitor_job(self, job_id: str) -> dict:
        """Get fuzzing job status: crashes, hangs, execs/sec, paths"""
        db = _db_session()
        try:
            job = db.query(FuzzingJob).filter_by(job_id=job_id).first()
            if not job:
                return {"error": "Job not found"}

            result = {
                "job_id": job.job_id,
                "fuzzer_type": job.fuzzer_type,
                "target": job.target,
                "target_type": job.target_type,
                "status": job.status,
                "crashes_found": job.crashes_found,
                "hangs_found": job.hangs_found,
                "execs_per_sec": job.execs_per_sec,
                "total_paths": job.total_paths,
                "output_dir": job.output_dir,
                "crash_dir": job.crash_dir,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "updated_at": job.updated_at.isoformat() if job.updated_at else None,
                "stopped_at": job.stopped_at.isoformat() if job.stopped_at else None,
                "is_active": job_id in _active_processes,
            }

            # Live AFL++ stats refresh
            if job.fuzzer_type == "afl" and job.output_dir and job.status == "running":
                result.update(_parse_afl_stats(job.output_dir))

            # Live ffuf results
            if job.fuzzer_type == "ffuf" and job.output_dir:
                rfile = Path(job.output_dir) / "results.json"
                if rfile.exists():
                    try:
                        ffuf_data = json.loads(rfile.read_text())
                        results = ffuf_data.get("results", [])
                        # Categorize by status code
                        by_status: dict = {}
                        for r in results:
                            sc = str(r.get("status", "?"))
                            by_status.setdefault(sc, []).append(r.get("input", {}).get("FUZZ", ""))
                        result["ffuf_by_status"] = by_status
                        result["ffuf_results_count"] = len(results)
                    except Exception:
                        pass

            return result
        finally:
            db.close()

    async def stop_job(self, job_id: str) -> bool:
        """Kill fuzzing process"""
        stopped = False

        task = _job_tasks.get(job_id)
        if task and not task.done():
            task.cancel()
            stopped = True

        proc = _active_processes.get(job_id)
        if proc and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                proc.kill()
            stopped = True

        _update_job(job_id, status="stopped", stopped_at=datetime.utcnow())
        _active_processes.pop(job_id, None)
        _job_tasks.pop(job_id, None)
        return stopped

    async def list_jobs(self, limit: int = 50) -> list:
        """List all fuzzing jobs."""
        db = _db_session()
        try:
            jobs = (
                db.query(FuzzingJob)
                .order_by(FuzzingJob.started_at.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "job_id": j.job_id,
                    "fuzzer_type": j.fuzzer_type,
                    "target": j.target,
                    "target_type": j.target_type,
                    "status": j.status,
                    "crashes_found": j.crashes_found,
                    "hangs_found": j.hangs_found,
                    "execs_per_sec": j.execs_per_sec,
                    "total_paths": j.total_paths,
                    "started_at": j.started_at.isoformat() if j.started_at else None,
                    "is_active": j.job_id in _active_processes,
                }
                for j in jobs
            ]
        finally:
            db.close()
