"""
SCADA/ICS Attack Service — Bloc 13 Neutralisation
Modbus, DNP3, IEC 61850, Profinet, S7, OPC-UA.
Simulation uniquement — authorization_confirmed requis.
"""
from __future__ import annotations

import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SCADA_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/neutralization/scada")
_OUTPUT.mkdir(parents=True, exist_ok=True)

PROTOCOLS = {
    "modbus_tcp":  {"port": 502,  "layer": "TCP", "auth": False, "desc": "Modbus TCP — PLCs/RTUs, no auth"},
    "modbus_rtu":  {"port": None, "layer": "serial", "auth": False, "desc": "Modbus RTU — serial legacy"},
    "dnp3":        {"port": 20000,"layer": "TCP/UDP","auth": False,"desc": "DNP3 — SCADA outstations, weak auth"},
    "s7comm":      {"port": 102,  "layer": "TCP", "auth": False, "desc": "Siemens S7 — S300/S400/S1200/S1500"},
    "s7comm_plus": {"port": 102,  "layer": "TCP", "auth": True,  "desc": "S7+ — S1200/S1500 with challenge-response"},
    "iec61850_mms":{"port": 102,  "layer": "TCP", "auth": True,  "desc": "IEC 61850 MMS — power substation"},
    "iec61850_goose":{"port":None,"layer":"Ethernet","auth":False,"desc": "IEC 61850 GOOSE — L2 multicast"},
    "profinet":    {"port": None, "layer": "Ethernet","auth": False,"desc": "Profinet — Siemens factory automation"},
    "ethernetip":  {"port": 44818,"layer":"TCP","auth": False,    "desc": "EtherNet/IP — Rockwell/Allen-Bradley"},
    "opc_ua":      {"port": 4840, "layer": "TCP", "auth": True,   "desc": "OPC-UA — modern SCADA standard, PKI"},
    "bacnet":      {"port": 47808,"layer":"UDP","auth": False,    "desc": "BACnet — building automation"},
}

ATTACK_VECTORS = {
    "modbus_read_coils":       "Read coil/discrete input state — reconnaissance",
    "modbus_force_coil":       "Force Single Coil — write bit to actuator",
    "modbus_write_register":   "Write Multiple Registers — change setpoint/parameter",
    "modbus_replay":           "Replay captured MODBUS frames — inject commands",
    "dnp3_unsolicited_spoof":  "Spoof DNP3 unsolicited response — false sensor data",
    "dnp3_cold_restart":       "DNP3 Cold Restart — force outstation reboot",
    "s7_plc_stop":             "S7 Stop CPU (SZL read + STOP PDU) — shutdown PLC",
    "s7_block_upload":         "S7 Block Upload — steal ladder logic/programs",
    "s7_force_io":             "S7 Force I/O — directly control physical outputs",
    "iec61850_goose_spoof":    "Spoof GOOSE trip command — open circuit breaker",
    "opc_read_all_nodes":      "OPC-UA browse tree — full tag enumeration",
    "replay_attack":           "Capture and replay control frames",
}

PLCS_SIMULATED = [
    {"vendor": "Siemens",   "model": "S7-1500", "protocol": "s7comm_plus", "sector": "power"},
    {"vendor": "Siemens",   "model": "S7-300",  "protocol": "s7comm",      "sector": "manufacturing"},
    {"vendor": "Siemens",   "model": "S7-400",  "protocol": "s7comm",      "sector": "water"},
    {"vendor": "Rockwell",  "model": "ControlLogix 5575", "protocol": "ethernetip", "sector": "oil_gas"},
    {"vendor": "Rockwell",  "model": "MicroLogix 1100",   "protocol": "ethernetip", "sector": "manufacturing"},
    {"vendor": "Schneider", "model": "Modicon M340",      "protocol": "modbus_tcp",  "sector": "energy"},
    {"vendor": "ABB",       "model": "AC500",             "protocol": "modbus_tcp",  "sector": "power"},
    {"vendor": "GE",        "model": "PACSystems",        "protocol": "ethernetip",  "sector": "manufacturing"},
    {"vendor": "Honeywell", "model": "C300",              "protocol": "modbus_tcp",  "sector": "oil_gas"},
]

SECTORS = {
    "power":        {"criticality": "CRITICAL", "consequence": "Blackout — cascading failure possible"},
    "water":        {"criticality": "CRITICAL", "consequence": "Water supply disruption / contamination"},
    "oil_gas":      {"criticality": "CRITICAL", "consequence": "Explosion risk / supply disruption"},
    "manufacturing":{"criticality": "HIGH",     "consequence": "Production halt / equipment damage"},
    "transport":    {"criticality": "HIGH",     "consequence": "Train collision / traffic system failure"},
    "nuclear":      {"criticality": "CRITICAL", "consequence": "Safety system bypass — SCRAM suppression"},
    "chemical":     {"criticality": "CRITICAL", "consequence": "Toxic release / Bhopal-type incident"},
}


