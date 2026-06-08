"""Air-Gap Exploitation Routes — Bloc 4 Supra-Étatiques."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from services.airgap.em_injection_service    import EMInjectionService
from services.airgap.acoustic_service        import AcousticService
from services.airgap.sidechannel_service     import SideChannelService
from services.airgap.thermal_exfil_service   import ThermalExfilService
from services.airgap.usb_dropper_service     import USBDropperService

router = APIRouter()

_em   = EMInjectionService()
_ac   = AcousticService()
_sc   = SideChannelService()
_th   = ThermalExfilService()
_usb  = USBDropperService()


def _auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


# ── EM / TEMPEST ──────────────────────────────────────────────────────────────

class EMScanReq(AuthReq):
    target_ip:    str = "192.168.1.1"
    duration_sec: int = 30

class VanEckReq(AuthReq):
    target_distance_m: float = 5.0
    frequency_mhz:     float = 165.0
    duration_sec:      int   = 60

class TempestKeyReq(AuthReq):
    duration_sec:     int   = 120
    antenna_gain_db:  float = 12.0

class EMFIReq(AuthReq):
    target_device: str = "smartcard"
    attack_type:   str = "secure_boot_bypass"

class ODINIReq(AuthReq):
    mode:            str = "transmit"
    data:            str = "SECRET"
    receiver_device: str = "smartphone"


@router.get("/em/techniques")
async def em_techniques():
    return _em.list_techniques()

@router.post("/em/scan")
async def em_scan(req: EMScanReq):
    _auth(req.authorization_confirmed, "em_spectrum_scan")
    return _em.scan_em_spectrum(req.target_ip, req.duration_sec)

@router.post("/em/van-eck")
async def van_eck(req: VanEckReq):
    _auth(req.authorization_confirmed, "van_eck_phreaking")
    return _em.van_eck_attack(req.target_distance_m, req.frequency_mhz, req.duration_sec)

@router.post("/em/tempest/keyboard")
async def tempest_keyboard(req: TempestKeyReq):
    _auth(req.authorization_confirmed, "tempest_keyboard_eavesdrop")
    return _em.tempest_keylog(req.duration_sec, req.antenna_gain_db)

@router.post("/em/fault-inject")
async def em_fault_inject(req: EMFIReq):
    _auth(req.authorization_confirmed, "em_fault_injection")
    return _em.em_fault_inject(req.target_device, req.attack_type)

@router.post("/em/odini")
async def em_odini(req: ODINIReq):
    _auth(req.authorization_confirmed, "odini_covert_channel")
    return _em.odini_covert_channel(req.mode, req.data, req.receiver_device)

@router.get("/em/session/{session_id}")
async def em_session(session_id: str):
    return _em.get_session(session_id)


# ── ACOUSTIC ──────────────────────────────────────────────────────────────────

class LaserMicReq(AuthReq):
    target_surface: str   = "window"
    duration_sec:   int   = 60
    distance_m:     float = 100.0

class MosquitoReq(AuthReq):
    mode:          str   = "transmit"
    data:          str   = "EXFIL_DATA"
    frequency_khz: float = 18.0

class FansmitterReq(AuthReq):
    data:         str = "KEY:0xDEADBEEF"
    fan_min_rpm:  int = 1000
    fan_max_rpm:  int = 3000

class AirHopperReq(AuthReq):
    data:          str   = "SECRET"
    fm_freq_mhz:   float = 107.5

class PowerHammerReq(AuthReq):
    data:         str = "AES_KEY"
    circuit_type: str = "in_line"


@router.get("/acoustic/techniques")
async def acoustic_techniques():
    return _ac.list_techniques()

@router.post("/acoustic/laser-mic")
async def laser_mic(req: LaserMicReq):
    _auth(req.authorization_confirmed, "laser_microphone")
    return _ac.laser_mic_capture(req.target_surface, req.duration_sec, req.distance_m)

@router.post("/acoustic/mosquito")
async def mosquito(req: MosquitoReq):
    _auth(req.authorization_confirmed, "mosquito_ultrasonic")
    return _ac.mosquito_exfil(req.mode, req.data, req.frequency_khz)

@router.post("/acoustic/fansmitter")
async def fansmitter(req: FansmitterReq):
    _auth(req.authorization_confirmed, "fansmitter_channel")
    return _ac.fansmitter_exfil(req.data, req.fan_min_rpm, req.fan_max_rpm)

@router.post("/acoustic/airhopper")
async def airhopper(req: AirHopperReq):
    _auth(req.authorization_confirmed, "airhopper_fm_exfil")
    return _ac.airhopper_exfil(req.data, req.fm_freq_mhz)

@router.post("/acoustic/powerhammer")
async def powerhammer(req: PowerHammerReq):
    _auth(req.authorization_confirmed, "powerhammer_powerline")
    return _ac.powerhammer_exfil(req.data, req.circuit_type)


# ── SIDE-CHANNEL ──────────────────────────────────────────────────────────────

class PowerAnalysisReq(AuthReq):
    attack:       str  = "cpa"
    target_algo:  str  = "AES-128"
    num_traces:   int  = 1000
    hw_available: bool = False

class CacheAttackReq(AuthReq):
    attack:          str = "flush_reload"
    target_process:  str = "openssl"
    duration_sec:    int = 30

class SpectreReq(AuthReq):
    variant:      str = "spectre_v1"
    target:       str = "kernel"
    read_offset:  int = 0x1000

class RowhammerReq(AuthReq):
    target: str = "page_table"
    method: str = "double_sided"

class TimingReq(AuthReq):
    target_url:  str = "https://target.example.com"
    oracle_type: str = "rsa_decrypt"
    samples:     int = 10000


@router.get("/sidechannel/attacks")
async def sidechannel_attacks():
    return _sc.list_attacks()

@router.post("/sidechannel/power-analysis")
async def power_analysis(req: PowerAnalysisReq):
    _auth(req.authorization_confirmed, "power_analysis")
    return _sc.run_power_analysis(req.attack, req.target_algo, req.num_traces, req.hw_available)

@router.post("/sidechannel/cache-attack")
async def cache_attack(req: CacheAttackReq):
    _auth(req.authorization_confirmed, "cache_side_channel")
    return _sc.run_cache_attack(req.attack, req.target_process, req.duration_sec)

@router.post("/sidechannel/spectre")
async def spectre_attack(req: SpectreReq):
    _auth(req.authorization_confirmed, "spectre_meltdown")
    return _sc.run_spectre(req.variant, req.target, req.read_offset)

@router.post("/sidechannel/rowhammer")
async def rowhammer(req: RowhammerReq):
    _auth(req.authorization_confirmed, "rowhammer_dram")
    return _sc.run_rowhammer(req.target, req.method)

@router.post("/sidechannel/timing")
async def timing_attack(req: TimingReq):
    _auth(req.authorization_confirmed, "timing_oracle")
    return _sc.timing_attack(req.target_url, req.oracle_type, req.samples)

@router.get("/sidechannel/job/{job_id}")
async def sidechannel_job(job_id: str):
    return _sc.get_job(job_id)


# ── THERMAL / OPTICAL ─────────────────────────────────────────────────────────

class FLIRReq(AuthReq):
    elapsed_sec:   int = 30
    keyboard_type: str = "membrane"

class BitWhisperReq(AuthReq):
    data:                  str   = "KEY"
    adjacent_distance_cm:  float = 30.0
    mode:                  str   = "transmit"

class LEDExfilReq(AuthReq):
    data_path:   str = "/etc/shadow"
    led_source:  str = "hdd_led"
    modulation:  str = "OOK"

class AIRInReq(AuthReq):
    camera_ip: str = "192.168.1.100"
    mode:      str = "exfil"
    data:      str = "PASSWORD"

class BrightnessReq(AuthReq):
    data:            str = "SECRET_KEY"
    brightness_min:  int = 0
    brightness_max:  int = 100


@router.get("/thermal/techniques")
async def thermal_techniques():
    return _th.list_techniques()

@router.post("/thermal/flir-keyboard")
async def flir_keyboard(req: FLIRReq):
    _auth(req.authorization_confirmed, "flir_keyboard_read")
    return _th.flir_keyboard_read(req.elapsed_sec, req.keyboard_type)

@router.post("/thermal/bitwhisper")
async def bitwhisper(req: BitWhisperReq):
    _auth(req.authorization_confirmed, "bitwhisper_channel")
    return _th.bitwhisper_channel(req.data, req.adjacent_distance_cm, req.mode)

@router.post("/thermal/led-exfil")
async def led_exfil(req: LEDExfilReq):
    _auth(req.authorization_confirmed, "led_optical_exfil")
    return _th.led_exfil(req.data_path, req.led_source, req.modulation)

@router.post("/thermal/airin-camera")
async def airin_camera(req: AIRInReq):
    _auth(req.authorization_confirmed, "airin_ir_camera")
    return _th.airin_camera_exfil(req.camera_ip, req.mode, req.data)

@router.post("/thermal/brightness-exfil")
async def brightness_exfil(req: BrightnessReq):
    _auth(req.authorization_confirmed, "brightness_screen_exfil")
    return _th.screen_brightness_exfil(req.data, req.brightness_min, req.brightness_max)


# ── USB DROPPER / BADUSB ──────────────────────────────────────────────────────

class USBPayloadReq(AuthReq):
    device:    str = "rubber_ducky"
    payload_id: str = "reverse_shell_ps"
    c2_ip:     str = "192.168.1.100"
    c2_port:   int = 4444
    target_os: str = "windows"

class USBDeployReq(AuthReq):
    session_id:          str = ""
    target_description:  str = "unlocked Windows workstation"

class JTAGReq(AuthReq):
    target_chip: str = "STM32F4"
    interface:   str = "SWD"
    attack_type: str = "readback_flash"

class OMGCableReq(AuthReq):
    wifi_ssid:        str  = "FREE_WIFI"
    c2_ip:            str  = "192.168.1.100"
    geofence_enabled: bool = False


@router.get("/usb/devices")
async def usb_devices():
    return _usb.list_devices()

@router.get("/usb/payloads")
async def usb_payloads():
    return _usb.list_payloads()

@router.post("/usb/payload/generate")
async def usb_generate(req: USBPayloadReq):
    _auth(req.authorization_confirmed, "usb_payload_generate")
    return _usb.generate_payload(req.device, req.payload_id, req.c2_ip, req.c2_port, req.target_os)

@router.post("/usb/deploy")
async def usb_deploy(req: USBDeployReq):
    _auth(req.authorization_confirmed, "usb_deploy")
    return _usb.simulate_deploy(req.session_id, req.target_description)

@router.post("/usb/jtag-swd")
async def jtag_swd(req: JTAGReq):
    _auth(req.authorization_confirmed, "jtag_swd_attack")
    return _usb.jtag_swd_attack(req.target_chip, req.interface, req.attack_type)

@router.post("/usb/omg-cable")
async def omg_cable(req: OMGCableReq):
    _auth(req.authorization_confirmed, "omg_cable_deploy")
    return _usb.omg_cable_deploy(req.wifi_ssid, req.c2_ip, req.geofence_enabled)
