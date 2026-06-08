# 3D Print Model Generation — Reference

## 1. File Formats

| Format | Geometry | Color/Texture | Units | Best For |
|--------|----------|---------------|-------|----------|
| **STL** | Triangles only | No | None (ambiguous) | Universal single-color FDM |
| **OBJ** | Polygons | Yes (via .MTL) | None | Multi-color/textured prints |
| **3MF** | Triangles + metadata | Yes (embedded) | Millimeters (native) | Modern workflows, assemblies |
| **STEP** | NURBS solids | Limited | Embedded | Engineering precision, CAD-native slicing |
| **AMF** | Curved triangles | Yes | Embedded | Legacy; superseded by 3MF |

**Rules**:
- Prefer **3MF** for all new work; fallback to **STL** only for legacy hardware
- Export **STEP** when dimensional accuracy is critical and slicer supports it (Bambu Studio, OrcaSlicer)
- Always verify scale after import; STL lacks units

## 2. Mesh Quality & Manifold Geometry

A model is **manifold** (watertight) when:
- Every edge is shared by exactly 2 faces
- Every face has consistent outward normal
- No zero-area faces or duplicate vertices
- No holes in the surface boundary

**Validation tools**:
- Blender: Edit Mode → Select → Select All by Trait → Non-Manifold
- Meshmixer: Analysis → Inspector
- Netfabb: Standard + Premium repair
- PrusaSlicer: Right-click → Fix through Netfabb
- Python: `trimesh`, `pymesh`, `open3d`

**Repair order**:
1. Merge duplicate vertices (weld by tolerance ~0.01 mm)
2. Recalculate outward normals
3. Fill holes (constrained delaunay preferred)
4. Remove non-manifold edges/faces
5. Verify zero self-intersections

## 3. Design Rules by Technology

### FDM / FFF

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Wall thickness | 0.8 mm | 1.2–2.0 mm | ≥ 2× nozzle diameter (0.4 mm typical) |
| Layer height | 0.08 mm | 0.2 mm | 25–75% of nozzle diameter |
| Overhang angle | — | ≤ 45° | Depends on cooling; test with calibration cube |
| Bridge span | — | ≤ 10 mm | Active part cooling required |
| Hole tolerance | +0.2 to +0.5 mm | +0.3 mm | Holes print undersized |
| Peg tolerance | −0.1 to −0.2 mm | −0.1 mm | Pegs print oversized |
| Moving parts clearance | 0.2–0.5 mm | 0.3 mm | Test with small joint before full print |
| Minimum feature | 0.4 mm | 0.8 mm | Nozzle diameter limited |
| Embossed detail | 0.5 mm | 1.0 mm | May fuse with surface if too shallow |
| Engraved detail | 0.5 mm | 1.0 mm | Walls may collapse if too thin |

**Orientation rules**:
- Largest flat face down for best adhesion
- Orient critical surfaces away from supports (support scars)
- Align layer lines perpendicular to primary stress direction
- Split models with overhangs > 60° instead of excessive supports

### SLA / DLP / LCD (Resin)

| Parameter | Minimum | Recommended | Notes |
|-----------|---------|-------------|-------|
| Wall thickness | 0.5 mm | 0.8–1.5 mm | Thicker for large flat walls |
| Overhang angle | — | ≤ 30°–35° | Depends on resin viscosity and layer height |
| Bridge span | — | ≤ 2–4 mm | Very limited without supports |
| Drain holes | ≥ 2 mm | 3–5 mm | Required for hollow models to avoid suction cups |
| Support contact | 0.2–0.4 mm | 0.3 mm | Too small = fail; too large = scars |
| Layer height | 25 µm | 50 µm | 25 µm for jewelry; 100 µm for speed |
| Critical angle (Standard 50µm) | 30° | 35° | Lower for flexible/castable resins |

**Resin-specific critical angles**:

| Resin Family | Layer | Critical Angle |
|--------------|-------|----------------|
| Standard / Grey / Clear | 50 µm | 30°–35° |
| Tough / Durable | 50–100 µm | 30°–35° |
| Rigid (glass-filled) | 50 µm | 25°–30° |
| Castable Wax | 25–50 µm | 20°–25° |
| Flexible / Elastic | 100 µm | 20°–25° |

### SLS / MJF (Powder Bed Fusion)

- Minimum wall thickness: 1.0 mm
- No support structures needed (self-supporting)
- Design for powder removal: include escape holes for internal channels
- Clearance for moving parts: 0.3–0.5 mm

