"""fab.py <board>: Gerbers + drill (zipped), JLCPCB BOM + CPL, full BOM with sourcing notes, renders."""
import sys, os, csv, subprocess, shutil, importlib, zipfile
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
b = sys.argv[1]
d = os.path.abspath(os.path.join(HERE, "..", b))
pcb = os.path.join(d, b + ".kicad_pcb")
out = os.path.join(d, "fab"); shutil.rmtree(out, ignore_errors=True); os.makedirs(out)
g = os.path.join(out, "gerbers"); os.makedirs(g)

def k9(*args):
    r = subprocess.run(["k9", "kicad-cli"] + list(args), capture_output=True, text=True, cwd=d)
    if r.returncode:
        print(r.stdout, r.stderr); raise SystemExit(1)

nlay = importlib.import_module(b + "_layout").LAYERS
layers = "F.Cu," + "".join("In%d.Cu," % i for i in range(1, nlay - 1)) + "B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
k9("pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask", "--no-x2", "-o", g + "/", pcb)
k9("pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
   "--map-format", "gerberx2", "-o", g + "/", pcb)
with zipfile.ZipFile(os.path.join(out, "%s-gerbers.zip" % b), "w", zipfile.ZIP_DEFLATED) as z:
    for f in sorted(os.listdir(g)):
        z.write(os.path.join(g, f), f)

# placement
pos = os.path.join(out, "pos.csv")
k9("pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "--exclude-dnp",
   "--smd-only", "-o", pos, pcb)
design = importlib.import_module(b + "_design").DESIGN
parts = {p.ref: p for p in design.parts}
skip = lambda r: r.startswith(("TP", "H"))          # bare pads and holes are not assembled
with open(os.path.join(out, "%s-CPL-jlcpcb.csv" % b), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for row in csv.DictReader(open(pos)):
        if skip(row["Ref"]): continue
        w.writerow([row["Ref"], row["PosX"] + "mm", row["PosY"] + "mm",
                    "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
os.remove(pos)

# BOMs
groups = OrderedDict()
for p in design.parts:
    if skip(p.ref): continue
    key = (p.value, p.fp, p.mpn, p.lcsc)
    groups.setdefault(key, []).append(p)
with open(os.path.join(out, "%s-BOM-jlcpcb.csv" % b), "w", newline="") as f:
    w = csv.writer(f); w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, mpn, lcsc), ps in groups.items():
        w.writerow([val, ",".join(p.ref for p in ps), fp.split(":")[1], lcsc])
with open(os.path.join(out, "%s-BOM-full.csv" % b), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "Designators", "Value", "MPN / spec", "Footprint", "LCSC", "LCSC status", "Notes"])
    for (val, fp, mpn, lcsc), ps in groups.items():
        status = ("recalled - confirm in JLC BOM tool" if ps[0].lcsc_ok else
                  "MISSING - pick an equivalent" if not lcsc else "unverified")
        notes = "; ".join(sorted({p.note for p in ps if p.note}))
        w.writerow([len(ps), " ".join(p.ref for p in ps), val, mpn, fp.split(":")[1], lcsc, status, notes])
print("lines:", len(groups), " parts placed:", sum(len(v) for v in groups.values()))

# renders (2D, both sides) for the README
for side, flags in (("top", []), ("bottom", ["--mirror"])):
    lay = "F.Cu,F.Silkscreen,F.Mask,Edge.Cuts" if side == "top" else "B.Cu,B.Silkscreen,B.Mask,Edge.Cuts"
    k9("pcb", "export", "svg", "--mode-single", "--exclude-drawing-sheet", "--fit-page-to-board", *flags,
       "--layers", lay, "-o", os.path.join(out, "%s-%s.svg" % (b, side)), pcb)
print("fab outputs in", out)
