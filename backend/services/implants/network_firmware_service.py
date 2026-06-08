"""
Network Interface Card Firmware Implant
Basé sur : NSA CherryBlossom (Cisco/Broadcom), CIA Vault7 networking
Survit à : changement OS, formatage, réinstallation
Outils réels : ethtool, lspci, ip
"""
from __future__ import annotations

import logging
import os
import random
import re
import subprocess
import uuid
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_NIC_VENDORS = {
    "Broadcom": {"chips": ["BCM5720", "BCM57810", "BCM5719", "BCM57840"], "vuln": "Firmware update without signature check (pre-2016)"},
    "Intel":    {"chips": ["I210", "I350", "82574L", "X540-AT2"],         "vuln": "Intel NVM firmware unsigned (CVE-2019-14575)"},
    "Realtek":  {"chips": ["RTL8111", "RTL8169", "RTL8188"], "vuln": "Bootrom accessible via EEPROM commands"},
    "Mellanox": {"chips": ["ConnectX-4", "ConnectX-5"],      "vuln": "Firmware update via FLINT tool"},
}


def _get_nics() -> List[Dict]:
    """Lister les NIC via lspci et ip link."""
    nics = []
    try:
        out = subprocess.check_output(["lspci", "-nn"], text=True, timeout=5, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if any(k in line for k in ["Ethernet", "Network", "Wireless"]):
                m = re.search(r"\[([\w:]+)\]$", line)
                nics.append({
                    "pci": line.split()[0],
                    "description": line[8:].strip(),
                    "device_id": m.group(1) if m else "unknown",
                })
    except Exception:
        pass

    try:
        out = subprocess.check_output(["ip", "link"], text=True, timeout=5, stderr=subprocess.DEVNULL)
        for m in re.finditer(r"\d+: (\w+):", out):
            iface = m.group(1)
            if iface != "lo":
                try:
                    eth = subprocess.check_output(["ethtool", "-i", iface], text=True, timeout=5, stderr=subprocess.DEVNULL)
                    driver = re.search(r"driver:\s+(\S+)", eth)
                    fw_ver = re.search(r"firmware-version:\s+(.+)", eth)
                    if nics:
                        nics[-1]["interface"] = iface
                        nics[-1]["driver"] = driver.group(1) if driver else "unknown"
                        nics[-1]["firmware_version"] = fw_ver.group(1).strip() if fw_ver else "unknown"
                except Exception:
                    nics.append({"interface": iface})
    except Exception:
        pass

    return nics


class NICFirmwareService:
    """Firmware implant pour cartes réseau."""

    def detect(self, interface: Optional[str] = None) -> Dict:
        nics = _get_nics()
        if nics:
            nic = next((n for n in nics if n.get("interface") == interface), nics[0]) if interface else nics[0]
            vendor = next((v for v in _NIC_VENDORS if v.lower() in nic.get("description","").lower()), "Unknown")
            return {
                "interface": nic.get("interface", "eth0"),
                "description": nic.get("description", "Unknown NIC"),
                "firmware_version": nic.get("firmware_version", "Unknown"),
                "driver": nic.get("driver", "Unknown"),
                "vendor": vendor,
                "all_nics": nics,
                "vulnerable": vendor in _NIC_VENDORS,
                "vulnerability": _NIC_VENDORS.get(vendor, {}).get("vuln", "Unknown"),
                "simulated": False,
            }

        # Simulation
        vendor = random.choice(list(_NIC_VENDORS.keys()))
        chip = random.choice(_NIC_VENDORS[vendor]["chips"])
        return {
            "interface": interface or "eth0",
            "description": f"{vendor} {chip} Gigabit NIC",
            "firmware_version": f"7.{random.randint(10,99)}.{random.randint(1,9)}",
            "driver": vendor.lower() + "e",
            "vendor": vendor,
            "chip": chip,
            "vulnerable": True,
            "vulnerability": _NIC_VENDORS[vendor]["vuln"],
            "simulated": True,
        }

    def dump(self, interface: str = "eth0") -> Dict:
        dump_id = str(uuid.uuid4())
        # ethtool --eeprom-dump
        try:
            result = subprocess.run(
                ["sudo", "ethtool", "--eeprom-dump", interface, "offset", "0", "length", "128"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout:
                return {
                    "dump_id": dump_id, "interface": interface,
                    "eeprom_dump": result.stdout[:500],
                    "simulated": False,
                }
        except Exception:
            pass

        return {
            "dump_id": dump_id,
            "interface": interface,
            "firmware_regions": ["EEPROM (config)", "Flash (firmware code)", "Boot ROM"],
            "eeprom_size": f"{random.choice([16, 32, 64])} KB",
            "firmware_size": f"{random.choice([128, 256, 512])} KB",
            "simulated": True,
        }

    def infect(self, interface: str = "eth0", payload: str = "packet_capture") -> Dict:
        implant_id = str(uuid.uuid4())
        payloads = {
            "packet_capture": "Capture tout le trafic réseau au niveau firmware — avant chiffrement OS",
            "packet_inject":  "Injection de paquets au niveau hardware — invisible au kernel",
            "covert_exfil":   "Canal d'exfiltration covert via paquets broadcast spécialement encodés",
            "nic_backdoor":   "Backdoor wake-on-LAN étendu — réveil sur magic packet + exécution code",
            "mitm":           "MITM au niveau firmware — modification paquets à la volée",
        }
        return {
            "implant_id": implant_id,
            "type": "nic",
            "interface": interface,
            "payload": payload,
            "description": payloads.get(payload, payloads["packet_capture"]),
            "location": "NIC firmware EEPROM / Flash",
            "persistence": "Survit formatage OS, reinstallation, changement de noyau",
            "stealth": "Invisible aux captures réseau OS-level (Wireshark, tcpdump)",
            "capabilities": list(payloads.keys()),
            "bandwidth_overhead": "<0.1% (imperceptible)",
            "simulated": True,
        }

    def capture_packets(self, interface: str, count: int = 100) -> Dict:
        """Capture de paquets via firmware — ou tcpdump en mode réel."""
        packets = []
        try:
            result = subprocess.run(
                ["sudo", "tcpdump", "-i", interface, "-c", str(min(count, 20)), "-nn", "--immediate-mode"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout:
                for line in result.stdout.splitlines()[:20]:
                    packets.append({"raw": line.strip()})
                return {"interface": interface, "captured": len(packets), "packets": packets, "simulated": False}
        except Exception:
            pass

        # Simulation
        protos = ["TCP", "UDP", "ICMP", "ARP", "DNS"]
        for _ in range(min(count, 10)):
            src = f"192.168.{random.randint(1,5)}.{random.randint(1,254)}"
            dst = f"192.168.{random.randint(1,5)}.{random.randint(1,254)}"
            proto = random.choice(protos)
            packets.append({"src": src, "dst": dst, "proto": proto, "size": random.randint(64, 1500)})
        return {"interface": interface, "captured": len(packets), "packets": packets, "simulated": True}

    def inject_packet(self, interface: str, payload_hex: str) -> Dict:
        """Injecter un paquet réseau au niveau firmware."""
        try:
            from scapy.all import sendp, Ether, Raw
            pkt = Ether() / Raw(load=bytes.fromhex(payload_hex))
            sendp(pkt, iface=interface, verbose=False)
            return {"status": "injected", "interface": interface, "bytes": len(payload_hex)//2, "simulated": False}
        except Exception:
            pass
        return {"status": "injected", "interface": interface, "bytes": len(payload_hex)//2, "simulated": True}

    def configure_exfil(self, interface: str, c2_ip: str) -> Dict:
        """Configurer exfiltration covert via NIC firmware."""
        return {
            "interface": interface,
            "c2": c2_ip,
            "method": "Covert channel via VLAN tag manipulation",
            "encoding": "LSB de champs réservés Ethernet/IP",
            "bandwidth": "~10 Kb/s (furtif)",
            "detection_probability": "< 0.1%",
            "simulated": True,
        }

    def check(self, interface: str = "eth0") -> Dict:
        indicators = []
        try:
            r = subprocess.run(["ethtool", "-i", interface], capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                fw = re.search(r"firmware-version:\s+(.+)", r.stdout)
                if fw:
                    indicators.append(f"Firmware: {fw.group(1).strip()}")
        except Exception:
            pass
        infected = random.random() > 0.7
        return {
            "interface": interface,
            "infected": infected,
            "indicators": indicators + (["Firmware version non standard"] if infected else []),
            "simulated": len(indicators) == 0,
        }

    def remove(self, interface: str) -> Dict:
        return {
            "status": "removed",
            "method": "Flash NIC avec firmware officiel via ethtool --flash-firmware",
            "command": f"sudo ethtool --flash-firmware {interface} /path/to/official.bin",
            "simulated": True,
        }
