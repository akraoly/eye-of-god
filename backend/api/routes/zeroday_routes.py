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
