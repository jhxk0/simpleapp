"""FC placement table. Coordinates in mm, origin = board centre, +y down (KiCad)."""
LAYERS = 4
BOARD_W = BOARD_H = 36.0
CORNER_R = 3.0
HOLES = [(-15.25, -15.25), (15.25, -15.25), (-15.25, 15.25), (15.25, 15.25)]   # 30.5 x 30.5 M3
HOLE_KEEPOUT = 3.3

# JLCPCB 4-layer capability with margin
RULES = dict(m_MinClearance=0.1, m_TrackMinWidth=0.1, m_ViasMinSize=0.4, m_MinThroughDrill=0.2,
             m_CopperEdgeClearance=0.2, m_HoleClearance=0.2, m_HoleToHoleMin=0.25)
NETCLASSES = {
    "Default": dict(clearance=0.127, track_width=0.15, via_diameter=0.5, via_drill=0.3),
    "Power":   dict(clearance=0.13, track_width=0.5, via_diameter=0.6, via_drill=0.3),
    "Supply":  dict(clearance=0.127, track_width=0.2, via_diameter=0.5, via_drill=0.3),
}
NETCLASS_NETS = {
    "Power": ["VBAT", "+5V", "BUCK_SW"],
    "Supply": ["+3V3", "+3V3_IMU", "VDDA", "GND", "VBUS"],
}

FIXED = {
    "H1": (-15.25, -15.25, 0, "F"), "H2": (15.25, -15.25, 0, "F"),
    "H3": (-15.25, 15.25, 0, "F"), "H4": (15.25, 15.25, 0, "F"),
    "U1": (1.0, -3.5, 0, "F"),            # MCU
    "J1": (14.4, 0.0, 90, "F"),           # USB-C, opening +x
    "J2": (0.0, 14.45, 180, "F"),         # ESC 8-pin, opening +y
    "J5": (0.0, -14.45, 0, "F"),          # VTX 6-pin, opening -y
    "J3": (-14.45, -6.0, 90, "F"),        # RX 4-pin, opening -x
    "J4": (-14.45, 5.0, 90, "F"),         # GPS 6-pin, opening -x
    "U2": (-7.3, 7.4, 0, "F"),            # buck
    "L1": (-0.9, 7.6, 0, "F"),
    "C13": (-9.0, 11.5, 0, "F"), "C14": (-9.0, 13.9, 0, "F"),
    "U3": (-8.8, -8.6, 90, "F"),          # 3V3 LDO
    "U6": (1.0, -3.5, 0, "B"),            # IMU, board centre-ish, under MCU
    "U8": (4.6, 8.6, 0, "B"),             # flash (kept clear of the buck thermal pad)
    "U7": (9.0, -10.6, 0, "B"),           # baro
    "U5": (5.6, -7.0, 90, "B"),           # USB ESD, under the MCU's USB pins (PA11/PA12)
    "D1": (10.6, -11.0, 0, "F"), "D3": (10.6, -9.2, 0, "F"), "D4": (10.6, -7.4, 0, "F"),   # LEDs visible on top
    # wire pads, bottom side, left edge column
    "TP1": (-16.0, -9.0, 0, "B"), "TP2": (-16.0, -6.5, 0, "B"), "TP3": (-16.0, -4.0, 0, "B"),
    "TP4": (-16.0, -1.5, 0, "B"), "TP5": (-16.0, 1.0, 0, "B"), "TP6": (-16.0, 3.5, 0, "B"),
    "TP7": (-16.0, 6.0, 0, "B"), "TP8": (-16.0, 8.5, 0, "B"),
    # SWD pads, bottom edge
    "TP9": (-4.0, 16.3, 0, "B"), "TP10": (-2.0, 16.3, 0, "B"), "TP11": (0.0, 16.3, 0, "B"),
    "TP12": (2.0, 16.3, 0, "B"), "TP13": (4.0, 16.3, 0, "B"),
}
KEEPOUTS = {"B": [(8.8, -5.6, 18, 5.6),            # USB-C shell legs
                  (-11.2, 4.6, -3.4, 10.2),        # buck thermal-via pad comes through to B.Cu
                  (-17.5, -10.0, -13.0, 9.5),      # pad column + labels
                  (-5.0, 15.3, 5.0, 17.5)]}        # SWD pads
NEAR = {
    "C1": "U1.19", "C2": "U1.32", "C3": "U1.48", "C4": "U1.64", "C5": "U1.19",
    "FB1": "U1.13", "C6": "U1.13", "C7": "U1.13", "C8": "U1.31", "C9": "U1.47",
    "C10": "U1.7", "R1": "U1.60", "R2": "U1.28", "Y1": "U1.5", "C11": "Y1.1", "C12": "Y1.3",
    "C15": "U2.2", "C17": "U2.6", "C16": "U2.7", "R3": "U2.3", "R4": "U2.3", "R5": "U2.5", "R6": "U2.5",
    "C18": "L1.2", "C19": "L1.2",
    "C20": "U3.1", "C21": "U3.5", "U4": "U6.8", "C22": "U4.1", "C23": "U4.5",
    "C26": "U6.8", "C27": "U6.5", "C28": "U6.8", "C29": "U7.8", "C30": "U8.8",
    "R13": "J1.A5", "R14": "J1.B5", "D2": "J1.A4",
}
SIDE = {"U4": "B", "C22": "B", "C23": "B", "C26": "B", "C27": "B", "C28": "B"}
ORDER = ["C1", "C2", "C3", "C4", "C8", "C9", "C6", "C7", "FB1", "C10", "Y1", "C11", "C12", "R1", "R2",
         "C15", "C17", "C16", "R5", "R6", "R3", "R4", "C18", "C19",
         "U4", "C26", "C27", "C28", "C22", "C23", "U5", "D2", "R13", "R14"]
ANCHOR_SKIP = ["GND", "+3V3"]
SILK = [
    ("F405 FC rev A", 0.0, 3.6, "F", 0.8),
    ("ESC", 0.0, 11.0, "F", 0.7), ("VTX", 0.0, -11.3, "F", 0.7),
    ("RX", -11.0, -6.0, "F", 0.7), ("GPS", -11.0, 5.0, "F", 0.7),
    ("TX4", -13.9, -9.0, "B", 0.6), ("RX4", -13.9, -6.5, "B", 0.6), ("TX6", -13.9, -4.0, "B", 0.6),
    ("LED", -13.9, -1.5, "B", 0.6), ("5V", -13.9, 1.0, "B", 0.6), ("GND", -13.9, 3.5, "B", 0.6),
    ("BZ-", -13.9, 6.0, "B", 0.6), ("5V", -13.9, 8.5, "B", 0.6),
    ("DIO CLK RST 3V3 GND", 0.0, 14.6, "B", 0.5),
]
PLANES = [("In1_Cu", "GND")]                       # solid reference plane, not routed on
POURS = [("F_Cu", "GND"), ("B_Cu", "GND"), ("In2_Cu", "GND")]   # added after routing
