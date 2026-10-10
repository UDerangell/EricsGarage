# Interpreting Xanadu zzz file format

**Exported with:** [AI Chat Exporter](https://ai-chat-exporter.covai.org)  
**Source:** Claude  
**Date:** 10/10/2026, 7:25:09 AM  
**Link:** [https://claude.ai/chat/34b9b28b-07bf-449a-924f-318c1861e4cd?artifact=cd6f45f5-9eb2-4bc7-ac31-869c04736dcc](https://claude.ai/chat/34b9b28b-07bf-449a-924f-318c1861e4cd?artifact=cd6f45f5-9eb2-4bc7-ac31-869c04736dcc)  
**Model:** claude-sonnet-5-5  
**Method:** API  

## Prompt:
The attached files are from Ted Nelson's Xanadu Space demo, named XuspMinMin18.05.12.  Can you interpret the file format of the zzz files?  TestEDL is an edit-decision list that points to characters in "Test Permascroll.txt"

## Response:
Parsing the zzz key/value structure and checking how the dimension links and the EDL map to the permascroll; continuing now.

The zzz files are a plain-text dump of a ZigZag-style cell store: a list of key/value records that hold every cell's content and every link between cells. All of this comes from reading the files, since I have no spec for XuspMinMin, so the "meaning" notes below are inferences.

## Record format

Every record is two lines with CRLF endings:

```
KEY=<cell address>
VAL=<value>
```

There are two kinds of record, distinguished by the key.

**Cell content**
```
KEY=2|Test Slice
VAL=slab
```
- The key is `<number>|<slice name>`, so a cell address is a number plus the slice it lives in. Slice names match the filename (`0.db`, `scene`, `style`, `tempslice`, `Test Slice`, and so on).
- The value is the cell's text. An empty `VAL=` is still a real cell, usually a structural or "head" cell.
- Newlines inside values are escaped as `^n`. A cell can hold a whole paragraph block, and in `Test_Slice.zzz` some hold several thousand characters.
- Text outside ASCII is Windows-1252: 0x97 is an em dash, 0x96 an en dash, and 0xE2/0xEA/0xFB are â/ê/û.

**Link**
```
KEY=37|Test Slice+d.text
VAL=38|Test Slice
```
- The key is `<cell>` + `+` or `-` + `d.<dimension>`, and the value is the neighbor cell's address.
- `+` means the positive neighbor along that dimension and `-` the negative one.
- Every link is stored twice, once from each end. In `Test_Slice.zzz` and `scrippleslice.zzz`, all 7,508 and 3,338 links have a matching reverse link. That is exactly the doubly-linked structure ZigZag uses.
- Dimension names are free-form. Numbered ones (`d.1`, `d.2`, `d.3`) coexist with named ones (`d.clone`, `d.cursor`, `d.text`, `d.color`, `d.size`, `d.translate`, `d.center`, `d.parentcenter`, `d.points`, `d.mastershape`, `d.representstype`, `d.flowposition`, `d.relativeposition`, `d.fontsize`, `d.fontcolor`, `d.font`).
- Links can cross slices. In `00_db.zzz`, `1|00.db-d.1` points to `10201|0.db`. In `tempslice.zzz`, `3090|tempslice-d.clone` points to `241|0.db`.
- The `d.clone` dimension looks like the clone/reference mechanism, with many cells in one slice pointing at cells in another. `scene.zzz` is almost nothing but clones into `tempslice`, and `tempslice` clones into `0.db`.
- A few clone links are one-directional, with no reverse record. That happens in `style.zzz` (19 cases) and `0_db.zzz` (92), always where a clone points into another slice.

## What the content encodes

Reading the cell values gives you the scene graph and the text.

- **Rank layout.** A header cell (say `27`) is followed along a dimension by its attribute cells. The `d.size`, `d.color`, `d.representstype` and `d.flowposition` links hang off cell 27, which holds `slab`.
- **Shape and style values.** Cells hold things like `slab`, `point`, `tetroid`, `trianglestrip`, and numbers such as `0`, `1`, `0.2`, `0.5`. Those are shape names and size/color/position components, with one component per cell along `d.size`, `d.color` and so on.
- **Text objects.** A `d.text` link from a shape's flow-position cell leads to cells holding text. In `Test_Slice.zzz`, `37+d.text → 38`, and cell 38 starts with `ORIGINS^n^nHow did all this get here?`, which is the start of the permascroll.
- **Scripts.** `0_db.zzz` has cells like `#0.db^nzz.slice_unload("0.db");^n`. A leading `#` followed by a slice name and code looks like an executable cell, here one that unloads a slice.
- **Dimension registry.** `old_0_db.zzz` and `0_db.zzz` list the dimension names as cell values (`d.texture`, `d.continuity`, `d.inside`, `d.cursor`, …). The `0.db` slice appears to be the home slice that names the dimensions.

## File by file

| File | Role |
|---|---|
| `0_db`, `Copy_of_0_db`, `bad_0_db`, `old_0_db`, `old2_0_db` | Variants and backups of the home database. `old_0_db` and `old2_0_db` are earlier, simpler ones. `bad_0_db` has about 1,200 cells and only 37 links. |
| `00_db`, `undo_db` | Tiny slices. `undo_db` holds cells whose `d.2` links point into `0.db`, which fits an undo journal. |
| `scene`, `tempslice`, `testscene` | Scene cells that are almost entirely `d.clone` references. `testscene` has one empty cell. |
| `style` | A style palette: `slab` plus ranks of numbers along `size`, `center`, `parentcenter`, `color` and `translate`. |
| `Test_Slice` (539 KB), `scrippleslice` | Full scenes. `Test_Slice` carries the text blocks, shapes and positions, and `scrippleslice` is mostly `translate`, `color` and `points`. |
| `scene.txt` | A text copy of the same KEY/VAL format as `scene.zzz`, not prose. |

## Test_EDL and the permascroll

`Test_EDL` is a separate, simpler format with two kinds of block.

```
$0
(,,Test Permascroll,0,9348)
```
- This is a numbered span block. The tuple appears to be `(, , document, start offset, length)`, with the first two fields empty. The four spans are 0+9348, 9348+5363, 14711+16728 and 31439+10000, so they tile the first 41,439 bytes of the permascroll with no gaps. That fits a document made by concatenating spans of the permascroll.

```
¢blue
from (,,Test Permascroll,535,209)
to   (,,Test Permascroll,9616,349)
```
- This is a typed link. The type, with a leading 0xA2 byte, is `blue`, and the `from` and `to` ends are spans.
- The three links chain, because each `to` becomes the next `from`: 535→9616→24377→40362.
- I checked the offsets against `Test_Permascroll.txt`, and they are byte offsets from 0.
- The first span, 535, falls mid-sentence in the opening essay, and the next three land at a Hawking quote, a Gilgamesh passage and a Genesis passage. That matches a link joining thematically related passages.

The permascroll itself is one CRLF-delimited text of about 60 KB. It mixes an "Origins" essay, Gilgamesh and Genesis, and it uses Windows-1252 for its few non-ASCII characters.

## Caveats and next steps

- The meaning of some numeric cell values (positions, the `points` ranks, `relativeposition`) is my guess from context.
- Where a key has a link but no reverse link, I treated the missing side as an unrecorded half rather than an error.

If it would help, I can write a parser that loads a slice into a cell/dimension graph and prints a rank, or one that resolves an EDL span to its permascroll text. I could also try to reconstruct the scene geometry in `Test_Slice.zzz`.

## Prompt:
Can you annotate the permascroll text to indicate the character positions referenced in the EDL?

## Response:
I've annotated the full 60,530-character permascroll with the positions from Test_EDL and published it as a page: https://claude.ai/artifact/AWRUpMjGxMNwQ4PQihpqmW

**What it shows**
- **EDL spans.** The four spans `$0`–`$3` are tinted bands, each with a start and end marker showing its offset. They tile bytes 0–41,438 with no gaps, and the last 19,091 characters (offset 41,439 onward) aren't referenced.
- **Link endpoints.** The three "blue" links have four distinct ranges, highlighted in yellow and bracketed with offsets. Each link's "to" is the next link's "from", so I labeled the ranges A to D.
- **Offset ticks.** Small gray numbers appear every 1,000 characters so you can orient yourself in the text.

| Range | Offset, length | Role | Where it starts and ends |
|---|---|---|---|
| A | 535, 209 | Link 1 from | in `$0`, starting "entific progress and with the…" and ending "…also greater than eve" |
| B | 9616, 349 | Link 1 to / Link 2 from | in `$1`, starting at the Hawking passage "d energy was created at one in…" |
| C | 24377, 286 | Link 2 to / Link 3 from | in `$2`, starting at the "56. The strong [man]…" line of the Gilgamesh flood story |
| D | 40362, 581 | Link 3 to | in `$3`, starting at "he knowledge of good and evil…" in Genesis |

Each endpoint falls in a different span. I treated EDL offsets as 0-based positions, and the text at each position matches the passages above, so I'm confident that reading is right. The file is CRLF with a few Windows-1252 characters, and because each is one byte, byte and character offsets are the same.

The page follows your light or dark setting. The generated file is also at `/mnt/user-data/outputs/annotated_permascroll.html`, and I can make a plain-text version with inline markers if you want one.

## Prompt:
What is the function of the scene.txt file?

## Response:
`scene.txt` is a full dump of the `scene` slice, which holds the layout of the 3D scene the demo draws. I was wrong earlier to call it a copy of `scene.zzz`: it has the same KEY/VAL format, but it's a different and much larger snapshot, and I've now read its contents.

## What it contains

`scene.txt` has 1,761 records, which come to 409 cells (numbered 1–409) plus their links. `scene.zzz` has only 36 records. The cells follow a repeating pattern of objects built from small groups of cells.

- **Shape cells.** The values `line` (50), `tetroid` (30), `slab` (29) and `spacer` (15) look like shape types. Each cell sits in a rank along `d.mastershape` that names the shape. Other `d.2` links tie the cells of an object together.
- **Geometry.** The 50 `d.points` ranks line up with the 50 `line` shapes, so each `line` has a set of point cells. Most of the numeric values are the point and size numbers.
- **Text objects.** About 30 objects have a `d.text` link to a text cell, and each such object also has a `d.represents` / `d.representstype` link. That fits "a tetroid that stands for a block of text".
- **Positioning.** About 15 objects have `d.flowposition` and `d.relativeposition` links, which chain objects into a flowing layout (cell 1 heads that structure).
- **Clones.** The 436 `d.clone` links (234 `+`, 202 `-`) tie scene cells together or point out to `style`, `0.db`, and `00.db`. This is how scene objects pick up shared styles and the home database.
- **System cells.** Cells such as `Cursor Home`, `Menu`, `Selection`, `Loaded`, `Lock Home`, `Recycle pile`, `#DimsTop`, `#Undo stack` and `#Redo stack` each appear six times. I think these are system home cells that other slices clone, but I haven't confirmed that.

## How it relates to scene.zzz

The two share cell numbers. For example, 393, 10 and 207 exist in both, which accounts for 22 of the 36 keys in `scene.zzz`. In `scene.txt` those cells are ordinary scene objects, while in `scene.zzz` they are empty cells whose `d.clone` points into `tempslice`.

That looks like two states of the same slice: `scene.txt` before the objects became references into `tempslice`, and `scene.zzz` after. I can't tell from the files which is older. Under that reading, `scene.txt` is probably a backup or an earlier export with the `.txt` extension, though I can't confirm that from the data.

If it would help, I can reconstruct the scene as a tree, with each shape, its points and its text, and compare the cell numbers shared by `scene.txt` and `scene.zzz` to see what changed.

## Prompt:
Please list all dimension names you have found and their probable function in the data structure or system code.

## Response:
I found 20 dimension names used in actual link records across the 16 files, and 17 more that are only registered by name. Everything below about function is inferred from how the dimensions are used. I have no spec or source code for the system.

Counts are link records, so each link counts twice, once as `+` and once as `-`. A dimension appears in a key as `…±d.<name>`, and the registry cells in `0.db` hold the same names as values, such as `d.size`.

## Dimensions used in links

| Dimension | Records | Where | Probable function |
|---|---|---|---|
| `2` | 2,885 | everywhere | The main structural axis. In scenes it chains an object's header cell to its attribute ranks and to sibling objects, and in `0_db` it lists cells. In `undo_db` the `d.2` links point into `0.db`, which fits an undo journal. |
| `1` | 383 | `0_db`, `Copy_of_0_db`, `00_db` | A general-purpose ZigZag axis, used for the home structure in `0.db`. In `00_db` it ties `00.db` cells to cells in `0.db`. |
| `3` | 36 | `0_db`, `Copy_of_0_db` | A third general axis. In `0_db`, cells 9000–9059 pair up along it. I can't tell what the pairs mean. |
| `clone` | 1,744 | most files | The clone dimension: one cell stands for another's content. It crosses slices (`scene` → `tempslice` → `0.db`, `style` → `tempslice`) and holds the template or reference relationships. |
| `cursor` | 8 | `0_db` | A rank of cursor cells (`Cursor Home` → `Menu` → `Event`), probably the cursor or focus structure. |
| `text` | 266 | `Test_Slice`, `scene.txt`, `0_db` | Links a scene object to the cell holding the text it displays. |
| `font` | 4 | `style` | The font name for text objects, a style attribute. |
| `fontsize` | 408 | `Test_Slice`, `style` | Text size. |
| `fontcolor` | 16 | `style` | Text color. |
| `flowposition` | 56 | `Test_Slice`, `scene.txt`, `0_db` | Links text objects into a flow, so text lays out one block after another. |
| `relativeposition` | 254 | `Test_Slice`, `scene.txt` | Places an object relative to another object (e.g. cell 1 → 14 → 292). |
| `mastershape` | 968 | `Test_Slice`, `scene.txt`, `style` | Points at a master shape template (`line`, `tetroid`, `slab`, `spacer`, `point`, `trianglestrip`) that an object instantiates. |
| `points` | 1,068 | `Test_Slice`, `scrippleslice`, `scene.txt` | The vertex or coordinate cells for a shape, such as the points of a `line` or `trianglestrip`. |
| `represents` | 140 | `scene.txt` only | Links a 3D object back to the data cell it stands for, as in "this object draws that cell". |
| `representstype` | 406 | `Test_Slice`, `scene.txt` | The kind of representation the object uses, with values like `slab` or `tetroid`. |
| `size` | 106 | five files | An object's dimensions, probably x, y and z values along a rank. |
| `color` | 3,798 | `Test_Slice`, `scrippleslice`, `style` | Color components, the most heavily used attribute (possibly RGB or RGBA). |
| `translate` | 1,500 | `Test_Slice`, `scrippleslice`, `style` | The offset of an object from its parent. It dominates `scrippleslice` (1,326 records), which looks like a drawing or "scribble" file. |
| `center` | 56 | `Test_Slice`, `style` | The object's own center point, used as the origin for transforms. |
| `parentcenter` | 144 | `style` (122), `Test_Slice` | The parent's center point for transforms, mostly in styles. |

## Names registered but not used in any link

These appear as values in the `0.db` registry (`d.*` cells in `0_db.zzz` and `old_0_db.zzz`) with no link records in these files. The functions below are guesses from the names.

| Name | Probable function |
|---|---|
| `continuity` | The first registered entry, in cell 0. It may relate to ordering or time continuity of objects, but I don't know. |
| `4` | A fourth general axis, reserved. |
| `inside`, `contents` | Containment: an object's enclosing cell and its contents. |
| `mark` | Marking or selection, probably related to the `Selection` home cell. |
| `texture`, `singlesided` | Rendering properties: surface texture and one-sided drawing. |
| `relativesize` | Size relative to a parent or reference. |
| `rotate`, `parentrotate` | Orientation of an object and its parent. |
| `globalmatrix`, `globalrotate`, `globaltranslate`, `globalsize` | World-space values computed from the local ones. |
| `screenposition`, `currentposition` | Where the object is on screen, and its current layout position. |
| `reverse` | Probably reverses a direction (it sits beside `screenposition` in the registry). |

## Patterns in the data

- The names fall into groups: general axes (1–4, `2` doing most of the work), structure (`clone`, `inside`, `contents`, `mark`, `cursor`), and a large visual and scene group.
- The visual group splits into local transforms (`translate`, `center`, `parentcenter`, `rotate`, `size`), shape (`mastershape`, `points`, `representstype`), layout (`flowposition`, `relativeposition`) and style (`color`, `font*`).
- The `global*` names look like cached world-space results of those local values, which would explain why they're registered but never stored as links.
- The `0.db` registry also has operational cells that aren't dimensions: `Autosave`, `Export`/`Import`, `Gzz XML`, `Gzz ASCII Dump`, `KBWheel` and others. The `#` cells hold small scripts. That mix suggests `0.db` is both the registry and the system's control surface, but I haven't looked closely at those cells.

I can pull the numeric values stored along `color`, `translate` and `size` to check whether they really are RGB and x/y/z triples.

## Prompt:
Please do web research to find out if source code for this application is available, or if people have documented how it works.  It ran in OpenGL under Windows only.

## Response:
I found no public source code for XanaduSpace, but I did find some documentation, and it supports several things I inferred from your files.

## Source code

- Nelson's own page calls XanaduSpace a "stuck demo" that can't be developed further. It says the package combined Python, C++, numerous libraries, OpenGL for the 3D view, ZigZag as internal storage for document parts and connections, and the Zzogl viewer for animation, and that it became too tangled to improve.
- The same page says John Ohno and Jonathan Kopetz spent several years trying to refactor it but concluded it was beyond fixing. I found no repository from that effort.
- Your files appear to come from the Internet Archive item `XuspMinMin18.05.12`. It's listed as a 3.7 MB zip, designed by Ted Nelson and programmed by Rob Smith, copyrighted by Hypercoin LLC with all rights reserved, for demonstration only. I couldn't see inside the zip. Because the app was partly Python, it might contain readable scripts, which is worth checking.
- The open-source Xanadu code is something else. Udanax Green is the 1988-era C server, with a Python demo client called Pyxi, so it covers the backend and not this viewer.

## Documentation

- **Origins data package.** The Internet Archive item `xanadox` holds the files needed to replicate the XanaduSpace demo: an EDL file, an ODL file, xanalink files, source files and a unifying directory. Its sources include the Gilgamesh and King James Bible texts, which is the material your permascroll is made from. It's the best place to see an EDL alongside its real source files.
- **Videos.** The archive item says Nelson's "Xanadu Basics 2" video explains the internal complexities, and it links a separate directions video.
- **Nelson's essay.** His essay "Toward a Deep Electronic Literature" credits Robert Adamson Smith as lead programmer and describes the 3D views of document interconnection, but it says nothing of the zzz format.
- **Developer comments.** The most useful account is an informal comment by enkiv2 (the GitHub name of John Ohno) on Lobsters. He says XanaduSpace used ordinary files, rendering `.edl` and `.xanadoc` files and importing links from `.odl` files. He also says link types are freeform strings, with unrecognized ones used to pick a highlight color. That matches the "blue" type in your EDL.
- **ZigZag in the display.** The same comment says XanaduSpace used ZigZag to model the display, that three incompatible scripting systems for ZigZag were built, and that later implementations dropped Zzogl. This fits the shape, color and transform dimensions in your slices.

## Gaps

I found no published description of the `.zzz` format or the dimension names. A Hacker News comment mentions a ZigZag implementation called GZigZag on SourceForge, and a repository by enkiv2 called `ix` implements a zzstructure editor, but I haven't checked whether either shares your files' conventions. The cells named "Gzz XML" and "Gzz ASCII Dump" in `0.db` hint at a connection to the Gzz project. The most promising next steps are the GZigZag project and asking enkiv2 directly.

## Prompt:
Here are 2 documents from the xanadox project referenced earlier from Wikipedia, and a xanalink file that references them.  Can you extract the text pointed to by the xanalink into a markdown file?

## Response:
I extracted both spans into `MoeJuste1_6_xanalink_text.md`.

The xanalink is a "CLASH" link between two passages:

- **Endset 1** is King James Bible Genesis 1:26–27 (start 3989, length 374), the passage about God making man in his own image.
- **Endset 2** is Darwin's *Descent of Man* (start 91228, length 203), a passage saying we should admit our "community of descent" from other animals, or else accept that our structure is a mere snare laid to entrap our judgment.

Both spans line up with the text, so the offsets are 0-based byte positions and the files' CRLF line endings count as two bytes each. In the markdown I converted those to plain line breaks. The Darwin span starts and ends mid-sentence, and the Bible span runs from the start of verse 26 to the end of verse 27.

The "CLASH" type matches the pairing: a creation text set against an evolution text. This is the same kind of link as the "blue" links in your EDL, with the link type as a freeform label.

## Prompt:
Can you write a Python script that will perform this process for other xanalink files?

## Response:
I wrote `xanalink_extract.py`, a standard-library Python script, and tested it on `MoeJuste1_6.xanalink`. It reproduced the same two passages as the markdown file I made earlier.

**Usage**

```
python xanalink_extract.py MoeJuste1_6.xanalink
python xanalink_extract.py links/*.xanalink -s sources/ -o out/
python xanalink_extract.py links/ -s sources/ --combined all_links.md
```

- **Inputs:** one or more `.xanalink` files, or a directory, in which case every `*.xanalink` in it is processed.
- **Sources:** `-s` names the folder holding the source texts and can be repeated. By default the script looks next to each xanalink. It finds each source by the last part of the URL, so `http:XXX/MoeJusteSources/5-KingJamesBible.txt` becomes `5-KingJamesBible.txt`. Matching ignores case.
- **Output:** the default is stdout. `-o DIR` writes one `.md` per link, and `--combined FILE` writes everything into a single file.

**What it does**

- It reads `TYPE`, each `ENDSET`, its source line, and `START` and `LENGTH`.
- It slices the source file by bytes using the 0-based offsets that matched your files.
- It converts CRLF to LF and formats each span as a blockquote.
- It tries UTF-8 first and falls back to Windows-1252.

**Error handling**

Bad links don't stop a batch. A missing source file, a span past the end of a file, or a malformed line produces a warning on stderr, a note in the markdown, and a nonzero exit code, and the script moves on to the next file. I tested a missing source and an out-of-range span.

**Limitations**

- I've only seen one xanalink file, so the parser follows that layout. It also accepts several `START`/`LENGTH` pairs under one endset and any number of endsets, but I haven't tested those cases against real files.
- The script strips trailing spaces from quoted lines. That is why the Darwin passage no longer ends in two spaces, as it did in the first file I made by hand.
- It doesn't read `.edl` or `.odl` files. I can add an EDL mode that assembles the document from its spans, if that would help.

## Response:
> **Artifact: xanalink_extract**
```python
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
```

## Prompt:
Please do not write any code.  Imagine that the source text files were stored in IPFS and the xanadoc files were somehow converted to JSON.  What would be the procedure for extracting the segments of text for the 2 related segments from the 2 CIDs?

## Response:
Here is the procedure, assuming each source file was added to IPFS unmodified and the JSON link keeps the same fields as the xanalink.

## The JSON link

Each endset would carry a CID in place of the `http:XXX/...` path, along with the same start and length. The link type (CLASH) stays as it is.

The CIDs are only trustworthy if the files were added byte for byte, with their CRLF line endings intact. If a tool converted the line endings first, the CID would describe a different file and every offset after the first line break would be wrong.

## Procedure, for each of the two endsets

1. **Resolve the CID to a file.** If the CID points to a single file, use it directly. If it points to a directory, you also need the file name within it.

2. **Work out which blocks hold the span.** IPFS stores a large file as a tree of blocks. With default settings the leaves are 256 KiB (262,144 bytes) each, and the root node records the size of every child.
   - Here, King James Bible start 3989 and Darwin start 91228 both fall within the first 262,144 bytes. Each needs only the first leaf block.
   - A span that straddles a block boundary needs both neighbouring blocks. Neither of yours does, since the first ends at byte 4,362 and the second at byte 91,430.
   - Don't assume 256 KiB. If the files were added with a different chunk size or a content-defined chunker, read the sizes from the root node's child list instead.

3. **Fetch only what you need.** Request a byte range of the file rather than the whole thing. A gateway accepts an HTTP Range header, and an IPFS node can read from an offset for a given length. The files are 1.9 MB and 4.4 MB, so this saves most of the transfer. Remember that an HTTP range's end position is inclusive, so the range for the Bible span is `3989` through `4362`, not `4363`.

4. **Check the result.** The block fetch is verified by the IPFS hash, so the bytes are the right ones for that CID. Also confirm the returned length equals the stated length. A short return means the offset is out of range or the wrong file was resolved.

5. **Decode and tidy.** Decode as ASCII or UTF-8 (your files contain no bytes above 127), and only then convert CRLF to LF. Offsets are bytes, not characters, so decode after slicing and never slice a decoded string by those numbers.

6. **Assemble the output.** Pair the two segments under the link type, and cite each by its CID and offsets so the passage can be re-fetched later.

## Notes

- A CID names a whole file, not a range, so the offset and length must travel with it in the JSON. The span is not itself addressable.
- Because a CID can never change, the offsets stay valid forever. This is the permanence Xanadu wanted from its permascroll.
- You could add a hash of each expected excerpt to the JSON, so a reader can confirm they got the right text without trusting anyone.
- If you want the spans to be addressable on their own, you could add the excerpts as separate IPFS objects and link to those. That would lose the "points into the original" property, since the excerpts would be copies.

## Prompt:
How could a similar procedure extract a segment of an audio file stored in IPFS?

## Response:
The IPFS side is the same as for text: the CID names the whole file, and you fetch only the blocks containing the bytes you need. What changes is that a segment is usually defined in time, and time has to be translated into byte offsets using knowledge of the audio format.

## 1. Decide what the span means

An audio span in the link would naturally be a start time and a duration, in milliseconds or in samples. Samples are more precise and avoid rounding. A raw byte range is possible too, but it is fragile, because most audio bytes aren't playable on their own. A Xanadu developer's comment I found earlier mentions this idea: a span could carry its own type, so audio would use start and end times, an image a bounding box, and a video both.

## 2. Fetch the format's index

You first need a small part of the file that says where each moment lives. Fetch it with a byte-range request, which in IPFS touches only the first block or two. What this index looks like depends on the format.

- **WAV (uncompressed PCM).** The easiest case. The header gives sample rate, channels and bit depth, which fix the bytes per second. Byte offset = header size + time × bytes per second, with no index needed. Round to a whole sample frame.
- **MP3.** There is no real time index. For constant bitrate files you can estimate the byte position from the bitrate. For variable bitrate you need the Xing or VBRI table in the first frame, which is approximate. Landing exactly requires scanning frame headers near the estimate.
- **MP4 / M4A (AAC).** The index is in the `moov` box, which maps times to sample sizes and file offsets. It is often at the end of the file, so you may need to fetch the end first. In a fragmented MP4, the fragment index serves the same purpose.
- **Ogg (Vorbis, Opus).** Pages carry a time stamp called a granule position. You fetch a page near the estimate and bisect until you reach the start time.
- **FLAC.** A seek table in the metadata block lists sample numbers with byte offsets.

## 3. Convert times to a byte range, with margin

Because compressed formats work in frames, you usually start at the frame that contains the start time, not at the start time itself. Many codecs also need a little preceding audio to decode the first frame cleanly: MP3 has a bit reservoir and Opus has pre-roll. Fetch a bit extra at the front and trim later.

## 4. Fetch the blocks

The byte range maps to IPFS blocks exactly as in the text case, with default 256 KiB leaves. Audio is much larger than text, so partial fetching saves a lot. A minute of 128 kbps MP3 is about 1 MB, or four blocks. Use the root node's child sizes for the mapping if the file wasn't added with the default chunker.

## 5. Produce the segment

You have two choices.

- **Play only.** Hand the player the byte range and the format headers, and let it decode and seek to the exact start. This keeps everything referenced and loses nothing.
- **Export a clip.** Decode and trim to the exact sample boundaries, then re-encode or repackage. This is lossy for compressed formats, or needs a clean container for lossless ones. The result is a copy, not a reference.

## 6. Verify

The block hashes prove you got the right bytes for the CID. They do not prove the time position is right, which depends on you reading the index correctly. Check that the clip's duration matches the stated length, within a frame. You can also store a hash of the expected decoded samples in the link JSON, so anyone can confirm the excerpt.

## Alternative: segment the file in advance

If the audio will be cited often, store it as many short chunks, such as HLS or DASH segments, in an IPFS directory with a manifest. A time span then maps to a few CIDs, and no byte arithmetic is needed. The cost is that each chunk is a separate object and there is no single CID for the whole recording, unless the directory itself serves as that identifier.

## Prompt:
How could ffmpeg be used in the previous answer?

## Response:
ffmpeg and its companion tool ffprobe can do most of the format-specific work from the previous answer, so you don't have to parse the audio containers yourself. The main thing to decide is how ffmpeg gets at the IPFS data.

## Getting the file to ffmpeg

- **Through a gateway URL.** This is the best option. ffmpeg's HTTP input can seek using range requests if the server supports them, and gateways generally do. ffmpeg then reads only the parts it needs, and the gateway or node fetches only the matching IPFS blocks. This works for every format, including MP4 files whose index is at the end.
- **Piped from the IPFS command line.** ffmpeg can read from standard input, but that stream can't seek. It is fine for WAV or an MP3 you read from the start. It fails or has to read everything for formats that need a seek, such as MP4 with the `moov` box at the end.

Neither route makes ffmpeg verify the CID. The verification comes from the IPFS node. Use your own local node's gateway, so the bytes are hash-checked as they are fetched. A public gateway means trusting it.

## Step 2: reading the index

ffprobe replaces the hand parsing of headers. It reports the format, duration, sample rate, channels and bitrate. With its packet listing option, it also shows each audio packet's timestamp and byte position in the file. That is the time-to-byte map, built for you, and it lets you see exactly which IPFS blocks a span touches before you fetch any audio.

## Steps 3 to 5: cutting the segment

- **Seeking.** Put the start time before the input in the command. ffmpeg then uses the container's index to jump near the start and reads only from there. It also decodes a little earlier audio to warm up codecs like MP3 and Opus, which handles the pre-roll problem for you.
- **Duration.** Give the length with the duration option, or an end time. These map directly to your link's start and length, converted from milliseconds or samples into ffmpeg's time format.
- **Playback only.** If you just need to listen, you can skip the export entirely and let a player or ffplay seek the same URL.
- **Lossless cut.** Stream copy writes the original compressed packets into a new file with no re-encoding. It is fast and keeps the quality, but the cut falls on frame boundaries, so the start can be off by a frame or so. MP3 frames are about 26 ms. For WAV the cut can be exact.
- **Sample-exact cut.** Decoding and re-encoding gives precise boundaries, at the cost of a generation of loss for MP3, AAC or Opus. Exporting to WAV or FLAC avoids further loss, but the file gets much larger.

The exported clip is a new file. If you add it to IPFS it gets a new CID unrelated to the original, so the link JSON should keep pointing to the original CID plus the time span, not to the clip.

## Step 6: verifying

ffmpeg has hash and checksum output formats that can fingerprint the decoded samples of the clip. Storing that fingerprint in the link JSON would let anyone confirm they extracted the same audio.

There is one caveat. For lossy formats, different ffmpeg versions or decoders can produce slightly different samples from the same bytes, so the fingerprint is dependable only for lossless audio or a pinned ffmpeg version. A hash of the raw bytes you fetched is more stable.

## Pre-segmenting

If you want the pre-split approach from before, ffmpeg's HLS output can cut a recording into short segments with a playlist. You add that folder to IPFS, and a time span then maps to a few segment files. The cost, as noted earlier, is that the recording no longer has a single CID of its own, unless the folder serves as it.

## Prompt:
How can a xanalink be reified into a CID, and how can other xanalinks refer to xanalink CIDs?

## Response:
A xanalink is a small structured record, so it can be stored as an IPLD object (IPFS's linked-data layer) and get a CID like any other file. The harder questions are what goes inside the record and how you find links afterwards.

## Turning a link into a CID

1. **Parse into a structure.** The text format (`TYPE`, `ENDSET`, `START`, `LENGTH`) becomes a record. It has a type string and an ordered list of endsets, and each endset has a target and one or more spans.
2. **Replace paths with CIDs.** `http:XXX/MoeJusteSources/5-KingJamesBible.txt` becomes the CID of that file, as in your earlier IPFS scenario. In IPLD, a CID inside a record is written as a proper link, not a string, so tools can follow it.
3. **Serialize canonically.** Use DAG-CBOR, or DAG-JSON if you want readable text. Both fix the key order and number encoding, so the same logical link always produces the same bytes. If you used ordinary JSON with free ordering or whitespace, two identical links could get different CIDs.
4. **Add the record to IPFS.** The resulting CID is the link's identity.

Several consequences follow:

- **Identity.** Two people who write the same link get the same CID, so duplicates collapse. That is deliberate, but it means the CID can't tell you who made the link or when.
- **Authorship.** To record that, add a signature and a creator field. These change the CID, so decide whether you want links that are identical in meaning to share a CID or to differ by author. A common design is a small signed wrapper pointing at the unsigned link.
- **Immutability.** A link can't be edited. A corrected link is a new object, and it can point to the old one as the version it replaces.

## Referring to links from other links

Because a link has a CID, another link can use that CID as an endset target, in exactly the way it uses a file's CID. This gives you links about links: a link of type "disputes" or "supports", a retraction, a comment, or a link that endorses a whole set of links.

The target can carry a span or not. For a document the span selects text. When the target is a link, you would usually point at the whole link, though you could also point into one of its fields.

## Limits of content addressing

- **No cycles.** A link's CID is computed from the CIDs inside it, so it can never contain its own CID, and two links can't point at each other. Links form a directed acyclic graph. If you need a mutual reference, point at something stable, such as a name that resolves to the current version (IPNS or a similar naming layer), or use a third object that lists both.
- **Direction.** A link points from its endsets to their targets, but the target holds no record of the link. Xanadu's claim that links are visible from both ends needs an extra layer. Finding "every link that cites this document" requires an index, which has to be built and maintained, perhaps by an indexing service, a pubsub topic per CID, or a published collection.
- **Collections.** The nearest equivalent in your files is the overlay, the ODL file I saw mentioned earlier. You could model it as a list of link CIDs with its own CID. Switching overlays on and off then means choosing which collection CIDs to load.
- **Naming.** CIDs of the same file may differ by how it was chunked or encoded. Two parties who added the same text with different settings get different CIDs, so their links won't match up. Agreeing on one encoding for sources avoids this.

## What I would put in the record

The type string, the ordered endsets, each with a target CID and its spans, and the CID of any earlier version. Optionally add a hash of each excerpt for checking, the creator's signature, and a timestamp. The exact field names are a design choice, since no standard exists for this.

## Prompt:
please explain DAG-CBOR

## Response:
DAG-CBOR is a way of writing structured data as bytes so that the same data always produces exactly the same bytes. That property is what lets you hash the result and get a stable CID. It is one of the codecs of IPLD, IPFS's data model for linked records.

## Three layers

- **CBOR** (Concise Binary Object Representation) is a general binary format, standardized in RFC 8949. It covers the same kinds of data as JSON: numbers, strings, lists and key-value maps. It adds raw byte strings and a compact binary encoding.
- **IPLD data model** is the small set of types IPLD recognizes: null, booleans, integers, floats, strings, bytes, lists, maps, and links.
- **DAG-CBOR** is CBOR restricted to that data model and made strictly deterministic. The "DAG" refers to the fact that records link to each other by CID and form a directed acyclic graph.

## Why strictness matters

Ordinary CBOR, like JSON, can say the same thing in several ways. A number could be stored in different widths, map keys could appear in any order, and some lengths can be written in an indefinite form. If the bytes differ, the hash differs, and so does the CID. DAG-CBOR removes those choices.

- **Map keys** must be strings, with no duplicates, and sorted in a fixed order (by length first, then by byte value).
- **Integers** use the shortest encoding that fits.
- **Lengths** are always stated up front, and indefinite-length items are not allowed.
- **Floats** are always 64-bit, and NaN and infinity are forbidden because they have several bit patterns.
- **Only the IPLD types** are permitted, so CBOR features outside that model, such as arbitrary tags, don't appear.

The result is that one logical record has exactly one valid encoding, and a decoder can reject anything that isn't canonical.

## How links work

JSON has no native way to say "this value is a link to another object". DAG-CBOR uses a CBOR tag, number 42, wrapped around the CID's bytes. A reader that understands the tag knows to treat the value as a link to follow, instead of as a string or a blob. That is how a record can hold the CIDs of the source files, or of other links, in a way tools can traverse. In plain JSON a CID would just be a piece of text.

## Comparison with DAG-JSON

DAG-JSON is the readable sibling. It follows the same data model and the same strictness, with sorted keys and no insignificant whitespace, and writes a link as an object with a special key (`"/"`) holding the CID text. It is easier to inspect, but larger and slower to parse. The two formats describe the same data but give different CIDs, since the bytes differ. DAG-CBOR is the usual choice for storage and DAG-JSON for display and debugging.

## What this means for a xanalink

If you store a link as DAG-CBOR, the type string, the span numbers and the target CIDs are all encoded in one agreed form. Anyone reconstructing the same link gets the same bytes and therefore the same CID. A record with different key order, or with a number written differently, would no longer match the first one. Two things can still differ without the encoding being at fault: a different field in the data (a timestamp or signature) changes the CID, as discussed before.

A few limits are worth knowing. Integers are best kept to the 64-bit range for compatibility, and floats should be avoided when you can use whole numbers, which is another reason offsets and lengths work well as integers. There is also no built-in schema, so DAG-CBOR does not check that a record has the fields a xanalink needs. That validation has to come from a schema layer or from your own checks.

## Prompt:
What API operations would be useful for a spatial backend that retrieves a xanadoc and lazy loads xanalinks as they are requested?

## Response:
A spatial viewer like XanaduSpace has to draw a document at once and fill in its links only when the user looks at them. The backend should therefore expose cheap questions first and expensive ones later. Here are the operations I would want, grouped by what they do. The names are descriptive, not a standard.

## Document and text

- **Get document.** Given a document's CID or name, return its manifest: the ordered spans (source CID, start, length), total virtual length, version information, and the overlays it recommends. No text is included, so the client can lay out the scene immediately.
- **Get text range.** Given a document and a virtual range, return the assembled text plus a provenance map showing which source CID and offsets each piece came from. Allow several ranges per request, so the client can prefetch what's near the viewport.
- **Translate position.** Convert a virtual position to a source address (CID and offset), and the reverse. This is what lets a link's source-offset endpoints be drawn on the document.
- **Get source span.** Fetch text directly from a source CID, offset and length, with a context margin option, for showing a link's far end.

## Link discovery (without loading links)

Because content addressing only points forward, finding links needs an index, and these are the queries on it.

- **Count links.** For a document range, return how many links touch it, split by type. This drives badges and density cues cheaply.
- **Find links.** Given a document or source CID plus an optional span, return link CIDs with small summaries: type, number of endsets, and each endpoint's span. Support filters by type, creator, overlay and date, plus paging with a cursor. A viewport variant takes the visible virtual range.
- **Find occurrences.** Given a source span, list every document that includes it. This supports parallel pages and "show me where else this appears".
- **Find links about links.** Given a link CID, return the links that cite it.

## Link retrieval (the lazy part)

- **Get link.** Fetch one link record by CID, or several in a batch.
- **Resolve endpoints in context.** For a link and the current document, return where each endset falls in this document's virtual positions. A span may appear several times, partly, or not at all, so the response must say which.
- **Get endset text.** Return the text at one endset with a length limit and surrounding context.
- **Get neighbourhood.** Starting from a link or document, return the nearby graph to a stated depth, with a cap on size, for 3D layout without a fetch per node.

## Overlays

- **List overlays.** Available link collections for a document, with sizes.
- **Select overlays.** Turn collections on or off for a session, so every query above respects the choice. Links come from collections of link CIDs, so this is cheap.

## Media

- **Get media segment.** For audio or video, take a CID and a time span, and return the matching byte range or a clip, as described earlier.

## Writing and updates

- **Create link.** Submit a link, validate it, store it, and return its CID. A signed form should be an option.
- **Supersede or retract.** Create a new link that replaces or withdraws an old one, since existing links can't be edited.
- **Subscribe.** Notify the client when new links appear on a document or span.

## Cross-cutting behaviour

- **Immutable caching.** A CID never changes, so everything addressed by CID can be cached forever. Only the indexes and name lookups need freshness.
- **Tiered detail.** Counts first, then summaries, then endset text, then full documents. Requests should say which tier they want, to avoid over-fetching.
- **Batching and priority.** Allow several lookups in one call, and let the client mark nearby items as low priority so visible ones arrive first.
- **Partial results.** If a source isn't reachable or a span is out of range, return what was found plus a per-item status, not a single failure.
- **Verification.** Say whether bytes were checked against their CID, and optionally return expected excerpt hashes from the link.
- **Limits.** Cap sizes and depths on neighbourhood and range queries so a request can't ask for the whole docuverse.

The first group alone lets a client render a document. The discovery group is the one most worth getting right, because the visible-connections experience depends on it being fast.

## Prompt:
How can a user viewing a spatial flight of xanadocs add their own links in their personal zzstructures?

## Response:
This brings together several things from earlier: spans that resolve to source addresses, links as immutable objects, overlays, and the cells and dimensions seen in the zzz files. In the viewer, the user selects, names the link, and saves it into their own zzstructure. The structure holds the working copy, and the link also gets a permanent CID.

## 1. Selecting

The user marks a passage in a flown-to document, or in a link's far end. Documents in the viewer are virtual, assembled from spans, so the selection is a virtual range. The backend's "translate position" operation turns it into source addresses: one or more (source CID, start, length) triples. A selection that crosses the boundary between two spans of the document gives two spans, and a selection inside quoted material resolves to the original source, not to the document quoting it. The user can usually add more selections to form further endsets, or select an existing link or a whole document as a target.

## 2. Describing the link

The user types a link type, which is a free string as in your files ("blue", "CLASH"). They can add a note. The viewer previews the endsets, showing each excerpt as it would appear, so a bad selection is caught before saving.

## 3. Storing it in a personal zzstructure

A personal slice would hold the working record as cells, much as the slices you gave me hold scenes and styles.

- **A head cell** for the link. Along one dimension hang the type cell and the endset cells in order.
- **Endset cells** each carry the target CID with start and length, and cells that already exist for a document can be reused through the clone dimension instead of being copied.
- **Other dimensions** are the user's own. They can arrange links by topic, project, reading trail or date, and a link can sit on several of these at once through clones. That personal organization is the main advantage of using a zzstructure: the structure of the user's thinking is stored beside the links, and none of it changes the link itself.

An undo slice like `undo_db` suggests edits were already journaled, so drafts and changes can be reversed before anything is published.

## 4. Committing

When the user is happy, the record is converted into an immutable link object, with CIDs in place of paths, and stored. The resulting CID goes back into a cell of the user's structure. From then on the cell has two roles: the editable working form, and a pointer to the permanent version. If the user edits afterwards, the viewer makes a new link that supersedes the old CID, and the structure shows the newest. Signing is optional here, and it can be set per link.

## 5. Showing it immediately

Links the user made have to appear in the viewer at once. The personal slice acts as an overlay, a collection of link CIDs. The viewer merges it into the link queries, so the new link shows up beside other people's, in its own color or marker. Nobody else's index knows about it yet, so a small local index is needed for personal links, otherwise they would not appear when the user looks at the spans they cite.

## 6. Privacy and sharing

The user chooses per link or per collection.

- **Private.** The structure and index stay on the user's side. The link object can be stored locally and not announced.
- **Shared.** The user publishes the link CID, or a collection of them, to an index or a named overlay that others can subscribe to.

A published link can't be recalled, since the content is permanent. Retraction means publishing a newer link that withdraws it. Interface wording should make that clear before the user commits.

## Practical points

- **Missing sources.** A document whose sources have no CID can't have stable links. The viewer should say so and offer to add the source first.
- **Links to links.** The user can attach a comment or dispute to someone else's link by selecting it as a target.
- **Drafts.** Unfinished links stay as cells only. They have no CID until committed, so they never appear in another person's index.
- **Moving in space.** Where the user puts the link head cell in the 3D scene is layout data in the structure, separate from the link. The same link can appear in different places in different scenes.

The layout and dimension use above is my inference from the files you gave me. I have not seen how XanaduSpace itself saved user links.

## Prompt:
how does all this relate to Ted Nelson's concept of the Poomfilade?

## Response:
The POOMfilade is the part of Nelson's Xanadu design that your EDL, the assembled virtual document and my "translate position" operation all correspond to. I haven't read the Udanax Green source, so the description of the enfilades below comes from a Wikipedia summary. The mapping to your files and to the IPFS design is my own analysis.

## The three structures

Xanadu Green used several kinds of enfilade, a family of tree structures Nelson invented, to keep three things apart.

- **The POOMfilade.** This is a two-dimensional enfilade that maps a virtual position in a document to the istream positions of the pooled content the document is built from. In other words, it is the document, defined as a rearrangement of pieces of permanent content.
- **The Spanfilade.** This collects the union of all istream spans used by a document or set of documents. That makes it the means of finding which documents and links share a stretch of content.
- **The Granfilade.** This organizes the storage of all this information on disks and a network of servers.

The istream is the single permanent address space for content, and the vstream is the document as the reader sees it. The enfilades handle the two-way conversion between them. According to Wikipedia, enfilades and istream addresses were not exposed in Xanadu's external interfaces, and were trade secrets until the code was open-sourced in 1999.

## How your files line up

- **EDL as a serialized POOM.** Your `Test_EDL` lists spans of the permascroll in order, and that is the same content a POOMfilade holds: virtual order mapped to pieces of source text. A Lobsters comment from a developer who worked on later implementations says that in Udanax Green, assembled documents live in their own namespace (the POOMfilade), apart from the chunks of text (the source enfilade). The same comment says XanaSpace used ordinary files instead, rendering `.edl` and `.xanadoc` files and importing links from `.odl` files. So XanaduSpace flattened the POOM into a text file and replaced the tree with a list.
- **Permascroll as the istream.** The permascroll is the pooled content. The difference is that Green has one global address space, while your demo files address separate text files by name and byte offset.
- **Links.** In Green, link ends are istream spans, so a link attaches to content wherever it appears. Your xanalink works the same way, with spans in source files and nothing about any document that quotes them. This is why the same link shows up in every document that includes the passage.

## How the IPFS design compares

| Xanadu Green | The IPFS design I described |
|---|---|
| istream address | CID plus byte offset |
| POOMfilade | A document object: an ordered list of (CID, start, length) |
| Spanfilade | The link index I said would be needed, answering "which links touch this span?" |
| Granfilade | IPFS blocks, plus whatever distributes them |
| vstream ↔ istream conversion | The "translate position" operation, in both directions |

There are some real differences:

- **One address versus two numbers.** The istream gives every byte a single address. With CIDs you must carry the file's CID and an offset. A span that crosses two files needs two spans.
- **Mutability.** A POOM changes as the document is edited, and enfilades are designed so a middle insertion only updates a few widths and offsets along one path. A DAG-CBOR record is immutable, so an edit creates a new object. For a short document a flat list of spans is fine. For a long one you would want the list stored as a tree of chunks, so a new version reuses most of the old objects. That gets close to what enfilades give, and to the versioning enfilade Wikipedia calls the ent.
- **Where the index lives.** Green's spanfilade is part of the server and always current. In the IPFS design, the index is a separate service, and its completeness depends on who publishes links to it.
- **Two dimensions.** The POOM is described as two-dimensional, so it can represent content moved around, duplicated, or in several documents at once. A list of spans does the same job for text, but it doesn't offer the same structure for questions like "where did this piece go in the new version?"

## Personal zzstructures

In this picture the user's zzstructure is a separate client-side layer. It holds arrangement and personal organization of links, while the POOM-like object holds the document and the link objects hold meaning. As far as I can tell from your files, XanaduSpace itself used ZigZag only to store scene and display data, so using it for personal link organization goes beyond what I saw.

## Prompt:
How can a group of users reference each other's publicly shared zzstructures and have them rendered lazily as they explore the connections

## Response:
You can reuse most of the earlier design. The new problems are naming a slice that keeps changing, splitting it so you load only what you need, and deciding how much to trust what you load.

## Naming other people's slices

Your files already have cross-slice references, with cell addresses like `241|0.db` and `d.clone` links pointing from one slice into another. For public sharing the slice name has to be globally unique. Plain names like `scene` would collide between users, so a slice should be identified by its owner's key plus a name.

A zzstructure is also edited constantly, which makes it unlike a document. So each slice has two layers:

- **Snapshots.** An immutable version of the slice with its own CID.
- **A signed pointer.** A mutable name that always points to the owner's latest snapshot, verified by signature.

A reference to someone else's cell can then be either **floating** (owner, slice, cell number, resolved to the newest snapshot) or **pinned** (a specific snapshot CID plus cell number). Floating suits following a colleague's evolving work, and pinned suits citation.

One hazard comes from the files: `0.db` has a "Recycle pile" cell, which suggests deleted cells can be reused. If so, a floating reference might silently land on different content. Including a hash of the cell's content in the reference lets the viewer notice, and publishers could be asked never to reuse numbers in published slices.

## Storing a slice for lazy loading

Storing a slice as one blob wastes bandwidth when an explorer wants a few cells. Better:

- **Index by cell number** in a tree whose leaves hold small groups of cells, so a change rewrites only one path.
- **Group by locality.** Put cells that neighbour each other along a dimension in the same leaf. Navigation in a zzstructure follows ranks, so one fetch then tends to cover the next few steps.
- **Record each cell's neighbours as ids,** one for each direction and dimension. Within a snapshot the ids are plain numbers and not hashes, so the circular two-way links of a zzstructure cause no problem. This differs from xanalinks, where pointing from one CID to another can't form cycles.
- **Make cross-user neighbours names,** not CIDs: owner, slice and cell. That keeps them resolvable to the current snapshot and avoids baking one user's version into another's.

## Exploring lazily

The viewer shows a cell with its neighbours along the dimensions on screen. Following a connection then works in steps:

1. Resolve the foreign slice's pointer, check the signature, and fetch the index root.
2. Fetch the leaf holding the target cell, and from it the neighbours along the visible axes.
3. Draw placeholders for anything further out, and prefetch a step or two ahead along the axes the user is moving.
4. Mark each cell with whose slice it came from. Your keys already do this (`number|slice`), so ownership can be shown by color or position.

Long ranks should be loaded in windows, not completely. Ranks can also be rings, so the traversal needs a visited set. Peers that are offline give an "unavailable" placeholder and the rest renders normally.

## Meaning of foreign dimensions

Dimension names are free strings, so my `color` may not mean yours. A viewer should therefore:

- apply its own rules for the dimensions it recognizes (size, color, position) and treat the rest as ordinary navigable dimensions, and
- decide per slice whether to trust its display settings, or let the user override them.

## Safety

Your `0.db` contains cells starting with `#` that look like scripts, such as one that unloads a slice. Cells from other people's slices must never be executed. Treat them as data only. Also cap how many cells, how deep, and how large a fetch from an untrusted slice can be.

## Finding each other

- **A group directory.** A shared, signed list of members' slice pointers lets a group see each other's work and add people.
- **Back-references.** A pointer only goes forward. To show "who cites this cell", you need an index or a subscription, as with links.
- **Updates.** A per-slice notification channel lets viewers say "newer version available" without reloading.

## Caching

Snapshots are immutable, so cache their chunks permanently. Only pointers need refreshing. The viewer can show the cached version at once and swap in the new one as a background update.

## Privacy

Public means copyable. Anyone who has fetched a snapshot keeps it, so the owner can stop publishing updates but can't recall old ones. The viewer should say so before publishing.

## Prompt:
If we assume that personal documents are versioned and collaborators always link to specific versions, but it is possible to find newer versions by following supersede links, how does the data structure change?

## Response:
The main change is that the mutable name goes away. Everything becomes an immutable object, and "latest" stops being a fact stored anywhere and becomes something you compute from supersede links.

## What gets removed or changed

- **No signed pointer.** The owner no longer publishes "my slice now points to X". Each version is just a snapshot CID.
- **Every reference is pinned.** A reference is a snapshot CID plus a cell id. The floating form is gone, and so is the hash-of-cell check I suggested for guarding against reused cell numbers. Pinned references can't land on different content. Reuse of numbers does matter again when you follow a supersede link to a newer version, so a "recycled" cell there should be treated as a different cell.
- **Each version records its parent.** The snapshot holds the CID of the version it replaces. That's a backward pointer and is free.

## The supersede link as a separate object

The backward pointer is not enough, because exploring needs the forward direction: "is there anything newer than this?" A snapshot can't point to its own successor, since that successor didn't exist when its hash was computed. So the successor relationship is a separate link object in the style of a xanalink, of type "supersedes", with the new and old snapshot CIDs as its endsets. It can carry:

- the author's signature,
- a short change summary,
- a mapping for cells that were renumbered, split or merged, so references into the old version can be translated to the new one,
- optionally, a scope narrower than the whole slice, such as one cell or one rank, so a supersede can replace part of a structure and leave the rest alone.

## Consequences for the version graph

- **It is a DAG.** Versions can fork when two people supersede the same snapshot, and can merge when a version supersedes two parents. "Latest" can therefore mean several heads, or none that you trust.
- **Whose supersede counts.** A link from the author is an ordinary update. A link from anyone else is a proposal or a fork. The viewer applies a trust policy: follow supersedes signed by the original author, or by anyone in a chosen group, and show the rest as alternatives.
- **Discovery needs an index.** Finding successors has the same difficulty as finding back-references: you must ask an index for links whose old endset is this CID. The index can be partial or lag, so "no newer version found" must not be shown as "this is the latest".
- **Structural sharing.** Because the tree of chunks is content-addressed, a new version shares unchanged leaves with the old one. Lineage is cheap to store, and a diff between two versions can compare the shared nodes and skip them.

## A cascading problem to avoid

If slice A stores a pinned CID of slice B inside its own cells, then moving to a newer B changes A, which makes a new version of A, and so on for everything that pins A. Cycles are impossible too, since A and B can't contain each other's hashes. The way around it is to keep cross-slice references out of the snapshots. They live in separate link objects or overlays, so adopting a newer B creates one small new link and leaves A as it was. Within a single snapshot the cell-to-cell neighbours are still plain ids, so rings and two-way links work as before.

## Changes to the viewer and API

Following a connection now shows the pinned version, with a badge such as "newer version exists" that appears when the index answers. The viewer never switches on its own, since the collaborator pinned that version on purpose. Useful operations:

- list successors of a snapshot, with the signer of each,
- list heads of a lineage, optionally filtered by trust policy,
- walk the lineage forward or back,
- translate a cell reference through a supersede link, returning "moved", "split", "deleted" or "unchanged",
- offer to update a reference: create a new reference link to the chosen successor.

## Trade-offs

You gain a full audit trail, reproducible views, and a design with no mutable state to trust. You lose a single canonical "current" version and any guaranteed way to learn about updates. Staying current depends on the index being complete and reachable, and a group needs a shared policy on which supersedes to follow.

## Prompt:
Please write a project brief that summarizes the requirements based on this entire conversation.

## Response:
I've written the project brief as a doc: https://claude.ai/artifact/SNLn2eQscRYQZCnUJs2zjV

It separates what I verified in your files, what comes from public sources, and what is still unknown. It then covers goals, requirements, open questions, phases and success criteria. The requirements are grouped by source addressing, documents, links, versioning, personal structures, lazy sharing, the backend API, the viewer and security. I flagged several open questions, including whether `0.db` reuses cell numbers, what the numeric values along color, translate and size mean, and the licensing limits on the archived demo.

You can edit it inline or comment, and I can revise it from your changes.

