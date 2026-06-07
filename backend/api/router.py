from fastapi import APIRouter, Depends
from api.routes import (
    chat, memory, user, system, exploit, code, knowledge, life,
    observe, soc, offensive, c2, auth, vision, autonomy, voice,
    c2_unified, network, pentest, sysmonitor,
    # Modules 5, 6, 7, 9
    exploit_engine, implants, osint, credentials,
    # Modules 11, 12, 14, 17, 18
    reports, threat_intel, re_engine, forensics, privesc,
    # Modules 13, 15, 16, 19, 20
    fuzzing, lab, honeypots, lateral, self_improve,
    # Capacités 1, 2, 3, 4, 5, 6, 7
    audio_capture, cameras, packet_capture,
    post_exploit, triggers, exfil, omniscience,
    # MITRE ATT&CK
    mitre,
    # BLE Scanner
    ble,
    # RFID
    rfid,
    # SDR
    sdr,
    # Audit Reports
    report_routes,
    # AEGIS — Renseignement offensif
    aegis_intel,
)
from core.auth.dependencies import get_current_user

router = APIRouter()

# ── Route publique ─────────────────────────────────────────────────────────────
router.include_router(auth.router, prefix="/auth", tags=["Auth"])

# ── Routes protégées ──────────────────────────────────────────────────────────
_protected = {"dependencies": [Depends(get_current_user)]}

# Core
router.include_router(chat.router,       prefix="/chat",       tags=["Chat"],                   **_protected)
router.include_router(memory.router,     prefix="/memory",     tags=["Memory"],                 **_protected)
router.include_router(user.router,       prefix="/user",       tags=["User"],                   **_protected)
router.include_router(system.router,     prefix="/system",     tags=["System"],                 **_protected)
router.include_router(exploit.router,    prefix="/exploit",    tags=["Exploit / OSEE"],         **_protected)
router.include_router(code.router,       prefix="/code",       tags=["Code / Dev"],             **_protected)
router.include_router(knowledge.router,  prefix="/knowledge",  tags=["Knowledge Base"],         **_protected)
router.include_router(life.router,       prefix="/life",       tags=["Life / Personal"],        **_protected)
router.include_router(observe.router,    prefix="/observe",    tags=["Self Observation"],       **_protected)
router.include_router(soc.router,        prefix="/soc",        tags=["SOC"],                    **_protected)
router.include_router(offensive.router,  prefix="/offensive",  tags=["Offensive"],              **_protected)
router.include_router(c2.router,         prefix="/c2",         tags=["C2 — Frameworks"],        **_protected)
router.include_router(c2_unified.router, prefix="/c2/unified", tags=["C2 Manager Unifié"],      **_protected)
router.include_router(vision.router,     prefix="/vision",     tags=["Vision"],                 **_protected)
router.include_router(autonomy.router,   prefix="/autonomy",   tags=["Autonomy"],               **_protected)
router.include_router(voice.router,      prefix="/voice",      tags=["Voice — STT/TTS"],        **_protected)
router.include_router(network.router,    prefix="/network",    tags=["Network Monitor"])
router.include_router(pentest.router,    prefix="/pentest",    tags=["Pentest Orchestré"],      **_protected)
router.include_router(sysmonitor.router, prefix="/sentinel",   tags=["Sentinel — Surveillance Système"])

# ── Modules 5, 6, 7, 9 ────────────────────────────────────────────────────────
router.include_router(exploit_engine.router, prefix="/exploit-engine", tags=["Exploit Engine"], **_protected)
router.include_router(implants.router,       prefix="/implants",       tags=["Implants"],        **_protected)
router.include_router(osint.router,          prefix="/osint",          tags=["OSINT"],           **_protected)
router.include_router(credentials.router,    prefix="/credentials",    tags=["Credentials"],     **_protected)

# ── Modules 11, 12, 14, 17, 18 ───────────────────────────────────────────────
router.include_router(reports.router,      prefix="/reports",      tags=["Reports"],             **_protected)
router.include_router(threat_intel.router, prefix="/threat-intel", tags=["Threat Intel"],        **_protected)
router.include_router(re_engine.router,    prefix="/re",           tags=["Reverse Engineering"], **_protected)
router.include_router(forensics.router,    prefix="/forensics",    tags=["Forensics"],           **_protected)
router.include_router(privesc.router,      prefix="/privesc",      tags=["PrivEsc"],             **_protected)

# ── Modules 13, 15, 16, 19, 20 ───────────────────────────────────────────────
router.include_router(fuzzing.router,      prefix="/fuzzing",      tags=["Fuzzing"],             **_protected)
router.include_router(lab.router,          prefix="/lab",          tags=["Virtual Lab"],         **_protected)
router.include_router(honeypots.router,    prefix="/honeypots",    tags=["Honeypots"],           **_protected)
router.include_router(lateral.router,      prefix="/lateral",      tags=["Lateral Movement"],    **_protected)
router.include_router(self_improve.router, prefix="/self-improve", tags=["Self Improvement"],    **_protected)

# ── Capacités 1, 2, 3, 4, 5, 6, 7 ───────────────────────────────────────────
router.include_router(audio_capture.router,  prefix="/audio",        tags=["Audio Capture"],  **_protected)
router.include_router(cameras.router,        prefix="/cameras",      tags=["Camera Scanner"], **_protected)
router.include_router(packet_capture.router, prefix="/capture",      tags=["Packet Capture"], **_protected)
router.include_router(post_exploit.router,   prefix="/post-exploit", tags=["Post-Exploit"],   **_protected)
router.include_router(triggers.router,       prefix="/triggers",     tags=["Triggers"],       **_protected)
router.include_router(exfil.router,          prefix="/exfil",        tags=["Exfiltration"],   **_protected)
router.include_router(omniscience.router,    prefix="/omniscience",  tags=["Omniscience"],    **_protected)

# ── MITRE ATT&CK ──────────────────────────────────────────────────────────────
router.include_router(mitre.router,          prefix="/mitre",         tags=["MITRE ATT&CK"],   **_protected)

# ── BLE Scanner ───────────────────────────────────────────────────────────────
router.include_router(ble.router,            prefix="/ble",           tags=["BLE Scanner"],    **_protected)

# ── RFID Badge Tool ────────────────────────────────────────────────────────────
router.include_router(rfid.router,           prefix="/rfid",          tags=["RFID Badge Tool"], **_protected)

# ── SDR ─────────────────────────────────────────────────────────────────────────
router.include_router(sdr.router,            prefix="/sdr",           tags=["SDR"],             **_protected)

# ── Audit Reports ───────────────────────────────────────────────────────────────
router.include_router(report_routes.router,  prefix="/reports/audit", tags=["Audit Reports"],   **_protected)

# ── AEGIS — Renseignement offensif ───────────────────────────────────────────
router.include_router(aegis_intel.router,    prefix="/aegis",         tags=["AEGIS Intel"],     **_protected)
