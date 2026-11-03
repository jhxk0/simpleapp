"""Load KiCad symbols (flattening 'extends') and footprint pad lists."""
import copy, os, re
from sexp import parse, find, findall, Sym

SYMDIR = "/opt/q/usr/share/kicad/symbols"
FPDIR = "/opt/q/usr/share/kicad/footprints"
LOCAL_SYMLIB = {}   # libname -> path, for project libraries

_libcache = {}

def _lib(libname):
    if libname not in _libcache:
        path = LOCAL_SYMLIB.get(libname, os.path.join(SYMDIR, libname + ".kicad_sym"))
        with open(path) as f:
            tree = parse(f.read())
        _libcache[libname] = {s[1]: s for s in findall(tree, "symbol")}
    return _libcache[libname]

def load_symbol(lib_id):
    """Return a flattened symbol s-expr named 'Lib:Name' suitable for lib_symbols."""
    libname, name = lib_id.split(":")
    syms = _lib(libname)
    s = copy.deepcopy(syms[name])
    ext = find(s, "extends")
    if ext:
        base = load_symbol(libname + ":" + ext[1])
        bname = base[1].split(":")[1]
        body = []
        props = {p[1]: p for p in findall(s, "property")}
        for x in base[2:]:
            if isinstance(x, list) and x[0] == "property":
                body.append(props.pop(x[1], x))
            elif isinstance(x, list) and x[0] == "symbol":
                y = copy.deepcopy(x)
                y[1] = name + y[1][len(bname):]
                body.append(y)
            else:
                body.append(x)
        body = list(props.values()) + body
        s = [Sym("symbol"), lib_id] + body
        return s
    s[1] = lib_id
    return s

def pins(sym):
    """List of dicts: number,name,type,x,y,rot,length,unit,hidden."""
    out = []
    base = sym[1].split(":")[-1]
    for sub in findall(sym, "symbol"):
        m = re.match(re.escape(base) + r"_(\d+)_(\d+)$", sub[1])
        unit = int(m.group(1)) if m else 0
        for p in findall(sub, "pin"):
            at = find(p, "at")
            ln = find(p, "length")
            hidden = any(x == "hide" for x in p if isinstance(x, Sym))
            out.append(dict(type=str(p[1]), x=float(at[1]), y=float(at[2]),
                            rot=float(at[3]) if len(at) > 3 else 0.0,
                            length=float(ln[1]) if ln else 2.54,
                            name=find(p, "name")[1], number=find(p, "number")[1],
                            unit=unit, hidden=hidden))
    return out

def bbox(sym):
    xs, ys = [], []
    for p in pins(sym):
        xs.append(p["x"]); ys.append(p["y"])
    for sub in findall(sym, "symbol"):
        for g in sub:
            if not isinstance(g, list):
                continue
            for k in ("start", "end", "center"):
                v = find(g, k)
                if v:
                    xs.append(float(v[1])); ys.append(float(v[2]))
            pts = find(g, "pts")
            if pts:
                for xy in findall(pts, "xy"):
                    xs.append(float(xy[1])); ys.append(float(xy[2]))
    if not xs:
        return (-2.54, -2.54, 2.54, 2.54)
    return (min(xs), min(ys), max(xs), max(ys))

def footprint_pads(fp_id):
    lib, name = fp_id.split(":")
    path = os.path.join(FPDIR, lib + ".pretty", name + ".kicad_mod")
    with open(path) as f:
        t = parse(f.read())
    return [p[1] for p in findall(t, "pad")]
