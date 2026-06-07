from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, Float, Enum, JSON, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base
from datetime import datetime
import uuid as _uuid
import uuid

Base = declarative_base()


class ScheduledTask(Base):
    """Tâche planifiée — shell, http_check, etc."""
    __tablename__ = "scheduled_tasks"

    id               = Column(String(36), primary_key=True, default=lambda: str(_uuid.uuid4()))
    name             = Column(String(255), nullable=False)
    description      = Column(Text, nullable=True)
    kind             = Column(String(30), default="shell")        # shell | http_check
    command          = Column(Text, nullable=True)                # pour kind=shell
    url              = Column(String(500), nullable=True)         # pour kind=http_check
    schedule_type    = Column(String(20), default="interval")     # interval | cron | once
    interval_seconds = Column(Integer, default=3600)
    cron             = Column(String(100), nullable=True)
    run_at           = Column(String(50), nullable=True)          # ISO datetime pour once
    enabled          = Column(Boolean, default=True)
    last_run         = Column(DateTime, nullable=True)
    run_count        = Column(Integer, default=0)
    created_at       = Column(DateTime, default=datetime.utcnow)


class AppUser(Base):
    """Utilisateur de l'application — auth locale."""
    __tablename__ = "app_users"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    username     = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(255), nullable=True)
    password_hash= Column(String(255), nullable=False)
    is_active    = Column(Boolean, default=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
    last_login   = Column(DateTime, nullable=True)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), index=True, default="default")
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    context_used = Column(Integer, default=0)


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_type = Column(String(20), nullable=False)  # 'user' | 'long'
    key = Column(String(200), nullable=False)
    value = Column(Text, nullable=False)
    importance = Column(Float, default=0.5)
    priority = Column(String(20), default="normal")  # critical|important|normal|archive
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (UniqueConstraint("memory_type", "key", name="uq_memory_type_key"),)


class EpisodicSession(Base):
    """Épisode mémoriel — une session de travail avec Mr Vitch."""
    __tablename__ = "episodic_sessions"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    session_id     = Column(String(100), nullable=False, unique=True, index=True)
    started_at     = Column(DateTime, default=datetime.utcnow, index=True)
    ended_at       = Column(DateTime, nullable=True)
    exchange_count = Column(Integer, default=0)
    goal           = Column(Text, nullable=True)
    summary        = Column(Text, nullable=True)
    files_touched  = Column(Text, nullable=True)   # JSON list
    key_commands   = Column(Text, nullable=True)   # JSON list
    topics         = Column(Text, nullable=True)   # JSON list
    is_summarized  = Column(Boolean, default=False)


class BashCommandLog(Base):
    """Commande bash indexée depuis l'historique shell."""
    __tablename__ = "bash_command_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    command    = Column(Text, nullable=False)
    cwd        = Column(String(500), nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, index=True)
    indexed    = Column(Boolean, default=False)


class UserProfile(Base):
    __tablename__ = "user_profile"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field = Column(String(200), nullable=False, unique=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)


# ── Nouvelles tables v2 ───────────────────────────────────────────────────────

class KnowledgeEntry(Base):
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general", index=True)
    source = Column(String(500), nullable=True)
    tags = Column(Text, nullable=True)           # JSON list as string
    importance = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LearningEvent(Base):
    __tablename__ = "learning_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    topic = Column(String(500), nullable=False)
    source_url = Column(String(1000), nullable=True)
    source_type = Column(String(50), nullable=False, default="text")  # text | url | file
    summary = Column(Text, nullable=True)
    content = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)           # JSON list as string
    importance = Column(Float, default=0.5)
    learned_at = Column(DateTime, default=datetime.utcnow)


class TerminalLog(Base):
    """Log d'exécution de commandes système — avec autorisation pour les commandes destructives."""
    __tablename__ = "terminal_logs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(String(36), nullable=False, unique=True, index=True)
    command    = Column(Text, nullable=False)
    stdout     = Column(Text, nullable=True)
    stderr     = Column(Text, nullable=True)
    exit_code  = Column(Integer, nullable=True)
    status     = Column(String(20), nullable=False, default="executed")  # executed | pending | approved | refused
    approved   = Column(Boolean, nullable=True)   # None=N/A, True=approuvée, False=refusée
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    executed_at= Column(DateTime, nullable=True)


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_name = Column(String(100), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    input_data = Column(Text, nullable=True)     # JSON string
    output_data = Column(Text, nullable=True)    # JSON string
    status = Column(String(20), nullable=False, default="success")  # success | error | skipped
    executed_at = Column(DateTime, default=datetime.utcnow, index=True)


class LifeGoal(Base):
    __tablename__ = "life_goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=False, default="general")
    status = Column(String(50), nullable=False, default="active")  # active | paused | done | abandoned
    priority = Column(Integer, default=3)        # 1=critical, 2=high, 3=medium, 4=low
    progress = Column(Integer, default=0)        # 0-100 %
    deadline = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class LifeHabit(Base):
    __tablename__ = "life_habits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(String(50), nullable=False, default="daily")  # daily | weekly | monthly
    streak = Column(Integer, default=0)
    last_done = Column(DateTime, nullable=True)
    active = Column(Integer, default=1)          # 1 = active, 0 = inactive
    created_at = Column(DateTime, default=datetime.utcnow)


# ── Tables SOC (Phase 1) ────────────────────────────────────────────────────

class Alert(Base):
    """Alerte de sécurité — portée depuis AEGIS AI."""
    __tablename__ = "soc_alerts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    alert_uuid    = Column(String(36), nullable=False, unique=True,
                           default=lambda: str(_uuid.uuid4()))
    timestamp     = Column(DateTime, default=datetime.utcnow, index=True)
    severity      = Column(String(10), nullable=False, index=True)   # LOW|MEDIUM|HIGH|CRITICAL
    category      = Column(String(50), nullable=False, index=True)   # PORT_SCAN|BRUTE_FORCE|…
    title         = Column(String(255), nullable=False)
    description   = Column(Text, nullable=True)
    source_ip     = Column(String(45), nullable=True, index=True)
    destination_ip= Column(String(45), nullable=True)
    affected_port = Column(Integer, nullable=True)
    protocol      = Column(String(10), nullable=True)
    raw_data      = Column(Text, nullable=True)                      # JSON string
    status        = Column(String(30), default="NEW", index=True)    # NEW|ACK|IN_PROGRESS|RESOLVED|FP
    mitre_tactic  = Column(String(10), nullable=True)               # TA0043…
    mitre_technique = Column(String(10), nullable=True)             # T1595…
    incident_id   = Column(Integer, nullable=True)
    source_engine = Column(String(50), default="manual")            # siem|ids|edr|manual
    created_at    = Column(DateTime, default=datetime.utcnow)


class Incident(Base):
    """Incident de sécurité."""
    __tablename__ = "soc_incidents"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    incident_uuid   = Column(String(36), nullable=False, unique=True,
                             default=lambda: str(_uuid.uuid4()))
    title           = Column(String(255), nullable=False)
    description     = Column(Text, nullable=True)
    severity        = Column(String(10), nullable=False, index=True)
    status          = Column(String(30), default="OPEN", index=True)  # OPEN|INVESTIGATING|CONTAINED|RESOLVED|CLOSED
    priority        = Column(Integer, default=3)                      # 1=critical → 4=low
    affected_systems= Column(Text, nullable=True)
    attack_vector   = Column(Text, nullable=True)
    impact_assessment=Column(Text, nullable=True)
    remediation_steps=Column(Text, nullable=True)
    resolution_notes= Column(Text, nullable=True)
    mitre_tactics   = Column(Text, nullable=True)                    # JSON list
    alert_ids       = Column(Text, nullable=True)                    # JSON list
    playbook_id     = Column(String(50), nullable=True)
    opened_at       = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at     = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow)


