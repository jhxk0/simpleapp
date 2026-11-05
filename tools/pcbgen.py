"""Build a KiCad 9 board from the schematic netlist + a placement table.  Needs KiCad's pcbnew module.

Usage: <kicad python> pcbgen.py <board>     (expects ../<board>/<board>.net.xml and <board>_layout.py)
"""
import sys, os, math, importlib, json
import xml.etree.ElementTree as ET
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kienv
FPDIR = kienv.footprint_dir()
MM = pcbnew.FromMM
def P(x, y): return pcbnew.VECTOR2I(MM(x), MM(y))

board_name = sys.argv[1]
L = importlib.import_module(board_name + "_layout")
out = os.path.join(HERE, "..", board_name)
pcb_path = os.path.join(out, board_name + ".kicad_pcb")

# ------------------------------------------------------------------ netlist
tree = ET.parse(os.path.join(out, board_name + ".net.xml"))
comps = {}
for c in tree.iter("comp"):
    comps[c.get("ref")] = dict(value=c.findtext("value"), fp=c.findtext("footprint"),
                               fields={f.get("name"): f.text for f in c.iter("field")})
pinnet = {}
for n in tree.iter("net"):
    for nd in n.iter("node"):
        pinnet[(nd.get("ref"), nd.get("pin"))] = n.get("name")

if os.path.exists(pcb_path):
    os.remove(pcb_path)
board = pcbnew.NewBoard(pcb_path)
board.SetCopperLayerCount(L.LAYERS)
CU_LAYERS = [pcbnew.F_Cu, pcbnew.B_Cu] + [getattr(pcbnew, 'In%d_Cu' % i) for i in range(1, L.LAYERS - 1)]
ds = board.GetDesignSettings()
for k, v in L.RULES.items():
    setattr(ds, k, MM(v))

nets = {}
def net(name):
    if name not in nets:
        ni = pcbnew.NETINFO_ITEM(board, name)
        board.Add(ni)
        nets[name] = ni
    return nets[name]

# ------------------------------------------------------------------ outline
W, H, R = L.BOARD_W, L.BOARD_H, L.CORNER_R
def seg(a, b, layer=pcbnew.Edge_Cuts, w=0.1):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(P(*a)); s.SetEnd(P(*b)); s.SetLayer(layer); s.SetWidth(MM(w)); board.Add(s)
def arc(c, start, ang):
    s = pcbnew.PCB_SHAPE(board); s.SetShape(pcbnew.SHAPE_T_ARC)
    s.SetCenter(P(*c)); s.SetStart(P(*start)); s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T))
    s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); board.Add(s)
w2, h2 = W / 2, H / 2
seg((-w2 + R, -h2), (w2 - R, -h2)); seg((w2, -h2 + R), (w2, h2 - R))
seg((w2 - R, h2), (-w2 + R, h2)); seg((-w2, h2 - R), (-w2, -h2 + R))
arc((w2 - R, -h2 + R), (w2 - R, -h2), 90); arc((w2 - R, h2 - R), (w2, h2 - R), 90)
arc((-w2 + R, h2 - R), (-w2 + R, h2), 90); arc((-w2 + R, -h2 + R), (-w2, -h2 + R), 90)

# ------------------------------------------------------------------ footprints
fps = {}
for ref, c in comps.items():
    lib, name = c["fp"].split(":")
    fp = pcbnew.FootprintLoad(os.path.join(FPDIR, lib + ".pretty"), name)
    fp.SetReference(ref); fp.SetValue(c["value"])
    fp.SetFPIDAsString(c["fp"])
    for k in ("MPN", "LCSC"):
        if c["fields"].get(k):
            fp.SetField(k, c["fields"][k])
            f = fp.GetFieldByName(k)
            if f: f.SetVisible(False)
    board.Add(fp)
    for pad in fp.Pads():
        n = pinnet.get((ref, pad.GetNumber()))
        if n:
            pad.SetNet(net(n))
    fps[ref] = fp
    # small, readable silkscreen refs
    t = fp.Reference(); t.SetTextSize(P(0.8, 0.8)); t.SetTextThickness(MM(0.15))
    if len(fp.Pads()) <= 3 and not ref.startswith(("TP", "J", "SW")):
        t.SetVisible(False)   # dense board: passive refs live on the fab/assembly drawing
    fp.Value().SetVisible(False)

