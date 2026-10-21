#!/usr/bin/env python3
"""Convert a comments JSON export into a markdown file showing threaded replies.

Usage:
    python comments_to_md.py input.json                # writes input.md
    python comments_to_md.py input.json -o out.md
    python comments_to_md.py a.json b.json c.json      # one .md per input

Expected format: {"comments": [...], "authors": {...}} where each comment has
id, author, createTime, replyParent, content (list of blocks), and optionally
targetPath. Replies are nested with ">" blockquotes using replyParent.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def fmt_time(ts):
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        return ts or "unknown time"


def block_text(block):
    """Return a block's text with Link annotations turned into markdown links."""
    text = block.get("text", "")
    spans = []
    for ann in block.get("annotations", []):
        if ann.get("type") == "Link" and ann.get("link"):
            for s, e in zip(ann.get("starts", []), ann.get("ends", [])):
                spans.append((s, e, ann["link"]))
    # apply right-to-left so earlier offsets stay valid
    for s, e, link in sorted(spans, reverse=True):
        text = f"{text[:s]}[{text[s:e]}]({link}){text[e:]}"
    return text.strip()


def flatten_content(items, depth=0):
    """Yield (depth, block_type, text) for content blocks, including nested children."""
    for item in items or []:
        block = item.get("block", {})
        text = block_text(block)
        if text:
            yield depth, block.get("type", "Paragraph"), text
        yield from flatten_content(item.get("children"), depth + 1)


def body_lines(comment):
    blocks = list(flatten_content(comment.get("content")))
    lines = []
    # If a comment is a short intro followed by short one-liners, show them as a list
    if len(blocks) > 3 and all(len(t) < 30 for _, _, t in blocks[1:]):
        lines += [blocks[0][2], ""]
        lines += [f"- {t}" for _, _, t in blocks[1:]]
        return lines
    for depth, btype, text in blocks:
        indent = "  " * depth
        if btype == "Heading":
            lines += [f"{indent}**{text}**", ""]
        elif depth:
            lines += [f"{indent}- {text}"]
        else:
            lines += [text, ""]
    while lines and lines[-1] == "":
        lines.pop()
    return lines


def quote(lines, depth):
    prefix = "> " * depth
    return [(prefix + l).rstrip() for l in lines]


def render(comment, children, authors, depth=0):
    name = authors.get(comment.get("author"), (comment.get("author") or "unknown")[:12])
    header = [f"**{name}** · {fmt_time(comment.get('createTime'))}", ""]
    out = quote(header + body_lines(comment) + [""], depth)
    for child in children.get(comment["id"], []):
        out += render(child, children, authors, depth + 1)
    return out


def convert(data):
    comments = sorted(data.get("comments", []), key=lambda c: c.get("createTime", ""))
    ids = {c["id"] for c in comments}
    authors = {}
    for key, info in (data.get("authors") or {}).items():
        authors[key] = (info.get("metadata") or {}).get("name") or key[:12]

    children, tops = {}, []
    for c in comments:
        parent = c.get("replyParent") or ""
        if parent and parent in ids:
            children.setdefault(parent, []).append(c)
        else:  # no parent, or parent missing from this file -> treat as thread start
            tops.append(c)

    targets = sorted({c.get("targetPath") for c in comments if c.get("targetPath")})
    md = ["# Comments" + (f": {targets[0]}" if len(targets) == 1 else ""), ""]
    if len(targets) > 1:
        md += ["Targets: " + ", ".join(f"`{t}`" for t in targets), ""]
    elif targets:
        md += [f"Target: `{targets[0]}`", ""]
    md += [f"{len(comments)} comments in {len(tops)} threads. Replies are nested with `>` blockquotes.",
           "", "---", ""]
    for i, top in enumerate(tops, 1):
        md += [f"## Thread {i}", ""] + render(top, children, authors) + ["---", ""]
    return "\n".join(md).rstrip() + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", type=Path, help="comment JSON file(s)")
    ap.add_argument("-o", "--output", type=Path, help="output path (only with a single input)")
    args = ap.parse_args()
    if args.output and len(args.inputs) > 1:
        ap.error("-o/--output can only be used with one input file")

    status = 0
    for path in args.inputs:
        try:
            md = convert(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            print(f"{path}: {exc}", file=sys.stderr)
            status = 1
            continue
        out = args.output or path.with_suffix(".md")
        out.write_text(md, encoding="utf-8")
        print(f"{path} -> {out}")
    return status


if __name__ == "__main__":
    sys.exit(main())
