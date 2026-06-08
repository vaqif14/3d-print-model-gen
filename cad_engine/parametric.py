"""Parametric part generators using trimesh + manifold3d booleans."""

import math
import io
import trimesh
import numpy as np
from . import dfam


def _save_stl_bytes(mesh: trimesh.Trimesh) -> bytes:
    buf = io.BytesIO()
    mesh.export(buf, file_type='stl')
    return buf.getvalue()


def make_bracket(width: float = 60, height: float = 40, depth: float = 25,
                 thickness: float = None, hole_d: float = 4.3,
                 load_kg: float = 5, material: str = "PETG", tech: str = "FDM") -> trimesh.Trimesh:
    """L-bracket with ribs and mounting holes."""
    if thickness is None:
        thickness = dfam.recommend_wall_thickness(load_kg, material, tech)

    # Base plate
    base = trimesh.primitives.Box(extents=[width, depth, thickness])
    base.apply_translation([0, 0, thickness / 2])

    # Vertical wall
    wall = trimesh.primitives.Box(extents=[width, thickness, height])
    wall.apply_translation([0, -depth / 2 + thickness / 2, height / 2])

    # Union
    bracket = base.union(wall)

    # Ribs
    rib_count = max(1, int(width / 30))
    rib_h = height * 0.5
    rib_d = depth * 0.5
    for i in range(rib_count):
        x = -width / 2 + (width / (rib_count + 1)) * (i + 1)
        rib_len = math.hypot(rib_d, rib_h)
        angle = math.atan2(rib_h, rib_d)
        rib = trimesh.primitives.Box(extents=[thickness, rib_len, thickness])
        rib.apply_transform(trimesh.transformations.rotation_matrix(angle, [1, 0, 0]))
        rib.apply_translation([x, -depth / 2 + thickness + rib_d / 2, thickness + rib_h / 2])
        bracket = bracket.union(rib)

    # Mounting holes
    hole_r = (hole_d + dfam.DESIGN_RULES[tech]['hole_tol_mm']) / 2
    hole = trimesh.primitives.Cylinder(radius=hole_r, height=thickness + 2)
    hole.apply_translation([0, 0, thickness / 2])
    bracket = bracket.difference(hole)

    wall_hole = trimesh.primitives.Cylinder(radius=hole_r, height=height + 2)
    wall_hole.apply_translation([0, -depth / 2 + thickness / 2, height / 2])
    bracket = bracket.difference(wall_hole)

    return bracket


def make_enclosure(width: float = 80, depth: float = 60, height: float = 40,
                   wall: float = 2.0, lid: str = "snap",
                   pcb_mount: bool = False, tech: str = "FDM") -> trimesh.Trimesh:
    """Hollow enclosure with optional PCB standoffs."""
    outer = trimesh.primitives.Box(extents=[width, depth, height])
    inner = trimesh.primitives.Box(extents=[width - wall * 2, depth - wall * 2, height])
    inner.apply_translation([0, 0, wall / 2])
    box = outer.difference(inner)

    if lid == "snap":
        groove = trimesh.primitives.Box(extents=[width + 2, 2, 2])
        groove.apply_translation([0, depth / 2, height - wall - 1])
        box = box.difference(groove)

    if pcb_mount:
        standoff_d = 7.0
        standoff_h = height - wall - 2
        hole_d = 3.3
        offsets = [
            (width / 2 - 10, depth / 2 - 10),
            (-width / 2 + 10, depth / 2 - 10),
            (width / 2 - 10, -depth / 2 + 10),
            (-width / 2 + 10, -depth / 2 + 10),
        ]
        for ox, oy in offsets:
            standoff = trimesh.primitives.Cylinder(radius=standoff_d / 2, height=standoff_h)
            standoff.apply_translation([ox, oy, standoff_h / 2 + wall])
            box = box.union(standoff)
            h = trimesh.primitives.Cylinder(radius=hole_d / 2, height=standoff_h + 2)
            h.apply_translation([ox, oy, standoff_h / 2 + wall])
            box = box.difference(h)

    return box


def make_gear(teeth: int = 20, module: float = 1.0, thickness: float = 5.0,
              bore_d: float = 8.0) -> trimesh.Trimesh:
    """Spur gear with simplified profile."""
    pitch_d = dfam.gear_pitch_diameter(module, teeth)
    outer_d = dfam.gear_outer_diameter(module, teeth)
    root_d = max(dfam.gear_root_diameter(module, teeth), 2.0)

    num_points = teeth * 8
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False)
    radii = []
    for a in angles:
        tooth_phase = (a * teeth) % (2 * np.pi)
        if tooth_phase < np.pi / teeth:
            r = outer_d / 2
        else:
            r = root_d / 2
        radii.append(r)

    radii = np.array(radii)
    xs = radii * np.cos(angles)
    ys = radii * np.sin(angles)
    pts = np.column_stack([xs, ys])

    try:
        from shapely.geometry import Polygon
        poly = Polygon(pts)
        gear = trimesh.creation.extrude_polygon(poly, height=thickness)
    except ImportError:
        # Fallback: manual triangulation
        gear = trimesh.creation.extrude_triangulation(vertices=pts, faces=np.array([[i, (i+1)%num_points, 0] for i in range(1, num_points-1)]), height=thickness)

    gear.apply_translation([0, 0, thickness / 2])

    bore = trimesh.primitives.Cylinder(radius=bore_d / 2, height=thickness + 2)
    gear = gear.difference(bore)
    return gear


def make_snap_fit(length: float = 30, width: float = 10, thickness: float = 2.0,
                  deflection: float = 2.0, material: str = "PETG") -> trimesh.Trimesh:
    """Cantilever snap-fit hook."""
    h = dfam.snap_fit_thickness(length, deflection)
    base = trimesh.primitives.Box(extents=[width + 4, 6, h])
    arm = trimesh.primitives.Box(extents=[width, length, h])
    arm.apply_translation([0, length / 2 + 3, 0])

    hook = trimesh.primitives.Box(extents=[width, 4, h + deflection])
    hook.apply_translation([0, length + 5, deflection / 2])

    clip = base.union(arm).union(hook)
    return clip


def export_stl(mesh: trimesh.Trimesh, filepath: str):
    mesh.export(filepath, file_type='stl')


def export_step(mesh: trimesh.Trimesh, filepath: str):
    # trimesh does not support STEP export natively
    # Fallback to STL with a note
    mesh.export(filepath.replace('.step', '.stl'), file_type='stl')


def to_mesh_bytes(mesh: trimesh.Trimesh) -> bytes:
    buf = io.BytesIO()
    mesh.export(buf, file_type='stl')
    return buf.getvalue()
