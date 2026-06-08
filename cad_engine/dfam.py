"""Design-for-Additive-Manufacturing rules engine."""

import math


DESIGN_RULES = {
    "FDM": {
        "min_wall_mm": 0.8,
        "rec_wall_mm": 1.5,
        "func_wall_mm": 2.5,
        "overhang_deg": 45,
        "bridge_mm": 10,
        "layer_h_mm": 0.2,
        "hole_tol_mm": 0.3,
        "peg_tol_mm": -0.1,
        "clearance_mm": 0.3,
        "min_feature_mm": 0.8,
        "embossed_min_mm": 1.0,
    },
    "SLA": {
        "min_wall_mm": 0.5,
        "rec_wall_mm": 1.0,
        "func_wall_mm": 1.5,
        "overhang_deg": 30,
        "bridge_mm": 3,
        "layer_h_mm": 0.05,
        "hole_tol_mm": 0.2,
        "peg_tol_mm": -0.05,
        "clearance_mm": 0.2,
        "min_feature_mm": 0.3,
        "embossed_min_mm": 0.5,
    },
}


def recommend_wall_thickness(load_kg: float, material: str, tech: str = "FDM") -> float:
    """Auto-select wall thickness based on load and material."""
    rules = DESIGN_RULES[tech]
    base = rules["rec_wall_mm"]
    # Scale with load: every 5 kg adds 0.5 mm
    scaled = base + (load_kg / 5.0) * 0.5
    return round(min(scaled, 5.0), 1)


def recommend_infill(load_kg: float, part_type: str) -> dict:
    """Recommend infill density and pattern."""
    if load_kg < 2 or part_type in ["visual", "prototype"]:
        return {"density": 15, "pattern": "gyroid", "label": "Visual"}
    elif load_kg < 10:
        return {"density": 30, "pattern": "gyroid", "label": "General"}
    else:
        return {"density": 50, "pattern": "grid", "label": "Functional"}


def recommend_supports(tech: str, has_overhang: bool = True) -> dict:
    """Recommend support strategy."""
    if tech == "FDM":
        if has_overhang:
            return {"type": "tree", "threshold_deg": 45, "density": 20}
        return {"type": "none", "threshold_deg": 45, "density": 0}
    else:
        return {"type": "heavy", "threshold_deg": 30, "density": 70}


def estimate_print_time(volume_mm3: float, layer_h_mm: float, nozzle_mm: float,
                        speed_mm_s: float = 40, overhead: float = 1.5) -> float:
    """Rough print time in hours."""
    flow_rate = speed_mm_s * nozzle_mm * layer_h_mm
    if flow_rate <= 0:
        return 0.0
    return (volume_mm3 / (flow_rate * 3600)) * overhead


def estimate_cost(volume_mm3: float, density_g_cm3: float, cost_per_kg: float) -> float:
    """Estimate material cost in USD."""
    weight_g = volume_mm3 * density_g_cm3 / 1000
    return weight_g * cost_per_kg / 1000


def snap_fit_thickness(length_mm: float, deflection_mm: float, epsilon_max: float = 0.02) -> float:
    """Cantilever snap-fit thickness from strain limit."""
    if length_mm <= 0 or deflection_mm <= 0:
        raise ValueError("length and deflection must be > 0")
    h = math.sqrt(2 * deflection_mm * length_mm / (3 * epsilon_max))
    return round(max(h, 1.0), 2)


def gear_outer_diameter(module: float, teeth: int) -> float:
    return module * (teeth + 2)


def gear_pitch_diameter(module: float, teeth: int) -> float:
    return module * teeth


def gear_root_diameter(module: float, teeth: int) -> float:
    return module * (teeth - 2.5)