class SiemRule(Base):
    """Règle de corrélation SIEM (style Sigma)."""
    __tablename__ = "siem_rules"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    name         = Column(String(255), nullable=False, unique=True)
    description  = Column(Text, nullable=True)
    rule_type    = Column(String(30), nullable=False)               # THRESHOLD|SEQUENCE|AGGREGATION
    conditions   = Column(Text, nullable=False)                     # JSON config
    timewindow   = Column(Integer, default=300)                     # secondes
    threshold    = Column(Integer, default=1)
    severity     = Column(String(10), default="MEDIUM")
    category     = Column(String(50), default="OTHER")
    mitre_tactic = Column(String(10), nullable=True)
    mitre_technique = Column(String(10), nullable=True)
    enabled      = Column(Boolean, default=True)
    hit_count    = Column(Integer, default=0)
    last_hit     = Column(DateTime, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)


class SiemEvent(Base):
    """Événement ingéré par le SIEM."""
    __tablename__ = "siem_events"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    timestamp    = Column(DateTime, default=datetime.utcnow, index=True)
    event_type   = Column(String(50), nullable=False, index=True)   # PORT_SCAN|BRUTE_FORCE|…
    source       = Column(String(50), nullable=False)               # ids|edr|manual|agent
    src_ip       = Column(String(45), nullable=True, index=True)
    dst_ip       = Column(String(45), nullable=True)
    hostname     = Column(String(255), nullable=True)
    severity     = Column(String(10), default="LOW")
    data         = Column(Text, nullable=True)                      # JSON raw
    correlated   = Column(Boolean, default=False)
    alert_id     = Column(Integer, nullable=True)


# ── Tables SOC Phase 2 ──────────────────────────────────────────────────────

class MLAnomaly(Base):
    """Anomalie détectée par le moteur ML."""
    __tablename__ = "ml_anomalies"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String(20), nullable=False)      # alert | host
    entity_id   = Column(Integer, nullable=True)
    score       = Column(Float, nullable=False)           # 0-100
    severity    = Column(String(10), nullable=False)      # LOW|MEDIUM|HIGH|CRITICAL
    cluster_id  = Column(Integer, nullable=True)
    cluster_name= Column(String(100), nullable=True)
    explanation = Column(Text, nullable=True)
    features    = Column(Text, nullable=True)             # JSON array
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


class MLTrainingRun(Base):
    """Historique des entraînements ML."""
    __tablename__ = "ml_training_runs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    status        = Column(String(20), default="running")  # running|success|failed
    n_samples     = Column(Integer, default=0)
    n_anomalies   = Column(Integer, default=0)
    inertia       = Column(Float, nullable=True)
    silhouette    = Column(Float, nullable=True)
    duration_s    = Column(Float, nullable=True)
    error_msg     = Column(Text, nullable=True)
    triggered_by  = Column(String(30), default="auto")
    trained_at    = Column(DateTime, default=datetime.utcnow)


class EdrAgent(Base):
    """Agent EDR sur un endpoint."""
    __tablename__ = "edr_agents"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    hostname    = Column(String(255), nullable=False, index=True)
    ip_address  = Column(String(45), nullable=True)
    os          = Column(String(50), nullable=True)
    status      = Column(String(20), default="online")  # online|offline|compromised|isolated
    risk_score  = Column(Float, default=0.0)            # 0-100
    last_seen   = Column(DateTime, default=datetime.utcnow)
    first_seen  = Column(DateTime, default=datetime.utcnow)
    tags        = Column(Text, nullable=True)           # JSON list


class EdrEvent(Base):
    """Événement de sécurité EDR sur un endpoint."""
    __tablename__ = "edr_events"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    agent_id     = Column(Integer, nullable=True, index=True)
    hostname     = Column(String(255), nullable=True)
    event_type   = Column(String(50), nullable=False)   # PROCESS_CREATE|NETWORK_CONNECT|MALWARE_DETECT|…
    severity     = Column(String(10), default="LOW")
    process_name = Column(String(255), nullable=True)
    command_line = Column(Text, nullable=True)
    mitre_tactic = Column(String(10), nullable=True)
    mitre_tech   = Column(String(10), nullable=True)
    description  = Column(Text, nullable=True)
    raw_data     = Column(Text, nullable=True)
    alert_id     = Column(Integer, nullable=True)
    timestamp    = Column(DateTime, default=datetime.utcnow, index=True)


class NetworkFlow(Base):
    """Flux réseau analysé par le moteur NTA."""
    __tablename__ = "network_flows"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    src_ip       = Column(String(45), nullable=True, index=True)
    dst_ip       = Column(String(45), nullable=True)
    src_port     = Column(Integer, nullable=True)
    dst_port     = Column(Integer, nullable=True)
    protocol     = Column(String(10), nullable=True)
    bytes_out    = Column(Integer, default=0)
    bytes_in     = Column(Integer, default=0)
    packets      = Column(Integer, default=0)
    duration_s   = Column(Float, default=0.0)
    direction    = Column(String(10), default="out")    # in|out|lateral
    threat_type  = Column(String(30), nullable=True)    # C2|EXFIL|BEACONING|DNS_TUNNEL|…
    risk_score   = Column(Float, default=0.0)
    country      = Column(String(50), nullable=True)
    alert_id     = Column(Integer, nullable=True)
    detected_at  = Column(DateTime, default=datetime.utcnow, index=True)


class ThreatIOC(Base):
    """Indicateur de compromission (IOC)."""
    __tablename__ = "threat_iocs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ioc_type    = Column(String(20), nullable=False, index=True)  # IP|DOMAIN|HASH_MD5|HASH_SHA256|URL|CVE|EMAIL
    value       = Column(String(500), nullable=False, index=True)
    threat_type = Column(String(50), nullable=True)               # C2|BOTNET|RANSOMWARE|PHISHING|SCANNER|…
    severity    = Column(String(10), default="MEDIUM")
    confidence  = Column(Integer, default=70)                     # 0-100
    source      = Column(String(100), nullable=True)
    description = Column(Text, nullable=True)
    active      = Column(Boolean, default=True)
    first_seen  = Column(DateTime, default=datetime.utcnow)
    last_seen   = Column(DateTime, default=datetime.utcnow)
    hit_count   = Column(Integer, default=0)


class ThreatHit(Base):
    """Match IOC sur une alerte ou un flux."""
    __tablename__ = "threat_hits"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ioc_id      = Column(Integer, nullable=False)
    ioc_value   = Column(String(500), nullable=True)
    entity_type = Column(String(20), nullable=True)    # alert|flow|event
    entity_id   = Column(Integer, nullable=True)
    matched_at  = Column(DateTime, default=datetime.utcnow, index=True)


# ── Tables SOC Phase 3 ──────────────────────────────────────────────────────

