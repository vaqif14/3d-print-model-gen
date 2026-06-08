#!/usr/bin/env python3
"""
Slicer Autopilot — Auto-Generate Slicer Profiles + Cost Estimates
Outputs ready-to-import profiles for PrusaSlicer, OrcaSlicer, and Cura.

Usage:
    python slicer_autopilot.py model.stl --material PETG --printer ender3 -o profile.ini
    python slicer_autopilot.py model.stl --material PLA --printer prusa --tech SLA

Requirements:
    pip install trimesh numpy
"""

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import trimesh
except ImportError as e:
    print(f"Missing dependency: {e}")
    sys.exit(1)


def _validate_output_path(path_str: str) -> str:
    """Ensure output path does not traverse outside cwd or output/."""
    if ".." in path_str:
        raise ValueError(f"Path traversal not allowed: {path_str}")
    path = Path(path_str).resolve()
    cwd = Path.cwd().resolve()
    if path.is_absolute():
        if not (path == cwd or path.is_relative_to(cwd)):
            raise ValueError(f"Absolute path outside project not allowed: {path_str}")
    if not (path == cwd or path.is_relative_to(cwd)):
        raise ValueError(f"Output must be within project directory: {path_str}")
    return str(path)

# ── Constants ────────────────────────────────────────────────────────────────

# Rough overhead multiplier for travel moves, acceleration ramps, first layer
# slowdown, and other non-extrusion time in a typical FDM print.
TIME_OVERHEAD_FACTOR = 1.5

# ── Database ─────────────────────────────────────────────────────────────────

MATERIAL_PROFILES = {
    'PLA': {
        'nozzle_temp': 210, 'bed_temp': 60, 'fan_speed': 100,
        'retract_length': 0.8, 'retract_speed': 35,
        'print_speed': 60, 'wall_speed': 45, 'first_layer_speed': 20,
        'cost_per_kg': 20.0, 'density': 1.24,
    },
    'PETG': {
        'nozzle_temp': 240, 'bed_temp': 80, 'fan_speed': 30,
        'retract_length': 1.2, 'retract_speed': 35,
        'print_speed': 50, 'wall_speed': 40, 'first_layer_speed': 20,
        'cost_per_kg': 25.0, 'density': 1.27,
    },
    'ABS': {
        'nozzle_temp': 240, 'bed_temp': 105, 'fan_speed': 0,
        'retract_length': 1.0, 'retract_speed': 40,
        'print_speed': 55, 'wall_speed': 45, 'first_layer_speed': 20,
        'cost_per_kg': 22.0, 'density': 1.04,
    },
    'ASA': {
        'nozzle_temp': 250, 'bed_temp': 100, 'fan_speed': 20,
        'retract_length': 1.0, 'retract_speed': 40,
        'print_speed': 55, 'wall_speed': 45, 'first_layer_speed': 20,
        'cost_per_kg': 28.0, 'density': 1.07,
    },
    'TPU': {
        'nozzle_temp': 220, 'bed_temp': 50, 'fan_speed': 50,
        'retract_length': 3.0, 'retract_speed': 25,
        'print_speed': 30, 'wall_speed': 25, 'first_layer_speed': 15,
        'cost_per_kg': 35.0, 'density': 1.21,
    },
    'Nylon': {
        'nozzle_temp': 260, 'bed_temp': 90, 'fan_speed': 30,
        'retract_length': 1.5, 'retract_speed': 35,
        'print_speed': 45, 'wall_speed': 40, 'first_layer_speed': 18,
        'cost_per_kg': 45.0, 'density': 1.14,
    },
    'PC': {
        'nozzle_temp': 280, 'bed_temp': 110, 'fan_speed': 30,
        'retract_length': 1.5, 'retract_speed': 40,
        'print_speed': 40, 'wall_speed': 35, 'first_layer_speed': 15,
        'cost_per_kg': 50.0, 'density': 1.20,
    },
}

PRINTER_PROFILES = {
    'ender3': {'nozzle': 0.4, 'bed_x': 220, 'bed_y': 220, 'bed_z': 250, 'accel': 500},
    'prusa':  {'nozzle': 0.4, 'bed_x': 250, 'bed_y': 210, 'bed_z': 220, 'accel': 1000},
    'bambu':  {'nozzle': 0.4, 'bed_x': 256, 'bed_y': 256, 'bed_z': 256, 'accel': 10000},
    'p1s':    {'nozzle': 0.4, 'bed_x': 256, 'bed_y': 256, 'bed_z': 256, 'accel': 20000},
    'p2s':    {'nozzle': 0.4, 'bed_x': 256, 'bed_y': 256, 'bed_z': 256, 'accel': 20000},
    'voron':  {'nozzle': 0.4, 'bed_x': 300, 'bed_y': 300, 'bed_z': 300, 'accel': 3000},
}

