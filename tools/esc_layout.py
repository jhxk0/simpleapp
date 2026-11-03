"""4-in-1 ESC placement + power copper.  44x44 mm, 30.5 mm M3 pattern, 6 layers.

Stack-up (6 layers, 2 oz outer / >=1 oz inner):
                  F.Cu  power stage (FETs, phase pours, VBAT/GND feed strips) + drivers
                  In1   solid GND plane
                  In2   signals + GND fill
                  In3   signals + GND fill
                  In4   solid VBAT plane
                  B.Cu  MCUs + small parts, phase pours mirrored under the FETs, GND fill
Each board edge carries one ESC: three half-bridges with their phase pour running to a motor
pad at the edge.  Order JLC 2 oz outer copper.
"""
import math
import esc_design

LAYERS = 6
BOARD_W = BOARD_H = 44.0
CORNER_R = 3.0
HOLES = [(-15.25, -15.25), (15.25, -15.25), (-15.25, 15.25), (15.25, 15.25)]
HOLE_KEEPOUT = 3.3

RULES = dict(m_MinClearance=0.1, m_TrackMinWidth=0.1, m_ViasMinSize=0.4, m_MinThroughDrill=0.2,
             m_CopperEdgeClearance=0.25, m_HoleClearance=0.2, m_HoleToHoleMin=0.25)
NETCLASSES = {
    "Default": dict(clearance=0.127, track_width=0.15, via_diameter=0.5, via_drill=0.3),
    "Power":   dict(clearance=0.13, track_width=0.6, via_diameter=0.6, via_drill=0.3),
    "Supply":  dict(clearance=0.15, track_width=0.3, via_diameter=0.5, via_drill=0.3),
    "Gate":    dict(clearance=0.127, track_width=0.25, via_diameter=0.5, via_drill=0.3),
}
_ph = ["E%d_PH_%s" % (n, p) for n in range(1, 5) for p in "ABC"]
NETCLASS_NETS = {
    "Power": ["VBAT", "GND"] + _ph,
    "Supply": ["+10V_A", "+10V_B", "VFILT_A", "VFILT_B"] + ["+3V3_%d" % n for n in range(1, 5)],
    "Gate": ["E%d_G%s_%s" % (n, hl, p) for n in range(1, 5) for hl in "HL" for p in "ABC"] +
            ["E%d_BST_%s" % (n, p) for n in range(1, 5) for p in "ABC"],   # gates are driven directly
}

# ------------------------------------------------------------------ helpers
def rot(x, y, phi):
    """rotate a point by phi degrees CCW on screen (KiCad convention, +y down)"""
    c, s = math.cos(math.radians(phi)), math.sin(math.radians(phi))
    return (round(x * c + y * s, 3), round(-x * s + y * c, 3))

def box(x0, y0, x1, y1, phi):
    return [rot(x, y, phi) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]

# refs by role, read from the design source so this stays in sync with the schematic
parts = esc_design.DESIGN.parts
def grp(g): return [p for p in parts if p.group == g]
def first(g, prefix, val=None):
    return [p.ref for p in grp(g) if p.ref.startswith(prefix) and (val is None or p.value == val)]

FIXED, ZONES, VIAS, TRACKS, NEAR, SIDE, SILK = {}, [], [], [], {}, {}, []
POWER_BANDS, POWER_BANDS_B, TAP_KEEPOUTS = [], [], []
for hx, hy in HOLES:
    pass
for i, h in enumerate(first("Mechanical", "H")):
    FIXED[h] = (HOLES[i][0], HOLES[i][1], 0, "F")

