"""
StegoService — Stéganographie réseau & média.
Cache des données dans images, audio, vidéo, et protocoles réseau.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import math
import os
import random
import struct
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SIMULATION_MODE = os.getenv("SIMULATION_MODE", "true").lower() == "true"
_OUTPUT_DIR = Path("./data/stego_output")
_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_deps() -> dict:
    deps = {}
    for mod in ["PIL", "cv2", "numpy", "pydub", "stegano"]:
        try:
            __import__(mod)
            deps[mod] = True
        except ImportError:
            deps[mod] = False
    return deps


class StegoService:

    def __init__(self):
        self.simulation_mode = SIMULATION_MODE
        self.deps = _check_deps()

    # ── Image LSB ─────────────────────────────────────────────────────────────

    async def image_encode_lsb(self, image_path: str, data: str, output_path: str = None) -> str:
        if output_path is None:
            output_path = str(_OUTPUT_DIR / f"encoded_{Path(image_path).stem}_{int(time.time())}.png")

        if self.simulation_mode or not self.deps.get("PIL"):
            await asyncio.sleep(1)
            Path(output_path).write_bytes(Path(image_path).read_bytes() if Path(image_path).exists() else b"\x89PNG\r\n\x1a\n[SIMULATED LSB ENCODED]")
            return output_path

        from PIL import Image
        loop = asyncio.get_event_loop()

        def _encode():
            img = Image.open(image_path).convert("RGB")
            pixels = list(img.getdata())
            payload = data.encode("utf-8")
            length_prefix = struct.pack(">I", len(payload))
            bits = []
            for byte in length_prefix + payload:
                for i in range(7, -1, -1):
                    bits.append((byte >> i) & 1)

            if len(bits) > len(pixels) * 3:
                raise ValueError(f"Données trop grandes: {len(bits)} bits > {len(pixels)*3} disponibles")

            new_pixels = []
            bit_idx = 0
            for pixel in pixels:
                r, g, b = pixel
                if bit_idx < len(bits):
                    r = (r & 0xFE) | bits[bit_idx]; bit_idx += 1
                if bit_idx < len(bits):
                    g = (g & 0xFE) | bits[bit_idx]; bit_idx += 1
                if bit_idx < len(bits):
                    b = (b & 0xFE) | bits[bit_idx]; bit_idx += 1
                new_pixels.append((r, g, b))

            new_img = Image.new("RGB", img.size)
            new_img.putdata(new_pixels)
            new_img.save(output_path, "PNG")
            return output_path

        return await loop.run_in_executor(None, _encode)

    async def image_decode_lsb(self, image_path: str) -> str:
        if self.simulation_mode or not self.deps.get("PIL"):
            await asyncio.sleep(0.5)
            return "[SIMULATED DECODE] Message secret: 'Opération Phoenix confirmée - 06/07/2026'"

        from PIL import Image
        loop = asyncio.get_event_loop()

        def _decode():
            img = Image.open(image_path).convert("RGB")
            pixels = list(img.getdata())
            bits = []
            for r, g, b in pixels:
                bits.extend([(r & 1), (g & 1), (b & 1)])

            length_bits = bits[:32]
            length = int("".join(str(b) for b in length_bits), 2)

            data_bits = bits[32:32 + length * 8]
            chars = []
            for i in range(0, len(data_bits), 8):
                byte_bits = data_bits[i:i+8]
                if len(byte_bits) == 8:
                    chars.append(chr(int("".join(str(b) for b in byte_bits), 2)))
            return "".join(chars)

        return await loop.run_in_executor(None, _decode)

    # ── Audio spectrogram ────────────────────────────────────────────────────

    async def audio_encode_spectrogram(self, audio_path: str, text: str, output_path: str = None) -> str:
        if output_path is None:
            output_path = str(_OUTPUT_DIR / f"stego_audio_{int(time.time())}.wav")

        if self.simulation_mode or not self.deps.get("numpy"):
            await asyncio.sleep(1.5)
            Path(output_path).write_bytes(b"RIFF[SIMULATED STEGO AUDIO]")
            return output_path

        import numpy as np
        loop = asyncio.get_event_loop()

        def _encode():
            sample_rate = 44100
            duration = max(3, len(text) * 0.1)
            t = np.linspace(0, duration, int(sample_rate * duration))
            signal = np.zeros(len(t), dtype=np.float32)

            for i, char in enumerate(text):
                freq = 18000 + (ord(char) % 2000)
                start = int(i * sample_rate * 0.1)
                end = min(start + int(sample_rate * 0.1), len(signal))
                chunk_t = np.linspace(0, 0.1, end - start)
                signal[start:end] += 0.1 * np.sin(2 * np.pi * freq * chunk_t)

            carrier_freq = 440
            carrier = 0.5 * np.sin(2 * np.pi * carrier_freq * t)
            mixed = (carrier + signal * 0.3).astype(np.float32)

            import wave, struct as _s
            with wave.open(output_path, 'w') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                pcm = (_s.pack('<' + 'h' * len(mixed),
                               *[int(s * 32767) for s in np.clip(mixed, -1, 1)]))
                wf.writeframes(pcm)
            return output_path

        return await loop.run_in_executor(None, _encode)

    async def audio_decode_spectrogram(self, audio_path: str) -> str:
        if self.simulation_mode or not self.deps.get("numpy"):
            await asyncio.sleep(0.5)
            return "[SIMULATED] Message extrait du spectrogramme: 'Rendez-vous Alpha 48.8566°N 2.3522°E'"
        return "Analyse spectrogramme disponible uniquement avec scipy installé"

    # ── Video ─────────────────────────────────────────────────────────────────

    async def video_encode(self, video_path: str, data: str, output_path: str = None, frame_interval: int = 30) -> str:
        if output_path is None:
            output_path = str(_OUTPUT_DIR / f"stego_video_{int(time.time())}.mp4")
        if self.simulation_mode or not self.deps.get("cv2"):
            await asyncio.sleep(2)
            Path(output_path).write_bytes(b"\x00\x00\x00\x18ftyp[SIMULATED STEGO VIDEO]")
            return output_path
        return "Encodage vidéo disponible avec opencv installé"

    # ── Network ───────────────────────────────────────────────────────────────

    async def network_tcp_timestamp(self, data: str, pcap_output: str = None) -> str:
        if pcap_output is None:
            pcap_output = str(_OUTPUT_DIR / f"stego_tcp_{int(time.time())}.pcap")
        await asyncio.sleep(1)
        bits = "".join(format(ord(c), "08b") for c in data)
        packets = []
        for i, bit in enumerate(bits):
            ts_offset = int(bit) * 2
            packets.append({"seq": i, "timestamp": f"1.{i*10 + ts_offset:06d}", "bit": int(bit)})
        pcap_path = Path(pcap_output)
        pcap_path.write_text(json.dumps({
            "method": "tcp_timestamp_covert",
            "bits_encoded": len(bits),
            "bytes_encoded": len(data),
            "packets": packets[:20],
            "simulation": self.simulation_mode,
        }, indent=2))
        return pcap_output

    async def network_dns_txt(self, data: str, domain: str) -> list[str]:
        await asyncio.sleep(0.5)
        encoded = base64.b32encode(data.encode()).decode().rstrip("=")
        chunk_size = 50
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        return [f"{chunk.lower()}.{i:03d}.{domain}" for i, chunk in enumerate(chunks)]

    async def network_http_header(self, data: str) -> dict:
        encoded = base64.b64encode(data.encode()).decode()
        headers = {
            "X-Cache-Token": encoded[:32],
            "X-Request-ID": encoded[32:64] if len(encoded) > 32 else "",
            "X-Content-Duration": str(len(data)),
            "X-Forwarded-For": ".".join(str(int(b, 2)) for b in [encoded[:8], encoded[8:16], encoded[16:24], encoded[24:32]] if b),
        }
        return {"headers": headers, "total_bytes_hidden": len(data), "method": "http_header_covert"}

    # ── Detection ─────────────────────────────────────────────────────────────

    async def detect_stego_in_image(self, image_path: str) -> dict:
        if self.simulation_mode or not self.deps.get("PIL"):
            await asyncio.sleep(1.5)
            detected = random.random() > 0.4
            return {
                "file": image_path,
                "stego_detected": detected,
                "confidence": round(random.uniform(0.6, 0.95) if detected else random.uniform(0.1, 0.35), 2),
                "method": "LSB" if detected else None,
                "estimated_hidden_bytes": random.randint(100, 5000) if detected else 0,
                "analysis": {
                    "lsb_chi_square": round(random.uniform(0.1, 1.8), 4),
                    "lsb_expected": 1.0,
                    "rs_analysis": random.choice(["pass", "anomaly"]),
                    "histogram_anomaly": detected,
                },
                "simulation": True,
            }

        from PIL import Image
        import numpy as np
        loop = asyncio.get_event_loop()

        def _analyze():
            img = Image.open(image_path).convert("RGB")
            arr = np.array(img)
            lsb_plane = arr & 1
            expected = 0.5
            actual = lsb_plane.mean()
            deviation = abs(actual - expected)
            detected = deviation < 0.05
            return {
                "file": image_path,
                "stego_detected": bool(detected),
                "confidence": round(1.0 - deviation * 10, 2),
                "method": "LSB" if detected else None,
                "analysis": {"lsb_mean": float(actual), "deviation": float(deviation)},
                "simulation": False,
            }

        return await loop.run_in_executor(None, _analyze)

    async def encode_file(self, file_path: str, data: str, method: str = "lsb", carrier_path: str = None) -> str:
        if method == "lsb":
            return await self.image_encode_lsb(carrier_path or file_path, data)
        elif method == "spectrum":
            return await self.audio_encode_spectrogram(carrier_path or file_path, data)
        elif method == "dns":
            records = await self.network_dns_txt(data, "c2.example.com")
            out = str(_OUTPUT_DIR / f"dns_records_{int(time.time())}.txt")
            Path(out).write_text("\n".join(records))
            return out
        return ""


stego_service = StegoService()
