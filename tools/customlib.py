"""Generate simple box symbols for parts missing from the KiCad library."""
from sexp import Sym, dump

def box_symbol(name, ref, left, right, fp, width=15.24, desc=""):
    """left/right: lists of (number, name, etype) or None for a gap."""
    rows = max(len(left), len(right))
    h = (rows + 1) * 2.54
    top = h / 2
    body = [Sym("rectangle"), [Sym("start"), -width / 2, top], [Sym("end"), width / 2, -top],
            [Sym("stroke"), [Sym("width"), 0.254], [Sym("type"), Sym("default")]],
            [Sym("fill"), [Sym("type"), Sym("background")]]]
    pins = []
    for side, lst in (("L", left), ("R", right)):
        for i, p in enumerate(lst):
            if p is None:
                continue
            num, pname, et = p
            y = top - 2.54 * (i + 1)
            x = -width / 2 - 2.54 if side == "L" else width / 2 + 2.54
            rot = 0 if side == "L" else 180
            pins.append([Sym("pin"), Sym(et), Sym("line"), [Sym("at"), round(x, 2), round(y, 2), rot],
                         [Sym("length"), 2.54],
                         [Sym("name"), pname, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]],
                         [Sym("number"), num, [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]]])
    def prop(k, v, y, hide=False):
        eff = [Sym("effects"), [Sym("font"), [Sym("size"), 1.27, 1.27]]]
        if hide:
            eff.append(Sym("hide"))
        return [Sym("property"), k, v, [Sym("at"), 0, y, 0], eff]
    return [Sym("symbol"), name, [Sym("in_bom"), Sym("yes")], [Sym("on_board"), Sym("yes")],
            prop("Reference", ref, top + 1.27), prop("Value", name, -top - 1.27),
            prop("Footprint", fp, -top - 3.81, True), prop("Datasheet", "", 0, True),
            prop("Description", desc, 0, True),
            [Sym("symbol"), name + "_0_1", body],
            [Sym("symbol"), name + "_1_1"] + pins]

def write_lib(path, symbols):
    tree = [Sym("kicad_symbol_lib"), [Sym("version"), 20220914], [Sym("generator"), "drone_gen"]] + symbols
    with open(path, "w") as f:
        f.write(dump(tree) + "\n")
