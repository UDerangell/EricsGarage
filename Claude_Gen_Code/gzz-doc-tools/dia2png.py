#!/usr/bin/env python3
"""
dia2png.py - convert Dia diagram files (.dia) to PNG, without needing Dia.

Requires only Python 3.8+ and Pillow:   pip install pillow

Usage:
    python dia2png.py diagram.dia                 # -> diagram.png next to the input
    python dia2png.py a.dia b.dia c.dia           # several files at once
    python dia2png.py a.dia -o out/a.png          # explicit output file
    python dia2png.py *.dia -o out_dir/           # explicit output directory
    python dia2png.py a.dia --scale 60 --transparent

Handles both plain-XML and gzip-compressed .dia files (Dia normally saves
gzip), with or without the "dia:" XML namespace prefix.

Supported Dia objects (the "Standard" shape set):
    Box, Ellipse, Line, PolyLine, ZigZagLine, Polygon, BezierLine,
    Beziergon, Text, and Groups of these.
Anything else (UML, flowchart sheets, etc.) is skipped with a warning.
For full fidelity on exotic shapes, use Dia itself:  dia -t png file.dia
"""

import argparse
import gzip
import math
import os
import subprocess
import sys
import xml.etree.ElementTree as ET

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Tunables
# --------------------------------------------------------------------------
DEFAULT_PX_PER_CM = 40      # output resolution (Dia's own default is 20)
DEFAULT_MARGIN_CM = 0.5     # blank border around the drawing
SUPERSAMPLE = 4             # render at Nx and downsample for anti-aliasing
MAX_SUPERSAMPLED_PX = 20000 # reduce supersampling for huge diagrams
TEXT_ASCENT = 0.793         # fraction of text height above the baseline (Dia)
FONT_EM_FACTOR = 1.0        # font size (em) = Dia text height * this

# Dia line_style enum -> (on, off, on, off, ...) in cm at dashlength 1.0
DASH_PATTERNS = {
    0: None,                              # solid
    1: (0.5, 0.3),                        # dashed
    2: (0.5, 0.2, 0.1, 0.2),              # dash-dot
    3: (0.5, 0.2, 0.1, 0.2, 0.1, 0.2),    # dash-dot-dot
    4: (0.2, 0.2),                        # dotted
}

warned = set()


def warn(msg):
    if msg not in warned:
        warned.add(msg)
        print("warning: " + msg, file=sys.stderr)


# --------------------------------------------------------------------------
# XML helpers
# --------------------------------------------------------------------------
def tag(el):
    """Tag name without any namespace ('{ns}attribute' / 'dia:attribute')."""
    return el.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def attr_map(el):
    return {c.get("name"): c for c in el if tag(c) == "attribute"}


def _child(attr, *tags):
    if attr is None:
        return None
    for c in attr:
        if tag(c) in tags:
            return c
    return None


def parse_pt(s):
    x, y = s.split(",")
    return float(x), float(y)


def get_num(a, name, default):
    c = _child(a.get(name), "real", "int", "enum")
    return float(c.get("val")) if c is not None else default


def get_bool(a, name, default):
    c = _child(a.get(name), "boolean")
    return (c.get("val") == "true") if c is not None else default


def get_color(a, name, default):
    c = _child(a.get(name), "color")
    if c is None:
        return default
    v = c.get("val").lstrip("#")
    if len(v) == 3:
        v = "".join(ch * 2 for ch in v)
    return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))


def get_point(a, name, default=None):
    c = _child(a.get(name), "point")
    return parse_pt(c.get("val")) if c is not None else default


def get_points(a, name):
    el = a.get(name)
    if el is None:
        return []
    return [parse_pt(c.get("val")) for c in el if tag(c) == "point"]


def get_string(el):
    """Decode a Dia <string>#...#</string> value."""
    c = _child(el, "string")
    t = (c.text or "") if c is not None else ""
    if len(t) >= 2 and t.startswith("#") and t.endswith("#"):
        t = t[1:-1]
    out, i = [], 0
    while i < len(t):                      # Dia escapes only '\' and '#'
        if t[i] == "\\" and i + 1 < len(t) and t[i + 1] in "\\#":
            out.append(t[i + 1])
            i += 2
        else:
            out.append(t[i])
            i += 1
    return "".join(out)


