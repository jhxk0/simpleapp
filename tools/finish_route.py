"""finish_route.py <board> <drc.json> [board file] [--near]: route the connections Freerouting left open.

A small grid router (A*, 0.05 mm grid, 8 directions, vias) over F, In2, In3 and B.  It reads the
unconnected pairs from a KiCad DRC report, removes the GND pours and free-standing stitching vias
(route.py finish puts them back), and routes each pair with a 0.15 mm track (0.2 mm for supply
nets) at >= 0.15 mm clearance.  The failing nets' own router copper is ripped up first; with
--near, router copper of other nets within 1.2 mm of their pads is ripped up and re-routed too.  Pure Python, runs in KiCad's bundled interpreter.
"""
import sys, os, json, math, heapq, importlib
from array import array
import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
NEAR_RIP = "--near" in sys.argv
PRE = None
if "--pre" in sys.argv:                  # pre-route mode: --pre <regex of net names>, no DRC report
    import re
    PRE = re.compile(sys.argv[sys.argv.index("--pre") + 1])
    args = [a for a in args if a != sys.argv[sys.argv.index("--pre") + 1]]
    args.insert(1, None)
name, rpt = args[0], args[1]
L = importlib.import_module(name + "_layout")
pcb_path = args[2] if len(args) > 2 else os.path.join(HERE, "..", name, name + ".kicad_pcb")
board = pcbnew.LoadBoard(pcb_path)
MM, TO = pcbnew.FromMM, pcbnew.ToMM

G = 0.05                                  # grid pitch
W2, H2 = L.BOARD_W / 2, L.BOARD_H / 2
NX, NY = int(round(L.BOARD_W / G)) + 1, int(round(L.BOARD_H / G)) + 1
LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.In3_Cu, pcbnew.B_Cu]
LCOST = [2.0, 1.0, 1.0, 2.0] if "--pre" in sys.argv else [1.4, 1.0, 1.0, 1.4]   # prefer inner layers
CLR = 0.15                                # clearance used for everything we add
WMAX = 0.2                                # widest track we draw
RT = CLR + WMAX / 2 + 0.03                # keep track centre this far from other copper (+ grid rounding)
VIA_D, VIA_DRILL = 0.5, 0.3
SUPPLY = {"/" + n for n in L.NETCLASS_NETS.get("Supply", [])}

def ix(x): return int(round((x + W2) / G))
def iy(y): return int(round((y + H2) / G))
def cx(i): return i * G - W2
def cy(j): return j * G - H2

# ------------------------------------------------------------------ clean up before routing
for z in list(board.Zones()):
    if z.GetZoneName() == "pour":
        board.Delete(z)
gnd = board.FindNet("/GND").GetNetCode()
tracks = list(board.GetTracks())
ends = {}
for t in tracks:
    if t.Type() == pcbnew.PCB_TRACE_T:
        for p in (t.GetStart(), t.GetEnd()):
            ends.setdefault((p.x, p.y), []).append(t)
removed = 0
for t in tracks:
    if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == gnd and abs(TO(t.GetWidth(pcbnew.F_Cu)) - 0.5) < 0.01:
        p = t.GetPosition()
        if not ends.get((p.x, p.y)):
            board.Delete(t); removed += 1

def segdist(a, b, c):
    dx, dy = b.x - a.x, b.y - a.y
    ll = dx * dx + dy * dy
    t = 0 if ll == 0 else max(0.0, min(1.0, ((c.x - a.x) * dx + (c.y - a.y) * dy) / ll))
    return math.hypot(a.x + t * dx - c.x, a.y + t * dy - c.y)

# ------------------------------------------------------------------ rip up
# nets with an open connection, plus the nets whose router-made copper crowds their pads
report = json.load(open(rpt)) if rpt else {}
uuid_net = {}
for t in board.GetTracks():
    uuid_net[t.m_Uuid.AsString()] = t.GetNetCode()
for f in board.GetFootprints():
    for p in f.Pads():
        uuid_net[p.m_Uuid.AsString()] = p.GetNetCode()
NOREROUTE = {board.FindNet("/" + n).GetNetCode() for n in L.NETCLASS_NETS.get("Power", []) if board.FindNet("/" + n)}
failing = []
if PRE:
    failing = sorted({n.GetNetCode() for n in board.GetNetsByNetcode().values() if PRE.search(n.GetNetname())})
for v in report.get("unconnected_items", []):
    n = uuid_net.get(v["items"][0]["uuid"])
    if n and n not in NOREROUTE and n not in failing:
        failing.append(n)
pads_of = {}
for f in board.GetFootprints():
    for p in f.Pads():
        pads_of.setdefault(p.GetNetCode(), []).append(p)
