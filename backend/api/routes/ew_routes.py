"""
Routes — Bloc 11 Guerre Électronique
Jamming, Drone Defense, WiFi/BT, Radar, Cellular.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from services.ew.jamming_service import JammingService
from services.ew.drone_defense_service import DroneDefenseService
from services.ew.wifi_bt_attack_service import WiFiAttackService, BtAttackService
from services.ew.radar_defense_service import RadarService
from services.ew.cellular_attack_service import CellularAttackService

router = APIRouter()

_jam   = JammingService()
_drone = DroneDefenseService()
_wifi  = WiFiAttackService()
_bt    = BtAttackService()
_radar = RadarService()
_cell  = CellularAttackService()


def _auth(authorization_confirmed: bool, msg: str = "Authorization required"):
    if not authorization_confirmed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)


# ── Jamming ──────────────────────────────────────────────────────────────────

class JamFreqReq(BaseModel):
    frequency_hz: float
    power_dbm: float = 30.0
    waveform: str = "noise"
    duration_s: Optional[int] = None
    authorization_confirmed: bool = False

class JamBandReq(BaseModel):
    band_name: str
    power_dbm: float = 30.0
    authorization_confirmed: bool = False

class SweepReq(BaseModel):
    start_hz: float
    stop_hz: float
    step_hz: float = 1_000_000
    dwell_ms: int = 100
    authorization_confirmed: bool = False


@router.get("/jamming/bands")
def jam_list_bands():
    return _jam.list_bands()

@router.get("/jamming/scan")
def jam_scan_spectrum(center_hz: float = 433_000_000, span_hz: float = 50_000_000):
    start = (center_hz - span_hz / 2) / 1e6
    end   = (center_hz + span_hz / 2) / 1e6
    return _jam.scan_spectrum(start, end)

@router.post("/jamming/frequency")
def jam_frequency(req: JamFreqReq):
    _auth(req.authorization_confirmed)
    freq_mhz = req.frequency_hz / 1e6
    return _jam.jam_frequency(freq_mhz, power=req.power_dbm, waveform=req.waveform)

@router.post("/jamming/band")
def jam_band(req: JamBandReq):
    _auth(req.authorization_confirmed)
    return _jam.jam_band(req.band_name, req.power_dbm)

@router.post("/jamming/sweep")
def jam_sweep(req: SweepReq):
    _auth(req.authorization_confirmed)
    return _jam.sweep_jam(req.start_hz / 1e6, req.stop_hz / 1e6, req.step_hz / 1e6, req.dwell_ms / 1000)

@router.delete("/jamming/{jam_id}")
def jam_stop(jam_id: str):
    return _jam.stop_jam(jam_id)

@router.delete("/jamming")
def jam_stop_all():
    return _jam.stop_all_jams()

@router.get("/jamming")
def jam_status():
    return _jam.get_jam_status()


# ── Drone Defense ─────────────────────────────────────────────────────────────

class DroneJamReq(BaseModel):
    contact_id: str
    authorization_confirmed: bool = False

class DroneHijackReq(BaseModel):
    contact_id: str
    authorization_confirmed: bool = False


@router.get("/drone/detect")
def drone_detect(radius_m: float = 2000):
    return _drone.detect_drones(radius_m)

@router.get("/drone/contacts")
def drone_contacts():
    return _drone.list_contacts()

@router.get("/drone/{contact_id}/classify")
def drone_classify(contact_id: str):
    return _drone.classify_drone(contact_id)

@router.get("/drone/{contact_id}/track")
def drone_track(contact_id: str):
    return _drone.track_drone(contact_id)

@router.get("/drone/{contact_id}/locate")
def drone_locate(contact_id: str):
    return _drone.locate_drone(contact_id)

@router.post("/drone/jam-control")
def drone_jam_control(req: DroneJamReq):
    _auth(req.authorization_confirmed)
    return _drone.jam_drone_control(req.contact_id)

@router.post("/drone/jam-video")
def drone_jam_video(req: DroneJamReq):
    _auth(req.authorization_confirmed)
    return _drone.jam_drone_video(req.contact_id)

@router.post("/drone/hijack-dji")
def drone_hijack(req: DroneHijackReq):
    _auth(req.authorization_confirmed)
    return _drone.hijack_dji(req.contact_id)

@router.post("/drone/forced-landing")
def drone_forced_landing(req: DroneJamReq):
    _auth(req.authorization_confirmed)
    return _drone.forced_landing(req.contact_id)


# ── WiFi ──────────────────────────────────────────────────────────────────────

class DeauthReq(BaseModel):
    bssid: str
    client_mac: str = "FF:FF:FF:FF:FF:FF"
    count: int = 100
    authorization_confirmed: bool = False

class EvilTwinReq(BaseModel):
    target_bssid: str
    target_ssid: str
    authorization_confirmed: bool = False

class WiFiJamReq(BaseModel):
    channel: int = 6
    authorization_confirmed: bool = False


@router.get("/wifi/scan")
def wifi_scan():
    return _wifi.scan_aps()

@router.post("/wifi/deauth")
def wifi_deauth(req: DeauthReq):
    _auth(req.authorization_confirmed)
    return _wifi.deauth_attack(req.bssid, req.client_mac, req.count)

@router.post("/wifi/beacon-flood")
def wifi_beacon_flood(authorization_confirmed: bool = False):
    _auth(authorization_confirmed)
    return _wifi.beacon_flood()

@router.post("/wifi/evil-twin")
def wifi_evil_twin(req: EvilTwinReq):
    _auth(req.authorization_confirmed)
    return _wifi.evil_twin(req.target_bssid, req.target_ssid)

@router.post("/wifi/pmkid")
def wifi_pmkid(bssid: str, authorization_confirmed: bool = False):
    _auth(authorization_confirmed)
    return _wifi.pmkid_capture(bssid)

@router.post("/wifi/jam")
def wifi_jam(req: WiFiJamReq):
    _auth(req.authorization_confirmed)
    return _wifi.wifi_jammer(req.channel)


# ── Bluetooth ─────────────────────────────────────────────────────────────────

class BtJamReq(BaseModel):
    authorization_confirmed: bool = False


@router.get("/bluetooth/scan")
def bt_scan():
    return _bt.scan_devices()

@router.post("/bluetooth/ble-jam")
def bt_ble_jam(req: BtJamReq):
    _auth(req.authorization_confirmed)
    return _bt.ble_jammer()

@router.post("/bluetooth/classic-jam")
def bt_classic_jam(req: BtJamReq):
    _auth(req.authorization_confirmed)
    return _bt.bt_classic_jammer()


# ── Radar ─────────────────────────────────────────────────────────────────────

class NoiseJamReq(BaseModel):
    radar_id: str
    waveform: str = "noise_spot"

class DeceptionJamReq(BaseModel):
    radar_id: str
    technique: str = "deception_rgpo"
    delay_time_us: float = 5.0
    doppler_shift_hz: float = 500.0

class FalseTargetReq(BaseModel):
    radar_id: str
    num_targets: int = 10


@router.get("/radar/scan")
def radar_scan(start_freq: float = 1.0, end_freq: float = 18.0):
    return _radar.detect_radar_emissions(start_freq, end_freq)

@router.get("/radar/contacts")
def radar_contacts():
    return _radar.list_contacts()

@router.get("/radar/types")
def radar_types():
    return _radar.list_radar_types()

@router.get("/radar/jamming-techniques")
def radar_jam_techniques():
    return _radar.list_jamming_techniques()

@router.get("/radar/threat-assessment")
def radar_threat():
    return _radar.threat_assessment()

@router.get("/radar/{radar_id}")
def radar_classify(radar_id: str):
    return _radar.classify_radar(radar_id)

@router.post("/radar/noise-jam")
def radar_noise_jam(req: NoiseJamReq):
    return _radar.noise_jamming(req.radar_id, req.waveform)

@router.post("/radar/deception-jam")
def radar_deception_jam(req: DeceptionJamReq):
    return _radar.deception_jamming(req.radar_id, req.technique, req.delay_time_us, req.doppler_shift_hz)

@router.post("/radar/false-targets")
def radar_false_targets(req: FalseTargetReq):
    return _radar.false_target_generation(req.radar_id, req.num_targets)


# ── Cellular ──────────────────────────────────────────────────────────────────

class IMSICatchReq(BaseModel):
    band: str = "gsm900"
    capture_mode: str = "passive"

class BtsSpoofReq(BaseModel):
    mcc: str = "208"
    mnc: str = "01"
    cell_id: int = 12345
    band: str = "gsm900"
    authorization_confirmed: bool = False

class SS7Req(BaseModel):
    msisdn: str
    attack_type: str = "location_query"
    authorization_confirmed: bool = False

class DiameterReq(BaseModel):
    imsi: str
    attack_type: str = "location_query"
    authorization_confirmed: bool = False


@router.get("/cellular/bts-scan")
def cell_bts_scan(band: str = "gsm900"):
    return _cell.detect_bts(band)

@router.post("/cellular/imsi-catch")
def cell_imsi_catch(req: IMSICatchReq):
    return _cell.imsi_catcher_advanced(req.band, req.capture_mode)

@router.get("/cellular/captures")
def cell_captures():
    return _cell.list_captures()

@router.get("/cellular/captures/{session_id}")
def cell_capture_detail(session_id: str):
    return _cell.get_capture(session_id)

@router.post("/cellular/bts-spoof")
def cell_bts_spoof(req: BtsSpoofReq):
    _auth(req.authorization_confirmed)
    return _cell.bts_spoofing(req.mcc, req.mnc, req.cell_id, req.band)

@router.post("/cellular/ss7")
def cell_ss7(req: SS7Req):
    _auth(req.authorization_confirmed)
    return _cell.ss7_attack(req.msisdn, req.attack_type)

@router.post("/cellular/diameter")
def cell_diameter(req: DiameterReq):
    _auth(req.authorization_confirmed)
    return _cell.diameter_attack(req.imsi, req.attack_type)

@router.post("/cellular/downgrade")
def cell_downgrade(target_imsi: Optional[str] = None, authorization_confirmed: bool = False):
    _auth(authorization_confirmed)
    return _cell.downgrade_attack(target_imsi)
