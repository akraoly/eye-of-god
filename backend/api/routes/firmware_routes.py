"""
Firmware Implants API — Bloc 2 Supra-Étatiques
UEFI / HDD / SMM / Intel ME / NIC / GPU / TPM / ACPI
Usage : pentest autorisé uniquement (authorization_confirmed=true requis)
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth.dependencies import get_current_user
from database.db import get_db
from database.models_firmware import FirmwareImplant, FirmwareDump, FirmwareOperation
from services.implants.uefi_implant_service import UEFIImplantService
from services.implants.hdd_firmware_service import HDDFirmwareService
from services.implants.smm_rootkit_service import SMMRootkitService
from services.implants.intel_me_service import IntelMEService
from services.implants.network_firmware_service import NICFirmwareService
from services.implants.gpu_firmware_service import GPUFirmwareService
from services.implants.tpm_inject_service import TPMInjectService
from services.implants.acpi_rootkit_service import ACPIRootkitService

logger = logging.getLogger(__name__)
router = APIRouter()

# ── Services ──────────────────────────────────────────────────────────────────
_uefi   = UEFIImplantService()
_hdd    = HDDFirmwareService()
_smm    = SMMRootkitService()
_me     = IntelMEService()
_nic    = NICFirmwareService()
_gpu    = GPUFirmwareService()
_tpm    = TPMInjectService()
_acpi   = ACPIRootkitService()


# ── Schemas ───────────────────────────────────────────────────────────────────
class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class UEFIInfectReq(AuthReq):
    target: str = "localhost"
    payload_type: str = "lojax"


class HDDInfectReq(AuthReq):
    device: str = "/dev/sda"
    payload_type: str = "grayfish"


class SMMInfectReq(AuthReq):
    smi_index: int = 0x30


class MEInfectReq(AuthReq):
    cve: str = "CVE-2017-5689"


class NICInfectReq(AuthReq):
    interface: str = "eth0"
    payload: str = "packet_capture"


class GPUInfectReq(AuthReq):
    payload_type: str = "gpu_rootkit"


class TPMBypassReq(AuthReq):
    drive: str = "C:"


class TPMInjectReq(AuthReq):
    key_data: str = ""
    handle: str = "0x81000010"


class ACPIInfectReq(AuthReq):
    table: str = "DSDT"
    payload_type: str = "persistence"


class ACPIExecReq(AuthReq):
    method: str = "\\_SB.IMPL._INI"


class GPUCrackReq(AuthReq):
    hash_type: str = "NTLM"
    hashes: list = []


class GPUExfilReq(AuthReq):
    data: str = ""
    method: str = "pixels"


def _require_auth(req: AuthReq):
    if not req.authorization_confirmed:
        raise HTTPException(403, "authorization_confirmed=true requis — pentest autorisé uniquement")


def _log_op(db: Session, implant_type: str, operation: str, result: dict):
    try:
        op = FirmwareOperation(
            type=implant_type,
            action=operation,
            status="done",
            result=result if isinstance(result, dict) else {},
            simulated=result.get("simulated", True) if isinstance(result, dict) else True,
        )
        db.add(op)
        db.commit()
    except Exception as e:
        logger.debug("DB log failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/overview")
def firmware_overview():
    """Vue globale de tous les modules firmware disponibles."""
    return {
        "modules": [
            {"id": "uefi",     "name": "UEFI Bootkit",         "ring": "Ring 0 / UEFI", "persistence": "Survit reflash OS"},
            {"id": "hdd",      "name": "HDD Firmware",         "ring": "Hardware",      "persistence": "Survit formatage"},
            {"id": "smm",      "name": "SMM Ring -2 Rootkit",  "ring": "Ring -2",       "persistence": "Survit hyperviseur"},
            {"id": "intel_me", "name": "Intel ME / AMD PSP",   "ring": "Ring -3",       "persistence": "Hors-bande, même éteint"},
            {"id": "nic",      "name": "NIC Firmware",         "ring": "Hardware NIC",  "persistence": "Survit OS swap"},
            {"id": "gpu",      "name": "GPU VBIOS",            "ring": "GPU firmware",  "persistence": "VBIOS ROM"},
            {"id": "tpm",      "name": "TPM 2.0 Injection",    "ring": "TPM coprocessor","persistence": "PCR manipulation"},
            {"id": "acpi",     "name": "ACPI Rootkit (DSDT)",  "ring": "Ring 0 / AML",  "persistence": "Survit réinstall OS"},
        ],
        "total_modules": 8,
        "requires_auth": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# UEFI
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/uefi/detect")
def uefi_detect():
    return _uefi.detect()


@router.get("/uefi/dump")
def uefi_dump():
    return _uefi.dump()


@router.post("/uefi/infect")
def uefi_infect(req: UEFIInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _uefi.infect(req.target, req.payload_type)
    _log_op(db, "uefi", "infect", result)
    return result


@router.post("/uefi/drop-esp")
def uefi_drop_esp(req: AuthReq, payload_path: str = "", db: Session = Depends(get_db)):
    _require_auth(req)
    result = _uefi.drop_to_esp(payload_path)
    _log_op(db, "uefi", "drop_esp", result)
    return result


@router.post("/uefi/install-bootkit")
def uefi_install_bootkit(req: UEFIInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _uefi.install_bootkit(req.target)
    _log_op(db, "uefi", "install_bootkit", result)
    return result


@router.get("/uefi/check")
def uefi_check():
    return _uefi.check()


@router.post("/uefi/remove")
def uefi_remove(req: UEFIInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _uefi.remove(req.target)
    _log_op(db, "uefi", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# HDD FIRMWARE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/hdd/detect")
def hdd_detect(device: str = "/dev/sda"):
    return _hdd.detect(device)


@router.get("/hdd/dump")
def hdd_dump(device: str = "/dev/sda"):
    return _hdd.dump(device)


@router.post("/hdd/infect")
def hdd_infect(req: HDDInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _hdd.infect(req.device, req.payload_type)
    _log_op(db, "hdd", "infect", result)
    return result


@router.post("/hdd/hidden-partition")
def hdd_hidden_partition(req: HDDInfectReq, size_mb: int = 100, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _hdd.create_hidden_partition(req.device, size_mb)
    _log_op(db, "hdd", "hidden_partition", result)
    return result


@router.get("/hdd/extract-hidden")
def hdd_extract_hidden(device: str = "/dev/sda"):
    return _hdd.extract_hidden(device)


@router.get("/hdd/check")
def hdd_check(device: str = "/dev/sda"):
    return _hdd.check(device)


@router.post("/hdd/remove")
def hdd_remove(req: HDDInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _hdd.remove(req.device)
    _log_op(db, "hdd", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# SMM RING -2
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/smm/detect")
def smm_detect():
    return _smm.detect_smi_handlers()


@router.post("/smm/infect")
def smm_infect(req: SMMInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _smm.infect(req.smi_index)
    _log_op(db, "smm", "infect", result)
    return result


@router.post("/smm/install-keylogger")
def smm_keylogger(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _smm.install_keylogger()
    _log_op(db, "smm", "keylogger", result)
    return result


@router.get("/smm/read-memory")
def smm_read_memory(address: str = "0xA0000", size: int = 256):
    return _smm.read_memory(address, size)


@router.post("/smm/disable-secureboot")
def smm_disable_secureboot(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _smm.disable_secureboot()
    _log_op(db, "smm", "disable_secureboot", result)
    return result


@router.get("/smm/check")
def smm_check():
    return _smm.check()


@router.post("/smm/remove")
def smm_remove(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _smm.remove()
    _log_op(db, "smm", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# INTEL ME / AMD PSP
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/me/detect")
def me_detect(target: str = "localhost"):
    return _me.detect(target)


@router.get("/me/dump")
def me_dump():
    return _me.dump()


@router.post("/me/infect")
def me_infect(req: MEInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _me.infect(req.cve)
    _log_op(db, "intel_me", "infect", result)
    return result


@router.get("/me/network-access")
def me_network(target_ip: str = "127.0.0.1"):
    return _me.network_access(target_ip)


@router.post("/me/kvm")
def me_kvm(req: MEInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _me.activate_kvm()
    _log_op(db, "intel_me", "kvm", result)
    return result


@router.get("/me/check")
def me_check():
    return _me.check()


@router.post("/me/remove")
def me_remove(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _me.remove()
    _log_op(db, "intel_me", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# NIC FIRMWARE
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/nic/detect")
def nic_detect(interface: Optional[str] = None):
    return _nic.detect(interface)


@router.get("/nic/dump")
def nic_dump(interface: str = "eth0"):
    return _nic.dump(interface)


@router.post("/nic/infect")
def nic_infect(req: NICInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _nic.infect(req.interface, req.payload)
    _log_op(db, "nic", "infect", result)
    return result


@router.post("/nic/capture")
def nic_capture(req: NICInfectReq, count: int = 100, db: Session = Depends(get_db)):
    _require_auth(req)
    return _nic.capture_packets(req.interface, count)


@router.post("/nic/inject")
def nic_inject(req: NICInfectReq, payload_hex: str = "", db: Session = Depends(get_db)):
    _require_auth(req)
    result = _nic.inject_packet(req.interface, payload_hex)
    _log_op(db, "nic", "inject", result)
    return result


@router.post("/nic/configure-exfil")
def nic_exfil(req: NICInfectReq, c2_ip: str = "0.0.0.0", db: Session = Depends(get_db)):
    _require_auth(req)
    result = _nic.configure_exfil(req.interface, c2_ip)
    _log_op(db, "nic", "exfil", result)
    return result


@router.get("/nic/check")
def nic_check(interface: str = "eth0"):
    return _nic.check(interface)


@router.post("/nic/remove")
def nic_remove(req: NICInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _nic.remove(req.interface)
    _log_op(db, "nic", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# GPU VBIOS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/gpu/detect")
def gpu_detect():
    return _gpu.detect()


@router.get("/gpu/dump")
def gpu_dump():
    return _gpu.dump()


@router.post("/gpu/infect")
def gpu_infect(req: GPUInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _gpu.infect(req.payload_type)
    _log_op(db, "gpu", "infect", result)
    return result


@router.post("/gpu/crack")
def gpu_crack(req: GPUCrackReq, db: Session = Depends(get_db)):
    _require_auth(req)
    return _gpu.offload_cracking(req.hash_type, req.hashes)


@router.post("/gpu/exfil-framebuffer")
def gpu_exfil(req: GPUExfilReq, db: Session = Depends(get_db)):
    _require_auth(req)
    return _gpu.exfil_framebuffer(req.data, req.method)


@router.get("/gpu/check")
def gpu_check():
    return _gpu.check()


@router.post("/gpu/remove")
def gpu_remove(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _gpu.remove()
    _log_op(db, "gpu", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# TPM 2.0
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/tpm/detect")
def tpm_detect():
    return _tpm.detect()


@router.get("/tpm/extract-keys")
def tpm_extract_keys():
    return _tpm.extract_keys()


@router.post("/tpm/inject-keys")
def tpm_inject_keys(req: TPMInjectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _tpm.inject_keys(req.key_data, req.handle)
    _log_op(db, "tpm", "inject_keys", result)
    return result


@router.post("/tpm/bypass-bitlocker")
def tpm_bypass(req: TPMBypassReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _tpm.bypass_bitlocker(req.drive)
    _log_op(db, "tpm", "bypass_bitlocker", result)
    return result


@router.post("/tpm/fake-attestation")
def tpm_attestation(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _tpm.fake_attestation()
    _log_op(db, "tpm", "fake_attestation", result)
    return result


@router.get("/tpm/check")
def tpm_check():
    return _tpm.check()


@router.post("/tpm/remove")
def tpm_remove(req: AuthReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _tpm.remove()
    _log_op(db, "tpm", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# ACPI ROOTKIT
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/acpi/detect")
def acpi_detect(target: str = "localhost"):
    return _acpi.detect(target)


@router.get("/acpi/dump")
def acpi_dump(table: str = "DSDT"):
    return _acpi.dump(table)


@router.post("/acpi/infect")
def acpi_infect(req: ACPIInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _acpi.infect(req.table, req.payload_type)
    _log_op(db, "acpi", "infect", result)
    return result


@router.post("/acpi/execute")
def acpi_execute(req: ACPIExecReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _acpi.execute_method(req.method)
    _log_op(db, "acpi", "execute", result)
    return result


@router.get("/acpi/check")
def acpi_check(table: str = "DSDT"):
    return _acpi.check(table)


@router.post("/acpi/remove")
def acpi_remove(req: ACPIInfectReq, db: Session = Depends(get_db)):
    _require_auth(req)
    result = _acpi.remove(req.table)
    _log_op(db, "acpi", "remove", result)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# IMPLANTS HISTORY (DB)
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/history")
def firmware_history(limit: int = 50, db: Session = Depends(get_db)):
    """Historique des opérations firmware."""
    try:
        ops = db.query(FirmwareOperation).order_by(
            FirmwareOperation.id.desc()
        ).limit(limit).all()
        return [
            {
                "id": o.id,
                "type": o.type,
                "operation": o.action,
                "status": o.status,
                "simulated": o.simulated,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in ops
        ]
    except Exception:
        return []


@router.get("/implants/list")
def firmware_implants_list(db: Session = Depends(get_db)):
    """Lister tous les implants actifs."""
    try:
        implants = db.query(FirmwareImplant).order_by(
            FirmwareImplant.id.desc()
        ).limit(100).all()
        return [
            {
                "id": i.id,
                "implant_id": i.implant_id,
                "type": i.type,
                "target": i.target_id,
                "status": i.status,
                "payload_type": i.payload_type,
                "simulated": i.simulated,
            }
            for i in implants
        ]
    except Exception:
        return []
