#!/usr/bin/env python3
"""
Interactive 3D Print Design Wizard
Shows a clean preview of all decisions before executing.
User can approve, edit any field, or cancel.

Usage:
    python interactive_wizard.py

Requirements:
    pip install trimesh numpy scipy shapely manifold3d
"""

import argparse
import math
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()

# ── Pretty Print Helpers ─────────────────────────────────────────────────────

def box_print(title, rows, footer=""):
    """Print a boxed summary."""
    max_len = max(len(title), max((len(f"{k}: {v}") for k, v in rows), default=0), len(footer)) + 4
    print(f"\n┌{'─' * max_len}┐")
    print(f"│ {title:^{max_len}} │")
    print(f"├{'─' * max_len}┤")
    for key, value in rows:
        line = f"{key}: {value}"
        print(f"│ {line:<{max_len}} │")
    if footer:
        print(f"├{'─' * max_len}┤")
        print(f"│ {footer:<{max_len}} │")
    print(f"└{'─' * max_len}┘\n")


def ask_choice(prompt, choices, default=None):
    """Ask user to pick from a list."""
    opts = "/".join(f"[{c.upper()}]{c[1:]}" if default and c.lower() == default.lower() else c for c in choices)
    while True:
        ans = input(f"{prompt} ({opts}): ").strip().lower()
        if not ans and default:
            return default.lower()
        if ans in [c.lower() for c in choices]:
            return ans
        print("Invalid choice. Try again.")


def ask_number(prompt, default=None, allow_empty=False):
    """Ask for a number."""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        ans = input(f"{prompt}{suffix}: ").strip()
        if not ans:
            if allow_empty:
                return None
            if default is not None:
                return default
            continue
        try:
            return float(ans)
        except ValueError:
            print("Please enter a valid number.")


def ask_text(prompt, default=None):
    """Ask for text input."""
    suffix = f" [{default}]" if default is not None else ""
    ans = input(f"{prompt}{suffix}: ").strip()
    return ans if ans else default


# ── Design Session ───────────────────────────────────────────────────────────

