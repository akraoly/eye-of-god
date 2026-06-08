from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.zeroday.fuzzing_service import fuzzing_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class DownloadFirmwareReq(AuthReq):
    vendor: str
    model: str
    url: Optional[str] = None


class ExtractReq(AuthReq):
    firmware_path: str


class FuzzReq(AuthReq):
    binary_path: str
    timeout: int = 3600
    corpus_path: Optional[str] = None


class TriageReq(AuthReq):
    crash_file: str
    binary_path: str


class CheckExploitReq(AuthReq):
    crash_file: str
    binary_path: str
    arch: str = "MIPS32"


class CheckDefReq(AuthReq):
    binary_path: str


class PocReq(AuthReq):
    crash_file: str
    binary_path: str


class CVEReq(AuthReq):
    vendor: str
    model: str
    binary_name: str
    version: str = "1.0.0"


class ReportReq(AuthReq):
    campaign_id: str


@router.get("/hardware")
async def check_hardware():
    return {"tools": fuzzing_service.tools, "simulation": fuzzing_service.simulation_mode}


@router.get("/vendors")
async def list_vendors():
    from services.zeroday.fuzzing_service import _MOCK_VENDORS
    return list(_MOCK_VENDORS.keys())


@router.post("/firmware/download")
async def download_firmware(req: DownloadFirmwareReq):
    _req_auth(req.authorization_confirmed, "download_firmware")
    return await fuzzing_service.download_firmware(req.vendor, req.model, req.url)


@router.post("/firmware/extract")
async def extract_firmware(req: ExtractReq):
    _req_auth(req.authorization_confirmed, "extract_firmware")
    return await fuzzing_service.extract_firmware(req.firmware_path)


@router.post("/firmware/identify")
async def identify_binaries(req: ExtractReq):
    _req_auth(req.authorization_confirmed, "identify_binaries")
    return await fuzzing_service.identify_binaries(req.firmware_path)


@router.post("/fuzz/start")
async def start_fuzzing(req: FuzzReq):
    _req_auth(req.authorization_confirmed, "fuzz_binary")
    return await fuzzing_service.fuzz_binary(req.binary_path, req.timeout, req.corpus_path)


@router.get("/fuzz/status/{task_id}")
async def get_status(task_id: str):
    return await fuzzing_service.get_fuzzing_status(task_id)


@router.post("/fuzz/stop/{task_id}")
async def stop_job(task_id: str, req: AuthReq):
    _req_auth(req.authorization_confirmed, "stop_fuzzing")
    return await fuzzing_service.stop_fuzzing_job(task_id)


@router.post("/triage")
async def triage_crash(req: TriageReq):
    _req_auth(req.authorization_confirmed, "triage_crash")
    return await fuzzing_service.triage_crash(req.crash_file, req.binary_path)


@router.post("/exploitability")
async def check_exploitability(req: CheckExploitReq):
    _req_auth(req.authorization_confirmed, "check_exploitability")
    return await fuzzing_service.check_exploitability(req.crash_file, req.binary_path, req.arch)


@router.post("/defenses")
async def check_defenses(req: CheckDefReq):
    _req_auth(req.authorization_confirmed, "check_defenses")
    return await fuzzing_service.check_defenses(req.binary_path)


@router.post("/poc/generate")
async def generate_poc(req: PocReq):
    _req_auth(req.authorization_confirmed, "generate_poc")
    path = await fuzzing_service.generate_poc(req.crash_file, req.binary_path)
    return {"poc_path": path}


@router.post("/cve/search")
async def search_cve(req: CVEReq):
    _req_auth(req.authorization_confirmed, "cve_search")
    return await fuzzing_service.search_cve_database(req.vendor, req.model, req.binary_name, req.version)


@router.post("/report")
async def generate_report(req: ReportReq):
    _req_auth(req.authorization_confirmed, "generate_report")
    path = await fuzzing_service.generate_report(req.campaign_id)
    return {"report_path": path}


@router.get("/targets")
async def get_targets():
    return await fuzzing_service.get_targets()


# ─── Bloc 3 — Fuzzing & Zero-Day Industriel ───────────────────────────────────

from services.zeroday.kernel_fuzzer_service   import KernelFuzzerService
from services.zeroday.browser_fuzzer_service  import BrowserFuzzerService
from services.zeroday.mobile_fuzzer_service   import MobileFuzzerService
from services.zeroday.protocol_fuzzer_service import ProtocolFuzzerService
from services.zeroday.exploit_pipeline_service import ExploitPipelineService