INFILL_PRESETS = {
    'visual':     {'density': 15, 'pattern': 'gyroid', 'walls': 2, 'top_layers': 3},
    'prototype':  {'density': 25, 'pattern': 'gyroid', 'walls': 2, 'top_layers': 3},
    'functional': {'density': 50, 'pattern': 'grid',   'walls': 3, 'top_layers': 4},
    'structural': {'density': 80, 'pattern': 'triangles', 'walls': 4, 'top_layers': 5},
}


def estimate_time_volume(mesh, layer_h, nozzle, infill_density, print_speed, wall_speed):
    """Rough time estimate based on extruded volume and speeds."""
    # Use mesh volume directly; for hollow models this is already correct
    # Add infill overhead: solid parts print slower due to more material
    total_vol = mesh.volume * (0.3 + 0.7 * (infill_density / 100))

    # Average extrusion speed in mm³/s
    flow_rate = print_speed * nozzle * layer_h  # mm³/s
    flow_rate = max(flow_rate, 0.1)

    # Pure extrusion time + overhead (travel, accel, first layer, etc.)
    time_hours = (total_vol / (flow_rate * 3600)) * TIME_OVERHEAD_FACTOR
    return total_vol, time_hours


def generate_prusa_orca_profile(mesh, material, printer, infill_preset, layer_h, output):
    """Generate PrusaSlicer / OrcaSlicer compatible INI profile."""
    mat = MATERIAL_PROFILES.get(material, MATERIAL_PROFILES['PLA'])
    pr = PRINTER_PROFILES.get(printer, PRINTER_PROFILES['ender3'])
    inf = INFILL_PRESETS.get(infill_preset, INFILL_PRESETS['prototype'])

    total_vol, est_time = estimate_time_volume(
        mesh, layer_h, pr['nozzle'], inf['density'], mat['print_speed'], mat['wall_speed']
    )

    # Weight and cost
    weight_g = total_vol * mat['density'] / 1000
    cost = weight_g / 1000 * mat['cost_per_kg']

    profile = f"""; Auto-generated by Slicer Autopilot
; Material: {material}
; Printer: {printer}
; Estimated weight: {weight_g:.1f} g
; Estimated cost: ${cost:.2f}
; Estimated time: {est_time:.1f} h

[print]
layer_height = {layer_h}
first_layer_height = {layer_h * 1.2:.2f}
perimeters = {inf['walls']}
top_solid_layers = {inf['top_layers']}
bottom_solid_layers = {inf['top_layers']}
fill_density = {inf['density']}%
fill_pattern = {inf['pattern']}

[material]
temperature = {mat['nozzle_temp']}
bed_temperature = {mat['bed_temp']}
fan_speed = {mat['fan_speed']}%
retract_length = {mat['retract_length']}
retract_speed = {mat['retract_speed']}

[speed]
perimeter_speed = {mat['wall_speed'] * 60}
infill_speed = {mat['print_speed'] * 60}
first_layer_speed = {mat['first_layer_speed'] * 60}
acceleration = {pr['accel']}
"""

    Path(output).write_text(profile)
    print(f"Profile saved: {output}")
    return {
        'volume_mm3': total_vol,
        'weight_g': weight_g,
        'cost_usd': cost,
        'time_hours': est_time,
    }


def generate_cura_profile(mesh, material, printer, infill_preset, layer_h, output):
    """Generate Cura compatible JSON profile (simplified)."""
    mat = MATERIAL_PROFILES.get(material, MATERIAL_PROFILES['PLA'])
    pr = PRINTER_PROFILES.get(printer, PRINTER_PROFILES['ender3'])
    inf = INFILL_PRESETS.get(infill_preset, INFILL_PRESETS['prototype'])

    total_vol, est_time = estimate_time_volume(
        mesh, layer_h, pr['nozzle'], inf['density'], mat['print_speed'], mat['wall_speed']
    )
    weight_g = total_vol * mat['density'] / 1000
    cost = weight_g / 1000 * mat['cost_per_kg']

    data = {
        "name": f"{material}_{printer}_auto",
        "version": 2,
        "settings": {
            "layer_height": {"value": layer_h},
            "layer_height_0": {"value": round(layer_h * 1.2, 2)},
            "wall_line_count": {"value": inf['walls']},
            "top_layers": {"value": inf['top_layers']},
            "bottom_layers": {"value": inf['top_layers']},
            "infill_sparse_density": {"value": inf['density']},
            "infill_pattern": {"value": inf['pattern'].upper()},
            "material_print_temperature": {"value": mat['nozzle_temp']},
            "material_bed_temperature": {"value": mat['bed_temp']},
            "cool_fan_speed": {"value": mat['fan_speed']},
            "retraction_amount": {"value": mat['retract_length']},
            "retraction_speed": {"value": mat['retract_speed']},
            "speed_print": {"value": mat['print_speed']},
            "speed_wall": {"value": mat['wall_speed']},
            "speed_layer_0": {"value": mat['first_layer_speed']},
            "acceleration_enabled": {"value": True},
            "acceleration_print": {"value": pr['accel']},
        },
        "metadata": {
            "estimated_weight_g": round(weight_g, 1),
            "estimated_cost_usd": round(cost, 2),
            "estimated_time_hours": round(est_time, 1),
        }
    }

    Path(output).write_text(json.dumps(data, indent=2))
    print(f"Cura profile saved: {output}")
    return data['metadata']


