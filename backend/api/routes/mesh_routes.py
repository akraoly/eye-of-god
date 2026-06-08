from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.radio.mesh_radio_service import mesh_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class InitNodeReq(AuthReq):
    device_port: str
    node_name: str
    frequency_mhz: float = 868.0
    power: int = 20


class BroadcastReq(AuthReq):
    node_id: str
    message: str
    encrypted: bool = True


class DirectMsgReq(AuthReq):
    node_id: str
    target_node_id: str
    message: str


class FileTransferReq(AuthReq):
    node_id: str
    target_node_id: str
    file_path: str


class ScanReq(AuthReq):
    start_mhz: float = 863.0
    end_mhz: float = 870.0


class GetMessagesReq(BaseModel):
    since_id: Optional[int] = None


@router.get("/hardware")
async def check_hardware():
    return await mesh_service.check_hardware()


@router.post("/node/init")
async def init_node(req: InitNodeReq):
    _req_auth(req.authorization_confirmed, "init_mesh_node")
    return await mesh_service.init_mesh_node(req.device_port, req.node_name, req.frequency_mhz, req.power)


@router.post("/broadcast")
async def broadcast(req: BroadcastReq):
    _req_auth(req.authorization_confirmed, "broadcast_message")
    ok = await mesh_service.broadcast_message(req.node_id, req.message, req.encrypted)
    return {"success": ok}


@router.post("/direct")
async def direct_message(req: DirectMsgReq):
    _req_auth(req.authorization_confirmed, "send_direct_message")
    ok = await mesh_service.send_direct_message(req.node_id, req.target_node_id, req.message)
    return {"success": ok}


@router.post("/file/transfer")
async def file_transfer(req: FileTransferReq):
    _req_auth(req.authorization_confirmed, "transfer_file")
    return await mesh_service.transfer_file(req.node_id, req.target_node_id, req.file_path)


@router.get("/topology/{node_id}")
async def topology(node_id: str):
    return await mesh_service.get_mesh_topology(node_id)


@router.post("/scan")
async def scan_frequencies(req: ScanReq):
    _req_auth(req.authorization_confirmed, "scan_frequencies")
    return await mesh_service.scan_frequencies_lora(req.start_mhz, req.end_mhz)


@router.get("/messages/{node_id}")
async def get_messages(node_id: str, since_id: Optional[int] = None):
    return await mesh_service.get_messages(node_id, since_id)


@router.get("/nodes")
async def get_nodes():
    from services.radio.mesh_radio_service import _MOCK_NODES
    return _MOCK_NODES