class ScadaAttackService:

    def __init__(self):
        self.is_simulation = True

    def _check_auth(self, authorization_confirmed: bool) -> Optional[Dict]:
        if not authorization_confirmed:
            return {"error": "authorization_required",
                    "message": "SCADA attacks require authorization_confirmed: true — pentest contractuel uniquement"}
        return None

    def scan_ics_network(self, network_cidr: str = "192.168.1.0/24") -> Dict:
        discovered = []
        for plc in PLCS_SIMULATED:
            if random.random() > 0.3:
                proto_info = PROTOCOLS.get(plc["protocol"], {})
                discovered.append({
                    "ip":        f"192.168.1.{random.randint(10,254)}",
                    "port":      proto_info.get("port", 502),
                    "vendor":    plc["vendor"],
                    "model":     plc["model"],
                    "protocol":  plc["protocol"],
                    "sector":    plc["sector"],
                    "criticality": SECTORS.get(plc["sector"],{}).get("criticality","UNKNOWN"),
                    "auth_required": proto_info.get("auth", False),
                    "firmware":  f"{random.randint(1,5)}.{random.randint(0,9)}.{random.randint(0,9)}",
                    "is_simulation": True,
                })
        return {
            "network":    network_cidr,
            "devices_found": len(discovered),
            "devices":    discovered,
            "is_simulation": True,
        }

    def modbus_read(self, target_ip: str, function_code: int = 1,
                    start_addr: int = 0, count: int = 10) -> Dict:
        fc_names = {1: "Read Coils", 2: "Read Discrete Inputs",
                    3: "Read Holding Registers", 4: "Read Input Registers"}
        return {
            "target": target_ip,
            "function_code": function_code,
            "function_name": fc_names.get(function_code, "Unknown"),
            "start_address": start_addr,
            "count":         count,
            "values":        [random.randint(0, 65535) for _ in range(count)],
            "raw_hex":       " ".join(f"{random.randint(0,255):02X}" for _ in range(count * 2)),
            "is_simulation": True,
        }

    def modbus_write(self, target_ip: str, address: int, value: int,
                     authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        return {
            "target":        target_ip,
            "action":        "WRITE_REGISTER",
            "address":       address,
            "value_written": value,
            "response":      "Write successful (simulation)",
            "is_simulation": True,
        }

    def s7_plc_stop(self, target_ip: str, rack: int = 0, slot: int = 1,
                     authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        session_id = f"s7_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":  session_id,
            "target_ip":   target_ip,
            "rack":        rack,
            "slot":        slot,
            "action":      "PLC_STOP",
            "method":      "S7 PDU type 0x29 — STOP CPU",
            "plc_state":   "STOP",
            "consequence": "Physical process halted — operator intervention required",
            "tools":       ["python-snap7", "s7scan", "nmap s7-info NSE"],
            "is_simulation": True,
        }
        _SCADA_SESSIONS[session_id] = result
        return result

    def s7_block_upload(self, target_ip: str, block_type: str = "OB",
                         block_number: int = 1) -> Dict:
        data_len = random.randint(500, 50000)
        return {
            "target_ip":  target_ip,
            "block_type": block_type,
            "block_number": block_number,
            "data_length_bytes": data_len,
            "block_data": f"<Ladder Logic / STL program — {data_len} bytes extracted>",
            "is_simulation": True,
        }

    def iec61850_goose_spoof(self, target_ip: str, goose_id: str,
                              trip_command: bool = True,
                              authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        session_id = f"goose_{uuid.uuid4().hex[:8]}"
        result = {
            "session_id":     session_id,
            "target_ip":      target_ip,
            "goose_id":       goose_id,
            "command":        "TRIP" if trip_command else "CLOSE",
            "protocol":       "IEC 61850 GOOSE (L2 multicast — Ethertype 0x88B8)",
            "consequence":    "Circuit breaker TRIP — substation protection triggered",
            "impact":         SECTORS["power"]["consequence"],
            "is_simulation":  True,
        }
        _SCADA_SESSIONS[session_id] = result
        return result

    def dnp3_cold_restart(self, target_ip: str, authorization_confirmed: bool = False) -> Dict:
        err = self._check_auth(authorization_confirmed)
        if err:
            return err
        return {
            "target_ip":    target_ip,
            "action":       "COLD_RESTART",
            "protocol":     "DNP3 Function Code 13",
            "consequence":  "Remote terminal unit reboots — sensor blackout during restart",
            "reboot_time_s": random.randint(30, 300),
            "is_simulation": True,
        }

    def opc_ua_browse(self, target_ip: str, port: int = 4840) -> Dict:
        tags = [f"ns=2;s={random.choice(['Tank','Valve','Pump','Motor','Sensor','Alarm'])}_{i}"
                for i in range(random.randint(10, 50))]
        return {
            "target":    f"opc.tcp://{target_ip}:{port}",
            "total_nodes": len(tags),
            "sample_tags": tags[:20],
            "server_info": {
                "application_name": f"SCADA_{random.choice(['Ignition','FactoryTalk','WinCC','Intouch'])}",
                "server_version": f"{random.randint(1,5)}.{random.randint(0,9)}",
                "security_mode": random.choice(["None","Sign","SignAndEncrypt"]),
            },
            "is_simulation": True,
        }

    def firmware_extraction(self, target_ip: str, protocol: str = "s7comm") -> Dict:
        return {
            "target":    target_ip,
            "protocol":  protocol,
            "firmware_version": f"V{random.randint(1,5)}.{random.randint(0,9)}",
            "extraction_method": "S7 SZL ReadSZL 0x0131 — CPU characteristics",
            "cpu_info":  {"model": random.choice([p["model"] for p in PLCS_SIMULATED]),
                          "serial": uuid.uuid4().hex[:16].upper()},
            "known_cves": random.sample(["CVE-2022-38773","CVE-2019-13945","CVE-2017-0144"], 2),
            "is_simulation": True,
        }

    def list_protocols(self) -> Dict:
        return {k: {"port": v["port"], "desc": v["desc"], "auth": v["auth"]}
                for k, v in PROTOCOLS.items()}

    def list_attack_vectors(self) -> Dict:
        return ATTACK_VECTORS

    def list_sectors(self) -> Dict:
        return SECTORS

    def get_session(self, session_id: str) -> Dict:
        return _SCADA_SESSIONS.get(session_id, {"error": "not_found"})
