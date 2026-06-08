"""
WiFiAgent — Agent IA spécialisé WiFi.

Orchestre les capacités WiFi avec Claude comme moteur de raisonnement.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es l'agent WiFi de L'Œil de Dieu, expert en sécurité sans fil.

Tu orchestres toutes les capacités WiFi :
- Scan et reconnaissance des réseaux 802.11
- Capture handshake 4-way et PMKID
- Attaques WPS (Pixie Dust, brute-force PIN)
- Cracking hashcat (mode 22000 WPA2)
- Evil Twin / Rogue AP
- Post-exploitation réseau connecté
- Enumération des hôtes, ports, partages SMB

RÈGLES :
1. Toujours demander confirmation avant une attaque active (deauth, Evil Twin)
2. Préciser si le mode simulation est actif
3. Analyser les résultats et proposer les étapes suivantes
4. Documenter chaque action pour le rapport final
5. Usage exclusivement légal : pentest autorisé, CTF, lab personnel

Tu réponds en français. Sois précis, technique, concis.
"""

TOOLS: List[Dict] = [
    {
        "name": "wifi_scan",
        "description": "Scanner les réseaux WiFi environnants",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string", "description": "Interface WiFi (ex: wlan0)"},
                "duration": {"type": "integer", "description": "Durée du scan en secondes (défaut: 30)"},
                "channels": {"type": "array", "items": {"type": "integer"}, "description": "Canaux à scanner"}
            },
            "required": ["interface"]
        }
    },
    {
        "name": "wifi_capture_handshake",
        "description": "Capturer le 4-way handshake d'un réseau WPA2",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string"},
                "bssid": {"type": "string", "description": "BSSID de l'AP cible"},
                "ssid": {"type": "string"},
                "channel": {"type": "integer"},
                "client_mac": {"type": "string", "description": "MAC d'un client connecté (optionnel)"}
            },
            "required": ["interface", "bssid", "ssid", "channel"]
        }
    },
    {
        "name": "wifi_capture_pmkid",
        "description": "Capturer le PMKID sans client via hcxdumptool",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string"},
                "bssid": {"type": "string"},
                "ssid": {"type": "string"}
            },
            "required": ["interface", "bssid", "ssid"]
        }
    },
    {
        "name": "wifi_crack",
        "description": "Lancer le cracking hashcat sur un handshake ou PMKID capturé",
        "input_schema": {
            "type": "object",
            "properties": {
                "bssid": {"type": "string"},
                "ssid": {"type": "string"},
                "hs_id": {"type": "string", "description": "ID du handshake capturé"},
                "wordlist": {"type": "string", "description": "Chemin de la wordlist"}
            },
            "required": ["bssid", "ssid"]
        }
    },
    {
        "name": "wifi_wps_attack",
        "description": "Attaque WPS Pixie Dust via reaver/bully",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string"},
                "bssid": {"type": "string"},
                "channel": {"type": "integer"}
            },
            "required": ["interface", "bssid"]
        }
    },
    {
        "name": "wifi_connect",
        "description": "Se connecter à un réseau WiFi avec une passphrase",
        "input_schema": {
            "type": "object",
            "properties": {
                "ssid": {"type": "string"},
                "passphrase": {"type": "string"},
                "interface": {"type": "string"}
            },
            "required": ["ssid", "passphrase"]
        }
    },
    {
        "name": "wifi_scan_network",
        "description": "Scanner les hôtes du réseau connecté (ARP + nmap)",
        "input_schema": {
            "type": "object",
            "properties": {
                "gateway": {"type": "string", "description": "IP de la passerelle (ex: 192.168.1.1)"}
            },
            "required": ["gateway"]
        }
    },
    {
        "name": "wifi_scan_host",
        "description": "Scanner les ports ouverts d'un hôte",
        "input_schema": {
            "type": "object",
            "properties": {
                "ip": {"type": "string", "description": "IP de l'hôte cible"}
            },
            "required": ["ip"]
        }
    },
    {
        "name": "wifi_evil_twin",
        "description": "Créer un Evil Twin (faux AP) pour capturer des credentials",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string"},
                "ssid": {"type": "string"},
                "bssid_victim": {"type": "string"},
                "channel": {"type": "integer"}
            },
            "required": ["interface", "ssid", "bssid_victim"]
        }
    },
    {
        "name": "wifi_full_automation",
        "description": "Lancer le workflow automatisé complet (scan → attack → connect → report)",
        "input_schema": {
            "type": "object",
            "properties": {
                "interface": {"type": "string"},
                "target_bssid": {"type": "string", "description": "Optionnel : cibler un BSSID spécifique"},
                "scan_duration": {"type": "integer"},
                "wordlist": {"type": "string"}
            },
            "required": ["interface"]
        }
    },
]


