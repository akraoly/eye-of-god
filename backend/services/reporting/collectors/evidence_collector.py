"""
EvidenceCollector — collecte les preuves depuis la base de données
pour un rapport d'audit complet.
"""
from __future__ import annotations

import logging
from datetime import datetime

log = logging.getLogger(__name__)


class EvidenceCollector:
    """Collecte toutes les preuves disponibles pour une campagne donnée."""

    async def collect_all(self, campaign_id: str, db) -> dict:
        """Retourne un dict avec toutes les sections du rapport."""
        return {
            "campaign_id": campaign_id,
            "generated_at": datetime.utcnow().isoformat(),
            "screenshots": await self.collect_screenshots(campaign_id, db),
            "audio_recordings": await self.collect_audio_recordings(campaign_id, db),
            "camera_snapshots": await self.collect_camera_snapshots(campaign_id, db),
            "keystrokes": await self.collect_keystrokes(campaign_id, db),
            "captured_forms": await self.collect_captured_forms(campaign_id, db),
            "network_captures": await self.collect_network_captures(campaign_id, db),
            "ble_devices": await self.collect_ble_devices(campaign_id, db),
            "rfid_cards": await self.collect_rfid_cards(campaign_id, db),
            "sdr_recordings": await self.collect_sdr_recordings(campaign_id, db),
            "mitre_stats": await self.collect_mitre_stats(campaign_id, db),
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _dt(val) -> str | None:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val.isoformat()
        return str(val)

    # ── Collecteurs ───────────────────────────────────────────────────────────

    async def collect_screenshots(self, campaign_id: str, db) -> list[dict]:
        """Collecte les captures d'écran liées à la session/campagne."""
        try:
            from database.models import CapturedForm
            # Les screenshots sont liés aux formulaires capturés (screenshot_before/after)
            forms = (
                db.query(CapturedForm)
                .filter(CapturedForm.session_id == campaign_id)
                .order_by(CapturedForm.captured_at.desc())
                .all()
            )
            screenshots = []
            for f in forms:
                if f.screenshot_before:
                    screenshots.append({
                        "file_path": f.screenshot_before,
                        "source": "form_capture_before",
                        "session_id": f.session_id,
                        "target_id": f.target_id,
                        "captured_at": self._dt(f.captured_at),
                    })
                if f.screenshot_after:
                    screenshots.append({
                        "file_path": f.screenshot_after,
                        "source": "form_capture_after",
                        "session_id": f.session_id,
                        "target_id": f.target_id,
                        "captured_at": self._dt(f.captured_at),
                    })
            return screenshots
        except Exception as e:
            log.warning("collect_screenshots error: %s", e)
            return []

    async def collect_audio_recordings(self, campaign_id: str, db) -> list[dict]:
        """Collecte les enregistrements audio."""
        try:
            from database.models import AudioRecording
            records = (
                db.query(AudioRecording)
                .filter(AudioRecording.session_id == campaign_id)
                .order_by(AudioRecording.created_at.desc())
                .all()
            )
            return [
                {
                    "recording_id": r.recording_id,
                    "session_id": r.session_id,
                    "target_id": r.target_id,
                    "mic_name": r.mic_name,
                    "duration": r.duration,
                    "file_path": r.file_path,
                    "file_size": r.file_size,
                    "format": r.format,
                    "keyword": r.keyword,
                    "analyzed": r.analyzed,
                    "created_at": self._dt(r.created_at),
                }
                for r in records
            ]
        except Exception as e:
            log.warning("collect_audio_recordings error: %s", e)
            return []

    async def collect_camera_snapshots(self, campaign_id: str, db) -> list[dict]:
        """Collecte les snapshots caméras IP."""
        try:
            from database.models import CameraSnapshot
            snapshots = (
                db.query(CameraSnapshot)
                .order_by(CameraSnapshot.taken_at.desc())
                .limit(100)
                .all()
            )
            return [
                {
                    "snapshot_id": s.snapshot_id,
                    "camera_id": s.camera_id,
                    "file_path": s.file_path,
                    "taken_at": self._dt(s.taken_at),
                }
                for s in snapshots
            ]
        except Exception as e:
            log.warning("collect_camera_snapshots error: %s", e)
            return []

    async def collect_keystrokes(self, campaign_id: str, db) -> list[dict]:
        """Collecte les logs de frappes clavier."""
        try:
            from database.models import KeystrokeLog
            logs = (
                db.query(KeystrokeLog)
                .filter(KeystrokeLog.session_id == campaign_id)
                .order_by(KeystrokeLog.captured_at.desc())
                .limit(200)
                .all()
            )
            return [
                {
                    "log_id": k.log_id,
                    "session_id": k.session_id,
                    "target_id": k.target_id,
                    "keystrokes": (k.keystrokes or "")[:500],  # tronqué pour le rapport
                    "window_title": k.window_title,
                    "app_name": k.app_name,
                    "captured_at": self._dt(k.captured_at),
                    "is_processed": k.is_processed,
                }
                for k in logs
            ]
        except Exception as e:
            log.warning("collect_keystrokes error: %s", e)
            return []

    async def collect_captured_forms(self, campaign_id: str, db) -> list[dict]:
        """Collecte les formulaires capturés (identifiants, mots de passe, etc.)."""
        try:
            from database.models import CapturedForm
            forms = (
                db.query(CapturedForm)
                .filter(CapturedForm.session_id == campaign_id)
                .order_by(CapturedForm.captured_at.desc())
                .all()
            )
            return [
                {
                    "form_id": f.form_id,
                    "session_id": f.session_id,
                    "target_id": f.target_id,
                    "url": f.url,
                    "form_data": f.form_data or {},
                    "captured_at": self._dt(f.captured_at),
                }
                for f in forms
            ]
        except Exception as e:
            log.warning("collect_captured_forms error: %s", e)
            return []

    async def collect_network_captures(self, campaign_id: str, db) -> list[dict]:
        """Collecte les captures réseau (PacketCapture)."""
        try:
            from database.models import PacketCapture
            captures = (
                db.query(PacketCapture)
                .order_by(PacketCapture.started_at.desc())
                .limit(50)
                .all()
            )
            return [
                {
                    "capture_id": c.capture_id,
                    "interface": c.interface,
                    "bpf_filter": c.bpf_filter,
                    "status": c.status,
                    "packet_count": c.packet_count,
                    "pcap_file_path": c.pcap_file_path,
                    "file_size": c.file_size,
                    "creds_found": c.creds_found,
                    "started_at": self._dt(c.started_at),
                    "stopped_at": self._dt(c.stopped_at),
                }
                for c in captures
            ]
        except Exception as e:
            log.warning("collect_network_captures error: %s", e)
            return []

    async def collect_ble_devices(self, campaign_id: str, db) -> list[dict]:
        """Collecte les appareils BLE découverts."""
        try:
            from database.models_ble import BLEDevice
            devices = (
                db.query(BLEDevice)
                .order_by(BLEDevice.last_seen.desc())
                .limit(100)
                .all()
            )
            return [
                {
                    "ble_id": d.ble_id,
                    "mac_address": d.mac_address,
                    "name": d.name,
                    "rssi": d.rssi,
                    "manufacturer": d.manufacturer,
                    "device_type": d.device_type,
                    "is_tracker": d.is_tracker,
                    "tracker_type": d.tracker_type,
                    "vulns": d.vulns or [],
                    "first_seen": self._dt(d.first_seen),
                    "last_seen": self._dt(d.last_seen),
                }
                for d in devices
            ]
        except Exception as e:
            log.warning("collect_ble_devices error: %s", e)
            return []

    async def collect_rfid_cards(self, campaign_id: str, db) -> list[dict]:
        """Collecte les cartes RFID capturées (table dynamique)."""
        try:
            from sqlalchemy import text
            result = db.execute(
                text("SELECT * FROM rfid_captures ORDER BY captured_at DESC LIMIT 100")
            )
            rows = result.mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            log.warning("collect_rfid_cards error (table may not exist): %s", e)
            return []

    async def collect_sdr_recordings(self, campaign_id: str, db) -> list[dict]:
        """Collecte les enregistrements SDR."""
        try:
            from database.models_sdr import SDRRecording
            recordings = (
                db.query(SDRRecording)
                .order_by(SDRRecording.created_at.desc())
                .limit(50)
                .all()
            )
            return [
                {
                    "recording_id": r.recording_id,
                    "frequency_mhz": r.frequency_mhz,
                    "sample_rate": r.sample_rate,
                    "modulation": r.modulation,
                    "duration": r.duration,
                    "file_path": r.file_path,
                    "file_size": r.file_size,
                    "protocol": r.protocol,
                    "decoded_content": r.decoded_content or [],
                    "replay_count": r.replay_count,
                    "simulated": r.simulated,
                    "created_at": self._dt(r.created_at),
                }
                for r in recordings
            ]
        except Exception as e:
            log.warning("collect_sdr_recordings error: %s", e)
            return []

    async def collect_mitre_stats(self, campaign_id: str, db) -> dict:
        """Collecte les statistiques MITRE ATT&CK pour la campagne."""
        try:
            from database.models_mitre import MitreEvent, MitreCampaignStats

            # Stats globales de campagne
            stats = (
                db.query(MitreCampaignStats)
                .filter(MitreCampaignStats.campaign_id == campaign_id)
                .first()
            )

            # Événements individuels
            events = (
                db.query(MitreEvent)
                .filter(MitreEvent.campaign_id == campaign_id)
                .order_by(MitreEvent.timestamp.desc())
                .limit(200)
                .all()
            )

            events_list = [
                {
                    "event_id": e.event_id,
                    "action_type": e.action_type,
                    "technique_id": e.technique_id,
                    "tactic_id": e.tactic_id,
                    "score": e.score,
                    "success": e.success,
                    "details": e.details or {},
                    "timestamp": self._dt(e.timestamp),
                }
                for e in events
            ]

            if stats:
                return {
                    "campaign_id": campaign_id,
                    "total_techniques": stats.total_techniques,
                    "total_tactics": stats.total_tactics,
                    "total_score": stats.total_score,
                    "coverage": stats.coverage,
                    "attack_graph": stats.attack_graph or {},
                    "heatmap": stats.heatmap or [],
                    "completed_phases": stats.completed_phases or [],
                    "events": events_list,
                    "updated_at": self._dt(stats.updated_at),
                }
            else:
                # Pas de stats agrégées — on calcule à la volée
                techniques = set(e["technique_id"] for e in events_list)
                tactics = set(e["tactic_id"] for e in events_list)
                return {
                    "campaign_id": campaign_id,
                    "total_techniques": len(techniques),
                    "total_tactics": len(tactics),
                    "total_score": sum(e["score"] for e in events_list),
                    "coverage": 0.0,
                    "attack_graph": {},
                    "heatmap": [],
                    "completed_phases": [],
                    "events": events_list,
                    "updated_at": datetime.utcnow().isoformat(),
                }
        except Exception as e:
            log.warning("collect_mitre_stats error: %s", e)
            return {
                "campaign_id": campaign_id,
                "total_techniques": 0,
                "total_tactics": 0,
                "total_score": 0,
                "coverage": 0.0,
                "attack_graph": {},
                "heatmap": [],
                "completed_phases": [],
                "events": [],
                "updated_at": datetime.utcnow().isoformat(),
            }
