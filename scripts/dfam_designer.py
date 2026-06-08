#!/usr/bin/env python3
"""
DfAM Designer — Pro-Level Parametric Part Generator
Auto-applies Design-for-Additive-Manufacturing rules.

Part types:
    bracket, enclosure, gear, snap_fit_clip, tolerance_gauge, heatset_boss

Usage:
    python dfam_designer.py bracket --width 60 --height 40 --depth 25 --load 10 --material PETG -o bracket.stl
    python dfam_designer.py enclosure --width 80 --depth 60 --height 40 --wall 2 --lid snap -o box.stl
    python dfam_designer.py gear --teeth 20 --module 1 --material PLA -o gear.stl
    python dfam_designer.py snap_fit --length 30 --deflection 2 --material PETG -o clip.stl

Requirements:
    pip install trimesh numpy scipy
"""

import argparse
import math
import sys
from pathlib import Path

try:
    import numpy as np
    import trimesh
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install trimesh numpy scipy")
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


def _bounded_float(val, min_v, max_v, name):
    if val is not None and not (min_v <= val <= max_v):
        raise ValueError(f"{name} must be between {min_v} and {max_v}")
    return val


def _bounded_int(val, min_v, max_v, name):
    if val is not None and not (min_v <= val <= max_v):
        raise ValueError(f"{name} must be between {min_v} and {max_v}")
    return val

# ── DfAM Rules Database ──────────────────────────────────────────────────────

MATERIAL_PROPS = {
    'PLA':    {'sigma': 35,  'E': 3500, 'temp_max': 55,  'uv_ok': False, 'chem_ok': False},
    'PETG':   {'sigma': 45,  'E': 2800, 'temp_max': 75,  'uv_ok': False, 'chem_ok': True},
    'ABS':    {'sigma': 40,  'E': 2300, 'temp_max': 90,  'uv_ok': False, 'chem_ok': True},
    'ASA':    {'sigma': 42,  'E': 2400, 'temp_max': 95,  'uv_ok': True,  'chem_ok': True},
    'PC':     {'sigma': 65,  'E': 2400, 'temp_max': 115, 'uv_ok': True,  'chem_ok': True},
    'Nylon':  {'sigma': 50,  'E': 1800, 'temp_max': 100, 'uv_ok': True,  'chem_ok': True},
    'TPU':    {'sigma': 25,  'E': 80,   'temp_max': 70,  'uv_ok': False, 'chem_ok': False},
    'Resin':  {'sigma': 55,  'E': 3500, 'temp_max': 60,  'uv_ok': False, 'chem_ok': False},
}

DESIGN_RULES = {
    'FDM': {
        'min_wall': 0.8,
        'rec_wall': 1.5,
        'func_wall': 2.5,
        'overhang': 45,
        'bridge': 10,
        'layer_h': 0.2,
        'hole_tol': 0.3,
        'peg_tol': -0.1,
        'clearance': 0.3,
        'min_feature': 0.8,
    },
    'SLA': {
        'min_wall': 0.5,
        'rec_wall': 1.0,
        'func_wall': 1.5,
        'overhang': 30,
        'bridge': 3,
        'layer_h': 0.05,
        'hole_tol': 0.2,
        'peg_tol': -0.05,
        'clearance': 0.2,
        'min_feature': 0.3,
    },
}