class DlpIncident(Base):
    """Incident DLP — fuite de données détectée."""
    __tablename__ = "dlp_incidents"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    policy_name = Column(String(100), nullable=False)        # CREDIT_CARD, AWS_KEY, PII…
    severity    = Column(String(10), default="HIGH")
    channel     = Column(String(30), nullable=True)          # EMAIL, HTTP_UPLOAD, GIT_COMMIT…
    source      = Column(String(255), nullable=True)         # fichier, endpoint, user
    data_type   = Column(String(50), nullable=True)          # carte, IBAN, token, clé privée…
    match_count = Column(Integer, default=1)
    snippet     = Column(Text, nullable=True)                # extrait masqué
    status      = Column(String(20), default="OPEN")         # OPEN|REVIEWING|RESOLVED|FP
    mitre_tech  = Column(String(15), nullable=True)
    alert_id    = Column(Integer, nullable=True)
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)


class RansomwareDetection(Base):
    """Détection d'activité ransomware."""
    __tablename__ = "ransomware_detections"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    family       = Column(String(50), nullable=True)          # LockBit 3.0, BlackCat/ALPHV…
    threat_level = Column(String(10), default="CRITICAL")
    detection_type= Column(String(30), nullable=False)        # CANARY_TRIGGER|BEHAVIORAL|IOC_MATCH|SIGNATURE
    hostname     = Column(String(255), nullable=True)
    affected_files= Column(Integer, default=0)
    extension    = Column(String(20), nullable=True)          # .lockbit, .alphv…
    ransom_note  = Column(String(100), nullable=True)
    indicators   = Column(Text, nullable=True)               # JSON list
    techniques   = Column(Text, nullable=True)               # JSON list MITRE
    status       = Column(String(20), default="ACTIVE")      # ACTIVE|CONTAINED|REMEDIATED
    alert_id     = Column(Integer, nullable=True)
    detected_at  = Column(DateTime, default=datetime.utcnow, index=True)


class PhishingEmail(Base):
    """Email analysé pour phishing/BEC."""
    __tablename__ = "phishing_emails"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    sender       = Column(String(255), nullable=True)
    sender_domain= Column(String(255), nullable=True)
    subject      = Column(String(500), nullable=True)
    recipient    = Column(String(255), nullable=True)
    risk_score   = Column(Float, default=0.0)                # 0-100
    verdict      = Column(String(20), default="CLEAN")       # CLEAN|SUSPICIOUS|PHISHING|BEC|MALWARE
    indicators   = Column(Text, nullable=True)               # JSON list des indicateurs déclenchés
    spf          = Column(String(10), nullable=True)         # PASS|FAIL|SOFTFAIL|NONE
    dkim         = Column(String(10), nullable=True)         # PASS|FAIL|NONE
    dmarc        = Column(String(10), nullable=True)         # PASS|FAIL|NONE
    urls         = Column(Text, nullable=True)               # JSON list d'URLs extraites
    attachments  = Column(Text, nullable=True)               # JSON list de pièces jointes
    campaign_id  = Column(String(50), nullable=True)
    alert_id     = Column(Integer, nullable=True)
    analyzed_at  = Column(DateTime, default=datetime.utcnow, index=True)


class OsintActor(Base):
    """Acteur de menace / groupe APT."""
    __tablename__ = "osint_actors"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    name              = Column(String(100), nullable=False, unique=True)
    aliases           = Column(Text, nullable=True)          # JSON list
    country           = Column(String(50), nullable=True)
    sponsor           = Column(String(20), nullable=True)    # STATE|CRIMINAL|HACKTIVISM|UNKNOWN
    motivation        = Column(Text, nullable=True)          # JSON list
    threat_level      = Column(String(10), default="HIGH")
    sophistication    = Column(String(20), default="INTERMEDIATE")
    is_active         = Column(Boolean, default=True)
    active_since      = Column(String(10), nullable=True)
    target_sectors    = Column(Text, nullable=True)          # JSON list
    target_countries  = Column(Text, nullable=True)          # JSON list
    primary_ttps      = Column(Text, nullable=True)          # JSON list MITRE
    description       = Column(Text, nullable=True)
    source            = Column(String(100), default="MITRE ATT&CK")


class OsintInvestigation(Base):
    """Investigation OSINT sur un IOC."""
    __tablename__ = "osint_investigations"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    target        = Column(String(500), nullable=False)      # IP, domaine, email, hash
    target_type   = Column(String(20), nullable=False)       # IP|DOMAIN|EMAIL|HASH|ORG
    reputation    = Column(Integer, default=50)              # 0=malveillant, 100=propre
    verdict       = Column(String(20), default="UNKNOWN")    # CLEAN|SUSPICIOUS|MALICIOUS|UNKNOWN
    sources       = Column(Text, nullable=True)              # JSON {source: résultat}
    related_actors= Column(Text, nullable=True)              # JSON list d'acteurs liés
    related_iocs  = Column(Text, nullable=True)              # JSON list d'IOCs liés
    notes         = Column(Text, nullable=True)
    investigated_at= Column(DateTime, default=datetime.utcnow, index=True)


# ── Tables SOC Phase 4 ──────────────────────────────────────────────────────

class IamAccount(Base):
    """Compte IAM — utilisateur, service, admin, partagé."""
    __tablename__ = "iam_accounts"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    username        = Column(String(100), nullable=False, unique=True)
    display_name    = Column(String(255), nullable=True)
    email           = Column(String(255), nullable=True)
    department      = Column(String(100), nullable=True)
    job_title       = Column(String(100), nullable=True)
    account_type    = Column(String(20), default="USER")       # USER|ADMIN|SERVICE|SHARED
    is_privileged   = Column(Boolean, default=False)
    is_admin        = Column(Boolean, default=False)
    privilege_level = Column(String(30), default="STANDARD")   # STANDARD|PRIVILEGED|SUPER_ADMIN
    groups          = Column(Text, nullable=True)              # JSON list
    mfa_enabled     = Column(Boolean, default=False)
    mfa_type        = Column(String(20), nullable=True)        # TOTP|FIDO2|SMS|NONE
    password_age_days = Column(Integer, default=0)
    failed_logins   = Column(Integer, default=0)
    is_locked       = Column(Boolean, default=False)
    is_dormant      = Column(Boolean, default=False)
    risk_score      = Column(Float, default=0.0)
    risk_reasons    = Column(Text, nullable=True)              # JSON list
    status          = Column(String(20), default="ACTIVE")     # ACTIVE|DISABLED|LOCKED
    source_system   = Column(String(50), default="manual")
    last_login_ip   = Column(String(45), nullable=True)
    last_login_at   = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, default=datetime.utcnow)
    updated_at      = Column(DateTime, default=datetime.utcnow)


class ComplianceControl(Base):
    """Contrôle de conformité — état vérifié ou non."""
    __tablename__ = "compliance_controls"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    control_id  = Column(String(20), nullable=False, unique=True)  # AC-1, AL-2…
    category    = Column(String(50), nullable=False)
    severity    = Column(String(10), default="MEDIUM")
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    requirement = Column(Text, nullable=True)
    status      = Column(String(20), default="NOT_ASSESSED")   # PASS|FAIL|PARTIAL|NOT_ASSESSED
    score       = Column(Integer, default=0)                   # 0-100
    evidence    = Column(Text, nullable=True)
    remediation = Column(Text, nullable=True)
    last_checked= Column(DateTime, nullable=True)


