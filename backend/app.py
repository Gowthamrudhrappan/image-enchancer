"""
Clarity — AI restore backend.

Runs real, self-hosted models — GFPGAN (face restoration) and
Real-ESRGAN (general upscale) — behind one HTTP endpoint that matches
exactly what the frontend (index.html, function runAiEnhanceViaBackend)
already sends and expects:

    POST /enhance-ai
    body: { "imageBase64": "data:image/png;base64,...", "strength": 0-100, "faceSafe": true|false }
    response: { "outputUrl": "data:image/png;base64,..." }

No third-party API, no per-request cost, no dependency on someone
else's uptime (unlike the free Hugging Face Space we tested and found
offline) — this runs entirely on infrastructure you control. See
README.md in this folder for deployment options and hardware notes.

Model weights are NOT bundled in this repo (they're a few hundred MB).
Both GFPGANer and RealESRGANer download their weights automatically
from the official GitHub release URLs on first use, and cache them in
./weights — so the first request after a fresh deploy will be slow
(downloading weights), every request after that will not be.
"""

import base64
import io
import logging
import os

import cv2
import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clarity-backend")

WEIGHTS_DIR = os.environ.get("CLARITY_WEIGHTS_DIR", "./weights")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

# Restrict this to your actual deployed frontend origin(s) once you know
# them — e.g. ["https://gowthamrudhrappan.github.io"]. "*" is fine while
# you're testing, but is an open door in production.
ALLOWED_ORIGINS = os.environ.get("CLARITY_ALLOWED_ORIGINS", "*").split(",")

app = FastAPI(title="Clarity AI Restore Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class EnhanceRequest(BaseModel):
    imageBase64: str
    strength: float = Field(default=60, ge=0, le=100)
    faceSafe: bool = True


# ----------------------------------------------------------------
# Lazy model loading: the (large, slow-to-load) models are only
# constructed on first request, not at server startup, so the
# process boots instantly and the deploy platform's health check
# doesn't time out waiting for torch + model weights.
# ----------------------------------------------------------------
_gfpganer = None
_realesrganer = None


def get_realesrganer():
    global _realesrganer
    if _realesrganer is None:
        logger.info("Loading Real-ESRGAN (first request only)…")
        from basicsr.archs.rrdbnet_arch import RRDBNet
        from realesrgan import RealESRGANer

        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64,
            num_block=23, num_grow_ch=32, scale=2,
        )
        _realesrganer = RealESRGANer(
            scale=2,
            model_path="https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth",
            model=model,
            tile=400,          # tiles large images to bound memory use
            tile_pad=10,
            pre_pad=0,
            half=torch.cuda.is_available(),  # fp16 only makes sense with a GPU
            model_dir=WEIGHTS_DIR,
        )
        logger.info("Real-ESRGAN ready.")
    return _realesrganer


def get_gfpganer():
    global _gfpganer
    if _gfpganer is None:
        logger.info("Loading GFPGAN (first request only)…")
        from gfpgan import GFPGANer

        # GFPGAN restores faces; a bg_upsampler (Real-ESRGAN) handles the
        # rest of the frame at the same time so backgrounds aren't left
        # soft next to a sharpened face.
        _gfpganer = GFPGANer(
            model_path="https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth",
            upscale=2,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=get_realesrganer(),
            model_dir=WEIGHTS_DIR,
        )
        logger.info("GFPGAN ready.")
    return _gfpganer


def decode_image(image_base64: str) -> np.ndarray:
    """Data URL or bare base64 -> OpenCV BGR numpy array."""
    payload = image_base64.split(",", 1)[1] if "," in image_base64 else image_base64
    try:
        raw = base64.b64decode(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid base64 image: {exc}")
    pil_img = Image.open(io.BytesIO(raw)).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def encode_image(bgr: np.ndarray) -> str:
    """OpenCV BGR numpy array -> PNG data URL."""
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/enhance-ai")
def enhance(req: EnhanceRequest):
    img = decode_image(req.imageBase64)

    try:
        if req.faceSafe:
            gfpganer = get_gfpganer()
            weight = max(0.1, min(1.0, req.strength / 100))
            _, _, restored = gfpganer.enhance(
                img,
                has_aligned=False,
                only_center_face=False,
                paste_back=True,
                weight=weight,
            )
        else:
            realesrganer = get_realesrganer()
            restored, _ = realesrganer.enhance(img, outscale=2)
    except Exception as exc:
        logger.exception("Enhancement failed")
        raise HTTPException(status_code=500, detail=f"Model inference failed: {exc}")

    return {"outputUrl": encode_image(restored)}
