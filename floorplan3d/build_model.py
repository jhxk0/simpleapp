"""Convert the ground-floor plan in the project DXF into a 3D model (GLB + OBJ).

Usage: python3 build_model.py <plan.dxf> <out_dir>

Reads walls (DUVAR), columns (KOLON), doors/windows (DOĞRAMA + K:/P: labels),
stairs (MERDİVEN M) and furniture blocks from the floor-plan sheet. Drawing units
are centimetres; heights come from the section sheet (KESİTLER):
ground ±0.00, finished floor +0.60, window head +2.80, eave +3.50, roof slope 40 %.
"""
import re
import sys
import json
from pathlib import Path

import numpy as np
import ezdxf
import trimesh
from ezdxf import bbox as ebbox
from ezdxf import path as epath
from ezdxf.disassemble import recursive_decompose
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union

# Floor-plan sheet window in drawing coordinates (cm).
X0, Y0, X1, Y1 = 497850, 4399200, 499050, 4400850

FLOOR = 0.60        # finished floor level
CEIL = 3.35         # underside of roof slab
SLAB_TOP = 3.50     # eave level
WIN_HEAD = FLOOR + 2.20
DOOR_HEAD = FLOOR + 2.10
ROOF_SLOPE = 0.40
OVERHANG = 0.90


def rel(x, y):
    return x - X0, y - Y0


def load(path):
    doc = ezdxf.readfile(path)
    msp = doc.modelspace()
    plan = box(X0, Y0, X1, Y1)
    lines = {"DUVAR": [], "KOLON": [], "DOĞRAMA": []}
    texts, inserts = [], []
    for e in msp:
        lay, t = e.dxf.layer, e.dxftype()
        if t == "TEXT":
            p = e.dxf.insert
            if plan.contains(LineString([(p.x, p.y), (p.x + 1, p.y)])):
                texts.append((e.dxf.text, p.x, p.y))
            continue
        if t == "INSERT":
            b = ebbox.extents([e])
            if b.has_data and plan.contains(box(b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)):
                inserts.append((lay, e.dxf.name, (b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)))
            continue
        if lay not in lines:
            continue
        if t == "LINE":
            g = LineString([(e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)])
        elif t == "LWPOLYLINE":
            pts = [(q[0], q[1]) for q in e.get_points()]
            if e.closed:
                pts.append(pts[0])
            if len(pts) < 2:
                continue
            g = LineString(pts)
        else:
            continue
        if plan.contains(g):
            lines[lay].append(g)
    return doc, lines, texts, inserts


def wall_footprint(lines):
    """Fill the space between parallel wall lines (morphological closing)."""
    r = 14  # half of the thickest (25 cm) wall, plus tolerance
    w = unary_union(lines["DUVAR"]).buffer(r, join_style=2, cap_style=2).buffer(-r, join_style=2)
    cols = unary_union([Polygon(k.coords) for k in lines["KOLON"] if len(k.coords) >= 4])
    w = unary_union([w, cols]).buffer(4, join_style=2).buffer(-4, join_style=2)
    return w, cols


def find_openings(walls, cols, lines):
    """Pair facing wall end-caps (or column faces) to get opening rectangles."""
    caps = []

    def add(a, b, any_len=False):
        a, b = np.asarray(a), np.asarray(b)
        L = np.linalg.norm(b - a)
        if L < 5 or (L > 32 and not any_len):
            return
        if abs(a[1] - b[1]) < 0.5:
            caps.append(("h", min(a[0], b[0]), max(a[0], b[0]), a[1]))
        elif abs(a[0] - b[0]) < 0.5:
            caps.append(("v", min(a[1], b[1]), max(a[1], b[1]), a[0]))

    for g in lines["DUVAR"]:
        c = list(g.coords)
        for i in range(len(c) - 1):
            add(c[i], c[i + 1])
    for c in getattr(cols, "geoms", [cols]):
        xs = list(c.exterior.coords)
        for i in range(len(xs) - 1):
            add(xs[i], xs[i + 1], any_len=True)

    core = walls.buffer(-1.5)
    found = []
    for i, c in enumerate(caps):
        best = None
        for j, e in enumerate(caps):
            if j == i or e[0] != c[0] or e[3] <= c[3]:
                continue
            lo, hi = max(c[1], e[1]), min(c[2], e[2])
            dist = e[3] - c[3]
            if hi - lo < 8 or not (35 <= dist <= 420):
                continue
            r = box(lo, c[3], hi, e[3]) if c[0] == "h" else box(c[3], lo, e[3], hi)
            if r.buffer(-1).intersects(core):
                continue
            if best is None or dist < best[0]:
                best = (dist, r)
        if best:
            found.append(best[1])
    out = []
    for r in sorted(found, key=lambda r: -r.area):
        if not any(r.intersection(u).area > 0.5 * r.area for u in out):
            out.append(r)
    return out