class ComplianceAssessment(Base):
    """Évaluation de conformité globale."""
    __tablename__ = "compliance_assessments"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    framework      = Column(String(100), default="AEGIS Security Baseline")
    total_controls = Column(Integer, default=0)
    passed         = Column(Integer, default=0)
    failed         = Column(Integer, default=0)
    partial        = Column(Integer, default=0)
    score_pct      = Column(Float, default=0.0)
    notes          = Column(Text, nullable=True)
    assessed_at    = Column(DateTime, default=datetime.utcnow, index=True)


class ZeroTrustPolicy(Base):
    """Politique Zero Trust / NAC."""
    __tablename__ = "zt_policies"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    action      = Column(String(20), default="DENY")           # ALLOW|DENY|MFA_REQUIRED|AUDIT
    conditions  = Column(Text, nullable=True)                  # JSON: {ip_range, user_groups, time_window, …}
    priority    = Column(Integer, default=100)
    enabled     = Column(Boolean, default=True)
    hit_count   = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow)


class ZeroTrustSession(Base):
    """Session d'accès Zero Trust évaluée."""
    __tablename__ = "zt_sessions"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    user         = Column(String(100), nullable=False, index=True)
    source_ip    = Column(String(45), nullable=True)
    resource     = Column(String(255), nullable=True)
    device_id    = Column(String(100), nullable=True)
    trust_score  = Column(Float, default=50.0)                 # 0-100
    decision     = Column(String(20), default="PENDING")       # ALLOW|DENY|MFA|AUDIT
    policy_id    = Column(Integer, nullable=True)
    mfa_verified = Column(Boolean, default=False)
    risk_factors = Column(Text, nullable=True)                 # JSON list
    status       = Column(String(20), default="ACTIVE")        # ACTIVE|EXPIRED|REVOKED
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at   = Column(DateTime, nullable=True)


class ZeroTrustAccessLog(Base):
    """Journal des décisions d'accès Zero Trust."""
    __tablename__ = "zt_access_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    user        = Column(String(100), nullable=False, index=True)
    source_ip   = Column(String(45), nullable=True)
    resource    = Column(String(255), nullable=True)
    decision    = Column(String(20), nullable=False)
    reason      = Column(Text, nullable=True)
    trust_score = Column(Float, nullable=True)
    policy_id   = Column(Integer, nullable=True)
    session_id  = Column(Integer, nullable=True)
    logged_at   = Column(DateTime, default=datetime.utcnow, index=True)


class SsoProvider(Base):
    """Configuration provider SSO — OAuth2/OIDC/SAML."""
    __tablename__ = "sso_providers"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    name           = Column(String(100), nullable=False, unique=True)
    provider_type  = Column(String(20), nullable=False)        # oauth2_google|oauth2_azure|oauth2_github|saml|oidc
    client_id      = Column(String(500), nullable=True)
    client_secret  = Column(String(500), nullable=True)        # stocké chiffré en prod
    tenant_id      = Column(String(100), nullable=True)        # Azure AD
    issuer_url     = Column(String(500), nullable=True)
    enabled        = Column(Boolean, default=False)
    user_count     = Column(Integer, default=0)
    last_sync      = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)


# ── Threat Hunting ──────────────────────────────────────────────────────────

class ThreatHunt(Base):
    """Campagne de Threat Hunting."""
    __tablename__ = "threat_hunts"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    hypothesis     = Column(Text, nullable=False)               # "L'attaquant utilise C2 via DNS"
    query_type     = Column(String(20), nullable=False)         # IOC|BEHAVIOR|NETWORK|USER|CUSTOM
    query_value    = Column(String(500), nullable=True)         # IP, hash, pattern…
    status         = Column(String(20), default="PENDING")      # PENDING|RUNNING|COMPLETED|FAILED
    verdict        = Column(String(20), nullable=True)          # CONFIRMED|LIKELY|UNLIKELY|BENIGN|UNKNOWN
    confidence     = Column(Float, default=0.0)                 # 0-100
    findings_count = Column(Integer, default=0)
    ai_analysis    = Column(JSON, nullable=True)                # rapport Claude
    duration_sec   = Column(Integer, nullable=True)
    started_at     = Column(DateTime, nullable=True)
    finished_at    = Column(DateTime, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)


class HuntFinding(Base):
    """Indicateur individuel trouvé lors d'une chasse."""
    __tablename__ = "hunt_findings"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    hunt_id     = Column(Integer, nullable=False, index=True)
    severity    = Column(String(10), default="MEDIUM")          # CRITICAL|HIGH|MEDIUM|LOW|INFO
    source      = Column(String(30), nullable=True)             # alerts|intel|network|edr|nta
    category    = Column(String(50), nullable=True)
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    evidence    = Column(Text, nullable=True)
    ioc_type    = Column(String(20), nullable=True)             # IP|DOMAIN|HASH|PATTERN|HOST
    ioc_value   = Column(String(500), nullable=True)
    host        = Column(String(255), nullable=True)
    found_at    = Column(DateTime, default=datetime.utcnow, index=True)


# ── User Behavior Analytics ─────────────────────────────────────────────────

class UBAEventLog(Base):
    """Journal d'activité utilisateur — source principale du moteur UBA."""
    __tablename__ = "uba_events"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    username   = Column(String(100), nullable=False, index=True)
    user_id    = Column(String(50), nullable=True, index=True)
    action     = Column(String(100), nullable=False)            # LOGIN|LOGOUT|READ|WRITE|DELETE|ADMIN|EXPORT…
    resource   = Column(String(255), nullable=True)
    method     = Column(String(10), nullable=True)              # GET|POST|PUT|DELETE
    ip_address = Column(String(45), nullable=True, index=True)
    success    = Column(Boolean, default=True)
    details    = Column(JSON, nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, index=True)


class UBAAnomaly(Base):
    """Anomalie comportementale détectée sur un utilisateur."""
    __tablename__ = "uba_anomalies"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    anomaly_uuid = Column(String(36), nullable=False, unique=True,
                          default=lambda: str(uuid.uuid4()))
    user_id      = Column(String(50), nullable=True, index=True)
    username     = Column(String(100), nullable=True, index=True)
    anomaly_type = Column(String(30), nullable=False, index=True)   # ODD_HOUR_LOGIN|HIGH_VELOCITY|NEW_IP|…
    severity     = Column(String(10), default="MEDIUM", index=True)
    score        = Column(Float, default=0.0)                       # 0-100
    description  = Column(Text, nullable=True)
    details      = Column(JSON, nullable=True)
    source_ip    = Column(String(45), nullable=True)
    status       = Column(String(20), default="OPEN", index=True)   # OPEN|INVESTIGATING|FALSE_POSITIVE|CONFIRMED
    alert_created= Column(Boolean, default=False)
    detected_at  = Column(DateTime, default=datetime.utcnow, index=True)


class UBAProfile(Base):
    """Profil comportemental de référence par utilisateur."""
    __tablename__ = "uba_profiles"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(String(50), nullable=False, unique=True, index=True)
    username      = Column(String(100), nullable=True)
    risk_score    = Column(Float, default=0.0)                      # 0-100
    total_events  = Column(Integer, default=0)
    failed_logins = Column(Integer, default=0)
    known_ips     = Column(JSON, nullable=True)                     # liste des IPs connues
    usual_hours   = Column(JSON, nullable=True)                     # distribution horaire {heure: count}
    last_seen     = Column(DateTime, nullable=True)
    last_ip       = Column(String(45), nullable=True)
    anomaly_count = Column(Integer, default=0)
    is_high_risk  = Column(Boolean, default=False, index=True)
    created_at    = Column(DateTime, default=datetime.utcnow)


