"""Mesh export and validation endpoints."""

import re
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

MESH_CACHE_DIR = Path(__file__).parent.parent / "static" / "cache"


def _validate_mesh_id(mesh_id: str) -> str:
    if not re.match(r'^[a-zA-Z0-9_-]+$', mesh_id):
        raise HTTPException(status_code=400, detail="Invalid mesh_id")
    return mesh_id


@router.get("/download/{mesh_id}/{format}")
async def download_mesh(mesh_id: str, format: str):
    """Download generated mesh in specified format."""
    _validate_mesh_id(mesh_id)
    if format not in ("stl", "step", "obj"):
        raise HTTPException(status_code=400, detail="Format must be stl, step, or obj")

    filepath = MESH_CACHE_DIR / f"{mesh_id}.{format}"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Mesh not found")

    media_types = {
        "stl": "application/octet-stream",
        "step": "application/octet-stream",
        "obj": "application/octet-stream",
    }

    return FileResponse(
        path=filepath,
        media_type=media_types[format],
        filename=f"part.{format}",
    )


@router.get("/validate/{mesh_id}")
async def validate_mesh(mesh_id: str):
    """Run mesh validation on cached mesh."""
    _validate_mesh_id(mesh_id)
    filepath = MESH_CACHE_DIR / f"{mesh_id}.stl"
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Mesh not found")

    import trimesh
    mesh = trimesh.load_mesh(str(filepath), force="mesh")

    # Boundary edge count
    edge_face_count = {}
    for face in mesh.faces:
        for j in range(3):
            a, b = int(face[j]), int(face[(j + 1) % 3])
            edge = tuple(sorted([a, b]))
            edge_face_count[edge] = edge_face_count.get(edge, 0) + 1
    boundary_count = sum(1 for v in edge_face_count.values() if v == 1)

    return {
        "watertight": mesh.is_watertight,
        "face_count": len(mesh.faces),
        "volume_mm3": round(float(mesh.volume), 4) if mesh.is_watertight else None,
        "surface_area_mm2": round(float(mesh.area), 4),
        "boundary_edges": boundary_count,
        "has_holes": boundary_count > 0,
        "extents_mm": mesh.extents.tolist(),
    }