def classify(openings, lines, texts, inserts):
    door_boxes = [box(*b) for lay, name, b in inserts if lay == "DOĞRAMA"]
    frames = unary_union(lines["DOĞRAMA"])
    labels = []
    for t, x, y in texts:
        m = re.match(r"([KP]):\s*(\d+)\s*/\s*(\d*)", t)
        if m:
            labels.append((m.group(1), int(m.group(2)), int(m.group(3) or 150), x, y))
    result = []
    for r in openings:
        x0, y0, x1, y1 = r.bounds
        horiz = (x1 - x0) >= (y1 - y0)
        length = max(x1 - x0, y1 - y0)
        along = (lambda b: max(0, min(x1, b.bounds[2]) - max(x0, b.bounds[0]))) if horiz else \
                (lambda b: max(0, min(y1, b.bounds[3]) - max(y0, b.bounds[1])))
        is_door = any(along(b) >= 0.7 * length and b.buffer(5).intersects(r) for b in door_boxes)
        if is_door:
            result.append({"kind": "door", "rect": r.bounds, "head": DOOR_HEAD})
            continue
        if frames.intersection(r.buffer(0.5)).length < 0.6 * length:
            continue  # open side of the veranda / not a real opening
        c = r.centroid
        near = [l for l in labels if l[0] == "P"]
        lab = min(near, key=lambda l: (l[3] - c.x) ** 2 + (l[4] - c.y) ** 2) if near else None
        h = (lab[2] if lab else 150) / 100
        if h >= 2.0:
            result.append({"kind": "glassdoor", "rect": r.bounds, "sill": FLOOR, "head": WIN_HEAD})
        else:
            result.append({"kind": "window", "rect": r.bounds, "sill": WIN_HEAD - h, "head": WIN_HEAD})
    return result


class Scene:
    def __init__(self, cx, cy):
        self.cx, self.cy = cx, cy
        self.parts = {}

    def m(self, x, y):
        return (x - self.cx) / 100.0, (y - self.cy) / 100.0

    def poly(self, mat, geom, z0, z1):
        if geom.is_empty or z1 <= z0:
            return
        for g in getattr(geom, "geoms", [geom]):
            if g.geom_type != "Polygon" or g.area < 1:
                continue
            g2 = Polygon([self.m(*p) for p in g.exterior.coords],
                         [[self.m(*p) for p in i.coords] for i in g.interiors])
            mesh = trimesh.creation.extrude_polygon(g2, z1 - z0)
            mesh.apply_translation((0, 0, z0))
            self.parts.setdefault(mat, []).append(mesh)

    def boxcm(self, mat, x0, y0, x1, y1, z0, z1):
        self.poly(mat, box(x0, y0, x1, y1), z0, z1)

    def mesh(self, mat, mesh):
        self.parts.setdefault(mat, []).append(mesh)

    def export(self, out_dir):
        scene = trimesh.Scene()
        colors = {
            "wall": [236, 230, 218], "column": [236, 230, 218], "slab": [225, 220, 210],
            "roof": [168, 74, 46], "fascia": [110, 70, 45], "platform": [190, 182, 168],
            "floor": [196, 160, 118], "stairs": [190, 182, 168], "glass": [150, 190, 210],
            "frame": [70, 70, 72], "door": [120, 80, 50], "railing": [60, 60, 62],
            "ground": [120, 150, 90], "furniture": [214, 205, 190], "bed": [235, 235, 240],
            "sofa": [120, 130, 140], "wood": [150, 110, 75], "sanitary": [245, 245, 245],
            "counter": [90, 90, 95],
        }
        for mat, meshes in self.parts.items():
            m = trimesh.util.concatenate(meshes)
            # Blender/GLB are Y-up; trimesh exports Z-up meshes as-is, rotate for GLB.
            c = colors.get(mat, [200, 200, 200])
            m.visual = trimesh.visual.ColorVisuals(m, face_colors=np.tile(c + [255], (len(m.faces), 1)))
            scene.add_geometry(m, node_name=mat, geom_name=mat)
        rot = trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0])
        y_up = scene.copy()
        y_up.apply_transform(rot)
        y_up.export(Path(out_dir) / "house.glb")
        scene.export(Path(out_dir) / "house.obj")