RIP_R = MM(1.2)
ripnets = set(failing)
def anchor_pts(n):
    pts = [p.GetPosition() for p in pads_of.get(n, [])]
    for t in board.GetTracks():
        if t.GetNetCode() == n and t.IsLocked():
            pts += [t.GetStart(), t.GetEnd()]
    return pts
for n in (failing if NEAR_RIP else []):
    for c in anchor_pts(n):
        for t in board.GetTracks():
            if t.IsLocked() or t.GetNetCode() in NOREROUTE or t.GetNetCode() == 0:
                continue
            if segdist(t.GetStart(), t.GetEnd(), c) < RIP_R:
                ripnets.add(t.GetNetCode())
ripped = 0
for t in list(board.GetTracks()):
    if not t.IsLocked() and t.GetNetCode() in ripnets:
        board.Delete(t); ripped += 1
order = failing + sorted(ripnets - set(failing))
print("rip-up: %d failing nets, %d nets re-routed, %d items removed" % (len(failing), len(order), ripped))
pcbnew.ZONE_FILLER(board).Fill(board.Zones())

# ------------------------------------------------------------------ obstacle maps
# owner[l][k]: 0 free, >0 the one net whose copper is near, -1 several nets / no-go
owner = [array("i", [0]) * (NX * NY) for _ in LAYERS]

def claim(l, i, j, net):
    k = j * NX + i
    o = owner[l][k]
    if o == 0:
        owner[l][k] = net
    elif o != net:
        owner[l][k] = -1

def mark_seg(l, x1, y1, x2, y2, r, net):
    i0, i1 = max(0, ix(min(x1, x2) - r) - 1), min(NX - 1, ix(max(x1, x2) + r) + 1)
    j0, j1 = max(0, iy(min(y1, y2) - r) - 1), min(NY - 1, iy(max(y1, y2) + r) + 1)
    dx, dy = x2 - x1, y2 - y1
    ll = dx * dx + dy * dy
    r2 = r * r
    for j in range(j0, j1 + 1):
        py = cy(j)
        for i in range(i0, i1 + 1):
            px = cx(i)
            t = 0.0 if ll == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / ll))
            qx, qy = x1 + t * dx - px, y1 + t * dy - py
            if qx * qx + qy * qy <= r2:
                claim(l, i, j, net)

def mark_poly(l, pts, r, net):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    i0, i1 = max(0, ix(min(xs)) - 1), min(NX - 1, ix(max(xs)) + 1)
    j0, j1 = max(0, iy(min(ys)) - 1), min(NY - 1, iy(max(ys)) + 1)
    n = len(pts)
    for j in range(j0, j1 + 1):
        py = cy(j)
        xs_cross = []
        for a in range(n):
            (xa, ya), (xb, yb) = pts[a], pts[(a + 1) % n]
            if (ya > py) != (yb > py):
                xs_cross.append(xa + (py - ya) * (xb - xa) / (yb - ya))
        xs_cross.sort()
        for a in range(0, len(xs_cross) - 1, 2):
            for i in range(max(i0, ix(xs_cross[a])), min(i1, ix(xs_cross[a + 1])) + 1):
                claim(l, i, j, net)
    for a in range(n):
        mark_seg(l, pts[a][0], pts[a][1], pts[(a + 1) % n][0], pts[(a + 1) % n][1], r, net)

def poly_points(sps):
    out = []
    for o in range(sps.OutlineCount()):
        ol = sps.Outline(o)
        out.append([(TO(ol.CPoint(k).x), TO(ol.CPoint(k).y)) for k in range(ol.PointCount())])
    return out

for t in board.GetTracks():
    net = t.GetNetCode() or -1
    if t.Type() == pcbnew.PCB_VIA_T:
        p = t.GetPosition(); rv = TO(t.GetWidth(pcbnew.F_Cu)) / 2
        for l in range(4):
            mark_seg(l, TO(p.x), TO(p.y), TO(p.x), TO(p.y), rv + RT, net)
    else:
        if t.GetLayer() in LAYERS:
            l = LAYERS.index(t.GetLayer())
            mark_seg(l, TO(t.GetStart().x), TO(t.GetStart().y), TO(t.GetEnd().x), TO(t.GetEnd().y),
                     TO(t.GetWidth()) / 2 + RT, net)