### SLM (Metal)

- Minimum wall thickness: 1.5 mm
- Support required for overhangs > 45°
- Thermal stress management: avoid thick-to-thin transitions
- Post-processing: machining allowances for precision fits

## 4. Supports Strategy

### When to Use Supports
- Overhangs below critical angle
- Bridges exceeding printer capability
- Islands (floating features)
- Tall slender features prone to wobbling

### Support Types

| Type | Best For | Pros | Cons |
|------|----------|------|------|
| **Tree** | Organic/complex shapes | Less material, easier removal, cleaner surface | Slicer-dependent, slower generation |
| **Linear / Zigzag** | Flat overhangs | Fast, stable | More material, scars on contact |
| **Grid** | Large flat areas | Very stable | Hardest to remove |
| **Tree (resin)** | SLA miniatures | Minimal contact points | Requires careful placement |

### Support Settings (FDM)
- Density: 15–25% (higher for tall prints)
- Interface layers: 2–3 (for easy separation)
- Interface gap: 0.2 mm (sacrifice surface for removability)
- Overhang threshold: 45° (calibrate per printer)
- Tree support branch angle: 40–50°

## 5. Infill Strategy

| Use Case | Density | Pattern | Notes |
|----------|---------|---------|-------|
| Visual / display | 0–15% | Gyroid, Lightning | Fast, minimal material |
| General prototyping | 20–30% | Gyroid, Cubic | Good strength-to-weight |
| Functional / structural | 50–100% | Grid, Triangular | Align with load direction |
| Impact resistant | 30–50% | Gyroid, Honeycomb | Isotropic energy absorption |
| Compression loads | 40–60% | Cubic | Equal strength all axes |

**Pattern selection**:
- **Gyroid**: Best all-around; isotropic, fast, self-supporting
- **Cubic**: Isotropic, good for compression
- **Grid**: Strong in XY, weak in Z; good for bending
- **Triangular**: Strong in XY, good for shells
- **Honeycomb**: Strongest per weight; slower to print
- **Lightning**: Lightning-fast for non-structural prints

## 6. Material Selection & Slicer Profiles

### FDM Filaments

| Material | Bed Temp | Nozzle Temp | Cooling | Adhesion | Notes |
|----------|----------|-------------|---------|----------|-------|
| PLA | 20–60°C | 190–220°C | 100% | Easy | Brittle, low temp resistance |
| PETG | 70–85°C | 230–250°C | 30–50% | Medium | Strong, chemical resistant |
| ABS | 100–110°C | 230–250°C | 0–20% | Hard (enclosure) | Impact resistant, fumes |
| TPU | 20–60°C | 210–230°C | 50% | Medium | Flexible, string-prone |
| Nylon | 70–100°C | 240–270°C | 30% | Hard (glue) | Very strong, absorbs moisture |
| ASA | 90–110°C | 240–260°C | 0–30% | Hard | UV resistant ABS alternative |
| PC | 100–145°C | 260–300°C | 30% | Very hard | Extremely strong, warps |

### Resin Types

| Resin | Flexural | Use Case | Post-Process |
|-------|----------|----------|--------------|
| Standard | Rigid | Prototypes, miniatures | Wash + UV cure |
| Tough | Impact resistant | Functional parts | Wash + UV cure |
| Flexible / Elastic | Shore 80A/50A | Gaskets, wearables | Wash + UV cure |
| Castable Wax | Low ash | Jewelry casting | Burnout |
| Dental / Bio | Biocompatible | Medical | Strict protocol |

## 7. Troubleshooting Guide

### Warping / Lifting
- **Cause**: Uneven cooling, poor bed adhesion
- **Fix**: Increase bed temp, use brim/raft, clean bed, enclosure for ABS/PC, reduce fan speed

### Stringing / Oozing
- **Cause**: Retraction too low, temp too high, wet filament
- **Fix**: Increase retraction distance (4–6 mm Bowden, 0.5–1 mm direct), lower temp 5–10°C, dry filament

### Layer Shifting
- **Cause**: Loose belts, high acceleration, obstruction
- **Fix**: Tension belts, reduce speed/accel, check for nozzle collisions

### Under-Extrusion
- **Cause**: Partial clog, low temp, worn extruder gear, tangled spool
- **Fix**: Cold pull / nozzle clean, increase temp 5–10°C, check extruder tension, verify spool freedom

