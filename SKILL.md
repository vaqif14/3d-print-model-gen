---
name: 3d-print-model-gen
description: Pro-level Design for Additive Manufacturing (DfAM) expert system. Generates validated, slicer-ready 3D models from vague user requests by auto-selecting technology, material, geometry, tolerances, supports, infill, orientation, and slicer profiles. Covers FDM, SLA/DLP, SLS/MJF, SLM/DMLS, and multi-material workflows. Use when user mentions 3D printing, wants a part designed, needs STL/3MF/OBJ/STEP, talks about slicers (Cura, PrusaSlicer, Bambu Studio, OrcaSlicer), or asks about supports, overhangs, infill, mesh repair, tolerances, or print troubleshooting.
---

# 3D Print Model Generation — Pro Level

## Pro Workflow (Agent-Autonomous)

When user says "design a part" or gives a vague request, **do not ask 20 questions**. Run this 5-step interview, then decide everything yourself:

1. **Function** — What does the part do? (bracket, enclosure, gear, clip, prototype)
2. **Load & Environment** — Static/dynamic load? Temp? Chemicals? UV? Outdoor?
3. **Printer Technology** — FDM, SLA, SLS, SLM? (If unknown, default to FDM)
4. **Material Preference** — PLA, PETG, ABS, Nylon, Resin, Metal? (If unknown, pick best fit)
5. **Critical Dimensions** — Size, mounting pattern, hole sizes, moving clearances

**Auto-decide the rest**: wall thickness, fillets, overhang strategy, support type, infill pattern+density, layer height, temperatures, orientation, tolerances, post-processing. Deliver: model file + slicer profile + print report.

## Decision Matrix (Agent Uses This)

| Use Case | Tech | Material | Infill | Supports | Notes |
|----------|------|----------|--------|----------|-------|
| Visual prototype | FDM | PLA | 15% Gyroid | Minimal | Fast, cheap |
| Functional bracket | FDM | PETG/ABS | 40–60% Grid/Triangular | Tree if >45° | Ribs + fillets |
| Outdoor enclosure | FDM | ASA/PC | 30% Gyroid | Tree | UV resistant |
| Flexible part | FDM | TPU | 100% | None | Slow speed |
| Speed run (P1S/P2S) | FDM | PLA/PETG | 15% Lightning | Minimal | 500–600 mm/s, 20k accel |
| Multi-color (AMS 2 Pro) | FDM | PLA | 15% Gyroid | Tree | P2S: purge 100–150 mm³ per swap |
| Miniature / jewelry | SLA | Standard/Tough | Solid | Heavy (light) | 25–50 µm layers |
| Engineering fit | SLA | Tough/Rigid | Solid | Medium | 0.05 mm, calibrate |
| Batch production | SLS/MJF | PA12 | 100% solid | None | Nesting required |
| Metal structural | SLM | AlSi10Mg / 316L | Solid | Anchor supports | HIP + machine after |

## Red Flags (Auto-Correct These)

- Sharp internal corners → add fillets (r ≥ 2 mm) or stress cracks
- Uniform wall thickness everywhere → thicken stress points, thin non-structural areas
- Holes without tolerance → holes +0.2–0.3 mm, pegs −0.1 mm
- Ignoring anisotropy → orient layers perpendicular to primary stress
- Overhangs > 60° without redesign → chamfer, split, or tree supports
- No drain holes in hollow resin → add ≥ 3 mm holes, check suction force
- Moving parts with 0 clearance → minimum 0.2–0.3 mm gap

## Design Patterns Library

See [REFERENCE.md](REFERENCE.md) §11 for parametric formulas for:
- Snap fits (cantilever, annular, torsion)
- Living hinges (constant thickness, strain-limiting)
- Compliant mechanisms (flexure pivots, parallel guides)
- Heat-set insert bosses (M2–M4, optimal hole sizes, wall thickness)
- Press-fit bearings (clearance tables by diameter)
- Gears (spur, involute profile, backlash formulas)
- Threaded inserts & self-tapping holes

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/dfam_designer.py` | Interactive parametric part generator (bracket, enclosure, gear, clip) |
| `scripts/mesh_optimizer.py` | Hollowing, lattice infill, shell/offset, decimation, repair |
| `scripts/slicer_autopilot.py` | Auto-generate slicer profiles + cost/time estimates |
| `scripts/print_simulator.py` | G-code risk analysis + cooling validation |
| `scripts/pro_pipeline.py` | Master orchestrator — runs full pipeline from request to output |
| `scripts/validate_mesh.py` | Mesh validation (watertight, manifold, thin walls) |
| `scripts/generate_parametric.py` | Basic parametric shapes + tolerance gauges |

## Quick Start (Manual Mode)

If user brings their own model:
1. **Validate**: `python scripts/validate_mesh.py model.stl`
2. **Optimize**: `python scripts/mesh_optimizer.py model.stl --hollow --wall 2`
3. **Slice**: `python scripts/slicer_autopilot.py model.stl --material PETG --printer ender3`
4. **Simulate**: `python scripts/print_simulator.py output.gcode`

## Interactive Wizard (Recommended for Humans)

Run the guided UI to preview every decision before printing:

```bash
python scripts/interactive_wizard.py
```

This shows a clean preview box:
- Part type, material, dimensions
- Auto-derived: wall thickness, infill, supports, temperatures
- Cost & time estimate
- Choose: **[A]pprove** → runs pipeline | **[E]dit** → change any field | **[C]ancel**

See [REFERENCE.md](REFERENCE.md) for advanced topics and [EXAMPLES.md](EXAMPLES.md) for complete parametric designs.
