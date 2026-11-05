"""4-in-1 ESC placement + power copper.  46x46 mm, 30.5 mm M3 pattern, 6 layers.

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
BOARD_W = BOARD_H = 46.0
CORNER_R = 3.0
HOLES = [(-15.25, -15.25), (15.25, -15.25), (-15.25, 15.25), (15.25, 15.25)]
HOLE_KEEPOUT = 3.3

RULES = dict(m_MinClearance=0.1, m_TrackMinWidth=0.1, m_ViasMinSize=0.4, m_MinThroughDrill=0.2,
             m_CopperEdgeClearance=0.25, m_HoleClearance=0.2, m_HoleToHoleMin=0.25)
NETCLASSES = {
    "Default": dict(clearance=0.127, track_width=0.15, via_diameter=0.5, via_drill=0.3),
    "Power":   dict(clearance=0.13, track_width=0.3, via_diameter=0.6, via_drill=0.3),
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
POWER_BANDS, POWER_BANDS_B, TAP_KEEPOUTS, DRV_KEEPOUTS, NO_TRACKS = [], [], [], [], []
for hx, hy in HOLES:
    pass
for i, h in enumerate(first("Mechanical", "H")):
    FIXED[h] = (HOLES[i][0], HOLES[i][1], 0, "F")

EDGE = BOARD_H / 2
Y_FET = 17.5           # FET centre distance from board centre (edge at 23)
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
        YD = Y_FET - 5.6                            # driver centre
        put(drv, xu, YD, 0)                         # outputs (pins 5-8) on the right, LO lowest
        put(c1u, xu - 0.6, YD - 2.05, 0)            # VDD bypass above the driver: +10V left, GND right
        put(cbst, xu + 2.8, YD - 0.3, 270)          # boot cap right of the driver: BST top, phase bottom
        net = "/E%d_PH_%s" % (n, ph)
        gate = "/E%d_GH_%s" % (n, ph)
        gl = "/E%d_GL_%s" % (n, ph)
        bst = "/E%d_BST_%s" % (n, ph)
        rail = "/+10V_A" if n <= 2 else "/+10V_B"
        def T(layer, nn, pts, w):
            for a, b in zip(pts, pts[1:]):
                TRACKS.append((layer, nn, rot(xu + a[0], a[1], phi), rot(xu + b[0], b[1], phi), w))
        def V(x, y, nn, dia=0.6):
            VIAS.append((rot(xu + x, y, phi), nn, dia))
        # phase pour: below both FETs out to the edge, on F and B.  The high-side gate pin sits on
        # the phase side of its FET, so the F pour gets a notch around it.
        def notched(x0, x1, top=Y_FET + 1.0, bottom=Y_FET + 2.65):
            pts = [(xu - 3.85, top), (xu + x0, top), (xu + x0, bottom), (xu + x1, bottom), (xu + x1, top),
                   (xu + 3.85, top), (xu + 3.85, EDGE - 0.35), (xu - 3.85, EDGE - 0.35)]
            return [rot(x, y, phi) for x, y in pts]
        ZONES.append(("F_Cu", net, notched(-1.45, 0.45), 5))
        ZONES.append(("B_Cu", net, box(xu - 3.85, Y_FET + 1.0, xu + 3.85, EDGE - 0.35, phi), 5))
        # no router tracks across the power copper (they would cut it into islands)
        NO_TRACKS.append(("F_Cu", notched(-1.45, 0.45)))
        NO_TRACKS.append(("B_Cu", box(xu - 3.85, Y_FET + 1.35, xu + 3.85, EDGE - 0.35, phi)))
        # ---- fixed driver <-> FET links (identical for all 12 half-bridges) ----
        # GL: LO (pin 5) straight down the F channel between the feed strips to the low-side gate
        T("F_Cu", gl, [(0.95, YD + 0.75), (0.95, Y_FET - 1.9), (0.97, Y_FET - 1.44)], 0.25)
        # GH: high-side gate pad -> via in the pour notch -> In2 up the via-field gap -> via -> HO (pin 7)
        T("F_Cu", gate, [(-0.99, Y_FET + 1.44), (-0.35, Y_FET + 2.2)], 0.25)
        V(-0.35, Y_FET + 2.2, gate, 0.5)
        T("In2_Cu", gate, [(-0.35, Y_FET + 2.2), (-0.35, Y_FET + 0.8), (0.4, Y_FET + 0.05),
                           (0.4, YD + 0.1), (1.9, YD - 0.45)], 0.25)
        V(1.9, YD - 0.45, gate, 0.5)
        T("F_Cu", gate, [(0.95, YD - 0.25), (1.9, YD - 0.45)], 0.25)
        # SH: phase stitch via in the pour -> In3 up the same gap -> via -> HS (pin 6) and boot cap
        T("In3_Cu", net, [(0.4, EDGE - 3.4), (0.4, Y_FET - 4.05), (2.4, Y_FET - 4.35)], 0.3)
        V(2.4, Y_FET - 4.35, net)
        T("F_Cu", net, [(0.95, YD + 0.25), (2.8, YD + 0.25)], 0.3)
        T("F_Cu", net, [(2.4, YD + 0.25), (2.4, Y_FET - 4.35)], 0.3)
        # HB (pin 8) over the HO via to the boot cap
        T("F_Cu", bst, [(0.95, YD - 0.75), (1.3, YD - 0.75), (1.6, YD - 1.15), (2.45, YD - 1.15),
                        (2.8, YD - 0.78)], 0.25)
        # VDD bypass and driver ground: cap GND -> exposed pad -> VSS (pin 4) -> GND via
        T("F_Cu", rail, [(-0.95, YD - 0.75), (-0.98, YD - 1.9)], 0.3)
        T("F_Cu", "/GND", [(0.1, YD - 1.9), (0.1, YD - 0.6)], 0.3)
        T("F_Cu", "/GND", [(-0.95, YD + 0.75), (-0.3, YD + 0.6)], 0.3)
        T("F_Cu", "/GND", [(-0.95, YD + 0.75), (-1.3, YD + 1.35)], 0.3)
        V(-1.3, YD + 1.35, "/GND")
        # driver inputs HI (pin 2) / LI (pin 3): short F escapes to vias on the left of the driver
        hi, li = "/E%d_H%s" % (n, ph), "/E%d_L%s" % (n, ph)
        T("F_Cu", hi, [(-0.95, YD - 0.25), (-1.45, YD - 0.25), (-1.9, YD - 0.55)], 0.15)
        T("F_Cu", li, [(-0.95, YD + 0.25), (-1.45, YD + 0.25), (-1.9, YD + 0.55)], 0.15)
        V(-1.9, YD - 0.55, hi, 0.5)
        V(-1.9, YD + 0.55, li, 0.5)
        # back-EMF divider on the bottom, under the FETs between the via fields and the phase pour;
        # its output leaves through the bottom channel between the VBAT and GND via fields.  The 10k
        # neutral resistors (rn) are auto-placed next to the MCU.
        rb, r2k, rn = [p.ref for p in blk[6:9]]
        NEAR[rn] = mcu[0] + ".10"                 # 10k neutral resistors sit at the MCU's PA1
        YR = Y_FET - 0.85
        put(rb, xu + 0.4, YR, 90, "B")
        put(r2k, xu + 1.45, YR, 270, "B")
        bemf = "/E%d_BEMF_%s" % (n, ph)
        T("B_Cu", net, [(0.4, YR + 0.48), (0.4, Y_FET + 1.15)], 0.3)
        T("B_Cu", bemf, [(1.45, YR - 0.48), (0.4, YR - 0.48), (0.4, Y_FET - 4.7)], 0.2)
        T("B_Cu", "/GND", [(1.45, YR + 0.48), (2.4, YR + 0.48), (2.6, Y_FET - 2.45)], 0.3)   # to the GND via field
        cx = [rot(xu + x, y, phi) for x, y in ((-0.3, Y_FET - 4.9), (2.9, Y_FET + 0.2))]
        TAP_KEEPOUTS.append((min(cx[0][0], cx[1][0]), min(cx[0][1], cx[1][1]), max(cx[0][0], cx[1][0]), max(cx[0][1], cx[1][1])))
        for vx_, vy_ in ((1.9, YD - 0.45), (2.4, Y_FET - 4.35), (-1.3, YD + 1.35), (-1.9, YD - 0.55), (-1.9, YD + 0.55)):
            cx = rot(xu + vx_, vy_, phi)
            TAP_KEEPOUTS.append((cx[0] - 0.55, cx[1] - 0.55, cx[0] + 0.55, cx[1] + 0.55))
        cx = [rot(x, y, phi) for x, y in ((xu - 2.0, YD - 2.7), (xu + 3.4, Y_FET - 3.65))]
        DRV_KEEPOUTS.append((min(cx[0][0], cx[1][0]), min(cx[0][1], cx[1][1]), max(cx[0][0], cx[1][0]), max(cx[0][1], cx[1][1])))
        # VBAT feed strip over the high-side drain; GND strip over the low-side source row,
        # leaving a channel between them for the low-side gate (pad at xu+0.97) to reach its driver
        ZONES.append(("F_Cu", "/VBAT", box(xu - 3.85, Y_FET - 3.65, xu - 0.15, Y_FET - 1.0, phi), 5))
        ZONES.append(("F_Cu", "/GND", box(xu + 1.35, Y_FET - 3.65, xu + 3.85, Y_FET - 1.15, phi), 5))
        NO_TRACKS.append(("F_Cu", box(xu - 3.85, Y_FET - 3.65, xu - 0.15, Y_FET - 1.0, phi)))
        NO_TRACKS.append(("F_Cu", box(xu + 1.35, Y_FET - 3.65, xu + 3.85, Y_FET - 1.15, phi)))
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
    # MCU on the bottom between the driver row and the battery via arrays, clear of the driver vias
    mx, my = rot(5.2, 8.0, phi)
    FIXED[mcu[0]] = (mx, my, phi, "B")
    # no other parts over this edge's power band (FETs, feed strips, via fields, phase pours)
    def kbox(x0, y0, x1, y1):
        bx = [rot(x, y, phi) for x, y in ((x0, y0), (x1, y1))]
        return (min(bx[0][0], bx[1][0]), min(bx[0][1], bx[1][1]), max(bx[0][0], bx[1][0]), max(bx[0][1], bx[1][1]))
    POWER_BANDS.append(kbox(-12.0, Y_FET - 3.9, 12.0, EDGE))                 # top: FETs + feed strips
    POWER_BANDS_B.append(kbox(-12.0, Y_FET - 3.75, 12.0, Y_FET - 1.95))   # bottom: via fields
    POWER_BANDS_B.append(kbox(-12.0, Y_FET - 1.95, 12.0, EDGE))          # bottom: dividers, phase pours

# ------------------------------------------------------------------ centre: battery pads, FC link
# Battery pads feed the In1 GND / In4 VBAT planes directly through 50-via arrays each.
bat = first("Battery & sense", "TP", "BAT+")[0], first("Battery & sense", "TP", "BAT-")[0]
FIXED[bat[0]] = (-3.2, 3.1, 0, "F")
FIXED[bat[1]] = (3.2, 3.1, 0, "F")
J = first("FC connector", "J")[0]
FIXED[J] = (0.0, -5.64, 0, "F")
for i in range(5):
    for j in range(7):          # 35 vias per pad; rows stop at y=4.3 so the ESC1 MCU fits below
        y = -1.7 + j * 1.0
        VIAS.append(((-4.55 + i * 0.9, y), "/VBAT"))     # 0.9 mm pitch keeps |x| <= 4.85 (MCUs of ESC2/4)
        VIAS.append(((0.95 + i * 0.9, y), "/GND"))

KEEPOUTS = {"F": [(-6.0, -2.3, 6.0, 8.3)] + POWER_BANDS + DRV_KEEPOUTS,
            "B": [(-5.9, -2.2, 5.9, 4.8)] + POWER_BANDS_B + TAP_KEEPOUTS}
SIDE = {}
for p in parts:
    if p.ref not in FIXED:
        SIDE[p.ref] = "B"            # small parts default to the bottom
ORDER = first("Gate drive supply", "U") + [first("ESC%d MCU" % n, "U")[1] for n in range(1, 5)]
ANCHOR_SKIP = ["/GND", "/VBAT", "GND", "VBAT"]
# 6 layers: F power stage | In1 GND plane | In2 signal | In3 signal | In4 VBAT plane | B control.
# Order 2 oz outer copper and at least 1 oz inner copper.
PLANES = [("In1_Cu", "GND"), ("In4_Cu", "VBAT")]
POURS = [("B_Cu", "GND"), ("F_Cu", "GND"), ("In2_Cu", "GND"), ("In3_Cu", "GND")]
SILK += [("4in1 ESC rev B  AM32 JUPITER_80_G071", 0, 0.0, "B", 0.8),
         ("+", -3.2, 8.9, "F", 1.2), ("-", 3.2, 8.9, "F", 1.2)]
# nets pre-routed by finish_route.py before Freerouting: the long MCU -> driver PWM lines and the
# back-EMF lines (regex on net names)
PREROUTE = r"E\d_([HL][ABC]|BEMF_[ABC])$"
