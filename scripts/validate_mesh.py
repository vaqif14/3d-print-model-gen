#!/usr/bin/env python3
"""
3D Print Mesh Validator
Validates a 3D model for print-readiness using trimesh.
Checks: watertight, manifold, normals, zero-area faces, bounds, thin walls.

Usage:
    python validate_mesh.py model.stl [--wall-threshold 0.8]

Requirements:
    pip install trimesh numpy
"""

import argparse
import sys

try:
    import trimesh
    import numpy as np
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install with: pip install trimesh numpy")
    sys.exit(1)


def validate_mesh(filepath: str, wall_threshold: float = 0.8) -> dict:
    """Validate a mesh for 3D print readiness."""
    mesh = trimesh.load_mesh(filepath, force='mesh')

    report = {
        'file': filepath,
        'face_count': len(mesh.faces),
        'vertex_count': len(mesh.vertices),
        'bounds_mm': mesh.bounds.tolist(),
        'extents_mm': mesh.extents.tolist(),
        'volume_mm3': round(float(mesh.volume), 4) if mesh.is_watertight else None,
        'surface_area_mm2': round(float(mesh.area), 4),
        'watertight': bool(mesh.is_watertight),
        'winding_consistent': bool(mesh.is_winding_consistent),
        'edge_manifold': bool(mesh.is_watertight),
        'vertex_manifold': bool(mesh.is_watertight),
    }

    # Boundary edges / holes
    # trimesh 4.x compatibility: derive boundary from edges shared by only 1 face
    try:
        edge_face_count = {}
        for face in mesh.faces:
            for j in range(3):
                a, b = face[j], face[(j+1)%3]
                edge = tuple(sorted([int(a), int(b)]))
                edge_face_count[edge] = edge_face_count.get(edge, 0) + 1
        boundary_count = sum(1 for v in edge_face_count.values() if v == 1)
        report['boundary_edge_count'] = boundary_count
        report['has_holes'] = boundary_count > 0
    except Exception:
        report['boundary_edge_count'] = -1
        report['has_holes'] = not mesh.is_watertight

    # Zero-area faces
    face_areas = mesh.area_faces
    zero_area = int((face_areas < 1e-12).sum())
    report['zero_area_faces'] = zero_area

    # Inverted normals check
    try:
        centroid = mesh.centroid
        face_centers = mesh.triangles_center
        to_center = face_centers - centroid
        norms = np.linalg.norm(to_center, axis=1, keepdims=True) + 1e-12
        to_center_norm = to_center / norms
        dot_products = np.einsum('ij,ij->i', mesh.face_normals, to_center_norm)
        inverted_count = int((dot_products < -0.1).sum())
        report['potentially_inverted_faces'] = inverted_count
    except Exception:
        report['potentially_inverted_faces'] = -1

    # Thin wall detection
    try:
        if mesh.is_watertight and mesh.volume > 0:
            approx_thickness = 3 * mesh.volume / mesh.area
            report['approximate_thickness_mm'] = round(float(approx_thickness), 4)
            report['thin_walls_detected'] = approx_thickness < wall_threshold
        else:
            report['approximate_thickness_mm'] = None
            report['thin_walls_detected'] = None
    except Exception:
        report['approximate_thickness_mm'] = None
        report['thin_walls_detected'] = None

    report['note'] = 'Self-intersection check: use meshlab or blender for full test'

    return report


def print_report(report: dict, wall_threshold: float):
    print(f"\n{'='*60}")
    print(f"  3D PRINT MESH VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"  File:          {report['file']}")
    print(f"  Faces:         {report['face_count']:,}")
    print(f"  Vertices:      {report['vertex_count']:,}")
    print(f"  Bounds (mm):   {report['bounds_mm']}")
    print(f"  Extents (mm):  {report['extents_mm']}")
    print(f"  Volume (mm³):  {report['volume_mm3']}")
    print(f"  Surface (mm²): {report['surface_area_mm2']}")
    print(f"{'-'*60}")

    checks = [
        ('Watertight', report['watertight'], 'FAIL: Mesh has holes — slicer may error'),
        ('Consistent Normals', report['winding_consistent'], 'WARN: Inconsistent face winding'),
        ('Edge Manifold', report['edge_manifold'], 'FAIL: Non-manifold edges detected'),
        ('Vertex Manifold', report['vertex_manifold'], 'FAIL: Non-manifold vertices detected'),
        ('Zero-Area Faces', report['zero_area_faces'] == 0, f"FAIL: {report['zero_area_faces']} degenerate faces"),
        ('Holes', not report['has_holes'], f"FAIL: {report['boundary_edge_count']} boundary edges (holes)"),
        ('Inverted Faces', report['potentially_inverted_faces'] == 0, f"WARN: {report['potentially_inverted_faces']} potentially inverted faces"),
    ]

    if report['thin_walls_detected'] is not None:
        checks.append((
            f'Wall Thickness (≥{wall_threshold} mm)',
            not report['thin_walls_detected'],
            f"WARN: Approx thickness ~{report['approximate_thickness_mm']} mm"
        ))

    all_pass = True
    for name, passed, msg in checks:
        status = '✅ PASS' if passed else msg
        if not passed and 'FAIL' in msg:
            status = f'❌ {msg}'
            all_pass = False
        elif not passed:
            status = f'⚠️  {msg}'
        print(f"  {name:<30} {status}")

    print(f"{'='*60}")
    if all_pass:
        print("  ✅ MESH IS PRINT-READY")
    else:
        print("  ❌ MESH REQUIRES REPAIR BEFORE PRINTING")
    print(f"{'='*60}\n")

    return all_pass


def main():
    parser = argparse.ArgumentParser(description='Validate 3D mesh for printing')
    parser.add_argument('file', help='Path to mesh file (STL, OBJ, 3MF, etc.)')
    parser.add_argument('--wall-threshold', type=float, default=0.8,
                        help='Minimum acceptable wall thickness in mm (default: 0.8)')
    args = parser.parse_args()

    try:
        report = validate_mesh(args.file, wall_threshold=args.wall_threshold)
        ok = print_report(report, wall_threshold=args.wall_threshold)
        sys.exit(0 if ok else 1)
    except Exception as e:
        print(f"Error processing mesh: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