for f in board.GetFootprints():
    for p in f.Pads():
        net = p.GetNetCode() or -1
        for l, lay in enumerate(LAYERS):
            if not p.IsOnLayer(lay) and not (p.HasHole() and lay in (pcbnew.In2_Cu, pcbnew.In3_Cu)):
                continue
            sh = p.GetEffectiveShape(lay if p.IsOnLayer(lay) else pcbnew.F_Cu)
            bb = sh.BBox()
            if p.HasHole() and not p.IsOnLayer(lay):          # NPTH / inner layer: keep off the hole
                hr = TO(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2
                c = p.GetPosition()
                mark_seg(l, TO(c.x), TO(c.y), TO(c.x), TO(c.y), hr + 0.25 + WMAX / 2, -1)
                continue
            x0, y0, x1, y1 = TO(bb.GetLeft()), TO(bb.GetTop()), TO(bb.GetRight()), TO(bb.GetBottom())
            mark_poly(l, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], RT, net)
for z in board.Zones():
    if z.GetIsRuleArea():
        if z.GetDoNotAllowTracks():
            for lay in z.GetLayerSet().CuStack():
                if lay in LAYERS:
                    for pts in poly_points(z.Outline()):
                        mark_poly(LAYERS.index(lay), pts, WMAX / 2 + 0.05, -1)
        continue
    for lay in z.GetLayerSet().CuStack():
        if lay in LAYERS and z.IsFilled():
            for pts in poly_points(z.GetFilledPolysList(lay)):
                mark_poly(LAYERS.index(lay), pts, RT, z.GetNetCode() or -1)
# board edge (rounded corners) and mounting holes
cr = getattr(L, "CORNER_R", 0)
edge = 0.3 + WMAX / 2
for l in range(4):
    for j in range(NY):
        for i in range(NX):
            x, y = abs(cx(i)), abs(cy(j))
            bad = x > W2 - edge or y > H2 - edge
            if not bad and cr and x > W2 - cr and y > H2 - cr:
                bad = math.hypot(x - (W2 - cr), y - (H2 - cr)) > cr - edge
            if bad:
                owner[l][j * NX + i] = -1
holes = [(TO(p.GetPosition().x), TO(p.GetPosition().y), TO(p.GetDrillSize().x) / 2)
         for f in board.GetFootprints() for p in f.Pads() if p.HasHole()] + \
        [(TO(t.GetPosition().x), TO(t.GetPosition().y), TO(t.GetDrillValue()) / 2)
         for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
print("obstacle maps built")

def free(l, i, j, net):
    o = owner[l][j * NX + i]
    return o == 0 or o == net

VR = int(math.ceil((VIA_D / 2 - WMAX / 2) / G))          # extra radius a via needs beyond a track
VDISK = [(a, b) for a in range(-VR, VR + 1) for b in range(-VR, VR + 1) if a * a + b * b <= VR * VR]
def via_ok(i, j, net):
    for l in range(4):
        for a, b in VDISK:
            if not (0 <= i + a < NX and 0 <= j + b < NY) or not free(l, i + a, j + b, net):
                return False
    x, y = cx(i), cy(j)
    return all(math.hypot(x - hx, y - hy) > hr + VIA_DRILL / 2 + 0.3 for hx, hy, hr in holes)

DIRS = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
        (1, 1, 1.4142), (1, -1, 1.4142), (-1, 1, 1.4142), (-1, -1, 1.4142)]
VIA_COST = 30.0

def route(net, srcs, dsts, margin=8.0):
    xs = [s[0] for s in srcs + dsts]; ys = [s[1] for s in srcs + dsts]
    bi0, bi1 = max(0, ix(min(xs) - margin)), min(NX - 1, ix(max(xs) + margin))
    bj0, bj1 = max(0, iy(min(ys) - margin)), min(NY - 1, iy(max(ys) + margin))
    goal = {}
    for x, y, ls in dsts:
        for l in ls:
            goal[(l, ix(x), iy(y))] = (x, y)
    gx = sum(d[0] for d in dsts) / len(dsts); gy = sum(d[1] for d in dsts) / len(dsts)
    def h(i, j):
        return min(math.hypot(i - ix(x), j - iy(y)) for x, y, _ in dsts)
    openq, best, prev = [], {}, {}
    for x, y, ls in srcs:
        for l in ls:
            s = (l, ix(x), iy(y))
            best[s] = 0.0; prev[s] = None
            heapq.heappush(openq, (h(s[1], s[2]), 0.0, s))
    n = 0
    while openq:
        f, g, s = heapq.heappop(openq)
        if g > best.get(s, 1e18):
            continue
        if s in goal:
            out = []
            while s is not None:
                out.append(s); s = prev[s]
            return out[::-1]
        n += 1
        if n > 4000000:
            print("    search limit", n); return None
        l, i, j = s
        for di, dj, c in DIRS:
            a, b = i + di, j + dj
            if not (bi0 <= a <= bi1 and bj0 <= b <= bj1):
                continue
            t = (l, a, b)
            if t not in goal and not free(l, a, b, net):
                continue
            if di and dj and not (free(l, a, j, net) and free(l, i, b, net)):
                continue
            ng = g + c * LCOST[l]
            if ng < best.get(t, 1e18):
                best[t] = ng; prev[t] = s
                heapq.heappush(openq, (ng + h(a, b), ng, t))
        if via_ok(i, j, net):
            for l2 in range(4):
                if l2 != l:
                    t = (l2, i, j)
                    ng = g + VIA_COST
                    if ng < best.get(t, 1e18):
                        best[t] = ng; prev[t] = s
                        heapq.heappush(openq, (ng + h(i, j), ng, t))
    print("    exhausted after", n, "expansions; sources free:",
          [free(l, ix(x), iy(y), net) for x, y, ls in srcs for l in ls],
          "neighbours free:", [sum(free(l, ix(x) + di, iy(y) + dj, net) for di, dj, _ in DIRS) for x, y, ls in srcs for l in ls],
          "goal neighbours free:", [sum(free(l, ix(x) + di, iy(y) + dj, net) for di, dj, _ in DIRS) for x, y, ls in dsts for l in ls])
    return None

