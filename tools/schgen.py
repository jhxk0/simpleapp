"""Generate a label-based KiCad 7 schematic from a Design."""
import uuid as _uuid, math
from sexp import Sym, dump, find, findall
import kicadlib as K

S = Sym
def U(): return str(_uuid.uuid4())
def eff(size=1.27, justify=None, hide=False):
    e = [S("effects"), [S("font"), [S("size"), size, size]]]
    if justify:
        e.append([S("justify")] + [S(j) for j in justify.split()])
    if hide:
        e.append(S("hide"))
    return e

def snap(v, g=2.54):
    return round(round(v / g) * g, 4)

def resolve(part, pins):
    """Map design conn keys to pin numbers -> net."""
    bynum = {p["number"]: p for p in pins}
    out = {}
    for key, net in part.conn.items():
        if key in bynum:
            out[key] = net
            continue
        hits = [p["number"] for p in pins if p["name"] == key]
        if not hits:
            raise KeyError("%s: no pin %r in %s" % (part.ref, key, part.lib_id))
        for h in hits:
            out[h] = net
    return out

def generate(design, path, paper="A1"):
    W, H = {"A1": (841, 594), "A2": (594, 420), "A0": (1189, 841)}[paper]
    root = U()
    libs = {}
    for p in design.parts:
        if p.lib_id not in libs:
            libs[p.lib_id] = K.load_symbol(p.lib_id)
    libs["power:PWR_FLAG"] = K.load_symbol("power:PWR_FLAG")

    items = []
    netmap = {}  # (ref, pin) -> net, for cross-check
    # --- layout: groups flow in columns of fixed height
    margin, colw_min = 25.4, 60
    x0, y0 = margin, margin + 10
    colx, coly, colw = x0, y0, 0
    gx = colx
    textitems = []
    for g in design.groups:
        parts = [p for p in design.parts if p.group == g]
        # estimate group footprint: ICs individually, passives in a grid of 6 columns
        big = [p for p in parts if len(K.pins(libs[p.lib_id])) > 4]
        small = [p for p in parts if p not in big]
        boxes = []
        for p in big:
            bx = K.bbox(libs[p.lib_id])
            boxes.append((p, bx[2] - bx[0] + 50, bx[3] - bx[1] + 15))
        ncol = 6
        cell_w, cell_h = 22.86, 25.4
        gw = max([b[1] for b in boxes] + [ncol * cell_w if small else 0, colw_min])
        gh = sum(b[2] for b in boxes) + math.ceil(len(small) / ncol) * cell_h + 12
        if coly + gh > H - margin and coly > y0:
            colx += colw + 20; coly = y0; colw = 0
        textitems.append([S("text"), g.upper(), [S("at"), snap(colx), snap(coly), 0], eff(3.0, "left bottom"),
                          [S("uuid"), U()]])
        cy = coly + 8
        placed = []
        for p, bw, bh in boxes:
            bx = K.bbox(libs[p.lib_id])
            # symbol coords y-up; place so bbox top-left sits at (colx+25, cy)
            px = snap(colx + 25 - bx[0])
            py = snap(cy + bx[3] + 5)
            placed.append((p, px, py))
            cy += bh
        for i, p in enumerate(small):
            r, c = divmod(i, ncol)
            placed.append((p, snap(colx + 12 + c * cell_w), snap(cy + 8 + r * cell_h)))
        colw = max(colw, gw)
        coly += gh + 10

        for p, px, py in placed:
            sym = libs[p.lib_id]
            pins = K.pins(sym)
            nets = resolve(p, pins)
            for k, v in nets.items():
                netmap[(p.ref, k)] = v
            props = []
            fp = p.fp
            vals = [("Reference", p.ref), ("Value", p.value), ("Footprint", fp), ("Datasheet", ""),
                    ("MPN", p.mpn), ("LCSC", p.lcsc)]
            bx = K.bbox(sym)
            for i, (k, v) in enumerate(vals):
                if k == "Reference":
                    at = [S("at"), snap(px + bx[2] + 1.27, 1.27), snap(py - bx[3] - 1.27, 1.27), 0]
                    e = eff(1.27, "left")
                elif k == "Value":
                    at = [S("at"), snap(px + bx[2] + 1.27, 1.27), snap(py - bx[3] + 1.27, 1.27), 0]
                    e = eff(1.27, "left")
                else:
                    at = [S("at"), px, py, 0]
                    e = eff(1.27, hide=True)
                props.append([S("property"), k, v, at, e])
            inst = [S("symbol"), [S("lib_id"), p.lib_id], [S("at"), px, py, 0], [S("unit"), 1],
                    [S("in_bom"), S("no" if p.ref.startswith(("TP", "H")) else "yes")], [S("on_board"), S("yes")],
                    [S("dnp"), S("yes" if p.dnp else "no")],
                    [S("uuid"), U()]] + props
            inst += [[S("pin"), pin["number"], [S("uuid"), U()]] for pin in pins]
            inst.append([S("instances"), [S("project"), design.name,
                         [S("path"), "/" + root, [S("reference"), p.ref], [S("unit"), 1]]]])
            items.append(inst)
            # labels / no-connects at pin endpoints
            for pin in pins:
                ex, ey = px + pin["x"], py - pin["y"]
                net = nets.get(pin["number"])
                if net is None:
                    items.append([S("no_connect"), [S("at"), round(ex, 4), round(ey, 4)], [S("uuid"), U()]])
                    continue
                out = (pin["rot"] + 180) % 360   # outward direction, lib coords (y-up)
                if out == 180:   ang, j = 180, "right"
                elif out == 0:   ang, j = 0, "left"
                elif out == 90:  ang, j = 90, "left"    # up on screen
                else:            ang, j = 270, "right"
                items.append([S("label"), net, [S("at"), round(ex, 4), round(ey, 4), ang],
                              [S("fields_autoplaced")], eff(1.0, j + " bottom"), [S("uuid"), U()]])

    # PWR_FLAGs in their own block at the bottom right
    fx, fy = W - 120, H - 60
    for i, net in enumerate(design.pwr_flags):
        px, py = snap(fx + (i % 6) * 15.24), snap(fy + (i // 6) * 15.24)
        items.append([S("symbol"), [S("lib_id"), "power:PWR_FLAG"], [S("at"), px, py, 0], [S("unit"), 1],
                      [S("in_bom"), S("yes")], [S("on_board"), S("yes")], [S("dnp"), S("no")],
                      [S("uuid"), U()],
                      [S("property"), "Reference", "#FLG%02d" % (i + 1), [S("at"), px, py + 2.54, 0], eff(1.27, hide=True)],
                      [S("property"), "Value", "PWR_FLAG", [S("at"), px, py - 3.81, 0], eff(1.0)],
                      [S("property"), "Footprint", "", [S("at"), px, py, 0], eff(1.27, hide=True)],
                      [S("property"), "Datasheet", "", [S("at"), px, py, 0], eff(1.27, hide=True)],
                      [S("pin"), "1", [S("uuid"), U()]],
                      [S("instances"), [S("project"), design.name,
                       [S("path"), "/" + root, [S("reference"), "#FLG%02d" % (i + 1)], [S("unit"), 1]]]]])
        items.append([S("label"), net, [S("at"), px, py, 270], [S("fields_autoplaced")],
                      eff(1.0, "right bottom"), [S("uuid"), U()]])

    tree = [S("kicad_sch"), [S("version"), 20230121], [S("generator"), "eeschema"], [S("uuid"), root],
            [S("paper"), paper],
            [S("title_block"), [S("title"), design.title], [S("rev"), "A"],
             [S("comment"), 1, "Generated from tools/%s_design.py - edit the source, not this file" % design.name]],
            [S("lib_symbols")] + list(libs.values())] + textitems + items + \
           [[S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]]]
    with open(path, "w") as f:
        f.write(dump(tree) + "\n")
    return netmap