### Over-Extrusion
- **Cause**: Flow too high, incorrect e-steps, nozzle too close to bed
- **Fix**: Calibrate e-steps, reduce flow 5–10%, relevel bed

### Poor Surface Finish
- **Cause**: Layer lines visible, Z-seam visible, vibrations
- **Fix**: Lower layer height, enable coasting/outer wall first, reduce speed, check frame rigidity

### Support Fusing / Hard to Remove
- **Cause**: Support density too high, interface gap too small
- **Fix**: Reduce density, increase interface gap, use tree supports, enable support interface

### Resin Print Failures (SLA)
- **Cause**: Insufficient supports, dirty screen/FEP, incorrect exposure
- **Fix**: Increase support density, check screen/FEP for debris, run exposure calibration (AmeraLabs / Cones of Calibration)

## 8. Tolerances & Fits

| Fit Type | Clearance | Application |
|----------|-----------|-------------|
| Press fit | 0.0–0.1 mm | Bearings, inserts |
| Slide fit | 0.1–0.2 mm | Moving parts, hinges |
| Loose fit | 0.2–0.5 mm | Snap fits, assemblies |
| Thread fit | 0.2–0.4 mm | Printed threads (ACME recommended) |

**Thread design**: Use ACME or trapezoidal threads with rounded roots. Minimum printed thread: M6 (6 mm). Smaller = use threaded inserts or tap/die.

## 9. Build Volume & Splitting

When model exceeds build volume:
1. Identify natural split planes (hidden seams)
2. Add alignment features: pins (⌀3–5 mm) + holes with 0.1–0.2 mm clearance
3. Add glue channels or interlocking joints
4. Label parts for assembly orientation
5. Consider print direction for each sub-part independently

## 10. Post-Processing

### FDM
1. Remove supports (flush cutters, needle-nose pliers)
2. Sand: 120 → 240 → 400 → 600 grit (wet sanding for PLA/PETG)
3. Fill layer lines: automotive filler primer
4. Paint: acrylic or automotive paint after primer
5. Vapor smoothing: acetone for ABS/ASA (not PLA)
6. Annealing: PLA @ 60–70°C oven for 30 min (improves strength, reduces warp)
7. Heat treatment: Nylon @ 80°C for 4h (crystallization, moisture removal)

### SLA
1. Wash in IPA or resin cleaner (2 minutes typical)
2. Dry completely
3. UV cure: 405 nm, 10–30 minutes depending on resin
4. Remove supports carefully (pre-cure for rigid resins)
5. Sand and polish if needed
6. Post-cure temp: Tough resins @ 60°C for 60 min (maximizes mechanical properties)

---

## 11. Design Patterns Library

### Snap Fits
**Cantilever snap fit** (most common):
- Strain formula: ε = 1.5 × y × h / L²
- y = deflection, h = thickness, L = arm length
- Keep ε ≤ 0.02 (2%) for repeated use; ≤ 0.05 for one-time
- Design: constant thickness arm, generous fillet at base (r ≥ 0.6h)

**Annular snap fit** (shaft/collar):
- Deflection: y = ε × d / 2 (d = diameter)
- Undercut depth: 0.5–1.0 mm typical
- Assembly force increases with interference and friction coefficient

### Living Hinges
- Thickness: 0.2–0.5 mm for FDM (constant, no variation)
- Material: PP or HDPE ideal; PLA/PETG possible but limited cycles
- Strain at bend: ε = t / (2 × r) where r = bend radius; keep ε < yield strain
- Design: full-width hinge, no gaps, gradual thickness transition

### Compliant Mechanisms
- **Flexure pivot**: replaces rotational joint; torsion spring behavior
- **Parallel guidance**: two parallel flexures for linear translation
- Minimum bend radius: r_min = E × t / (2 × σ_yield)
- Avoid stress concentrations: constant width, fillet all corners

### Heat-Set Insert Bosses
| Insert | Hole ⌀ (mm) | Boss OD (mm) | Boss wall (mm) | Notes |
|--------|-------------|--------------|----------------|-------|
| M2     | 2.3         | 5.0          | ≥ 1.2          | Brass, knurled |
| M2.5   | 2.8         | 6.0          | ≥ 1.5          | Brass, knurled |
| M3     | 3.3         | 7.0          | ≥ 1.8          | Most common |
| M4     | 4.3         | 8.5          | ≥ 2.0          | High torque |

