# 3D Print Pre-Flight Checklist

Copy this checklist before every print job.

## Mesh Validation
- [ ] File format matches slicer capability (STL / 3MF / STEP)
- [ ] Model is watertight (no holes)
- [ ] No non-manifold edges or vertices
- [ ] No inverted face normals
- [ ] No zero-area or degenerate faces
- [ ] Scale verified in millimeters
- [ ] Model fits within build volume (or split planned)

## Design Rules
- [ ] Wall thickness ≥ printer minimum (FDM: 0.8–1.2 mm, SLA: 0.5 mm)
- [ ] Overhangs ≤ 45° (FDM) or ≤ 30° (SLA)
- [ ] Bridges within printer capability
- [ ] Tolerances added for holes, pegs, and moving parts
- [ ] Drain holes included for hollow resin prints (≥ 3 mm)
- [ ] Minimum feature size ≥ nozzle/laser spot size

## Slicer Setup
- [ ] Orientation optimized for surface finish and strength
- [ ] Layer height appropriate for detail vs speed
- [ ] Wall count meets strength requirements
- [ ] Infill density and pattern match use case
- [ ] Supports generated where needed; minimized where possible
- [ ] Support interface enabled for easy removal
- [ ] Temperatures match material recommendations
- [ ] Print speed calibrated for quality
- [ ] Cooling tuned for material (PLA: high, ABS: low)
- [ ] Retraction settings tuned (direct vs Bowden)
- [ ] Bed adhesion aid selected (brim/raft/glue) if needed

## Material & Printer
- [ ] Filament/resin is correct type and diameter
- [ ] Filament is dry (PETG, Nylon, PC especially)
- [ ] Bed is clean and level
- [ ] Nozzle is clean and not clogged
- [ ] Printer calibrated (e-steps, flow, Z-offset)
- [ ] Build plate prepared (PEI, glass, tape, glue)

## Post-Processing Plan
- [ ] Support removal tools ready
- [ ] Sanding/painting supplies available if needed
- [ ] Curing station ready (for resin)
- [ ] IPA or cleaning solution available (for resin)