def hip_roof(s, x0, y0, x1, y1, z):
    """Hip roof over rectangle (metres) with ridge along the long axis."""
    w, d = x1 - x0, y1 - y0
    t = 0.18
    if d >= w:
        h = w / 2
        rz = z + h * ROOF_SLOPE
        cx = (x0 + x1) / 2
        top = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (cx, y0 + h, rz), (cx, y1 - h, rz)]
        faces = [(0, 1, 4), (1, 2, 5), (1, 5, 4), (2, 3, 5), (3, 0, 4), (3, 4, 5)]
    else:
        h = d / 2
        rz = z + h * ROOF_SLOPE
        cy = (y0 + y1) / 2
        top = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), (x0 + h, cy, rz), (x1 - h, cy, rz)]
        faces = [(0, 1, 5), (0, 5, 4), (1, 2, 5), (2, 3, 4), (2, 4, 5), (3, 0, 4)]
    v = np.array(top)
    vb = v.copy()
    vb[:, 2] -= t
    verts = np.vstack([v, vb])
    f = [list(x) for x in faces] + [[a + 6, c + 6, b + 6] for a, b, c in faces]
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 0)]:
        f += [[a, b + 6, b], [a, a + 6, b + 6]]
    roof = trimesh.Trimesh(verts, f, process=True)
    roof.fix_normals()
    s.mesh("roof", roof)
    return rz


