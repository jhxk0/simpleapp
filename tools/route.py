"""Route a placed board with Freerouting.  Run inside k9.  Usage: route.py <board> <stage>
stage 'dsn': add GND plane zone(s), export DSN.   stage 'ses': import SES, pour GND, fill, save."""
import sys, os, importlib, pcbnew
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
name, stage = sys.argv[1], sys.argv[2]
L = importlib.import_module(name + "_layout")
d = os.path.join(HERE, "..", name); path = os.path.join(d, name + ".kicad_pcb")
board = pcbnew.LoadBoard(path)
MM = pcbnew.FromMM

# PLANES entries: (layer, net) for a full plane, or (layer, net, hole_pts) for a plane with a routable hole
PLANES = [tuple(p) + (None,) * (3 - len(p)) for p in L.PLANES]
FULL_PLANES = [p for p in PLANES if p[2] is None]

def zone(layer, netname, prio=0, clearance=0.2, minw=0.2, thermal=True, name="pour", hole=None):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet("/" + netname) or board.FindNet(netname))
    z.SetZoneName(name)
    w2, h2 = MM(L.BOARD_W / 2 + 0.05), MM(L.BOARD_H / 2 + 0.05)
    o = pcbnew.SHAPE_POLY_SET(); o.NewOutline()
    for x, y in ((-w2, -h2), (w2, -h2), (w2, h2), (-w2, h2)):
        o.Append(int(x), int(y))
    if hole:
        o.NewHole()
        for x, y in hole:
            o.Append(int(MM(x)), int(MM(y)))
    o.thisown = False          # ZONE takes ownership of the outline
    z.SetOutline(o)
    z.SetAssignedPriority(prio)
    z.SetLocalClearance(MM(clearance)); z.SetMinThickness(MM(minw))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
    z.SetThermalReliefGap(MM(0.2)); z.SetThermalReliefSpokeWidth(MM(0.3))
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    board.Add(z)
    return z