# --------------------------------------------------------------------------
# Fonts
# --------------------------------------------------------------------------
_font_file_cache = {}
_font_cache = {}

_FALLBACK_FONTS = {
    "mono": ["DejaVuSansMono", "LiberationMono-Regular", "FreeMono", "Courier New"],
    "serif": ["DejaVuSerif", "LiberationSerif-Regular", "FreeSerif", "Times New Roman"],
    "sans": ["DejaVuSans", "LiberationSans-Regular", "FreeSans", "Arial"],
}


def _style_flags(name):
    n = name.lower()
    return ("bold" in n or "demi" in n), ("italic" in n or "oblique" in n)


def _family_class(name):
    n = name.lower()
    if n.startswith(("courier", "mono", "lucidatypewriter", "consolas")):
        return "mono"
    if n.startswith(("times", "serif", "palatino", "bookman", "century",
                     "new century", "georgia")):
        return "serif"
    return "sans"


def find_font_file(dia_name, override=None):
    if override:
        return override
    key = dia_name
    if key in _font_file_cache:
        return _font_file_cache[key]
    fam = _family_class(dia_name)
    bold, italic = _style_flags(dia_name)
    pattern = {"mono": "monospace", "serif": "serif", "sans": "sans-serif"}[fam]
    if bold:
        pattern += ":bold"
    if italic:
        pattern += ":italic"
    path = None
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pattern],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and os.path.exists(out.stdout.strip()):
            path = out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    if path is None:                       # no fontconfig: try Pillow's search
        for cand in _FALLBACK_FONTS[fam]:
            try:
                ImageFont.truetype(cand + ".ttf", 10)
                path = cand + ".ttf"
                break
            except OSError:
                continue
    _font_file_cache[key] = path
    return path


def get_font(dia_name, px, override=None):
    px = max(1, int(round(px)))
    path = find_font_file(dia_name, override)
    key = (path, px)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(path, px)
        except (OSError, TypeError):
            warn("no TrueType font found; falling back to Pillow's default font")
            try:
                _font_cache[key] = ImageFont.load_default(px)
            except TypeError:
                _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


# --------------------------------------------------------------------------
# Geometry helpers
# --------------------------------------------------------------------------
def flatten_bezier(pts, steps=32):
    """Dia bez_points: p0, then (c1, c2, p) triples -> list of points."""
    out = [pts[0]]
    for i in range(1, len(pts) - 2, 3):
        p0, c1, c2, p1 = out[-1], pts[i], pts[i + 1], pts[i + 2]
        for s in range(1, steps + 1):
            t = s / steps
            u = 1 - t
            out.append((
                u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p1[0],
                u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p1[1],
            ))
    return out


def direction(frm, to):
    dx, dy = to[0] - frm[0], to[1] - frm[1]
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else None


def end_direction(pts):
    """Unit vector pointing out of the last point of a polyline."""
    tip = pts[-1]
    for p in reversed(pts[:-1]):
        d = direction(p, tip)
        if d:
            return d
    return (1.0, 0.0)


def trim_end(pts, length):
    """Remove `length` of arc length from the end of a polyline."""
    pts = list(pts)
    remaining = length
    while len(pts) > 2:
        seg = math.dist(pts[-1], pts[-2])
        if seg <= remaining:
            remaining -= seg
            pts.pop()
        else:
            break
    if len(pts) >= 2:
        seg = math.dist(pts[-1], pts[-2])
        if seg > remaining + 1e-9:
            d = direction(pts[-2], pts[-1])
            pts[-1] = (pts[-1][0] - d[0] * remaining, pts[-1][1] - d[1] * remaining)
    return pts