Installation: 200–230°C for 3–5 seconds; do not force-press cold.

### Press-Fit Bearings
| Bearing OD (mm) | Hole ⌀ (mm) | Interference (mm) | Notes |
|-----------------|-------------|-------------------|-------|
| 6 (MR126)       | 5.95        | 0.05              | Light press |
| 10 (MR106)      | 9.90        | 0.10              | Medium press |
| 15 (MR156)      | 14.85       | 0.15              | Tight press |

### Gears — Spur Gear Basics
- Module (m) = pitch diameter / teeth count
- Outer diameter = m × (z + 2)
- Root diameter = m × (z − 2.5)
- Backlash (printed): 0.1–0.3 mm depending on module and printer
- Minimum printable module: 0.5 for FDM 0.4 mm nozzle; 0.3 for SLA

---

## 12. Advanced FDM

### Variable Layer Height
- Use 0.08–0.12 mm on curved top surfaces; 0.2–0.3 mm on vertical walls
- Adaptive slicing: calculate curvature per layer and auto-select height
- Impact: up to 40% time reduction with equal or better surface quality

### Pressure Advance / Linear Advance
- Compensates for oozing by varying extrusion rate at acceleration/deceleration
- Tuning: print calibration tower, find PA value where corners are sharp but not under-extruded
- Typical values: PLA 0.04–0.08; PETG 0.08–0.12; TPU 0.12–0.20

### Input Shaping
- Cancels resonant vibrations (ringing/ghosting) by modifying motion profiles
- Common shapers: ZV, ZVD, MZV, EI
- Frequency measurement: print ringing tower, measure wave spacing
- Klipper default: `input_shaper freq_x=... freq_y=...`

### Nozzle Wear Modeling
- Abrasive filaments (CF, glow-in-dark, metal-filled) wear brass nozzles 10–50× faster
- Hardened steel: 3–5× life vs brass; Ruby/tungsten carbide: 20×+
- Wear symptom: extrusion width decreases over time → under-extrusion

### Multi-Material (AMS / MMU)
- Purge volume: 100–300 mm³ per color change (depends on color contrast)
- Minimize purge: order colors by similarity; use purge towers or side-wipe
- Filament tips: must be sharp and consistent; adjust cooling moves per material
- Loading order: flexible filaments last (TPU jams easily)

### Special Modes
- **Ironing**: extrudes a thin layer on top surface at slow speed; gives mirror finish
- **Fuzzy skin**: randomizes outer wall path for matte, organic texture; hides layer lines
- **Spiral vase**: single wall, no infill, continuous Z-rise; for decorative hollow parts

---

## 13. Advanced Resin (SLA/DLP/LCD)

### Anti-Aliasing & Pixel Dilation
- LCD printers render layers as raster images
- Anti-aliasing (2×/4×/8×) smooths stair-stepping on angled surfaces
- Pixel dilation: expands black pixels by N to compensate for light bleed
- Recommended: 2× AA + 1–2 pixel dilation for 50 µm screens

### Suction Force
- Formula: F = ΔP × A (ΔP ≈ resin weight per layer lift)
- Large flat cross-sections create highest suction → print failure / FEP damage
- Mitigation: tilt model 30–45°, hollow with drain holes, reduce lift speed

### Lift Speed Curves
| Phase | Speed | Reason |
|-------|-------|--------|
| Initial lift | 30–60 mm/min | Break suction gently |
| Mid lift | 100–150 mm/min | Fast travel |
| Top / retract | 60–100 mm/min | Avoid resin splashing |

### Exposure Calibration
- **Cones of Calibration** (free): 2-pass exposure finder
- **AmeraLabs town**: detailed calibration for XY accuracy and exposure
- Fine-tune: base layers 30–50 s; normal layers 2–3 s for 50 µm grey standard

### Resin Viscosity vs Temperature
- Viscosity drops ~2–3% per °C increase
- Cold resin (< 20°C): longer exposure needed, more suction, poor flow
- Heat resin to 25–30°C before printing for consistent results

---

## 14. SLS / MJF Professional

### Nesting Algorithms
- Pack parts in XY to maximize build density (50–70% typical)
- Z-clearance: 2–3 mm between parts for thermal isolation
- Orientation: minimize Z-height to reduce print time; flat faces down for surface quality

### Powder Refresh Ratio
- SLS: mix 30–50% fresh PA12 powder with used cake per build
- MJF: refresh rate ~15–20% (higher efficiency)
- Over-cycled powder: reduced mechanical properties, yellowing