EDGE = BOARD_H / 2
Y_FET = 16.5           # FET centre distance from board centre (edge at 22)
PITCH = 7.85           # half-bridge pitch along the edge
for n in range(1, 5):
    phi = (n - 1) * 90                     # ESC1 rear(+y), ESC2 right, ESC3 front, ESC4 left
    ps = grp("ESC%d power stage" % n)
    mcu = first("ESC%d MCU" % n, "U")
    for k, ph in enumerate("ABC"):
        blk = ps[k * 9:(k + 1) * 9]        # driver, C1u, Cboot, Qhs, Qls, TPmotor, R18k, R2k, R18k
        drv, c1u, cbst, qhs, qls, tpm = [p.ref for p in blk[:6]]
        xu = (k - 1) * PITCH
        def put(ref, x, y, r, side="F"):
            px, py = rot(x, y, phi)
            FIXED[ref] = (px, py, (r + phi) % 360, side)
        put(qhs, xu - 1.96, Y_FET, 90)              # source/gate row faces the edge
        put(qls, xu + 1.94, Y_FET, 270)            # drain faces the edge, source/gate inboard
        put(tpm, xu, EDGE - 1.55, 0)               # motor pad 2.5x2.5 at the edge
        put(drv, xu, Y_FET - 5.6, 0)
        NEAR.update({c1u: drv + ".1", cbst: drv + ".8"})
        net = "/E%d_PH_%s" % (n, ph)
        # phase pour: below both FETs out to the edge, on F and B.  The high-side gate pin sits on
        # the phase side of its FET, so both pours get a notch there: on F around the gate pad, on B
        # a channel open towards the board centre for the gate trace to leave by.
        def notched(x0, x1, top=Y_FET + 1.0, bottom=Y_FET + 2.65):
            pts = [(xu - 3.85, top), (xu + x0, top), (xu + x0, bottom), (xu + x1, bottom), (xu + x1, top),
                   (xu + 3.85, top), (xu + 3.85, EDGE - 0.35), (xu - 3.85, EDGE - 0.35)]
            return [rot(x, y, phi) for x, y in pts]
        ZONES.append(("F_Cu", net, notched(-1.45, 0.45), 5))
        ZONES.append(("B_Cu", net, notched(-1.0, 0.3), 5))
        gate = "/E%d_GH_%s" % (n, ph)
        gx, gy = xu - 0.99, Y_FET + 1.44                   # HS gate pad (FET rotated 90)
        vx, vy = xu - 0.35, Y_FET + 2.2                    # escape via inside the notch
        TRACKS.append(("F_Cu", gate, rot(gx, gy, phi), rot(vx, vy, phi), 0.25))
        VIAS.append((rot(vx, vy, phi), gate))
        TRACKS.append(("B_Cu", gate, rot(vx, vy, phi), rot(vx, Y_FET + 0.4, phi), 0.25))
        # phase tap: B.Cu from inside the phase pour, through the gap in the via fields, to a via
        # beside the driver - gives SH, the boot cap and the BEMF dividers a short local hookup
        TRACKS.append(("B_Cu", net, rot(xu + 0.9, Y_FET + 1.3, phi), rot(xu + 0.9, Y_FET - 4.0, phi), 0.3))
        VIAS.append((rot(xu + 0.9, Y_FET - 4.0, phi), net))
        cx = [rot(x, y, phi) for x, y in ((xu + 0.3, Y_FET - 4.5), (xu + 1.5, Y_FET + 1.3))]
        TAP_KEEPOUTS.append((min(cx[0][0], cx[1][0]), min(cx[0][1], cx[1][1]), max(cx[0][0], cx[1][0]), max(cx[0][1], cx[1][1])))
        # VBAT feed strip over the high-side drain; GND strip over the low-side source row,
        # leaving a channel between them for the low-side gate (pad at xu+0.98) to reach its driver
        ZONES.append(("F_Cu", "/VBAT", box(xu - 3.85, Y_FET - 3.9, xu - 0.15, Y_FET - 1.0, phi), 5))
        ZONES.append(("F_Cu", "/GND", box(xu + 1.35, Y_FET - 3.9, xu + 3.85, Y_FET - 1.15, phi), 5))
        for dx in (-3.3, -2.3, -1.3, -0.5):
            for dy in (-3.3, -2.45):
                VIAS.append((rot(xu + dx, Y_FET + dy, phi), "/VBAT"))
        for dx in (1.75, 2.6, 3.4):
            for dy in (-3.3, -2.45):
                VIAS.append((rot(xu + dx, Y_FET + dy, phi), "/GND"))
        for dx in (-3.2, -1.5, 0.4, 2.2, 3.3):          # stitch phase pours F<->B
            VIAS.append((rot(xu + dx, EDGE - 3.0 if abs(dx) > 1 else EDGE - 3.4, phi), net))
        lx, ly = rot(xu, EDGE - 3.9, phi)
        SILK.append(("M%d%s" % (n, ph), lx, ly, "B", 0.7))
    # MCU on the bottom, in the corner next to its edge (clear of the power band and the centre)
    mx, my = rot(8.7, 8.7, phi)
    FIXED[mcu[0]] = (mx, my, phi, "B")
    # no other parts over this edge's power band (FETs, feed strips, via fields, phase pours)
    def kbox(x0, y0, x1, y1):
        bx = [rot(x, y, phi) for x, y in ((x0, y0), (x1, y1))]
        return (min(bx[0][0], bx[1][0]), min(bx[0][1], bx[1][1]), max(bx[0][0], bx[1][0]), max(bx[0][1], bx[1][1]))
    POWER_BANDS.append(kbox(-12.0, 12.6, 12.0, EDGE))                 # top: FETs + feed strips
    POWER_BANDS_B.append(kbox(-12.0, Y_FET - 3.75, 12.0, Y_FET - 1.95))   # bottom: via fields
    POWER_BANDS_B.append(kbox(-12.0, Y_FET + 0.2, 12.0, EDGE))           # bottom: gate escapes + phase pours

