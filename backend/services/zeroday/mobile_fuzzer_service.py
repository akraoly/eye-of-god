"""
Mobile Fuzzer Service — Bloc 3
Cibles : iOS IOKit/XPC/MIG, Android Binder/Media/OpenGL, Baseband, MediaCodec
Basé sur : iofuzz, syzkaller-iOS, trinity (Android), Binder fuzzer
"""
from __future__ import annotations

import logging
import os
import random
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_JOBS: Dict[str, Dict] = {}
_CRASHES: Dict[str, List] = {}

_TARGETS = {
    "ios_iokit":    {"desc": "IOKit userspace driver interface", "ring": "kernel",  "crash_rate": 0.15},
    "ios_xpc":      {"desc": "XPC IPC (privilege boundary)",     "ring": "sandbox", "crash_rate": 0.10},
    "ios_webkit":   {"desc": "WebKit JS engine + DOM",           "ring": "sandbox", "crash_rate": 0.20},
    "ios_mediacodec": {"desc": "Apple VideoToolbox/CoreMedia",   "ring": "process", "crash_rate": 0.25},
    "android_binder": {"desc": "Android Binder IPC",             "ring": "kernel",  "crash_rate": 0.12},
    "android_media":  {"desc": "Stagefright/MediaCodec",         "ring": "mediaserver","crash_rate": 0.30},
    "android_opengl": {"desc": "GPU driver OpenGL/Vulkan",       "ring": "gpu_driver","crash_rate": 0.18},
    "baseband_at":    {"desc": "AT commands/modem interface",    "ring": "baseband", "crash_rate": 0.08},
    "baseband_nas":   {"desc": "NAS/RRC network stack",         "ring": "baseband", "crash_rate": 0.07},
}

_CRASH_TYPES = [
    {"type": "IOKIT_UAF",         "severity": "CRITICAL", "cvss": 9.8, "exploitable": True},
    {"type": "BINDER_OOB_WRITE",  "severity": "CRITICAL", "cvss": 9.3, "exploitable": True},
    {"type": "MEDIA_HEAP_OVERFLOW","severity": "HIGH",    "cvss": 8.8, "exploitable": True},
    {"type": "XPC_TYPE_CONFUSION", "severity": "HIGH",    "cvss": 8.1, "exploitable": True},
    {"type": "GPU_UAF",           "severity": "HIGH",     "cvss": 7.8, "exploitable": True},
    {"type": "BASEBAND_STACK_OVF","severity": "CRITICAL", "cvss": 9.6, "exploitable": True},
    {"type": "NULL_DEREF",        "severity": "MEDIUM",   "cvss": 5.5, "exploitable": False},
]

_OUTPUT = Path("./data/zeroday/mobile_fuzz")
_OUTPUT.mkdir(parents=True, exist_ok=True)


class MobileFuzzerService:
    """Mobile platform fuzzer — iOS IOKit + Android Binder + Baseband."""

    def start(self, target: str = "ios_iokit", duration_min: int = 60,
              iterations: int = 1000000) -> Dict:
        job_id = str(uuid.uuid4())
        info = _TARGETS.get(target, _TARGETS["ios_iokit"])
        _JOBS[job_id] = {
            "job_id": job_id, "target": target,
            "description": info["desc"], "ring": info["ring"],
            "duration_min": duration_min, "iterations": iterations,
            "status": "running", "progress": 0, "crashes_found": 0,
            "simulated": True,
        }
        _CRASHES[job_id] = []
        return _JOBS[job_id]

    def stop(self, job_id: str) -> Dict:
        if job_id in _JOBS:
            _JOBS[job_id]["status"] = "stopped"
        return _JOBS.get(job_id, {"error": "not found"})

    def get_crashes(self, job_id: str) -> List[Dict]:
        crashes = _CRASHES.get(job_id, [])
        if not crashes:
            target = _JOBS.get(job_id, {}).get("target", "ios_iokit")
            info = _TARGETS.get(target, _TARGETS["ios_iokit"])
            count = 1 if random.random() > info["crash_rate"] else random.randint(1, 3)
            for _ in range(count):
                cls = random.choice(_CRASH_TYPES)
                crashes.append({
                    "crash_id": str(uuid.uuid4()), "job_id": job_id,
                    "target": target, "type": cls["type"],
                    "severity": cls["severity"], "cvss": cls["cvss"],
                    "exploitable": cls["exploitable"],
                    "crash_dump": f"Process {target} died: {cls['type']} at 0x{random.randint(0,0xFFFFFF):06x}",
                    "platform": "ios" if target.startswith("ios") else ("baseband" if target.startswith("baseband") else "android"),
                    "simulated": True,
                })
            _CRASHES[job_id] = crashes
        return crashes

    def triage_crash(self, crash_id: str, job_id: str) -> Dict:
        for c in _CRASHES.get(job_id, []):
            if c["crash_id"] == crash_id:
                return {
                    "crash_id": crash_id, "exploitable": c["exploitable"],
                    "cvss": c["cvss"], "severity": c["severity"],
                    "privesc_possible": c["cvss"] > 8.5,
                    "sandbox_escape": "xpc_bypass" if c.get("platform") == "ios" else "binder_priv",
                    "estimated_effort": "1-3 semaines" if c["exploitable"] else "N/A",
                    "simulated": True,
                }
        return {"error": "crash not found"}

    def generate_poc(self, crash_id: str, job_id: str) -> Dict:
        crash = next((c for c in _CRASHES.get(job_id, []) if c["crash_id"] == crash_id),
                     {"type": "IOKIT_UAF", "target": "ios_iokit"})
        target = crash.get("target", "ios_iokit")
        poc_path = str(_OUTPUT / f"poc_{crash_id[:8]}.{'m' if 'ios' in target else 'java'}")
        content = (
            f"// PoC: {crash.get('type')} in {target}\n"
            f"// crash_id: {crash_id}\n"
            "// Pentest autorisé uniquement\n"
        )
        with open(poc_path, "w") as f:
            f.write(content)
        return {"crash_id": crash_id, "poc_path": poc_path, "target": target, "simulated": True}

    def list_targets(self) -> List[Dict]:
        return [
            {"id": k, "description": v["desc"], "ring": v["ring"],
             "crash_rate": v["crash_rate"]}
            for k, v in _TARGETS.items()
        ]