if stage == "fanout":
    # short locked stub + via from every SMD pad on a plane net, before autorouting
    import math
    pnets = {(board.FindNet("/" + n) or board.FindNet(n)).GetNetCode() for _, n, _h in FULL_PLANES}
    pads = [p for f in board.GetFootprints() for p in f.Pads()
            if p.GetNetCode() in pnets and not p.HasHole() and max(p.GetSize(pcbnew.F_Cu).x, p.GetSize(pcbnew.F_Cu).y) < MM(2.6)]
    obst = [p for f in board.GetFootprints() for p in f.Pads()] + list(board.GetTracks())
    holes = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole()] + \
            [t.GetPosition() for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    mh = [f.GetPosition() for f in board.GetFootprints() if f.GetReference().startswith("H")]
    w2, h2 = MM(L.BOARD_W / 2 - 0.6), MM(L.BOARD_H / 2 - 0.6)
    VR = MM(0.25)
    done = fail = 0
    for pad in pads:
        lay = pcbnew.B_Cu if pad.IsOnLayer(pcbnew.B_Cu) and not pad.IsOnLayer(pcbnew.F_Cu) else pcbnew.F_Cu
        nc = pad.GetNetCode(); c = pad.GetPosition()
        # already has a via of its net on/next to it (e.g. thermal pads, pre-placed fields)?
        if any((h - c).EuclideanNorm() < MM(1.0) for h in holes if True) and \
           any(t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == nc and (t.GetPosition() - c).EuclideanNorm() < MM(1.2)
               for t in board.GetTracks()):
            continue
        best = None
        for rr in [MM(0.75 + 0.15 * k) for k in range(10)]:
            for a in range(0, 360, 15):
                pt = pcbnew.VECTOR2I(int(c.x + rr * math.cos(math.radians(a))), int(c.y + rr * math.sin(math.radians(a))))
                if abs(pt.x) > w2 or abs(pt.y) > h2 or any((pt - m).EuclideanNorm() < MM(3.4) for m in mh):
                    continue
                if any((pt - h).EuclideanNorm() < MM(0.75) for h in holes):
                    continue
                circ = pcbnew.SHAPE_CIRCLE(pt, VR); seg = pcbnew.SHAPE_SEGMENT(c, pt, MM(0.25))
                ok = True
                for o in obst:
                    same = o.GetNetCode() == nc
                    for L_ in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if not o.IsOnLayer(L_):
                            continue
                        sh = o.GetEffectiveShape(L_)
                        if (not same and sh.Collide(circ, MM(0.15))) or \
                           (L_ == lay and not same and sh.Collide(seg, MM(0.15))):
                            ok = False; break
                    if not ok: break
                if ok:
                    best = pt; break
            if best: break
        if not best:
            fail += 1; continue
        t = pcbnew.PCB_TRACK(board); t.SetStart(c); t.SetEnd(best); t.SetWidth(MM(0.25)); t.SetLayer(lay)
        t.SetNet(pad.GetNet()); t.SetLocked(True); board.Add(t)
        v = pcbnew.PCB_VIA(board); v.SetPosition(best); v.SetDrill(MM(0.3))
        for L_ in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
            v.SetWidth(L_, MM(0.5))
        v.SetNet(pad.GetNet()); v.SetLocked(True); board.Add(v)
        obst += [t, v]; holes.append(best); done += 1
    pcbnew.SaveBoard(path, board)
    print("fanout vias", done, "failed", fail)
if stage == "dsn":
    for z in list(board.Zones()):
        if z.GetZoneName() != "fixed":
            board.Remove(z)
    for layer, net, hole in PLANES:
        zone(getattr(pcbnew, layer), net, thermal=False, name="plane", hole=hole, prio=1 if hole else 0)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    dsn = os.path.join(d, name + ".dsn")
    ok = pcbnew.ExportSpecctraDSN(board, dsn)
    s = open(dsn).read()
    for layer, _, _h in FULL_PLANES:     # full plane layers are not available to the router
        ln = layer.replace("_", ".")
        s = s.replace("(layer %s\n      (type signal)" % ln, "(layer %s\n      (type power)" % ln)
    open(dsn, "w").write(s)
    print("dsn exported", ok)
if stage == "ses":
    ok = pcbnew.ImportSpecctraSES(board, os.path.join(d, name + ".ses"))
    pcbnew.SaveBoard(path, board)
    print("ses imported", ok, "tracks", len(board.GetTracks()))
if stage == "finish":
    for z in list(board.Zones()):               # idempotent: drop earlier pours
        if z.GetZoneName() == "pour":
            board.Remove(z)
    # drop vias that connect nothing on one of their sides (router leftovers)
    conn = board.GetConnectivity()
    removed = 0
    plane_nets = {"/" + n for _, n, _h in PLANES}
    for t in list(board.GetTracks()):
        if t.Type() != pcbnew.PCB_VIA_T or t.GetNetname() in plane_nets:
            continue
        pos, nc, layers = t.GetPosition(), t.GetNetCode(), set()
        for o in board.GetTracks():
            if o.Type() != pcbnew.PCB_VIA_T and o.GetNetCode() == nc and pos in (o.GetStart(), o.GetEnd()):
                layers.add(o.GetLayer())
        for f in board.GetFootprints():
            for p in f.Pads():
                if p.GetNetCode() == nc:
                    for L_ in (pcbnew.F_Cu, pcbnew.B_Cu):
                        if p.IsOnLayer(L_) and p.HitTest(pos):
                            layers.add(L_)
        for z in board.Zones():
            if z.GetNetCode() == nc:
                for L_ in z.GetLayerSet().CuStack():
                    if z.Outline().Contains(pos):
                        layers.add(L_)
        if len(layers) <= 1:                 # reaches copper on at most one layer: goes nowhere
            board.Remove(t); removed += 1
    print("removed dangling vias", removed)
    widened = 0                      # router neck-downs below the fab minimum
    for t in board.GetTracks():
        if t.Type() == pcbnew.PCB_TRACE_T and t.GetWidth() < MM(0.1):
            t.SetWidth(MM(0.1)); widened += 1
    print("widened neck-downs", widened)
    for layer, net in L.POURS:
        zone(getattr(pcbnew, layer), net, prio=0, thermal=False)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    # GND stitching: a via wherever one fits on a 1.5 mm grid and lands in GND copper on F and B
    gnd = board.FindNet("/GND")
    VR, CL = MM(0.25), MM(0.25)            # via radius (0.5 dia), clearance to other nets
    items = [t for t in board.GetTracks()] + [p for f in board.GetFootprints() for p in f.Pads()]
    others = [(it, it.GetNetCode()) for it in items]
    bb = board.GetBoardEdgesBoundingBox()
    edge = board.GetBoardEdgesBoundingBox()
    added = 0
    step = MM(1.5)
    def filled(layer, pt):
        for z in board.Zones():
            if z.GetNetCode() == gnd.GetNetCode() and z.IsOnLayer(layer) and z.GetFilledPolysList(layer).Contains(pt):
                return True
        return False
    holes = [f.GetPosition() for f in board.GetFootprints() if f.GetReference().startswith("H")]
    drills = [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole()] + \
             [t.GetPosition() for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
    y = bb.GetTop() + MM(1.0)
    while y < bb.GetBottom() - MM(1.0):
        x = bb.GetLeft() + MM(1.0)
        while x < bb.GetRight() - MM(1.0):
            pt = pcbnew.VECTOR2I(int(x), int(y))
            ok = all(filled(L_, pt) for L_ in (pcbnew.F_Cu, pcbnew.B_Cu))
            if ok and any((pt - h).EuclideanNorm() < MM(3.4) for h in holes):
                ok = False
            if ok and any((pt - h).EuclideanNorm() < MM(0.85) for h in drills):
                ok = False
            if ok:
                circ = pcbnew.SHAPE_CIRCLE(pt, VR)
                for it, nc in others:
                    if nc == gnd.GetNetCode() and it.Type() != pcbnew.PCB_VIA_T:
                        continue
                    for L_ in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu):
                        if it.IsOnLayer(L_) and it.GetEffectiveShape(L_).Collide(circ, CL if nc != gnd.GetNetCode() else MM(0.3)):
                            ok = False; break
                    if not ok: break
            if ok:
                v = pcbnew.PCB_VIA(board); v.SetPosition(pt); v.SetDrill(MM(0.3))
                for L_ in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                    v.SetWidth(L_, MM(0.5))
                v.SetNet(gnd); board.Add(v); others.append((v, gnd.GetNetCode())); drills.append(pt); added += 1
            x += step
        y += step
    print("stitching vias", added)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())

    # GND islands on the outer layers with no via: drop one inside, where it fits
    def fits_via(pt, r):
        circ = pcbnew.SHAPE_CIRCLE(pt, r)
        if any((pt - h).EuclideanNorm() < MM(0.8) for h in drills):
            return False
        for it, nc in others:
            if nc == gnd.GetNetCode() and it.Type() != pcbnew.PCB_VIA_T:
                continue
            for L_ in (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu):
                if it.IsOnLayer(L_) and it.GetEffectiveShape(L_).Collide(circ, CL if nc != gnd.GetNetCode() else MM(0.25)):
                    return False
        return True
    gvias = lambda: [t.GetPosition() for t in board.GetTracks() if t.Type() == pcbnew.PCB_VIA_T and t.GetNetCode() == gnd.GetNetCode()] + \
                    [p.GetPosition() for f in board.GetFootprints() for p in f.Pads() if p.HasHole() and p.GetNetCode() == gnd.GetNetCode()]
    fixed_islands = 0
    for z in list(board.Zones()):
        if z.GetNetCode() != gnd.GetNetCode() or z.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
            continue
        ps = z.GetFilledPolysList(z.GetLayer())
        vs = gvias()
        for i in range(ps.OutlineCount()):
            o = ps.Outline(i)
            if any(o.PointInside(v) for v in vs):
                continue
            bb = o.BBox(); r = MM(0.225); done = False
            y = bb.GetTop()
            while y <= bb.GetBottom() and not done:
                x = bb.GetLeft()
                while x <= bb.GetRight() and not done:
                    pt = pcbnew.VECTOR2I(int(x), int(y))
                    if o.PointInside(pt) and o.SquaredDistance(pt) >= r * r and fits_via(pt, r):
                        v = pcbnew.PCB_VIA(board); v.SetPosition(pt); v.SetDrill(MM(0.25))
                        for L_ in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                            v.SetWidth(L_, MM(0.45))
                        v.SetNet(gnd); board.Add(v); others.append((v, gnd.GetNetCode())); drills.append(pt)
                        fixed_islands += 1; done = True
                    x += MM(0.05)
                y += MM(0.05)
            if not done:      # enclosed pad: short trace from the pad out to the nearest spot a via fits
                lay = z.GetLayer()
                pads = [p for f in board.GetFootprints() for p in f.Pads()
                        if p.GetNetCode() == gnd.GetNetCode() and p.IsOnLayer(lay) and o.PointInside(p.GetPosition())]
                for pad in pads:
                    c = pad.GetPosition(); best = None
                    for rr in [MM(0.6 + 0.1 * k) for k in range(20)]:
                        for a in range(0, 360, 10):
                            import math
                            pt = pcbnew.VECTOR2I(int(c.x + rr * math.cos(math.radians(a))), int(c.y + rr * math.sin(math.radians(a))))
                            if not fits_via(pt, r):
                                continue
                            seg = pcbnew.SHAPE_SEGMENT(c, pt, MM(0.25))
                            clash = False
                            for it, nc in others:
                                if nc == gnd.GetNetCode():
                                    continue
                                if it.IsOnLayer(lay) and it.GetEffectiveShape(lay).Collide(seg, MM(0.15)):
                                    clash = True; break
                            if not clash:
                                best = pt; break
                        if best: break
                    if best:
                        t = pcbnew.PCB_TRACK(board); t.SetStart(c); t.SetEnd(best); t.SetWidth(MM(0.25))
                        t.SetLayer(lay); t.SetNet(gnd); board.Add(t); others.append((t, gnd.GetNetCode()))
                        v = pcbnew.PCB_VIA(board); v.SetPosition(best); v.SetDrill(MM(0.25))
                        for L_ in (pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu):
                            v.SetWidth(L_, MM(0.45))
                        v.SetNet(gnd); board.Add(v); others.append((v, gnd.GetNetCode())); drills.append(best)
                        fixed_islands += 1; done = True; break
            if not done:
                print("  island without via at (%.2f, %.2f)" % (pcbnew.ToMM(bb.Centre().x), pcbnew.ToMM(bb.Centre().y)))
    print("island vias", fixed_islands)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    print("tracks", len(board.GetTracks()))
