import hashlib
import secrets
from core.tools.logger import get_logger

logger = get_logger(__name__)


class SecurityTools:
    def generate_token(self, length: int = 32) -> str:
        return secrets.token_hex(length)

    def hash_password(self, password: str, salt: str = None) -> dict:
        salt = salt or secrets.token_hex(16)
        hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return {"hash": hashed, "salt": salt}

    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return secrets.compare_digest(check, hashed)

    def audit_log(self, action: str, details: str = ""):
        logger.info(f"[AUDIT] {action} | {details}")


security = SecurityTools()
