import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from database.models import Base
from app.config import settings
import database.models_mitre  # noqa: F401 — register MITRE tables
import database.models_ble    # noqa: F401 — register BLE tables
import database.models_rfid      # noqa: F401 — register RFID tables
import database.models_sdr       # noqa: F401 — register SDR tables
import database.models_reporting # noqa: F401 — register Audit Report tables
import database.models_wifi      # noqa: F401 — register WiFi tables
import database.models_firmware      # noqa: F401 — register Firmware Implant tables
import database.models_mobile_zero  # noqa: F401 — register Mobile Zero-Click tables
import database.models_zeroday      # noqa: F401 — register Zero-Day Industriel tables
import database.models_airgap       # noqa: F401 — register Air-Gap Exploitation tables
import database.models_geoint       # noqa: F401 — register OSINT Géopolitique tables
import database.models_automation   # noqa: F401 — register Automation Stratégique tables
import database.models_quantum      # noqa: F401 — register Quantum & Cryptographie tables
import database.models_influence    # noqa: F401 — register Influence Stratégique tables

os.makedirs("./data", exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
