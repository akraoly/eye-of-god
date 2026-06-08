"""
Routes — Bloc 13 Neutralisation
SCADA/ICS, Military Protocols, Network Neutralization, Missile Defense.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional

from services.neutralization.scada_attack_service import ScadaAttackService
from services.neutralization.military_protocols_service import MilitaryProtocolsService
from services.neutralization.network_neutralization_service import NetworkNeutralizationService
from services.neutralization.missile_defense_service import MissileDefenseService

router = APIRouter()

_scada   = ScadaAttackService()
_milprot = MilitaryProtocolsService()
_net     = NetworkNeutralizationService()
_missile = MissileDefenseService()


# ── SCADA / ICS ───────────────────────────────────────────────────────────────

class ModbusWriteReq(BaseModel):
    target_ip: str
    address: int
    value: int
    authorization_confirmed: bool = False

class S7StopReq(BaseModel):
    target_ip: str
    rack: int = 0
    slot: int = 1
    authorization_confirmed: bool = False

class GOOSEReq(BaseModel):
    target_ip: str
    goose_id: str
    trip_command: bool = True
    authorization_confirmed: bool = False

class DNP3RestartReq(BaseModel):
    target_ip: str
    authorization_confirmed: bool = False


@router.get("/scada/scan")
def scada_scan(network_cidr: str = "192.168.1.0/24"):
    return _scada.scan_ics_network(network_cidr)

@router.get("/scada/protocols")
def scada_protocols():
    return _scada.list_protocols()

@router.get("/scada/attack-vectors")
def scada_attack_vectors():
    return _scada.list_attack_vectors()

@router.get("/scada/sectors")
def scada_sectors():
    return _scada.list_sectors()

@router.get("/scada/read")
def scada_modbus_read(target_ip: str, function_code: int = 3, start_addr: int = 0, count: int = 10):
    return _scada.modbus_read(target_ip, function_code, start_addr, count)

@router.post("/scada/write")
def scada_modbus_write(req: ModbusWriteReq):
    return _scada.modbus_write(req.target_ip, req.address, req.value, req.authorization_confirmed)

@router.post("/scada/s7-stop")
def scada_s7_stop(req: S7StopReq):
    return _scada.s7_plc_stop(req.target_ip, req.rack, req.slot, req.authorization_confirmed)

@router.get("/scada/s7-upload")
def scada_s7_upload(target_ip: str, block_type: str = "OB", block_number: int = 1):
    return _scada.s7_block_upload(target_ip, block_type, block_number)

@router.post("/scada/goose-spoof")
def scada_goose_spoof(req: GOOSEReq):
    return _scada.iec61850_goose_spoof(req.target_ip, req.goose_id, req.trip_command, req.authorization_confirmed)

@router.post("/scada/dnp3-restart")
def scada_dnp3_restart(req: DNP3RestartReq):
    return _scada.dnp3_cold_restart(req.target_ip, req.authorization_confirmed)

@router.get("/scada/opc-browse")
def scada_opc_browse(target_ip: str, port: int = 4840):
    return _scada.opc_ua_browse(target_ip, port)

@router.get("/scada/firmware")
def scada_firmware(target_ip: str, protocol: str = "s7comm"):
    return _scada.firmware_extraction(target_ip, protocol)

@router.get("/scada/sessions/{session_id}")
def scada_session(session_id: str):
    return _scada.get_session(session_id)


# ── Military Protocols ────────────────────────────────────────────────────────

class MIL1553InjectReq(BaseModel):
    rt_address: int
    subaddress: int
    data_words: List[int]
    authorization_confirmed: bool = False

class ARINC429Req(BaseModel):
    label: int
    value: float
    sdi: int = 0
    authorization_confirmed: bool = False

class IFFSpoofReq(BaseModel):
    mode: str = "3A"
    code: str = "7700"
    authorization_confirmed: bool = False

class STANAGReq(BaseModel):
    uav_ip: str
    port: int = 4586
    new_waypoint_lat: float = 48.85
    new_waypoint_lon: float = 2.35
    authorization_confirmed: bool = False

class Link16JamReq(BaseModel):
    authorization_confirmed: bool = False


@router.get("/milprot/protocols")
def milprot_list():
    return _milprot.list_protocols()

@router.get("/milprot/protocols/{protocol}")
def milprot_detail(protocol: str):
    return _milprot.protocol_detail(protocol)

@router.get("/milprot/1553/scan")
def milprot_1553_scan(bus_address: str = "/dev/ttyUSB0"):
    return _milprot.mil1553_bus_scan(bus_address)

@router.post("/milprot/1553/inject")
def milprot_1553_inject(req: MIL1553InjectReq):
    return _milprot.mil1553_inject(req.rt_address, req.subaddress, req.data_words, req.authorization_confirmed)

@router.post("/milprot/arinc429/spoof")
def milprot_arinc429(req: ARINC429Req):
    return _milprot.arinc429_spoof(req.label, req.value, req.sdi, req.authorization_confirmed)

@router.get("/milprot/link16/traffic")
def milprot_link16_traffic(freq_mhz: float = 1000.0):
    return _milprot.link16_analyze_traffic(freq_mhz)

@router.post("/milprot/link16/jam")
def milprot_link16_jam(req: Link16JamReq):
    return _milprot.link16_jam(req.authorization_confirmed)

@router.post("/milprot/iff/spoof")
def milprot_iff_spoof(req: IFFSpoofReq):
    return _milprot.iff_spoof(req.mode, req.code, req.authorization_confirmed)

@router.post("/milprot/stanag/hijack")
def milprot_stanag_hijack(req: STANAGReq):
    return _milprot.stanag4586_uav_hijack(req.uav_ip, req.port, req.new_waypoint_lat,
                                            req.new_waypoint_lon, req.authorization_confirmed)

@router.get("/milprot/attack-scenarios")
def milprot_scenarios():
    return _milprot.list_attack_scenarios()

@router.get("/milprot/link16/j-series")
def milprot_j_series():
    return _milprot.list_link16_j_series()

@router.get("/milprot/sessions/{session_id}")
def milprot_session(session_id: str):
    return _milprot.get_session(session_id)


# ── Network Neutralization ────────────────────────────────────────────────────

class BGPHijackReq(BaseModel):
    target_prefix: str
    attacker_asn: int
    hijack_type: str = "exact_match"
    authorization_confirmed: bool = False

class BGPBlackholeReq(BaseModel):
    target_prefix: str
    upstreams: Optional[List[str]] = None
    authorization_confirmed: bool = False

class DNSPoisonReq(BaseModel):
    target_domain: str
    malicious_ip: str
    nameserver: str = "8.8.8.8"
    authorization_confirmed: bool = False

class DNSAmpReq(BaseModel):
    target_ip: str
    reflectors: Optional[List[str]] = None
    record_type: str = "ANY"
    authorization_confirmed: bool = False

class ARPSpoofReq(BaseModel):
    gateway_ip: str
    gateway_mac: str
    victim_ip: str
    attacker_mac: str
    authorization_confirmed: bool = False

class DHCPStarvReq(BaseModel):
    interface: str = "eth0"
    authorization_confirmed: bool = False

class STPReq(BaseModel):
    interface: str = "eth0"
    authorization_confirmed: bool = False


@router.get("/network/attack-types")
def net_attack_types():
    return _net.list_attack_types()

@router.get("/network/amplification-factors")
def net_amp_factors():
    return _net.list_amplification_factors()

@router.get("/network/bgp-communities")
def net_bgp_communities():
    return _net.list_bgp_communities()

@router.get("/network/infra-scan")
def net_infra_scan(target_asn: int = 12322):
    return _net.infrastructure_scan(target_asn)

@router.post("/network/bgp-hijack")
def net_bgp_hijack(req: BGPHijackReq):
    return _net.bgp_hijack(req.target_prefix, req.attacker_asn, req.hijack_type, req.authorization_confirmed)

@router.post("/network/bgp-blackhole")
def net_bgp_blackhole(req: BGPBlackholeReq):
    return _net.bgp_blackhole(req.target_prefix, req.upstreams, req.authorization_confirmed)

@router.post("/network/dns-poison")
def net_dns_poison(req: DNSPoisonReq):
    return _net.dns_cache_poison(req.target_domain, req.malicious_ip, req.nameserver, req.authorization_confirmed)

@router.post("/network/dns-amplification")
def net_dns_amp(req: DNSAmpReq):
    return _net.dns_amplification(req.target_ip, req.reflectors, req.record_type, req.authorization_confirmed)

@router.post("/network/arp-spoof")
def net_arp_spoof(req: ARPSpoofReq):
    return _net.arp_spoof(req.gateway_ip, req.gateway_mac, req.victim_ip, req.attacker_mac,
                           req.authorization_confirmed)

@router.post("/network/dhcp-starvation")
def net_dhcp_starv(req: DHCPStarvReq):
    return _net.dhcp_starvation(req.interface, req.authorization_confirmed)

@router.post("/network/stp-attack")
def net_stp(req: STPReq):
    return _net.stp_root_takeover(req.interface, req.authorization_confirmed)

@router.get("/network/sessions/{session_id}")
def net_session(session_id: str):
    return _net.get_session(session_id)


# ── Missile Defense ────────────────────────────────────────────────────────────

class TrackReq(BaseModel):
    threat_type: str
    launch_lat: float
    launch_lon: float
    target_lat: float
    target_lon: float

class EngageReq(BaseModel):
    track_id: str
    sam_system: str
    salvo_size: int = 2

class MultiLayerReq(BaseModel):
    threat_type: str
    available_systems: Optional[List[str]] = None

class SaturationReq(BaseModel):
    num_threats: int
    sam_systems: List[str]


@router.get("/missile/sam-systems")
def missile_sam_systems():
    return _missile.list_sam_systems()

@router.get("/missile/threat-classes")
def missile_threat_classes():
    return _missile.list_threat_classes()

@router.get("/missile/countermeasures")
def missile_cms():
    return _missile.list_countermeasures()

@router.post("/missile/track")
def missile_track(req: TrackReq):
    return _missile.track_threat(req.threat_type, req.launch_lat, req.launch_lon,
                                  req.target_lat, req.target_lon)

@router.post("/missile/engage")
def missile_engage(req: EngageReq):
    return _missile.engage_threat(req.track_id, req.sam_system, req.salvo_size)

@router.post("/missile/multi-layer")
def missile_multi_layer(req: MultiLayerReq):
    return _missile.multi_layer_defense(req.threat_type, req.available_systems)

@router.post("/missile/saturation")
def missile_saturation(req: SaturationReq):
    return _missile.saturation_analysis(req.num_threats, req.sam_systems)

@router.get("/missile/effectiveness")
def missile_cm_effectiveness(threat_type: str = "SRBM", cm_type: str = "kinetic_intercept"):
    return _missile.countermeasure_effectiveness(threat_type, cm_type)

@router.get("/missile/tracks")
def missile_tracks():
    return _missile.list_tracks()

@router.get("/missile/engagements/{engagement_id}")
def missile_engagement(engagement_id: str):
    return _missile.get_engagement(engagement_id)
