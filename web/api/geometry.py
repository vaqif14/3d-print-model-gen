"""Geometry generation endpoints."""

import uuid
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from cad_engine import parametric

router = APIRouter()

MESH_CACHE_DIR = Path(__file__).parent.parent / "static" / "cache"
MESH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


class GenerateRequest(BaseModel):
    part_type: str
    params: dict
    material: str = "PETG"
    printer: str = "p2s"


class GenerateResult(BaseModel):
    mesh_id: str
    stl_url: str
    step_url: str
    volume_mm3: float
    bounds_mm: list


def _clamp(val, min_v, max_v, name):
    if val < min_v or val > max_v:
        raise ValueError(f"{name} must be between {min_v} and {max_v}")
    return val


def _generate_mesh(req: GenerateRequest):
    pt = req.part_type
    p = req.params
    if pt == "bracket":
        width = _clamp(p.get("width", 60), 1, 500, "width")
        height = _clamp(p.get("height", 40), 1, 500, "height")
        depth = _clamp(p.get("depth", 25), 1, 500, "depth")
        thickness = p.get("thickness")
        if thickness is not None:
            thickness = _clamp(thickness, 0.1, 50, "thickness")
        hole_d = _clamp(p.get("hole_d", 4.3), 1, 50, "hole_d")
        load_kg = _clamp(p.get("load_kg", 5), 0, 100, "load_kg")
        return parametric.make_bracket(
            width=width,
            height=height,
            depth=depth,
            thickness=thickness,
            hole_d=hole_d,
            load_kg=load_kg,
            material=req.material,
        )
    elif pt == "enclosure":
        width = _clamp(p.get("width", 80), 1, 500, "width")
        depth = _clamp(p.get("depth", 60), 1, 500, "depth")
        height = _clamp(p.get("height", 40), 1, 500, "height")
        wall = _clamp(p.get("wall", 2.0), 0.1, 50, "wall")
        return parametric.make_enclosure(
            width=width,
            depth=depth,
            height=height,
            wall=wall,
            lid=p.get("lid", "snap"),
            pcb_mount=p.get("pcb_mount", False),
        )
    elif pt == "gear":
        teeth = _clamp(int(p.get("teeth", 20)), 5, 200, "teeth")
        module = _clamp(p.get("module", 1.0), 0.1, 10, "module")
        thickness = _clamp(p.get("thickness", 5.0), 0.1, 50, "thickness")
        bore_d = _clamp(p.get("bore_d", 8.0), 1, 50, "bore_d")
        return parametric.make_gear(
            teeth=teeth,
            module=module,
            thickness=thickness,
            bore_d=bore_d,
        )
    elif pt == "snap_fit":
        length = _clamp(p.get("length", 30), 1, 200, "length")
        width = _clamp(p.get("width", 10), 1, 50, "width")
        thickness = _clamp(p.get("thickness", 2.0), 0.1, 50, "thickness")
        deflection = _clamp(p.get("deflection", 2.0), 0.1, 20, "deflection")
        return parametric.make_snap_fit(
            length=length,
            width=width,
            thickness=thickness,
            deflection=deflection,
            material=req.material,
        )
    else:
        raise ValueError(f"Unknown part type: {pt}")


@router.post("/generate", response_model=GenerateResult)
async def generate(req: GenerateRequest):
    try:
        mesh = _generate_mesh(req)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    mesh_id = str(uuid.uuid4())[:8]

    stl_path = MESH_CACHE_DIR / f"{mesh_id}.stl"
    step_path = MESH_CACHE_DIR / f"{mesh_id}.step"

    parametric.export_stl(mesh, str(stl_path))
    # STEP fallback to STL since trimesh doesn't export STEP
    parametric.export_step(mesh, str(step_path))

    volume = float(mesh.volume) if mesh.is_watertight else 0.0
    bounds = mesh.bounds.tolist()

    return GenerateResult(
        mesh_id=mesh_id,
        stl_url=f"/static/cache/{mesh_id}.stl",
        step_url=f"/static/cache/{mesh_id}.step",
        volume_mm3=round(volume, 2),
        bounds_mm=bounds,
    )
