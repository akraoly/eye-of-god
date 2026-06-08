"""
Routes — Bloc 12 Surveillance Stratégique
Air (ADS-B/MLAT/ACARS), Maritime (AIS), SIGINT, Satellite ISR.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from services.surveillance.air_surveillance_service import AirSurveillanceService
from services.surveillance.maritime_surveillance_service import MaritimeSurveillanceService
from services.surveillance.sigint_service import SigintService
from services.surveillance.satellite_intel_service import SatelliteIntelService

router = APIRouter()

_air  = AirSurveillanceService()
_sea  = MaritimeSurveillanceService()
_sig  = SigintService()
_sat  = SatelliteIntelService()


# ── ADS-B / Air Surveillance ─────────────────────────────────────────────────

class MLATReq(BaseModel):
    station_data: List[dict]

class PredictReq(BaseModel):
    flight_id: str
    time_horizon_minutes: int = 30


@router.post("/air/start")
def air_start(lat: float = 48.85, lon: float = 2.35, radius_km: float = 200):
    return _air.adsb_receiver_start(lat, lon, radius_km=radius_km)

@router.post("/air/stop")
def air_stop():
    return _air.adsb_receiver_stop()

@router.get("/air/contacts")
def air_contacts():
    return _air.adsb_contacts()

@router.get("/air/military")
def air_military():
    return _air.adsb_filter_military()

@router.get("/air/private")
def air_private():
    return _air.adsb_filter_private()

@router.get("/air/aircraft/{icao24}")
def air_aircraft_detail(icao24: str):
    return _air.adsb_aircraft_detail(icao24)

@router.post("/air/mlat")
def air_mlat(req: MLATReq):
    return _air.mlat_aircraft_position(req.station_data)

@router.get("/air/acars")
def air_acars(message: Optional[str] = None):
    return _air.acars_decode(message)

@router.get("/air/military-detect")
def air_military_detect():
    return _air.military_flight_detect()

@router.post("/air/predict")
def air_predict(req: PredictReq):
    return _air.flight_prediction(req.flight_id, req.time_horizon_minutes)


# ── AIS / Maritime ────────────────────────────────────────────────────────────

@router.post("/maritime/start")
def sea_start(lat: float = 48.85, lon: float = 2.35, radius_km: float = 100):
    return _sea.ais_receiver_start(lat, lon, radius_km)

@router.post("/maritime/stop")
def sea_stop():
    return _sea.ais_receiver_stop()

@router.get("/maritime/vessels")
def sea_vessels():
    return _sea.ais_vessels()

@router.get("/maritime/military")
def sea_military():
    return _sea.ais_filter_military()

@router.get("/maritime/suspicious")
def sea_suspicious():
    return _sea.ais_filter_suspicious()

@router.get("/maritime/vessel/{mmsi}")
def sea_vessel_detail(mmsi: int):
    return _sea.ais_ship_detail(mmsi)

@router.get("/maritime/anomaly/{vessel_id}")
def sea_anomaly(vessel_id: str):
    return _sea.ais_anomaly_detect(vessel_id)

@router.get("/maritime/predict/{vessel_id}")
def sea_predict(vessel_id: str, hours: int = 12):
    return _sea.vessel_trajectory_prediction(vessel_id, hours)

@router.get("/maritime/eez")
def sea_eez(eez_name: str = "French_EEZ"):
    return _sea.exclusive_economic_zone_monitor(eez_name)


# ── SIGINT ────────────────────────────────────────────────────────────────────

class ScanReq(BaseModel):
    start_freq: float
    stop_freq: float
    step_hz: float = 25000

class DemodReq(BaseModel):
    freq_mhz: float
    modulation: str
    bandwidth_khz: float = 200

class DFReq(BaseModel):
    signal_freq_mhz: float
    station_data: Optional[List[dict]] = None
    method: str = "tdoa"

class GeoReq(BaseModel):
    station_bearings: List[dict]

class HopReq(BaseModel):
    base_freq_mhz: float
    hop_rate_hz: float = 100


@router.post("/sigint/scan")
def sigint_scan(req: ScanReq):
    return _sig.scanner_wideband(req.start_freq, req.stop_freq, req.step_hz)

@router.get("/sigint/classify")
def sigint_classify(freq_mhz: float = 433.0, snr_db: float = 20.0):
    return _sig.automatic_signal_classification(snr_db, freq_mhz)

@router.post("/sigint/demodulate")
def sigint_demod(req: DemodReq):
    return _sig.demodulate(req.freq_mhz, req.modulation, req.bandwidth_khz)

@router.post("/sigint/df")
def sigint_df(req: DFReq):
    return _sig.direction_finding(req.signal_freq_mhz, req.station_data, req.method)

@router.post("/sigint/geolocate")
def sigint_geolocate(req: GeoReq):
    return _sig.signal_geolocate(req.station_bearings)

@router.post("/sigint/fhss")
def sigint_fhss(req: HopReq):
    return _sig.frequency_hopping_track(req.base_freq_mhz, req.hop_rate_hz)

@router.get("/sigint/burst")
def sigint_burst(freq_mhz: float = 433.0, window_s: float = 60.0):
    return _sig.burst_detection(freq_mhz, window_s)

@router.get("/sigint/protocols")
def sigint_protocols():
    return _sig.list_protocols()

@router.get("/sigint/df-methods")
def sigint_df_methods():
    return _sig.list_df_methods()

@router.get("/sigint/captures/{capture_id}")
def sigint_capture(capture_id: str):
    return _sig.get_capture(capture_id)

@router.get("/sigint/emitters")
def sigint_emitters():
    return _sig.list_emitters()


# ── Satellite ISR ─────────────────────────────────────────────────────────────

class TaskSatReq(BaseModel):
    sat_name: str
    target_lat: float
    target_lon: float
    mode: str = "spotlight"

class CoverageReq(BaseModel):
    lat_min: float
    lat_max: float
    lon_min: float
    lon_max: float
    sat_types: Optional[List[str]] = None

class ISRPlanReq(BaseModel):
    target_name: str
    lat: float
    lon: float
    priority: str = "HIGH"

class SARReq(BaseModel):
    target_lat: float
    target_lon: float
    pre_event_date: Optional[str] = None


@router.get("/satellite/list")
def sat_list(sat_type: Optional[str] = None):
    return _sat.list_satellites(sat_type)

@router.get("/satellite/{name}")
def sat_detail(name: str):
    return _sat.get_satellite_detail(name)

@router.get("/satellite/{name}/passes")
def sat_passes(name: str, lat: float = 48.85, lon: float = 2.35, hours: int = 24):
    return _sat.predict_pass(lat, lon, name, hours)

@router.post("/satellite/coverage")
def sat_coverage(req: CoverageReq):
    return _sat.area_coverage_windows(req.lat_min, req.lat_max, req.lon_min, req.lon_max, req.sat_types)

@router.post("/satellite/task")
def sat_task(req: TaskSatReq):
    return _sat.task_satellite(req.sat_name, req.target_lat, req.target_lon, req.mode)

@router.post("/satellite/sar-analysis")
def sat_sar(req: SARReq):
    return _sat.sar_analysis(req.target_lat, req.target_lon, req.pre_event_date)

@router.post("/satellite/isr-plan")
def sat_isr_plan(req: ISRPlanReq):
    return _sat.isr_collection_plan(req.target_name, req.lat, req.lon, req.priority)

@router.get("/satellite/orbit-types")
def sat_orbits():
    return _sat.list_orbit_types()

@router.get("/satellite/tasking-modes")
def sat_modes():
    return _sat.list_tasking_modes()
