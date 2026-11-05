"""Locate KiCad 9 and Freerouting on this machine, so the tools run both locally and in the
original build container.  Override anything with environment variables:

  KICAD_SHARE      KiCad's share dir (contains symbols/ and footprints/)
  KICAD_CLI        kicad-cli executable
  KICAD_PYTHON     a Python that can `import pcbnew` (KiCad's bundled python on Windows/macOS)
  FREEROUTING_JAR  path to freerouting-2.4.1-executable.jar
  JAVA             java executable (Java 21+; Freerouting 2.4.1 needs 25 for its class files)
"""
import os, shutil, sys, glob

def _first(paths):
    for p in paths:
        if p and os.path.isdir(p):
            return p
    return None

IN_K9 = shutil.which("k9") is not None          # the original container runs KiCad in a chroot

def share_dir():
    env = os.environ.get("KICAD_SHARE")
    if env:
        return env
    fp = os.environ.get("KICAD9_FOOTPRINT_DIR")
    if fp:
        return os.path.dirname(fp.rstrip("/\\"))
    return _first(["/opt/q/usr/share/kicad", "/usr/share/kicad", "/usr/local/share/kicad",
                   "/Applications/KiCad/KiCad.app/Contents/SharedSupport",
                   r"C:\Program Files\KiCad\9.0\share\kicad"]) or "/usr/share/kicad"

def symbol_dir():
    return os.environ.get("KICAD9_SYMBOL_DIR") or os.path.join(share_dir(), "symbols")

def footprint_dir():
    return os.environ.get("KICAD9_FOOTPRINT_DIR") or os.path.join(share_dir(), "footprints")

def kicad_cli():
    if os.environ.get("KICAD_CLI"):
        return [os.environ["KICAD_CLI"]]
    if IN_K9:
        return ["k9", "kicad-cli"]
    for c in ["kicad-cli", "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
              r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe"]:
        if shutil.which(c) or os.path.isfile(c):
            return [c]
    sys.exit("kicad-cli not found: install KiCad 9 or set KICAD_CLI")

def kicad_python():
    """command prefix that runs a script with pcbnew available"""
    if os.environ.get("KICAD_PYTHON"):
        return [os.environ["KICAD_PYTHON"]]
    if IN_K9:
        return ["k9", "python3"]
    for c in ["/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3",
              r"C:\Program Files\KiCad\9.0\bin\python.exe"]:
        if os.path.isfile(c):
            return [c]
    return [sys.executable]                       # Linux: system python with python3-pcbnew

def freerouting():
    jar = os.environ.get("FREEROUTING_JAR") or _jar()
    if not jar:
        sys.exit("Freerouting jar not found: download freerouting-2.4.1-executable.jar and set FREEROUTING_JAR")
    java = os.environ.get("JAVA") or ("/usr/lib/jvm/java-25-openjdk-amd64/bin/java"
                                      if os.path.isfile("/usr/lib/jvm/java-25-openjdk-amd64/bin/java") else "java")
    heap = os.environ.get("FREEROUTING_HEAP", "6g")      # cap the heap; it grows without bound otherwise
    return [java, "-Xmx" + heap, "-jar", jar, "--gui.enabled=false"]

def _jar():
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in [os.path.join(here, "freerouting*.jar"), os.path.join(here, "..", "freerouting*.jar"),
                os.path.expanduser("~/tools/freerouting*.jar"), "/home/user/tools/freerouting*.jar"]:
        g = sorted(glob.glob(pat))
        if g:
            return g[-1]
    return None
