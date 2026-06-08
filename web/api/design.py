"""AI Design Intent — parse natural language into parametric JSON."""

from fastapi import APIRouter
from pydantic import BaseModel
from cad_engine import materials, dfam

router = APIRouter()


class DesignPrompt(BaseModel):
    prompt: str
    printer: str = "p2s"


class DesignResult(BaseModel):
    part_type: str
    params: dict
    material: str
    printer: str
    tech: str
    infill: dict
    supports: dict
    estimates: dict
    param_schema: list


PART_KEYWORDS = {
    "bracket": ["bracket", "mount", "support", "holder", "clevis"],
    "enclosure": ["enclosure", "box", "case", "housing", "cover"],
    "gear": ["gear", "pinion", "spur", "helical", "bevel"],
    "snap_fit": ["clip", "snap", "latch", "hook", "fastener"],
    "heatset_boss": ["insert", "boss", "threaded", "nut"],
}

MATERIAL_KEYWORDS = {
    "PLA": ["pla", "prototype", "visual", "cheap"],
    "PETG": ["petg", "strong", "functional", "durable"],
    "ABS": ["abs", "impact", "heat resistant"],
    "ASA": ["asa", "outdoor", "uv", "weather"],
    "TPU": ["tpu", "flexible", "soft", "gasket", "rubber"],
    "Nylon": ["nylon", "pa", "tough", "wear"],
    "PC": ["pc", "polycarbonate", "extreme", "high temp"],
}


def parse_prompt(text: str, printer: str) -> DesignResult:
    """Parse natural language into parametric design."""
    text_lower = text.lower()

    # Detect part type
    part_type = "bracket"
    for pt, keywords in PART_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            part_type = pt
            break

    # Detect material
    material = "PETG"
    for mat, keywords in MATERIAL_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            material = mat
            break

    # Detect load
    import re
    load_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:kg|kilo|kilogram)', text_lower)
    load_kg = float(load_match.group(1)) if load_match else 5.0
    load_kg = max(0.0, min(load_kg, 100.0))

    # Detect dimensions
    dim_match = re.search(r'(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)', text_lower)
    if dim_match:
        width, depth, height = map(float, dim_match.groups())
        width = max(1.0, min(width, 500.0))
        depth = max(1.0, min(depth, 500.0))
        height = max(1.0, min(height, 500.0))
    else:
        width, depth, height = 60.0, 25.0, 40.0

    tech = "FDM"
    if printer not in materials.PRINTER_PROFILES:
        printer = "p2s"
    printer_profile = materials.PRINTER_PROFILES.get(printer, materials.PRINTER_PROFILES["p2s"])
    mat_props = materials.MATERIALS.get(material, materials.MATERIALS["PETG"])

    wall = dfam.recommend_wall_thickness(load_kg, material, tech)
    infill = dfam.recommend_infill(load_kg, part_type)
    supports = dfam.recommend_supports(tech)

    # Estimate volume roughly
    if part_type == "bracket":
        volume = width * depth * height * 0.25
    elif part_type == "enclosure":
        volume = width * depth * height * 0.15
    elif part_type == "gear":
        volume = 1000
    else:
        volume = width * depth * height * 0.2

    time_h = dfam.estimate_print_time(volume, 0.2, printer_profile["nozzle_mm"])
    cost = dfam.estimate_cost(volume, mat_props["density"], mat_props["cost_per_kg"])

    params = {
        "width": width,
        "height": height,
        "depth": depth,
        "thickness": wall,
        "hole_d": 4.3,
        "load_kg": load_kg,
    }

    if part_type == "enclosure":
        params["wall"] = wall
        params["lid"] = "snap"
        params["pcb_mount"] = "pcb" in text_lower or "electronics" in text_lower

    if part_type == "gear":
        params["teeth"] = 20
        params["module"] = 1.0
        params["bore_d"] = 8.0

    schema = build_schema(part_type)

    return DesignResult(
        part_type=part_type,
        params=params,
        material=material,
        printer=printer,
        tech=tech,
        infill=infill,
        supports=supports,
        estimates={
            "volume_mm3": round(volume, 1),
            "time_hours": round(time_h, 1),
            "cost_usd": round(cost, 2),
            "weight_g": round(volume * mat_props["density"] / 1000, 1),
        },
        param_schema=schema,
    )


def build_schema(part_type: str) -> list:
    """Build parametric JSON schema for UI form generation."""
    common = [
        {"key": "material", "type": "select", "label": "Material", "options": list(materials.MATERIALS.keys())},
        {"key": "printer", "type": "select", "label": "Printer", "options": list(materials.PRINTER_PROFILES.keys())},
    ]

    if part_type == "bracket":
        return [
            {"key": "width", "type": "number", "label": "Width (mm)", "min": 10, "max": 500, "step": 1},
            {"key": "height", "type": "number", "label": "Height (mm)", "min": 10, "max": 500, "step": 1},
            {"key": "depth", "type": "number", "label": "Depth (mm)", "min": 5, "max": 200, "step": 1},
            {"key": "thickness", "type": "number", "label": "Wall Thickness (mm)", "min": 0.8, "max": 10, "step": 0.1},
            {"key": "hole_d", "type": "number", "label": "Mounting Hole ⌀ (mm)", "min": 2, "max": 20, "step": 0.1},
            {"key": "load_kg", "type": "number", "label": "Load (kg)", "min": 0, "max": 100, "step": 0.5},
        ] + common

    elif part_type == "enclosure":
        return [
            {"key": "width", "type": "number", "label": "Width (mm)", "min": 20, "max": 500, "step": 1},
            {"key": "height", "type": "number", "label": "Height (mm)", "min": 20, "max": 500, "step": 1},
            {"key": "depth", "type": "number", "label": "Depth (mm)", "min": 20, "max": 500, "step": 1},
            {"key": "wall", "type": "number", "label": "Wall Thickness (mm)", "min": 0.8, "max": 10, "step": 0.1},
            {"key": "lid", "type": "select", "label": "Lid Type", "options": ["snap", "screw", "none"]},
            {"key": "pcb_mount", "type": "checkbox", "label": "PCB Standoffs"},
        ] + common

    elif part_type == "gear":
        return [
            {"key": "teeth", "type": "number", "label": "Teeth Count", "min": 5, "max": 200, "step": 1},
            {"key": "module", "type": "number", "label": "Module", "min": 0.2, "max": 10, "step": 0.1},
            {"key": "thickness", "type": "number", "label": "Thickness (mm)", "min": 1, "max": 50, "step": 0.5},
            {"key": "bore_d", "type": "number", "label": "Bore ⌀ (mm)", "min": 2, "max": 50, "step": 0.1},
        ] + common

    elif part_type == "snap_fit":
        return [
            {"key": "length", "type": "number", "label": "Arm Length (mm)", "min": 5, "max": 100, "step": 1},
            {"key": "width", "type": "number", "label": "Width (mm)", "min": 5, "max": 50, "step": 1},
            {"key": "deflection", "type": "number", "label": "Deflection (mm)", "min": 0.5, "max": 10, "step": 0.1},
        ] + common

    return common


@router.post("/parse", response_model=DesignResult)
async def parse_design_prompt(prompt: DesignPrompt):
    return parse_prompt(prompt.prompt, prompt.printer)
