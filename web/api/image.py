"""Image-to-3D heightmap converter."""

import io
import re
import uuid
from pathlib import Path

import numpy as np
import trimesh
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from PIL import Image, ImageFilter
from pydantic import BaseModel, Field

MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/bmp", "image/tiff", "image/webp"}

router = APIRouter()

MESH_CACHE_DIR = Path(__file__).parent.parent / "static" / "cache"
MESH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class ConvertRequest(BaseModel):
    mesh_id: str
    max_height_mm: float = Field(10.0, ge=0.1, le=100.0)
    base_thickness_mm: float = Field(2.0, ge=0.1, le=100.0)
    smoothing: int = Field(0, ge=0, le=20)
    invert: bool = False
    resolution: int = Field(128, ge=8, le=512)


def _resize_keep_aspect(img: Image.Image, target_size: int) -> Image.Image:
    """Resize image to fit target_size x target_size with padding."""
    w, h = img.size
    scale = target_size / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

    # Pad to square
    padded = Image.new("L", (target_size, target_size), 0)
    off_x = (target_size - new_w) // 2
    off_y = (target_size - new_h) // 2
    padded.paste(img, (off_x, off_y))
    return padded


def _validate_mesh_id(mesh_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', mesh_id):
        raise HTTPException(status_code=400, detail="Invalid mesh_id")
    return mesh_id


def image_to_mesh(image_bytes: bytes, max_height: float = 10.0,
                  base_thickness: float = 2.0, resolution: int = 128,
                  smoothing: int = 0, invert: bool = False) -> trimesh.Trimesh:
    """Convert image to heightmap mesh."""
    if not (8 <= resolution <= 512):
        raise ValueError("resolution must be between 8 and 512")

    img = Image.open(io.BytesIO(image_bytes)).convert("L")

    if smoothing > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=smoothing))

    img = _resize_keep_aspect(img, resolution)
    arr = np.array(img, dtype=np.float32) / 255.0  # 0.0 - 1.0

    if invert:
        arr = 1.0 - arr

    h, w = arr.shape
    xs = np.linspace(-w / 2, w / 2, w)
    ys = np.linspace(-h / 2, h / 2, h)

    # Top surface vertices
    verts_top = []
    for iy in range(h):
        for ix in range(w):
            z = arr[iy, ix] * max_height
            verts_top.append([xs[ix], ys[iy], z])

    verts_top = np.array(verts_top)

    # Bottom plate vertices
    verts_bottom = []
    for iy in range(h):
        for ix in range(w):
            verts_bottom.append([xs[ix], ys[iy], -base_thickness])

    verts_bottom = np.array(verts_bottom)

    # Combine vertices
    verts = np.vstack([verts_top, verts_bottom])
    top_offset = 0
    bot_offset = len(verts_top)

    faces = []

    # Top faces
    for iy in range(h - 1):
        for ix in range(w - 1):
            i0 = top_offset + iy * w + ix
            i1 = top_offset + iy * w + (ix + 1)
            i2 = top_offset + (iy + 1) * w + ix
            i3 = top_offset + (iy + 1) * w + (ix + 1)
            faces.append([i0, i1, i3])
            faces.append([i0, i3, i2])

    # Bottom faces (reversed winding)
    for iy in range(h - 1):
        for ix in range(w - 1):
            i0 = bot_offset + iy * w + ix
            i1 = bot_offset + iy * w + (ix + 1)
            i2 = bot_offset + (iy + 1) * w + ix
            i3 = bot_offset + (iy + 1) * w + (ix + 1)
            faces.append([i0, i3, i1])
            faces.append([i0, i2, i3])

    # Side walls
    # Front (y = min)
    for ix in range(w - 1):
        t0 = top_offset + 0 * w + ix
        t1 = top_offset + 0 * w + (ix + 1)
        b0 = bot_offset + 0 * w + ix
        b1 = bot_offset + 0 * w + (ix + 1)
        faces.append([t0, b0, b1])
        faces.append([t0, b1, t1])

    # Back (y = max)
    for ix in range(w - 1):
        t0 = top_offset + (h - 1) * w + ix
        t1 = top_offset + (h - 1) * w + (ix + 1)
        b0 = bot_offset + (h - 1) * w + ix
        b1 = bot_offset + (h - 1) * w + (ix + 1)
        faces.append([t0, b1, b0])
        faces.append([t0, t1, b1])

    # Left (x = min)
    for iy in range(h - 1):
        t0 = top_offset + iy * w + 0
        t1 = top_offset + (iy + 1) * w + 0
        b0 = bot_offset + iy * w + 0
        b1 = bot_offset + (iy + 1) * w + 0
        faces.append([t0, b1, b0])
        faces.append([t0, t1, b1])

    # Right (x = max)
    for iy in range(h - 1):
        t0 = top_offset + iy * w + (w - 1)
        t1 = top_offset + (iy + 1) * w + (w - 1)
        b0 = bot_offset + iy * w + (w - 1)
        b1 = bot_offset + (iy + 1) * w + (w - 1)
        faces.append([t0, b0, b1])
        faces.append([t0, b1, t1])

    faces = np.array(faces, dtype=np.int64)
    mesh = trimesh.Trimesh(vertices=verts, faces=faces)
    mesh.merge_vertices()
    return mesh


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    """Upload image and cache original bytes."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid file type. Only image files are allowed.")

    image_id = str(uuid.uuid4())[:8]
    image_bytes = await file.read()

    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="File too large. Max size is 10MB.")

    # Save original for re-conversion
    cache_path = MESH_CACHE_DIR / f"{image_id}_orig.png"
    cache_path.write_bytes(image_bytes)

    # Generate preview mesh with defaults
    mesh = image_to_mesh(image_bytes)
    stl_path = MESH_CACHE_DIR / f"{image_id}.stl"
    mesh.export(str(stl_path), file_type="stl")

    return JSONResponse({
        "image_id": image_id,
        "stl_url": f"/static/cache/{image_id}.stl",
        "width": mesh.bounds[1][0] - mesh.bounds[0][0],
        "height": mesh.bounds[1][1] - mesh.bounds[0][1],
        "max_z": float(mesh.bounds[1][2]),
    })


@router.post("/convert")
async def convert_image(req: ConvertRequest):
    """Re-convert cached image with new parameters."""
    _validate_mesh_id(req.mesh_id)
    cache_path = MESH_CACHE_DIR / f"{req.mesh_id}_orig.png"
    if not cache_path.exists():
        return JSONResponse({"error": "Image not found"}, status_code=404)

    image_bytes = cache_path.read_bytes()

    # Parse resolution from request if embedded, else default
    mesh = image_to_mesh(
        image_bytes,
        max_height=req.max_height_mm,
        base_thickness=req.base_thickness_mm,
        resolution=req.resolution,
        smoothing=req.smoothing,
        invert=req.invert,
    )

    stl_path = MESH_CACHE_DIR / f"{req.mesh_id}.stl"
    mesh.export(str(stl_path), file_type="stl")

    return JSONResponse({
        "mesh_id": req.mesh_id,
        "stl_url": f"/static/cache/{req.mesh_id}.stl",
        "volume_mm3": round(float(mesh.volume), 2) if mesh.is_watertight else 0,
        "watertight": mesh.is_watertight,
    })
