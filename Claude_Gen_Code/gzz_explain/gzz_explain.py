#!/usr/bin/env python3
"""
gzz_explain.py - explain a GZigZag "GZZ0" dimension file in plain English.

GZigZag (the ZigZag implementation behind demos such as "Adam's Royals")
stores a space as a folder of append-only journal files:

    d.1, d.2, d.cursor, d.masterdim, ...   one file per dimension
    CONTENT                                 the text of every cell

This script reads ONE such file and writes a human-readable text report:
what the file is, how it changed over time, and what its final state is
(the ranks of linked cells).  If a CONTENT file sits next to the input (or
is given with --content), cell IDs are shown together with their text.

File format, as inferred from the sample data and the GZigZag Java sources
(there is no official specification; see the notes at the end of each report):

    header   "GZZ0", 8-byte big-endian number, 4-byte number        (16 bytes)
    block    't', u32 stamp, u32 payload length, <operations>
    ops      'c'  <utf> a <utf> b     connect a -> b  (b is a's + neighbour)
             'd+' <utf> a             disconnect a from its + neighbour
             'd-' <utf> a             disconnect a from its - neighbour
             's'  <utf> id <utf> txt  set the text of cell id        (CONTENT)
    <utf>    u16 big-endian length + modified UTF-8 (Java writeUTF)

Usage:
    python gzz_explain.py d.2
    python gzz_explain.py d.cursor -o cursor_report.txt
    python gzz_explain.py d.1 --content /path/to/CONTENT --full
    python gzz_explain.py CONTENT

Requires only the Python 3.8+ standard library.
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
import os
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

MAGIC = b"GZZ0"
HEADER_SIZE = 16
WIDTH = 100

# --------------------------------------------------------------------------
# Glossary of dimension names.  Inferred from how the Java code uses them;
# nothing here is documented by the original authors.
# --------------------------------------------------------------------------
GLOSSARY: Dict[str, str] = {
    "d.1": "General-purpose dimension. By convention it carries values: the "
           "cells after a parameter name, or the rest of a 'row'.",
    "d.2": "General-purpose dimension. By convention the 'next item' / list "
           "dimension: property lists, menus and name lists run along it.",
    "d.3": "General-purpose dimension. By convention it links to a "
           "sub-structure; parameter lookup follows it to inherit values.",
    "d.clone": "Clone chains. Cells in one rank share the text of the rank's "
               "first cell (the 'root clone').",
    "d.cellcreation": "Creation order of cells. Not stored on disk; computed "
                      "from the numeric cell IDs.",
    "d.masterdim": "Registry of every dimension in the space. Each cell's "
                   "text is a dimension name; ranks run from the home cell.",
    "d.system": "System list hanging off the home cell: named cells such as "
                "Views, Bindings, Windows and ClientCell used by the program.",
    "d.cursor": "Links an 'accursed' cell (the one pointed at) to the cursor "
                "cell that points at it.",
    "d.cursor-list": "Chains several cursor cells that point at the same "
                     "accursed cell.",
    "d.cursor-cargo": "Attaches 'cargo' cells (typically windows/views) "
                      "behind a cursor cell; the cargo follows that cursor. "
                      "The cursor cell's text holds the text offset.",
    "d..cursor-trigger": "Links a cargo cell to a command cell that runs "
                         "when the cursor moves.",
    "d.view": "Chains the view (window) cells under the ClientCell.",
    "d.ctrlview": "Pairs a control view with the data view it controls.",
    "d.dims": "A view's list of dimensions to display (entries are pointers "
              "to cells whose text is a dimension name).",
    "d.mark": "A view's marked cells: relation cells chained here point at "
              "the marked cells via d.mark-set.",
    "d.mark-set": "Points from a mark relation cell to the marked cell.",
    "d.bind": "A window's current key-bindings mode (a cursor on a bindings "
              "cell).",
    "d.cellview": "Selects a per-cell display/edit-bindings override.",
    "d.xeq": "Flag dimension: a code cell with a d.xeq neighbour is run by "
             "the Flowing Clang interpreter instead of as a plain command.",
    "d.bounds": "A window's position and size as four number cells.",
    "d.color": "Colours for windows or modes, stored as cell text.",
    "d.photo": "URL of an image shown by the photo view.",
    "d.help": "Help text attached to a view cursor.",
    "d.slices": "Chains the home cells of slices (sub-spaces).",
    "d.gzz-space-version": "Links the home cell to a cell whose text is the "
                           "space-format version number.",
    "d.children": "Application-specific (meaning inferred from the name "
                  "only): parent-to-child relations.",
    "d.marriage": "Application-specific (meaning inferred from the name "
                  "only): marriage relations.",
    "d.date": "Application-specific (meaning inferred from the name only): "
              "links a cell to a date or year.",
}


class FormatError(Exception):
    """The file is not a readable GZZ0 journal."""


class Truncated(FormatError):
    pass


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------
@dataclass
class Op:
    kind: str                 # 'c', 'd+', 'd-', 's'
    a: str
    b: Optional[str] = None


@dataclass
class Block:
    stamp: int
    length: int
    offset: int
    ops: List[Op] = field(default_factory=list)
    damaged: bool = False


@dataclass
class Journal:
    path: str
    size: int
    tag: int
    reserved: int
    blocks: List[Block] = field(default_factory=list)
    error: Optional[str] = None


def decode_utf(raw: bytes) -> str:
    """Decode Java 'modified UTF-8' (as written by DataOutputStream.writeUTF)."""
    raw = raw.replace(b"\xc0\x80", b"\x00")
    try:
        s = raw.decode("utf-8", "surrogatepass")
        return s.encode("utf-16", "surrogatepass").decode("utf-16")
    except UnicodeError:
        return raw.decode("utf-8", "replace")


class Reader:
    def __init__(self, data: bytes, pos: int, end: int):
        self.data, self.pos, self.end = data, pos, end

    def take(self, n: int) -> bytes:
        if self.pos + n > self.end:
            raise Truncated(f"data ends unexpectedly at byte offset {self.pos}")
        chunk = self.data[self.pos:self.pos + n]
        self.pos += n
        return chunk

    def u8(self) -> int:
        return self.take(1)[0]

    def utf(self) -> str:
        n = struct.unpack(">H", self.take(2))[0]
        return decode_utf(self.take(n))


def parse_journal(path: str) -> Journal:
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < HEADER_SIZE:
        raise FormatError(f"file is only {len(data)} bytes; a GZZ0 header "
                          f"needs {HEADER_SIZE}")
    if data[:4] != MAGIC:
        raise FormatError(f"missing 'GZZ0' signature (file starts with "
                          f"{data[:4]!r}); this is not a GZigZag journal")
    tag, reserved = struct.unpack(">QI", data[4:HEADER_SIZE])
    j = Journal(path, len(data), tag, reserved)
    pos = HEADER_SIZE
    while pos < len(data):
        if data[pos:pos + 1] != b"t":
            j.error = (f"expected a block marker 't' at byte offset {pos} but "
                       f"found 0x{data[pos]:02x}; reading stopped there")
            break
        if pos + 9 > len(data):
            j.error = f"truncated block header at byte offset {pos}"
            break
        stamp, length = struct.unpack(">II", data[pos + 1:pos + 9])
        body, end = pos + 9, pos + 9 + length
        blk = Block(stamp, length, pos)
        if end > len(data):
            blk.damaged = True
            j.error = (f"block for stamp {stamp} claims {length} bytes but only "
                       f"{len(data) - body} remain (file truncated?)")
            end = len(data)
        r = Reader(data, body, end)
        try:
            while r.pos < r.end:
                code = chr(r.u8())
                if code == "c":
                    blk.ops.append(Op("c", r.utf(), r.utf()))
                elif code == "d":
                    sign = chr(r.u8())
                    if sign not in "+-":
                        raise FormatError(f"bad disconnect direction {sign!r} "
                                          f"at byte offset {r.pos - 1}")
                    blk.ops.append(Op("d" + sign, r.utf()))
                elif code == "s":
                    blk.ops.append(Op("s", r.utf(), r.utf()))
                else:
                    raise FormatError(f"unknown operation byte {code!r} at "
                                      f"byte offset {r.pos - 1}")
        except FormatError as e:
            blk.damaged = True
            j.error = f"in the block for stamp {stamp}: {e}"
        j.blocks.append(blk)
        if j.error:
            break
        pos = end
    return j


# --------------------------------------------------------------------------
# Link state (mirrors ZZLocalDimension: forward map + backward map)
# --------------------------------------------------------------------------
class Links:
    def __init__(self) -> None:
        self.cp: Dict[str, str] = {}      # cell -> its + neighbour
        self.cm: Dict[str, str] = {}      # cell -> its - neighbour

    def disconnect(self, c: str, direction: int) -> Optional[str]:
        if direction > 0:
            other = self.cp.pop(c, None)
            if other is not None:
                self.cm.pop(other, None)
        else:
            other = self.cm.pop(c, None)
            if other is not None:
                self.cp.pop(other, None)
        return other

    def connect(self, a: str, b: str):
        """Returns None if already connected, else (old_next, old_prev)."""
        if self.cp.get(a) == b:
            return None
        old_next = self.disconnect(a, 1)
        old_prev = self.disconnect(b, -1)
        self.cp[a], self.cm[b] = b, a
        return old_next, old_prev

    def consistent(self) -> bool:
        return (all(self.cm.get(b) == a for a, b in self.cp.items())
                and all(self.cp.get(a) == b for b, a in self.cm.items()))


def sort_key(cid: str):
    return (0, int(cid), "") if cid.isdigit() else (1, 0, cid)


def build_ranks(links: Links) -> List[Tuple[List[str], bool]]:
    """Split the links into ranks. Returns (cells, is_circular) pairs."""
    cells = set(links.cp) | set(links.cm) | set(links.cp.values()) \
        | set(links.cm.values())
    seen: set = set()
    ranks: List[Tuple[List[str], bool]] = []
    for head in sorted((c for c in cells if c in links.cp and c not in links.cm),
                       key=sort_key):
        chain, cur = [head], head
        seen.add(head)
        while cur in links.cp and links.cp[cur] not in seen:
            cur = links.cp[cur]
            chain.append(cur)
            seen.add(cur)
        ranks.append((chain, False))
    for start in sorted(cells - seen, key=sort_key):
        if start in seen:
            continue
        members, cur = [start], start
        seen.add(start)
        while cur in links.cp and links.cp[cur] not in seen:
            cur = links.cp[cur]
            members.append(cur)
            seen.add(cur)
        # The Java code names the lexically greatest ID the head of a loop.
        i = members.index(max(members))
        ranks.append((members[i:] + members[:i], True))
    return ranks


# --------------------------------------------------------------------------
# Formatting helpers
# --------------------------------------------------------------------------
def quote(text: str, width: int) -> str:
    s = json.dumps(text, ensure_ascii=False)
    return s if len(s) <= width else s[:width - 2] + "…\""


def fmt_ms(ms) -> str:
    try:
        d = dt.datetime.fromtimestamp(int(ms) / 1000, dt.timezone.utc)
        return d.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, OverflowError, OSError):
        return f"(invalid time {ms})"


def make_label(texts: Optional[Dict[str, str]], width: int) -> Callable[[str], str]:
    def label(cid: str) -> str:
        if texts is None:
            return f"#{cid}"
        t = texts.get(cid, "")
        return f"#{cid} {quote(t, width)}" if t != "" else f"#{cid} (empty)"
    return label


def rank_parts(chain: List[str], circular: bool, label, max_cells: int) -> List[str]:
    if len(chain) > max_cells:
        keep_end = 3
        keep_start = max_cells - keep_end
        parts = [label(c) for c in chain[:keep_start]]
        parts.append(f"… {len(chain) - max_cells} more cells …")
        parts += [label(c) for c in chain[-keep_end:]]
    else:
        parts = [label(c) for c in chain]
    if circular:
        parts.append("(back to the start)")
    return parts


def wrap_parts(parts: List[str], indent: str = "   ", sep: str = "  →  ") -> List[str]:
    """Join parts with arrows, wrapping only between parts."""
    lines, cur = [], indent
    for i, part in enumerate(parts):
        piece = part if i == 0 else sep.strip() + "  " + part
        if cur.strip() and len(cur) + 2 + len(piece) > WIDTH:
            lines.append(cur.rstrip())
            cur = indent + "   " + piece
        else:
            cur += ("" if not cur.strip() else "  ") + piece
    lines.append(cur.rstrip())
    return lines


class Out:
    def __init__(self) -> None:
        self.lines: List[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(text)

    def head(self, title: str) -> None:
        self.add()
        self.add("=" * WIDTH)
        self.add(title)
        self.add("=" * WIDTH)

    def para(self, text: str, indent: int = 0) -> None:
        import textwrap
        for line in textwrap.wrap(text, WIDTH - indent) or [""]:
            self.add(" " * indent + line)

    def bullet(self, text: str, indent: int = 2) -> None:
        import textwrap
        wrapped = textwrap.wrap(text, WIDTH - indent - 2)
        for i, line in enumerate(wrapped or [""]):
            self.add(" " * indent + ("- " if i == 0 else "  ") + line)


# --------------------------------------------------------------------------
# Content file (cell texts)
# --------------------------------------------------------------------------
@dataclass
class Content:
    path: str
    texts: Dict[str, str]
    saves: List[Tuple[int, int]]          # (stamp, epoch ms)


def load_content(path: str) -> Content:
    j = parse_journal(path)
    texts: Dict[str, str] = {}
    saves: List[Tuple[int, int]] = []
    for blk in j.blocks:
        for op in blk.ops:
            if op.kind == "s":
                texts[op.a] = op.b or ""
                if op.a == "savetime" and (op.b or "").isdigit():
                    saves.append((blk.stamp, int(op.b)))
    return Content(path, texts, saves)


def save_time_after(content: Optional[Content], stamp: int) -> Optional[int]:
    """The first recorded save time at or after the given stamp."""
    if not content or not content.saves:
        return None
    stamps = [s for s, _ in content.saves]
    i = bisect.bisect_left(stamps, stamp)
    return content.saves[i][1] if i < len(content.saves) else None


# --------------------------------------------------------------------------
# Report sections
# --------------------------------------------------------------------------
def describe_dimension(name: str) -> str:
    if name in GLOSSARY:
        return GLOSSARY[name]
    if ":" in name:
        return ("A dimension provided by a 'space part' (the prefix before the "
                "colon names the part), i.e. a virtual region of the space.")
    return ("Not a dimension this script recognises; it is probably "
            "application-specific. What it means depends on how the data uses it.")


def detect_kind(j: Journal, name: str) -> str:
    kinds = {("text" if op.kind == "s" else "links")
             for b in j.blocks for op in b.ops}
    if kinds == {"text"}:
        return "content"
    if kinds == {"links"}:
        return "dimension"
    if not kinds:
        return "content" if name.upper() == "CONTENT" else "dimension"
    return "mixed"


def section_overview(out: Out, j: Journal, name: str, kind: str,
                     content: Optional[Content]) -> None:
    out.head("1. WHAT THIS FILE IS")
    out.add(f"File        : {j.path}")
    out.add(f"Size        : {j.size} bytes")
    out.add(f"Signature   : GZZ0 (GZigZag journal)")
    out.add(f"Header      : format tag {j.tag}, reserved value {j.reserved}  "
            f"(meaning unknown; the sample files use 42 for dimension files "
            f"and 43 for CONTENT)")
    ops = Counter(op.kind for b in j.blocks for op in b.ops)
    stamps = [b.stamp for b in j.blocks]
    out.add(f"Blocks      : {len(j.blocks)}"
            + (f"  (stamps {stamps[0]} to {stamps[-1]})" if stamps else ""))
    if ops:
        names = {"c": "connect", "d+": "disconnect(+)", "d-": "disconnect(-)",
                 "s": "set-text"}
        out.add("Operations  : " + ", ".join(
            f"{names[k]}={ops[k]}" for k in ("c", "d+", "d-", "s") if ops[k]))
    out.add()
    if kind == "content":
        out.para("This is the CONTENT file. It does not store links; it stores "
                 "the text of the cells (and a few bookkeeping values) as "
                 "'set text' records, one block per timestamp.")
    elif kind == "dimension":
        out.para(f"This file stores the dimension '{name}'. A dimension "
                 "arranges cells into ranks: each cell has at most one neighbour "
                 "in the positive (+) direction and one in the negative (-) "
                 "direction, so cells form chains (or loops). The file is an "
                 "append-only journal of 'connect' and 'disconnect' records; "
                 "replaying it from the top gives the current links.")
        out.add()
        out.add(f"What '{name}' is for:")
        out.para(describe_dimension(name), 2)
        if content:
            out.add()
            out.para(f"Cell texts come from {content.path} ({len(content.texts)} "
                     "records), so cells are shown as  #ID \"text\".", 0)
        else:
            out.add()
            out.para("No CONTENT file was used, so cells are shown only by ID "
                     "(#329). Put the dimension file next to its CONTENT file, "
                     "or pass --content, to see the cell texts.")
    else:
        out.para("This file contains both link and text records, which is "
                 "unusual; both are explained below.")
    if j.error:
        out.add()
        out.para("WARNING - the file could not be read to the end: " + j.error
                 + ". Everything before that point is reported below.")


def section_timeline(out: Out, j: Journal, kind: str, label, content,
                     max_ops: int) -> Tuple[Links, Dict[str, str]]:
    out.head("2. HISTORY (one block per timestamp, in file order)")
    out.para("Each block is one saved change set, tagged with a stamp number. "
             "The stamp is shared by all files of a space, so the same stamp "
             "in different files belongs to the same user action. The first "
             "block of a file normally holds the whole initial state; later "
             "blocks are small incremental changes.")
    out.add()
    if not j.blocks:
        out.add("(no blocks: nothing was ever stored in this file)")
        return Links(), {}
    links = Links()
    texts: Dict[str, str] = {}
    for blk in j.blocks:
        lines: List[str] = []
        n = Counter()
        ordered = ([o for o in blk.ops if o.kind in ("d+", "d-")]
                   + [o for o in blk.ops if o.kind == "c"]
                   + [o for o in blk.ops if o.kind == "s"])
        for op in ordered:
            if op.kind in ("d+", "d-"):
                d = 1 if op.kind == "d+" else -1
                sign = "+" if d > 0 else "-"
                old = links.disconnect(op.a, d)
                if old is None:
                    lines.append(f"Unlink {label(op.a)}: it had no {sign} "
                                 f"neighbour, so nothing changed")
                    n["noop"] += 1
                else:
                    lines.append(f"Unlink {label(op.a)} from its {sign} "
                                 f"neighbour {label(old)}")
                    n["unlink"] += 1
            elif op.kind == "c":
                res = links.connect(op.a, op.b)
                if res is None:
                    lines.append(f"Link {label(op.a)}  →  {label(op.b)} "
                                 f"(already linked, no change)")
                    n["noop"] += 1
                else:
                    old_next, old_prev = res
                    extra = []
                    if old_next is not None:
                        extra.append(f"its old + neighbour {label(old_next)} "
                                     f"was detached")
                    if old_prev is not None:
                        extra.append(f"{label(op.b)}'s old - neighbour "
                                     f"{label(old_prev)} was detached")
                    lines.append(f"Link {label(op.a)}  →  {label(op.b)}"
                                 + (f"   ({'; '.join(extra)})" if extra else ""))
                    n["link"] += 1
            else:  # 's'
                old = texts.get(op.a)
                texts[op.a] = op.b or ""
                if op.a == "savetime":
                    lines.append(f"Save time recorded: {fmt_ms(op.b)}")
                    n["meta"] += 1
                elif op.a == "nextfreeid":
                    lines.append(f"Next free cell ID is now {op.b}"
                                 + (f" (was {old})" if old else ""))
                    n["meta"] += 1
                elif old is None:
                    lines.append(f"Set text of #{op.a} to {quote(op.b or '', 60)}")
                    n["text"] += 1
                else:
                    lines.append(f"Change text of #{op.a} from "
                                 f"{quote(old, 40)} to {quote(op.b or '', 40)}")
                    n["text"] += 1
        summary = ", ".join(f"{v} {k}" for k, v in n.items()) or "empty"
        when = save_time_after(content, blk.stamp)
        out.add(f"Stamp {blk.stamp}  -  {len(blk.ops)} operation(s): {summary}"
                + ("   [DAMAGED BLOCK]" if blk.damaged else ""))
        if when is not None and kind == "dimension":
            out.add(f"   first save recorded at or after this stamp: "
                    f"{fmt_ms(when)}")
        for line in lines[:max_ops]:
            out.add("   " + line)
        if len(lines) > max_ops:
            out.add(f"   … and {len(lines) - max_ops} more (use --full to "
                    f"list every operation)")
        out.add()
    return links, texts


def section_state(out: Out, links: Links, name: str, label, max_ranks: int,
                  max_cells: int, have_text: bool) -> List[Tuple[List[str], bool]]:
    out.head(f"3. CURRENT STATE OF '{name}' (after replaying every block)")
    if not links.cp and not links.cm:
        out.para("No cell is linked on this dimension. The dimension exists "
                 "(it is registered in the space) but holds no connections.")
        return []
    ranks = build_ranks(links)
    cells = len(set(links.cp) | set(links.cm))
    lin = sum(1 for _, c in ranks if not c)
    loops = len(ranks) - lin
    out.add(f"Linked cells  : {cells}")
    out.add(f"Ranks         : {len(ranks)}  ({lin} linear, {loops} circular)")
    out.add(f"Link records  : {len(links.cp)} (each is one 'A → B' link)")
    out.add(f"Consistent    : "
            f"{'yes' if links.consistent() else 'NO - forward/backward links disagree'}")
    hist = Counter(len(ch) for ch, _ in ranks)
    out.add("Rank lengths : " + ", ".join(
        f"{n} rank(s) of {l} cells" for l, n in sorted(hist.items())[:12])
        + (" …" if len(hist) > 12 else ""))
    out.add()
    out.para("A rank is a chain of cells; '→' points in the positive (+) "
             "direction. Ranks are listed longest first.")
    out.add()
    order = sorted(ranks, key=lambda r: (-len(r[0]), sort_key(r[0][0])))
    for i, (chain, circ) in enumerate(order[:max_ranks], 1):
        out.add(f"Rank {i} ({len(chain)} cells{', circular' if circ else ''}):")
        for line in wrap_parts(rank_parts(chain, circ, label, max_cells)):
            out.add(line)
    if len(order) > max_ranks:
        out.add()
        out.add(f"… {len(order) - max_ranks} more rank(s) not shown "
                f"(use --max-ranks N or --full)")
    return ranks


def section_special(out: Out, name: str, links: Links, ranks, label,
                    have_text: bool) -> None:
    notes: List[str] = []
    home_rank = next((ch for ch, _ in ranks if "1" in ch), None)
    if name in ("d.masterdim", "d.system") and home_rank:
        what = ("dimensions registered in this space" if name == "d.masterdim"
                else "system-list entries")
        notes.append(f"The rank through the home cell (#1) lists the {what}, "
                     f"in rank order:")
        for i, c in enumerate(home_rank, 1):
            notes.append(f"   {i:>3}. {label(c)}")
        if not have_text:
            notes.append("   (cell names need the CONTENT file)")
    elif name == "d.cursor":
        notes.append("Each rank reads: accursed cell (the one pointed at), "
                     "then the cursor cell that points at it:")
        for ch, _ in ranks[:40]:
            notes.append(f"   {label(ch[0])}   ←  pointed at by cursor "
                         + ", ".join(label(c) for c in ch[1:]))
        if len(ranks) > 40:
            notes.append(f"   … {len(ranks) - 40} more")
    elif name == "d.cursor-list":
        notes.append("Each rank is a group of cursor cells that point at the "
                     "same cell (the first is the one connected on d.cursor).")
    elif name == "d.cursor-cargo":
        notes.append("In each rank the first cell is a cursor cell and the "
                     "cells after it are its cargo (e.g. windows that follow "
                     "that cursor).")
    elif name == "d.gzz-space-version" and links.cp:
        a, b = next(iter(links.cp.items()))
        notes.append(f"{label(a)} is linked to {label(b)}; the text of the "
                     f"second cell is the space format version.")
    if notes:
        out.head(f"4. EXTRA READING NOTES FOR '{name}'")
        for n in notes:
            if n.startswith("   "):
                out.add(n)
            else:
                out.para(n)


def section_content(out: Out, j: Journal, texts: Dict[str, str],
                    max_texts: int, width: int) -> None:
    out.head("3. CURRENT STATE OF CELL TEXT (after replaying every block)")
    cells = {k: v for k, v in texts.items() if k.isdigit()}
    meta = {k: v for k, v in texts.items() if not k.isdigit()}
    out.add(f"Cells with a text record  : {len(cells)}")
    empty = sum(1 for v in cells.values() if v == "")
    out.add(f"   of which empty          : {empty}")
    if "nextfreeid" in meta:
        out.add(f"Next free cell ID        : {meta['nextfreeid']}  "
                f"(so IDs up to {int(meta['nextfreeid']) - 1} have been "
                f"allocated; cells with no record have empty text)"
                if meta["nextfreeid"].isdigit()
                else f"Next free cell ID        : {meta['nextfreeid']}")
    saves = [(b.stamp, op.b) for b in j.blocks for op in b.ops
             if op.kind == "s" and op.a == "savetime"]
    if saves:
        out.add(f"Save markers             : {len(saves)}  "
                f"(first {fmt_ms(saves[0][1])}, last {fmt_ms(saves[-1][1])})")
    other = [k for k in meta if k not in ("savetime", "nextfreeid")]
    if other:
        out.add("Other bookkeeping keys   : " + ", ".join(sorted(other)))
    out.add()
    out.add(f"Cell texts, by ID (first {max_texts}):")
    shown = sorted(cells, key=sort_key)[:max_texts]
    for cid in shown:
        out.add(f"   #{cid:<6} {quote(cells[cid], width)}")
    if len(cells) > len(shown):
        out.add(f"   … {len(cells) - len(shown)} more (use --max-texts N or --full)")
    history: Dict[str, List[Tuple[int, str]]] = {}
    for b in j.blocks:
        for op in b.ops:
            if op.kind == "s" and op.a.isdigit():
                history.setdefault(op.a, []).append((b.stamp, op.b or ""))
    changed = {k: h for k, h in history.items()
               if len({v for _, v in h}) > 1}
    if changed:
        out.add()
        out.add(f"Cells whose text changed over time ({len(changed)}):")
        for cid in sorted(changed, key=sort_key)[:15]:
            trail = "  →  ".join(f"{quote(v, 24)}@{s}" for s, v in changed[cid])
            out.add(f"   #{cid}: {trail}")
        if len(changed) > 15:
            out.add(f"   … {len(changed) - 15} more")


def section_notes(out: Out, kind: str) -> None:
    out.head("NOTES ON HOW TO TRUST THIS REPORT")
    notes = [
        "The file format is not documented. It was reverse-engineered from "
        "sample data and the GZigZag Java sources, then checked by replaying "
        "a complete sample space (every dimension file replayed without "
        "inconsistencies, and with identical results whichever order the "
        "records of a block are applied in). Treat the explanations as "
        "well-founded inference, not specification.",
    ]
    if kind != "content":
        notes += [
            "Inside a block the records are stored in hash-table order, not in "
            "the order the user made them. This script applies the "
            "disconnections of a block first and its connections second.",
            "A note such as 'its old + neighbour X was detached' describes "
            "one replay step; X may be linked elsewhere again later in the "
            "same block (this is how an insertion into a rank looks).",
            "'Positive' (+) is the direction of 'A → B'. For a circular rank "
            "the start is the cell with the lexically greatest ID, which "
            "matches how the Java code picks a loop's 'head'.",
            "Dimension meanings come from how the Java code uses each name; "
            "application-specific dimensions are guessed from their names.",
            "Save times are matched to stamps heuristically: the first "
            "'savetime' record at or after a block's stamp.",
        ]
    for n in notes:
        out.bullet(n)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def build_report(args) -> str:
    j = parse_journal(args.input)
    name = args.name or os.path.basename(args.input)
    kind = detect_kind(j, name)

    content: Optional[Content] = None
    if kind != "content" and not args.no_content:
        cpath = args.content or os.path.join(
            os.path.dirname(os.path.abspath(args.input)), "CONTENT")
        if os.path.isfile(cpath):
            try:
                content = load_content(cpath)
            except (FormatError, OSError) as e:
                print(f"warning: could not use {cpath}: {e}", file=sys.stderr)
        elif args.content:
            print(f"warning: --content file {cpath} not found", file=sys.stderr)

    big = 10 ** 9
    max_ops = big if args.full else args.max_ops
    max_ranks = big if args.full else args.max_ranks
    max_cells = big if args.full else args.max_cells_per_rank
    max_texts = big if args.full else args.max_texts

    label = make_label(content.texts if content else None, args.text_width)

    out = Out()
    out.add("GZigZag file report")
    out.add("-" * WIDTH)
    section_overview(out, j, name, kind, content)
    links, texts = section_timeline(out, j, kind, label, content, max_ops)
    if kind in ("dimension", "mixed"):
        ranks = section_state(out, links, name, label, max_ranks, max_cells,
                              content is not None)
        section_special(out, name, links, ranks, label, content is not None)
    if kind in ("content", "mixed"):
        section_content(out, j, texts, max_texts, args.text_width)
    section_notes(out, kind)
    return "\n".join(out.lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Explain a GZigZag GZZ0 dimension (or CONTENT) file in "
                    "plain English.")
    ap.add_argument("input", help="dimension file such as d.1, d.cursor, "
                                  "d.masterdim (or CONTENT)")
    ap.add_argument("-o", "--output",
                    help="output text file (default: <input name>.explained.txt "
                         "in the current directory; '-' prints to the screen)")
    ap.add_argument("--content", help="path to the CONTENT file (default: the "
                                      "file called CONTENT next to the input)")
    ap.add_argument("--no-content", action="store_true",
                    help="do not look up cell texts; show bare cell IDs")
    ap.add_argument("--name", help="dimension name (default: the file name)")
    ap.add_argument("--full", action="store_true",
                    help="do not truncate any listing")
    ap.add_argument("--max-ops", type=int, default=12,
                    help="operations listed per block (default 12)")
    ap.add_argument("--max-ranks", type=int, default=30,
                    help="ranks listed in the current state (default 30)")
    ap.add_argument("--max-cells-per-rank", type=int, default=20,
                    help="cells shown per rank before abbreviating (default 20)")
    ap.add_argument("--max-texts", type=int, default=60,
                    help="cell texts listed for CONTENT (default 60)")
    ap.add_argument("--text-width", type=int, default=40,
                    help="maximum characters of a cell's text shown (default 40)")
    args = ap.parse_args(argv)

    try:
        report = build_report(args)
    except FormatError as e:
        print(f"error: {args.input}: {e}", file=sys.stderr)
        return 2
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.output == "-":
        sys.stdout.write(report)
    else:
        path = args.output or (os.path.basename(args.input) + ".explained.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