def commit(netobj, path, sx, sy, ex, ey, w, lock=False):
    net = netobj.GetNetCode()
    pts = [(l, cx(i), cy(j)) for l, i, j in path]
    pts[0] = (pts[0][0], sx, sy); pts[-1] = (pts[-1][0], ex, ey)
    # split into same-layer runs, merge collinear steps
    runs, cur = [], [pts[0]]
    for p in pts[1:]:
        if p[0] != cur[-1][0]:
            runs.append(cur); cur = [(p[0], cur[-1][1], cur[-1][2])]
            v = pcbnew.PCB_VIA(board); v.SetPosition(pcbnew.VECTOR2I(MM(p[1]), MM(p[2])))
            v.SetDrill(MM(VIA_DRILL))
            for lay in [pcbnew.F_Cu, pcbnew.B_Cu] + [getattr(pcbnew, "In%d_Cu" % k) for k in range(1, board.GetCopperLayerCount() - 1)]:
                v.SetWidth(lay, MM(VIA_D))
            v.SetNet(netobj); v.SetLocked(lock); board.Add(v)
            for l in range(4):
                mark_seg(l, p[1], p[2], p[1], p[2], VIA_D / 2 + RT, net)
            holes.append((p[1], p[2], VIA_DRILL / 2))
            if p[1:] == cur[-1][1:]:
                continue
        cur.append(p)
    runs.append(cur)
    nseg = 0
    for run in runs:
        l = run[0][0]
        simp = [run[0]]
        for k in range(1, len(run) - 1):
            a, b, c = simp[-1], run[k], run[k + 1]
            if abs((b[1] - a[1]) * (c[2] - b[2]) - (b[2] - a[2]) * (c[1] - b[1])) > 1e-9:
                simp.append(b)
        simp.append(run[-1])
        for a, b in zip(simp, simp[1:]):
            if (a[1], a[2]) == (b[1], b[2]):
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(MM(a[1]), MM(a[2]))); t.SetEnd(pcbnew.VECTOR2I(MM(b[1]), MM(b[2])))
            t.SetWidth(MM(w)); t.SetLayer(LAYERS[l]); t.SetNet(netobj); t.SetLocked(lock); board.Add(t)
            mark_seg(l, a[1], a[2], b[1], b[2], w / 2 + RT, net)
            nseg += 1
    return nseg

