import hashlib
import uuid
from datetime import datetime


def generate_session_id() -> str:
    return str(uuid.uuid4())


def truncate(text: str, max_length: int = 500) -> str:
    return text if len(text) <= max_length else text[:max_length] + "..."


def now_iso() -> str:
    return datetime.utcnow().isoformat()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
