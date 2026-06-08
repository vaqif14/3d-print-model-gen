# 3D Print Model Generation — Examples

## Example 1: Parametric Bracket (OpenSCAD-style pseudocode)

```scad
// Design rules applied:
// - Wall thickness: 3 mm (functional load-bearing)
// - Fillet radius: 2 mm (stress reduction)
// - Overhangs: all ≤ 45° (no supports needed)
// - Holes: 4.3 mm for M4 bolt (nominal 4.0 + 0.3 tolerance)

module bracket(width=40, height=30, depth=20, thickness=3) {
    difference() {
        // Main body with filleted edges
        rounded_cube([width, height, depth], r=2);
        
        // Hollow interior (save material, maintain walls)
        translate([thickness, thickness, thickness])
            rounded_cube([width-thickness*2, height-thickness*2, depth], r=1);
        
        // Mounting holes (4.3 mm for M4 clearance)
        translate([width/2, height/2, 0])
            cylinder(d=4.3, h=depth+1, $fn=32);
    }
}
```

**Slicer settings**:
- Layer height: 0.2 mm
- Walls: 3 (1.2 mm total)
- Infill: 40% Grid (load-bearing)
- Orientation: Largest flat face down
- Material: PETG (strength + chemical resistance)

## Example 2: Mesh Validation Script (Python)

```python
import trimesh

def validate_print_mesh(filepath):
    mesh = trimesh.load_mesh(filepath)
    
    report = {
        'is_watertight': mesh.is_watertight,
        'is_winding_consistent': mesh.is_winding_consistent,
        'volume': mesh.volume,
        'bounds': mesh.bounds,
        'extents': mesh.extents,
        'face_count': len(mesh.faces),
        'edge_manifold': mesh.is_edge_manifold,
    }
    
    # Check for non-manifold edges
    edges = mesh.edges_unique
    edge_count = mesh.edges_boundary
    report['boundary_edges'] = len(edge_count)
    
    # Check for zero-area faces
    face_areas = mesh.area_faces
    report['zero_area_faces'] = int((face_areas < 1e-12).sum())
    
    # Check for degenerate geometry
    report['bounds_volume_ratio'] = mesh.volume / mesh.bounding_box.volume
    
    return report

# Usage
report = validate_print_mesh('model.stl')
for key, value in report.items():
    print(f"{key}: {value}")
```

## Example 3: Support Strategy Decision Tree

```
Overhang angle?
├── > 60° → Redesign model (split or add chamfer)
├── 45°–60° → Tree supports recommended
├── 30°–45° → Linear supports sufficient
└── < 30° → No supports needed (self-supporting)

Bridge span?
├── > 15 mm → Supports required
├── 10–15 mm → Test with cooling; supports recommended
└── < 10 mm → Self-bridge with good cooling

Feature type?
├── Island / floating → Point supports (resin) or tree (FDM)
├── Arch / dome → Tree supports, avoid contact with visible face
└── Flat overhang → Linear supports with interface layers
```

## Example 4: Slicer Profile Template (PrusaSlicer / OrcaSlicer)

```ini
; PETG Functional Part Profile
layer_height = 0.2
first_layer_height = 0.24
perimeters = 3
top_solid_layers = 4
bottom_solid_layers = 3
fill_density = 40%
fill_pattern = grid
support_material = 1
support_material_threshold = 45
support_material_pattern = rectilinear
support_material_interface_layers = 2
support_material_contact_distance = 0.2
raft_layers = 0
perimeter_speed = 45
infill_speed = 60
temperature = 240
bed_temperature = 80
fan_speed = 30
retract_length = 1.2  ; direct drive
retract_speed = 35
```

## Example 5: Moving Parts Clearance Test

Before printing a full assembly, print a **tolerance gauge**:

```scad
// Tolerance gauge: pegs from 5.0 to 5.5 mm in 0.1 mm steps
for (i = [0:5]) {
    translate([i*12, 0, 0])
        cylinder(d=5.0+i*0.1, h=10, $fn=32);
}

// Matching holes: 5.1 to 5.6 mm
for (i = [0:5]) {
    translate([i*12, 20, 0])
        difference() {
            cube([10, 10, 10]);
            translate([5, 5, 0])
                cylinder(d=5.1+i*0.1, h=10, $fn=32);
        }
}
```

Test which peg fits which hole to determine optimal clearance for your specific printer + filament combination.

