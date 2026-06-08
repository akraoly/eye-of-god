"""DB models — Blocs 11/12/13: EW, Surveillance Stratégique, Neutralisation"""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime
from sqlalchemy.sql import func
from database.base import Base


class EWJammingSession(Base):
    __tablename__ = "ew_jamming_sessions"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(String(64), unique=True, index=True)
    jam_type      = Column(String(30))  # freq|band|sweep|protocol
    frequency_hz  = Column(Float)
    band_name     = Column(String(50))
    waveform      = Column(String(30))
    power_dbm     = Column(Float)
    is_simulation = Column(Boolean, default=True)
    started_at    = Column(DateTime, server_default=func.now())
    stopped_at    = Column(DateTime, nullable=True)


class EWWifiTarget(Base):
    __tablename__ = "ew_wifi_targets"
    id          = Column(Integer, primary_key=True)
    bssid       = Column(String(20))
    ssid        = Column(String(100))
    channel     = Column(Integer)
    attack_type = Column(String(50))  # deauth|evil_twin|beacon_flood|pmkid
    status      = Column(String(20), default="active")
    created_at  = Column(DateTime, server_default=func.now())


class EWBtTarget(Base):
    __tablename__ = "ew_bt_targets"
    id          = Column(Integer, primary_key=True)
    bd_addr     = Column(String(20))
    device_name = Column(String(100))
    attack_type = Column(String(50))
    created_at  = Column(DateTime, server_default=func.now())


class DroneContact(Base):
    __tablename__ = "drone_contacts"
    id            = Column(Integer, primary_key=True)
    contact_id    = Column(String(64), unique=True, index=True)
    model         = Column(String(100))
    lat           = Column(Float)
    lon           = Column(Float)
    altitude_m    = Column(Float)
    freq_mhz      = Column(Float)
    action        = Column(String(50))  # detect|track|jam|hijack
    is_simulation = Column(Boolean, default=True)
    detected_at   = Column(DateTime, server_default=func.now())


class RadarEmission(Base):
    __tablename__ = "radar_emissions"
    id            = Column(Integer, primary_key=True)
    radar_id      = Column(String(64), unique=True, index=True)
    radar_type    = Column(String(50))
    freq_ghz      = Column(Float)
    threat_level  = Column(String(20))
    bearing_deg   = Column(Float)
    distance_km   = Column(Float)
    is_simulation = Column(Boolean, default=True)
    detected_at   = Column(DateTime, server_default=func.now())


class AircraftContact(Base):
    __tablename__ = "aircraft_contacts"
    id            = Column(Integer, primary_key=True)
    icao24        = Column(String(10), index=True)
    callsign      = Column(String(20))
    aircraft_type = Column(String(50))
    lat           = Column(Float)
    lon           = Column(Float)
    altitude_ft   = Column(Integer)
    speed_kts     = Column(Integer)
    military_flag = Column(Boolean, default=False)
    is_simulation = Column(Boolean, default=True)
    first_seen    = Column(DateTime, server_default=func.now())


class MaritimeVessel(Base):
    __tablename__ = "maritime_vessels"
    id            = Column(Integer, primary_key=True)
    mmsi          = Column(Integer, index=True)
    vessel_name   = Column(String(100))
    vessel_type   = Column(Integer)
    flag_country  = Column(String(50))
    lat           = Column(Float)
    lon           = Column(Float)
    speed_kts     = Column(Float)
    military_flag = Column(Boolean, default=False)
    is_simulation = Column(Boolean, default=True)
    first_seen    = Column(DateTime, server_default=func.now())


class SigintCapture(Base):
    __tablename__ = "sigint_captures"
    id            = Column(Integer, primary_key=True)
    capture_id    = Column(String(64), unique=True, index=True)
    frequency_mhz = Column(Float)
    modulation    = Column(String(30))
    bandwidth_khz = Column(Float)
    snr_db        = Column(Float)
    is_simulation = Column(Boolean, default=True)
    captured_at   = Column(DateTime, server_default=func.now())


class SatellitePass(Base):
    __tablename__ = "satellite_passes"
    id              = Column(Integer, primary_key=True)
    pass_id         = Column(String(64), unique=True, index=True)
    satellite_name  = Column(String(100))
    observer_lat    = Column(Float)
    observer_lon    = Column(Float)
    passes_count    = Column(Integer)
    next_pass_time  = Column(String(50))
    is_simulation   = Column(Boolean, default=True)
    computed_at     = Column(DateTime, server_default=func.now())


class ScadaSession(Base):
    __tablename__ = "scada_sessions"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(String(64), unique=True, index=True)
    target_ip     = Column(String(45))
    protocol      = Column(String(50))
    attack_type   = Column(String(100))
    sector        = Column(String(50))
    is_simulation = Column(Boolean, default=True)
    executed_at   = Column(DateTime, server_default=func.now())


class MilProtocolSession(Base):
    __tablename__ = "mil_protocol_sessions"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(String(64), unique=True, index=True)
    protocol      = Column(String(50))
    attack_type   = Column(String(100))
    is_simulation = Column(Boolean, default=True)
    executed_at   = Column(DateTime, server_default=func.now())


class NetworkAttack(Base):
    __tablename__ = "network_attacks_log"
    id            = Column(Integer, primary_key=True)
    session_id    = Column(String(64), unique=True, index=True)
    attack_type   = Column(String(50))
    target        = Column(String(200))
    is_simulation = Column(Boolean, default=True)
    executed_at   = Column(DateTime, server_default=func.now())


class MissileEngagement(Base):
    __tablename__ = "missile_engagements"
    id              = Column(Integer, primary_key=True)
    engagement_id   = Column(String(64), unique=True, index=True)
    track_id        = Column(String(64))
    sam_system      = Column(String(50))
    threat_type     = Column(String(50))
    intercept_success = Column(Boolean)
    pk_salvo        = Column(Float)
    is_simulation   = Column(Boolean, default=True)
    executed_at     = Column(DateTime, server_default=func.now())