# ── MODULE 2 — Pentest Jobs ──────────────────────────────────────────────────

class PentestJob(Base):
    """Job de pentest autonome — lancé par AutoPentestAgent."""
    __tablename__ = "pentest_jobs"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(String(20), nullable=False, unique=True, index=True)
    target     = Column(String(255), nullable=False, index=True)
    status     = Column(String(20), default="pending", index=True)   # pending|running|completed|failed|stopped
    notes      = Column(Text, nullable=True)
    summary    = Column(Text, nullable=True)   # JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow)


class PentestStep(Base):
    """Étape d'un job de pentest."""
    __tablename__ = "pentest_steps"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(String(20), nullable=False, index=True)
    name        = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    status      = Column(String(20), default="pending")   # pending|running|done|error|skipped
    output      = Column(Text, nullable=True)
    data        = Column(Text, nullable=True)   # JSON
    duration    = Column(Float, default=0.0)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── MODULE 3 — Mémoire Tactique ──────────────────────────────────────────────

class TacticalOperation(Base):
    """Opération indexée dans la mémoire tactique — pour contexte historique."""
    __tablename__ = "tactical_operations"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    job_id     = Column(String(20), nullable=True, index=True)
    target     = Column(String(255), nullable=False, index=True)
    ports      = Column(Text, nullable=True)   # JSON list
    services   = Column(Text, nullable=True)   # JSON dict
    cves       = Column(Text, nullable=True)   # JSON list
    summary    = Column(Text, nullable=True)   # JSON complet
    created_at = Column(DateTime, default=datetime.utcnow, index=True)


# ══════════════════════════════════════════════════════════════════════════════
# MODULES 5-20 — Nouvelles tables
# ══════════════════════════════════════════════════════════════════════════════

# ── MODULE 5 — Exploit Generation ────────────────────────────────────────────

