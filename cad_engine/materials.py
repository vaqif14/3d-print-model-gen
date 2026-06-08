MATERIALS = {
    "PLA": {
        "nozzle_temp": 210, "bed_temp": 60, "fan_speed": 100,
        "cost_per_kg": 20.0, "density": 1.24,
        "colors": ["white", "black", "grey", "red", "blue", "green", "orange"],
        "strength_mpa": 35, "flexural_modulus_mpa": 3500,
        "max_temp_c": 55, "uv_stable": False,
    },
    "PETG": {
        "nozzle_temp": 240, "bed_temp": 80, "fan_speed": 30,
        "cost_per_kg": 25.0, "density": 1.27,
        "colors": ["white", "black", "grey", "red", "blue", "clear"],
        "strength_mpa": 45, "flexural_modulus_mpa": 2800,
        "max_temp_c": 75, "uv_stable": False,
    },
    "ABS": {
        "nozzle_temp": 240, "bed_temp": 105, "fan_speed": 0,
        "cost_per_kg": 22.0, "density": 1.04,
        "colors": ["white", "black", "grey"],
        "strength_mpa": 40, "flexural_modulus_mpa": 2300,
        "max_temp_c": 90, "uv_stable": False,
    },
    "ASA": {
        "nozzle_temp": 250, "bed_temp": 100, "fan_speed": 20,
        "cost_per_kg": 28.0, "density": 1.07,
        "colors": ["white", "black", "grey", "red"],
        "strength_mpa": 42, "flexural_modulus_mpa": 2400,
        "max_temp_c": 95, "uv_stable": True,
    },
    "TPU": {
        "nozzle_temp": 220, "bed_temp": 50, "fan_speed": 50,
        "cost_per_kg": 35.0, "density": 1.21,
        "colors": ["black", "clear", "red"],
        "strength_mpa": 25, "flexural_modulus_mpa": 80,
        "max_temp_c": 70, "uv_stable": False,
    },
    "Nylon": {
        "nozzle_temp": 260, "bed_temp": 90, "fan_speed": 30,
        "cost_per_kg": 45.0, "density": 1.14,
        "colors": ["white", "black", "natural"],
        "strength_mpa": 50, "flexural_modulus_mpa": 1800,
        "max_temp_c": 100, "uv_stable": True,
    },
    "PC": {
        "nozzle_temp": 280, "bed_temp": 110, "fan_speed": 30,
        "cost_per_kg": 50.0, "density": 1.20,
        "colors": ["clear", "black"],
        "strength_mpa": 65, "flexural_modulus_mpa": 2400,
        "max_temp_c": 115, "uv_stable": True,
    },
}

PRINTER_PROFILES = {
    "ender3": {
        "bed_x": 220, "bed_y": 220, "bed_z": 250,
        "nozzle_mm": 0.4, "accel_mm_s2": 500,
        "kinematics": "cartesian", "direct_drive": False,
    },
    "prusa": {
        "bed_x": 250, "bed_y": 210, "bed_z": 220,
        "nozzle_mm": 0.4, "accel_mm_s2": 1000,
        "kinematics": "cartesian", "direct_drive": True,
    },
    "bambu": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "nozzle_mm": 0.4, "accel_mm_s2": 10000,
        "kinematics": "corexy", "direct_drive": True,
    },
    "p1s": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "nozzle_mm": 0.4, "accel_mm_s2": 20000,
        "kinematics": "corexy", "direct_drive": True,
    },
    "p2s": {
        "bed_x": 256, "bed_y": 256, "bed_z": 256,
        "nozzle_mm": 0.4, "accel_mm_s2": 20000,
        "kinematics": "corexy", "direct_drive": True,
        "max_speed_mm_s": 600, "max_nozzle_temp": 300,
        "max_bed_temp": 110, "enclosed": True,
    },
    "voron": {
        "bed_x": 300, "bed_y": 300, "bed_z": 300,
        "nozzle_mm": 0.4, "accel_mm_s2": 3000,
        "kinematics": "corexy", "direct_drive": True,
    },
}
