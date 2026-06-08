"""Routes Cloud Enumeration — AWS / Azure / GCP / Firebase / Cloudflare."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.routes.auth import get_current_user
from services.cloud.cloud_enum_service import cloud_service

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class AWSCredentials(BaseModel):
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    authorization_confirmed: bool = False


class AzureCredentials(BaseModel):
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    subscription_id: str = ""
    authorization_confirmed: bool = False


class GCPCredentials(BaseModel):
    project_id: str = ""
    credentials_json: str = ""
    authorization_confirmed: bool = False


class FirebaseRequest(BaseModel):
    project_id: str
    authorization_confirmed: bool = False


class CloudflareRequest(BaseModel):
    domain: str
    cf_api_token: str = ""
    authorization_confirmed: bool = False


class MetadataRequest(BaseModel):
    target_ip: str
    authorization_confirmed: bool = False


class S3ObjectsRequest(BaseModel):
    bucket_name: str
    access_key: str = ""
    secret_key: str = ""
    authorization_confirmed: bool = False


class LambdaEnvRequest(BaseModel):
    function_name: str
    access_key: str = ""
    secret_key: str = ""
    region: str = "us-east-1"
    authorization_confirmed: bool = False


class AzureStorageRequest(BaseModel):
    connection_string: str = ""
    authorization_confirmed: bool = False


# ── Guard ─────────────────────────────────────────────────────────────────────

def _require_auth(auth: bool, action: str):
    if not auth:
        raise HTTPException(403, detail=f"{action} nécessite authorization_confirmed=true")


# ── Routes AWS ────────────────────────────────────────────────────────────────

@router.post("/aws/s3/enumerate")
async def aws_s3_enumerate(req: AWSCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération S3")
    buckets = await cloud_service.enumerate_s3_buckets(req.access_key, req.secret_key, req.region)
    public_count = sum(1 for b in buckets if b.get("public"))
    return {"buckets": buckets, "count": len(buckets), "public_count": public_count}


@router.post("/aws/s3/objects")
async def aws_s3_objects(req: S3ObjectsRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération objets S3")
    objects = await cloud_service.enumerate_s3_objects(req.bucket_name, req.access_key, req.secret_key)
    interesting = [o for o in objects if o.get("interesting")]
    return {"objects": objects, "count": len(objects), "interesting": interesting}


@router.post("/aws/iam/enumerate")
async def aws_iam_enumerate(req: AWSCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération IAM")
    return await cloud_service.enumerate_iam(req.access_key, req.secret_key)


@router.post("/aws/lambda/enumerate")
async def aws_lambda_enumerate(req: AWSCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération Lambda")
    functions = await cloud_service.enumerate_lambda(req.access_key, req.secret_key, req.region)
    return {"functions": functions, "count": len(functions)}


@router.post("/aws/lambda/env-vars")
async def aws_lambda_env_vars(req: LambdaEnvRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Extraction variables Lambda")
    return await cloud_service.get_lambda_env_vars(req.function_name, req.access_key, req.secret_key, req.region)


@router.post("/aws/metadata")
async def aws_metadata(req: MetadataRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Accès metadata EC2")
    return await cloud_service.check_metadata_service(req.target_ip)


# ── Routes Azure ──────────────────────────────────────────────────────────────

@router.post("/azure/resources")
async def azure_resources(req: AzureCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération ressources Azure")
    resources = await cloud_service.enumerate_azure_resources(req.tenant_id, req.client_id, req.client_secret, req.subscription_id)
    return {"resources": resources, "count": len(resources)}


@router.post("/azure/storage")
async def azure_storage(req: AzureStorageRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération Azure Storage")
    return await cloud_service.enumerate_azure_storage(req.connection_string)


# ── Routes GCP ────────────────────────────────────────────────────────────────

@router.post("/gcp/storage")
async def gcp_storage(req: GCPCredentials, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération GCP Storage")
    buckets = await cloud_service.enumerate_gcp_storage(req.project_id, req.credentials_json)
    return {"buckets": buckets, "count": len(buckets)}


@router.post("/gcp/metadata")
async def gcp_metadata(req: MetadataRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Accès metadata GCP")
    return await cloud_service.check_gcp_metadata(req.target_ip)


# ── Routes Firebase ───────────────────────────────────────────────────────────

@router.post("/firebase/database")
async def firebase_database(req: FirebaseRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Test Firebase Database")
    return await cloud_service.check_firebase_database(req.project_id, req.authorization_confirmed)


@router.post("/firebase/storage")
async def firebase_storage(req: FirebaseRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération Firebase Storage")
    return await cloud_service.enumerate_firebase_storage(req.project_id)


# ── Routes DNS / Cloudflare ───────────────────────────────────────────────────

@router.post("/dns/cloudflare")
async def dns_cloudflare(req: CloudflareRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Énumération DNS Cloudflare")
    records = await cloud_service.enumerate_dns_cloudflare(req.domain, req.cf_api_token)
    return {"records": records, "count": len(records), "domain": req.domain}


@router.post("/dns/subdomain-bruteforce")
async def subdomain_bruteforce(req: CloudflareRequest, current_user=Depends(get_current_user)):
    _require_auth(req.authorization_confirmed, "Bruteforce sous-domaines")
    subdomains = await cloud_service.subdomain_bruteforce(req.domain)
    active = [s for s in subdomains if s.get("status") == "active"]
    return {"subdomains": subdomains, "count": len(subdomains), "active_count": len(active)}
