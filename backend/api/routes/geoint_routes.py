"""OSINT Géopolitique Routes — Bloc 6 Supra-Étatiques."""
from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from services.geoint.satellite_service    import SatelliteService
from services.geoint.maritime_service     import MaritimeService
from services.geoint.aviation_service     import AviationService
from services.geoint.darkweb_service      import DarkWebService
from services.geoint.crypto_tracer_service import CryptoTracerService

router = APIRouter()
_sat  = SatelliteService()
_mar  = MaritimeService()
_avi  = AviationService()
_dw   = DarkWebService()
_cry  = CryptoTracerService()


def _auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


# ── SATELLITE ─────────────────────────────────────────────────────────────────

class SatAcquireReq(AuthReq):
    lat:             float = 48.8566
    lon:             float = 2.3522
    satellite:       str   = "sentinel2"
    date_from:       Optional[str] = None
    date_to:         Optional[str] = None
    cloud_cover_max: int   = 20

class SatChangeReq(AuthReq):
    lat:           float = 48.8566
    lon:           float = 2.3522
    date_before:   str   = "2024-01-01"
    date_after:    str   = "2024-06-01"
    analysis_type: str   = "change_det"
    satellite:     str   = "sentinel2"

class SatMilitaryReq(AuthReq):
    lat:       float = 48.8566
    lon:       float = 2.3522
    radius_km: float = 50.0

class SatMonitorReq(AuthReq):
    name:              str  = "Target Installation"
    lat:               float = 48.8566
    lon:               float = 2.3522
    installation_type: str  = "military_base"
    satellites:        Optional[List[str]] = None


@router.get("/satellite/list")
async def sat_list():
    return _sat.list_satellites()

@router.get("/satellite/analysis-types")
async def sat_analysis_types():
    return _sat.list_analysis_types()

@router.post("/satellite/acquire")
async def sat_acquire(req: SatAcquireReq):
    _auth(req.authorization_confirmed, "satellite_acquire")
    return _sat.acquire_image(req.lat, req.lon, req.satellite, req.date_from, req.date_to, req.cloud_cover_max)

@router.post("/satellite/change-detection")
async def sat_change(req: SatChangeReq):
    _auth(req.authorization_confirmed, "satellite_change_detection")
    return _sat.analyze_change(req.lat, req.lon, req.date_before, req.date_after, req.analysis_type, req.satellite)

@router.post("/satellite/military-activity")
async def sat_military(req: SatMilitaryReq):
    _auth(req.authorization_confirmed, "satellite_military_activity")
    return _sat.detect_military_activity(req.lat, req.lon, req.radius_km)

@router.post("/satellite/monitor")
async def sat_monitor(req: SatMonitorReq):
    _auth(req.authorization_confirmed, "satellite_monitor")
    return _sat.monitor_installation(req.name, req.lat, req.lon, req.installation_type, req.satellites)


# ── MARITIME ──────────────────────────────────────────────────────────────────

class MarTrackReq(AuthReq):
    identifier:    str = "123456789"
    id_type:       str = "mmsi"
    history_days:  int = 30

class MarSearchReq(AuthReq):
    lat:         float = 26.0
    lon:         float = 53.0
    radius_nm:   float = 50.0
    filter_type: Optional[str] = None

class MarDarkReq(AuthReq):
    region: str = "Persian Gulf"
    days:   int = 30

class MarSTSReq(AuthReq):
    area: str = "Arabian Sea"

class MarSanctionsReq(AuthReq):
    mmsi_list: List[str] = []


@router.get("/maritime/high-risk-ports")
async def mar_ports():
    return _mar.list_high_risk_ports()

@router.post("/maritime/track")
async def mar_track(req: MarTrackReq):
    _auth(req.authorization_confirmed, "maritime_track")
    return _mar.track_vessel(req.identifier, req.id_type, req.history_days)

@router.post("/maritime/search-area")
async def mar_search(req: MarSearchReq):
    _auth(req.authorization_confirmed, "maritime_search")
    return _mar.search_area(req.lat, req.lon, req.radius_nm, req.filter_type)

@router.post("/maritime/dark-shipping")
async def mar_dark(req: MarDarkReq):
    _auth(req.authorization_confirmed, "maritime_dark_shipping")
    return _mar.detect_dark_shipping(req.region, req.days)

@router.post("/maritime/sts-transfer")
async def mar_sts(req: MarSTSReq):
    _auth(req.authorization_confirmed, "maritime_sts")
    return _mar.ship_to_ship_transfer(req.area)

@router.post("/maritime/sanctions-screen")
async def mar_sanctions(req: MarSanctionsReq):
    _auth(req.authorization_confirmed, "maritime_sanctions")
    return _mar.sanctions_screening(req.mmsi_list)


# ── AVIATION ──────────────────────────────────────────────────────────────────

class AviTrackReq(AuthReq):
    identifier:     str = "a00001"
    id_type:        str = "icao24"
    history_hours:  int = 24

class AviRegionReq(AuthReq):
    lat:             float = 50.0
    lon:             float = 14.0
    radius_nm:       float = 200.0
    filter_category: Optional[str] = None

class AviJetReq(AuthReq):
    owner_name:   str = ""
    tail_number:  str = ""
    history_days: int = 90

class AviMilReq(AuthReq):
    region: str = "Eastern Europe"
    hours:  int = 48

