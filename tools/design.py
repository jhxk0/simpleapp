"""Tiny design-description DSL shared by the FC and ESC boards."""

class Part:
    def __init__(self, ref, lib_id, value, fp, conn, group, mpn="", lcsc="", lcsc_ok=False, note="", dnp=False):
        self.ref, self.lib_id, self.value, self.fp = ref, lib_id, value, fp
        self.conn = conn          # {pin number or pin name: net}
        self.group = group        # schematic section
        self.mpn, self.lcsc, self.lcsc_ok, self.note, self.dnp = mpn, lcsc, lcsc_ok, note, dnp

class Design:
    def __init__(self, name, title):
        self.name, self.title = name, title
        self.parts = []
        self.groups = []
        self._n = {}
        self.pwr_flags = []

    def group(self, g):
        if g not in self.groups:
            self.groups.append(g)
        self.cur = g

    def ref(self, prefix):
        self._n[prefix] = self._n.get(prefix, 0) + 1
        return "%s%d" % (prefix, self._n[prefix])

    def add(self, prefix, lib_id, value, fp, conn, **kw):
        p = Part(self.ref(prefix), lib_id, value, fp, conn, self.cur, **kw)
        self.parts.append(p)
        return p

    # ---- passives -------------------------------------------------------
    R_LCSC = {"0": "C17168", "22": "C25092", "33": "C25105", "100": "C25076", "1k": "C11702",
              "1.5k": "C25867", "2.2k": "C25879", "4.7k": "C25900", "5.1k": "C25905", "10k": "C25744",
              "20k": "C25765", "100k": "C25741", "1M": "C26083", "27k": "C25771"}
    C_LCSC = {("100nF", "0402"): "C1525", ("1uF", "0402"): "C52923", ("2.2uF", "0402"): "C12530",
              ("4.7uF", "0603"): "C19666", ("10uF", "0603"): "C19702", ("22uF", "0805"): "C45783",
              ("33pF", "0402"): "C1562", ("10nF", "0402"): "C15195", ("4.7nF", "0402"): "C1538",
              ("10uF", "1206"): "C13585", ("100nF", "0603"): "C14663"}

    def R(self, val, a, b, size="0402", **kw):
        fp = {"0402": "Resistor_SMD:R_0402_1005Metric", "0603": "Resistor_SMD:R_0603_1608Metric"}[size]
        lc = self.R_LCSC.get(val, "")
        return self.add("R", "Device:R", val, fp, {"1": a, "2": b},
                        mpn="%s %s 1%%" % (size, val), lcsc=lc, lcsc_ok=bool(lc), **kw)

    def C(self, val, a, b, size="0402", volt="", **kw):
        fp = {"0402": "Capacitor_SMD:C_0402_1005Metric", "0603": "Capacitor_SMD:C_0603_1608Metric",
              "0805": "Capacitor_SMD:C_0805_2012Metric", "1206": "Capacitor_SMD:C_1206_3216Metric",
              "1210": "Capacitor_SMD:C_1210_3225Metric"}[size]
        lc = kw.pop("lcsc", self.C_LCSC.get((val, size), ""))
        v = val + (" " + volt if volt else "")
        return self.add("C", "Device:C", v, fp, {"1": a, "2": b},
                        mpn="%s %s %s X5R/X7R" % (size, val, volt), lcsc=lc,
                        lcsc_ok=kw.pop("lcsc_ok", (val, size) in self.C_LCSC), **kw)

    def flag(self, net):
        self.pwr_flags.append(net)

    def nets(self):
        """{net: [(ref, pin-key)]} — pin keys still unresolved names; resolved in schgen."""
        out = {}
        for p in self.parts:
            for k, n in p.conn.items():
                out.setdefault(n, []).append((p.ref, k))
        return out
