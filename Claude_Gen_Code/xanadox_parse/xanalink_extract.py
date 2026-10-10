#!/usr/bin/env python3
"""Extract the text a .xanalink file points to and write it as Markdown.

Xanalink format (as seen in the XanaduSpace "Origins" demo data):

    TYPE = CLASH
    ENDSET 1
    http:XXX/MoeJusteSources/5-KingJamesBible.txt
    START = 3989
    LENGTH = 374
    ENDSET 2
    http:XXX/MoeJusteSources/2-DarwinDescentOfMan.txt
    START = 91228
    LENGTH = 203

START is a 0-based byte offset into the source file, and LENGTH is a byte
count. The source file is located by the last path component of the URL, so
put the source texts in --sources (default: the xanalink's own directory).

Usage:
    python xanalink_extract.py MoeJuste1_6.xanalink
    python xanalink_extract.py links/*.xanalink -s sources/ -o out/
    python xanalink_extract.py links/ -s sources/ --combined all_links.md
"""
import argparse
import sys
from pathlib import Path
from urllib.parse import unquote


# ---------------------------------------------------------------- parsing --

def parse_xanalink(path):
    """Return (link_type, endsets).

    endsets is a list of dicts: {"num": int, "source": str, "spans": [(start, length), ...]}
    An endset may hold several START/LENGTH pairs; each pair after a source
    line belongs to that source.
    """
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    link_type = None
    endsets = []
    cur = None
    pending_start = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        upper = line.upper()
        if upper.startswith("TYPE"):
            link_type = line.split("=", 1)[1].strip() if "=" in line else line[4:].strip()
        elif upper.startswith("ENDSET"):
            parts = line.split()
            num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else len(endsets) + 1
            cur = {"num": num, "source": None, "spans": []}
            endsets.append(cur)
            pending_start = None
        elif upper.startswith("START"):
            pending_start = int(line.split("=", 1)[1])
        elif upper.startswith("LENGTH"):
            if cur is None or pending_start is None:
                raise ValueError(f"{path}: LENGTH without START/ENDSET: {line!r}")
            cur["spans"].append((pending_start, int(line.split("=", 1)[1])))
            pending_start = None
        elif cur is not None and cur["source"] is None:
            cur["source"] = line          # the source URL / path line
        else:
            print(f"warning: {path}: ignoring unrecognised line {line!r}", file=sys.stderr)
    return link_type, endsets


# ------------------------------------------------------------- extraction --

def find_source(url, search_dirs):
    name = unquote(url.replace("\\", "/").rstrip("/").split("/")[-1])
    for d in search_dirs:
        cand = Path(d) / name
        if cand.is_file():
            return cand
    # case-insensitive fallback
    for d in search_dirs:
        if Path(d).is_dir():
            for p in Path(d).iterdir():
                if p.name.lower() == name.lower():
                    return p
    return None


def decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", errors="replace")


def extract(src_path, start, length):
    data = Path(src_path).read_bytes()
    if start < 0 or start + length > len(data):
        raise ValueError(
            f"span {start}+{length} is outside {src_path} ({len(data)} bytes)")
    return decode(data[start:start + length]).replace("\r\n", "\n").replace("\r", "\n")


def blockquote(text):
    return "\n".join(("> " + l).rstrip() if l.strip() else ">" for l in text.split("\n"))


def render(xanalink_path, source_dirs):
    """Return (markdown, problems) for one xanalink."""
    link_type, endsets = parse_xanalink(xanalink_path)
    problems = []
    out = [f"# Text pointed to by {Path(xanalink_path).name}", ""]
    if link_type:
        out += [f"**Link type:** {link_type}", ""]
    out += ["Offsets are 0-based byte positions; line endings converted to LF.", ""]

    for es in endsets:
        out += [f"## Endset {es['num']}", ""]
        if not es["source"]:
            problems.append(f"endset {es['num']} has no source")
            out += ["*(no source given)*", ""]
            continue
        src = find_source(es["source"], source_dirs)
        label = es["source"].replace("http:XXX/", "")
        if src is None:
            problems.append(f"source not found: {es['source']}")
            out += [f"Source: `{label}`", "", "*(source file not found)*", ""]
            continue
        for start, length in es["spans"]:
            out += [f"Source: `{label}` (start {start}, length {length})", ""]
            try:
                out += [blockquote(extract(src, start, length)), ""]
            except ValueError as e:
                problems.append(str(e))
                out += [f"*({e})*", ""]
    return "\n".join(out), problems


# -------------------------------------------------------------------- CLI --

def collect_inputs(paths):
    files = []
    for p in map(Path, paths):
        if p.is_dir():
            files += sorted(p.glob("*.xanalink"))
        else:
            files.append(p)
    return files


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help=".xanalink files and/or directories of them")
    ap.add_argument("-s", "--sources", action="append",
                    help="directory holding the source texts (repeatable; "
                         "default: each xanalink's own directory)")
    ap.add_argument("-o", "--outdir",
                    help="write one <name>.md per xanalink into this directory "
                         "(default: print to stdout)")
    ap.add_argument("--combined", help="write all results into this single .md file")
    args = ap.parse_args()

    files = collect_inputs(args.inputs)
    if not files:
        sys.exit("no .xanalink files found")
    if args.outdir:
        Path(args.outdir).mkdir(parents=True, exist_ok=True)

    results, failed = [], 0
    for f in files:
        dirs = args.sources or [str(Path(f).parent)]
        try:
            md, problems = render(f, dirs)
        except Exception as e:                       # keep going on bad files
            print(f"error: {f}: {e}", file=sys.stderr)
            failed += 1
            continue
        for p in problems:
            print(f"warning: {f}: {p}", file=sys.stderr)
        failed += bool(problems)
        results.append((f, md))
        if args.outdir:
            (Path(args.outdir) / (Path(f).stem + ".md")).write_text(md, encoding="utf-8")

    if args.combined:
        Path(args.combined).write_text("\n\n---\n\n".join(m for _, m in results),
                                       encoding="utf-8")
    elif not args.outdir:
        print("\n\n---\n\n".join(m for _, m in results))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
