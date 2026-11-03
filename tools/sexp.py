"""Minimal S-expression reader/writer for KiCad files."""
import re

class Sym(str):
    """Bare (unquoted) atom."""
    pass

_tok = re.compile(r'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|([^\s()"]+))', re.S)

def parse(text):
    stack, cur = [], []
    pos = 0
    n = len(text)
    while pos < n:
        m = _tok.match(text, pos)
        if not m:
            if text[pos:].strip() == "":
                break
            raise ValueError("parse error at %d: %r" % (pos, text[pos:pos + 40]))
        pos = m.end()
        if m.group(1):
            stack.append(cur); cur = []
        elif m.group(2):
            done = cur; cur = stack.pop(); cur.append(done)
        elif m.group(3) is not None:
            cur.append(m.group(3).replace('\\"', '"').replace('\\\\', '\\'))
        else:
            cur.append(Sym(m.group(4)))
    return cur[0] if len(cur) == 1 else cur

def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

def dump(e, ind=0):
    if isinstance(e, list):
        if not e:
            return "()"
        simple = all(not isinstance(x, list) for x in e)
        if simple:
            return "(" + " ".join(dump(x) for x in e) + ")"
        head = []
        rest = []
        for i, x in enumerate(e):
            if isinstance(x, list):
                rest = e[i:]; break
            head.append(dump(x))
        pad = "  " * (ind + 1)
        return "(" + " ".join(head) + "".join("\n" + pad + dump(x, ind + 1) for x in rest) + "\n" + "  " * ind + ")"
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, bool):
        return "yes" if e else "no"
    if isinstance(e, (int, float)):
        return fmtnum(e)
    return q(e)

def fmtnum(v):
    if isinstance(v, int):
        return str(v)
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s == "-0" else s

def find(e, key):
    """First child list whose head == key."""
    for x in e:
        if isinstance(x, list) and x and x[0] == key:
            return x
    return None

def findall(e, key):
    return [x for x in e if isinstance(x, list) and x and x[0] == key]