_kfuzz  = KernelFuzzerService()
_bfuzz  = BrowserFuzzerService()
_mfuzz  = MobileFuzzerService()
_pfuzz  = ProtocolFuzzerService()
_pipe   = ExploitPipelineService()


class KernelFuzzReq(AuthReq):
    target:       str = "linux"
    subsystem:    str = "net/tcp"
    duration_min: int = 60
    workers:      int = 4

class BrowserFuzzReq(AuthReq):
    browser:      str = "chrome"
    module:       str = "dom"
    fuzzer:       str = "domato"
    duration_min: int = 120
    workers:      int = 2

class MobileFuzzReq(AuthReq):
    target:       str = "ios_iokit"
    duration_min: int = 60
    iterations:   int = 1000000

class ProtocolFuzzReq(AuthReq):
    target_ip:    str = "127.0.0.1"
    protocol:     str = "http2"
    port:         int = 0
    duration_min: int = 30
    mode:         str = "mutation"

class PipelineReq(AuthReq):
    crash_id:      str
    crash_type:    str
    platform:      str = "linux_x64"
    target_binary: str = "/usr/bin/target"

class DeployExploitReq(AuthReq):
    target_ip:  str = "127.0.0.1"
    c2_ip:      str = "127.0.0.1"
    c2_port:    int = 4444

class SandboxReq(AuthReq):
    exploit_id: str

class C2Req(AuthReq):
    c2_framework: str = "metasploit"

class TriageB3Req(AuthReq):
    crash_id: str
    job_id:   str

class PocB3Req(AuthReq):
    crash_id: str
    job_id:   str

class GenExploitReq(AuthReq):
    crash_id: str
    job_id:   str

class MalformedPktReq(AuthReq):
    protocol: str = "http2"
    field:    str = "length"


# — Kernel Fuzzer —
@router.post("/kernel/start")
async def kernel_fuzz_start(req: KernelFuzzReq):
    _req_auth(req.authorization_confirmed, "kernel_fuzzer_start")
    return _kfuzz.start(req.target, req.subsystem, req.duration_min, req.workers)

@router.post("/kernel/stop/{job_id}")
async def kernel_fuzz_stop(job_id: str, req: AuthReq):
    _req_auth(req.authorization_confirmed, "kernel_fuzzer_stop")
    return _kfuzz.stop(job_id)

@router.get("/kernel/status/{job_id}")
async def kernel_fuzz_status(job_id: str):
    return _kfuzz.status(job_id)

@router.get("/kernel/crashes/{job_id}")
async def kernel_fuzz_crashes(job_id: str):
    return _kfuzz.get_crashes(job_id)

@router.post("/kernel/triage")
async def kernel_triage(req: TriageB3Req):
    _req_auth(req.authorization_confirmed, "kernel_triage")
    return _kfuzz.triage_crash(req.crash_id, req.job_id)

@router.get("/kernel/coverage/{job_id}")
async def kernel_coverage(job_id: str):
    return _kfuzz.coverage_report(job_id)


# — Browser Fuzzer —
@router.post("/browser/start")
async def browser_fuzz_start(req: BrowserFuzzReq):
    _req_auth(req.authorization_confirmed, "browser_fuzzer_start")
    return _bfuzz.start(req.browser, req.module, req.fuzzer, req.duration_min, req.workers)

@router.post("/browser/stop/{job_id}")
async def browser_fuzz_stop(job_id: str, req: AuthReq):
    _req_auth(req.authorization_confirmed, "browser_fuzzer_stop")
    return _bfuzz.stop(job_id)

@router.get("/browser/status/{job_id}")
async def browser_fuzz_status(job_id: str):
    return _bfuzz.status(job_id)

@router.get("/browser/crashes/{job_id}")
async def browser_fuzz_crashes(job_id: str):
    return _bfuzz.get_crashes(job_id)

@router.post("/browser/triage")
async def browser_triage(req: TriageB3Req):
    _req_auth(req.authorization_confirmed, "browser_triage")
    return _bfuzz.triage_crash(req.crash_id, req.job_id)

@router.post("/browser/poc/generate")
async def browser_poc(req: PocB3Req):
    _req_auth(req.authorization_confirmed, "browser_poc")
    return _bfuzz.generate_poc(req.crash_id, req.job_id)

