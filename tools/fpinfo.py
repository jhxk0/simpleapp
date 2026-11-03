import pcbnew, sys
for fid in sys.argv[1:]:
    lib, n = fid.split(":")
    fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/%s.pretty" % lib, n)
    bb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox() if fp.GetCourtyard(pcbnew.F_CrtYd).OutlineCount() else fp.GetBoundingBox()
    mm = pcbnew.ToMM
    print("##", n, "courtyard x[%.2f,%.2f] y[%.2f,%.2f]" % (mm(bb.GetLeft()), mm(bb.GetRight()), mm(bb.GetTop()), mm(bb.GetBottom())))
    print("   pads:", " ".join("%s(%.2f,%.2f)" % (p.GetNumber(), mm(p.GetPosition().x), mm(p.GetPosition().y)) for p in fp.Pads())[:400])