def courtyard(fp):
    side = pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd
    fp.BuildCourtyardCaches()
    poly = fp.GetCourtyard(side)
    if poly.OutlineCount():
        bb = poly.BBox()
        return (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()), pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    # no courtyard in the library footprint: pad extents + 0.25 mm
    xs, ys = [], []
    for p in fp.Pads():
        b = p.GetBoundingBox()
        xs += [b.GetLeft(), b.GetRight()]; ys += [b.GetTop(), b.GetBottom()]
    m = 0.25
    return (pcbnew.ToMM(min(xs)) - m, pcbnew.ToMM(min(ys)) - m, pcbnew.ToMM(max(xs)) + m, pcbnew.ToMM(max(ys)) + m)

def place(fp, x, y, rot, side):
    if (side == "B") != fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(P(x, y))

occupied = {"F": [], "B": []}
def fits(bb, side, margin=0.05, edge=0.25):
    x0, y0, x1, y1 = bb
    if x0 < -w2 + edge or x1 > w2 - edge or y0 < -h2 + edge or y1 > h2 - edge:
        return False
    for hx, hy in L.HOLES:
        cx, cy = min(max(hx, x0), x1), min(max(hy, y0), y1)
        if math.hypot(cx - hx, cy - hy) < L.HOLE_KEEPOUT:
            return False
    for k in L.KEEPOUTS.get(side, []):
        if not (x1 <= k[0] or x0 >= k[2] or y1 <= k[1] or y0 >= k[3]):
            return False
    for o in occupied[side]:
        if not (x1 + margin <= o[0] or x0 - margin >= o[2] or y1 + margin <= o[1] or y0 - margin >= o[3]):
            return False
    return True

# fixed placements
for ref, (x, y, rot, side) in L.FIXED.items():
    place(fps[ref], x, y, rot, side)
    occupied[side].append(courtyard(fps[ref]))
for hx, hy in L.HOLES:
    pass

# auto-placement of the rest, near the pad they serve
design = importlib.import_module(board_name + "_design").DESIGN
group_of = {p.ref: p.group for p in design.parts}
placed = set(L.FIXED)
load = {}
SKIPNETS = set(L.ANCHOR_SKIP)

def anchor_for(ref):
    fp = fps[ref]
    if ref in L.NEAR:
        a = L.NEAR[ref]
        r2, pn = a.split(".")
        pad = [p for p in fps[r2].Pads() if p.GetNumber() == pn][0]
        return fps[r2], pad
    cands = []
    for pad in fp.Pads():
        n = pad.GetNetname()
        if not n or n in SKIPNETS:
            continue
        for r2 in placed:
            if r2 == ref:
                continue
            f2 = fps[r2]
            for p2 in f2.Pads():
                if p2.GetNetname() == n:
                    same = group_of.get(r2) == group_of.get(ref)
                    big = len(f2.Pads()) > 3
                    cands.append((not same, not big, load.get((r2, p2.GetNumber()), 0), r2, p2))
    if not cands:
        return None, None
    cands.sort(key=lambda c: c[:3])
    best = cands[0]
    load[(best[3], best[4].GetNumber())] = best[2] + 1
    return fps[best[3]], best[4]

def autoplace(ref):
    fp = fps[ref]
    f2, pad = anchor_for(ref)
    if pad is None:
        tx, ty, side0 = 0.0, 0.0, "F"
    else:
        px, py = pcbnew.ToMM(pad.GetPosition().x), pcbnew.ToMM(pad.GetPosition().y)
        cx, cy = pcbnew.ToMM(f2.GetPosition().x), pcbnew.ToMM(f2.GetPosition().y)
        d = math.hypot(px - cx, py - cy) or 1
        tx, ty = px + (px - cx) / d * 1.2, py + (py - cy) / d * 1.2
        side0 = "B" if f2.IsFlipped() else "F"
    side_pref = L.SIDE.get(ref, side0)
    sides = [side_pref] + [s for s in "FB" if s != side_pref]
    for rmax in (4.0, 8.0, 40.0):
        for side in sides:
            best = None
            r = 0.0
            while r <= rmax and best is None:
                n = max(1, int(2 * math.pi * r / 0.3))
                for i in range(n):
                    a = 2 * math.pi * i / n
                    x, y = round(tx + r * math.cos(a), 2), round(ty + r * math.sin(a), 2)
                    for rot in (0, 90):
                        place(fp, x, y, rot, side)
                        bb = courtyard(fp)
                        if fits(bb, side):
                            best = (x, y, rot, side, bb); break
                    if best: break
                r += 0.25
            if best:
                place(fp, *best[:4])
                occupied[best[3]].append(best[4])
                placed.add(ref)
                return best
    raise RuntimeError("could not place " + ref)