class DesignSession:
    def __init__(self):
        self.params = {
            'part': 'bracket',
            'material': 'PETG',
            'tech': 'FDM',
            'printer': 'ender3',
            'load_kg': 5.0,
            'width': 60.0,
            'height': 40.0,
            'depth': 25.0,
            'output_dir': './output',
        }
        self.derived = {}
        self._compute_derived()

    def _compute_derived(self):
        """Auto-compute derived values based on current params."""
        mat = self.params['material']
        tech = self.params['tech']
        part = self.params['part']
        load = self.params.get('load_kg', 5)

        # Material properties (simplified)
        mat_props = {
            'PLA': {'temp': 210, 'bed': 60, 'cost_kg': 20, 'density': 1.24},
            'PETG': {'temp': 240, 'bed': 80, 'cost_kg': 25, 'density': 1.27},
            'ABS': {'temp': 240, 'bed': 105, 'cost_kg': 22, 'density': 1.04},
            'ASA': {'temp': 250, 'bed': 100, 'cost_kg': 28, 'density': 1.07},
            'TPU': {'temp': 220, 'bed': 50, 'cost_kg': 35, 'density': 1.21},
            'Nylon': {'temp': 260, 'bed': 90, 'cost_kg': 45, 'density': 1.14},
            'PC': {'temp': 280, 'bed': 110, 'cost_kg': 50, 'density': 1.20},
        }
        mp = mat_props.get(mat, mat_props['PETG'])

        # Design rules
        rules = {
            'FDM': {'min_wall': 0.8, 'rec_wall': 1.5, 'layer': 0.2, 'overhang': 45},
            'SLA': {'min_wall': 0.5, 'rec_wall': 1.0, 'layer': 0.05, 'overhang': 30},
        }
        rule = rules.get(tech, rules['FDM'])

        # Auto wall thickness
        if part == 'bracket':
            wall = max(rule['rec_wall'], rule['rec_wall'] * (load / 5))
            wall = round(min(wall, 5.0), 1)
        elif part == 'enclosure':
            wall = 2.0
        else:
            wall = rule['rec_wall']

        # Infill
        if load < 2:
            infill = '15% Gyroid (visual)'
        elif load < 10:
            infill = '30% Gyroid (general)'
        else:
            infill = '50% Grid (functional)'

        # Supports
        supports = 'Tree' if tech == 'FDM' else 'Heavy (light)'

        # Rough estimates
        vol = self.params['width'] * self.params['height'] * self.params['depth'] * 0.3
        weight_g = vol * mp['density'] / 1000
        cost = weight_g / 1000 * mp['cost_kg']
        time_h = (vol / (40 * 0.4 * 0.2 * 3600)) * 1.5  # rough flow rate

        self.derived = {
            'wall_thickness': f"{wall} mm",
            'layer_height': f"{rule['layer']} mm",
            'overhang_limit': f"≤ {rule['overhang']}°",
            'nozzle_temp': f"{mp['temp']}°C",
            'bed_temp': f"{mp['bed']}°C",
            'infill': infill,
            'supports': supports,
            'hole_tolerance': '+0.3 mm' if tech == 'FDM' else '+0.2 mm',
            'est_weight': f"{weight_g:.1f} g",
            'est_cost': f"${cost:.2f}",
            'est_time': f"~{max(time_h, 0.3):.1f} hours",
        }

    def preview(self):
        """Show the design preview box."""
        rows = [
            ("Part Type", self.params['part'].upper()),
            ("Material", self.params['material']),
            ("Technology", self.params['tech']),
            ("Printer", self.params['printer']),
            ("Dimensions", f"{self.params['width']} × {self.params['height']} × {self.params['depth']} mm"),
            ("Load Target", f"{self.params.get('load_kg', '-')} kg"),
            ("", ""),
            ("Wall Thickness", self.derived['wall_thickness']),
            ("Layer Height", self.derived['layer_height']),
            ("Nozzle Temp", self.derived['nozzle_temp']),
            ("Bed Temp", self.derived['bed_temp']),
            ("Infill", self.derived['infill']),
            ("Supports", self.derived['supports']),
            ("Overhang Limit", self.derived['overhang_limit']),
            ("Hole Tolerance", self.derived['hole_tolerance']),
            ("", ""),
            ("Est. Weight", self.derived['est_weight']),
            ("Est. Cost", self.derived['est_cost']),
            ("Est. Time", self.derived['est_time']),
        ]
        box_print("3D PRINT DESIGN PREVIEW", rows, "[A]pprove  [E]dit  [C]ancel")

    def run(self):
        print("\n" + "=" * 60)
        print("   3D PRINT DESIGN WIZARD")
        print("   Pro-Level DfAM Assistant")
        print("=" * 60)

        while True:
            self._compute_derived()
            self.preview()

            choice = ask_choice("Your decision", ["approve", "edit", "cancel"], default="approve")

            if choice == "approve":
                self._execute()
                return True
            elif choice == "edit":
                self._edit()
            else:
                print("\nDesign cancelled. No files written.")
                return False

    def _edit(self):
        """Let user edit specific fields."""
        print("\n--- Edit Menu ---")
        editable = {
            '1': ('part', 'Part type', ['bracket', 'enclosure', 'gear', 'snap_fit']),
            '2': ('material', 'Material', ['PLA', 'PETG', 'ABS', 'ASA', 'TPU', 'Nylon', 'PC']),
            '3': ('tech', 'Technology', ['FDM', 'SLA']),
            '4': ('printer', 'Printer', ['ender3', 'prusa', 'bambu', 'p1s', 'p2s', 'voron']),
            '5': ('load_kg', 'Load (kg)', None),
            '6': ('width', 'Width (mm)', None),
            '7': ('height', 'Height (mm)', None),
            '8': ('depth', 'Depth (mm)', None),
            '9': ('output_dir', 'Output directory', None),
        }

        for key, (field, label, _) in editable.items():
            print(f"  {key}. {label}: {self.params.get(field, '-')}")

        ans = ask_text("Enter number to edit (or press Enter to go back)")
        if not ans or ans not in editable:
            return

        field, label, choices = editable[ans]
        if choices:
            print(f"Options: {', '.join(choices)}")
        new_val = ask_text(f"New {label}", default=str(self.params.get(field, '')))

        if new_val is not None:
            # Type conversion
            if field in ['load_kg', 'width', 'height', 'depth']:
                try:
                    self.params[field] = float(new_val)
                except ValueError:
                    print("Invalid number. Keeping previous value.")
            else:
                self.params[field] = new_val

    def _execute(self):
        """Run the pro_pipeline with current params."""
        print("\n>>> Executing pipeline...\n")
        cmd = [
            sys.executable, str(SCRIPT_DIR / "pro_pipeline.py"),
            '--part', self.params['part'],
            '--material', self.params['material'],
            '--tech', self.params['tech'],
            '--printer', self.params['printer'],
            '--output-dir', self.params['output_dir'],
        ]

        if self.params['part'] == 'bracket':
            cmd += [
                '--width', str(self.params['width']),
                '--height', str(self.params['height']),
                '--depth', str(self.params['depth']),
                '--load', str(self.params['load_kg']),
            ]
        elif self.params['part'] == 'enclosure':
            cmd += [
                '--width', str(self.params['width']),
                '--height', str(self.params['height']),
                '--depth', str(self.params['depth']),
            ]

        subprocess.run(cmd)

        out = Path(self.params['output_dir']).resolve()
        print(f"\n✅ Done! Your files are in: {out}")
        print(f"   • part.stl       — ready to slice")
        print(f"   • profile.ini    — slicer settings")
        print(f"   • print_report.md — full report")


def main():
    wizard = DesignSession()
    wizard.run()


if __name__ == '__main__':
    main()
