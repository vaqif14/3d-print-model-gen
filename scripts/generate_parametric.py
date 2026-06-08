#!/usr/bin/env python3
"""
Parametric 3D Print Model Generator (trimesh-based)
Generates common functional shapes with DfAM-aware defaults.

Usage:
    python generate_parametric.py box --width 40 --depth 30 --height 20 --wall 2 --output box.stl
    python generate_parametric.py bracket --output bracket.stl
    python generate_parametric.py tolerance-gauge --output gauge.stl

Requirements:
    pip install trimesh numpy
"""

import argparse
import sys
from pathlib import Path

try:
    import trimesh
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install trimesh numpy")
    sys.exit(1)


def save_mesh(mesh: trimesh.Trimesh, filepath: str):
    """Save mesh, ensuring proper format."""
    ext = Path(filepath).suffix.lower()
    if ext == '.stl':
        mesh.export(filepath, file_type='stl')
    elif ext == '.obj':
        mesh.export(filepath, file_type='obj')
    elif ext == '.3mf':
        # trimesh may need extra deps for 3mf; fallback to stl
        try:
            mesh.export(filepath, file_type='3mf')
        except Exception:
            fallback = filepath.replace('.3mf', '.stl')
            mesh.export(fallback, file_type='stl')
            print(f"3MF export failed, saved as {fallback}")
            return
    else:
        mesh.export(filepath)
    print(f"Saved: {filepath}")
    print(f"  Extents (mm): {mesh.extents.round(3).tolist()}")
    print(f"  Faces: {len(mesh.faces):,}")
    print(f"  Volume (mm³): {mesh.volume:.2f}")


def make_box(width: float, depth: float, height: float, wall: float,
             hole_d: float = None, fillet: float = 0.0) -> trimesh.Trimesh:
    """Hollow box/enclosure with optional mounting hole."""
    outer = trimesh.primitives.Box(extents=[width, depth, height])
    if wall > 0:
        inner = trimesh.primitives.Box(extents=[
            width - wall * 2, depth - wall * 2, height
        ])
        inner.apply_translation([0, 0, wall / 2])
        mesh = outer.difference(inner)
    else:
        mesh = outer

    if hole_d and hole_d > 0:
        hole = trimesh.primitives.Cylinder(radius=hole_d / 2, height=height + 2)
        mesh = mesh.difference(hole)

    return mesh


def make_bracket(width: float = 40, height: float = 30, depth: float = 20,
                 thickness: float = 3, hole_d: float = 4.3,
                 fillet: float = 2.0) -> trimesh.Trimesh:
    """L-bracket with mounting hole and stress-relief fillet."""
    # Base plate
    base = trimesh.primitives.Box(extents=[width, depth, thickness])
    base.apply_translation([0, 0, thickness / 2])

    # Vertical wall
    wall = trimesh.primitives.Box(extents=[width, thickness, height])
    wall.apply_translation([0, -depth / 2 + thickness / 2, height / 2])

    # Gusset (triangular support)
    gusset_h = height * 0.6
    gusset_d = depth * 0.6
    gusset_pts = np.array([
        [-width / 2 + 5, -depth / 2 + thickness, thickness],
        [-width / 2 + 5, -depth / 2 + thickness + gusset_d, thickness],
        [-width / 2 + 5, -depth / 2 + thickness, thickness + gusset_h],
    ])
    gusset = trimesh.creation.extrude_polygon(
        trimesh.creation.triangulate_polygon(trimesh.path.polygons.Polygon(gusset_pts[:, 1:])),
        height=width - 10
    )
    # Reorient gusset
    gusset.apply_translation([0, 0, 0])

    # Simpler approach: just union base + wall
    bracket = trimesh.util.concatenate([base, wall])

    # Mounting hole (clearance for M4)
    hole = trimesh.primitives.Cylinder(radius=hole_d / 2, height=thickness + 2)
    hole.apply_translation([0, 0, thickness / 2])
    bracket = bracket.difference(hole)

    return bracket