class ExploitGenJob(Base):
    __tablename__ = "exploit_gen_jobs"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    job_type    = Column(String(30), nullable=False)
    status      = Column(String(20), default="pending", index=True)
    platform    = Column(String(20), nullable=True)
    arch        = Column(String(10), nullable=True)
    payload     = Column(String(200), nullable=True)
    format      = Column(String(20), nullable=True)
    lhost       = Column(String(100), nullable=True)
    lport       = Column(Integer, nullable=True)
    encoder     = Column(String(100), nullable=True)
    output_path = Column(String(500), nullable=True)
    result      = Column(Text, nullable=True)
    error       = Column(Text, nullable=True)
    celery_task = Column(String(36), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at  = Column(DateTime, default=datetime.utcnow)


# ── MODULE 6 — Implant Beacons ────────────────────────────────────────────────

class ImplantBeacon(Base):
    __tablename__ = "implant_beacons"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    beacon_id   = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    hostname    = Column(String(255), nullable=False, index=True)
    ip          = Column(String(45), nullable=True, index=True)
    os_type     = Column(String(50), nullable=True)
    arch        = Column(String(10), nullable=True)
    privilege   = Column(String(30), nullable=True)
    protocol    = Column(String(20), nullable=True)
    status      = Column(String(20), default="active", index=True)
    last_seen   = Column(DateTime, nullable=True, index=True)
    first_seen  = Column(DateTime, default=datetime.utcnow)
    c2_host     = Column(String(255), nullable=True)
    c2_port     = Column(Integer, nullable=True)
    tags        = Column(JSON, nullable=True)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── MODULE 7 — OSINT Jobs ─────────────────────────────────────────────────────

class OsintJob(Base):
    __tablename__ = "osint_jobs"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    job_id      = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    target      = Column(String(500), nullable=False, index=True)
    status      = Column(String(20), default="pending", index=True)
    results     = Column(JSON, nullable=True)
    celery_task = Column(String(36), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at  = Column(DateTime, default=datetime.utcnow)


# ── MODULE 9 — Cracked Credentials ───────────────────────────────────────────

class CrackedCredential(Base):
    __tablename__ = "cracked_credentials"
    id           = Column(Integer, primary_key=True, autoincrement=True)
    cred_id      = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    target       = Column(String(255), nullable=False, index=True)
    username     = Column(String(255), nullable=False, index=True)
    password_enc = Column(Text, nullable=True)
    hash_value   = Column(String(512), nullable=True)
    hash_type    = Column(String(50), nullable=True)
    source       = Column(String(50), nullable=True)
    cracked_at   = Column(DateTime, default=datetime.utcnow, index=True)
    is_valid     = Column(Boolean, default=False)


# ── MODULE 11 — Generated Reports ────────────────────────────────────────────

class GeneratedReport(Base):
    __tablename__ = "generated_reports"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    report_id   = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    report_type = Column(String(50), nullable=False)
    title       = Column(String(500), nullable=False)
    target      = Column(String(255), nullable=True)
    filename    = Column(String(255), nullable=False)
    format      = Column(String(10), default="pdf")
    file_path   = Column(String(500), nullable=False)
    file_size   = Column(Integer, default=0)
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)


# ── MODULE 12 — Threat Intel Feeds ───────────────────────────────────────────

class ThreatFeedEntry(Base):
    __tablename__ = "threat_feed_entries"
    id                   = Column(Integer, primary_key=True, autoincrement=True)
    feed_id              = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    source               = Column(String(30), nullable=False, index=True)
    entry_type           = Column(String(20), nullable=False, index=True)
    identifier           = Column(String(100), nullable=False, index=True)
    title                = Column(String(255), nullable=True)
    description          = Column(Text, nullable=True)
    severity             = Column(String(20), nullable=True, index=True)
    cvss_score           = Column(Float, default=0.0)
    published_at         = Column(DateTime, nullable=True)
    fetched_at           = Column(DateTime, default=datetime.utcnow, index=True)
    affects_known_target = Column(Boolean, default=False, index=True)
    raw_data             = Column(Text, nullable=True)


class ThreatIntelJob(Base):
    __tablename__ = "threat_intel_jobs"
    id              = Column(Integer, primary_key=True, autoincrement=True)
    last_run        = Column(DateTime, default=datetime.utcnow, index=True)
    entries_fetched = Column(Integer, default=0)
    alerts_created  = Column(Integer, default=0)
    status          = Column(String(20), default="success")
    error_message   = Column(Text, nullable=True)


# ── MODULE 13 — Fuzzing ───────────────────────────────────────────────────────

class FuzzingJob(Base):
    __tablename__ = "fuzzing_jobs"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    job_id        = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    fuzzer_type   = Column(String(20), nullable=False, index=True)
    target        = Column(String(500), nullable=False)
    target_type   = Column(String(20), nullable=False)
    status        = Column(String(20), default="running", index=True)
    crashes_found = Column(Integer, default=0)
    hangs_found   = Column(Integer, default=0)
    execs_per_sec = Column(Float, default=0.0)
    total_paths   = Column(Integer, default=0)
    output_dir    = Column(String(500), nullable=True)
    crash_dir     = Column(String(500), nullable=True)
    started_at    = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at    = Column(DateTime, default=datetime.utcnow)
    stopped_at    = Column(DateTime, nullable=True)


# ── MODULE 14 — Reverse Engineering ──────────────────────────────────────────

class REAnalysis(Base):
    __tablename__ = "re_analyses"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id      = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    binary_name      = Column(String(255), nullable=False)
    binary_hash      = Column(String(64), nullable=True, index=True)
    file_type        = Column(String(30), nullable=True)
    arch             = Column(String(20), nullable=True)
    protections      = Column(Text, nullable=True)
    strings_count    = Column(Integer, default=0)
    functions_count  = Column(Integer, default=0)
    vulnerabilities  = Column(Text, nullable=True)
    claude_analysis  = Column(Text, nullable=True)
    ghidra_available = Column(Boolean, default=False)
    decompiled_path  = Column(String(500), nullable=True)
    status           = Column(String(20), default="pending", index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True)


# ── MODULE 15 — Virtual Lab ───────────────────────────────────────────────────

class LabInstance(Base):
    __tablename__ = "lab_instances"
    id            = Column(Integer, primary_key=True, autoincrement=True)
    lab_id        = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    template_name = Column(String(100), nullable=False, index=True)
    lab_name      = Column(String(255), nullable=True)
    container_id  = Column(String(100), nullable=True)
    network_id    = Column(String(100), nullable=True)
    target_ip     = Column(String(45), nullable=True)
    exposed_ports = Column(Text, nullable=True)
    status        = Column(String(20), default="running", index=True)
    created_at    = Column(DateTime, default=datetime.utcnow, index=True)
    last_activity = Column(DateTime, default=datetime.utcnow)


# ── MODULE 16 — Honeypots ─────────────────────────────────────────────────────

class HoneypotConfig(Base):
    __tablename__ = "honeypot_configs"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    honeypot_id    = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    port           = Column(Integer, nullable=False, index=True)
    service_type   = Column(String(30), nullable=False)
    fake_banner    = Column(Text, nullable=True)
    is_active      = Column(Boolean, default=True, index=True)
    captures_count = Column(Integer, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)


class HoneypotCapture(Base):
    __tablename__ = "honeypot_captures"
    id                 = Column(Integer, primary_key=True, autoincrement=True)
    capture_id         = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    honeypot_id        = Column(String(36), nullable=False, index=True)
    attacker_ip        = Column(String(45), nullable=False, index=True)
    attacker_port      = Column(Integer, nullable=True)
    timestamp          = Column(DateTime, default=datetime.utcnow, index=True)
    raw_data           = Column(Text, nullable=True)
    parsed_credentials = Column(Text, nullable=True)
    mitre_techniques   = Column(Text, nullable=True)
    severity           = Column(String(10), default="low", index=True)


# ── MODULE 17 — Forensics ─────────────────────────────────────────────────────

class ForensicsCase(Base):
    __tablename__ = "forensics_cases"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    case_id          = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    filename         = Column(String(255), nullable=False)
    file_hash        = Column(String(64), nullable=True, index=True)
    file_type        = Column(String(50), nullable=True)
    file_size        = Column(Integer, default=0)
    iocs             = Column(Text, nullable=True)
    analysis_results = Column(Text, nullable=True)
    sandbox_output   = Column(Text, nullable=True)
    is_malicious     = Column(Boolean, default=False, index=True)
    malware_family   = Column(String(100), nullable=True)
    stix_report      = Column(Text, nullable=True)
    status           = Column(String(20), default="pending", index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True)


# ── MODULE 18 — PrivEsc ───────────────────────────────────────────────────────

class PrivEscScan(Base):
    __tablename__ = "privesc_scans"
    id                = Column(Integer, primary_key=True, autoincrement=True)
    scan_id           = Column(String(36), nullable=False, unique=True, default=lambda: str(_uuid.uuid4()))
    target            = Column(String(255), nullable=True, index=True)
    os_type           = Column(String(20), nullable=False, index=True)
    findings          = Column(Text, nullable=True)
    high_risk_count   = Column(Integer, default=0)
    medium_risk_count = Column(Integer, default=0)
    auto_exploitable  = Column(Text, nullable=True)
    status            = Column(String(20), default="pending", index=True)
    created_at        = Column(DateTime, default=datetime.utcnow, index=True)


# ── MODULE 19 — Lateral Movement ─────────────────────────────────────────────

class LateralMovement(Base):
    __tablename__ = "lateral_movements"
    id               = Column(Integer, primary_key=True, autoincrement=True)
    op_id            = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    operation_type   = Column(String(50), nullable=False, index=True)
    source_host      = Column(String(255), nullable=True)
    target_host      = Column(String(255), nullable=False, index=True)
    technique        = Column(String(20), nullable=True)
    credentials_used = Column(Text, nullable=True)
    result           = Column(Text, nullable=True)
    success          = Column(Boolean, default=False, index=True)
    created_at       = Column(DateTime, default=datetime.utcnow, index=True)


# ── MODULE 20 — Self-Improvement ──────────────────────────────────────────────

class OperationOutcome(Base):
    __tablename__ = "operation_outcomes"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    outcome_id     = Column(String(36), nullable=False, unique=True, index=True, default=lambda: str(_uuid.uuid4()))
    operation_type = Column(String(50), nullable=False, index=True)
    target_profile = Column(Text, nullable=True)
    technique      = Column(String(200), nullable=False)
    success        = Column(Boolean, default=False, index=True)
    context        = Column(Text, nullable=True)
    reason         = Column(Text, nullable=True)
    tags           = Column(Text, nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)


class TechniqueLearning(Base):
    __tablename__ = "technique_learnings"
    id             = Column(Integer, primary_key=True, autoincrement=True)
    technique_id   = Column(String(50), nullable=False, unique=True, index=True)
    technique_name = Column(String(300), nullable=False)
    category       = Column(String(100), nullable=False, default="unknown", index=True)
    success_rate   = Column(Float, default=0.0, index=True)
    success_count  = Column(Integer, default=0)
    failure_count  = Column(Integer, default=0)
    last_used      = Column(DateTime, nullable=True, index=True)
    contexts       = Column(Text, nullable=True)
    notes          = Column(Text, nullable=True)
    source_url     = Column(String(500), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# CAPACITÉS 1-7 — 10 nouveaux modèles
# ══════════════════════════════════════════════════════════════════════════════

import uuid as _uuid

# ── Capacité 1 — Audio Capture ───────────────────────────────────────────────

class AudioRecording(Base):
    """Audio recording captured from a target microphone via implant or local mic."""
    __tablename__ = "audio_recordings"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    recording_id = Column(String(36), nullable=False, unique=True, index=True,
                          default=lambda: str(_uuid.uuid4()))
    session_id   = Column(String(100), nullable=True, index=True)
    target_id    = Column(String(100), nullable=True, index=True)
    mic_name     = Column(String(255), nullable=True)
    duration     = Column(Integer, default=0)
    file_path    = Column(String(500), nullable=True)
    file_size    = Column(Integer, default=0)
    format       = Column(String(10), default="wav")
    keyword      = Column(String(255), nullable=True)
    analyzed     = Column(Boolean, default=False)
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)


# ── Capacité 2 — IP Camera Scanner ──────────────────────────────────────────

class Camera(Base):
    """Discovered IP camera — ONVIF / RTSP / HTTP."""
    __tablename__ = "cameras"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    camera_id     = Column(String(36), nullable=False, unique=True, index=True,
                           default=lambda: str(_uuid.uuid4()))
    ip            = Column(String(45), nullable=False, index=True)
    port          = Column(Integer, default=80)
    model         = Column(String(255), nullable=True)
    firmware      = Column(String(255), nullable=True)
    manufacturer  = Column(String(100), nullable=True, index=True)
    username      = Column(String(100), nullable=True)
    password_enc  = Column(Text, nullable=True)
    rtsp_url      = Column(String(500), nullable=True)
    http_url      = Column(String(500), nullable=True)
    has_mic       = Column(Boolean, default=False)
    has_ptz       = Column(Boolean, default=False)
    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_seen     = Column(DateTime, nullable=True)
    status        = Column(String(20), default="unknown", index=True)
    vulns         = Column(Text, nullable=True)
    scan_job_id   = Column(String(36), nullable=True)


class CameraSnapshot(Base):
    """Snapshot captured from an IP camera."""
    __tablename__ = "camera_snapshots"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(36), nullable=False, unique=True, index=True,
                         default=lambda: str(_uuid.uuid4()))
    camera_id   = Column(String(36), nullable=True, index=True)
    file_path   = Column(String(500), nullable=True)
    taken_at    = Column(DateTime, default=datetime.utcnow, index=True)


