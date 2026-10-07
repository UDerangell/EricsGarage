# Parsing WML files

**Exported with:** [AI Chat Exporter](https://ai-chat-exporter.covai.org)  
**Source:** Claude  
**Date:** 10/7/2026, 6:45:41 AM  
**Link:** [https://claude.ai/chat/4d1f304d-4e6e-4c29-8a52-55438f9ab5dd](https://claude.ai/chat/4d1f304d-4e6e-4c29-8a52-55438f9ab5dd)  
**Model:** claude-sonnet-5-5  
**Method:** API  

## Prompt:
What software is required to parse a WML file such as the attached?

## Response:
I'll take a look at the file first so the answer fits what's actually in it.

This file isn't the mobile-phone WML (Wireless Markup Language). It's a source file for **Website META Language**, also called WML, written by Ralf S. Engelschall. The header says "This file uses WML 2.0.1", and the file is HTML with extra directives such as `#include '../wmlinc/article.wml'` and `#use wml::fmt::xtable`. It's the specification document for GZigZag, and the authors edit the `.wml` and generate the `.html` from it.

**Software needed to process it**

- **Website META Language (WML) 2.x** is the main requirement. Its command-line tool is `wml`, which you'd run as `wml zzspec.wml` or `wml -o zzspec.html zzspec.wml`. On Debian or Ubuntu the package is `wml` (`sudo apt install wml`). Otherwise you can build it from source from the project's site, thewml.org.
- **Perl** is required, because WML is a Perl-based suite. It is installed by default on most Linux and macOS systems.
- **The WML passes' own dependencies** come along with the package. WML runs the file through a chain of passes: `mp4h` for macro expansion, `gpp` for the `#include` and `#use` directives, and `eperl` for embedded Perl. If you build from source, you may need these installed first.
- **The included files** matter too. The file pulls in `../wmlinc/article.wml`, which isn't part of the upload. It comes from the original GZigZag source tree, so the build will fail without it. The file also uses custom tags like `<substdims>`, `<toc>` and `<warn>`, which are probably defined in that include.

**If you just want to read or extract the content**

- Because the body is mostly plain HTML, you can open it in a text editor or strip the directives and view it in a browser. The custom tags and `#include` lines won't render properly, though.
- For programmatic parsing, you can use any HTML parser, such as Python's BeautifulSoup, and ignore or pre-filter the WML directives. This won't expand the macros, so it works for extracting text but not for reproducing the intended output.

Do you want to generate the HTML, or only pull out the text? I can suggest a specific approach for either.

## Prompt:
Attached is a diagram that may be used by the WML.  What software would be needed to view the diagram, or embed it in HTML output?

## Response:
The `.dia` file is a diagram from **Dia**, the open-source diagram editor (GNOME Dia). It's an old-style, uncompressed XML file: the root element is `<diagram>` and the objects are things like `Standard - Box`. Newer Dia versions save gzip-compressed XML, but this one is plain text, and current Dia opens both.

**Viewing and editing**

- **Dia** (dia-installer.de, or `sudo apt install dia` on Debian/Ubuntu) is the standard tool. It's available for Linux, Windows and macOS.
- Other programs can import `.dia` files, such as LibreOffice Draw (through the Dia import filter) and some Visio-like tools, but fidelity varies. Dia is the safe choice.

**Embedding in HTML output**

Browsers can't render `.dia` files directly, so you have to export to an image format first. The spec shows how the original authors did it. Line 384 of `zzspec.wml` has:

```
<figure img="rasterspec.png" width="250px">
```

So the HTML refers to a **PNG** exported from this diagram, and `<figure>` is a macro defined in the included WML files (probably `../wmlinc/article.wml`). The `.dia` file itself is only the editable source. The workflow was probably:

1. Edit `rasterspec.dia` in Dia.
2. Export to `rasterspec.png`, from the GUI via *File → Export* or from the command line.
3. Run `wml` on `zzspec.wml`, which expands `<figure>` into an `<img>` tag.

**Exporting from the command line**

```
dia --export=rasterspec.png --filter=png --size=500x rasterspec.dia
```

The `--filter` option also accepts `svg`, `eps` and `jpg`, among others. You can use SVG for sharper scaling with a plain `<img src="rasterspec.svg">` or `<object>` tag. On a headless server, use `dia -t png ...`, or `xvfb-run` if it complains about a missing display.

You don't need any extra software on the WML side for the diagram. WML only handles the `<figure>` tag, so the PNG just needs to sit next to the generated HTML.

## Prompt:
This file came from a wmlinc directory.  What is its probable function?

## Response:
`common.wml` is the **shared macro library** for the GZigZag documentation. Its job is to define the custom tags that `zzspec.wml` and the other documents use, so that each document's source stays simple. It is probably pulled in by `../wmlinc/article.wml`, which `zzspec.wml` includes directly, though I can't confirm that without seeing that file.

**The tags it defines**

| Tag | Purpose |
|---|---|
| `<substdims>` | Wraps a block and uses a Perl regex to turn dimension names like `d.foo` into `<code>d.foo</code>`. Writers don't have to mark them up by hand. This is the tag `zzspec.wml` opens right after `<body>`. |
| `<docref doc="...">text</docref>` | Makes a link to another GZZ document. It points to `../<doc>.html`, or `../<doc>-ns4.html` in NS4 mode. |
| `<figure img="..." width="...">caption</figure>` | A captioned figure. This is the tag that pulls in `rasterspec.png` in the spec. |
| `<infigure img="...">` | A simpler inline figure with no caption. |
| `<abstract>` | A formatted "Abstract" section. |
| `<warn>` | A notice at the top of the document about browser rendering (see below). |

**Two output modes, selected by `$(mode)`**

The file defines most of these tags twice, using `<if <string-eq $(mode) ns4>>` to choose.

- **Default mode** produces modern CSS markup, with `<div class=figure>` and similar. The `<warn>` text says this works best in a CSS1-compliant browser like Mozilla.
- **`ns4` mode** produces crude table-based layout for Netscape Navigator 4.x, which handled CSS badly. The warning says "you are reading an ugly version". This variant is built by passing a switch to `wml`, probably something like `-D mode=ns4`.

This tells us the site was built around 2001, in the Netscape 4 versus Mozilla era.

**Other details**

- The last two lines load the WML modules `wml::std::grid` and `wml::fmt::isolatin`. The first provides a grid layout helper. The second converts ISO Latin-1 characters to HTML entities.
- Since `zzspec.wml` uses `<toc>`, `<warn>`, `<figure>` and `<substdims>`, you now know where most of its custom tags come from. `<toc>` isn't defined here, so it presumably comes from `article.wml` or from a WML module such as `wml::std::toc`.
- `<docref>`, `<figure>` and `<abstract>` assume a stylesheet that defines the classes `figure`, `figureimg`, `astract` (a typo, but used consistently as far as I can tell) and `abstracthdr`. A CSS file is therefore missing from what you've uploaded, probably one loaded by `article.wml`.

To build `zzspec.wml` you now need `article.wml` and that stylesheet, in addition to this file.

## Prompt:
Please analyze and explain the contents of this file format

## Response:
`zzgentle.tex` is a **LaTeX 2e source file**, which is plain text with markup commands. It is the source of "A Gentle Introduction to Ted Nelson's ZigZag Structure" by Tuomas J. Lukka. It has about 1,280 lines and is encoded as ISO-8859-1 (Latin-1), not UTF-8. The only non-ASCII character is the "ä" in "Jyväskylä". That matters if you open it in a modern editor or compile it.

## Document structure

- **Preamble:** `\documentclass[12pt]{article}`, then the packages and title block. The copyright header (1999, "Redistribution permitted") is in comments.
- **Packages:**
  - `rcs` fills in the revision and date from CVS/RCS keywords (revision 1.17, September 2000).
  - `umlaut` helps with accented characters.
  - `times` selects the Times font.
  - `xy` (XY-pic) is for diagrams, with the frame, matrix, arrow and curve options loaded.
- **Front matter:** `\maketitle`, `\tableofcontents` and `\listoffigures`.
- **Macro:** `\def\zz{ZigZag}` is a shortcut, used about 76 times, so the product name can be typed as `\zz`.
- **Environments:** `figure` (8 captioned figures), `itemize`/`enumerate`/`description`, and a commented-out `abstract`.

## Content outline (9 sections, about 35 subsections)

1. **Introduction**
2. **Basics:** cells, ranks and dimensions, "a different perspective", special system dimensions, and a comparison to existing computer structures.
3. **Viewing:** raster, "vanishing", multicentric, 3D, tree, animated cloud and pseudo-3D views.
4. **Sample structures:** a CD player, a virtual pre/reprint collection, program settings, keybindings, a "better javadoc", a personal information manager, and a programmer's editor.
5. **Designing structures:** arrangement along a dimension, clones, many-to-one references, relation cells.
6. **Programming ZigZag:** scripting API, scripts, editing via scripts, watches.
7. **Versioning:** cell identity, scrolls.
8. **Distributed ZigZag:** remote protocol, slices.
9. **ZZ Programs:** model-view-controller.

It is a conceptual tutorial for the ZigZag data structure. This is the same project as the `zzspec.wml` specification you uploaded earlier. This document is the gentle introduction and the spec is the detailed reference.

## The unusual part: figures are drawn with pic

Most figures are not LaTeX. They embed **pic code** (`.PS` … `.PE` blocks), a Unix diagram language, followed by `\box\graph`:

```
.PS
box "Cell A" wid 0.6 ht 0.25
arrow "\tt d.1" ""
box "Cell B" same
.PE
\box\graph
```

That is the output convention of **GNU gpic** in TeX mode (`gpic -t`). The pic source is converted to TeX drawing commands that place the picture in a box named `\graph`. Older XY-pic versions of the same figures survive as commented-out `\xymatrix{...}` blocks. The header note "XXX redo pics in gpic" suggests the author was mid-migration from XY-pic to pic. You can see the shift in the command counts: `\xymatrix` appears 13 times, but most of those are in comments.

So the file is **not directly compilable**. Plain `latex` would choke on the `.PS`/`.PE` lines.

## What you need to build it

- A **TeX distribution** such as TeX Live or MiKTeX, which provides `latex`, `dvips` and the `xy` package.
- **groff's `gpic`** (the `groff` package), to preprocess the pic blocks into TeX.
- The old **`rcs` and `umlaut` packages**. These aren't in modern TeX distributions, so you'll probably need to find them or comment them out. The date line then needs a manual replacement.
- A rough build chain would be: `gpic -t zzgentle.tex > tmp.tex` → `latex tmp.tex` (twice, for the table of contents and cross-references) → `dvips` or `dvipdf`. Modern `pdflatex` can fail because pic's output may use `tpic` specials, which only DVI-based tools handle. Using `latex` then `dvips` then `ps2pdf` is safer.
- Run `iconv -f ISO-8859-1 -t UTF-8` only if you also add `\usepackage[utf8]{inputenc}`. Otherwise, keep the original Latin-1 encoding and add `\usepackage[latin1]{inputenc}`.

If you want, I can try building it into a PDF here. `latex` and `pdflatex` are installed in this environment, though `gpic` and the old packages may not be.

## Prompt:
Can you create human readable text files that extract only the text content from zzgentle.tex and zzspec.wml?

## Response:
I'll check which constructs each file uses so the converters handle them properly.

Still working: I'm fixing a few issues in the TeX extraction (blank lines after lists, empty figure captions), then I'll build the WML extractor.

TeX extraction is nearly done (references now resolve correctly); I'm fixing the header note, then building the WML extractor.

The WML extractor is working; I'm cleaning up its last quirks (the header note, a compact table, and a stray TeX fragment in the source), then I'll do a final check of both files.

I've made both plain-text files, UTF-8 and wrapped at 78 columns. I checked them for leftover markup and spot-checked the layout, but I haven't read every line.

**zzgentle.txt** (about 900 lines) is the ZigZag tutorial.
- The LaTeX commands and the pic/gpic diagram code are removed.
- Sections are numbered, and the `\ref` cross-references are resolved to those numbers, so "Fig. 5" and "see 5.4" point to the right places.
- Figure captions are kept as `[Figure N: …]`.
- The drawings themselves are not included, since they exist only as diagram code.

**zzspec.txt** (about 860 lines) is the GZigZag specification.
- WML directives and HTML tags are removed.
- Headings are underlined, and definition lists, bullets, the two record-format grids and the one table are laid out as text.
- Figures appear as `[Figure (rasterspec.png): caption]`.

Things I couldn't fully recover or had to interpret:
- **Missing include:** `zzspec.wml` pulls in `keybindings.wml`, which wasn't uploaded. A bracketed note marks where its content would go.
- **Omitted tags:** the `<toc>` and `<warn>` tags are left out, because WML generates their output at build time.
- **Source quirks:** the original files have a few errors, and I handled them as follows.
  - Figure 3 in the tutorial has no caption (the source just says "XXX!!!"), so it is labeled as a placeholder.
  - A sentence in section 3.1 ends mid-line ("…so that the part of") in the source, and I left it that way.
  - One definition list in the spec has its `dt`/`dd` tags swapped, so I rendered it as intended.
  - The text "fig:relcell" in section 5.4 is a literal reference that I resolved to "Figure 7".
  - A stray `{\em will}` in the spec is now plain "will".

I noted the dt/dd swap and the "fig:relcell" fix in each file's header note as well.

## Prompt:
Here is another WML file.  Please convert it to text.  Then reflect on the work you have done and suggest next steps for building a WML converter for other similar files.

## Response:
The generalized converter reproduces the earlier zzspec output, and `ug.wml` converts without errors. I'm checking the new constructs in `ug.txt` before I reflect on the approach.

I converted `ug.wml` (the GZigZag User's Guide) to `ug.txt`, which is about 300 lines of UTF-8 text. I also folded the earlier throwaway script into a reusable converter, `wml2txt.py`, and checked that it still reproduces the earlier `zzspec.txt`. I read the opening, the blockquote, the figures and the include placeholder in `ug.txt`, but not every line.

The new file added four things the first converter didn't handle:
- **`<infigure>`:** inline figures with no caption now appear as `[Figure (edit1.png)]`.
- **`<blockquote>` and `<dfn>`:** the blockquote is indented, and `<dfn>` is treated as ordinary text.
- **Layout-only `<grid>`:** the author block is a one-cell grid used for layout, so it is printed as plain lines.
- **Perl filter block:** the body is wrapped in `{: [[s/…/…/g]] … :}`, which is now stripped.

Two details to know about:
- **Encoding:** the file is ISO-8859-1 (the "ä" in Jyväskylä), so the script now tries UTF-8 and falls back to Latin-1.
- **Missing include:** `keybindings.wml` is again missing, so a bracketed placeholder marks where it would go.

## Reflection

**What worked.**
- Using Python's `HTMLParser` was robust for WML's sloppy HTML, with unclosed `<p>`, `<dt>` and `<li>` tags.
- Turning the document into blocks (heading, paragraph, list item, figure, table) and rendering them separately kept the parsing logic apart from the layout logic.
- Being explicit about what was dropped (the header note, the include placeholders) means readers can tell what the text file doesn't contain.

**What was fragile.**
- I wrote the first converters after looking at only one or two files, so they hard-coded things that turned out to be general. The `<dt>`/`<dd>` swap, the `<xtable>` handling and the heading underline styles were all special cases for `zzspec.wml`.
- I never saw the real macro definitions. I inferred what `<toc>`, `<warn>` and `<substdims>` do, and `article.wml` is still missing.
- The check was weak. I confirmed that the output looked right and had no leftover tags, but I had no automated test that the text was complete.
- The two kinds of source need different approaches. The TeX converter needed numbering, cross-references and a figure pre-pass. The WML converter is mostly about structure.

## Suggested next steps

1. **Collect the macro files.** Get `article.wml`, `common.wml` (already uploaded) and `keybindings.wml`. Then expand `<toc>`, resolve the includes, and make the converter read the real definitions instead of my guesses.
2. **Consider running real WML first.** If you can install `wml`, run `wml -o file.html file.wml`, then convert the HTML to text with something like `html2text`, `lynx -dump` or `pandoc`. This handles every macro correctly and removes my hand-written tag handling. My converter is still useful when the full tool chain isn't available.
3. **Build a small test set.** Keep the four documents you've shown me (`zzspec`, `ug`, plus the TeX one for the other converter) and compare each new output against a saved reference. That would have caught my two regressions earlier.
4. **Make unknown tags a hard signal.** The script now lists unrecognized tags in the header and on stderr. Treat any new tag as something to look at before trusting the result.
5. **Decide the output format.** Plain text loses structure. If the goal is feeding the content to other tools, Markdown (`#` headings, `-` lists, `![](...)` figures) would be easy to produce from the same block list and would preserve more.
6. **Handle the figures.** The diagrams exist only as PNGs, plus `rasterspec.dia`. For a complete text version, export them with `dia` or describe them, and decide whether captions alone are enough.
7. **Merge the two converters.** If more `.tex` files are coming, share the heading numbering, wrapping and header-note code between the two scripts, so the output style is the same.

## Prompt:
How do your previous answers change given this file that was missing from your previous analysis

## Response:
`article.wml` is only seven lines, so most of what I said stands. It mainly confirms two guesses and turns one assumption into a known gap.

```
#include "common.wml"
#use wml::std::toc style=ol type=11111
<style type="text/css">
#include "art.css"
</style>
```

## What it confirms

- **`common.wml` is loaded through `article.wml`.** I said this was probable, and it is now certain. The chain is `zzspec.wml` or `ug.wml` → `article.wml` → `common.wml`, all pulled in inside `<head>`. So the macros I described (`figure`, `infigure`, `docref`, `abstract`, `warn`, `substdims`) are the full set of custom tags, and I read their real definitions.
- **`<toc>` comes from a WML module.** It is provided by `wml::std::toc`, not by a macro in these files. The settings (`style=ol type=11111`) make it a nested ordered list that is numbered at every level. I had guessed this module, and it ships with WML, so nothing extra needs installing.
- **The stylesheet is inlined.** `art.css` is pasted into a `<style>` block in the page head. That is the CSS I said was missing, which defines the `figure`, `figureimg` and `astract` classes.

## What changes

1. **Missing pieces for building.** I earlier said you'd need `article.wml` and a stylesheet. You now have `article.wml`. Still missing are `art.css` and `keybindings.wml`, which `zzspec.wml` and `ug.wml` include. The `mode` variable (the NS4 versus CSS switch) is not set in any of these files, so it must come from the build command or a Makefile, which I haven't seen.
2. **Directory layout.** The paths imply a `wmlinc/` folder holding `article.wml`, `common.wml` and `art.css`, with the documents in a sibling folder. That is also why my converter drops any `#include` under `wmlinc/` without a note. This file shows those includes carry only macros, CSS and TOC settings, never document text, so that choice was right.
3. **My earlier reflection overstated the gap.** I said I'd been guessing at macro definitions. In fact the content-relevant macros were all in `common.wml`, which I had, and `article.wml` is just glue. The converters were on firmer ground than I implied. The real unknowns are `keybindings.wml` (actual text content) and `art.css` (appearance only).
4. **One omission can now be fixed.** My text output leaves out `<toc>`. Since it is generated from the headings, the converter could build a table of contents in text from the headings it already extracts. I'd need to confirm how many heading levels the module includes, and whether it numbers the headings themselves (I believe it only numbers the contents list). Running real `wml` on a document would settle both.
5. **Next steps revised.** Step 1 in my last list becomes: obtain `keybindings.wml` and `art.css`, and find the build command that sets `mode`. The idea of running real WML first still stands, but it is now easier to try, because the include chain is known.

Nothing in `zzspec.txt` or `ug.txt` needs correcting, since neither depended on `article.wml`'s content. If you'd like, I can add the generated table of contents to the converter's output.

## Prompt:
The script gets the following error on the attached file: python3 ../wml2txt.py appw.wml
unrecognized tags: ['abstract']
appw.wml -> appw.txt: 3 blocks

## Response:
I fixed `wml2txt.py`, and `appw.wml` now converts completely. Your run printed two symptoms, and both came from my script.

**1. `unrecognized tags: ['abstract']`.** `<abstract>` is defined in `common.wml`, which expands it to an "Abstract" `<h2>` heading followed by the body. I had read that definition earlier but never added the tag to the converter. It now produces an "Abstract" heading with the text under it.

**2. `3 blocks`.** This was the more serious bug, and the warning about `abstract` didn't point to it. The author block in `appw.wml` is a `<grid>` whose third `<cell>` is never closed:

```
<cell>
</grid>
```

My parser stayed "inside a cell" after the grid ended and swallowed all the remaining text, so only the title, the id line and a stub came out. Browsers and WML tolerate this, but my script didn't. The converter now closes any open cell when a new cell starts, when the grid ends, and at end of file. I also changed how layout-only grids are detected: a grid with at most one non-empty cell is printed as plain lines. That is why the author block comes out as just "Tuomas Lukka".

**New safeguards**
- **Coverage check:** the script now compares the word count of its output with the word count of the source text and prints a warning if less than 85% survives. The three files I've tested come out at 102 to 103%. I haven't tested it against the broken old version of the script, so I can't say it would have caught this bug, but a loss as large as this one should trip it.
- **Tabs:** tabs in `<pre>` blocks are expanded to spaces, so the Java sample in `appw.txt` lines up properly.

**Checks:** after the change, `ug.wml` produces identical text to before, and `zzspec.wml`'s body text is unchanged. `appw.txt` is 11 blocks: the title, the abstract, three sections and the Java example.

Two oddities in the source that I left alone because they don't affect the text. The Perl filter at the top (`s/\bZZModule\b/<code>\1<\/code>`) has no capture group and no `/g` flag, so it probably never worked as intended. The file also has `<substdims>` inside the filter block.

## Prompt:
How does this LaTeX file differ from the previous one you have seen?

## Response:
`design.ptex` is the same kind of document as `zzgentle.tex`, written by the same authors in the same pic-in-LaTeX style, but it is simpler in some ways and uses different commands in others. It is the "Clang Design Document", dated August 2000, revision 1.9. Clang is the cellular scripting language planned for ZigZag. Authors are Lukka and Kaijanaho, not Lukka alone.

| | `zzgentle.tex` | `design.ptex` |
|---|---|---|
| Extension | `.tex` | `.ptex` |
| Encoding | ISO-8859-1 | UTF-8 (ASCII-only text) |
| Document class | `article` at 12pt | `article` at default size |
| Packages | `rcs`, `umlaut`, `times`, `xy` | `rcs` only |
| Front matter | table of contents and list of figures | title only |
| Heading depth | section, subsection | adds `\subsubsection` (2 uses) |
| Size | 9 sections, 35 subsections, 8 figures | 7 sections, 17 subsections, 4 figures |
| Fonts | `{\tt x}`, `{\em x}` | mostly `{\tt x}`, plus `\texttt{x}` and `\emph{x}` |
| Shortcut macro | `\def\zz{ZigZag}` before the text | `\newcommand{\zz}{ZigZag}` after `\begin{document}` |
| Lists | `itemize`, `enumerate`, `description` | none |
| Math | one `5\times5` | several inline `$O(N+M)$` expressions |
| Diagrams | pic, with commented-out XY-pic versions | pic only (7 `.PS` blocks, no XY-pic) |

**The `.ptex` extension.** The first line says "BE SURE TO EDIT design.ptex", the same warning as in the WML files about not editing generated output. I suspect `.ptex` means "TeX with pic embedded", where a build step runs `gpic -t` and writes a plain `.tex` file. I haven't seen the Makefile, so that is an inference. If it's right, the file as it stands won't compile with plain `latex`, as with `zzgentle.tex`, but it needs fewer old packages (only `rcs`).

**Figures.** They differ in layout from `zzgentle.tex`:
- One pic drawing sits outside any figure, as a small "Clang" box under the introduction heading, displayed with `$$\box\graph$$`.
- Inside figures, the pic code comes before `\caption`, not after it. It is often wrapped in a `{\tt … }` group, and one figure has three sub-pictures labeled `a)`, `b)` and `c)` separated by `\\`.

**Effect on my converter.** The pic-removal, caption extraction, cross-references, math and `\zz` handling should work unchanged. It would need small additions for:
- `\subsubsection`, which my heading handling doesn't recognize
- `\texttt{…}` and `\emph{…}`, which my font handling doesn't know about
- `\newcommand{\zz}{ZigZag}`, which my code only handles in the `\def` form
- the title, authors (`\and`) and revision date, which I hard-coded for `zzgentle.tex` rather than reading from the file

I also never saved the TeX converter to the outputs folder, unlike `wml2txt.py`, and it still has `zzgentle` paths written into it. If you want a text version of this file, I'll generalize that script into a command-line tool first and run it on `design.ptex`.

## Prompt:
Please create the python script for .tex and .ptex conversion to .txt

## Response:
I'll write one general script that handles both `.tex` and `.ptex`. It will read the title and revision from the file instead of hard-coding them, and handle the extra constructs we've met so far (`\subsubsection`, `\texttt`, `\newcommand`, and so on). Then I'll test it on the two files and on a synthetic document that exercises lists, tables, math and macros.

## Response:
> **Artifact: tex2txt**
```python
#!/usr/bin/env python3
"""tex2txt.py - extract readable plain text from LaTeX (.tex) and pic+LaTeX (.ptex) sources.

usage: tex2txt.py INPUT.tex [OUTPUT.txt]

What it does
  * reads the source as UTF-8, falling back to ISO-8859-1
  * takes title / author / date / RCS revision from the preamble for a header
  * expands simple user macros (\\newcommand, \\def, with or without arguments)
  * numbers chapters/sections/subsections/subsubsections (and appendices),
    figures, tables and equations, and resolves \\ref, \\eqref, \\cite
  * keeps lists, quotes, verbatim blocks, simple tables, footnotes and
    bibliographies as readable text; math is turned into Unicode text
  * drops figure drawings (embedded pic/gpic code, \\includegraphics, xy-pic ...)
    but keeps captions as  [Figure N: caption]
  * reports anything it did not understand (unknown commands/environments,
    missing \\input files, unresolved references) in the header and on stderr
  * warns when much less text comes out than the source seems to contain

Not handled: custom environments defined with \\newenvironment, tikz/pgf
drawings, multi-line math layout, floats nested inside floats, bibliographies
that live in a .bib file.
"""
import re, sys, os, textwrap, unicodedata

W = 78
BRK, SEP, MK0, MK1, TS, TE = '\x04', '\x03', '\x01', '\x02', '\x06', '\x07'
ESC_MAP = {'\\\\': BRK, '\\%': '\x13', '\\{': '\x10', '\\}': '\x11',
           '\\$': '\x12', '\\&': '\x14', '\\#': '\x15', '\\_': '\x16'}
UNESC = {'\x13': '%', '\x10': '{', '\x11': '}', '\x12': '$', '\x14': '&', '\x15': '#', '\x16': '_'}

# ---------------------------------------------------------------- tables
DECL = set('''tt em bf it rm sf sc sl up md normalfont ttfamily rmfamily sffamily bfseries itshape
slshape scshape mdseries upshape small footnotesize large Large LARGE huge Huge normalsize tiny
scriptsize centering raggedright raggedleft noindent indent selectfont relax protect clearpage
newpage cleardoublepage bigskip medskip smallskip bigbreak medbreak smallbreak nopagebreak
pagebreak goodbreak sloppy fussy maketitle tableofcontents listoffigures listoftables appendix
frenchspacing nonumber notag hfill vfill hrulefill dotfill strut allowbreak null
hline toprule midrule bottomrule footnotemark protect displaystyle textstyle
scriptstyle limits nolimits'''.split())
KEEP = set('''textbf textit texttt emph textrm textsf textsc textsl textup textmd textnormal underline
mbox hbox fbox makebox framebox text textsuperscript textsubscript mathrm mathbf mathit mathsf mathtt
mathcal mathbb MakeUppercase uppercase lowercase MakeLowercase caption centerline
operatorname boldsymbol bm mathnormal'''.split())
DROP = {'label': 1, 'index': 1, 'glossary': 1, 'vspace': 1, 'hspace': 1, 'pagestyle': 1,
        'thispagestyle': 1, 'setlength': 2, 'setcounter': 2, 'addtocounter': 2, 'pagenumbering': 1,
        'bibliographystyle': 1, 'usepackage': 1, 'documentclass': 1, 'graphicspath': 1,
        'hyphenation': 1, 'linespread': 1, 'DeclareMathOperator': 2, 'addcontentsline': 3,
        'markboth': 2, 'markright': 1, 'fontsize': 2, 'rule': 2, 'phantom': 1, 'hphantom': 1,
        'vphantom': 1, 'enlargethispage': 1, 'newlength': 1, 'hypersetup': 1, 'geometry': 1,
        'lstset': 1, 'captionsetup': 1, 'cline': 1, 'raisebox': 1, 'includeonly': 1}
SYMS = {'LaTeX': 'LaTeX', 'TeX': 'TeX', 'ldots': '...', 'dots': '...', 'textbackslash': '\\',
        'S': '§', 'P': '¶', 'copyright': '©', 'textregistered': '®', 'texttrademark': '™',
        'pounds': '£', 'euro': '€', 'texteuro': '€', 'ss': 'ß', 'oe': 'œ', 'OE': 'Œ', 'ae': 'æ',
        'AE': 'Æ', 'o': 'ø', 'O': 'Ø', 'aa': 'å', 'AA': 'Å', 'l': 'ł', 'L': 'Ł', 'i': 'i', 'j': 'j',
        'dag': '†', 'ddag': '‡', 'textbullet': '•', 'textasciitilde': '~', 'textasciicircum': '^',
        'textunderscore': '_', 'textbar': '|', 'textless': '<', 'textgreater': '>',
        'textendash': '–', 'textemdash': '—', 'today': '', 'quad': ' ', 'qquad': '  ',
        'textdegree': '°', 'degree': '°', 'textquotedblleft': '"', 'textquotedblright': '"',
        'textquoteleft': "'", 'textquoteright': "'", 'ldq': '"', 'rdq': '"', 'par': '\n\n',
        'newline': BRK, 'linebreak': BRK, 'break': BRK, 'item': '', 'and': ', ',
        'textcopyright': '©', 'ell': 'ℓ'}
ACC = {'"': '\u0308', "'": '\u0301', '`': '\u0300', '^': '\u0302', '~': '\u0303', '=': '\u0304',
       '.': '\u0307', 'u': '\u0306', 'v': '\u030c', 'H': '\u030b', 'c': '\u0327', 'k': '\u0328',
       'r': '\u030a', 'd': '\u0323', 'b': '\u0331'}
GREEK = {n: c for n, c in zip(
    'alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi '
    'varpi rho varrho sigma varsigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda '
    'Xi Pi Sigma Upsilon Phi Psi Omega'.split(),
    'αβγδεϵζηθϑικλμνξπϖρϱσςτυφϕχψωΓΔΘΛΞΠΣΥΦΨΩ')}
MATHSYM = dict(GREEK, **{
    'times': '×', 'cdot': '·', 'div': '÷', 'pm': '±', 'mp': '∓', 'leq': '≤', 'le': '≤', 'geq': '≥',
    'ge': '≥', 'neq': '≠', 'ne': '≠', 'approx': '≈', 'equiv': '≡', 'sim': '∼', 'simeq': '≃',
    'propto': '∝', 'infty': '∞', 'll': '≪', 'gg': '≫', 'ast': '*', 'circ': '∘', 'bullet': '•',
    'star': '⋆', 'langle': '⟨', 'rangle': '⟩', 'lceil': '⌈', 'rceil': '⌉', 'lfloor': '⌊',
    'rfloor': '⌋', 'sum': '∑', 'prod': '∏', 'int': '∫', 'oint': '∮', 'partial': '∂', 'nabla': '∇',
    'forall': '∀', 'exists': '∃', 'in': '∈', 'notin': '∉', 'ni': '∋', 'subset': '⊂',
    'subseteq': '⊆', 'supset': '⊃', 'supseteq': '⊇', 'cup': '∪', 'cap': '∩', 'emptyset': '∅',
    'varnothing': '∅', 'land': '∧', 'wedge': '∧', 'lor': '∨', 'vee': '∨', 'neg': '¬', 'lnot': '¬',
    'Rightarrow': '⇒', 'Leftarrow': '⇐', 'Leftrightarrow': '⇔', 'iff': '⇔', 'implies': '⇒',
    'rightarrow': '→', 'to': '→', 'leftarrow': '←', 'gets': '←', 'leftrightarrow': '↔',
    'mapsto': '↦', 'uparrow': '↑', 'downarrow': '↓', 'cdots': '...', 'ldots': '...', 'dots': '...',
    'vdots': '⋮', 'ddots': '⋱', 'perp': '⊥', 'parallel': '∥', 'angle': '∠', 'prime': "′",
    'setminus': '∖', 'oplus': '⊕', 'otimes': '⊗', 'top': '⊤', 'bot': '⊥', 'vdash': '⊢',
    'models': '⊨', 'hbar': 'ħ', 'ell': 'ℓ', 'Re': 'ℜ', 'Im': 'ℑ', 'aleph': 'ℵ', 'quad': ' ',
    'qquad': '  ', 'mid': '|', 'vert': '|', 'Vert': '‖', 'lbrace': '{', 'rbrace': '}'})
MATHFUNC = set('log ln lg sin cos tan cot sec csc arcsin arccos arctan sinh cosh tanh exp max min '
               'lim limsup liminf sup inf det gcd deg dim arg ker hom Pr mod bmod'.split())
BB = {'R': 'ℝ', 'Z': 'ℤ', 'C': 'ℂ', 'Q': 'ℚ', 'N': 'ℕ', 'P': 'ℙ', 'H': 'ℍ'}
SUP = dict(zip('0123456789+-=()ni', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱ'))
SUB = dict(zip('0123456789+-=()', '₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎'))
WRAP_ENVS = set('center flushleft flushright minipage small footnotesize large Large normalsize '
                'tiny scriptsize samepage multicols titlepage sloppypar'.split())
ARG_ENVS = {'minipage', 'multicols'}
HEAD_NAMES = ['chapter', 'section', 'subsection', 'subsubsection']
UNDERLINE = {0: '#', 1: '=', 2: '-', 3: '~'}
HEAD_RE = re.compile(r'\\(chapter|section|subsection|subsubsection)(\*?)\s*(?:\[[^\]]*\])?\s*\{')
FLOAT_RE = re.compile(r'\\begin\{(figure|table)(\*?)\}(.*?)\\end\{\1\2\}', re.S)
EQ_RE = re.compile(r'\\begin\{equation\}(.*?)\\end\{equation\}', re.S)
DISPLAY_ENV_RE = re.compile(r'\\begin\{(equation|displaymath|align|eqnarray|gather|multline|flalign|math)(\*?)\}(.*?)\\end\{\1\2\}', re.S)
LABEL_RE = re.compile(r'\\label\{([^}]*)\}')


def balanced(s, i):
    """s[i] must be '{'; return the index just after the matching '}'."""
    d = 0
    for j in range(i, len(s)):
        c = s[j]
        if c == '{': d += 1
        elif c == '}':
            d -= 1
            if d == 0: return j + 1
    return len(s)

def get_arg(s, i):
    """Skip whitespace from i; return (content, end) of a {...} argument, or None."""
    while i < len(s) and s[i] in ' \t\r\n': i += 1
    if i < len(s) and s[i] == '{':
        j = balanced(s, i)
        return s[i + 1:j - 1], j
    return None

def take_cmd(s, name):
    m = re.search(r'\\%s\*?\s*(?:\[[^\]]*\])?\s*\{' % name, s)
    if not m: return s, None
    j = balanced(s, m.end() - 1)
    return s[:m.start()] + s[j:], s[m.end():j - 1]

def combine(letter, mark):
    return unicodedata.normalize('NFC', letter + mark)


class Conv:
    def __init__(self, name):
        self.name = name
        self.store, self.tabs = [], []
        self.labels, self.heads, self.floats = {}, [], []
        self.unknown_cmds, self.unknown_envs, self.includes = set(), set(), []
        self.has_pic = False; self.unresolved = set(); self.theorems = {}; self.thm_count = {}
        self.has_float = False; self.has_graphics = False

    # ---------------------------------------------------------- store/restore
    def stash(self, text):
        self.store.append(text)
        return TS + str(len(self.store) - 1) + TE

    def restore(self, s):
        for _ in range(4):
            if TS not in s: break
            s = re.sub(TS + r'(\d+)' + TE, lambda m: self.store[int(m.group(1))], s)
        for k, v in UNESC.items(): s = s.replace(k, v)
        return s

    # ---------------------------------------------------------------- math
    def math(self, x):
        x = re.sub(r'\\(?:nonumber|notag|displaystyle|textstyle|limits|nolimits)(?![A-Za-z])', '', x)
        x = LABEL_RE.sub('', x)
        x = re.sub(r'\\(?:left|right)\s*\.', '', x)
        x = re.sub(r'\\(?:left|right|bigl|bigr|Bigl|Bigr|biggl|biggr|big|Big|bigg|Bigg)(?![A-Za-z])', '', x)
        x = x.replace('&', ' ')
        for name in ('frac', 'dfrac', 'tfrac', 'binom'):
            x = self._two_arg(x, name)
        x = self._sqrt(x)
        x = re.sub(r'\\mathbb\s*\{\s*([A-Za-z])\s*\}', lambda m: BB.get(m.group(1), m.group(1)), x)
        for cmd, mark in (('bar', '\u0304'), ('overline', '\u0304'), ('hat', '\u0302'), ('widehat', '\u0302'),
                          ('tilde', '\u0303'), ('widetilde', '\u0303'), ('dot', '\u0307'),
                          ('ddot', '\u0308'), ('vec', '\u20d7'), ('underline', '\u0332')):
            x = re.sub(r'\\%s\s*\{\s*([A-Za-z])\s*\}' % cmd, lambda m, mk=mark: combine(m.group(1), mk), x)
        def word(m):
            n = m.group(1)
            if n in MATHSYM: return MATHSYM[n]
            if n in MATHFUNC: return n
            if n in KEEP or n in DECL: return ''
            self.unknown_cmds.add('\\' + n + ' (in math)'); return ''
        x = re.sub(r'\\([A-Za-z]+)\*?(?![A-Za-z])', word, x)
        x = re.sub(r'\\[,;:> ]', ' ', x)
        x = re.sub(r'\\[!/@-]', '', x)
        x = self._scripts(x)
        x = x.replace('{', '').replace('}', '').replace('~', ' ')
        x = re.sub(r"(?<=\w)'+", lambda m: '′' * len(m.group(0)), x)
        lines = [re.sub(r'[ \t]+', ' ', l).strip() for l in x.split(BRK)]
        return BRK.join(l for l in lines if l)

    def _two_arg(self, x, name):
        out, pos = [], 0
        for m in re.finditer(r'\\%s(?![A-Za-z])' % name, x):
            if m.start() < pos: continue
            a = get_arg(x, m.end())
            b = get_arg(x, a[1]) if a else None
            if not (a and b): continue
            wrap = lambda t: t if re.fullmatch(r'[\w.]+', t.strip()) else '(' + t + ')'
            if name == 'binom': rep = 'C(%s, %s)' % (a[0], b[0])
            else: rep = wrap(a[0]) + '/' + wrap(b[0])
            out.append(x[pos:m.start()] + rep); pos = b[1]
        return ''.join(out) + x[pos:]

    def _sqrt(self, x):
        out, pos = [], 0
        for m in re.finditer(r'\\sqrt(?![A-Za-z])(?:\[([^\]]*)\])?', x):
            if m.start() < pos: continue
            a = get_arg(x, m.end())
            if not a: continue
            pre = '√' if not m.group(1) else '(%s)√' % m.group(1)
            out.append(x[pos:m.start()] + pre + '(' + a[0] + ')'); pos = a[1]
        return ''.join(out) + x[pos:]

    def _scripts(self, x):
        def sc(m):
            kind, g = m.group(1), m.group(2)
            body = g[1:-1] if g.startswith('{') else g
            table = SUP if kind == '^' else SUB
            plain = re.sub(r'[{}\s]', '', body)
            if plain and all(c in table for c in plain): return ''.join(table[c] for c in plain)
            return kind + (body if len(plain) <= 1 else '(' + body + ')')
        return re.sub(r'([_^])(\{[^{}]*\}|.)', sc, x)

    # ------------------------------------------------------------ pipeline
    def convert(self, raw, enc):
        s = raw
        notes = []
        # 1. protect verbatim material
        def venv(m):
            self.store.append(m.group(2).strip('\n'))
            return '\n\n' + MK0 + 'VB' + SEP + str(len(self.store) - 1) + MK1 + '\n\n'
        s = re.sub(r'\\begin\{(verbatim\*?|Verbatim|lstlisting)\}(?:\[[^\]]*\])?(.*?)\\end\{\1\}', venv, s, flags=re.S)
        s = re.sub(r'\\(?:verb|lstinline)\*?(?:\[[^\]]*\])?(\S)(.*?)\1', lambda m: self.stash(m.group(2)), s)
        s = re.sub(r'\\url\{([^}]*)\}', lambda m: self.stash(m.group(1)), s)
        s = re.sub(r'\\href\{([^}]*)\}\{([^{}]*)\}', lambda m: m.group(2) + ' (' + self.stash(m.group(1)) + ')', s)
        # 2. embedded pic (gpic) drawings
        pic = re.compile(r'(?m)^[ \t]*\.PS\b.*?^[ \t]*\.PE\b[^\n]*\n?', re.S)
        if pic.search(s): self.has_pic = True
        s = pic.sub('', s)
        s = s.replace('\\box\\graph', '')
        # 3. escapes, comments
        s = re.sub(r'\\(?:\\|[%{}$&#_])', lambda m: ESC_MAP[m.group(0)], s)
        s = re.sub(r'%.*', '', s)
        s = re.sub(r'\\begin\{comment\}.*?\\end\{comment\}', '', s, flags=re.S)
        s = re.sub(BRK + r'\s*\*?\s*\[\s*-?[\d.]*\s*(?:pt|ex|em|cm|mm|in|bp)\s*\]', BRK, s)
        # 4. RCS keywords, macros
        rev = re.search(r'\\RCS\s*\$Revision:\s*([\d.]+)\s*\$', s)
        dat = re.search(r'\\RCS\s*\$Date:\s*(\S+)', s)
        rev, dat = (rev.group(1) if rev else ''), (dat.group(1) if dat else '')
        s = re.sub(r'\\RCS\s*\$[^$]*\$', '', s)
        s = s.replace('\\RCSRevision', rev).replace('\\RCSDate', dat)
        s = self.collect_macros(s)
        # 5. header material
        s, title = take_cmd(s, 'title')
        s, author = take_cmd(s, 'author')
        s, date = take_cmd(s, 'date')
        # 6. body only
        a = s.find('\\begin{document}')
        if a >= 0: s = s[a + len('\\begin{document}'):]
        b = s.rfind('\\end{document}')
        if b >= 0: s = s[:b]
        body_for_check = s
        s = self.numbering_pass(s)
        s = self.structure(s)
        s = self.inline(s)
        header = self.header(title, author, date, rev, dat)
        text = self.layout(s)
        return header, text, body_for_check

    # ------------------------------------------------------------- macros
    def collect_macros(self, s):
        macros = {}
        pat = re.compile(r'\\(newcommand|providecommand|renewcommand|DeclareRobustCommand)\*?\s*\{?\s*\\([A-Za-z]+)\s*\}?\s*(?:\[(\d)\])?\s*(?:\[[^\]]*\])?\s*\{')
        while True:
            m = pat.search(s)
            if not m: break
            j = balanced(s, m.end() - 1)
            if m.group(1) != 'renewcommand':
                macros[m.group(2)] = (int(m.group(3) or 0), s[m.end():j - 1])
            s = s[:m.start()] + s[j:]
        pat = re.compile(r'\\def\s*\\([A-Za-z]+)((?:#\d)*)\s*\{')
        while True:
            m = pat.search(s)
            if not m: break
            j = balanced(s, m.end() - 1)
            macros[m.group(1)] = (len(m.group(2)) // 2, s[m.end():j - 1])
            s = s[:m.start()] + s[j:]
        pat = re.compile(r'\\newtheorem\*?\{([^}]*)\}(?:\[[^\]]*\])?\{([^}]*)\}(?:\[[^\]]*\])?')
        for m in pat.finditer(s): self.theorems[m.group(1)] = m.group(2)
        s = pat.sub('', s)
        s = re.sub(r'\\newenvironment\*?\{[^}]*\}.*', lambda m: m.group(0), s) if False else s
        if macros:
            names = sorted(macros, key=len, reverse=True)
            rx = re.compile(r'\\(' + '|'.join(map(re.escape, names)) + r')(?![A-Za-z@])')
            for _ in range(8):
                out, pos, changed = [], 0, False
                for m in rx.finditer(s):
                    if m.start() < pos: continue
                    n, body = macros[m.group(1)]
                    end, args = m.end(), []
                    for _k in range(n):
                        g = get_arg(s, end)
                        if g: args.append(g[0]); end = g[1]
                        else:
                            t = re.match(r'\s*(\\[A-Za-z]+|.)', s[end:], re.S)
                            if not t: break
                            args.append(t.group(1)); end += t.end()
                    rep = body
                    for k, a in enumerate(args, 1): rep = rep.replace('#%d' % k, a)
                    if n == 0:
                        t = re.match(r'(\{\})?(\\ )?', s[end:])
                        end += t.end()
                        if t.group(2): rep += ' '
                    out.append(s[pos:m.start()] + rep); pos = end; changed = True
                s = ''.join(out) + s[pos:]
                if not changed: break
        return s

    # ----------------------------------------------------------- numbering
    def numbering_pass(self, s):
        has_chapter = bool(re.search(r'\\chapter(?![A-Za-z])', s))
        start = 0 if has_chapter else 1
        events = []
        float_spans = [(m.start(), m.end(), m) for m in FLOAT_RE.finditer(s)]
        eq_spans = [(m.start(), m.end(), m) for m in EQ_RE.finditer(s)]
        for m in HEAD_RE.finditer(s): events.append((m.start(), 'head', m))
        for st, en, m in float_spans: events.append((st, 'float', m))
        for st, en, m in eq_spans: events.append((st, 'eq', m))
        for m in re.finditer(r'\\appendix(?![A-Za-z])', s): events.append((m.start(), 'app', m))
        inside = lambda p: any(st <= p < en for st, en, _ in float_spans + eq_spans)
        for m in LABEL_RE.finditer(s):
            if not inside(m.start()): events.append((m.start(), 'label', m))
        events.sort(key=lambda e: e[0])
        c = [0, 0, 0, 0]; cnt = {'figure': 0, 'table': 0, 'eq': 0}
        appendix = False; cur = ('Section', '')
        letter = lambda n: chr(ord('A') + n - 1)
        for pos, kind, m in events:
            if kind == 'app':
                appendix = True; c[start:] = [0] * (4 - start)
            elif kind == 'head':
                L = HEAD_NAMES.index(m.group(1))
                if m.group(2): self.heads.append((L, '')); continue
                c[L] += 1
                for k in range(L + 1, 4): c[k] = 0
                parts = [(letter(c[i]) if appendix and i == start else str(c[i])) for i in range(start, L + 1)]
                num = '.'.join(parts)
                self.heads.append((L, num)); cur = ('Section', num)
            elif kind == 'float':
                k = m.group(1); cnt[k] += 1
                self.floats.append((k, cnt[k]))
                for lm in LABEL_RE.finditer(m.group(3)): self.labels[lm.group(1)] = (k, str(cnt[k]))
            elif kind == 'eq':
                cnt['eq'] += 1
                for lm in LABEL_RE.finditer(m.group(1)): self.labels[lm.group(1)] = ('eq', str(cnt['eq']))
            elif kind == 'label':
                self.labels[m.group(1)] = cur
        return s

    # ----------------------------------------------------------- structure
    def tabulars(self, s):
        out, pos = [], 0
        for m in re.finditer(r'\\begin\{(tabular\*?|tabularx|longtable|array|tabulary)\}', s):
            if m.start() < pos: continue
            name = m.group(1); i = m.end()
            t = re.match(r'\s*\[[^\]]*\]', s[i:])
            if t: i += t.end()
            if name in ('tabular*', 'tabularx', 'tabulary'):
                a = get_arg(s, i); i = a[1] if a else i
            a = get_arg(s, i); i = a[1] if a else i
            e = s.find('\\end{%s}' % name, i)
            if e < 0: continue
            content = s[i:e]
            rows_raw = content.split(BRK)
            rule = lambda r: bool(re.match(r'\s*\\(hline|midrule|toprule|cline\{[^}]*\})', r))
            header_sep = len(rows_raw) > 1 and rule(rows_raw[1])
            rows = []
            for r in rows_raw:
                r = re.sub(r'\\(hline|midrule|toprule|bottomrule|endhead|endfirsthead|cline\{[^}]*\})', '', r)
                r = re.sub(r'\\multicolumn\s*\{(\d+)\}\s*\{[^{}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}',
                           lambda mm: mm.group(2) + '&' * (int(mm.group(1)) - 1), r)
                r = re.sub(r'\\multirow\s*\{[^{}]*\}\s*\{[^{}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}', r'\1', r)
                if not r.strip(): continue
                rows.append([c.strip() for c in r.split('&')])
            self.tabs.append({'rows': rows, 'sep': header_sep})
            out.append(s[pos:m.start()] + '\n\n' + MK0 + 'TAB' + SEP + str(len(self.tabs) - 1) + MK1 + '\n\n')
            pos = e + len('\\end{%s}' % name)
        return ''.join(out) + s[pos:]

    def structure(self, s):
        s = self.tabulars(s)
        # floats
        fq = list(self.floats)
        def flt(m):
            kind, num = fq.pop(0) if fq else (m.group(1), '?')
            self.has_float = True
            body = m.group(3)
            cap = ''
            cm = re.search(r'\\caption\*?\s*(?:\[[^\]]*\])?\s*\{', body)
            if cm:
                j = balanced(body, cm.end() - 1); cap = body[cm.end():j - 1]
            files = re.findall(r'\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]*)\}', body)
            if files: self.has_graphics = True
            label = '%s %s' % (kind.capitalize(), num)
            if files: label += ' (' + ', '.join(files) + ')'
            r = '\n\n' + MK0 + 'CAP' + SEP + label + SEP + (cap.strip() or '(no caption)') + MK1 + '\n\n'
            if kind == 'table':
                r += ''.join('\n\n' + t + '\n\n' for t in re.findall(MK0 + 'TAB' + SEP + r'\d+' + MK1, body))
            return r
        s = FLOAT_RE.sub(flt, s)
        # display math
        def disp(m):
            return '\n\n' + MK0 + 'DM' + SEP + self.stash(self.math(m.group(3))) + MK1 + '\n\n'
        s = DISPLAY_ENV_RE.sub(disp, s)
        s = re.sub(r'\$\$(.*?)\$\$', lambda m: '\n\n' + MK0 + 'DM' + SEP + self.stash(self.math(m.group(1))) + MK1 + '\n\n', s, flags=re.S)
        s = re.sub(r'\\\[(.*?)\\\]', lambda m: '\n\n' + MK0 + 'DM' + SEP + self.stash(self.math(m.group(1))) + MK1 + '\n\n', s, flags=re.S)
        def inl(m):
            if re.search(r'\n\s*\n', m.group(1)): return m.group(0)
            return self.stash(self.math(m.group(1)))
        s = re.sub(r'\$([^$]+)\$', inl, s)
        s = re.sub(r'\\\((.*?)\\\)', inl, s, flags=re.S)
        # headings
        out, pos, hq = [], 0, list(self.heads)
        for m in HEAD_RE.finditer(s):
            if m.start() < pos: continue
            j = balanced(s, m.end() - 1)
            L, num = hq.pop(0) if hq else (HEAD_NAMES.index(m.group(1)), '')
            out.append(s[pos:m.start()] + '\n\n' + MK0 + 'H' + SEP + str(L) + SEP + num + SEP + s[m.end():j - 1] + MK1 + '\n\n')
            pos = j
        s = ''.join(out) + s[pos:]
        s = re.sub(r'\\(?:sub)?paragraph\*?\s*\{([^{}]*)\}', r'\n\n\1. ', s)
        # abstract, quotes, lists, bibliography, theorems
        s = re.sub(r'\\begin\{abstract\}', '\n\n' + MK0 + 'H' + SEP + '2' + SEP + SEP + 'Abstract' + MK1 + '\n\n', s)
        s = s.replace('\\end{abstract}', '\n\n')
        s = re.sub(r'\\begin\{(quote|quotation|verse)\}', '\n\n' + MK0 + 'QB' + MK1 + '\n\n', s)
        s = re.sub(r'\\end\{(quote|quotation|verse)\}', '\n\n' + MK0 + 'QE' + MK1 + '\n\n', s)
        s = re.sub(r'\\begin\{(itemize|enumerate|description)\}(?:\[[^\]]*\])?', lambda m: '\n\n' + MK0 + 'LB' + SEP + m.group(1) + MK1 + '\n', s)
        s = re.sub(r'\\begin\{thebibliography\}\{[^}]*\}', '\n\n' + MK0 + 'LB' + SEP + 'bib' + MK1 + '\n', s)
        s = re.sub(r'\\end\{(itemize|enumerate|description|thebibliography)\}', '\n' + MK0 + 'LE' + MK1 + '\n\n', s)
        s = re.sub(r'\\bibitem\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}', lambda m: '\n' + MK0 + 'IT' + SEP + '[' + (m.group(1) or m.group(2)) + ']' + MK1, s)
        s = re.sub(r'\\item\s*(?:\[((?:[^\[\]{}]|\{[^{}]*\})*)\])?', lambda m: '\n' + MK0 + 'IT' + SEP + (m.group(1) or '') + MK1, s)
        for name, title in list(self.theorems.items()) + [('proof', 'Proof')]:
            def tb(m, name=name, title=title):
                if name == 'proof': return '\n\n' + title + '. '
                self.thm_count[name] = self.thm_count.get(name, 0) + 1
                extra = ' (%s)' % m.group(1) if m.group(1) else ''
                return '\n\n%s %d%s. ' % (title, self.thm_count[name], extra)
            s = re.sub(r'\\begin\{%s\}(?:\[([^\]]*)\])?' % re.escape(name), tb, s)
            s = s.replace('\\end{%s}' % name, '\n\n')
        # wrappers / unknown environments
        def env(m):
            n = m.group(2)
            if n == 'document': return ''
            if n not in WRAP_ENVS: self.unknown_envs.add(n)
            return '\n\n' if n in ('center', 'flushleft', 'flushright') else ''
        s = re.sub(r'\\(begin|end)\{([A-Za-z]+\*?)\}(?:\{[^{}]*\})?', env, s)
        # includes, graphics, footnotes
        def inc(m):
            self.includes.append(m.group(2))
            return '\n\n[The source includes "%s" here (%s); that file was not provided.]\n\n' % (m.group(2), m.group(1))
        s = re.sub(r'\\(input|include|bibliography|lstinputlisting)\s*(?:\[[^\]]*\])?\{([^}]*)\}', inc, s)
        s = re.sub(r'\\includegraphics\*?(?:\[[^\]]*\])?\{([^}]*)\}', r'[Image: \1]', s)
        s = self.footnotes(s)
        return s

    def footnotes(self, s):
        while True:
            m = re.search(r'\\(footnote|thanks)\*?\s*(?:\[[^\]]*\])?\s*\{', s)
            if not m: break
            j = balanced(s, m.end() - 1)
            s = s[:m.start()] + ' [Note: ' + s[m.end():j - 1].strip() + ']' + s[j:]
        return s

    # -------------------------------------------------------------- inline
    def ref(self, key):
        if key in self.labels: return self.labels[key][1]
        self.unresolved.add(key); return '?'

    def inline(self, s):
        s = re.sub(r'\\(ref|autoref|cref|Cref|vref|nameref|eqref|pageref)\*?\{([^}]*)\}', lambda m:
                   '?' if m.group(1) == 'pageref' else ('(%s)' % self.ref(m.group(2)) if m.group(1) == 'eqref' else self.ref(m.group(2))), s)
        s = re.sub(r'\\(?:cite[a-z]*|parencite|textcite)\*?\s*(?:\[([^\]]*)\])?\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}',
                   lambda m: '[' + ', '.join(k.strip() for k in m.group(3).split(',')) + ((', ' + (m.group(2) or m.group(1))) if (m.group(2) or m.group(1)) else '') + ']', s)
        s = re.sub(r'\\(?:vskip|hskip|kern)\s*-?[\d.]+\s*(?:pt|ex|em|cm|mm|in|bp|pc|sp)(?:\s*(?:plus|minus)\s*[\d.]+\s*(?:pt|ex|em|fil+))*', '', s)
        s = self.drop_commands(s)
        # accents
        def acc_sym(m):
            letter = m.group(2) or m.group(3)
            letter = {'\\i': 'i', '\\j': 'j'}.get(letter, letter)
            return combine(letter, ACC[m.group(1)])
        s = re.sub(r'\\(["\'`^~=.])\s*(?:\{\s*(\\?[A-Za-z])\s*\}|(\\?[ij](?![A-Za-z])|[A-Za-z]))', acc_sym, s)
        s = re.sub(r'\\([uvHckrdb])(?![A-Za-z])\s*(?:\{\s*([A-Za-z])\s*\}|\s([A-Za-z]))',
                   lambda m: combine(m.group(2) or m.group(3), ACC[m.group(1)]), s)
        # symbols
        s = re.sub(r'\\([A-Za-z]+)(?![A-Za-z])(\s*\{\})?(?:\\ )?', lambda m: self._sym(m), s)
        s = re.sub(r'\\[ ,;:>]', ' ', s)
        s = re.sub(r'\\[!/@\-]', '', s)
        # unknown commands (name dropped, argument text kept)
        def unk(m):
            n = m.group(1)
            if n not in KEEP and n not in DECL: self.unknown_cmds.add('\\' + n)
            return ''
        s = re.sub(r'\\([A-Za-z]+)\*?', unk, s)
        s = re.sub(r'\\(.)', r'\1', s)
        # typography
        s = s.replace('``', '"').replace("''", '"').replace('`', "'")
        s = s.replace('---', ' \u2014 ').replace('--', '\u2013').replace('~', ' ')
        s = s.replace('{', '').replace('}', '')
        return s

    def _sym(self, m):
        n = m.group(1)
        if n in SYMS:
            r = SYMS[n]
            return r + (' ' if m.group(0).endswith('\\ ') and r not in ('', '\n\n', BRK) else '')
        return m.group(0)

    def drop_commands(self, s):
        for name, n in DROP.items():
            while True:
                m = re.search(r'\\%s\*?(?![A-Za-z])\s*(?:\[[^\]]*\])?' % name, s)
                if not m: break
                end = m.end()
                for _ in range(n):
                    g = get_arg(s, end)
                    if not g: break
                    end = g[1]
                s = s[:m.start()] + s[end:]
        return s

    # ---------------------------------------------------------------- header
    def clean(self, t):
        t = self.inline(self.footnotes(t))
        t = self.restore(t).replace(BRK, ', ')
        return re.sub(r'\s+', ' ', t).strip()

    def header(self, title, author, date, rev, dat):
        lines, notes = [], []
        def split_notes(t):
            found = []
            while True:
                m = re.search(r'\\(footnote|thanks)\*?\s*(?:\[[^\]]*\])?\s*\{', t)
                if not m: break
                j = balanced(t, m.end() - 1)
                found.append(t[m.end():j - 1]); t = t[:m.start()] + t[j:]
            return t, found
        if title:
            t, fn = split_notes(title); notes += fn
            lines.append(self.clean(t).upper())
        if author:
            a, fn = split_notes(author); notes += fn
            names = [self.clean(x) for x in re.split(r'\\and(?![A-Za-z])', a)]
            names = [n for n in names if n]
            if names:
                who = ', '.join(names[:-1]) + (' and ' if len(names) > 1 else '') + names[-1]
                lines.append('By ' + who)
        if date:
            d = self.clean(date)
            if d: lines.append(d)
        elif rev:
            lines.append('Revision %s%s' % (rev, ', ' + dat if dat else ''))
        for n in notes: lines.append('(' + self.clean(n).rstrip('.') + '.)')
        return lines

    # ---------------------------------------------------------------- layout
    def para_lines(self, text):
        text = self.restore(text).replace(BRK, '\n')
        out = []
        for ln in text.split('\n'):
            ln = re.sub(r'[ \t\r\f]+', ' ', ln).strip()
            out.append(ln)
        return [l for l in out if l]

    def wrap(self, lines, first, rest):
        res = []
        for k, ln in enumerate(lines):
            res += textwrap.wrap(ln, W, initial_indent=first if k == 0 else rest, subsequent_indent=rest,
                                 break_long_words=False, break_on_hyphens=False) or ['']
        return res

    def layout(self, s):
        out, lists, quote, pending = [], [], 0, None
        tok = re.compile(MK0 + r'([A-Z]+)(.*?)' + MK1, re.S)
        def blank():
            if out and out[-1] != '': out.append('')
        def ind():
            return ' ' * (4 * quote) + '  ' * len(lists)
        def flush_pending():
            nonlocal pending
            if pending is not None:
                out.append((ind() + pending).rstrip()); pending = None
        def text_seg(seg):
            nonlocal pending
            for para in re.split(r'\n[ \t]*\n+', seg):
                lines = self.para_lines(para)
                if not lines: continue
                if lists and pending is not None:
                    lab = pending; pending = None
                    out.extend(self.wrap(lines, ind() + lab, ind() + ' ' * len(lab)))
                    lists[-1]['hang'] = len(lab)
                else:
                    extra = ' ' * lists[-1]['hang'] if lists else ''
                    if lists and out and out[-1] != '' and lists[-1].get('had_text'): out.append('')
                    out.extend(self.wrap(lines, ind() + extra, ind() + extra))
                    if lists: lists[-1]['had_text'] = True
                if not lists: out.append('')
        pos = 0
        for m in tok.finditer(s):
            text_seg(s[pos:m.start()]); pos = m.end()
            kind, payload = m.group(1), m.group(2).lstrip(SEP)
            f = payload.split(SEP)
            if kind == 'H':
                flush_pending(); L, num, title = int(f[0]), f[1], f[2]
                t = (num + '  ' if num else '') + ' '.join(self.para_lines(title))
                blank(); out += [t, UNDERLINE[L] * len(t), '']
            elif kind == 'CAP':
                flush_pending(); blank()
                cap = ' '.join(self.para_lines(f[1])) or '(no caption)'
                out.extend(self.wrap(['[%s: %s]' % (f[0], cap)], ind(), ind() + '  ')); out.append('')
            elif kind == 'TAB':
                flush_pending(); blank(); out.extend(self.render_tab(self.tabs[int(f[0])], ind())); out.append('')
            elif kind == 'VB':
                flush_pending(); blank()
                out.extend(ind() + '    ' + l.expandtabs(4) for l in self.store[int(f[0])].split('\n')); out.append('')
            elif kind == 'DM':
                flush_pending(); blank()
                for l in self.restore(f[0]).replace(BRK, '\n').split('\n'):
                    if l.strip(): out.append(ind() + '    ' + l.strip())
                out.append('')
            elif kind == 'QB': flush_pending(); quote += 1
            elif kind == 'QE': quote = max(0, quote - 1)
            elif kind == 'LB':
                flush_pending()
                if not lists: blank()
                lists.append({'kind': f[0], 'n': 0, 'hang': 0})
            elif kind == 'LE':
                flush_pending()
                if lists: lists.pop()
                if not lists: blank()
            elif kind == 'IT':
                flush_pending()
                if not lists: lists.append({'kind': 'itemize', 'n': 0, 'hang': 0})
                L = lists[-1]; L['n'] += 1; L['had_text'] = False
                lab = f[0].strip() if f else ''
                if L['kind'] == 'enumerate': pending = '%d. ' % L['n']
                elif L['kind'] == 'description': pending = (' '.join(self.para_lines(lab)) + ': ') if lab else '- '
                elif L['kind'] == 'bib': pending = lab + ' '
                else: pending = '- '
                lists[-1]['hang'] = len(pending)
        text_seg(s[pos:])
        flush_pending()
        txt = '\n'.join(l.rstrip() for l in out)
        return re.sub(r'\n{3,}', '\n\n', txt).strip() + '\n'

    def render_tab(self, t, indent):
        rows = [[' '.join(self.para_lines(c)) for c in r] for r in t['rows']]
        ncol = max(len(r) for r in rows)
        rows = [r + [''] * (ncol - len(r)) for r in rows]
        w = [max(len(r[i]) for r in rows) for i in range(ncol)]
        out = []
        for k, r in enumerate(rows):
            out.append((indent + '  ' + ' | '.join(c.ljust(w[i]) for i, c in enumerate(r))).rstrip())
            if k == 0 and t['sep']: out.append(indent + '  ' + '-+-'.join('-' * x for x in w))
        return out


def read_source(path):
    b = open(path, 'rb').read()
    try: return b.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError: return b.decode('latin-1'), 'latin-1'


def main(argv):
    if len(argv) < 2 or argv[1] in ('-h', '--help'):
        print(__doc__); return 0
    src = argv[1]
    dst = argv[2] if len(argv) > 2 else os.path.splitext(src)[0] + '.txt'
    raw, enc = read_source(src)
    name = os.path.basename(src)
    c = Conv(name)
    header, text, body = c.convert(raw, enc)

    notes = ['Plain-text extraction of %s (%s source). LaTeX markup removed; sections, figures, '
             'tables and equations numbered and cross-references resolved.' %
             (name, 'pic+LaTeX' if name.endswith('.ptex') or c.has_pic else 'LaTeX')]
    if c.has_pic: notes.append('Embedded pic/gpic drawing code was removed.')
    if c.has_float: notes.append('Figure captions are kept as [Figure N: ...]; the drawings themselves are not included.')
    if c.includes: notes.append('Files pulled in but not provided: ' + ', '.join(c.includes) + '.')
    if enc == 'latin-1': notes.append('Source was ISO-8859-1; output is UTF-8.')
    if c.unresolved: notes.append('Unresolved references shown as "?": ' + ', '.join(sorted(c.unresolved)) + '.')
    if c.unknown_envs: notes.append('Environments ignored (their text is kept): ' + ', '.join(sorted(c.unknown_envs)) + '.')
    if c.unknown_cmds: notes.append('Unrecognized commands (name dropped, argument text kept): ' + ', '.join(sorted(c.unknown_cmds)) + '.')
    if re.search(r'(?m)^\.[A-Z]{2}\b', text): notes.append('Lines that look like troff/pic preprocessor code remain in the text.')

    # coverage check
    chk = re.sub(r'(?m)^[ \t]*\.PS\b.*?^[ \t]*\.PE\b[^\n]*\n?', '', body, flags=re.S)
    chk = re.sub(r'%.*', '', chk)
    chk = FLOAT_RE.sub(lambda m: re.sub(r'.*?(\\caption\*?\s*\{)', r'\1', m.group(0), flags=re.S) if '\\caption' in m.group(0) else '', chk)
    chk = re.sub(r'\\[A-Za-z]+\*?|[{}$~\\&^_]', ' ', chk)
    src_words, out_words = len(chk.split()), len(text.split())
    ratio = out_words / max(src_words, 1)
    print('coverage: %d words out / %d words in (%.0f%%)' % (out_words, src_words, ratio * 100), file=sys.stderr)
    if ratio < 0.85:
        print('WARNING: much less text extracted than the source seems to contain; '
              'check for unclosed braces or unhandled constructs', file=sys.stderr)
        notes.append('WARNING: the output may be incomplete (extracted only %.0f%% of the expected word count).' % (ratio * 100))
    for what, items in (('unknown commands', c.unknown_cmds), ('unknown environments', c.unknown_envs),
                        ('unresolved references', c.unresolved), ('missing files', c.includes)):
        if items: print('%s: %s' % (what, sorted(items)), file=sys.stderr)

    head = '\n'.join(header)
    note = '[' + textwrap.fill(' '.join(notes), W - 1, break_long_words=False).replace('\n', '\n ') + ']'
    out = (head + '\n\n' if head else '') + note + '\n\n' + text
    open(dst, 'w', encoding='utf-8').write(out)
    print('%s -> %s' % (src, dst), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
```

## Prompt:
What is the cause of this error when processing the attached file? python3 ../wml2txt.py nileug.wml
Traceback (most recent call last):
  File "/Users/ericrangell/Downloads/gzigzag-0.6.3/Documentation/Nile/../wml2txt.py", line 216, in <module>
    main(sys.argv)
    ~~~~^^^^^^^^^^
  File "/Users/ericrangell/Downloads/gzigzag-0.6.3/Documentation/Nile/../wml2txt.py", line 189, in main
    txt = render(p.blocks)
  File "/Users/ericrangell/Downloads/gzigzag-0.6.3/Documentation/Nile/../wml2txt.py", line 177, in render
    elif kind == 'xtable': render_xtable(t, out)
                           ~~~~~~~~~~~~~^^^^^^^^
  File "/Users/ericrangell/Downloads/gzigzag-0.6.3/Documentation/Nile/../wml2txt.py", line 150, in render_xtable
    R = max(r for r, c in cells)
ValueError: max() iterable argument is empty

## Response:
The crash came from the `<xtable>` handling in my script. `nileug.wml` writes its table cells in a different style from `zzspec.wml`, and my parser only knew the `zzspec.wml` style.

- **Old style (`zzspec.wml`):** absolute positions such as `((1,2))`.
- **Style in `nileug.wml`:** relative positions such as `(=,1)`, `(+,1)` and `(=, 2)`, where `=` means the same row or column as the previous cell and `+` means the next one. Cells can also carry attributes like `colspan=2`.

My regex found no cells in the new style, so `max()` was called on an empty list and raised the `ValueError`.

In the fixed `wml2txt.py`:
- **Both styles parse.** The parser understands absolute numbers and `=`, `+`, `-`, plus `colspan`. The three key-binding tables in `nileug.wml` now render with a title row, a rule and aligned columns.
- **No more crash.** If a table can't be parsed at all, the script now prints its text and carries on instead of stopping.

Two other problems turned up in `nileug.txt` on the first run, and I fixed those as well:
- **Headings were swallowed.** The file uses `<doctitle>` and `<s1>`, which come from `catart.wml` (included instead of `article.wml`). I haven't seen that file, so I mapped them to a top-level heading and a section heading. The header note in the output says this is a guess. If you send `catart.wml`, I can check it.
- **`{#MYTOC#}`** is a WML location marker, probably where a table of contents is inserted. It is now removed and listed in the header note.

I also changed how `#include` lines are treated. It now accepts both single and double quotes. It ignores includes that appear before `<body>` as setup files, and it marks includes inside the body as missing content, like `keybindings.wml`.

I re-ran `zzspec.wml`, `ug.wml` and `appw.wml` and their text is unchanged. `nileug.txt` is complete (90% word coverage, because the table cell coordinates count as source words but are rightly dropped).

## Prompt:
Does this file confirm or change any of your findings?

## Response:
`catart.wml` mostly confirms my guesses, but it also shows that my reading of the section headings was incomplete. Let me check which parts of the converter this affects.

Only `nileug.wml` uses `catart.wml`, with two `<s1>` headings. I'll apply what the file shows: numbered headings, the generated contents list, and the two extra heading levels.

`catart.wml` confirms my guesses about its tags, but it also shows that `nileug.txt` was missing the heading numbers and the contents list. I've fixed the converter and regenerated that file.

## What it confirms

- **`<doctitle>` is the document title.** It emits an `<H1>` and also stores the text for the page `<title>`.
- **`<s1>` to `<s3>` are headings**, mapped to `<h2>` to `<h4>`, as I had assumed.
- **`{#MYTOC#}` is a generated table of contents.** Each section adds an entry to that location, and the marker is where the list gets inserted.
- **`catart.wml` plays the same role as `article.wml`.** It includes `common.wml` and `art.css` the same way. The two are alternative setups, and a document picks one.

## What it changes

- **Headings are numbered.** A Perl counter gives `<s1>` the number `1.`, `<s2>` under it `1.1.`, and so on. My earlier `nileug.txt` printed plain "Warning" and "Keystrokes". It now prints "1. Warning" and "2. Keystrokes".
- **The contents list is real content.** The generated list sits right after the intro paragraph (the old output had silently dropped it). The converter now reproduces it as "1. Warning / 2. Keystrokes" at that spot.
- **There are two more heading levels.** `<s4>` and `<s5>` map to `<h5>` and `<h6>`, which my converter didn't know about.
- **`<ref name>` and `<section level label>`** are now supported. A heading like `<s2 mylabel>` can be cited with `<ref mylabel>`, which becomes its number. I tested this on a small synthetic file with nested sections, and it numbered correctly (1., 1.1., 1.2.1., and so on). No file you've given me uses these tags.
- **The assumptions only apply when `catart.wml` is included.** Without that include, `<s1>` and `<doctitle>` are reported as unrecognized tags again, because they only mean something with this macro file.
- **The header note is now accurate.** It no longer mentions `<toc>` and `<warn>` unless the file actually contains them.

## What is still unknown

- **`art.css`, `keybindings.wml` and the `mode` setting** are still missing, as before. None of them affects the text content except `keybindings.wml`.
- **One quirk in `catart.wml`:** it opens a heading as `<h2>` but closes it as `</h1>` (the level numbers are off by one). Browsers tolerate that and it doesn't affect text extraction.

I re-ran `zzspec.wml`, `ug.wml` and `appw.wml`, and their body text is unchanged.

## Prompt:
How do the attached files help your understanding of the WML structure?



### Attachment: art.css _(1.0 KB, text/css)_
````
 body { color: black; background: white; 
 	margin-left: 15%; margin-right: 10%;
	text-align: left; 
	font-size: medium;
	}
 h1 { margin-left: -15%;}
 h2 { margin-left: -15%; margin-top: 2.0em; margin-bottom: 0.5em; }
 h3 { margin-left: -7%;  margin-top: 0.75em; margin-bottom: 0.5em; }
 h4,h5 { margin-left: -0%;  margin-top: 0.5em; margin-bottom: 0.25em; }
 h1, h2, h3, h4, h5, p, ul { font-family: sans-serif; }
 h1, h2, h3, h4, h5 { font-weight: bold; }
 h1 { font-size: xx-large; }
 h2 { font-size: xx-large; }
 h3 { font-size: x-large; }
 h4 { font-size: large; }
 h5 { font-size: medium; }
 dt { font-weight: bold; }
 dfn { font-weight: bold; }
 code { font-family: monospace; }
 .figure { float: right; padding: 1em; padding-bottom: 0em;
 		border: 1pt solid black; margin-left: 1.5em; }
 .figureimg { text-align: center; }
 .abstract { width: 60%; text-align: center; }
 .algorithm { font-family: serif; background: #00E0E0; margin-left: 1cm;}
 span.red { color: red; background: white;}
 span.green { color: green; background: white; }

````

## Response:
Between them, the two files complete the include chain I'd been inferring. `keybindings.wml` is real document content, and `art.css` is only styling.

## The WML build structure

| Layer | Files | Role |
|---|---|---|
| Document | `zzspec.wml`, `ug.wml`, `appw.wml`, `nileug.wml` | HTML plus WML directives |
| Document class | `article.wml` or `catart.wml` | Loads modules, pulls in the macro library, and inlines the CSS |
| Macro library | `common.wml` | The `figure`, `abstract`, `docref` and other custom tags |
| Stylesheet | `art.css` | Appearance only, so it adds nothing to the text |
| Shared content | `keybindings.wml` | Included in the body of two documents |

## What `keybindings.wml` shows

- **It is shared content.** It is a body fragment with an `<h3>` heading, a paragraph and three tables. Both `zzspec.wml` (line 515) and `ug.wml` (line 393) include it with `#include '../keybindings.wml'`. So the two documents repeat the same key-binding section, which I had previously marked as missing content.
- **It confirms my include rule.** Includes before `<body>` are setup files, and includes inside the body bring in text.
- **The `layout=2x40` grid size isn't the row count.** The three tables have 37, 11 and 5 rows, so only the column count (the first number) matters, which is how my converter already treated it.

## What `art.css` shows

- **The abstract styling doesn't work.** `common.wml` emits `class=astract` and `class=abstracthdr`, but the CSS defines `.abstract` and has no `.abstracthdr`. So the typo I saw in `common.wml` is real, and it only affects appearance.
- **No styling carries meaning.** The `.algorithm`, `span.red` and `span.green` classes are never used in the documents I have, so plain text loses nothing.
- **It matches what I'd inferred.**
  - The `dt` term is bold, as I'd assumed, so the swapped `dt`/`dd` list in `zzspec.wml` would show bold definitions in a browser.
  - Headings are styled only up to `h5`. `catart.wml`'s fifth level (`<s5>`) becomes `<h6>`, which has no style.

## What I changed in the converter

- **Includes are expanded in place.** If the included file exists relative to the source, its text is inserted at that spot. If not, the placeholder stays as before. Because your layout puts `keybindings.wml` one folder above the documents, `../keybindings.wml` resolves correctly when you run the script from your checkout.
- **Tables wrap to the page width.** Wide cells (such as the "Binding" column) wrap within the 78-column limit, and the widest column is shrunk when needed.
- **Header rows get a rule line.** A grid whose first row is all bold now has a separator under it.

I regenerated `zzspec.txt` and `ug.txt` with the key-binding tables included. `nileug.txt` and `appw.txt` are unchanged. A comparison with the earlier versions shows the only differences are the new section, with the table now wrapped.

## What is still missing

The only piece I haven't seen is the build command that sets `mode` (the NS4 versus CSS switch), probably in a Makefile or on the `wml` command line. It doesn't affect the text content.

## Prompt:
Can you translate this document to English while using the markup in the document to format it?



### Attachment: byrokratiadoku.txt _(9.0 KB, text/plain)_
````
\documentclass[a4paper,12pt]{artikel3}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage[latin1]{inputenc}
\usepackage[finnish]{babel}
\usepackage{times}
%\def\zigzag{ZigZag}
%\def\zigzag{{\fontfamily{yinit}\fontencoding{U}\fontsize{5}{7pt}\selectfont Z}
%{\huge i}{\fontfamily{yinit}\fontencoding{U}\fontsize{5}{7pt}\selectfont G}
%{\huge}{\fontfamily{cmr}\fontencoding{OMS}\fontsize{30}{30pt}\selectfont  Z}
%{\large$\displaystyle \alpha$\Huge\bf\selectfont$\gamma$}}
%\def\gzigzag{{\it \Huge G}\zigzag}
\def\zigzag{ZigZag}
\def\gzigzag{G\zigzag}
\def\url#1{\texttt{#1}}
\pagestyle{empty}
\begin{document}
{\hfill{}{\Huge Projektisuunnitelma}\hfill{}}
\vspace{1.2cm}

\gzigzag"-projekti tutkii ja soveltaa käytäntöön nykyistä edistyneempiä
tiedonhallintamenetelmiä käyttäen pohjana Ted Nelsonin \zigzag"- ja
Xanadu"-malleja. Lähtökohtana on, että nykyiset
tiedonhallintamenetelmät ovat riittämättömiä vastaamaan tulevaisuuden
haasteisiin. Ryhmän olennaisia tutkimusalueita ovat käyttöliittymät ja
informaation varastointi hyperrakenteisiin, sekä näiden tutkimusten
tulosten soveltaminen käytäntöön.

Suurten tietomäärien hallinta on nykyjärjestelmillä hyvin hankalaa,
koska tiedostojärjestelmässä ainut tiedostojen välinen tieto on
hakemistorakenne. Hakemistorakenne on hierarkia, eikä siksi sovellu
kuin yksinkertaiseen kategorioihin jakamiseen. HTML:ssä hakemistorakenteen
puutteita on korjattu linkeillä, jotka on varastoitu tiedoston sisälle.
Nämä linkit ovat yksisuuntaisia ja rikkoutuvat helposti.

Tietokannat ovat paljon tiedostojärjestelmiä edistyneempi tapa hallita
tietoa.  Ne ovat kuitenkin kovin jäykkiä järjestelmiä: tietokanta
suunnitellaan yleensä yksittäisen sovelluksen käyttöön, eikä sovellu
yleisen tiedon varastointiin; tietokantajärjestelmät eivät tarjoa sen
enempää mahdollisuuksia tietokantojen väliseen linkitykseen kuin
tiedostojärjestelmät; ja tietokantoihin on harvoin pääsyä ulkopuolelta
--- usein ainoastaan WWW-käyttöliittymä on saatavilla.  Tietokantojen
merkittävimmät edut tiedostojärjestelmiin nähden ovat mahdollisuudet
tiedon tehokkaaseen hakuun ja tietojen välisten suhteiden tallennukseen,
mutta ne eivät ole tarpeeksi joustavia yleiseen tiedonhallintaan.

Projektin päätavoitteena on luoda \gzigzag"-ohjelmisto, jonka
päälle voidaan helposti rakentaa tiedon esitys"-, haku"- ja
käyttöominaisuuksiltaan nykyistä parempia ohjelmia. Ohjelmiston pohjana
on \zigzag"-rakenne, joka koostuu soluista ja eri ulottuvuuksia pitkin
tehdyistä kytkennöistä. Rakenteessa tieto on soluissa, joista
kukin sisältää paljon pienemmän osan tiedosta kuin nykyiset tiedostot;
yksi solu sisältää suunnilleen saman verran tietoa kuin
taulukkolaskennan solu.
%Toisin kuin taulukkolaskennassa, kyseessä ei ole kaksiulotteinen soluhila
%vaan moniulotteinen soluavaruus, jossa sama informaatio voi olla kytkettynä
%eri dokumentteihin eri ulottuvuuksia pitkin.
Toisin kuin taulukkolaskennassa, solut on kytketty toisiinsa moniulotteisessa,
joustavassa rakenteessa, jossa jokainen solu voi olla kytkettynä mihin tahansa
soluihin. Rakenteen ulottuvuuksilla voi olla eri merkityksiä,
kuten esimerkiksi ''pöytäkirjan 3141S sisältö'', ''viittaus'',
''tarkennus asiasta kiinnostuneille'', tai ''hakemistorakenne''.
Ulottuvuuksilla ei myöskään ole samanlaisia rajoituksia kuin reaalimaailmassa:
kuljettaessa ensin ylös ja sitten oikealle voidaan päätyä eri paikkaan kuin
kuljettaessa ensin oikealle ja sitten ylös.

Kytkentöjen kaksisuuntaisuus on eräs \zigzag"-rakenteen tärkeimmistä
ominaisuuksista. WWW:ssä, jossa on käytössä yksisuuntaiset linkit, ei ole
mahdollista esimerkiksi lisätä omia reunahuomautuksia sivuihin, tai selata
niitä sivuja, jotka viittaavat tai lainaavat jonkin kappaleen dokumentista.
\zigzag"-järjestelmässä nämä asiat ovat helppoja, ja oheisinformaation
mahdollistaman suodatuksen avulla vältetään myös asian hukkuminen erilaisten
reunahuomautusten ja tarkennusten viidakkoon.

\gzigzag"-ohjelmistoa kehitettäessä on tarkoitus tutkia erilaisten visuaalisten
menetelmien etuja, kun niitä käytetään koko järjestelmän laajuisesti.
Ryhmä pyrkii parantamaan sovellusten käyttöliittymiä jättämällä pois
perinteisen ''ikkunat, valikot ja painonapit'' "-mallin: tieto on
esitettävä kontekstissaan, ei pilkottuna laatikoihin, joilla ei ole
minkäänlaisia keskinäisiä yhteyksiä. Menetelmistä ehkä tärkein onkin
Focus+Context, jonka pääideana on tuoda käyttäjää kullakin
ajanhetkellä kiinnostava tieto (Focus) mahdollsimman korostetusti
esille, ja siihen liittyvät asiat (Context) sen mukaan, miten tärkeitä
ne ovat fokuksen kannalta. Focus+Contextiin liittyy läheisesti
animaatio: kun käyttäjä liikkuu tietorakenteessa, on hyvin tärkeää
näyttää, miten uusi tieto liittyy edelliseen, ja paras tapa näyttää se
on animointi.

Ryhmä kirjoittaa tutkimusten tuloksista artikkeleja kansainvälisiin
konferensseihin ja julkaisuihin, mm. UIST, HICSS ja HT01. Tällä hetkellä on
tekeillä artikkelit Focus+Contextin soveltamisesta viestiketjuihin
ja suureen joukkoon tekstidokumentteja, sekä artikkeli, jossa esitellään
\zigzag"-malli yleisellä tasolla.

%\gzigzag"-ohjelmiston lisenssi on GNU Lesser General Public License,
%sama kuin Linuxin GNU GPL, paitsi että se antaa enemmän mahdollisuuksia
%\gzigzag in käyttöön kaupallisten järjestelmien pohjana. Tällä hetkellä
%toteutus on prototyyppiasteella, ja sen avulla voi kokeilla \zigzag"-rakenteen
%soveltuvuutta erilaisiin tehtäviin.

\gzigzag"-ohjelmiston kehitys on julkista, ja ohjelmistoa levitetään
menestyineiden Linuxin ja Apachen tavoin vapaalla lisenssillä (GNU LGPL). Tällä
hetkellä toteutus on prototyyppiasteella, ja on saatavissa verkosta
osoitteesta \url{http://www.gzigzag.org/}.

Vuoden 2001 loppuun on asetettu seuraavat tavoitteet:
\begin{itemize}
\item{Viesti-, kalenteri-, yms. järjestelmän prototyyppi (Sonera).}
\item{Uudenlaisen tekstinkäsittelyohjelman (Nile) prototyyppi. Nile eroaa
      nykyisistä ohjelmista mm. siten, että tekstiä voidaan lainata
      niin, että lainauksen vieressä näkyy dokumentti, josta lainaus
      on.  Dokumenttiin liittyvät asiat, kuten kuvat, kelluvat tekstin
      vieressä, jolloin pitkäänkin tekstiin liittyvä kuva pysyy koko
      ajan näkyvissä, vaikka tekstiä selaa eteenpäin. Versiointi takaa
      sen, että vanhoja versioita pääsee aina lukemaan, ja
      lainauslinkit (transkluusiot) sen, että intertekstuaaliset
      yhteydet voidaan esittää käyttäjälle ymmärrettävällä tavalla.}
\end{itemize}
Vuoden 2002 loppuun mennessä on tarkoitus toteuttaa \gzigzag"-ohjelmisto
solukielillä (''bootstrap'').  Tämä vaatii ensin tehtävään soveltuvien
solukielten kehittämisen, ja on eräs tärkeimmistä kehitystyön
vaiheista. Solukieliin siirtyminen mahdollistaa selkeän
\zigzag"-rakennetta käsittelevän ohjelmakoodin nopean kirjoittamisen,
ja siksi tämä vaihe on hyvin olennainen sekä tutkimustyön että
\gzigzag"-ohjelmiston kehityksen kannalta.
\newpage
Projektista vastaa FT Tuomas J. Lukka. Tehtävät on jaettu projektin
työntekijöille seuraavasti:

\begin{tabular}{ll}
Katariina Ervasti & Tutkimus humanistisista näkökohdista, dokumentointi ja
                    popularisointi. \\
Tuukka Hastrup & \zigzag in teoria. \\
Antti-Juhani Kaijanaho & Soluavaruuksien versionhallinta, tietoverkot,
                         solukielet ja \zigzag in teoria.\\
Tuomas Lukka & Projektin johto ja kokonaisuuden hallinta. \\
Tero Mäyränen & \zigzag in käyttö multimediasovelluksissa ja solukielet. \\
Vesa Parkkinen & \zigzag in hyödyntäminen kämmenmikroissa ja multimedia. \\
Rauli Ruohonen & Solukielet, \zigzag in teoria ja kämmenmikrot. \\
Kimmo Wideroos & Tietokoneavusteinen oppiminen ja prosessikirjoitus.\\
\end{tabular}

Ryhmä tekee yhteistyötä professori Ted Nelsonin (Keion yliopisto, Japani;
Xanadu, Inc.) ja saksalaisen opiskelijan Benjamin Fallensteinin
kanssa. Professori Nelson yhdessä tohtori Lukan kanssa kehittää
\zigzag"- ja Xanadu"-malleja eteenpäin, ja Fallenstein on mukana
\gzigzag"- ohjelmiston kehitystyössä.

\gzigzag ia ja sen perusajatuksia voidaan periaatteessa hyödyntää minkä tahansa
loppukäyttäjälle suunnatun ohjelmiston tuottamisessa, mutta erityisen hyvin
se soveltuu tietoverkoissa toimiviin järjestelmiin ja integroituihin
järjestelmiin.

Projektiin liittyviä riskejä ovat:
\begin{itemize}
\item{\zigzag in hyödyntämisen jääminen vähäiseksi, koska se eroaa niin paljon
      nykyisistä järjestelmistä, että siihen siirtymisen kynnys voi olla
      korkea.}
\item{Suljettujen tiedon tallennusmenetelmien yleistyminen voi luoda
      esteitä \zigzag in yleistymiselle, sillä ne rajoittavat mahdollisuutta
      tehdä \gzigzag ista yhteensopiva muiden järjestelmien kanssa.
      Suljettuja tallennusmenetelmiä käyttävien ohjelmien tekemiä
      tiedostoja ei voi lukea muilla ohjelmilla.}
\item{Toteutuksen vaikeus.}
\item{Avainhenkilöiden lähteminen projektista.}
\end{itemize}

\end{document}

````

## Response:
Page 1 looks right. I'm checking the staff table on page 3, then I'll deliver the files.

I translated the document into English and kept its LaTeX markup. I compiled the result into a 3-page PDF so you can see the formatting.

**What I kept from the original**
- The `artikel3` class, the original package list and the Latin-1 file encoding.
- The `\zigzag`, `\gzigzag` and `\url` macros.
- The centered `\Huge` title, the `\vspace`, the two `itemize` lists with their `\item{...}` form and the `\newpage` before the staff section.
- The `%` comment lines, which I translated too, including the commented-out license paragraph.

**What I had to change**
- **Language setting:** `babel` is now set to `english`.
- **Finnish hyphenation shorthand:** I removed the `"-` markers (as in `\zigzag"-rakenne`), which only work under Finnish babel. Finnish case endings such as `\zigzag in` ("ZigZag's") became `\zigzag{}` plus English wording, because `\zigzag` followed by a space would otherwise run into the next word.
- **Quotes:** Finnish `''text''` became English ``text''.
- **Staff table:** `{ll}` became `{lp{0.58\textwidth}}`. With `ll`, the long description column ran off the page by about 130pt in English. I couldn't compile your original because Finnish `babel` isn't installed here, so I don't know whether it fit in Finnish.
- **URL sentence:** I rephrased it as "available over the network at …". Compiled the original way, the unbreakable URL stuck out of the margin, and this is a close match to the Finnish wording ("saatavissa verkosta").

**Translation choices**
- "FT" became PhD.
- "Keion yliopisto" became Keio University.
- "kämmenmikro" became palmtop computer.
- "solukieli" became cell language.
- "pöytäkirja" became minutes.
- "prosessikirjoitus" became process writing.
- "transkluusio" became transclusion.
- I translated the sentence saying the LGPL is "the same as Linux's GNU GPL" as written, even though the two licenses differ. It is in a commented-out paragraph in the source.

The PDF has three pages: the plan runs over the first two, and the `\newpage` puts the staff list and risks on page 3.

