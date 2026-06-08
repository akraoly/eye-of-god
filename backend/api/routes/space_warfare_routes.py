"""
Routes — Bloc 14 Guerre Spatiale & Orbital
ASAT, GPS Warfare, Sat Jamming, SSA, LEO Constellations.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from services.space_warfare.asat_service import AsatService
from services.space_warfare.gps_warfare_service import GpsWarfareService
from services.space_warfare.sat_jamming_service import SatJammingService
from services.space_warfare.ssa_service import SsaService
from services.space_warfare.leo_constellation_service import LeoConstellationService

router = APIRouter()

_asat  = AsatService()
_gps   = GpsWarfareService()
_satjam = SatJammingService()
_ssa   = SsaService()
_leo   = LeoConstellationService()


def _auth(authorization_confirmed: bool):
    if not authorization_confirmed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail={"error": "authorization_required"})


# ── ASAT ─────────────────────────────────────────────────────────────────────

class AsatPlanReq(BaseModel):
    norad_id: int
    method: str
    authorization_confirmed: bool = False

class AsatExecReq(BaseModel):
    mission_id: str
    authorization_confirmed: bool = False


@router.get("/asat/methods")
def asat_methods():
    return _asat.list_methods()

@router.get("/asat/satellites")
def asat_satellites(orbit: Optional[str] = None, military_only: bool = False):
    return _asat.list_satellites(orbit, military_only)

@router.get("/asat/missions")
def asat_missions():
    return _asat.list_missions()

@router.get("/asat/satellites/{norad_id}/assess")
def asat_assess(norad_id: int):
    return _asat.assess_target(norad_id)

@router.get("/asat/satellites/{norad_id}/debris")
def asat_debris(norad_id: int, method: str = "ke_interceptor"):
    return _asat.debris_analysis(norad_id, method)

@router.post("/asat/plan")
def asat_plan(req: AsatPlanReq):
    _auth(req.authorization_confirmed)
    return _asat.plan_intercept(req.norad_id, req.method, True)

@router.post("/asat/execute")
def asat_execute(req: AsatExecReq):
    _auth(req.authorization_confirmed)
    return _asat.execute_intercept(req.mission_id, True)


# ── GPS Warfare ───────────────────────────────────────────────────────────────

class GpsJamReq(BaseModel):
    target_system: str = "gps"
    power_w: float = 100.0
    jamming_type: str = "noise_jammer"
    authorization_confirmed: bool = False

class GpsSpoofReq(BaseModel):
    target_system: str = "gps"
    technique: str = "sophisticated_spoof"
    fake_lat: float = 0.0
    fake_lon: float = 0.0
    fake_alt_m: float = 0.0
    authorization_confirmed: bool = False

class NavDenialReq(BaseModel):
    target_area_km2: float = 10000.0
    target_systems: List[str] = ["gps", "glonass"]
    method: str = "combined"
    authorization_confirmed: bool = False


@router.get("/gps/systems")
def gps_systems():
    return _gps.list_gnss_systems()

@router.get("/gps/scan")
def gps_scan(lat: float = 48.85, lon: float = 2.35):
    return _gps.scan_gnss_environment(lat, lon)

@router.get("/gps/sessions")
def gps_sessions():
    return _gps.list_sessions()

@router.get("/gps/anti-spoof")
def gps_anti_spoof(lat: float = 48.85, lon: float = 2.35):
    return _gps.anti_spoofing_detect(lat, lon)

@router.post("/gps/jam")
def gps_jam(req: GpsJamReq):
    _auth(req.authorization_confirmed)
    return _gps.jam_gnss(req.target_system, req.power_w, req.jamming_type, True)

@router.post("/gps/spoof")
def gps_spoof(req: GpsSpoofReq):
    _auth(req.authorization_confirmed)
    return _gps.spoof_position(req.target_system, req.technique, req.fake_lat, req.fake_lon, req.fake_alt_m, True)

@router.post("/gps/nav-denial")
def gps_nav_denial(req: NavDenialReq):
    _auth(req.authorization_confirmed)
    return _gps.navigation_denial(req.target_area_km2, req.target_systems, req.method, True)

@router.delete("/gps/sessions/{session_id}")
def gps_stop(session_id: str):
    return _gps.stop_session(session_id)


# ── Satellite Jamming ─────────────────────────────────────────────────────────

class SatJamReq(BaseModel):
    sat_id: str
    mode: str = "uplink_jam"
    power_kw: float = 10.0
    authorization_confirmed: bool = False

class SatHijackReq(BaseModel):
    sat_id: str
    target_freq_ghz: float
    authorization_confirmed: bool = False


@router.get("/satjam/bands")
def satjam_bands():
    return _satjam.list_bands()

@router.get("/satjam/satellites")
def satjam_satellites(military_only: bool = False):
    return _satjam.list_satellites(military_only)

@router.get("/satjam/operations")
def satjam_ops():
    return _satjam.list_operations()

@router.get("/satjam/satellites/{sat_id}")
def satjam_analyze(sat_id: str):
    return _satjam.analyze_target(sat_id)

@router.post("/satjam/jam")
def satjam_jam(req: SatJamReq):
    _auth(req.authorization_confirmed)
    return _satjam.jam_satellite(req.sat_id, req.mode, req.power_kw, True)

@router.post("/satjam/hijack")
def satjam_hijack(req: SatHijackReq):
    _auth(req.authorization_confirmed)
    return _satjam.transponder_hijack(req.sat_id, req.target_freq_ghz, True)

@router.delete("/satjam/operations/{op_id}")
def satjam_stop(op_id: str):
    return _satjam.stop_operation(op_id)


# ── SSA ───────────────────────────────────────────────────────────────────────

@router.get("/ssa/catalog")
def ssa_catalog():
    return _ssa.get_catalog_stats()

@router.get("/ssa/conjunctions")
def ssa_conjunctions():
    return _ssa.list_conjunctions()

@router.get("/ssa/scan/{orbit_shell}")
def ssa_scan(orbit_shell: str, count: int = 20):
    return _ssa.scan_shell(orbit_shell, count)

@router.get("/ssa/objects/{norad_id}")
def ssa_track(norad_id: int):
    return _ssa.track_object(norad_id)

@router.get("/ssa/objects/{norad_id}/conjunction")
def ssa_conjunction(norad_id: int, look_ahead_hours: int = 72):
    return _ssa.conjunction_analysis(norad_id, look_ahead_hours)

@router.get("/ssa/objects/{norad_id}/maneuver")
def ssa_maneuver(norad_id: int):
    return _ssa.detect_maneuver(norad_id)

@router.get("/ssa/kessler")
def ssa_kessler(altitude_km: float = 800.0):
    return _ssa.kessler_risk_assessment(altitude_km)

@router.get("/ssa/anti-ssa/{norad_id}")
def ssa_anti(norad_id: int, technique: str = "stealth_maneuver"):
    return _ssa.anti_ssa(norad_id, technique)


# ── LEO Constellations ────────────────────────────────────────────────────────

class LeoAttackReq(BaseModel):
    constellation: str
    target_region: str = "EUROPE"
    attack_type: str = "terminal_jamming"
    authorization_confirmed: bool = False

class LeoGsReq(BaseModel):
    constellation: str
    station_id: str
    method: str = "cyber_intrusion"
    authorization_confirmed: bool = False

class LeoCrosslinkReq(BaseModel):
    constellation: str
    authorization_confirmed: bool = False


@router.get("/leo/constellations")
def leo_list():
    return _leo.list_constellations()

@router.get("/leo/operations")
def leo_ops():
    return _leo.list_operations()

@router.get("/leo/constellations/{name}")
def leo_analyze(name: str):
    return _leo.analyze_constellation(name)

@router.get("/leo/constellations/{name}/impact")
def leo_impact(name: str, attack_type: str = "terminal_jamming"):
    return _leo.impact_assessment(name, attack_type)

@router.post("/leo/terminal-attack")
def leo_terminal(req: LeoAttackReq):
    _auth(req.authorization_confirmed)
    return _leo.terminal_attack(req.constellation, req.target_region, req.attack_type, True)

@router.post("/leo/ground-station")
def leo_gs(req: LeoGsReq):
    _auth(req.authorization_confirmed)
    return _leo.ground_station_attack(req.constellation, req.station_id, req.method, True)

@router.post("/leo/crosslink-jam")
def leo_crosslink(req: LeoCrosslinkReq):
    _auth(req.authorization_confirmed)
    return _leo.crosslink_jam(req.constellation, True)

@router.delete("/leo/operations/{op_id}")
def leo_stop(op_id: str):
    return _leo.stop_operation(op_id)
