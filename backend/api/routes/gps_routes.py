from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from services.radio.gps_spoofing_service import gps_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class GenerateSignalReq(AuthReq):
    target_lat: float
    target_lon: float
    altitude: float = 50.0
    timestamp: Optional[str] = None
    satellites: int = 8


class WaypointReq(AuthReq):
    waypoints: List[dict]
    speed_kmh: int = 50


class TransmitReq(AuthReq):
    signal_file: str
    frequency: float = 1575420000.0
    gain: int = 40
    duration: int = 60


class DroneReq(AuthReq):
    target_drone_ip: str
    fake_lat: float
    fake_lon: float


class JamReq(AuthReq):
    frequency: float = 1575420000.0
    duration: int = 10


@router.get("/hardware")
async def check_hardware():
    return await gps_service.check_hardware()


@router.post("/signal/generate")
async def generate_signal(req: GenerateSignalReq):
    _req_auth(req.authorization_confirmed, "generate_gps_signal")
    path = await gps_service.generate_gps_signal(req.target_lat, req.target_lon, req.altitude, req.timestamp, req.satellites)
    return {"signal_file": path}


@router.post("/signal/waypoints")
async def generate_waypoints(req: WaypointReq):
    _req_auth(req.authorization_confirmed, "generate_waypoint_path")
    path = await gps_service.generate_waypoint_path(req.waypoints, req.speed_kmh)
    return {"signal_file": path}


@router.post("/transmit/start")
async def transmit(req: TransmitReq):
    _req_auth(req.authorization_confirmed, "transmit_gps_signal")
    return await gps_service.transmit_gps_signal(req.signal_file, req.frequency, req.gain, req.duration)


@router.post("/transmit/stop")
async def stop_transmit(req: AuthReq):
    _req_auth(req.authorization_confirmed, "stop_transmit")
    return await gps_service.stop_transmit()


@router.post("/drone/spoof")
async def spoof_drone(req: DroneReq):
    _req_auth(req.authorization_confirmed, "spoof_drone")
    return await gps_service.spoof_drone(req.target_drone_ip, req.fake_lat, req.fake_lon)


@router.post("/jam")
async def jam_gps(req: JamReq):
    _req_auth(req.authorization_confirmed, "jam_gps")
    return await gps_service.jam_gps(req.frequency, req.duration)


@router.get("/status")
async def get_status():
    return {"transmitting": gps_service._transmitting, "simulation": gps_service.simulation_mode}
