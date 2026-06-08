"""
SQLAlchemy models — WiFi module.
"""
from database.models import Base
from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Text, Float
from datetime import datetime
import uuid as _uuid


class WifiNetwork(Base):
    __tablename__ = "wifi_networks"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    wifi_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    bssid         = Column(String(17), unique=True, index=True, nullable=False)
    ssid          = Column(String(200), nullable=True)
    hidden        = Column(Boolean, default=False)
    channel       = Column(Integer, nullable=True)
    frequency     = Column(Float, nullable=True)      # GHz
    signal        = Column(Integer, default=-70)       # dBm
    quality       = Column(Integer, default=0)         # 0-100
    encryption    = Column(String(50), default="WPA2") # WEP/WPA/WPA2/WPA3/OPN
    cipher        = Column(String(50), nullable=True)  # CCMP/TKIP
    auth          = Column(String(50), nullable=True)  # PSK/MGT
    wps_enabled   = Column(Boolean, default=False)
    wps_locked    = Column(Boolean, default=False)
    vendor        = Column(String(100), nullable=True)
    capabilities  = Column(JSON, default=list)
    beacon_count  = Column(Integer, default=0)
    data_count    = Column(Integer, default=0)
    clients       = Column(JSON, default=list)         # liste MACs clients
    first_seen    = Column(DateTime, default=datetime.utcnow)
    last_seen     = Column(DateTime, default=datetime.utcnow)
    scan_id       = Column(String(36), nullable=True, index=True)
    simulated     = Column(Boolean, default=False)
    created_at    = Column(DateTime, default=datetime.utcnow)


class WifiClient(Base):
    __tablename__ = "wifi_clients"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    client_id     = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    mac           = Column(String(17), nullable=False, index=True)
    bssid         = Column(String(17), nullable=True, index=True)  # AP associé
    ssid          = Column(String(200), nullable=True)
    signal        = Column(Integer, default=-70)
    probed_ssids  = Column(JSON, default=list)
    vendor        = Column(String(100), nullable=True)
    first_seen    = Column(DateTime, default=datetime.utcnow)
    last_seen     = Column(DateTime, default=datetime.utcnow)
    created_at    = Column(DateTime, default=datetime.utcnow)


class WifiScan(Base):
    __tablename__ = "wifi_scans"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    scan_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    interface     = Column(String(20), nullable=True)
    duration      = Column(Integer, default=30)        # secondes
    channels      = Column(JSON, default=list)
    networks_found= Column(Integer, default=0)
    clients_found = Column(Integer, default=0)
    status        = Column(String(20), default="pending")  # pending/running/done/error
    started_at    = Column(DateTime, default=datetime.utcnow)
    finished_at   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class WifiHandshake(Base):
    __tablename__ = "wifi_handshakes"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    hs_id         = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    bssid         = Column(String(17), nullable=False, index=True)
    ssid          = Column(String(200), nullable=True)
    capture_type  = Column(String(20), default="handshake")  # handshake/pmkid
    cap_file      = Column(String(500), nullable=True)
    hccapx_file   = Column(String(500), nullable=True)
    captured_at   = Column(DateTime, default=datetime.utcnow)
    status        = Column(String(20), default="captured")   # captured/cracking/cracked/failed
    passphrase    = Column(String(500), nullable=True)
    cracked_at    = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class WifiCrackJob(Base):
    __tablename__ = "wifi_crack_jobs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    job_id        = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    bssid         = Column(String(17), nullable=False, index=True)
    ssid          = Column(String(200), nullable=True)
    hs_id         = Column(String(36), nullable=True)
    method        = Column(String(30), default="dictionary")  # dictionary/pmkid/wps/pixiedust
    wordlist      = Column(String(500), nullable=True)
    hashcat_mode  = Column(String(10), default="22000")
    status        = Column(String(20), default="queued")      # queued/running/done/failed
    progress      = Column(Integer, default=0)
    speed         = Column(String(50), nullable=True)         # H/s
    result        = Column(String(500), nullable=True)        # passphrase si cracké
    started_at    = Column(DateTime, nullable=True)
    finished_at   = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


class WifiConnection(Base):
    __tablename__ = "wifi_connections"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    conn_id       = Column(String(36), unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    bssid         = Column(String(17), nullable=False)
    ssid          = Column(String(200), nullable=True)
    passphrase    = Column(String(500), nullable=True)
    interface     = Column(String(20), nullable=True)
    local_ip      = Column(String(45), nullable=True)
    gateway       = Column(String(45), nullable=True)
    dns           = Column(JSON, default=list)
    status        = Column(String(20), default="connecting")  # connecting/connected/failed/disconnected
    hosts_found   = Column(JSON, default=list)
    connected_at  = Column(DateTime, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