### Anisotropy
- PA12: Z tensile strength ~70–80% of XY
- PA11: more ductile, better chemical resistance, lower stiffness
- Design: orient primary load in XY plane

### Post-Process
- Dyeing: common for SLS; media blast before dye for absorption
- Infiltration: cyanoacrylate or epoxy for sealing and strength

---

## 15. Metal AM (SLM / DMLS)

### Support Anchor Design
- Supports must conduct heat away and resist warping forces
- Anchor depth: 0.2–0.5 mm into part
- Support density: 50–70% for stainless steel; higher for titanium
- Removable via wire EDM, band saw, or CNC milling

### Residual Stress & Heat Treatment
- As-printed parts contain high residual stress from thermal gradients
- Stress relief: heat to 300–400°C (Al) or 600–700°C (Ti, steel), hold 2h
- HIP (Hot Isostatic Pressing): eliminates internal porosity; essential for aerospace

### Machining Allowances
- As-printed surface roughness Ra: 8–16 µm (Al), 10–20 µm (Ti, steel)
- Precision fits require 0.3–0.5 mm machining stock
- Threads: always machine or use threaded inserts; printed metal threads unreliable

---

## 16. Multi-Material & Color

### Purge Block Optimization
- Volume formula: V = π × r² × h × color_contrast_factor
- Contrast factor: 1.0 (white→light grey) to 3.0 (black→white)
- Minimize: use infill purge (sacrifice infill color for purge), side-wipe brushes

### Color Painting (PrusaSlicer / Orca)
- Paint tool assigns extruder per triangle
- Sharp color boundaries need purge tower or sacrificial layer
- Transition gradient: 5–10 layers for smooth color fade

### AMS / MMU Loading Order
1. Rigid, non-flexible filaments first
2. TPU / flexible last (or manual load)
3. Similar colors adjacent to reduce purge

---

## 17. Tolerance Engineering

### Statistical Tolerance Analysis (RSS)
- Total tolerance = √(t₁² + t₂² + ... + tₙ²)
- Printed parts typically achieve ±0.2 mm (FDM), ±0.05 mm (SLA), ±0.1 mm (SLS)

### Thermal Expansion Coefficients (CTE)
| Material | CTE (µm/m·K) | Compensation per 100°C |
|----------|--------------|------------------------|
| PLA      | 68           | 0.68%                  |
| PETG     | 70           | 0.70%                  |
| ABS      | 90           | 0.90%                  |
| Nylon    | 80           | 0.80%                  |
| Aluminum | 23           | 0.23%                  |

Shrinkage compensation: scale model by 1/(1 + ΔT × CTE) in slicer or CAD.

### Cp / Cpk for Printed Parts
- Cp ≥ 1.33 and Cpk ≥ 1.0 considered capable for functional prints
- Measure 30+ samples for statistical validity
- Major variation sources: ambient temp, filament diameter, bed level

---

## 18. Failure Mode Analysis (FMEA)

| Failure Mode | Cause | Detection | Prevention |
|--------------|-------|-----------|------------|
| **Warping** | Uneven cooling, poor adhesion | Visual (first layers) | Brim, heated bed, enclosure, slow first layer |
| **Layer delamination** | Low temp, wet filament, poor Z adhesion | Audible crack, weak part | Increase temp, dry filament, reduce fan |
| **Under-extrusion** | Clog, wrong e-steps, tangled spool | Gaps, weak layers | Cold pull, calibrate e-steps, check spool |
| **Over-extrusion** | Flow too high, nozzle too close | Bulging, dimensional error | Calibrate flow, relevel bed |
| **Stringing** | High temp, low retraction, wet filament | Fine hairs between parts | Lower temp, increase retraction, dry filament |
| **Support fusion** | Density too high, no interface gap | Cannot remove supports | Reduce density, add interface layers, increase gap |
| **Resin print fail** | Insufficient supports, wrong exposure | Nothing on build plate | Calibrate exposure, increase support density |
| **FEP puncture** | Over-tightened, suction force, debris | Resin leak | Check FEP tension, tilt large flat models |
| **SLS powder fusion** | Insufficient laser power, old powder | Weak, crumbly parts | Refresh powder, check laser calibration |
| **Metal crack** | Residual stress, thick-to-thin transition | X-ray / CT scan | Stress relief, HIP, uniform wall thickness |