def recommend_orientation(mesh):
    """Recommend print orientation: maximize flat face on bed, minimize overhangs."""
    # Simple heuristic: try all face normals as 'up' directions, score by flatness + area
    normals = mesh.face_normals
    areas = mesh.area_faces

    best_score = -1
    best_up = np.array([0, 0, 1])

    # Sample dominant directions
    candidate_dirs = [np.array([0, 0, 1]), np.array([0, 0, -1]),
                      np.array([0, 1, 0]), np.array([0, -1, 0]),
                      np.array([1, 0, 0]), np.array([-1, 0, 0])]

    # Add face normals of largest faces
    top_faces = np.argsort(areas)[-20:]
    for fi in top_faces:
        candidate_dirs.append(normals[fi])

    for up in candidate_dirs:
        up = up / (np.linalg.norm(up) + 1e-12)
        # Project face normals against up
        cos_angles = np.dot(normals, up)
        # Flat faces have cos ≈ ±1
        flatness = np.sum(areas * np.abs(cos_angles))
        # Overhangs: faces pointing down (cos < -0.7)
        overhang_area = np.sum(areas[cos_angles < -0.7])
        score = flatness - overhang_area * 2
        if score > best_score:
            best_score = score
            best_up = up

    print(f"Recommended orientation: Z-axis aligned with [{best_up[0]:.2f}, {best_up[1]:.2f}, {best_up[2]:.2f}]")
    print(f"  (Place this direction pointing UP in your slicer)")
    return best_up


def main():
    parser = argparse.ArgumentParser(description='Slicer Autopilot')
    parser.add_argument('input', help='Input mesh file')
    parser.add_argument('--material', default='PETG', choices=list(MATERIAL_PROFILES.keys()))
    parser.add_argument('--printer', default='ender3', choices=list(PRINTER_PROFILES.keys()))
    parser.add_argument('--infill', default='prototype', choices=list(INFILL_PRESETS.keys()))
    parser.add_argument('--layer-height', type=float, default=0.2)
    parser.add_argument('--format', default='prusa', choices=['prusa', 'cura'])
    parser.add_argument('-o', '--output', default=None)

    args = parser.parse_args()

    if args.output is not None:
        try:
            args.output = _validate_output_path(args.output)
        except ValueError as e:
            parser.error(str(e))

    if not (0.05 <= args.layer_height <= 1.0):
        parser.error("layer-height must be between 0.05 and 1.0")

    mesh = trimesh.load_mesh(args.input, force='mesh')
    print(f"Loaded: {args.input} ({len(mesh.faces):,} faces)")

    if args.output is None:
        ext = '.ini' if args.format == 'prusa' else '.json'
        args.output = Path(args.input).stem + '_profile' + ext

    print(f"\n[Slicer Autopilot Report]")
    print(f"  Material: {args.material}")
    print(f"  Printer: {args.printer}")
    print(f"  Infill preset: {args.infill}")
    print(f"  Layer height: {args.layer_height} mm")

    recommend_orientation(mesh)

    if args.format == 'prusa':
        stats = generate_prusa_orca_profile(mesh, args.material, args.printer,
                                            args.infill, args.layer_height, args.output)
    else:
        stats = generate_cura_profile(mesh, args.material, args.printer,
                                      args.infill, args.layer_height, args.output)

    print(f"\n[Print Estimate]")
    print(f"  Filament volume: {stats.get('volume_mm3', stats.get('estimated_weight_g')):.1f}")
    print(f"  Weight: {stats.get('weight_g', stats.get('estimated_weight_g')):.1f} g")
    print(f"  Cost: ${stats.get('cost_usd', stats.get('estimated_cost_usd')):.2f}")
    print(f"  Time: ~{stats.get('time_hours', stats.get('estimated_time_hours')):.1f} hours")


if __name__ == '__main__':
    main()
