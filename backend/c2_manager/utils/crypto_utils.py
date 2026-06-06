"""Utilitaires crypto — mTLS, génération de certificats, HMAC."""
from __future__ import annotations

import ipaddress
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def generate_ca_bundle(
    ca_common_name: str = "C2Manager CA",
    out_dir: str | Path = "/tmp/c2_certs",
    valid_days: int = 365,
) -> dict[str, str]:
    """
    Génère une CA auto-signée + certificat client pour mTLS.
    Retourne les chemins des fichiers générés.
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError as exc:
        raise ImportError("pip install cryptography") from exc

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # ── CA key + cert ──────────────────────────────────────────────────────
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=4096)

    ca_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, ca_common_name),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "C2Manager"),
    ])
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # ── Client key + cert signé par la CA ─────────────────────────────────
    client_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    client_name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "c2manager-operator"),
    ])
    client_cert = (
        x509.CertificateBuilder()
        .subject_name(client_name)
        .issuer_name(ca_name)
        .public_key(client_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=valid_days))
        .add_extension(
            x509.ExtendedKeyUsage([x509.ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # ── Sauvegarder les fichiers ───────────────────────────────────────────
    paths: dict[str, str] = {}
    files = {
        "ca_key.pem":     ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ),
        "ca_cert.pem":    ca_cert.public_bytes(serialization.Encoding.PEM),
        "client_key.pem": client_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ),
        "client_cert.pem": client_cert.public_bytes(serialization.Encoding.PEM),
    }
    for fname, data in files.items():
        fpath = out_path / fname
        fpath.write_bytes(data)
        os.chmod(fpath, 0o600)
        paths[fname.replace(".pem", "").replace(".", "_")] = str(fpath)

    return paths


def sliver_config_from_certs(
    host: str,
    port: int,
    operator: str,
    ca_cert_path: str,
    client_cert_path: str,
    client_key_path: str,
) -> dict[str, Any]:
    """Construire un dict au format Sliver operator .cfg."""
    return {
        "operator":       operator,
        "lhost":          host,
        "lport":          port,
        "ca_certificate": Path(ca_cert_path).read_text(),
        "certificate":    Path(client_cert_path).read_text(),
        "private_key":    Path(client_key_path).read_text(),
        "token":          "",
    }


def hmac_sign(data: bytes, key: bytes) -> str:
    """HMAC-SHA256 pour signer des frames/tokens."""
    import hmac as _hmac
    import hashlib
    return _hmac.new(key, data, hashlib.sha256).hexdigest()


def hmac_verify(data: bytes, key: bytes, signature: str) -> bool:
    import hmac as _hmac
    import hashlib
    expected = _hmac.new(key, data, hashlib.sha256).hexdigest()
    return _hmac.compare_digest(expected, signature)