# ── Capacité 3 — Post-Exploit (Keylogger, Clipboard, Forms) ─────────────────

class KeystrokeLog(Base):
    """Keystrokes captured via Meterpreter keyscan or local keylogger."""
    __tablename__ = "keystroke_logs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    log_id       = Column(String(36), nullable=False, unique=True, index=True,
                          default=lambda: str(_uuid.uuid4()))
    session_id   = Column(String(100), nullable=False, index=True)
    target_id    = Column(String(255), nullable=True, index=True)
    keystrokes   = Column(Text, nullable=True)
    window_title = Column(String(500), nullable=True)
    app_name     = Column(String(255), nullable=True)
    captured_at  = Column(DateTime, default=datetime.utcnow, index=True)
    is_processed = Column(Boolean, default=False)


class CapturedForm(Base):
    """Form submissions captured by the JavaScript form grabber."""
    __tablename__ = "captured_forms"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    form_id           = Column(String(36), nullable=False, unique=True, index=True,
                               default=lambda: str(_uuid.uuid4()))
    session_id        = Column(String(100), nullable=False, index=True)
    target_id         = Column(String(255), nullable=True, index=True)
    url               = Column(String(2000), nullable=True)
    form_data         = Column(JSON, nullable=True)
    screenshot_before = Column(String(500), nullable=True)
    screenshot_after  = Column(String(500), nullable=True)
    captured_at       = Column(DateTime, default=datetime.utcnow, index=True)


class ClipboardCapture(Base):
    """Clipboard content captured from a session."""
    __tablename__ = "clipboard_captures"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    capture_id   = Column(String(36), nullable=False, unique=True, index=True,
                          default=lambda: str(_uuid.uuid4()))
    session_id   = Column(String(100), nullable=False, index=True)
    content      = Column(Text, nullable=True)
    content_type = Column(String(20), default="text")
    size         = Column(Integer, default=0)
    captured_at  = Column(DateTime, default=datetime.utcnow, index=True)


# ── Capacité 4 — Network Sniffer ─────────────────────────────────────────────

class PacketCapture(Base):
    """Network packet capture session (tcpdump)."""
    __tablename__ = "packet_captures"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    capture_id     = Column(String(36), nullable=False, unique=True, index=True,
                            default=lambda: str(_uuid.uuid4()))
    interface      = Column(String(50), nullable=False)
    bpf_filter     = Column(String(500), nullable=True)
    status         = Column(String(20), default="running", index=True)
    packet_count   = Column(Integer, default=0)
    pcap_file_path = Column(String(500), nullable=True)
    file_size      = Column(Integer, default=0)
    creds_found    = Column(Integer, default=0)
    started_at     = Column(DateTime, default=datetime.utcnow, index=True)
    stopped_at     = Column(DateTime, nullable=True)


# ── Capacité 5 — Automation Triggers ─────────────────────────────────────────

class AutoTrigger(Base):
    """IF-THEN automation rule."""
    __tablename__ = "auto_triggers"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    trigger_id     = Column(String(36), nullable=False, unique=True, index=True,
                            default=lambda: str(_uuid.uuid4()))
    name           = Column(String(255), nullable=False)
    condition_type = Column(String(50), nullable=False, index=True)
    condition      = Column(JSON, nullable=False)
    action_type    = Column(String(50), nullable=False, index=True)
    action         = Column(JSON, nullable=False)
    enabled        = Column(Boolean, default=True, index=True)
    last_triggered = Column(DateTime, nullable=True)
    trigger_count  = Column(Integer, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow, index=True)


class TriggerLog(Base):
    """Execution log for an automation trigger."""
    __tablename__ = "trigger_logs"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    log_id        = Column(String(36), nullable=False, unique=True, index=True,
                           default=lambda: str(_uuid.uuid4()))
    trigger_id    = Column(String(36), nullable=False, index=True)
    event_data    = Column(JSON, nullable=True)
    action_result = Column(JSON, nullable=True)
    success       = Column(Boolean, default=False)
    triggered_at  = Column(DateTime, default=datetime.utcnow, index=True)


# ── Capacité 6 — Exfiltration ────────────────────────────────────────────────

class ExfilJob(Base):
    """Data exfiltration job — tracks status and telemetry."""
    __tablename__ = "exfil_jobs"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    exfil_id     = Column(String(36), nullable=False, unique=True, index=True,
                          default=lambda: str(_uuid.uuid4()))
    channel      = Column(String(30), nullable=False, index=True)
    status       = Column(String(20), default="pending", index=True)
    data_size    = Column(Integer, default=0)
    chunks_total = Column(Integer, default=0)
    chunks_sent  = Column(Integer, default=0)
    encrypted    = Column(Boolean, default=False)
    compressed   = Column(Boolean, default=False)
    scheduled_at = Column(DateTime, nullable=True)
    started_at   = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    checksum     = Column(String(64), nullable=True)
    error_msg    = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)


# ══════════════════════════════════════════════════════════════════════════════
# MODULE SENTINEL — Surveillance système temps réel
# ══════════════════════════════════════════════════════════════════════════════

class SystemMetricHistory(Base):
    """Historique des métriques système — collecté toutes les 30s."""
    __tablename__ = "system_metric_history"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    timestamp     = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_pct       = Column(Float, default=0.0)
    ram_pct       = Column(Float, default=0.0)
    disk_pct      = Column(Float, default=0.0)
    swap_pct      = Column(Float, default=0.0)
    cpu_temp      = Column(Float, nullable=True)
    net_sent_mb   = Column(Float, default=0.0)
    net_recv_mb   = Column(Float, default=0.0)
    process_count = Column(Integer, default=0)
    open_ports    = Column(Integer, default=0)
    health_score  = Column(Integer, default=100)


class SecurityEventLog(Base):
    """Journal des événements de sécurité détectés par le daemon Sentinel."""
    __tablename__ = "security_event_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)
    category    = Column(String(50), nullable=False, index=True)
    # METRIC|PROCESS|NETWORK|FILE|PORT|LOG
    severity    = Column(String(10), default="INFO", index=True)
    # INFO|LOW|MEDIUM|HIGH|CRITICAL
    title       = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    details     = Column(Text, nullable=True)   # JSON
    source      = Column(String(50), default="sentinel")
    resolved    = Column(Boolean, default=False)


class MonitorBaseline(Base):
    """Baseline de référence pour la comparaison (processus, ports, fichiers)."""
    __tablename__ = "monitor_baseline"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    baseline_type  = Column(String(30), nullable=False, unique=True, index=True)
    # processes | ports | files
    data           = Column(Text, nullable=False)   # JSON
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow)