def arrow_geometry(kind, tip, d, length, width):
    """
    Return a dict describing the arrow head, or None.
      poly:   polygon/polyline points
      filled: True -> filled with line colour, False -> filled with background
      open:   True -> just draw strokes (no polygon fill)
      circle: (cx, cy, r) instead of poly
      trim:   how much to shorten the line so it ends at the head's base
    """
    ux, uy = d
    nx, ny = -uy, ux
    base = (tip[0] - ux * length, tip[1] - uy * length)
    c1 = (base[0] + nx * width / 2, base[1] + ny * width / 2)
    c2 = (base[0] - nx * width / 2, base[1] - ny * width / 2)
    mid = (tip[0] - ux * length / 2, tip[1] - uy * length / 2)

    if kind == 1:                                   # open "lines" arrow
        return dict(poly=[c1, tip, c2], open=True, filled=False, trim=0)
    if kind in (2, 3):                              # triangle (hollow / filled)
        return dict(poly=[tip, c1, c2], filled=(kind == 3), trim=length)
    if kind in (4, 5):                              # diamond
        s1 = (mid[0] + nx * width / 2, mid[1] + ny * width / 2)
        s2 = (mid[0] - nx * width / 2, mid[1] - ny * width / 2)
        return dict(poly=[tip, s1, base, s2], filled=(kind == 5), trim=length)
    if kind in (22, 23):                            # concave (filled / blanked)
        notch = (base[0] + ux * length * 0.3, base[1] + uy * length * 0.3)
        return dict(poly=[tip, c1, notch, c2], filled=(kind == 22), trim=length)
    if kind in (8, 9, 13, 15):                      # ellipse / dot
        return dict(circle=(mid[0], mid[1], min(length, width) / 2),
                    filled=(kind in (8, 13)), trim=length)
    if kind in (16, 17):                            # box
        return dict(poly=[c1, (c1[0] + ux * length, c1[1] + uy * length),
                          (c2[0] + ux * length, c2[1] + uy * length), c2],
                    filled=(kind == 16), trim=length)
    warn("arrow type %d not supported; drawing a filled triangle" % kind)
    return dict(poly=[tip, c1, c2], filled=True, trim=length)


# --------------------------------------------------------------------------
# Parsing: .dia -> list of primitives (all coordinates in cm)
# --------------------------------------------------------------------------
def load_dia(path):
    with open(path, "rb") as f:
        raw = f.read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return ET.fromstring(raw)


def read_style(a, width_name="line_width", color_names=("line_colour", "line_color")):
    color = (0, 0, 0)
    for n in color_names:
        color = get_color(a, n, color)
    return dict(
        lw=get_num(a, width_name, 0.1),
        color=color,
        style=int(get_num(a, "line_style", 0)),
        dash=get_num(a, "dashlength", 1.0),
    )


def read_arrow(a, prefix):
    kind = int(get_num(a, prefix + "arrow", 0))
    if kind == 0:
        return None
    return (kind, get_num(a, prefix + "arrow_length", 0.8),
            get_num(a, prefix + "arrow_width", 0.8))


def object_to_prims(obj, bg, prims):
    typ = obj.get("type", "")
    a = attr_map(obj)

    if typ == "Standard - Box":
        x, y = get_point(a, "elem_corner")
        w, h = get_num(a, "elem_width", 0), get_num(a, "elem_height", 0)
        st = read_style(a, "border_width", ("border_color",))
        prims.append(dict(
            k="rect", x=x, y=y, w=w, h=h, radius=get_num(a, "corner_radius", 0),
            fill=get_color(a, "inner_color", (255, 255, 255))
            if get_bool(a, "show_background", True) else None, **st))

    elif typ == "Standard - Ellipse":
        x, y = get_point(a, "elem_corner")
        w, h = get_num(a, "elem_width", 0), get_num(a, "elem_height", 0)
        st = read_style(a, "border_width", ("border_color",))
        prims.append(dict(
            k="ellipse", x=x, y=y, w=w, h=h,
            fill=get_color(a, "inner_color", (255, 255, 255))
            if get_bool(a, "show_background", True) else None, **st))

    elif typ in ("Standard - Line", "Standard - PolyLine", "Standard - ZigZagLine",
                 "Standard - BezierLine"):
        if typ == "Standard - Line":
            pts = get_points(a, "conn_endpoints")
        elif typ == "Standard - PolyLine":
            pts = get_points(a, "poly_points")
        elif typ == "Standard - ZigZagLine":
            pts = get_points(a, "orth_points")
        else:
            pts = flatten_bezier(get_points(a, "bez_points"))
        if len(pts) >= 2:
            prims.append(dict(k="path", pts=pts, closed=False, fill=None,
                              start_arrow=read_arrow(a, "start_"),
                              end_arrow=read_arrow(a, "end_"),
                              bg=bg, **read_style(a)))

    elif typ in ("Standard - Polygon", "Standard - Beziergon"):
        if typ == "Standard - Polygon":
            pts = get_points(a, "poly_points")
        else:
            pts = flatten_bezier(get_points(a, "bez_points"))
        if len(pts) >= 3:
            st = read_style(a, "line_width", ("line_colour", "line_color"))
            prims.append(dict(
                k="path", pts=pts, closed=True, start_arrow=None, end_arrow=None, bg=bg,
                fill=get_color(a, "inner_color", (255, 255, 255))
                if get_bool(a, "show_background", True) else None, **st))

    elif typ == "Standard - Text":
        comp = _child(a.get("text"), "composite")
        if comp is not None:
            t = attr_map(comp)
            text = get_string(t.get("string"))
            fnt = _child(t.get("font"), "font")
            prims.append(dict(
                k="text", lines=text.split("\n"),
                pos=get_point(t, "pos", get_point(a, "obj_pos", (0, 0))),
                h=get_num(t, "height", 0.8),
                align=int(get_num(t, "alignment", 0)),
                color=get_color(t, "color", (0, 0, 0)),
                font=fnt.get("name") if fnt is not None else "Helvetica"))
    else:
        warn("skipping unsupported object type %r" % typ)