order = [r for r in L.ORDER if r in fps and r not in placed] + \
        sorted([r for r in fps if r not in placed and r not in L.ORDER],
               key=lambda r: (design.groups.index(group_of[r]) if r in group_of else 99, r))
unplaced = []
for ref in order:
    try:
        autoplace(ref)
    except RuntimeError:
        unplaced.append(ref)
        place(fps[ref], L.BOARD_W / 2 + 5 + 3 * (len(unplaced) % 6), -L.BOARD_H / 2 + 4 * (len(unplaced) // 6), 0, "F")
if unplaced:
    print("UNPLACED:", " ".join(unplaced))

# silkscreen labels
for (txt, x, y, side, size) in L.SILK:
    size = max(size, 0.8)
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt); t.SetPosition(P(x, y)); t.SetTextSize(P(size, size)); t.SetTextThickness(MM(size * 0.15))
    t.SetLayer(pcbnew.F_SilkS if side == "F" else pcbnew.B_SilkS)
    if side == "B":
        t.SetMirrored(True)
    board.Add(t)

# hand-defined copper: power pours and via fields (kept by route.py, named "fixed")
for layer, netname, pts, prio in getattr(L, "ZONES", []):
    z = pcbnew.ZONE(board)
    z.SetLayer(getattr(pcbnew, layer))
    z.SetNet(nets[netname])
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(MM(x), MM(y))
    z.SetAssignedPriority(prio)
    z.SetZoneName("fixed")
    z.SetLocalClearance(MM(0.2)); z.SetMinThickness(MM(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)   # drop slivers cut off by routing
    board.Add(z)
for layer, pts in getattr(L, "NO_TRACKS", []):   # rule areas: no tracks (vias, pads, pours allowed)
    z = pcbnew.ZONE(board)
    z.SetLayer(getattr(pcbnew, layer))
    o = z.Outline(); o.NewOutline()
    for x, y in pts:
        o.Append(MM(x), MM(y))
    z.SetIsRuleArea(True); z.SetDoNotAllowTracks(True); z.SetDoNotAllowVias(False)
    z.SetDoNotAllowPads(False); z.SetDoNotAllowFootprints(False); z.SetDoNotAllowCopperPour(False)
    z.SetZoneName("fixed")
    board.Add(z)
for via in getattr(L, "VIAS", []):           # ((x, y), net) or ((x, y), net, diameter)
    (x, y), netname = via[:2]
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(P(x, y)); v.SetDrill(MM(0.3))
    for L_ in CU_LAYERS:
        v.SetWidth(L_, MM(via[2] if len(via) > 2 else 0.6))
    v.SetNet(nets[netname]); v.SetLocked(True)
    board.Add(v)
for layer, netname, a, b, w in getattr(L, "TRACKS", []):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a)); t.SetEnd(P(*b)); t.SetWidth(MM(w)); t.SetLayer(getattr(pcbnew, layer))
    t.SetNet(nets[netname]); t.SetLocked(True)
    board.Add(t)

pcbnew.SaveBoard(pcb_path, board)

# net classes -> project file
pro = os.path.join(out, board_name + ".kicad_pro")
pj = json.load(open(pro))
ns = pj.setdefault("net_settings", {})
TEMPLATE = {"bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
            "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "track_width": 0.2, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6}
ns["classes"] = []
for i, (n, v) in enumerate(L.NETCLASSES.items()):
    c = dict(TEMPLATE, name=n, priority=2147483647 if n == "Default" else i)
    c.update(v)
    ns["classes"].append(c)
ns["netclass_patterns"] = [{"netclass": c, "pattern": "/" + p} for c, pats in L.NETCLASS_NETS.items() for p in pats]
ns.setdefault("meta", {"version": 4})
json.dump(pj, open(pro, "w"), indent=2)
print("placed", len(fps), "footprints;", "nets", len(nets))
