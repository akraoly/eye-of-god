"""
Routes /api/vision — capture d'écran + analyse Claude Vision.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from pydantic import BaseModel
from typing import Optional
import base64
import mimetypes

from core.vision.vision_engine import capture_screenshot, analyze_image

router = APIRouter()

ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
MAX_SIZE = 20 * 1024 * 1024  # 20 MB


class AnalyzeBase64Request(BaseModel):
    image_b64: str
    media_type: str = "image/png"
    prompt: Optional[str] = None


@router.post("/screenshot")
async def screenshot_and_analyze(prompt: Optional[str] = None):
    """Capture l'écran et l'analyse avec Claude Vision."""
    try:
        image_data, media_type = capture_screenshot()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Capture échouée : {e}")

    analysis = await analyze_image(
        image_data, media_type,
        prompt or "Décris ce que tu vois sur cet écran en détail.",
    )
    b64 = base64.standard_b64encode(image_data).decode()
    return {
        "analysis": analysis,
        "image_b64": b64,
        "media_type": media_type,
        "source": "screenshot",
    }


@router.post("/upload")
async def upload_and_analyze(
    file: UploadFile = File(...),
    prompt: str = Form(default="Décris ce que tu vois en détail."),
):
    """Analyse une image uploadée avec Claude Vision."""
    media_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "image/png"
    if media_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Type non supporté : {media_type}. Acceptés : PNG, JPEG, WEBP, GIF")

    image_data = await file.read()
    if len(image_data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Fichier trop grand (max 20 MB)")
    if len(image_data) == 0:
        raise HTTPException(status_code=400, detail="Fichier vide")

    analysis = await analyze_image(image_data, media_type, prompt)
    b64 = base64.standard_b64encode(image_data).decode()
    return {
        "analysis": analysis,
        "image_b64": b64,
        "media_type": media_type,
        "source": "upload",
        "filename": file.filename,
    }


@router.post("/analyze")
async def analyze_base64(body: AnalyzeBase64Request):
    """Analyse une image fournie en base64."""
    if body.media_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"Type non supporté : {body.media_type}")
    try:
        image_data = base64.b64decode(body.image_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="Base64 invalide")

    if len(image_data) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Image trop grande (max 20 MB)")

    analysis = await analyze_image(
        image_data, body.media_type,
        body.prompt or "Décris ce que tu vois en détail.",
    )
    return {"analysis": analysis, "source": "base64"}