def collect_prims(root):
    bg = (255, 255, 255)
    dd = _child_by_tag(root, "diagramdata")
    if dd is not None:
        bg = get_color(attr_map(dd), "background", bg)

    prims = []

    def walk(parent):
        for el in parent:
            t = tag(el)
            if t == "object":
                if el.get("type") == "Group":
                    for g in el:
                        if tag(g) == "group":
                            walk(g)
                else:
                    object_to_prims(el, bg, prims)

    for layer in root:
        if tag(layer) == "layer" and layer.get("visible", "true") != "false":
            walk(layer)
    return bg, prims


def _child_by_tag(el, name):
    for c in el:
        if tag(c) == name:
            return c
    return None


# --------------------------------------------------------------------------
# Bounds
# --------------------------------------------------------------------------
def text_extent_cm(p, probe_px=100, font_override=None):
    """Return (x0, y0, x1, y1) of a text primitive in cm."""
    font = get_font(p["font"], probe_px, font_override)
    em_cm = p["h"] * FONT_EM_FACTOR
    k = em_cm / probe_px
    widths = [font.getlength(l) * k for l in p["lines"]]
    w = max(widths) if widths else 0
    x, y = p["pos"]
    if p["align"] == 1:
        x0 = x - w / 2
    elif p["align"] == 2:
        x0 = x - w
    else:
        x0 = x
    y0 = y - TEXT_ASCENT * p["h"]
    return x0, y0, x0 + w, y0 + p["h"] * len(p["lines"])


def prim_bounds(p, font_override):
    if p["k"] in ("rect", "ellipse"):
        pad = p["lw"] / 2
        return (p["x"] - pad, p["y"] - pad, p["x"] + p["w"] + pad, p["y"] + p["h"] + pad)
    if p["k"] == "path":
        xs = [q[0] for q in p["pts"]]
        ys = [q[1] for q in p["pts"]]
        pad = p["lw"] / 2
        for ar in (p["start_arrow"], p["end_arrow"]):
            if ar:
                pad = max(pad, ar[1], ar[2])    # generous: covers any head
        return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)
    return text_extent_cm(p, font_override=font_override)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