# ------------------------------------------------------------------ connect every net in the rip-up set
def components(net):
    """groups of anchors [(x, y, [layers])] that are already connected copper"""
    nodes = []                                      # (anchors, test-points)
    for p in pads_of.get(net, []):
        c = p.GetPosition()
        nodes.append(("pad", p, [(TO(c.x), TO(c.y), [l for l, lay in enumerate(LAYERS) if p.IsOnLayer(lay)])]))
    for t in board.GetTracks():
        if t.GetNetCode() != net:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            c = t.GetPosition(); nodes.append(("via", t, [(TO(c.x), TO(c.y), [0, 1, 2, 3])]))
        elif t.GetLayer() in LAYERS:
            l = LAYERS.index(t.GetLayer())
            nodes.append(("trk", t, [(TO(q.x), TO(q.y), [l]) for q in (t.GetStart(), t.GetEnd())]))
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetCode() == net:
            nodes.append(("zone", z, []))
    par = list(range(len(nodes)))
    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]; a = par[a]
        return a
    def touch(a, b):
        ka, ia, pa = nodes[a]; kb, ib, pb = nodes[b]
        if ka == "zone" or kb == "zone":
            z, o = (ia, nodes[b]) if ka == "zone" else (ib, nodes[a])
            return any(z.Outline().Contains(pcbnew.VECTOR2I(MM(x), MM(y))) and
                       any(z.IsOnLayer(LAYERS[l]) for l in ls) for x, y, ls in o[2])
        if ka == "pad" or kb == "pad":
            p, o = (ia, nodes[b]) if ka == "pad" else (ib, nodes[a])
            if o[0] == "pad":
                return False
            return any(p.HitTest(pcbnew.VECTOR2I(MM(x), MM(y))) and
                       any(p.IsOnLayer(LAYERS[l]) for l in ls) for x, y, ls in o[2])
        return any(abs(x1 - x2) < 1e-3 and abs(y1 - y2) < 1e-3 and set(l1) & set(l2)
                   for x1, y1, l1 in pa for x2, y2, l2 in pb)
    for a in range(len(nodes)):
        for b in range(a + 1, len(nodes)):
            if find(a) != find(b) and touch(a, b):
                par[find(a)] = find(b)
    groups = {}
    for a in range(len(nodes)):
        groups.setdefault(find(a), []).extend(nodes[a][2])
    return [g for g in groups.values() if g]

def fanout_qfn():
    """staggered escape stub + via for every QFN pin on a pre-routed net, straight out from the package"""
    made = 0
    targets = set(order)
    for f in board.GetFootprints():
        pads = list(f.Pads())
        if len(pads) < 20:
            continue
        fc = f.GetPosition()
        for p in pads:
            if p.GetNetCode() not in targets or p.GetNumber() in ("33", "EP", ""):
                continue
            lay = pcbnew.B_Cu if p.IsOnLayer(pcbnew.B_Cu) else pcbnew.F_Cu
            l = LAYERS.index(lay)
            c = p.GetPosition(); dx, dy = TO(c.x - fc.x), TO(c.y - fc.y)
            if abs(dx) < 1.0 and abs(dy) < 1.0:
                continue                                   # exposed pad
            ux, uy = (math.copysign(1, dx), 0) if abs(dx) > abs(dy) else (0, math.copysign(1, dy))
            x0, y0 = TO(c.x), TO(c.y)
            stag = [0.75, 1.45] if int(p.GetNumber()) % 2 else [1.45, 0.75]
            for dist in stag:
                vx, vy = x0 + ux * dist, y0 + uy * dist
                i, j = ix(vx), iy(vy)
                if not via_ok(i, j, p.GetNetCode()):
                    continue
                steps = int(round(dist / G))
                if not all(free(l, ix(x0 + ux * k * G), iy(y0 + uy * k * G), p.GetNetCode()) for k in range(steps + 1)):
                    continue
                path = [(l, ix(x0 + ux * k * G), iy(y0 + uy * k * G)) for k in range(steps + 1)] + [(1, i, j)]
                commit(p.GetNet(), path, x0, y0, cx(i), cy(j), 0.15, lock=True)
                made += 1
                break
    print("QFN fanout vias", made)

if PRE:
    fanout_qfn()

ok = fail = 0
for net in order:
    netobj = pads_of[net][0].GetNet()
    comps = components(net)
    w = 0.2 if netobj.GetNetname() in SUPPLY else 0.15
    tree, rest = comps[0], comps[1:]
    while rest:
        rest.sort(key=lambda g: min(math.hypot(a[0] - b[0], a[1] - b[1]) for a in tree for b in g))
        tgt = rest[0]
        pth = route(net, tree, tgt) or route(net, tree, tgt, margin=30.0)
        if not pth:
            print("  FAILED", netobj.GetNetname()); fail += 1
            tree = tree + tgt; rest = rest[1:]          # keep going with the other pieces
            continue
        st = [s_ for s_ in tree if (ix(s_[0]), iy(s_[1])) == (pth[0][1], pth[0][2])][0]
        en = [d for d in tgt if (ix(d[0]), iy(d[1])) == (pth[-1][1], pth[-1][2])][0]
        commit(netobj, pth, st[0], st[1], en[0], en[1], w, lock=bool(PRE))
        tree = tree + tgt + [(cx(i), cy(j), [l]) for l, i, j in pth]
        rest = rest[1:]
        ok += 1
pcbnew.SaveBoard(pcb_path, board)
print("finish_route: %d connections made, %d failed (removed %d stitching vias; run route.py finish next)" % (ok, fail, removed))
