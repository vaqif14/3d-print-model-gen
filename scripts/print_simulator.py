#!/usr/bin/env python3
"""
Print Simulator — Lightweight G-Code Risk Analysis
Flags risky moves, cooling issues, and potential print failures.

Usage:
    python print_simulator.py output.gcode
    python print_simulator.py output.gcode --bed 220x220 --layer-time-threshold 15

Requirements:
    pip install numpy
"""

import argparse
import math
import re
import sys
from pathlib import Path

try:
    import numpy as np
except ImportError:
    print("Install with: pip install numpy")
    sys.exit(1)


class GCodeSimulator:
    def __init__(self, filepath, bed_x=220, bed_y=220):
        self.lines = Path(filepath).read_text().splitlines()
        self.bed_x = bed_x
        self.bed_y = bed_y
        self.moves = []  # list of dicts: {type, x, y, z, e, f, line_num}
        self.layers = []  # list of (z_height, moves_indices)
        self.stats = {
            'total_lines': len(self.lines),
            'extrusion_moves': 0,
            'travel_moves': 0,
            'total_distance_mm': 0.0,
            'total_extrusion_mm': 0.0,
            'min_x': float('inf'), 'max_x': float('-inf'),
            'min_y': float('inf'), 'max_y': float('-inf'),
            'min_z': float('inf'), 'max_z': float('-inf'),
            'warnings': [],
        }

    def parse(self):
        x = y = z = e = f = 0.0
        in_extrusion = False
        current_layer_z = 0.0
        layer_start_idx = 0
        relative_mode = False

        for i, line in enumerate(self.lines, 1):
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            # Absolute / relative positioning
            if line.startswith('G90'):
                relative_mode = False
                continue
            if line.startswith('G91'):
                relative_mode = True
                continue

            # Set position (e.g. G92 E0 at layer changes)
            if line.startswith('G92'):
                x = self._parse_val(line, 'X', x)
                y = self._parse_val(line, 'Y', y)
                z = self._parse_val(line, 'Z', z)
                e = self._parse_val(line, 'E', e)
                continue

            # Parse G0/G1
            if line.startswith('G0') or line.startswith('G1'):
                raw_x = self._parse_val(line, 'X', 0.0 if relative_mode else x)
                raw_y = self._parse_val(line, 'Y', 0.0 if relative_mode else y)
                raw_z = self._parse_val(line, 'Z', 0.0 if relative_mode else z)
                raw_e = self._parse_val(line, 'E', 0.0 if relative_mode else e)
                new_f = self._parse_val(line, 'F', f)

                if relative_mode:
                    new_x = x + raw_x
                    new_y = y + raw_y
                    new_z = z + raw_z
                    new_e = e + raw_e
                else:
                    new_x, new_y, new_z, new_e = raw_x, raw_y, raw_z, raw_e

                is_extrude = new_e > e + 1e-6
                dist = math.hypot(new_x - x, new_y - y)

                if new_z != z:
                    # Layer change
                    if self.moves:
                        self.layers.append((current_layer_z, list(range(layer_start_idx, len(self.moves)))))
                    current_layer_z = new_z
                    layer_start_idx = len(self.moves)

                self.moves.append({
                    'line': i,
                    'x': new_x, 'y': new_y, 'z': new_z,
                    'e': new_e, 'f': new_f,
                    'extrude': is_extrude,
                    'dist': dist,
                    'dx': new_x - x, 'dy': new_y - y,
                })

                if is_extrude:
                    self.stats['extrusion_moves'] += 1
                    self.stats['total_distance_mm'] += dist
                    self.stats['total_extrusion_mm'] += new_e - e
                else:
                    self.stats['travel_moves'] += 1

                # Bounds
                self.stats['min_x'] = min(self.stats['min_x'], new_x)
                self.stats['max_x'] = max(self.stats['max_x'], new_x)
                self.stats['min_y'] = min(self.stats['min_y'], new_y)
                self.stats['max_y'] = max(self.stats['max_y'], new_y)
                self.stats['min_z'] = min(self.stats['min_z'], new_z)
                self.stats['max_z'] = max(self.stats['max_z'], new_z)

                x, y, z, e, f = new_x, new_y, new_z, new_e, new_f
                continue

            # Parse G2/G3 arcs (center format with I, J)
            if line.startswith('G2') or line.startswith('G3'):
                clockwise = line.startswith('G2')
                raw_x = self._parse_val(line, 'X', 0.0 if relative_mode else x)
                raw_y = self._parse_val(line, 'Y', 0.0 if relative_mode else y)
                raw_z = self._parse_val(line, 'Z', 0.0 if relative_mode else z)
                raw_e = self._parse_val(line, 'E', 0.0 if relative_mode else e)
                new_f = self._parse_val(line, 'F', f)
                i_off = self._parse_val(line, 'I', 0.0)
                j_off = self._parse_val(line, 'J', 0.0)

                if relative_mode:
                    new_x = x + raw_x
                    new_y = y + raw_y
                    new_z = z + raw_z
                    new_e = e + raw_e
                else:
                    new_x, new_y, new_z, new_e = raw_x, raw_y, raw_z, raw_e

                arc_moves = self._interpolate_arc(
                    x, y, new_x, new_y, i_off, j_off, clockwise,
                    e, new_e, new_z, new_f, i
                )

                for move in arc_moves:
                    if move['z'] != z:
                        if self.moves:
                            self.layers.append((current_layer_z, list(range(layer_start_idx, len(self.moves)))))
                        current_layer_z = move['z']
                        layer_start_idx = len(self.moves)
                        z = move['z']

                    self.moves.append(move)
                    if move['extrude']:
                        self.stats['extrusion_moves'] += 1
                        self.stats['total_distance_mm'] += move['dist']
                        self.stats['total_extrusion_mm'] += move['e'] - e
                    else:
                        self.stats['travel_moves'] += 1

                    self.stats['min_x'] = min(self.stats['min_x'], move['x'])
                    self.stats['max_x'] = max(self.stats['max_x'], move['x'])
                    self.stats['min_y'] = min(self.stats['min_y'], move['y'])
                    self.stats['max_y'] = max(self.stats['max_y'], move['y'])
                    self.stats['min_z'] = min(self.stats['min_z'], move['z'])
                    self.stats['max_z'] = max(self.stats['max_z'], move['z'])

                    x, y, e = move['x'], move['y'], move['e']
                f = new_f
                continue

        if self.moves and layer_start_idx < len(self.moves):
            self.layers.append((current_layer_z, list(range(layer_start_idx, len(self.moves)))))

    def _parse_val(self, line, key, default):
        m = re.search(rf'{key}(-?\d+\.?\d*)', line)
        return float(m.group(1)) if m else default

    def _interpolate_arc(self, x0, y0, x1, y1, i, j, clockwise,
                         e_start, e_end, z, f, line_num):
        """Interpolate G2/G3 arc into linear segments using fixed segment count.
        Center format: center offset from start by I, J."""
        cx = x0 + i
        cy = y0 + j
        r = math.hypot(i, j)
        if r < 1e-6:
            # Degenerate arc — treat as straight line to endpoint
            dist = math.hypot(x1 - x0, y1 - y0)
            is_extrude = e_end > e_start + 1e-6
            return [{
                'line': line_num,
                'x': x1, 'y': y1, 'z': z,
                'e': e_end, 'f': f,
                'extrude': is_extrude,
                'dist': dist,
                'dx': x1 - x0, 'dy': y1 - y0,
            }]

        start_angle = math.atan2(y0 - cy, x0 - cx)
        end_angle = math.atan2(y1 - cy, x1 - cx)

        if clockwise:
            if end_angle > start_angle:
                end_angle -= 2 * math.pi
        else:
            if end_angle < start_angle:
                end_angle += 2 * math.pi

        sweep = end_angle - start_angle
        if abs(sweep) < 1e-6:
            sweep = -2 * math.pi if clockwise else 2 * math.pi

        # Fixed segment count: ~16 segments per full circle
        segments = max(1, int(abs(sweep) / (math.pi / 8)) + 1)
        total_e = e_end - e_start
        is_extrude = total_e > 1e-6

        moves = []
        prev_x, prev_y = x0, y0
        for seg in range(1, segments + 1):
            t = seg / segments
            angle = start_angle + sweep * t
            seg_x = cx + r * math.cos(angle)
            seg_y = cy + r * math.sin(angle)
            seg_e = e_start + total_e * t

            dist = math.hypot(seg_x - prev_x, seg_y - prev_y)
            moves.append({
                'line': line_num,
                'x': seg_x, 'y': seg_y, 'z': z,
                'e': seg_e, 'f': f,
                'extrude': is_extrude,
                'dist': dist,
                'dx': seg_x - prev_x, 'dy': seg_y - prev_y,
            })
            prev_x, prev_y = seg_x, seg_y

        # Force last point to exact endpoint to avoid drift
        if moves:
            moves[-1]['x'] = x1
            moves[-1]['y'] = y1
            moves[-1]['e'] = e_end
            moves[-1]['dx'] = x1 - (moves[-2]['x'] if len(moves) > 1 else x0)
            moves[-1]['dy'] = y1 - (moves[-2]['y'] if len(moves) > 1 else y0)
            moves[-1]['dist'] = math.hypot(moves[-1]['dx'], moves[-1]['dy'])

        return moves

    def analyze(self, layer_time_threshold=15, min_cooling_time=5):
        warnings = self.stats['warnings']

        # 1. Out of bounds check
        if self.stats['max_x'] > self.bed_x or self.stats['max_y'] > self.bed_y:
            warnings.append(f"OUT OF BOUNDS: print exceeds bed size ({self.bed_x}x{self.bed_y})")
        if self.stats['min_x'] < 0 or self.stats['min_y'] < 0:
            warnings.append("OUT OF BOUNDS: negative coordinates detected")

        # 2. Layer time analysis (cooling)
        fast_layers = 0
        for z, indices in self.layers:
            layer_dist = sum(self.moves[i]['dist'] for i in indices if self.moves[i]['extrude'])
            # Estimate time: assume average speed ~40 mm/s for extrusion
            avg_speed = 40  # mm/s
            layer_time_sec = layer_dist / avg_speed if avg_speed > 0 else 0

            if layer_time_sec < layer_time_threshold and layer_dist > 10:
                fast_layers += 1
                if fast_layers <= 3:  # Limit noise
                    warnings.append(
                        f"FAST LAYER at Z={z:.2f}: ~{layer_time_sec:.1f}s "
                        f"(threshold {layer_time_threshold}s) — risk of poor cooling"
                    )

        if fast_layers > 3:
            warnings.append(f"{fast_layers} layers are too fast — consider slowing down or enabling minimum layer time")

        # 3. High-speed overhangs (simplified: check for high-speed extrusion on upper layers)
        for move in self.moves:
            if move['extrude'] and move['f'] > 3000:  # > 50 mm/s
                # Flag if this is on a layer > 50% of max height (potential overhang area)
                if move['z'] > self.stats['max_z'] * 0.5:
                    # Only warn a few times
                    if len([w for w in warnings if 'HIGH SPEED' in w]) < 3:
                        warnings.append(
                            f"HIGH SPEED at line {move['line']}: F{move['f']:.0f} at Z={move['z']:.2f} — "
                            f"may cause overhang sagging"
                        )

        # 4. Excessive retractions
        retraction_count = 0
        for move in self.moves:
            if not move['extrude'] and move['dist'] > 5:
                retraction_count += 1
        if retraction_count > 500:
            warnings.append(f"EXCESSIVE TRAVELS: {retraction_count} long moves — may cause stringing")

        # 5. No extrusion check
        if self.stats['total_extrusion_mm'] < 1:
            warnings.append("NO EXTRUSION DETECTED — G-code may be travels only")

        # 6. Temperature commands check
        has_temp = any('M104' in line or 'M109' in line for line in self.lines)
        if not has_temp:
            warnings.append("NO TEMPERATURE SET FOUND — ensure hotend temp is set before print")

        # 7. Fan control check
        has_fan = any('M106' in line for line in self.lines)
        if not has_fan:
            warnings.append("NO FAN CONTROL FOUND — parts cooling may be insufficient")

    def report(self):
        print(f"\n{'='*60}")
        print(f"  G-CODE SIMULATION REPORT")
        print(f"{'='*60}")
        print(f"  Total lines parsed: {self.stats['total_lines']:,}")
        print(f"  Extrusion moves:    {self.stats['extrusion_moves']:,}")
        print(f"  Travel moves:       {self.stats['travel_moves']:,}")
        print(f"  Print distance:     {self.stats['total_distance_mm']:.1f} mm")
        print(f"  Extrusion length:   {self.stats['total_extrusion_mm']:.1f} mm")
        print(f"  Layers:             {len(self.layers)}")
        print(f"  Print bounds:")
        print(f"    X: {self.stats['min_x']:.1f} → {self.stats['max_x']:.1f}")
        print(f"    Y: {self.stats['min_y']:.1f} → {self.stats['max_y']:.1f}")
        print(f"    Z: {self.stats['min_z']:.1f} → {self.stats['max_z']:.1f}")

        if self.stats['warnings']:
            print(f"\n  ⚠️  WARNINGS ({len(self.stats['warnings'])}):")
            for w in self.stats['warnings']:
                print(f"    - {w}")
        else:
            print(f"\n  ✅ No warnings detected")

        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description='Print Simulator / G-Code Analyzer')
    parser.add_argument('gcode', help='Path to G-code file')
    parser.add_argument('--bed-x', type=float, default=220)
    parser.add_argument('--bed-y', type=float, default=220)
    parser.add_argument('--layer-time-threshold', type=float, default=15,
                        help='Minimum recommended layer time in seconds')
    args = parser.parse_args()

    sim = GCodeSimulator(args.gcode, args.bed_x, args.bed_y)
    sim.parse()
    sim.analyze(layer_time_threshold=args.layer_time_threshold)
    sim.report()


if __name__ == '__main__':
    main()