class Renderer:
    def __init__(self, width, height, minx, miny, scale, bg, transparent, font_override):
        self.S = scale
        self.minx, self.miny = minx, miny
        self.font_override = font_override
        self.bg = bg
        if transparent:
            self.img = Image.new("RGBA", (width, height), bg + (0,))
        else:
            self.img = Image.new("RGB", (width, height), bg)
        self.d = ImageDraw.Draw(self.img)

    # coordinate transforms
    def P(self, p):
        return ((p[0] - self.minx) * self.S, (p[1] - self.miny) * self.S)

    def L(self, cm):
        return cm * self.S

    def lw(self, cm):
        return max(1, int(round(cm * self.S)))

    # strokes
    def stroke(self, pts_cm, lw_cm, color, style, dashlen, closed=False):
        pts = [self.P(p) for p in pts_cm]
        if closed:
            pts = pts + [pts[0]]
        w = self.lw(lw_cm)
        pattern = DASH_PATTERNS.get(style)
        if not pattern:
            self.d.line(pts, fill=color, width=w, joint="curve")
            return
        pat = [max(0.5, v * dashlen * self.S) for v in pattern]
        for piece in self._dash(pts, pat):
            self.d.line(piece, fill=color, width=w)

    @staticmethod
    def _dash(pts, pat):
        pieces, cur = [], [pts[0]]
        idx, left, on = 0, pat[0], True
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            if seg < 1e-9:
                continue
            pos = 0.0
            while seg - pos > left:
                pos += left
                t = pos / seg
                pt = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                if on:
                    cur.append(pt)
                    pieces.append(cur)
                    cur = []
                else:
                    cur = [pt]
                on = not on
                idx = (idx + 1) % len(pat)
                left = pat[idx]
            left -= seg - pos
            if on:
                cur.append(b)
        if on and len(cur) > 1:
            pieces.append(cur)
        return pieces

    # primitives
    def draw(self, p):
        k = p["k"]
        if k == "rect":
            self.rect(p)
        elif k == "ellipse":
            self.ellipse(p)
        elif k == "path":
            self.path(p)
        elif k == "text":
            self.text(p)

    def rect(self, p):
        x0, y0 = self.P((p["x"], p["y"]))
        x1, y1 = self.P((p["x"] + p["w"], p["y"] + p["h"]))
        r = self.L(p["radius"])
        w = self.lw(p["lw"])
        if p["fill"] is not None:
            if r > 0:
                self.d.rounded_rectangle((x0, y0, x1, y1), r, fill=p["fill"])
            else:
                self.d.rectangle((x0, y0, x1, y1), fill=p["fill"])
        if p["style"] == 0:
            box = (x0 - w / 2, y0 - w / 2, x1 + w / 2, y1 + w / 2)
            if r > 0:
                self.d.rounded_rectangle(box, r + w / 2, outline=p["color"], width=w)
            else:
                self.d.rectangle(box, outline=p["color"], width=w)
        else:
            pts = [(p["x"], p["y"]), (p["x"] + p["w"], p["y"]),
                   (p["x"] + p["w"], p["y"] + p["h"]), (p["x"], p["y"] + p["h"])]
            self.stroke(pts, p["lw"], p["color"], p["style"], p["dash"], closed=True)

    def ellipse(self, p):
        x0, y0 = self.P((p["x"], p["y"]))
        x1, y1 = self.P((p["x"] + p["w"], p["y"] + p["h"]))
        if p["fill"] is not None:
            self.d.ellipse((x0, y0, x1, y1), fill=p["fill"])
        cx, cy = p["x"] + p["w"] / 2, p["y"] + p["h"] / 2
        pts = [(cx + p["w"] / 2 * math.cos(2 * math.pi * i / 180),
                cy + p["h"] / 2 * math.sin(2 * math.pi * i / 180)) for i in range(180)]
        self.stroke(pts, p["lw"], p["color"], p["style"], p["dash"], closed=True)

    def path(self, p):
        pts = list(p["pts"])
        if p["fill"] is not None and p["closed"]:
            self.d.polygon([self.P(q) for q in pts], fill=p["fill"])

        heads = []
        for arrow, at_end in ((p["start_arrow"], False), (p["end_arrow"], True)):
            if not arrow:
                continue
            kind, length, width = arrow
            seq = pts if at_end else pts[::-1]
            geo = arrow_geometry(kind, seq[-1], end_direction(seq), length, width)
            heads.append(geo)
            if geo["trim"] > 0 and not p["closed"]:
                seq = trim_end(seq, geo["trim"])
                pts = seq if at_end else seq[::-1]

        self.stroke(pts, p["lw"], p["color"], p["style"], p["dash"], closed=p["closed"])

        w = self.lw(p["lw"])
        for geo in heads:
            fill = p["color"] if geo.get("filled") else self.bg
            if "circle" in geo:
                cx, cy, r = geo["circle"]
                (px, py), rr = self.P((cx, cy)), self.L(r)
                self.d.ellipse((px - rr, py - rr, px + rr, py + rr),
                               fill=fill, outline=p["color"], width=w)
            elif geo.get("open"):
                self.d.line([self.P(q) for q in geo["poly"]], fill=p["color"],
                            width=w, joint="curve")
            else:
                poly = [self.P(q) for q in geo["poly"]]
                self.d.polygon(poly, fill=fill)
                self.d.line(poly + [poly[0]], fill=p["color"], width=w, joint="curve")

    def text(self, p):
        font = get_font(p["font"], self.L(p["h"] * FONT_EM_FACTOR), self.font_override)
        x, y = p["pos"]
        anchor = {0: "ls", 1: "ms", 2: "rs"}.get(p["align"], "ls")
        for i, line in enumerate(p["lines"]):
            if line:
                self.d.text(self.P((x, y + i * p["h"])), line, font=font,
                            fill=p["color"], anchor=anchor)