## Example 6: Resin Miniature Workflow

1. **Model requirements**:
   - Wall thickness ≥ 0.8 mm
   - Base added for build plate adhesion
   - Drain holes in hollow sections ≥ 3 mm
   - Supports: light density, contact size 0.3 mm

2. **Orientation**:
   - Tilt 30–45° from vertical (reduces suction forces)
   - Heaviest section closest to build plate
   - Avoid flat surfaces parallel to build plate (peel force)

3. **Slicer settings**:
   - Layer height: 0.05 mm (high detail)
   - Exposure: per resin calibration (typically 2–3 s normal, 30–40 s bottom)
   - Lift speed: slow (60 mm/min) for delicate parts
   - Rest time: 1–2 s after lift (resin flow)

4. **Post-process**:
   - Wash: 3 minutes in IPA (agitation)
   - Dry: compressed air + 10 min ambient
   - Cure: 10 min under 405 nm UV (rotate every 2 min)

## Example 7: Enclosure with Living Hinge (OpenSCAD)

```scad
// IP54-rated snap-latch enclosure with PCB standoffs
module enclosure(width=80, depth=60, height=40, wall=2) {
    difference() {
        // Outer shell
        rounded_cube([width, depth, height], r=2);
        // Hollow interior
        translate([wall, wall, wall])
            rounded_cube([width-wall*2, depth-wall*2, height], r=1);
    }
    
    // Living hinge (0.3 mm thick, full width)
    translate([-width/2, depth/2-1, height-5])
        cube([width, 0.3, 5]);
    
    // Snap latch (cantilever hook)
    translate([0, depth/2, height-8])
        rotate([90,0,0])
            linear_extrude(height=wall)
                polygon([[0,0], [4,0], [4,3], [1,3]]);
    
    // PCB standoffs (M3 brass inserts)
    for (x = [-width/2+10, width/2-10])
        for (y = [-depth/2+10, depth/2-10])
            translate([x, y, wall])
                difference() {
                    cylinder(d=7, h=height-wall-2, $fn=32);
                    cylinder(d=3.3, h=height, $fn=32); // M3 hole
                }
}
```

**Slicer settings**:
- Material: PETG (hinge flexibility + chemical resistance)
- Walls: 3 | Top/Bottom: 4 layers
- Infill: 30% Gyroid
- First layer: 0.24 mm, speed 20 mm/s
- Hinge area: slow down to 15 mm/s for consistent extrusion

## Example 8: Compliant Parallel Gripper (Python/trimesh)

```python
import trimesh
import numpy as np

def compliant_gripper(jaw_width=30, jaw_depth=20, flexure_thickness=1.5,
                      flexure_length=25, base_thickness=4):
    """Single-piece parallel gripper via flexure beams."""
    
    # Base block
    base = trimesh.primitives.Box(extents=[jaw_width*2+10, 15, base_thickness])
    base.apply_translation([0, 0, base_thickness/2])
    
    # Flexure arms (thin beams)
    arm_l = trimesh.primitives.Box(extents=[flexure_thickness, flexure_length, base_thickness])
    arm_l.apply_translation([-jaw_width/2, flexure_length/2+7.5, base_thickness/2])
    
    arm_r = trimesh.primitives.Box(extents=[flexure_thickness, flexure_length, base_thickness])
    arm_r.apply_translation([jaw_width/2, flexure_length/2+7.5, base_thickness/2])
    
    # Jaw pads
    pad = trimesh.primitives.Box(extents=[8, jaw_depth, base_thickness+2])
    pad_l = pad.copy()
    pad_l.apply_translation([-jaw_width/2, flexure_length+7.5+jaw_depth/2, base_thickness/2+1])
    pad_r = pad.copy()
    pad_r.apply_translation([jaw_width/2, flexure_length+7.5+jaw_depth/2, base_thickness/2+1])
    
    gripper = trimesh.util.concatenate([base, arm_l, arm_r, pad_l, pad_r])
    return gripper

# Export
gripper = compliant_gripper()
gripper.export('gripper.stl')
```

**Notes**:
- Flexure thickness determines force vs displacement
- PETG or Nylon recommended (fatigue resistance)
- No assembly required — print and use

## Example 9: Heat-Set Insert Boss Test Plate

