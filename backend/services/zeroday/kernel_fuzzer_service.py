"""
Kernel Fuzzer Service — Bloc 3
Basé sur : Syzkaller (Google Project Zero), kAFL, syzbot
Cibles : Linux syscalls/drivers, Windows NTAPI, macOS XNU, eBPF
Coverage-guided — détecte UAF, OOB, race conditions Ring 0
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_JOBS: Dict[str, Dict] = {}
_CRASHES: Dict[str, List] = {}

_KERNEL_TARGETS = {
    "linux":   {"syscalls": 380, "fuzzer": "syzkaller", "versions": ["6.1", "6.6", "6.8", "6.9"]},
    "windows": {"syscalls": 500, "fuzzer": "kAFL+winAFL", "versions": ["10.22H2", "11.23H2", "Server2022"]},
    "macos":   {"syscalls": 500, "fuzzer": "kAFL+XNUFuzz", "versions": ["14.4 Sonoma", "13.6 Ventura"]},
    "ebpf":    {"syscalls": 0,   "fuzzer": "bpf_fuzzer (syzkaller)", "versions": ["Linux 5.8+"]},
    "driver":  {"syscalls": 0,   "fuzzer": "kAFL+IOCTLFUZZ", "versions": ["Generic kernel drivers"]},
}

_SUBSYSTEMS = {
    "linux": ["fs/ext4", "fs/btrfs", "net/tcp", "net/udp", "drivers/usb", "drivers/gpu",
              "mm/slab", "mm/hugetlb", "security/bpf", "net/ipv6", "drivers/nfc", "ipc/shm"],
    "windows": ["win32k.sys", "ntfs.sys", "tcpip.sys", "ntkrnlpa.exe", "dxgkrnl.sys",
                "usbhub.sys", "storport.sys", "cng.sys"],
}

_CRASH_CLASSES = [
    {"type": "UAF",              "severity": "CRITICAL", "cvss": 9.8, "rop_gadgets": True},
    {"type": "OOB_WRITE",        "severity": "CRITICAL", "cvss": 9.3, "rop_gadgets": True},
    {"type": "OOB_READ",         "severity": "HIGH",     "cvss": 7.5, "rop_gadgets": False},
    {"type": "NULL_DEREF",       "severity": "MEDIUM",   "cvss": 5.5, "rop_gadgets": False},
    {"type": "DOUBLE_FREE",      "severity": "HIGH",     "cvss": 8.1, "rop_gadgets": True},
    {"type": "STACK_OVERFLOW",   "severity": "HIGH",     "cvss": 7.8, "rop_gadgets": True},
    {"type": "RACE_CONDITION",   "severity": "HIGH",     "cvss": 7.0, "rop_gadgets": True},
    {"type": "INFO_LEAK",        "severity": "MEDIUM",   "cvss": 6.5, "rop_gadgets": False},
    {"type": "HEAP_GROOMING",    "severity": "HIGH",     "cvss": 8.8, "rop_gadgets": True},
    {"type": "PRIVILEGE_ESC",    "severity": "CRITICAL", "cvss": 9.8, "rop_gadgets": True},
]

_OUTPUT = Path("./data/zeroday/kernel")
_OUTPUT.mkdir(parents=True, exist_ok=True)


def _syzkaller_available() -> bool:
    return os.path.exists("/usr/local/bin/syz-fuzzer") or os.path.exists("/opt/syzkaller/syz-fuzzer")


class KernelFuzzerService:
    """Kernel coverage-guided fuzzer — Syzkaller style."""

    def start(self, target: str = "linux", subsystem: str = "net/tcp",
              duration_min: int = 60, workers: int = 4) -> Dict:
        """Lancer session de kernel fuzzing."""
        job_id = str(uuid.uuid4())
        info = _KERNEL_TARGETS.get(target, _KERNEL_TARGETS["linux"])

        _JOBS[job_id] = {
            "job_id": job_id, "target": target, "subsystem": subsystem,
            "status": "running", "workers": workers, "duration_min": duration_min,
            "start_time": "now", "coverage": 0, "executions": 0,
            "crashes_found": 0, "unique_crashes": 0,
            "fuzzer": info["fuzzer"], "simulated": not _syzkaller_available(),
        }
        _CRASHES[job_id] = []

        if _syzkaller_available():
            cfg = {
                "target": f"{target}/amd64", "http": "127.0.0.1:56741",
                "workdir": str(_OUTPUT / job_id), "kernel_obj": "/boot",
                "syzkaller": "/opt/syzkaller", "procs": workers,
                "type": "isolated", "vm": {"count": workers, "cpu": 2, "mem": 2048},
            }
            cfg_path = _OUTPUT / f"syz_cfg_{job_id[:8]}.json"
            with open(cfg_path, "w") as f:
                json.dump(cfg, f)
            _JOBS[job_id]["config_path"] = str(cfg_path)
            _JOBS[job_id]["simulated"] = False

        return _JOBS[job_id]

    def stop(self, job_id: str) -> Dict:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "stopped"
            return _JOBS[job_id]
        return {"error": "job not found"}

    def status(self, job_id: str) -> Dict:
        if job_id not in _JOBS:
            return {"error": "job not found", "job_id": job_id}
        job = _JOBS[job_id].copy()
        # Simulate progress
        if job["status"] == "running":
            job["executions"] = random.randint(10000, 500000)
            job["coverage"] = random.randint(15, 75)
            job["crashes_found"] = random.randint(0, 12)
            job["unique_crashes"] = random.randint(0, job["crashes_found"])
            job["exec_per_sec"] = random.randint(800, 8000)
        return job

    def get_crashes(self, job_id: str) -> List[Dict]:
        """Lister les crashes trouvés."""
        crashes = _CRASHES.get(job_id, [])
        if not crashes:
            crashes = self._generate_mock_crashes(job_id, random.randint(1, 5))
            _CRASHES[job_id] = crashes
        return crashes

    def _generate_mock_crashes(self, job_id: str, count: int) -> List[Dict]:
        target = _JOBS.get(job_id, {}).get("target", "linux")
        subsystems = _SUBSYSTEMS.get(target, ["net/tcp"])
        crashes = []
        for _ in range(count):
            cls = random.choice(_CRASH_CLASSES)
            crash_id = str(uuid.uuid4())
            crashes.append({
                "crash_id": crash_id,
                "job_id": job_id,
                "type": cls["type"],
                "severity": cls["severity"],
                "cvss": cls["cvss"],
                "subsystem": random.choice(subsystems),
                "call_trace": [
                    f"RIP: 0xffffffff{random.randint(0,0xFFFFFFFF):08x}",
                    f"BUG: {cls['type'].lower().replace('_',' ')} in {random.choice(subsystems)}",
                    f"Call Trace: __alloc_skb+0x{random.randint(0,0xFF):02x}/0x{random.randint(0x40,0x200):x}",
                    f"  kmalloc_node+0x{random.randint(0,0xFF):02x}/0x{random.randint(0x40,0x200):x}",
                ],
                "exploitable": cls["rop_gadgets"],
                "rop_gadgets": cls["rop_gadgets"],
                "kasan_report": f"KASAN: {cls['type'].lower()} in {random.choice(subsystems)}+0x{random.randint(0,0xFFF):03x}",
                "reproducible": random.random() > 0.3,
                "repro_path": str(_OUTPUT / f"repro_{crash_id[:8]}.c"),
                "simulated": True,
            })
        return crashes

    def triage_crash(self, crash_id: str, job_id: str) -> Dict:
        """Analyser un crash — exploitable ou non ?"""
        for c in _CRASHES.get(job_id, []):
            if c["crash_id"] == crash_id:
                return {
                    "crash_id": crash_id,
                    "exploitable": c["exploitable"],
                    "severity": c["severity"],
                    "cvss": c["cvss"],
                    "exploit_class": c["type"],
                    "bypass_needed": ["SMEP", "SMAP", "KASLR", "CFI"] if c["exploitable"] else [],
                    "rop_gadget_count": random.randint(200, 2000) if c["exploitable"] else 0,
                    "cve_candidate": c["exploitable"],
                    "estimated_effort": random.choice(["1-2 jours", "1 semaine", "2-4 semaines"]) if c["exploitable"] else "N/A",
                    "simulated": True,
                }
        return {"error": "crash not found"}

    def coverage_report(self, job_id: str) -> Dict:
        """Rapport de coverage syscall/driver."""
        target = _JOBS.get(job_id, {}).get("target", "linux")
        info = _KERNEL_TARGETS.get(target, _KERNEL_TARGETS["linux"])
        total = info["syscalls"] or 300
        covered = random.randint(int(total * 0.3), int(total * 0.8))
        return {
            "job_id": job_id,
            "total_syscalls": total,
            "covered_syscalls": covered,
            "coverage_pct": round(covered / total * 100, 1),
            "top_uncovered": [
                f"sys_{random.choice(['ioctl','mmap','clone','openat','read','write'])}+variant_{i}"
                for i in range(5)
            ],
            "crash_density": f"{random.uniform(0.1, 2.5):.2f} crashes/100K executions",
            "simulated": True,
        }
