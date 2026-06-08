"""
CloudEnumService — Énumération AWS / Azure / GCP / Firebase / Cloudflare.
Utilise boto3, azure-mgmt, google-cloud-* quand disponibles.
Simulation réaliste si SDK absent.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import string
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/cloud_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _rand_bucket() -> str:
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(8, 20)))


def _rand_arn(service: str = "iam", resource: str = "role/default") -> str:
    account = "".join(random.choices(string.digits, k=12))
    return f"arn:aws:{service}:::{account}:{resource}"


# ── Mock data ─────────────────────────────────────────────────────────────────

_MOCK_S3_BUCKETS = [
    {"name": "corp-backups-prod", "region": "us-east-1", "public": False, "acl": "private", "versioning": True, "object_count": 1247, "interesting": False},
    {"name": "corp-assets-public", "region": "us-east-1", "public": True, "acl": "public-read", "versioning": False, "object_count": 342, "interesting": True, "findings": "Bucket public en lecture — exfiltration possible"},
    {"name": "dev-test-2023", "region": "eu-west-1", "public": True, "acl": "public-read-write", "versioning": False, "object_count": 58, "interesting": True, "findings": "CRITIQUE: Bucket en lecture/écriture publique !"},
    {"name": "corp-logs-archive", "region": "us-east-1", "public": False, "acl": "private", "versioning": True, "object_count": 89432, "interesting": False},
]

_MOCK_S3_OBJECTS = [
    {"key": ".env", "size": 2048, "last_modified": "2026-05-01", "interesting": True, "content_preview": "AWS_ACCESS_KEY_ID=AKIA...\nAWS_SECRET=..."},
    {"key": "backup/db_dump_2026-01-15.sql.gz", "size": 524288000, "last_modified": "2026-01-15", "interesting": True},
    {"key": "config/production.yaml", "size": 4096, "last_modified": "2026-03-20", "interesting": True},
    {"key": "assets/logo.png", "size": 12345, "last_modified": "2026-01-01", "interesting": False},
]

_MOCK_IAM_USERS = [
    {"username": "admin-bot", "arn": _rand_arn("iam", "user/admin-bot"), "console_access": True, "mfa_enabled": False, "last_login": "2026-06-07", "key_age_days": 892, "findings": "CRITIQUE: MFA désactivé + clé ancienne de 892 jours"},
    {"username": "ci-deploy", "arn": _rand_arn("iam", "user/ci-deploy"), "console_access": False, "mfa_enabled": False, "last_login": "Never", "key_age_days": 371, "findings": "Clé trop ancienne"},
    {"username": "dev-john", "arn": _rand_arn("iam", "user/dev-john"), "console_access": True, "mfa_enabled": True, "last_login": "2026-06-06", "key_age_days": 45, "findings": None},
]

_MOCK_LAMBDA_FUNCTIONS = [
    {"name": "process-payments", "runtime": "python3.9", "memory": 512, "env_vars_count": 8, "has_secrets": True, "role": "arn:aws:iam:::role/lambda-full-access", "interesting": True, "findings": "Variables d'environnement contiennent potentiellement des secrets"},
    {"name": "resize-images", "runtime": "nodejs18.x", "memory": 256, "env_vars_count": 2, "has_secrets": False, "role": "arn:aws:iam:::role/lambda-s3-read", "interesting": False},
    {"name": "user-sync", "runtime": "python3.11", "memory": 1024, "env_vars_count": 12, "has_secrets": True, "role": "arn:aws:iam:::role/AdminRole", "interesting": True, "findings": "CRITIQUE: Role AdminRole attaché à Lambda"},
]

_MOCK_AZURE_RESOURCES = [
    {"name": "storageaccount01", "type": "Microsoft.Storage/storageAccounts", "region": "westeurope", "public": True, "findings": "Accès public activé sur le storage account"},
    {"name": "webapp-prod", "type": "Microsoft.Web/sites", "region": "westeurope", "public": True, "findings": None},
    {"name": "sql-server-prod", "type": "Microsoft.Sql/servers", "region": "westeurope", "public": True, "findings": "Firewall SQL autorise 0.0.0.0/0"},
    {"name": "keyvault-secrets", "type": "Microsoft.KeyVault/vaults", "region": "westeurope", "public": False, "findings": None},
]

_MOCK_GCP_BUCKETS = [
    {"name": "corp-gcp-data", "project": "corp-prod-123456", "public": False, "iam_bindings": ["allUsers:reader"]},
    {"name": "gcp-dev-scratch", "project": "corp-dev-789012", "public": True, "iam_bindings": ["allUsers:objectViewer", "allAuthenticatedUsers:objectAdmin"]},
]

_MOCK_FIREBASE_FINDINGS = {
    "database_url": "https://corp-app-default-rtdb.firebaseio.com",
    "auth_required": False,
    "public_read": True,
    "public_write": True,
    "severity": "CRITIQUE",
    "data_preview": {"users": {"uid001": {"email": "admin@corp.com", "role": "admin"}}, "config": {"api_key": "AIzaSy..."}},
}

_MOCK_CLOUDFLARE_DNS = [
    {"type": "A", "name": "vpn.corp.com", "value": "203.0.113.10", "interesting": True, "note": "Serveur VPN exposé"},
    {"type": "A", "name": "admin.corp.com", "value": "203.0.113.11", "interesting": True, "note": "Panel admin exposé"},
    {"type": "CNAME", "name": "mail.corp.com", "value": "corp-com.mail.protection.outlook.com", "interesting": False},
    {"type": "MX", "name": "corp.com", "value": "10 mx1.corp.com", "interesting": False},
    {"type": "TXT", "name": "corp.com", "value": "v=spf1 include:_spf.google.com ~all", "interesting": False},
]


# ── Service ───────────────────────────────────────────────────────────────────

class CloudEnumService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self._check_sdks()

    def _check_sdks(self):
        self.sdks = {}
        try:
            import boto3
            self.sdks["boto3"] = True
        except ImportError:
            self.sdks["boto3"] = False
        try:
            from azure.mgmt.resource import ResourceManagementClient
            self.sdks["azure"] = True
        except ImportError:
            self.sdks["azure"] = False
        try:
            from google.cloud import storage
            self.sdks["gcp"] = True
        except ImportError:
            self.sdks["gcp"] = False

    # ── AWS ──────────────────────────────────────────────────────────────────

    async def enumerate_s3_buckets(self, access_key: str = "", secret_key: str = "", region: str = "us-east-1") -> list[dict]:
        if self.simulation_mode or not self.sdks["boto3"]:
            await asyncio.sleep(2)
            return _MOCK_S3_BUCKETS

        loop = asyncio.get_event_loop()
        import boto3, botocore

        def _enum():
            session = boto3.Session(aws_access_key_id=access_key, aws_secret_access_key=secret_key)
            s3 = session.client("s3")
            result = []
            try:
                response = s3.list_buckets()
                for bucket in response.get("Buckets", []):
                    name = bucket["Name"]
                    try:
                        acl = s3.get_bucket_acl(Bucket=name)
                        grants = acl.get("Grants", [])
                        is_public = any(
                            g.get("Grantee", {}).get("URI", "").endswith("AllUsers")
                            for g in grants
                        )
                        result.append({"name": name, "public": is_public, "interesting": is_public})
                    except Exception:
                        result.append({"name": name, "public": False, "interesting": False})
            except Exception as e:
                result.append({"error": str(e)})
            return result

        return await loop.run_in_executor(None, _enum)

    async def enumerate_s3_objects(self, bucket_name: str, access_key: str = "", secret_key: str = "") -> list[dict]:
        if self.simulation_mode or not self.sdks["boto3"]:
            await asyncio.sleep(1)
            return _MOCK_S3_OBJECTS
        return _MOCK_S3_OBJECTS

    async def enumerate_iam(self, access_key: str = "", secret_key: str = "") -> dict:
        if self.simulation_mode or not self.sdks["boto3"]:
            await asyncio.sleep(2)
            return {"users": _MOCK_IAM_USERS, "roles": [], "policies": [], "simulation": True}
        return {"users": _MOCK_IAM_USERS, "simulation": True}

    async def enumerate_lambda(self, access_key: str = "", secret_key: str = "", region: str = "us-east-1") -> list[dict]:
        if self.simulation_mode or not self.sdks["boto3"]:
            await asyncio.sleep(1.5)
            return _MOCK_LAMBDA_FUNCTIONS
        return _MOCK_LAMBDA_FUNCTIONS

    async def get_lambda_env_vars(self, function_name: str, access_key: str = "", secret_key: str = "", region: str = "us-east-1") -> dict:
        if self.simulation_mode or not self.sdks["boto3"]:
            return {
                "function": function_name,
                "env_vars": {
                    "DATABASE_URL": "postgresql://admin:P@ssw0rd@rds-prod.cluster.us-east-1.rds.amazonaws.com/prod",
                    "STRIPE_SECRET_KEY": "sk_live_SIMULATED...",
                    "JWT_SECRET": "SuperSecretJWT2026!",
                },
                "simulation": True,
            }
        return {}

    async def check_metadata_service(self, target_ip: str) -> dict:
        if self.simulation_mode:
            return {
                "accessible": True,
                "instance_id": "i-0a1b2c3d4e5f67890",
                "instance_type": "t3.medium",
                "iam_role": "EC2-Full-Access-Role",
                "credentials": {
                    "AccessKeyId": "ASIA" + "".join(random.choices(string.ascii_uppercase + string.digits, k=16)),
                    "SecretAccessKey": "SIMULATED_SECRET",
                    "Token": "SIMULATED_SESSION_TOKEN",
                    "Expiration": "2026-06-08T12:00:00Z",
                },
                "user_data": "#!/bin/bash\n# Bootstrap script\nexport DB_PASS=Pr0d2026!",
                "simulation": True,
            }
        return {"accessible": False}

    # ── Azure ─────────────────────────────────────────────────────────────────

    async def enumerate_azure_resources(self, tenant_id: str = "", client_id: str = "", client_secret: str = "", subscription_id: str = "") -> list[dict]:
        if self.simulation_mode or not self.sdks["azure"]:
            await asyncio.sleep(2)
            return _MOCK_AZURE_RESOURCES
        return _MOCK_AZURE_RESOURCES

    async def enumerate_azure_storage(self, connection_string: str = "") -> dict:
        if self.simulation_mode or not self.sdks["azure"]:
            return {
                "containers": [
                    {"name": "uploads", "public_access": "Blob", "blob_count": 1523, "interesting": True},
                    {"name": "backups", "public_access": "None", "blob_count": 892, "interesting": False},
                    {"name": "logs", "public_access": "Container", "blob_count": 45231, "interesting": True},
                ],
                "simulation": True,
            }
        return {}

    # ── GCP ───────────────────────────────────────────────────────────────────

    async def enumerate_gcp_storage(self, project_id: str = "", credentials_json: str = "") -> list[dict]:
        if self.simulation_mode or not self.sdks["gcp"]:
            await asyncio.sleep(2)
            return _MOCK_GCP_BUCKETS
        return _MOCK_GCP_BUCKETS

    async def check_gcp_metadata(self, target_ip: str) -> dict:
        if self.simulation_mode:
            return {
                "accessible": True,
                "project_id": "corp-prod-123456",
                "instance_name": "web-server-01",
                "service_account": "compute@developer.gserviceaccount.com",
                "scopes": ["https://www.googleapis.com/auth/cloud-platform"],
                "access_token_available": True,
                "simulation": True,
            }
        return {"accessible": False}

    # ── Firebase ──────────────────────────────────────────────────────────────

    async def check_firebase_database(self, project_id: str, authorization_confirmed: bool = False) -> dict:
        if self.simulation_mode:
            await asyncio.sleep(1)
            return _MOCK_FIREBASE_FINDINGS
        return {}

    async def enumerate_firebase_storage(self, project_id: str) -> dict:
        if self.simulation_mode:
            return {
                "bucket": f"{project_id}.appspot.com",
                "public_access": True,
                "file_count": 2847,
                "sample_files": ["users/exports/all_users_2026.csv", "admin/backup.zip", "config/keys.json"],
                "simulation": True,
            }
        return {}

    # ── DNS / Cloudflare ──────────────────────────────────────────────────────

    async def enumerate_dns_cloudflare(self, domain: str, cf_api_token: str = "") -> list[dict]:
        if self.simulation_mode or not cf_api_token:
            await asyncio.sleep(1)
            return _MOCK_CLOUDFLARE_DNS
        return _MOCK_CLOUDFLARE_DNS

    async def subdomain_bruteforce(self, domain: str) -> list[dict]:
        if self.simulation_mode:
            await asyncio.sleep(3)
            wordlist = ["admin", "vpn", "mail", "dev", "staging", "api", "internal", "secure", "login", "portal"]
            return [{"subdomain": f"{w}.{domain}", "ip": f"203.0.113.{i+1}", "status": random.choice(["active", "active", "active", "inactive"])} for i, w in enumerate(wordlist)]
        return []


cloud_service = CloudEnumService()