class AviSquawkReq(AuthReq):
    squawk: str = "7700"


@router.post("/aviation/track")
async def avi_track(req: AviTrackReq):
    _auth(req.authorization_confirmed, "aviation_track")
    return _avi.track_aircraft(req.identifier, req.id_type, req.history_hours)

@router.post("/aviation/monitor-region")
async def avi_region(req: AviRegionReq):
    _auth(req.authorization_confirmed, "aviation_region")
    return _avi.monitor_region(req.lat, req.lon, req.radius_nm, req.filter_category)

@router.post("/aviation/private-jet")
async def avi_jet(req: AviJetReq):
    _auth(req.authorization_confirmed, "aviation_private_jet")
    return _avi.detect_private_jet(req.owner_name, req.tail_number, req.history_days)

@router.post("/aviation/military-ops")
async def avi_mil(req: AviMilReq):
    _auth(req.authorization_confirmed, "aviation_military")
    return _avi.detect_military_ops(req.region, req.hours)

@router.post("/aviation/squawk-alert")
async def avi_squawk(req: AviSquawkReq):
    _auth(req.authorization_confirmed, "aviation_squawk")
    return _avi.squawk_alert(req.squawk)


# ── DARK WEB ──────────────────────────────────────────────────────────────────

class DWKeywordsReq(AuthReq):
    keywords: List[str] = ["company_name"]
    sources:  Optional[List[str]] = None
    depth:    str = "standard"

class DWCredLeakReq(AuthReq):
    email_or_domain: str = "company.com"

class DWRansomReq(AuthReq):
    gang_name: str = "LockBit"

class DWMarketsReq(AuthReq):
    search_terms: Optional[List[str]] = None

class DWOnionReq(AuthReq):
    onion_url: str = ""
    depth:     int = 2


@router.get("/darkweb/gangs")
async def dw_gangs():
    return _dw.list_ransomware_gangs()

@router.get("/darkweb/markets")
async def dw_markets_list():
    return _dw.list_known_markets()

@router.post("/darkweb/monitor")
async def dw_monitor(req: DWKeywordsReq):
    _auth(req.authorization_confirmed, "darkweb_monitor")
    return _dw.monitor_keywords(req.keywords, req.sources, req.depth)

@router.post("/darkweb/credential-leak")
async def dw_cred(req: DWCredLeakReq):
    _auth(req.authorization_confirmed, "darkweb_credential_leak")
    return _dw.search_credential_leaks(req.email_or_domain)

@router.post("/darkweb/ransomware/track")
async def dw_ransom(req: DWRansomReq):
    _auth(req.authorization_confirmed, "darkweb_ransomware_track")
    return _dw.track_ransomware_gang(req.gang_name)

@router.post("/darkweb/markets/search")
async def dw_market_search(req: DWMarketsReq):
    _auth(req.authorization_confirmed, "darkweb_markets")
    return _dw.monitor_markets(req.search_terms)

@router.post("/darkweb/onion/crawl")
async def dw_crawl(req: DWOnionReq):
    _auth(req.authorization_confirmed, "darkweb_crawl")
    return _dw.onion_crawl(req.onion_url, req.depth)


# ── CRYPTO TRACER ─────────────────────────────────────────────────────────────

class CryptoTraceReq(AuthReq):
    address:    str = ""
    blockchain: str = "bitcoin"
    depth:      int = 3

class CryptoClusterReq(AuthReq):
    seed_address: str = ""
    blockchain:   str = "bitcoin"
    algorithm:    str = "common_input_ownership"

class CryptoRansomReq(AuthReq):
    ransom_address: str = ""
    gang:           str = "LockBit"
    blockchain:     str = "bitcoin"

class CryptoMixerReq(AuthReq):
    address:      str = ""
    blockchain:   str = "bitcoin"
    lookback_txs: int = 100

class CryptoDeFiReq(AuthReq):
    contract_address: str = ""
    network:          str = "ethereum"


@router.get("/crypto/blockchains")
async def crypto_blockchains():
    return _cry.list_blockchains()

@router.get("/crypto/known-entities")
async def crypto_entities():
    return _cry.known_entities()

@router.post("/crypto/trace")
async def crypto_trace(req: CryptoTraceReq):
    _auth(req.authorization_confirmed, "crypto_trace")
    return _cry.trace_address(req.address, req.blockchain, req.depth)

@router.post("/crypto/cluster")
async def crypto_cluster(req: CryptoClusterReq):
    _auth(req.authorization_confirmed, "crypto_cluster")
    return _cry.cluster_wallets(req.seed_address, req.blockchain, req.algorithm)

@router.post("/crypto/ransomware/track")
async def crypto_ransom(req: CryptoRansomReq):
    _auth(req.authorization_confirmed, "crypto_ransomware")
    return _cry.track_ransomware_payment(req.ransom_address, req.gang, req.blockchain)

@router.post("/crypto/mixer/detect")
async def crypto_mixer(req: CryptoMixerReq):
    _auth(req.authorization_confirmed, "crypto_mixer")
    return _cry.detect_mixer(req.address, req.blockchain, req.lookback_txs)

@router.post("/crypto/defi/analyze")
async def crypto_defi(req: CryptoDeFiReq):
    _auth(req.authorization_confirmed, "crypto_defi")
    return _cry.analyze_defi_contract(req.contract_address, req.network)