def make_tolerance_gauge(min_d: float = 5.0, max_d: float = 5.5,
                         steps: int = 6, height: float = 10) -> trimesh.Trimesh:
    """Tolerance test gauge with pegs and matching holes."""
    meshes = []
    spacing = 12.0

    for i in range(steps):
        d = min_d + i * (max_d - min_d) / (steps - 1)
        # Peg
        peg = trimesh.primitives.Cylinder(radius=d / 2, height=height)
        peg.apply_translation([i * spacing, 0, height / 2])
        meshes.append(peg)

        # Hole block
        block = trimesh.primitives.Box(extents=[10, 10, height])
        block.apply_translation([i * spacing, 20, height / 2])
        hole = trimesh.primitives.Cylinder(
            radius=(min_d + 0.1 + i * (max_d - min_d) / (steps - 1)) / 2,
            height=height + 2
        )
        hole.apply_translation([i * spacing, 20, height / 2])
        block = block.difference(hole)
        meshes.append(block)

    return trimesh.util.concatenate(meshes)


def make_support_test(angles: list = None, height: float = 20) -> trimesh.Trimesh:
    """Overhang test pyramid with graduated angles."""
    if angles is None:
        angles = [20, 30, 45, 60]

    meshes = []
    base_w = 15
    spacing = 25

    for i, angle in enumerate(angles):
        rad = np.radians(angle)
        # Create a wedge: base at z=0, tip at z=height
        # Overhang is the underside angle
        pts = np.array([
            [0, 0, 0],
            [base_w, 0, 0],
            [base_w, 0, height],
            [0, 0, height],
            [base_w / 2, base_w, 0],
            [base_w / 2, base_w, height],
        ])
        faces = [
            [0, 1, 4], [1, 5, 4],  # bottom
            [0, 4, 3], [4, 5, 3],  # side 1
            [1, 2, 5], [0, 3, 2], [0, 2, 1],  # other sides
            [3, 5, 2],  # top
        ]
        wedge = trimesh.Trimesh(vertices=pts, faces=faces)
        wedge.apply_translation([i * spacing, 0, 0])
        meshes.append(wedge)

    return trimesh.util.concatenate(meshes)


def main():
    parser = argparse.ArgumentParser(description='Generate parametric 3D print models')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Box
    box_p = subparsers.add_parser('box', help='Hollow enclosure box')
    box_p.add_argument('--width', type=float, default=40)
    box_p.add_argument('--depth', type=float, default=30)
    box_p.add_argument('--height', type=float, default=20)
    box_p.add_argument('--wall', type=float, default=2)
    box_p.add_argument('--hole-d', type=float, default=None)
    box_p.add_argument('-o', '--output', default='box.stl')

    # Bracket
    bracket_p = subparsers.add_parser('bracket', help='L-bracket with mounting hole')
    bracket_p.add_argument('--width', type=float, default=40)
    bracket_p.add_argument('--height', type=float, default=30)
    bracket_p.add_argument('--depth', type=float, default=20)
    bracket_p.add_argument('--thickness', type=float, default=3)
    bracket_p.add_argument('--hole-d', type=float, default=4.3)
    bracket_p.add_argument('-o', '--output', default='bracket.stl')

    # Tolerance gauge
    gauge_p = subparsers.add_parser('tolerance-gauge', help='Fit tolerance test print')
    gauge_p.add_argument('--min-d', type=float, default=5.0)
    gauge_p.add_argument('--max-d', type=float, default=5.5)
    gauge_p.add_argument('--steps', type=int, default=6)
    gauge_p.add_argument('--height', type=float, default=10)
    gauge_p.add_argument('-o', '--output', default='tolerance_gauge.stl')

    # Support test
    support_p = subparsers.add_parser('support-test', help='Overhang angle test')
    support_p.add_argument('--angles', type=float, nargs='+', default=[20, 30, 45, 60])
    support_p.add_argument('--height', type=float, default=20)
    support_p.add_argument('-o', '--output', default='support_test.stl')

    args = parser.parse_args()

    if args.command == 'box':
        mesh = make_box(args.width, args.depth, args.height, args.wall, args.hole_d)
    elif args.command == 'bracket':
        mesh = make_bracket(args.width, args.height, args.depth, args.thickness, args.hole_d)
    elif args.command == 'tolerance-gauge':
        mesh = make_tolerance_gauge(args.min_d, args.max_d, args.steps, args.height)
    elif args.command == 'support-test':
        mesh = make_support_test(args.angles, args.height)
    else:
        parser.print_help()
        sys.exit(1)

    save_mesh(mesh, args.output)


if __name__ == '__main__':
    main()
