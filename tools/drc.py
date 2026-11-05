"""drc.py <board>: run KiCad DRC with schematic parity, print a summary."""
import sys, json, subprocess, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kienv
from collections import Counter
b = sys.argv[1]; d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", b)
subprocess.run(kienv.kicad_cli() + ["pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity",
                "-o", os.path.join(d, "drc.json"), os.path.join(d, b + ".kicad_pcb")], capture_output=True)
r = json.load(open(os.path.join(d, "drc.json")))
allv = [(k, v) for k in ("violations", "unconnected_items", "schematic_parity") for v in r.get(k, [])]
print(Counter((v["severity"], v["type"]) for k, v in allv))
show = int(sys.argv[2]) if len(sys.argv) > 2 else 15
for k, v in [x for x in allv if x[1]["severity"] == "error"][:show]:
    print(" ", v["type"], "|", "; ".join("%s @(%.2f,%.2f)" % (i["description"][:60], i["pos"]["x"], i["pos"]["y"]) for i in v["items"]))

errs = sum(1 for k, v in allv if v["severity"] == "error")
print("ERRORS:", errs)
sys.exit(1 if errs else 0)