```scad
// One plate to test all insert sizes
inserts = [
    ["M2",  2.3, 3.2, 3.0],
    ["M2.5",2.8, 3.9, 3.5],
    ["M3",  3.3, 4.6, 4.0],
    ["M4",  4.3, 5.6, 5.5],
];

for (i = [0:len(inserts)-1]) {
    name = inserts[i][0];
    hole_d = inserts[i][1];
    boss_od = inserts[i][2] + 3;
    boss_h = inserts[i][3] + 2;
    
    translate([i*15, 0, 0]) {
        difference() {
            cylinder(d=boss_od, h=boss_h, $fn=32);
            cylinder(d=hole_d, h=boss_h+1, $fn=32);
        }
        // Label
        translate([0, -boss_od/2-2, 0])
            linear_extrude(height=0.4)
                text(name, size=3, halign="center");
    }
}
```

**Print settings**:
- Material: ABS or PETG (withstands insert heating)
- Layer height: 0.2 mm (accurate hole size)
- Holes: print vertically (layer direction affects roundness)
- Test: install inserts with soldering iron at 200°C

## Example 10: Functionally Graded Lattice Infill (Python)

```python
import numpy as np
from skimage import measure
import trimesh

def graded_gyroid(bounds, cell_size=4.0, resolution=80):
    """Gyroid density varies with Z: dense at bottom, sparse at top."""
    x = np.linspace(bounds[0][0], bounds[1][0], resolution)
    y = np.linspace(bounds[0][1], bounds[1][1], resolution)
    z = np.linspace(bounds[0][2], bounds[1][2], resolution)
    X, Y, Z = np.meshgrid(x, y, z, indexing='ij')
    
    # Normalized Z: 0 = bottom, 1 = top
    Zn = (Z - bounds[0][2]) / (bounds[1][2] - bounds[0][2])
    
    # Density gradient: 0.6 at bottom, 0.15 at top
    density = 0.6 - 0.45 * Zn
    
    # Gyroid field
    Xc, Yc, Zc = X/cell_size, Y/cell_size, Z/cell_size
    field = np.sin(Xc)*np.cos(Yc) + np.sin(Yc)*np.cos(Zc) + np.sin(Zc)*np.cos(Xc)
    
    # Threshold per-voxel based on density
    thresholds = np.percentile(field, (1-density)*100)
    
    # Marching cubes with varying threshold (approximate)
    # For true graded lattice, use multi-material or multiple boolean operations
    threshold = np.mean(thresholds)
    verts, faces, _, _ = measure.marching_cubes(field, level=threshold)
    
    scale = np.array(bounds[1]) - np.array(bounds[0])
    verts = verts * scale / resolution + bounds[0]
    return trimesh.Trimesh(vertices=verts, faces=faces)

# Usage: create lattice inside a bounding box
bounds = [[0,0,0], [40, 40, 40]]
lattice = graded_gyroid(bounds, cell_size=3.0, resolution=60)
lattice.export('graded_lattice.stl')
```

**Note**: True functionally-graded infill requires slicer support (Cura "gradual infill" or custom G-code) or multi-step boolean in CAD. This script generates a visual approximation.

## Example 11: Complete Pipeline Script

```bash
#!/bin/bash
# Full pipeline from request to output

PART_TYPE="bracket"
MATERIAL="PETG"
OUTPUT_DIR="./output"
mkdir -p "$OUTPUT_DIR"

# 1. Design
python scripts/dfam_designer.py "$PART_TYPE" --material "$MATERIAL" \
    -o "$OUTPUT_DIR/part.stl"

# 2. Validate
python scripts/validate_mesh.py "$OUTPUT_DIR/part.stl"

# 3. Optimize (optional hollow for resin)
# python scripts/mesh_optimizer.py "$OUTPUT_DIR/part.stl" --hollow --wall 2 \
#     -o "$OUTPUT_DIR/part_hollow.stl"

# 4. Generate slicer profile
python scripts/slicer_autopilot.py "$OUTPUT_DIR/part.stl" \
    --material "$MATERIAL" --printer ender3 \
    -o "$OUTPUT_DIR/profile.ini"

# 5. Simulate (after slicing manually or via CLI)
# prusa-slicer --export-gcode --load "$OUTPUT_DIR/profile.ini" \
#     "$OUTPUT_DIR/part.stl" -o "$OUTPUT_DIR/part.gcode"
# python scripts/print_simulator.py "$OUTPUT_DIR/part.gcode"

echo "Pipeline complete. Files in $OUTPUT_DIR"
```
