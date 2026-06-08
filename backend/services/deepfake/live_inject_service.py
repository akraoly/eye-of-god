"""
Live Video Injection — Bloc 5
Techniques : V4L2 loopback virtual camera, OBS virtual cam,
             inject deepfake stream dans Zoom/Teams/Meet/Webex,
             RTSP stream hijack, WebRTC injection
"""
from __future__ import annotations

import logging
import os
import random
import subprocess
import uuid
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_SESSIONS: Dict[str, Dict] = {}
_OUTPUT = Path("./data/deepfake/inject")
_OUTPUT.mkdir(parents=True, exist_ok=True)

_TARGETS = {
    "zoom": {
        "name": "Zoom",
        "protocol": "WebRTC + proprietary",
        "injection_method": "v4l2_virtual_cam",
        "voice_inject": "pulse_audio_virtual",
        "detection_risk": "LOW",
        "notes": "Sélectionner 'OBS Virtual Camera' dans paramètres vidéo",
    },
    "teams": {
        "name": "Microsoft Teams",
        "protocol": "WebRTC",
        "injection_method": "v4l2_virtual_cam",
        "voice_inject": "pulse_audio_virtual",
        "detection_risk": "LOW",
        "notes": "Teams accepte V4L2 loopback comme webcam",
    },
    "meet": {
        "name": "Google Meet",
        "protocol": "WebRTC",
        "injection_method": "v4l2_virtual_cam",
        "voice_inject": "pulse_audio_virtual",
        "detection_risk": "LOW",
        "notes": "Chrome reconnaît /dev/video20 comme caméra",
    },
    "webex": {
        "name": "Cisco Webex",
        "protocol": "WebRTC",
        "injection_method": "v4l2_virtual_cam",
        "voice_inject": "pulse_audio_virtual",
        "detection_risk": "MEDIUM",
        "notes": "Webex peut valider le driver — utiliser OBS plugin",
    },
    "rtsp_stream": {
        "name": "RTSP Stream Hijack",
        "protocol": "RTSP/RTP",
        "injection_method": "ffmpeg_rtsp_inject",
        "voice_inject": "rtp_audio_replace",
        "detection_risk": "MEDIUM",
        "notes": "Requiert MITM ou accès au serveur RTSP",
    },
    "webrtc_hijack": {
        "name": "WebRTC ICE Candidate Hijack",
        "protocol": "WebRTC/DTLS",
        "injection_method": "ice_candidate_poisoning",
        "voice_inject": "dtls_media_replace",
        "detection_risk": "HIGH",
        "notes": "Requiert MITM sur signaling server",
    },
}


def _v4l2_available() -> bool:
    return (
        os.path.exists("/dev/video20")
        or os.path.exists("/sys/module/v4l2loopback")
        or os.path.exists("/dev/video0")
    )


def _obs_available() -> bool:
    return os.path.exists("/usr/bin/obs") or os.path.exists("/usr/local/bin/obs")


def _ffmpeg_available() -> bool:
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


