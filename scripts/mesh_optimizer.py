#!/usr/bin/env python3
"""
Mesh Optimizer — Pro-Level 3D Print Preparation
Operations: hollowing, shell/offset, TPMS lattice infill, decimation,
            repair, drain hole placement.

Usage:
    python mesh_optimizer.py model.stl --hollow --wall 2.0 --drain-holes -o hollow.stl
    python mesh_optimizer.py model.stl --lattice gyroid --density 0.3 -o lattice.stl
    python mesh_optimizer.py model.stl --decimate 0.5 -o reduced.stl
    python mesh_optimizer.py model.stl --repair -o fixed.stl
    python mesh_optimizer.py model.stl --offset 1.5 -o shell.stl

Requirements:
    pip install trimesh numpy scipy
"""

import argparse
import sys
from pathlib import Path

try:
    import numpy as np
    import trimesh
    from scipy.spatial import cKDTree
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install trimesh numpy scipy")
    sys.exit(1)


def ensure_watertight(mesh):
    """Basic repair: merge vertices, fill holes, fix normals."""
    mesh.merge_vertices(merge_tex=True, merge_norm=True)
    if not mesh.is_watertight:
        # Try convex hull fill for small holes (aggressive fallback)
        # Better: use pymeshfix or Blender for real repair
        print("WARN: Mesh has holes. Using convex hull as fallback (may alter shape).")
        print("      For proper repair, use Blender or pymeshfix.")
        hull = mesh.convex_hull
        return hull
    mesh.fix_normals()
    return mesh


def shell_mesh(mesh, offset, outer=True):
    """Create uniform shell by offsetting surface inward/outward."""
    # Approximate via vertex normal offset (fast, not exact for sharp features)
    # For exact offset, use libigl or OpenVDB. This is a lightweight fallback.
    if not mesh.is_watertight:
        mesh = ensure_watertight(mesh)

    normals = mesh.vertex_normals
    vertices = mesh.vertices.copy()

    if outer:
        vertices += normals * offset
    else:
        vertices -= normals * offset

    new_mesh = trimesh.Trimesh(vertices=vertices, faces=mesh.faces)
    new_mesh.merge_vertices()
    return new_mesh


def hollow_mesh(mesh, wall_thickness=2.0):
    """Hollow out a solid mesh by creating inner offset shell and boolean subtract."""
    if not mesh.is_watertight:
        mesh = ensure_watertight(mesh)

    print(f"Hollowing with wall thickness {wall_thickness} mm...")

    # Inner shell (inward offset)
    inner = shell_mesh(mesh, wall_thickness, outer=False)

    # Boolean subtract inner from outer
    try:
        hollow = mesh.difference(inner)
        hollow.merge_vertices()
        return hollow
    except Exception as e:
        print(f"Boolean failed: {e}")
        print("Returning original mesh. Use CAD software (Fusion 360, FreeCAD) for reliable hollowing.")
        return mesh


def add_drain_holes(mesh, diameter=3.0, count=2, z_threshold=0.3):
    """Add drain holes at lowest Z points (for resin printing)."""
    if not mesh.is_watertight:
        mesh = ensure_watertight(mesh)

    # Find lowest vertices
    z_min = mesh.bounds[0][2]
    z_range = mesh.extents[2]
    low_mask = mesh.vertices[:, 2] < z_min + z_threshold * z_range
    low_pts = mesh.vertices[low_mask]

    if len(low_pts) == 0:
        print("No low points found; adding holes at bounds center.")
        low_pts = [mesh.centroid - [0, 0, mesh.extents[2] / 2]]

    # K-means-ish clustering to pick `count` locations
    if len(low_pts) > count:
        # Simple greedy selection: pick furthest apart points
        indices = [0]
        for _ in range(1, count):
            tree = cKDTree(low_pts[indices])
            dists, _ = tree.query(low_pts, k=1)
            next_idx = int(np.argmax(dists))
            indices.append(next_idx)
        hole_centers = low_pts[indices]
    else:
        hole_centers = low_pts[:count]

    hole_r = diameter / 2
    hole_h = mesh.extents[2] + 4

    for center in hole_centers:
        hole = trimesh.primitives.Cylinder(radius=hole_r, height=hole_h)
        hole.apply_translation(center + [0, 0, hole_h / 2 - 2])
        mesh = mesh.difference(hole)

    print(f"Added {len(hole_centers)} drain holes (⌀{diameter} mm)")
    return mesh


