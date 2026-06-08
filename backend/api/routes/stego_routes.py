from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from services.stego.stego_service import stego_service

router = APIRouter()


def _req_auth(confirmed: bool, action: str):
    if not confirmed:
        raise HTTPException(403, f"authorization_confirmed=true requis pour: {action}")


class AuthReq(BaseModel):
    authorization_confirmed: bool = False


class ImageEncodeReq(AuthReq):
    image_path: str
    message: str
    password: Optional[str] = None


class ImageDecodeReq(AuthReq):
    image_path: str
    password: Optional[str] = None


class AudioEncodeReq(AuthReq):
    audio_path: str
    message: str


class AudioDecodeReq(AuthReq):
    audio_path: str


class TCPChannelReq(AuthReq):
    target_ip: str
    target_port: int
    message: str


class DNSChannelReq(AuthReq):
    domain: str
    message: str
    dns_server: Optional[str] = "8.8.8.8"


class HTTPChannelReq(AuthReq):
    url: str
    message: str


class DetectReq(AuthReq):
    file_path: str


@router.post("/image/encode")
async def encode_image(req: ImageEncodeReq):
    _req_auth(req.authorization_confirmed, "stego_image_encode")
    out = await stego_service.encode_image_lsb(req.image_path, req.message, req.password)
    return {"output_path": out}


@router.post("/image/decode")
async def decode_image(req: ImageDecodeReq):
    _req_auth(req.authorization_confirmed, "stego_image_decode")
    msg = await stego_service.decode_image_lsb(req.image_path, req.password)
    return {"message": msg}


@router.post("/audio/encode")
async def encode_audio(req: AudioEncodeReq):
    _req_auth(req.authorization_confirmed, "stego_audio_encode")
    out = await stego_service.encode_audio_spectrogram(req.audio_path, req.message)
    return {"output_path": out}


@router.post("/audio/decode")
async def decode_audio(req: AudioDecodeReq):
    _req_auth(req.authorization_confirmed, "stego_audio_decode")
    msg = await stego_service.decode_audio_spectrogram(req.audio_path)
    return {"message": msg}


@router.post("/network/tcp")
async def tcp_channel(req: TCPChannelReq):
    _req_auth(req.authorization_confirmed, "stego_tcp_channel")
    return await stego_service.network_tcp_timestamp(req.target_ip, req.target_port, req.message)


@router.post("/network/dns")
async def dns_channel(req: DNSChannelReq):
    _req_auth(req.authorization_confirmed, "stego_dns_channel")
    return await stego_service.network_dns_txt(req.domain, req.message, req.dns_server)


@router.post("/network/http")
async def http_channel(req: HTTPChannelReq):
    _req_auth(req.authorization_confirmed, "stego_http_channel")
    return await stego_service.network_http_header(req.url, req.message)


@router.post("/detect")
async def detect_stego(req: DetectReq):
    _req_auth(req.authorization_confirmed, "stego_detect")
    return await stego_service.detect_stego_in_image(req.file_path)


@router.get("/methods")
async def list_methods():
    return {
        "methods": [
            {"id": "image_lsb", "name": "Image LSB", "type": "image", "capacity": "high", "detectability": "low"},
            {"id": "audio_spectrogram", "name": "Audio Spectrogram", "type": "audio", "capacity": "medium", "detectability": "very_low"},
            {"id": "tcp_timestamp", "name": "TCP Timestamp Covert", "type": "network", "capacity": "low", "detectability": "very_low"},
            {"id": "dns_txt", "name": "DNS TXT Covert", "type": "network", "capacity": "low", "detectability": "low"},
            {"id": "http_header", "name": "HTTP Header Stego", "type": "network", "capacity": "medium", "detectability": "medium"},
        ]
    }