# --------------------------------------------------------------------------
# Top-level conversion
# --------------------------------------------------------------------------
def convert(src, dst, px_per_cm=DEFAULT_PX_PER_CM, margin=DEFAULT_MARGIN_CM,
            background=None, transparent=False, font=None):
    root = load_dia(src)
    bg, prims = collect_prims(root)
    if background is not None:
        bg = background
    if not prims:
        raise ValueError("nothing to draw (empty or fully unsupported diagram)")

    boxes = [prim_bounds(p, font) for p in prims]
    minx = min(b[0] for b in boxes) - margin
    miny = min(b[1] for b in boxes) - margin
    maxx = max(b[2] for b in boxes) + margin
    maxy = max(b[3] for b in boxes) + margin

    ss = SUPERSAMPLE
    while ss > 1 and max(maxx - minx, maxy - miny) * px_per_cm * ss > MAX_SUPERSAMPLED_PX:
        ss -= 1
    S = px_per_cm * ss
    out_w = max(1, int(math.ceil((maxx - minx) * px_per_cm)))
    out_h = max(1, int(math.ceil((maxy - miny) * px_per_cm)))

    r = Renderer(out_w * ss, out_h * ss, minx, miny, S, bg, transparent, font)
    for p in prims:
        r.draw(p)

    img = r.img if ss == 1 else r.img.resize((out_w, out_h), Image.LANCZOS)
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    img.save(dst, "PNG")
    return out_w, out_h


def parse_color_arg(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) != 6:
        raise argparse.ArgumentTypeError("colour must look like #rrggbb")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert Dia (.dia) diagrams to PNG.")
    ap.add_argument("inputs", nargs="+", help=".dia file(s)")
    ap.add_argument("-o", "--output",
                    help="output .png (single input) or output directory (ends with / "
                         "or already exists). Default: next to each input.")
    ap.add_argument("-s", "--scale", type=float, default=DEFAULT_PX_PER_CM,
                    help="pixels per cm (default %(default)s)")
    ap.add_argument("-m", "--margin", type=float, default=DEFAULT_MARGIN_CM,
                    help="margin around the drawing in cm (default %(default)s)")
    ap.add_argument("-b", "--background", type=parse_color_arg,
                    help="override background colour, e.g. '#ffffff'")
    ap.add_argument("-t", "--transparent", action="store_true",
                    help="transparent background")
    ap.add_argument("--font", help="path to a .ttf/.otf to use for ALL text")
    args = ap.parse_args(argv)

    out_is_dir = bool(args.output) and (args.output.endswith(("/", os.sep))
                                        or os.path.isdir(args.output))
    if args.output and len(args.inputs) > 1 and not out_is_dir:
        ap.error("with several inputs, -o must be a directory")

    failures = 0
    for src in args.inputs:
        stem = os.path.splitext(os.path.basename(src))[0] + ".png"
        if args.output and out_is_dir:
            dst = os.path.join(args.output, stem)
        elif args.output:
            dst = args.output
        else:
            dst = os.path.join(os.path.dirname(src), stem)
        try:
            w, h = convert(src, dst, args.scale, args.margin, args.background,
                           args.transparent, args.font)
            print("%s -> %s (%dx%d)" % (src, dst, w, h))
        except Exception as e:  # keep going with the remaining files
            failures += 1
            print("error: %s: %s" % (src, e), file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
