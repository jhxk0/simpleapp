"""Usage: python3 build_sch.py fc|esc  -> writes ../<board>/<board>.kicad_sch and runs ERC."""
import sys, os, json, subprocess, importlib
sys.path.insert(0, os.path.dirname(__file__))
import kicadlib as K, customlib as CL, schgen, kienv

HERE = os.path.dirname(os.path.abspath(__file__))
board = sys.argv[1]
out = os.path.join(HERE, "..", board)
os.makedirs(out, exist_ok=True)

# project-local symbol library
LIB = os.path.join(out, "drone.kicad_sym")
N = "no_connect"
CL.write_lib(LIB, [
    CL.box_symbol("ICM-42688-P", "U",
        [("12", "AP_CS", "input"), ("13", "AP_SCLK", "input"), ("14", "AP_SDI", "bidirectional"),
         ("1", "AP_SDO", "output"), ("4", "INT1", "output"), ("9", "INT2_FSYNC", "bidirectional")],
        [("8", "VDD", "power_in"), ("5", "VDDIO", "power_in"), ("6", "GND", "power_in"), None,
         ("2", "RESV", N), ("3", "RESV", N), ("7", "RESV", N), ("10", "RESV", N), ("11", "RESV", N)],
        "Package_LGA:LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y", desc="6-axis IMU, SPI"),
])
K.LOCAL_SYMLIB["drone"] = LIB
with open(os.path.join(out, "sym-lib-table"), "w") as f:
    f.write('(sym_lib_table\n  (lib (name "drone")(type "KiCad")(uri "${KIPRJMOD}/drone.kicad_sym")(options "")(descr ""))\n)\n')

mod = importlib.import_module(board + "_design")
D = mod.DESIGN
sch = os.path.join(out, board + ".kicad_sch")
netmap = schgen.generate(D, sch)
pro = os.path.join(out, board + ".kicad_pro")
if not os.path.exists(pro):
    with open(pro, "w") as f:
        json.dump({"meta": {"filename": board + ".kicad_pro", "version": 1}}, f)
print("parts:", len(D.parts), " nets:", len(set(netmap.values())))

# ERC
rpt = os.path.join(out, "erc.json")
subprocess.run(kienv.kicad_cli() + ["sch", "erc", "--format", "json", "--severity-all", "-o", rpt, sch],
               check=True, capture_output=True)
r = json.load(open(rpt))
viol = [v for s in r["sheets"] for v in s["violations"]]
from collections import Counter
print("ERC:", Counter((v["severity"], v["type"]) for v in viol))
for v in viol[:25]:
    print("  ", v["severity"], v["type"], "|", v["description"], "|",
          "; ".join(i["description"] for i in v["items"]))

# netlist export + cross-check against the design source
xml = os.path.join(out, board + ".net.xml")
subprocess.run(kienv.kicad_cli() + ["sch", "export", "netlist", "--format", "kicadxml", "-o", xml, sch],
               check=True, capture_output=True)
import xml.etree.ElementTree as ET
t = ET.parse(xml)
got = {}
for n in t.iter("net"):
    for nd in n.iter("node"):
        got[(nd.get("ref"), nd.get("pin"))] = n.get("name")
bad = [(k, v, got.get(k)) for k, v in netmap.items() if got.get(k, "").lstrip("/") != v]
print("netlist cross-check mismatches:", len(bad), bad[:10])
