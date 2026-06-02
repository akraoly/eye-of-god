"""
Moteur Vision — capture d'écran + analyse Claude Vision.
"""
import os
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import anthropic
from app.config import settings

_client: Optional[anthropic.AsyncAnthropic] = None

def _get_client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def capture_screenshot() -> tuple[bytes, str]:
    """Capture l'écran via ImageMagick import. Retourne (bytes, media_type)."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        env = {**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":0.0")}
        result = subprocess.run(
            ["import", "-window", "root", "-resize", "1920x", tmp_path],
            env=env,
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.decode() or "Capture échouée")

        with open(tmp_path, "rb") as f:
            data = f.read()
        return data, "image/png"
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


async def analyze_image(
    image_data: bytes,
    media_type: str,
    prompt: str = "Décris ce que tu vois en détail. Si c'est un écran d'ordinateur, identifie les applications, le contenu visible, et tout ce qui est pertinent.",
) -> str:
    """Envoie l'image à Claude Vision et retourne l'analyse."""
    b64 = base64.standard_b64encode(image_data).decode("utf-8")

    response = await _get_client().messages.create(
        model=settings.CLAUDE_MODEL,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )
    return response.content[0].text