async def run_wifi_agent(
    user_message: str,
    llm_client: Any,
    model: str = "claude-sonnet-4-6",
    conversation_history: Optional[List[Dict]] = None,
) -> Dict:
    """
    Exécute l'agent WiFi — Claude raisonne + appelle les outils WiFi.
    """
    from services.wifi.wifi_scanner_service import WiFiScannerService
    from services.wifi.wifi_crack_service import WiFiCrackService
    from services.wifi.wifi_automation_service import WiFiAutomationService

    scanner = WiFiScannerService()
    cracker = WiFiCrackService()
    automation = WiFiAutomationService()

    messages = list(conversation_history or [])
    messages.append({"role": "user", "content": user_message})

    tools_used = []
    final_response = ""

    for _ in range(5):  # max 5 tours d'outils
        response = llm_client.messages.create(
            model=model,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Collecter les text blocks
        text_parts = [b.text for b in response.content if hasattr(b, "text") and b.text]
        if text_parts:
            final_response = " ".join(text_parts)

        if response.stop_reason != "tool_use":
            break

        # Traiter les tool_use blocks
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            tool_name = block.name
            inputs = block.input or {}
            tools_used.append(tool_name)

            try:
                result = await _dispatch_tool(tool_name, inputs, scanner, cracker, automation)
            except Exception as e:
                result = {"error": str(e)}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    return {
        "response": final_response,
        "tools_used": tools_used,
        "agent": "wifi_agent",
        "model": model,
    }


async def _dispatch_tool(
    name: str, inputs: Dict,
    scanner: Any, cracker: Any, automation: Any,
) -> Any:
    if name == "wifi_scan":
        return await scanner.scan(
            inputs["interface"],
            duration=inputs.get("duration", 30),
            channels=inputs.get("channels"),
        )
    elif name == "wifi_capture_handshake":
        return await cracker.capture_handshake(
            inputs["interface"], inputs["bssid"], inputs["ssid"],
            channel=inputs.get("channel", 6),
            client_mac=inputs.get("client_mac"),
        )
    elif name == "wifi_capture_pmkid":
        return await cracker.capture_pmkid(
            inputs["interface"], inputs["bssid"], inputs["ssid"]
        )
    elif name == "wifi_crack":
        return await cracker.crack_hashcat(
            inputs["bssid"], inputs["ssid"],
            wordlist=inputs.get("wordlist"),
        )
    elif name == "wifi_wps_attack":
        return await cracker.wps_pixiedust(
            inputs["interface"], inputs["bssid"],
            channel=inputs.get("channel", 6),
        )
    elif name == "wifi_connect":
        return cracker.connect(
            inputs["ssid"], inputs["passphrase"],
            interface=inputs.get("interface", "wlan0"),
        )
    elif name == "wifi_scan_network":
        return await automation.scan_connected_network(inputs["gateway"])
    elif name == "wifi_scan_host":
        return await automation.scan_host_ports(inputs["ip"])
    elif name == "wifi_evil_twin":
        return await cracker.start_evil_twin(
            inputs["interface"], inputs["ssid"], inputs["bssid_victim"],
            channel=inputs.get("channel", 6),
        )
    elif name == "wifi_full_automation":
        return await automation.run_full_workflow(
            interface=inputs["interface"],
            target_bssid=inputs.get("target_bssid"),
            scan_duration=inputs.get("scan_duration", 30),
            wordlist=inputs.get("wordlist"),
        )
    else:
        return {"error": f"Outil inconnu : {name}"}