@router.post("/browser/exploit/generate")
async def browser_exploit_gen(req: GenExploitReq):
    _req_auth(req.authorization_confirmed, "browser_exploit_gen")
    return _bfuzz.generate_exploit(req.crash_id, req.job_id)

@router.get("/browser/cves/{browser}")
async def browser_cves(browser: str):
    return _bfuzz.list_known_cves(browser)


# — Mobile Fuzzer —
@router.get("/mobile/fuzz/targets")
async def mobile_fuzz_targets():
    return _mfuzz.list_targets()

@router.post("/mobile/fuzz/start")
async def mobile_fuzz_start(req: MobileFuzzReq):
    _req_auth(req.authorization_confirmed, "mobile_fuzzer_start")
    return _mfuzz.start(req.target, req.duration_min, req.iterations)

@router.post("/mobile/fuzz/stop/{job_id}")
async def mobile_fuzz_stop(job_id: str, req: AuthReq):
    _req_auth(req.authorization_confirmed, "mobile_fuzzer_stop")
    return _mfuzz.stop(job_id)

@router.get("/mobile/fuzz/crashes/{job_id}")
async def mobile_fuzz_crashes(job_id: str):
    return _mfuzz.get_crashes(job_id)

@router.post("/mobile/fuzz/triage")
async def mobile_fuzz_triage(req: TriageB3Req):
    _req_auth(req.authorization_confirmed, "mobile_fuzz_triage")
    return _mfuzz.triage_crash(req.crash_id, req.job_id)

@router.post("/mobile/fuzz/poc/generate")
async def mobile_poc(req: PocB3Req):
    _req_auth(req.authorization_confirmed, "mobile_poc")
    return _mfuzz.generate_poc(req.crash_id, req.job_id)


# — Protocol Fuzzer —
@router.get("/protocol/list")
async def protocol_list():
    return _pfuzz.list_protocols()

@router.post("/protocol/start")
async def protocol_fuzz_start(req: ProtocolFuzzReq):
    _req_auth(req.authorization_confirmed, "protocol_fuzzer_start")
    return _pfuzz.start(req.target_ip, req.protocol, req.port, req.duration_min, req.mode)

@router.post("/protocol/stop/{job_id}")
async def protocol_fuzz_stop(job_id: str, req: AuthReq):
    _req_auth(req.authorization_confirmed, "protocol_fuzzer_stop")
    return _pfuzz.stop(job_id)

@router.get("/protocol/crashes/{job_id}")
async def protocol_fuzz_crashes(job_id: str):
    return _pfuzz.get_crashes(job_id)

@router.post("/protocol/triage")
async def protocol_triage(req: TriageB3Req):
    _req_auth(req.authorization_confirmed, "protocol_triage")
    return _pfuzz.triage_crash(req.crash_id, req.job_id)

@router.post("/protocol/malformed-packet")
async def protocol_malformed(req: MalformedPktReq):
    _req_auth(req.authorization_confirmed, "malformed_packet_gen")
    return _pfuzz.generate_malformed_packet(req.protocol, req.field)


# — Exploit Pipeline —
@router.post("/pipeline/run")
async def pipeline_run(req: PipelineReq):
    _req_auth(req.authorization_confirmed, "exploit_pipeline_run")
    return _pipe.run_pipeline(req.crash_id, req.crash_type, req.platform, req.target_binary)

@router.get("/pipeline/status/{job_id}")
async def pipeline_status(job_id: str):
    return _pipe.get_job_status(job_id)

@router.get("/pipeline/exploits")
async def pipeline_exploits():
    return _pipe.get_exploit_database()

@router.post("/pipeline/exploit/deploy/{exploit_id}")
async def pipeline_deploy(exploit_id: str, req: DeployExploitReq):
    _req_auth(req.authorization_confirmed, "exploit_deploy")
    return _pipe.deploy_exploit(exploit_id, req.target_ip, req.c2_ip, req.c2_port)

@router.post("/pipeline/sandbox-test")
async def pipeline_sandbox(req: SandboxReq):
    _req_auth(req.authorization_confirmed, "sandbox_test")
    return _pipe.sandbox_test(req.exploit_id)

@router.post("/pipeline/c2/add/{exploit_id}")
async def pipeline_c2(exploit_id: str, req: C2Req):
    _req_auth(req.authorization_confirmed, "c2_integrate")
    return _pipe.add_to_c2(exploit_id, req.c2_framework)