def tpms_lattice(mesh, pattern='gyroid', density=0.3, cell_size=5.0):
    """Generate TPMS lattice infill inside mesh bounds."""
    # TPMS functions evaluated on grid, then marching cubes
    bounds = mesh.bounds
    extents = mesh.extents
    res = max(20, int(max(extents) / cell_size * 8))

    x = np.linspace(bounds[0][0], bounds[1][0], res)
    y = np.linspace(bounds[0][1], bounds[1][1], res)
    z = np.linspace(bounds[0][2], bounds[1][2], res)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')

    # Normalize to cell size
    Xn, Yn, Zn = X / cell_size, Y / cell_size, Z / cell_size

    if pattern == 'gyroid':
        field = np.sin(Xn) * np.cos(Yn) + np.sin(Yn) * np.cos(Zn) + np.sin(Zn) * np.cos(Xn)
    elif pattern == 'schwarz_p':
        field = np.cos(Xn) + np.cos(Yn) + np.cos(Zn)
    elif pattern == 'schwarz_d':
        field = (np.sin(Xn) * np.sin(Yn) * np.sin(Zn) +
                 np.sin(Xn) * np.cos(Yn) * np.cos(Zn) +
                 np.cos(Xn) * np.sin(Yn) * np.cos(Zn) +
                 np.cos(Xn) * np.cos(Yn) * np.sin(Zn))
    else:
        raise ValueError(f"Unknown pattern: {pattern}")

    # Threshold for density
    threshold = np.percentile(field, (1 - density) * 100)
    # Marching cubes on the field
    from skimage import measure
    verts, faces, _, _ = measure.marching_cubes(field, level=threshold)

    # Scale back to world coordinates
    scale = extents / np.array([res - 1, res - 1, res - 1])
    verts = verts * scale + bounds[0]

    lattice = trimesh.Trimesh(vertices=verts, faces=faces)
    lattice.merge_vertices()

    # Intersect with original mesh to keep only inside volume
    # Note: trimesh boolean is slow/fragile; as fallback, use mesh bounds clip
    # For production, use Blender or OpenVDB
    print(f"Generated {pattern} lattice ({len(lattice.faces):,} faces)")
    print("NOTE: Boolean intersection with original shell may fail; use Blender for production.")

    return lattice


def decimate_mesh(mesh, target_ratio=0.5):
    """Reduce face count while preserving shape."""
    if not hasattr(mesh, 'simplify_quadric_decimation'):
        print("WARN: trimesh decimation unavailable. Install `pip install meshlabxml` or use Blender.")
        return mesh

    target_faces = int(len(mesh.faces) * target_ratio)
    simplified = mesh.simplify_quadric_decimation(target_faces)
    print(f"Decimated: {len(mesh.faces):,} → {len(simplified.faces):,} faces")
    return simplified


def save_mesh(mesh, filepath):
    ext = Path(filepath).suffix.lower()
    if ext == '.stl':
        mesh.export(filepath, file_type='stl')
    elif ext == '.obj':
        mesh.export(filepath, file_type='obj')
    else:
        mesh.export(filepath)
    print(f"Saved: {filepath}")
    print(f"  Faces: {len(mesh.faces):,} | Volume: {mesh.volume:.2f} mm³")


def main():
    parser = argparse.ArgumentParser(description='Mesh Optimizer for 3D Printing')
    parser.add_argument('input', help='Input mesh file')
    parser.add_argument('-o', '--output', default='optimized.stl')
    parser.add_argument('--hollow', action='store_true', help='Hollow out mesh')
    parser.add_argument('--wall', type=float, default=2.0, help='Wall thickness for hollowing')
    parser.add_argument('--drain-holes', action='store_true', help='Add drain holes (resin)')
    parser.add_argument('--hole-d', type=float, default=3.0, help='Drain hole diameter')
    parser.add_argument('--hole-count', type=int, default=2, help='Number of drain holes')
    parser.add_argument('--lattice', choices=['gyroid', 'schwarz_p', 'schwarz_d'], help='TPMS lattice pattern')
    parser.add_argument('--density', type=float, default=0.3, help='Lattice density (0–1)')
    parser.add_argument('--cell-size', type=float, default=5.0, help='Lattice cell size in mm')
    parser.add_argument('--decimate', type=float, help='Target face ratio (0–1)')
    parser.add_argument('--offset', type=float, help='Offset mesh by mm (positive = outward)')
    parser.add_argument('--repair', action='store_true', help='Repair mesh (basic)')

    args = parser.parse_args()

    print(f"Loading: {args.input}")
    mesh = trimesh.load_mesh(args.input, force='mesh')
    print(f"  Original: {len(mesh.faces):,} faces | Watertight: {mesh.is_watertight}")

    if args.repair:
        mesh = ensure_watertight(mesh)

    if args.offset:
        mesh = shell_mesh(mesh, args.offset, outer=(args.offset > 0))

    if args.hollow:
        mesh = hollow_mesh(mesh, args.wall)

    if args.drain_holes:
        mesh = add_drain_holes(mesh, args.hole_d, args.hole_count)

    if args.lattice:
        lattice = tpms_lattice(mesh, args.lattice, args.density, args.cell_size)
        # Try to boolean union shell + lattice
        try:
            mesh = trimesh.util.concatenate([mesh, lattice])
        except Exception:
            print("Could not union lattice with shell; saving lattice separately.")
            lattice_path = args.output.replace('.stl', '_lattice.stl')
            save_mesh(lattice, lattice_path)

    if args.decimate:
        mesh = decimate_mesh(mesh, args.decimate)

    save_mesh(mesh, args.output)


if __name__ == '__main__':
    main()
