"""
Fernet symmetric encryption utility — L'Œil de Dieu.

Key resolution order:
  1. Environment variable FERNET_KEY
  2. ./data/.fernet_key file (auto-generated on first run)
"""
from __future__ import annotations

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_KEY_FILE = Path("./data/.fernet_key")
_fernet_instance = None


def _load_or_create_key() -> bytes:
    """Load Fernet key from env or file; generate and persist if missing."""
    # 1. Environment variable
    env_key = os.environ.get("FERNET_KEY", "").strip()
    if env_key:
        return env_key.encode()

    # 2. Key file
    try:
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if _KEY_FILE.exists():
            key = _KEY_FILE.read_bytes().strip()
            if key:
                return key
    except Exception as exc:
        logger.warning("fernet_enc: cannot read key file: %s", exc)

    # 3. Generate a new key and persist it
    try:
        from cryptography.fernet import Fernet as _Fernet
        key = _Fernet.generate_key()
        _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        _KEY_FILE.write_bytes(key)
        _KEY_FILE.chmod(0o600)
        logger.info("fernet_enc: new Fernet key generated and saved to %s", _KEY_FILE)
        return key
    except Exception as exc:
        logger.error("fernet_enc: cannot generate Fernet key: %s", exc)
        # Last-resort fallback — deterministic but insecure; warns loudly
        from cryptography.fernet import Fernet as _Fernet
        fallback = _Fernet.generate_key()
        logger.warning(
            "fernet_enc: using ephemeral key — encrypted data will NOT survive restarts!"
        )
        return fallback


def _get_fernet():
    """Return a cached Fernet instance, initializing on first call."""
    global _fernet_instance
    if _fernet_instance is None:
        try:
            from cryptography.fernet import Fernet as _Fernet
            key = _load_or_create_key()
            _fernet_instance = _Fernet(key)
        except ImportError:
            logger.error(
                "fernet_enc: 'cryptography' package not installed. "
                "Install it with: pip install cryptography"
            )
            _fernet_instance = None
    return _fernet_instance


def encrypt(text: str) -> str:
    """Encrypt a plaintext string and return a URL-safe base64 token."""
    f = _get_fernet()
    if f is None:
        # Graceful degradation: return prefixed plaintext so callers know
        logger.warning("fernet_enc: encryption unavailable — storing plaintext (UNSAFE)")
        return f"PLAINTEXT:{text}"
    return f.encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(token: str) -> str:
    """Decrypt a Fernet token and return the original plaintext."""
    if token.startswith("PLAINTEXT:"):
        return token[len("PLAINTEXT:"):]
    f = _get_fernet()
    if f is None:
        raise RuntimeError("fernet_enc: cannot decrypt — cryptography package unavailable")
    from cryptography.fernet import InvalidToken
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("fernet_enc: invalid or tampered ciphertext") from exc
