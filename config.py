# config.py

# =========================================================
# 1. SECTIONS DATABASE (Exact Data from Acrow Catalogs & Derived Timber)
# =========================================================
SECTIONS_DB = {
    # Timber 10x10
    "Timber 10x10": {"E": 76.00, "I": 833.33, "Mall": 1.05, "Qall": 13.40},
    "Double Timber 10x10": {"E": 76.00, "I": 1666.66, "Mall": 2.10, "Qall": 26.80},
    
    # Timber 7.5x7.5 (Derived)
    "Timber 7.5x7.5": {"E": 76.00, "I": 263.67, "Mall": 0.44, "Qall": 7.54},
    "Double Timber 7.5x7.5": {"E": 76.00, "I": 527.34, "Mall": 0.88, "Qall": 15.08},
    
    # Timber 5x10 (Derived)
    "Timber 5x10": {"E": 76.00, "I": 416.67, "Mall": 0.52, "Qall": 6.70},
    "Double Timber 5x10": {"E": 76.00, "I": 833.34, "Mall": 1.04, "Qall": 13.40},
    
    # Timber 5x20 (Derived)
    "Timber 5x20": {"E": 76.00, "I": 3333.33, "Mall": 2.10, "Qall": 13.40},
    "Double Timber 5x20": {"E": 76.00, "I": 6666.66, "Mall": 4.20, "Qall": 26.80},

    # Timber H20
    "Timber H20": {"E": 92.45, "I": 4613.00, "Mall": 5.00, "Qall": 11.00},
    "Double Timber H20": {"E": 92.45, "I": 9226.00, "Mall": 10.00, "Qall": 22.00},

    # Acrow Beam S12
    "Acrow Beam S12": {"E": 2100.00, "I": 141.50, "Mall": 5.00, "Qall": 55.00},
    "Double Acrow Beam S12": {"E": 2100.00, "I": 283.00, "Mall": 10.00, "Qall": 110.00},

    # Acrow X-Beam
    "Acrow X-Beam": {"E": 2100.00, "I": 147.00, "Mall": 5.20, "Qall": 20.00},
    "Double Acrow X-Beam": {"E": 2100.00, "I": 294.00, "Mall": 10.40, "Qall": 40.00},

    # Aluminum Beam
    "Aluminum Beam": {"E": 700.00, "I": 404.81, "Mall": 6.00, "Qall": 25.00},
    "Double Aluminum Beam": {"E": 700.00, "I": 809.62, "Mall": 12.00, "Qall": 50.00},

    # Soldier U100 (which is internally two channels back-to-back ][10)
    "Soldier U100": {"E": 2100.00, "I": 412.00, "Mall": 13.10, "Qall": 100.80},
    "Double Soldier U100": {"E": 2100.00, "I": 824.00, "Mall": 26.20, "Qall": 201.60},

    # Aliases for Strongback standard names used in UI (Mapping to catalog)
    "Soldier ][8": {"E": 2100.00, "I": 222.00, "Mall": 8.00, "Qall": 80.00}, 
    "Soldier ][10": {"E": 2100.00, "I": 412.00, "Mall": 13.10, "Qall": 100.80}, 
    "Soldier ][12": {"E": 2100.00, "I": 656.00, "Mall": 18.00, "Qall": 120.00}, 
}

# =========================================================
# 2. PUSH-PULL / STRUTS DATABASE
# =========================================================
STRUTS_DB = {
    "PPH164 (1.10:1.64m)": {"min": 1.10, "max": 1.64, "allow": 35.0},
    "PPH203 (1.35:2.03m)": {"min": 1.35, "max": 2.03, "allow": 35.0},
    "PPH254 (1.61:2.54m)": {"min": 1.61, "max": 2.54, "allow": 35.0},
    "PPH304 (1.90:3.04m)": {"min": 1.90, "max": 3.04, "allow": 35.0},
    "PPS132 (0.90:1.32m)": {"min": 0.90, "max": 1.32, "allow": 25.0},
    "MPP6 (4.40:6.20m)": {"min": 4.40, "max": 6.20, "allow": 25.0},
    "MPP9 (6.30:9.30m)": {"min": 6.30, "max": 9.30, "allow": 25.0},
}

# =========================================================
# 3. STANDARD LENGTHS DATABASE
# =========================================================
STD_LENGTHS = {
    "Timber H20": [1.8, 2.5, 2.9, 3.3, 3.6, 3.9, 4.2, 4.5, 4.9, 5.4, 5.9],
    "Double Timber H20": [1.8, 2.5, 2.9, 3.3, 3.6, 3.9, 4.2, 4.5, 4.9, 5.4, 5.9],
    
    "Acrow Beam S12": [2.0, 2.5, 3.0, 3.5, 4.0, 4.5],
    "Double Acrow Beam S12": [2.0, 2.5, 3.0, 3.5, 4.0, 4.5],
    
    "Acrow X-Beam": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Double Acrow X-Beam": [2.0, 2.5, 3.0, 3.5, 4.0],
    
    "Aluminum Beam": [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
    "Double Aluminum Beam": [2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0],
    
    "Soldier U100": [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.5, 5.0, 5.5, 6.0],
    "Double Soldier U100": [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0, 4.5, 5.0, 5.5, 6.0],

    "Timber 10x10": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Double Timber 10x10": [2.0, 2.5, 3.0, 3.5, 4.0],
    
    "Timber 7.5x7.5": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Double Timber 7.5x7.5": [2.0, 2.5, 3.0, 3.5, 4.0],
    
    "Timber 5x10": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Double Timber 5x10": [2.0, 2.5, 3.0, 3.5, 4.0],
    
    "Timber 5x20": [2.0, 2.5, 3.0, 3.5, 4.0],
    "Double Timber 5x20": [2.0, 2.5, 3.0, 3.5, 4.0]
}

# =========================================================
# 4. SHORING OPTIONS & ALLOWABLE PRESSURES
# =========================================================
SHORING_OPTIONS_SLAB = [
    "Acrow Prop", 
    "Shorebrace Frame", 
    "Acrow Frame", 
    "Cup-lock", 
    "Ring-lock", 
    "Other (Manual Input)"
]

ECO_FORM_ALLOW = {
    "Wall": {0.30: 90.0, 0.45: 90.0, 0.60: 90.0, 0.75: 75.0, 0.90: 65.0, 1.05: 55.0},
    "Column": {0.30: 90.0, 0.45: 90.0, 0.60: 90.0, 0.75: 90.0, 0.90: 90.0, 1.05: 90.0}
}

TECH_FORM_ALLOW = {
    "Wall": {0.30: 80.0, 0.45: 80.0, 0.60: 80.0, 0.75: 70.0, 0.90: 60.0, 1.05: 50.0},
    "Column": {0.30: 80.0, 0.45: 80.0, 0.60: 80.0, 0.75: 80.0, 0.90: 80.0, 1.05: 80.0}
}

CIRCULAR_ALLOW = {
    "Wall": {0.30: 80.0},
    "Column": {0.30: 80.0}
}