class LiveInjectService:
    """Injection flux vidéo deepfake en temps réel dans appels vidéo."""

    def setup_v4l2_loopback(self, device_num: int = 20,
                              label: str = "Deepfake Camera") -> Dict:
        """Configurer périphérique V4L2 loopback comme caméra virtuelle."""
        session_id = str(uuid.uuid4())
        device = f"/dev/video{device_num}"

        real_v4l2 = _v4l2_available()
        cmd_output = None

        if real_v4l2:
            try:
                r = subprocess.run(
                    ["modprobe", "v4l2loopback",
                     f"devices=1", f"video_nr={device_num}",
                     f"card_label={label}", "exclusive_caps=1"],
                    capture_output=True, text=True, timeout=10
                )
                cmd_output = r.stdout + r.stderr
                success = r.returncode == 0
            except Exception as e:
                cmd_output = str(e)
                success = False
        else:
            success = False

        result = {
            "session_id": session_id,
            "device": device,
            "label": label,
            "v4l2_loaded": success,
            "module": "v4l2loopback",
            "cmd_output": cmd_output,
            "simulated": not success,
            "next_step": f"ffmpeg -re -i source.mp4 -f v4l2 {device}",
        }
        _SESSIONS[session_id] = result
        return result

    def inject_video_stream(self, source: str,
                             target_device: str = "/dev/video20",
                             fps: int = 25,
                             loop: bool = True) -> Dict:
        """Injecter flux vidéo (deepfake) dans périphérique V4L2."""
        session_id = str(uuid.uuid4())
        has_ffmpeg = _ffmpeg_available()
        has_v4l2 = os.path.exists(target_device)

        cmd = [
            "ffmpeg", "-re", "-stream_loop", "-1" if loop else "0",
            "-i", source,
            "-vf", f"fps={fps}",
            "-f", "v4l2", target_device
        ]
        pid = None

        if has_ffmpeg and has_v4l2:
            try:
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                pid = proc.pid
            except Exception as e:
                logger.warning(f"inject_video_stream: {e}")

        result = {
            "session_id": session_id,
            "source": source,
            "target_device": target_device,
            "fps": fps,
            "loop": loop,
            "pid": pid,
            "status": "injecting" if pid else "simulated",
            "cmd": " ".join(cmd),
            "simulated": pid is None,
        }
        _SESSIONS[session_id] = result
        return result

    def inject_audio_pulse(self, audio_source: str,
                            sink_name: str = "deepfake_mic") -> Dict:
        """Injecter audio deepfake dans microphone virtuel PulseAudio."""
        session_id = str(uuid.uuid4())
        has_pulse = os.path.exists("/usr/bin/pactl") or os.path.exists("/usr/bin/pacmd")

        module_idx = None
        if has_pulse:
            try:
                r = subprocess.run(
                    ["pactl", "load-module", "module-null-sink",
                     f"sink_name={sink_name}", "sink_properties=device.description=DeepfakeMic"],
                    capture_output=True, text=True, timeout=5
                )
                if r.returncode == 0:
                    module_idx = r.stdout.strip()
            except Exception:
                pass

        return {
            "session_id": session_id,
            "audio_source": audio_source,
            "sink_name": sink_name,
            "module_index": module_idx,
            "status": "active" if module_idx else "simulated",
            "use_as_mic": f"pactl load-module module-loopback source={sink_name}.monitor sink=@DEFAULT_SINK@",
            "simulated": module_idx is None,
        }

    def start_call_injection(self, target_app: str = "zoom",
                              video_source: str = "/dev/video20",
                              audio_source: str = "deepfake_mic",
                              face_swap_active: bool = True,
                              lipsync_active: bool = True) -> Dict:
        """Orchestrer injection complète dans appel vidéo cible."""
        session_id = str(uuid.uuid4())
        app = _TARGETS.get(target_app, _TARGETS["zoom"])

        return {
            "session_id": session_id,
            "target": app["name"],
            "injection_method": app["injection_method"],
            "video_source": video_source,
            "audio_source": audio_source,
            "face_swap_active": face_swap_active,
            "lipsync_active": lipsync_active,
            "detection_risk": app["detection_risk"],
            "setup_notes": app["notes"],
            "pipeline": [
                "1. Webcam → FaceSwap (roop/ghost) → V4L2 loopback",
                "2. Microphone → VoiceClone (XTTS/RVC) → PulseAudio virtual sink",
                "3. LipSync (MuseTalk) → synchronise lèvres avatar avec audio cloné",
                f"4. Ouvrir {app['name']} → sélectionner caméra virtuelle + micro virtuel",
            ],
            "status": "ready",
            "simulated": True,
        }

    def rtsp_hijack(self, rtsp_url: str,
                     replacement_video: str,
                     mitm_mode: str = "arp_spoof") -> Dict:
        """Hijack flux RTSP et remplacer par vidéo deepfake."""
        session_id = str(uuid.uuid4())
        return {
            "session_id": session_id,
            "original_rtsp": rtsp_url,
            "replacement_video": replacement_video,
            "mitm_mode": mitm_mode,
            "attack_chain": [
                f"ARP spoof → RTSP proxy intercept → replace RTP payload with deepfake"
            ],
            "latency_added_ms": random.randint(20, 80),
            "detection_risk": "MEDIUM",
            "success": random.random() > 0.25,
            "simulated": True,
        }

    def list_targets(self) -> List[Dict]:
        return [{"id": k, **v} for k, v in _TARGETS.items()]

    def get_session(self, session_id: str) -> Dict:
        return _SESSIONS.get(session_id, {"error": "not found"})