class CustomMonitorRule(Base):
    """Règle de surveillance personnalisée définie par Mr Vitch."""
    __tablename__ = "custom_monitor_rules"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    rule_id     = Column(String(36), nullable=False, unique=True, index=True,
                         default=lambda: str(_uuid.uuid4()))
    name        = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    rule_type   = Column(String(30), nullable=False)
    # watch_dir | watch_process | ignore_port | alert_metric | watch_service
    condition   = Column(Text, nullable=False)   # JSON
    action      = Column(String(20), default="alert")   # alert | ignore | restart
    enabled     = Column(Boolean, default=True, index=True)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ── BLOC 5 — AEGIS Renseignement Offensif ─────────────────────────────────────

class AegisCVE(Base):
    """CVE ingéré par AEGIS depuis NVD/CISA/ExploitDB."""
    __tablename__ = "aegis_cves"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    cve_id           = Column(String(30), nullable=False, unique=True, index=True)
    title            = Column(String(500), nullable=True)
    description      = Column(Text, nullable=True)
    cvss_score       = Column(Float, default=0.0, index=True)
    cvss_vector      = Column(String(200), nullable=True)
    severity         = Column(String(20), nullable=True, index=True)  # CRITICAL/HIGH/MEDIUM/LOW
    cwe_ids          = Column(Text, nullable=True)          # JSON list
    affected_products= Column(Text, nullable=True)          # JSON list
    references       = Column(Text, nullable=True)          # JSON list of URLs
    source           = Column(String(30), default="nvd", index=True)  # nvd|cisa|exploitdb
    published_at     = Column(DateTime, nullable=True, index=True)
    modified_at      = Column(DateTime, nullable=True)
    ingested_at      = Column(DateTime, default=datetime.utcnow, index=True)
    read             = Column(Boolean, default=False, index=True)
    starred          = Column(Boolean, default=False, index=True)
    has_exploit      = Column(Boolean, default=False, index=True)
    affects_project  = Column(Boolean, default=False, index=True)  # corrélation projets
    alert_sent       = Column(Boolean, default=False)
    status           = Column(String(20), default="new", index=True)  # new|analyzed|exploited|mitigated|archived
    ai_summary       = Column(Text, nullable=True)   # résumé Claude 2 phrases
    notes            = Column(Text, nullable=True)   # notes Mr Vitch


class AegisExploit(Base):
    """Exploit public surveillé depuis GitHub."""
    __tablename__ = "aegis_exploits"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    exploit_id    = Column(String(36), nullable=False, unique=True,
                           default=lambda: str(_uuid.uuid4()))
    cve_id        = Column(String(30), nullable=True, index=True)
    repo_url      = Column(String(500), nullable=False, unique=True)
    repo_name     = Column(String(200), nullable=True)
    repo_owner    = Column(String(100), nullable=True)
    description   = Column(Text, nullable=True)
    tags          = Column(Text, nullable=True)          # JSON list (CVE, PoC, RCE…)
    language      = Column(String(50), nullable=True)
    stars         = Column(Integer, default=0)
    ai_analysis   = Column(Text, nullable=True)   # analyse Claude
    technique     = Column(String(200), nullable=True)  # vecteur d'attaque
    reliability   = Column(String(20), nullable=True)   # high|medium|low|unknown
    attack_vector = Column(String(50), nullable=True)   # NETWORK|LOCAL|PHYSICAL
    added_at      = Column(DateTime, default=datetime.utcnow, index=True)
    repo_created  = Column(DateTime, nullable=True)
    status        = Column(String(20), default="new")   # new|analyzed|tested|archived
    notes         = Column(Text, nullable=True)


class AegisTarget(Base):
    """Cible surveillée — pentest autorisé uniquement."""
    __tablename__ = "aegis_targets"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    target_id             = Column(String(36), nullable=False, unique=True,
                                   default=lambda: str(_uuid.uuid4()))
    name                  = Column(String(200), nullable=False)
    target_type           = Column(String(20), nullable=False, index=True)  # domain|ip|org
    target_value          = Column(String(500), nullable=False)
    authorization_confirmed = Column(Boolean, default=False, nullable=False)  # OBLIGATOIRE
    authorization_note    = Column(Text, nullable=True)   # référence du mandat
    notes                 = Column(Text, nullable=True)
    tags                  = Column(Text, nullable=True)   # JSON list
    created_at            = Column(DateTime, default=datetime.utcnow)
    last_checked          = Column(DateTime, nullable=True)
    # Résultats reconnaissance passive
    subdomains            = Column(Text, nullable=True)   # JSON list (crt.sh)
    technologies          = Column(Text, nullable=True)   # JSON list
    dns_records           = Column(Text, nullable=True)   # JSON dict
    whois_info            = Column(Text, nullable=True)
    findings              = Column(Text, nullable=True)   # JSON list de changements détectés
    active                = Column(Boolean, default=True, index=True)


class AegisIntelLog(Base):
    """Journal de renseignement opérationnel."""
    __tablename__ = "aegis_intel_log"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    entry_id    = Column(String(36), nullable=False, unique=True,
                         default=lambda: str(_uuid.uuid4()))
    entry_type  = Column(String(30), nullable=False, index=True)
    # cve_alert|exploit_found|target_change|attack_mapped|report|manual
    title       = Column(String(500), nullable=False)
    content     = Column(Text, nullable=True)
    cve_id      = Column(String(30), nullable=True, index=True)
    exploit_id  = Column(String(36), nullable=True)
    target_id   = Column(String(36), nullable=True)
    tags        = Column(Text, nullable=True)   # JSON list
    severity    = Column(String(20), nullable=True, index=True)
    status      = Column(String(20), default="new", index=True)
    # new|analyzing|tested|mitigated|archived
    notes       = Column(Text, nullable=True)   # annotations Mr Vitch
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)


class AegisATTACKMap(Base):
    """Matrice ATT&CK personnelle de Mr Vitch."""
    __tablename__ = "aegis_attack_map"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    technique_id   = Column(String(20), nullable=False, unique=True, index=True)  # T1059.001
    tactic         = Column(String(50), nullable=False, index=True)
    technique_name = Column(String(200), nullable=False)
    level          = Column(String(20), default="studied")  # studied|practiced|mastered
    source         = Column(String(50), nullable=True)  # ctf|pentest|lab|course
    cve_ids        = Column(Text, nullable=True)   # JSON list de CVE liés
    notes          = Column(Text, nullable=True)
    first_seen     = Column(DateTime, default=datetime.utcnow)
    last_updated   = Column(DateTime, default=datetime.utcnow)


class AegisReport(Base):
    """Rapport de veille généré par AEGIS (hebdomadaire ou à la demande)."""
    __tablename__ = "aegis_reports"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    report_id    = Column(String(36), nullable=False, unique=True,
                          default=lambda: str(_uuid.uuid4()))
    report_type  = Column(String(20), default="weekly")   # weekly|on_demand
    period_start = Column(DateTime, nullable=True)
    period_end   = Column(DateTime, nullable=True)
    title        = Column(String(300), nullable=True)
    content      = Column(Text, nullable=False)   # markdown
    stats        = Column(Text, nullable=True)    # JSON
    created_at   = Column(DateTime, default=datetime.utcnow, index=True)
