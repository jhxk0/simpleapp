"""Cross-platform build pipeline (Linux / macOS / Windows).

  python3 tools/pipeline.py <board> sch               schematic + ERC + netlist cross-check
  python3 tools/pipeline.py <board> route [passes] [tries]
                                                      place, fanout, Freerouting x2, pours, DRC;
                                                      retries until DRC is clean
  python3 tools/pipeline.py <board> fab               Gerbers, drill, BOM, CPL
  python3 tools/pipeline.py <board> all               all three

<board> is fc or esc.  See tools/kienv.py for the environment variables that point it at KiCad,
Java and Freerouting if they are not found automatically.
"""
import os, sys, subprocess, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kienv

def run(cmd, cwd=HERE, show=1, filt=("assert", "leak")):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    lines = [l for l in (r.stdout + r.stderr).splitlines() if l.strip() and not any(f in l for f in filt)]
    for l in lines[-(25 if r.returncode else show):] if (show or r.returncode) else []:
        print("  " + l)
    return r.returncode

def kpy(*args, show=1):
    rc = run(kienv.kicad_python() + list(args), show=show, filt=("assert", "leak", "Debug:"))
    if rc:
        sys.exit("step failed: " + " ".join(args))
    return rc

def sch(b):
    if run([sys.executable, "build_sch.py", b], show=20):
        sys.exit("schematic step failed")

def route(b, passes=100, tries=3):
    d = os.path.join(HERE, "..", b)
    pcb, fan = os.path.join(d, b + ".kicad_pcb"), os.path.join(d, b + ".fanout.kicad_pcb")
    kpy("pcbgen.py", b)
    kpy("route.py", b, "fanout", show=8)
    pre = getattr(__import__(b + "_layout"), "PREROUTE", None)
    if pre:                                  # long critical nets first, with the grid router (locked)
        kpy("finish_route.py", b, "--pre", pre, show=1)
    shutil.copy(pcb, fan)
    fr = kienv.freerouting()
    try:
        scores = []
        for t in range(1, tries + 1):
            print("--- attempt", t)
            shutil.copy(fan, pcb)
            for p in (1, 2):
                kpy("route.py", b, "dsn")
                ses = os.path.join(d, b + ".ses")
                if os.path.exists(ses):
                    os.remove(ses)
                with open(os.path.join(d, "fr%d.log" % p), "w") as log:
                    subprocess.run(fr + ["-de", b + ".dsn", "-do", b + ".ses", "-mp", str(passes), "-mt", "3"],
                                   cwd=d, stdout=log, stderr=subprocess.STDOUT)
                kpy("route.py", b, "ses")
            kpy("route.py", b, "finish", show=4)
            if run([sys.executable, "drc.py", b, "20"], show=25) == 0:
                print("CLEAN on attempt", t)
                return
            # finish what Freerouting left open with the grid router; keep a round only if it helps
            best = errors(d)
            for mode in ([], ["--near"]):
                shutil.copy(pcb, pcb + ".before")
                kpy("finish_route.py", b, os.path.join(d, "drc.json"), *mode, show=2)
                kpy("route.py", b, "finish", show=2)
                rc = run([sys.executable, "drc.py", b, "20"], show=1)
                if rc == 0:
                    print("CLEAN on attempt", t, "after finish_route", " ".join(mode))
                    return
                if errors(d) >= best:
                    print("  finish_route %s did not help (%d >= %d) - reverted" % (" ".join(mode), errors(d), best))
                    shutil.copy(pcb + ".before", pcb)
                    run([sys.executable, "drc.py", b, "20"], show=0)
                else:
                    best = errors(d)
                    print("  finish_route %s: %d errors" % (" ".join(mode), best))
            if os.path.exists(pcb + ".before"):
                os.remove(pcb + ".before")
            shutil.copy(pcb, os.path.join(d, "%s.attempt%d.kicad_pcb" % (b, t)))   # keep for inspection
            scores.append((errors(d), t))
        e, t = min(scores)
        shutil.copy(os.path.join(d, "%s.attempt%d.kicad_pcb" % (b, t)), pcb)        # keep the best attempt
        run([sys.executable, "drc.py", b, "20"], show=0)
        sys.exit("not clean after %d attempts; kept attempt %d with %d DRC errors (see drc.json)" % (tries, t, e))
    finally:
        if os.path.exists(fan):
            os.remove(fan)

def errors(d):
    import json
    r = json.load(open(os.path.join(d, "drc.json")))
    return sum(1 for k in ("violations", "unconnected_items", "schematic_parity") for v in r.get(k, [])
               if v["severity"] == "error")

def fab(b):
    if run([sys.executable, "fab.py", b], show=3):
        sys.exit("fab step failed")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    b, step = sys.argv[1], sys.argv[2]
    extra = [int(x) for x in sys.argv[3:]]
    if step in ("sch", "all"):
        sch(b)
    if step in ("route", "all"):
        route(b, *extra)
    if step in ("fab", "all"):
        fab(b)