# ------------------------------------------------------------------ centre: battery pads, FC link
# Battery pads feed the In1 GND / In4 VBAT planes directly through 50-via arrays each.
bat = first("Battery & sense", "TP", "BAT+")[0], first("Battery & sense", "TP", "BAT-")[0]
FIXED[bat[0]] = (-3.2, 2.6, 0, "F")
FIXED[bat[1]] = (3.2, 2.6, 0, "F")
J = first("FC connector", "J")[0]
FIXED[J] = (0.0, -6.2, 0, "F")
for i in range(5):
    for j in range(10):
        y = -1.9 + j * 1.0
        VIAS.append(((-5.2 + i * 1.0, y), "/VBAT"))
        VIAS.append(((1.2 + i * 1.0, y), "/GND"))

KEEPOUTS = {"F": [(-6.2, -3.0, 6.2, 8.2)] + POWER_BANDS,
            "B": [(-5.9, -2.6, 5.9, 7.8)] + POWER_BANDS_B + TAP_KEEPOUTS}
SIDE = {}
for p in parts:
    if p.ref not in FIXED and p.ref not in NEAR:
        SIDE[p.ref] = "B"            # small parts default to the bottom
for r in NEAR:
    SIDE[r] = "F"                    # driver satellites on top next to the driver
ORDER = list(NEAR) + first("Gate drive supply", "U") + [first("ESC%d MCU" % n, "U")[1] for n in range(1, 5)]
ANCHOR_SKIP = ["/GND", "/VBAT", "GND", "VBAT"]
# 6 layers: F power stage | In1 GND plane | In2 signal | In3 signal | In4 VBAT plane | B control.
# Order 2 oz outer copper and at least 1 oz inner copper.
PLANES = [("In1_Cu", "GND"), ("In4_Cu", "VBAT")]
POURS = [("B_Cu", "GND"), ("F_Cu", "GND"), ("In2_Cu", "GND"), ("In3_Cu", "GND")]
SILK += [("4in1 ESC rev B  AM32 JUPITER_80_G071", 0, 0.0, "B", 0.8),
         ("+", -3.2, -3.9, "F", 1.2), ("-", 3.2, -3.9, "F", 1.2)]