def apply_fillet(mesh, radius, segments=8):
    """Approximate fillet by subdivision + Taubin smoothing.

    Real fillets require a true CAD kernel (OpenSCAD, CadQuery, FreeCAD).
    This lightweight fallback subdivides the mesh and smooths sharp edges,
    producing a rounded-edge approximation suitable for visualisation and
    coarse DfAM checks.
    """
    if radius <= 0 or len(mesh.faces) == 0:
        return mesh

    try:
        # Subdivide to give the smoother enough vertices to work with
        subdivided = mesh.subdivide()
    except Exception:
        subdivided = mesh.copy()

    try:
        import trimesh.smoothing
        smoothed = subdivided.copy()
        trimesh.smoothing.filter_taubin(
            smoothed, lamb=0.5, nu=0.53, iterations=max(1, segments // 2)
        )
        return smoothed
    except Exception:
        # Fallback: return subdivided mesh (better than nothing)
        return subdivided


def _boolean_union(a, b, engines=None):
    """Union with fallback across boolean engines."""
    if engines is None:
        engines = ['manifold', 'blender', 'scad']
    for engine in engines:
        try:
            return a.union(b, engine=engine)
        except Exception:
            continue
    # Fallback: concatenate (non-manifold but preserves geometry)
    return trimesh.util.concatenate([a, b])


def _boolean_difference(a, b, engines=None):
    """Difference with fallback across boolean engines."""
    if engines is None:
        engines = ['manifold', 'blender', 'scad']
    for engine in engines:
        try:
            return a.difference(b, engine=engine)
        except Exception:
            continue
    raise RuntimeError(
        "Boolean difference failed. Install manifold3d (`pip install manifold3d`), "
        "Blender, or OpenSCAD."
    )


def save_mesh(mesh, filepath):
    filepath = _validate_output_path(filepath)
    ext = Path(filepath).suffix.lower()
    if ext == '.stl':
        mesh.export(filepath, file_type='stl')
    elif ext == '.obj':
        mesh.export(filepath, file_type='obj')
    elif ext == '.3mf':
        try:
            mesh.export(filepath, file_type='3mf')
        except Exception:
            fp = filepath.replace('.3mf', '.stl')
            mesh.export(fp, file_type='stl')
            print(f"3MF failed, saved {fp}")
            return
    else:
        mesh.export(filepath)
    print(f"Saved: {filepath}")
    print(f"  Extents (mm): {mesh.extents.round(2).tolist()}")
    print(f"  Volume (mm³): {mesh.volume:.2f}")
    print(f"  Faces: {len(mesh.faces):,}")


# ── Part Generators ──────────────────────────────────────────────────────────

def make_bracket(width=60, height=40, depth=25, thickness=None, hole_d=4.3,
                 load_kg=5, material='PETG', tech='FDM'):
    """L-bracket with stress-relief ribs and DfAM auto-rules."""
    rules = DESIGN_RULES[tech]
    mat = MATERIAL_PROPS.get(material, MATERIAL_PROPS['PETG'])

    # Auto-thickness based on load
    if thickness is None:
        thickness = max(rules['rec_wall'], rules['func_wall'] * (load_kg / 10))
        thickness = round(thickness, 1)

    # Base plate
    base = trimesh.primitives.Box(extents=[width, depth, thickness])
    base.apply_translation([0, 0, thickness / 2])

    # Vertical wall
    wall = trimesh.primitives.Box(extents=[width, thickness, height])
    wall.apply_translation([0, -depth / 2 + thickness / 2, height / 2])

    # Gusset / rib (triangular support as rotated box)
    rib_h = height * 0.5
    rib_d = depth * 0.5
    rib_thick = thickness
    rib_count = max(1, int(width / 30))

    ribs = []
    for i in range(rib_count):
        x = -width / 2 + (width / (rib_count + 1)) * (i + 1)
        # Diagonal rib box
        rib_len = math.hypot(rib_d, rib_h)
        rib = trimesh.primitives.Box(extents=[rib_thick, rib_len, thickness])
        # Rotate to align with diagonal
        angle = math.atan2(rib_h, rib_d)
        rib.apply_transform(trimesh.transformations.rotation_matrix(
            angle, [1, 0, 0], point=[0, 0, 0]))
        rib.apply_translation([x, -depth / 2 + thickness + rib_d / 2, thickness + rib_h / 2])
        ribs.append(rib)

    # Union all parts via boolean
    bracket = _boolean_union(base, wall)
    for rib in ribs:
        bracket = _boolean_union(bracket, rib)

    # Mounting holes with tolerance
    hole_r = (hole_d + rules['hole_tol']) / 2
    hole_h = thickness + 2
    hole = trimesh.primitives.Cylinder(radius=hole_r, height=hole_h)
    hole.apply_translation([0, 0, thickness / 2])
    bracket = _boolean_difference(bracket, hole)

    # Wall mounting holes
    wall_hole = trimesh.primitives.Cylinder(radius=hole_r, height=height + 2)
    wall_hole.apply_translation([0, -depth / 2 + thickness / 2, height / 2])
    bracket = _boolean_difference(bracket, wall_hole)

    # Report
    print(f"\n[BRACKET DESIGN REPORT]")
    print(f"  Load target: {load_kg} kg")
    print(f"  Material: {material} (σ={mat['sigma']} MPa)")
    print(f"  Wall thickness: {thickness} mm")
    print(f"  Rib count: {rib_count}")
    print(f"  Hole tolerance: +{rules['hole_tol']} mm")

    return bracket


def make_enclosure(width=80, depth=60, height=40, wall=None, lid='snap',
                   pcb_mount=False, tech='FDM'):
    """Hollow enclosure with optional snap lid and PCB standoffs."""
    rules = DESIGN_RULES[tech]
    if wall is None:
        wall = rules['rec_wall']

    outer = trimesh.primitives.Box(extents=[width, depth, height])
    inner = trimesh.primitives.Box(extents=[width - wall * 2, depth - wall * 2, height])
    inner.apply_translation([0, 0, wall / 2])
    box = _boolean_difference(outer, inner)

    # Snap-fit lid groove (simple channel)
    if lid == 'snap':
        groove = trimesh.primitives.Box(extents=[width + 2, 2, 2])
        groove.apply_translation([0, depth / 2, height - wall - 1])
        box = _boolean_difference(box, groove)

    # PCB standoffs (M3 holes)
    if pcb_mount:
        standoff_d = 6
        standoff_h = height - wall - 2
        hole_d = 3.0 + rules['hole_tol']
        offsets = [(width / 2 - 10, depth / 2 - 10),
                   (-width / 2 + 10, depth / 2 - 10),
                   (width / 2 - 10, -depth / 2 + 10),
                   (-width / 2 + 10, -depth / 2 + 10)]
        for ox, oy in offsets:
            standoff = trimesh.primitives.Cylinder(radius=standoff_d / 2, height=standoff_h)
            standoff.apply_translation([ox, oy, standoff_h / 2 + wall])
            box = _boolean_union(box, standoff)
            hole = trimesh.primitives.Cylinder(radius=hole_d / 2, height=standoff_h + 2)
            hole.apply_translation([ox, oy, standoff_h / 2 + wall])
            box = _boolean_difference(box, hole)

    # Vent holes (if not resin)
    if tech == 'FDM':
        vent = trimesh.primitives.Cylinder(radius=4, height=wall + 2)
        for i in range(3):
            v = vent.copy()
            v.apply_translation([-width / 2, -10 + i * 10, height / 2])
            box = _boolean_difference(box, v)

    print(f"\n[ENCLOSURE DESIGN REPORT]")
    print(f"  Wall thickness: {wall} mm")
    print(f"  Lid type: {lid}")
    print(f"  PCB mounts: {pcb_mount}")

    return box


def make_gear(teeth=20, module=1, thickness=5, material='PLA', tech='FDM'):
    """Spur gear with true involute profile and backlash compensation."""
    rules = DESIGN_RULES[tech]
    pressure_angle = math.radians(20)
    backlash = 0.1 if tech == 'FDM' else 0.05

    pitch_radius = module * teeth / 2
    tip_radius = pitch_radius + module
    root_radius = max(pitch_radius - 1.25 * module, module)
    base_radius = pitch_radius * math.cos(pressure_angle)

    # Tooth half-angle at pitch circle
    tooth_half_angle = math.pi / (2 * teeth)
    # Backlash: reduce tooth thickness symmetrically
    backlash_angle = backlash / (2 * pitch_radius) if pitch_radius > 0 else 0
    effective_half_angle = tooth_half_angle - backlash_angle

    inv_pressure_angle = math.tan(pressure_angle) - pressure_angle

    profile_points = []

    for i in range(teeth):
        tooth_angle = i * 2 * math.pi / teeth
        next_tooth_angle = ((i + 1) % teeth) * 2 * math.pi / teeth
        r_min = max(root_radius, base_radius)
        r_max = tip_radius
        n_flank = max(8, teeth)

        # Root arc from previous tooth's right root to this tooth's left root
        if i > 0:
            prev_tooth_angle = ((i - 1) % teeth) * 2 * math.pi / teeth
            if root_radius < base_radius:
                prev_right_root = prev_tooth_angle + (effective_half_angle + inv_pressure_angle)
                this_left_root = tooth_angle - (effective_half_angle + inv_pressure_angle)
            else:
                alpha_root = math.acos(base_radius / root_radius)
                inv_alpha_root = math.tan(alpha_root) - alpha_root
                prev_right_root = prev_tooth_angle + (effective_half_angle + inv_pressure_angle - inv_alpha_root)
                this_left_root = tooth_angle - (effective_half_angle + inv_pressure_angle - inv_alpha_root)
            n_root = max(3, teeth // 2)
            root_angles = np.linspace(prev_right_root, this_left_root, n_root)
            for ra in root_angles[1:]:
                profile_points.append([
                    root_radius * math.cos(ra),
                    root_radius * math.sin(ra)
                ])

        # Radial line from left root to left base (if root < base)
        if root_radius < base_radius:
            theta_left_root = tooth_angle - (effective_half_angle + inv_pressure_angle)
            profile_points.append([
                root_radius * math.cos(theta_left_root),
                root_radius * math.sin(theta_left_root)
            ])

        # Left flank: base to tip (CCW, increasing angle)
        rs = np.linspace(r_min, r_max, n_flank)
        for r in rs:
            alpha = math.acos(base_radius / r)
            inv_alpha = math.tan(alpha) - alpha
            half_angle = effective_half_angle + inv_pressure_angle - inv_alpha
            theta = tooth_angle - half_angle
            profile_points.append([
                r * math.cos(theta),
                r * math.sin(theta)
            ])

        # Tip centre point for smoother tip arc
        profile_points.append([
            tip_radius * math.cos(tooth_angle),
            tip_radius * math.sin(tooth_angle)
        ])

        # Right flank: tip to base (CCW, increasing angle)
        for r in reversed(rs):
            alpha = math.acos(base_radius / r)
            inv_alpha = math.tan(alpha) - alpha
            half_angle = effective_half_angle + inv_pressure_angle - inv_alpha
            theta = tooth_angle + half_angle
            profile_points.append([
                r * math.cos(theta),
                r * math.sin(theta)
            ])

        # Radial line from right base to right root (if root < base)
        if root_radius < base_radius:
            theta_right_root = tooth_angle + (effective_half_angle + inv_pressure_angle)
            profile_points.append([
                root_radius * math.cos(theta_right_root),
                root_radius * math.sin(theta_right_root)
            ])

    # Close polygon with root arc from last tooth back to first tooth
    if teeth > 0:
        last_tooth_angle = (teeth - 1) * 2 * math.pi / teeth
        first_tooth_angle = 0
        if root_radius < base_radius:
            last_right_root = last_tooth_angle + (effective_half_angle + inv_pressure_angle)
            first_left_root = first_tooth_angle - (effective_half_angle + inv_pressure_angle)
        else:
            alpha_root = math.acos(base_radius / root_radius)
            inv_alpha_root = math.tan(alpha_root) - alpha_root
            last_right_root = last_tooth_angle + (effective_half_angle + inv_pressure_angle - inv_alpha_root)
            first_left_root = first_tooth_angle - (effective_half_angle + inv_pressure_angle - inv_alpha_root)
        n_root = max(3, teeth // 2)
        root_angles = np.linspace(last_right_root, first_left_root + 2 * math.pi, n_root)
        for ra in root_angles[1:]:
            profile_points.append([
                root_radius * math.cos(ra),
                root_radius * math.sin(ra)
            ])

    pts = np.array(profile_points)
    from shapely.geometry import Polygon
    poly = Polygon(pts)
    # Simplify to remove near-collinear points that cause degenerate triangles
    poly = poly.simplify(0.01, preserve_topology=True)
    gear = trimesh.creation.extrude_polygon(poly, height=thickness)
    gear.apply_translation([0, 0, thickness / 2])

    # Bore hole with tolerance
    bore_d = 8 + rules['hole_tol']
    bore = trimesh.primitives.Cylinder(radius=bore_d / 2, height=thickness + 2)
    gear = _boolean_difference(gear, bore)

    print(f"\n[GEAR DESIGN REPORT]")
    print(f"  Module: {module}")
    print(f"  Teeth: {teeth}")
    print(f"  Pitch diameter: {pitch_radius * 2:.2f} mm")
    print(f"  Outer diameter: {tip_radius * 2:.2f} mm")
    print(f"  Backlash applied: {backlash} mm")

    return gear


def make_snap_fit(length=30, width=10, thickness=2, deflection=2, material='PETG', tech='FDM'):
    """Cantilever snap-fit hook with strain-limited design."""
    rules = DESIGN_RULES[tech]
    mat = MATERIAL_PROPS.get(material, MATERIAL_PROPS['PETG'])

    # Strain limit: ε = 1.5 * y * h / L² (cantilever beam)
    # Solve for thickness h given deflection y and allowed strain
    epsilon_max = 0.02  # 2% strain typical for plastics
    L = length
    y = deflection
    h = math.sqrt(2 * y * L / (3 * epsilon_max))
    h = max(h, rules['min_feature'] * 2)
    h = round(h, 2)

    # Base + arm + hook
    base = trimesh.primitives.Box(extents=[width + 4, 6, h])
    arm = trimesh.primitives.Box(extents=[width, length, h])
    arm.apply_translation([0, length / 2, 0])

    hook = trimesh.primitives.Box(extents=[width, 4, h + deflection])
    hook.apply_translation([0, length + 2, deflection / 2])

    clip = trimesh.util.concatenate([base, arm, hook])

    print(f"\n[SNAP-FIT DESIGN REPORT]")
    print(f"  Material: {material} (ε_allow ≈ 2%)")
    print(f"  Arm length: {length} mm")
    print(f"  Thickness: {h} mm")
    print(f"  Deflection: {deflection} mm")
    print(f"  Estimated strain: {1.5 * y * h / L**2:.3f}")

    return clip


def make_heatset_boss(insert='M3', tech='FDM'):
    """Heat-set insert boss with optimal hole size and wall thickness."""
    rules = DESIGN_RULES[tech]
    specs = {
        'M2':  {'insert_od': 3.2, 'insert_len': 3.0, 'hole_d': 2.3},
        'M2.5': {'insert_od': 3.9, 'insert_len': 3.5, 'hole_d': 2.8},
        'M3':   {'insert_od': 4.6, 'insert_len': 4.0, 'hole_d': 3.3},
        'M4':   {'insert_od': 5.6, 'insert_len': 5.5, 'hole_d': 4.3},
    }
    s = specs.get(insert, specs['M3'])
    wall = max(rules['rec_wall'], s['insert_od'] / 2 + 1.0)
    boss_od = s['insert_od'] + wall * 2
    boss_h = s['insert_len'] + 2

    boss = trimesh.primitives.Cylinder(radius=boss_od / 2, height=boss_h)
    hole = trimesh.primitives.Cylinder(radius=s['hole_d'] / 2, height=boss_h + 2)
    boss = _boolean_difference(boss, hole)

    # Anti-rotation knurls (small protrusions)
    for i in range(6):
        angle = i * np.pi / 3
        knurl = trimesh.primitives.Box(extents=[1.5, 1, boss_h - 2])
        x = (boss_od / 2) * np.cos(angle)
        y = (boss_od / 2) * np.sin(angle)
        knurl.apply_translation([x, y, 0])
        boss = _boolean_union(boss, knurl)

    print(f"\n[HEAT-SET BOSS REPORT]")
    print(f"  Insert: {insert}")
    print(f"  Boss OD: {boss_od:.1f} mm")
    print(f"  Boss height: {boss_h:.1f} mm")
    print(f"  Hole diameter: {s['hole_d']} mm")

    return boss


def make_tolerance_gauge(min_d=5.0, max_d=5.5, steps=6, height=10, tech='FDM'):
    """Tolerance test gauge with pegs and matching holes using DfAM tolerances."""
    rules = DESIGN_RULES[tech]
    meshes = []
    spacing = 12.0

    for i in range(steps):
        d = min_d + i * (max_d - min_d) / max(1, steps - 1)
        # Peg: apply peg_tol (undersized for printed peg compensation)
        peg_d = d + rules['peg_tol']
        peg = trimesh.primitives.Cylinder(radius=peg_d / 2, height=height)
        peg.apply_translation([i * spacing, 0, height / 2])
        meshes.append(peg)

        block = trimesh.primitives.Box(extents=[10, 10, height])
        block.apply_translation([i * spacing, 20, height / 2])
        # Hole: apply hole_tol for clearance fit
        hole_d = min_d + rules['hole_tol'] + i * (max_d - min_d) / max(1, steps - 1)
        hole = trimesh.primitives.Cylinder(radius=hole_d / 2, height=height + 2)
        hole.apply_translation([i * spacing, 20, height / 2])
        block = _boolean_difference(block, hole)
        meshes.append(block)

    return trimesh.util.concatenate(meshes)


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='DfAM Parametric Part Designer')
    subparsers = parser.add_subparsers(dest='command', required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--material', default='PETG', choices=list(MATERIAL_PROPS.keys()))
    common.add_argument('--tech', default='FDM', choices=['FDM', 'SLA'])
    common.add_argument('-o', '--output', default='part.stl')

    # Bracket
    bracket_p = subparsers.add_parser('bracket', parents=[common])
    bracket_p.add_argument('--width', type=float, default=60)
    bracket_p.add_argument('--height', type=float, default=40)
    bracket_p.add_argument('--depth', type=float, default=25)
    bracket_p.add_argument('--thickness', type=float, default=None)
    bracket_p.add_argument('--hole-d', type=float, default=4.3)
    bracket_p.add_argument('--load', type=float, default=5, help='Expected load in kg')

    # Enclosure
    enc_p = subparsers.add_parser('enclosure', parents=[common])
    enc_p.add_argument('--width', type=float, default=80)
    enc_p.add_argument('--depth', type=float, default=60)
    enc_p.add_argument('--height', type=float, default=40)
    enc_p.add_argument('--wall', type=float, default=None)
    enc_p.add_argument('--lid', default='snap', choices=['snap', 'screw', 'none'])
    enc_p.add_argument('--pcb-mount', action='store_true')

    # Gear
    gear_p = subparsers.add_parser('gear', parents=[common])
    gear_p.add_argument('--teeth', type=int, default=20)
    gear_p.add_argument('--module', type=float, default=1.0)
    gear_p.add_argument('--thickness', type=float, default=5)

    # Snap fit
    snap_p = subparsers.add_parser('snap_fit', parents=[common])
    snap_p.add_argument('--length', type=float, default=30)
    snap_p.add_argument('--width', type=float, default=10)
    snap_p.add_argument('--thickness', type=float, default=2)
    snap_p.add_argument('--deflection', type=float, default=2)

    # Heat-set boss
    boss_p = subparsers.add_parser('heatset_boss', parents=[common])
    boss_p.add_argument('--insert', default='M3', choices=['M2', 'M2.5', 'M3', 'M4'])

    # Tolerance gauge
    gauge_p = subparsers.add_parser('tolerance_gauge')
    gauge_p.add_argument('--min-d', type=float, default=5.0)
    gauge_p.add_argument('--max-d', type=float, default=5.5)
    gauge_p.add_argument('--steps', type=int, default=6)
    gauge_p.add_argument('--height', type=float, default=10)
    gauge_p.add_argument('--tech', default='FDM', choices=['FDM', 'SLA'])
    gauge_p.add_argument('-o', '--output', default='gauge.stl')

    args = parser.parse_args()

    # Validate output path
    try:
        args.output = _validate_output_path(args.output)
    except ValueError as e:
        parser.error(str(e))

    # Validate numeric bounds
    try:
        if args.command == 'bracket':
            _bounded_float(args.width, 1, 500, "width")
            _bounded_float(args.height, 1, 500, "height")
            _bounded_float(args.depth, 1, 500, "depth")
            if args.thickness is not None:
                _bounded_float(args.thickness, 0.1, 50, "thickness")
            _bounded_float(args.hole_d, 1, 50, "hole-d")
            _bounded_float(args.load, 0, 100, "load")
        elif args.command == 'enclosure':
            _bounded_float(args.width, 1, 500, "width")
            _bounded_float(args.height, 1, 500, "height")
            _bounded_float(args.depth, 1, 500, "depth")
            if args.wall is not None:
                _bounded_float(args.wall, 0.1, 50, "wall")
        elif args.command == 'gear':
            _bounded_int(args.teeth, 5, 200, "teeth")
            _bounded_float(args.module, 0.1, 10, "module")
            _bounded_float(args.thickness, 0.1, 50, "thickness")
        elif args.command == 'snap_fit':
            _bounded_float(args.length, 1, 200, "length")
            _bounded_float(args.width, 1, 50, "width")
            _bounded_float(args.thickness, 0.1, 50, "thickness")
            _bounded_float(args.deflection, 0.1, 20, "deflection")
        elif args.command == 'tolerance_gauge':
            _bounded_float(args.min_d, 0.1, 100, "min-d")
            _bounded_float(args.max_d, 0.1, 100, "max-d")
            _bounded_int(args.steps, 1, 50, "steps")
            _bounded_float(args.height, 1, 500, "height")
    except ValueError as e:
        parser.error(str(e))

    if args.command == 'bracket':
        mesh = make_bracket(args.width, args.height, args.depth, args.thickness,
                            args.hole_d, args.load, args.material, args.tech)
    elif args.command == 'enclosure':
        mesh = make_enclosure(args.width, args.depth, args.height, args.wall,
                              args.lid, args.pcb_mount, args.tech)
    elif args.command == 'gear':
        mesh = make_gear(args.teeth, args.module, args.thickness, args.material, args.tech)
    elif args.command == 'snap_fit':
        mesh = make_snap_fit(args.length, args.width, args.thickness,
                             args.deflection, args.material, args.tech)
    elif args.command == 'heatset_boss':
        mesh = make_heatset_boss(args.insert, args.tech)
    elif args.command == 'tolerance_gauge':
        mesh = make_tolerance_gauge(args.min_d, args.max_d, args.steps, args.height, args.tech)
    else:
        parser.print_help()
        sys.exit(1)

    save_mesh(mesh, args.output)


if __name__ == '__main__':
    main()