def build(dxf_path, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    doc, lines, texts, inserts = load(dxf_path)
    walls, cols = wall_footprint(lines)
    openings = classify(find_openings(walls, cols, lines), lines, texts, inserts)

    # Footprint (absolute cm): outer wall extents.
    wx0, wy0, wx1, wy1 = walls.bounds
    s = Scene((wx0 + wx1) / 2, (wy0 + wy1) / 2)
    A = lambda x, y: (X0 + x, Y0 + y)  # plan-relative cm -> absolute

    # Ground and raised platform (+0.60). Entrance porch steps cut out at the SW.
    s.poly("ground", box(wx0 - 100000, wy0 - 100000, wx1 + 100000, wy1 + 100000), -0.05, 0.0)
    porch_cut = box(*A(40, 0), *A(250, 148))
    platform = box(wx0, wy0, wx1, wy1).difference(porch_cut)
    s.poly("platform", platform, 0.0, FLOOR - 0.02)
    interior = box(wx0, wy0, wx1, wy1).difference(box(*A(0, 1328), *A(598, 1700))).difference(porch_cut)
    s.poly("floor", interior, FLOOR - 0.02, FLOOR)
    s.poly("platform", box(*A(40, 1328), *A(598, 1603)), FLOOR - 0.02, FLOOR)  # veranda deck

    # Entrance stairs (6 risers, 35 cm treads) going south, veranda stairs going north.
    for k in range(1, 5):
        z = FLOOR - FLOOR / 5 * k
        s.boxcm("stairs", *A(40, 148 - 35 * k), *A(250, 148 - 35 * (k - 1)), 0, z)
    for k in range(1, 5):
        z = FLOOR - FLOOR / 5 * k
        s.boxcm("stairs", *A(445, 1603 + 35 * (k - 1)), *A(595, 1603 + 35 * k), 0, z)

    # Walls and columns, full height to the slab.
    s.poly("wall", walls.difference(cols), FLOOR, CEIL)
    s.poly("column", cols, FLOOR, CEIL)

    # Openings: lintels, sills, glazing, frames.
    for o in openings:
        x0, y0, x1, y1 = o["rect"]
        r = box(x0, y0, x1, y1)
        s.poly("wall", r, o["head"], CEIL)
        horiz = (x1 - x0) >= (y1 - y0)
        if o["kind"] == "door":
            if r.intersects(box(*A(130, 290), *A(240, 320))):  # main entrance: closed wooden door
                s.poly("door", r.buffer(-4 if horiz else -4), FLOOR, o["head"])
            continue
        if o["sill"] > FLOOR:
            s.poly("wall", r, FLOOR, o["sill"])
        c = r.centroid
        pane = box(x0, c.y - 1.5, x1, c.y + 1.5) if horiz else box(c.x - 1.5, y0, c.x + 1.5, y1)
        s.poly("glass", pane, o["sill"], o["head"])
        fr = 5
        if horiz:
            frame = unary_union([box(x0, c.y - 4, x0 + fr, c.y + 4), box(x1 - fr, c.y - 4, x1, c.y + 4),
                                 box((x0 + x1) / 2 - 2.5, c.y - 4, (x0 + x1) / 2 + 2.5, c.y + 4)])
            bar = box(x0, c.y - 4, x1, c.y + 4)
        else:
            frame = unary_union([box(c.x - 4, y0, c.x + 4, y0 + fr), box(c.x - 4, y1 - fr, c.x + 4, y1),
                                 box(c.x - 4, (y0 + y1) / 2 - 2.5, c.x + 4, (y0 + y1) / 2 + 2.5)])
            bar = box(c.x - 4, y0, c.x + 4, y1)
        s.poly("frame", frame, o["sill"], o["head"])
        s.poly("frame", bar, o["sill"], o["sill"] + 0.05)
        s.poly("frame", bar, o["head"] - 0.05, o["head"])

    # Veranda railing (120 cm) on the west and north sides.
    for rx0, ry0, rx1, ry1 in [(40, 1328, 48, 1573), (100, 1595, 445, 1603)]:
        s.boxcm("railing", *A(rx0, ry0), *A(rx1, ry1), FLOOR + 1.15, FLOOR + 1.20)
        horiz = (rx1 - rx0) > (ry1 - ry0)
        n = int(max(rx1 - rx0, ry1 - ry0) // 12)
        for i in range(n + 1):
            if horiz:
                px = rx0 + i * (rx1 - rx0) / n
                s.boxcm("railing", *A(px - 1, ry0 + 2), *A(px + 1, ry1 - 2), FLOOR, FLOOR + 1.15)
            else:
                py = ry0 + i * (ry1 - ry0) / n
                s.boxcm("railing", *A(rx0 + 2, py - 1), *A(rx1 - 2, py + 1), FLOOR, FLOOR + 1.15)

    # Furniture from blocks / polylines (simple massing).
    heights = {"çift yatak": ("bed", 0.55), "grth": ("wood", 0.45), "ddgt": ("sofa", 0.80),
               "Klozet-3": ("sanitary", 0.40), "A$C1DB355E0": ("sanitary", 0.85),
               "ALAPE": ("sanitary", 0.92), "FRN": ("counter", 0.92)}
    for lay, name, b in inserts:
        if name in heights:
            mat, h = heights[name]
            s.boxcm(mat, b[0] + 2, b[1] + 2, b[2] - 2, b[3] - 2, FLOOR, FLOOR + h)
    extra = [((415, 743, 610, 833), "wood", 0.75),     # dining table
             ((987, 781, 1107, 851), "wood", 0.75),    # desks
             ((966, 71, 1101, 136), "wood", 0.75),
             ((1038, 1417, 1108, 1570), "wood", 0.75),
             ((572, 1047, 607, 1259), "wood", 0.50),   # TV unit
             ((65, 578, 125, 900), "counter", 0.92),   # kitchen counter
             ((125, 578, 185, 638), "counter", 0.92)]
    for (a, b_, c, d), mat, h in extra:
        s.boxcm(mat, *A(a, b_), *A(c, d), FLOOR, FLOOR + h)

    # Roof slab and hip roof with 90 cm overhang, 40 % slope.
    s.poly("slab", box(wx0, wy0, wx1, wy1), CEIL, SLAB_TOP)
    mx0, my0 = s.m(wx0, wy0)
    mx1, my1 = s.m(wx1, wy1)
    ridge = hip_roof(s, mx0 - OVERHANG, my0 - OVERHANG, mx1 + OVERHANG, my1 + OVERHANG, SLAB_TOP)
    o = OVERHANG * 100
    outer = box(wx0 - o, wy0 - o, wx1 + o, wy1 + o)
    s.poly("fascia", outer.difference(outer.buffer(-3, join_style=2)), SLAB_TOP - 0.22, SLAB_TOP - 0.02)

    s.export(out_dir)
    info = {
        "footprint_m": [round((wx1 - wx0) / 100, 2), round((wy1 - wy0) / 100, 2)],
        "floor_level_m": FLOOR, "eave_m": SLAB_TOP, "ridge_m": round(ridge, 2),
        "openings": {k: sum(o["kind"] == k for o in openings) for k in ("door", "window", "glassdoor")},
    }
    (out_dir / "model_info.json").write_text(json.dumps(info, indent=2))
    print(json.dumps(info, indent=2))


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
