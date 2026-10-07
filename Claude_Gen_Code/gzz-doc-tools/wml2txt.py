#!/usr/bin/env python3
"""wml2txt.py - extract readable plain text from Website META Language (.wml) sources.

usage: wml2txt.py INPUT.wml [OUTPUT.txt]

Handles the HTML subset and the custom tags seen in the GZigZag documents
(<figure>, <infigure>, <grid>/<cell>, <xtable>, <toc>, <warn>, <substdims>, ...).
Unknown tags are reported on stderr and in the output header.
"""
import os, re, sys, textwrap
from html.parser import HTMLParser

W = 78
HEADINGS = {'h1': '=', 'h2': '-', 'h3': '~', 'h4': '.', 'h5': '.', 'h6': '.'}
# catart.wml: <doctitle> -> <H1>; <s1>..<s5> -> <section 0..4> -> numbered <h2>..<h6>
CATART = {'doctitle': 'h1', 's1': 'h2', 's2': 'h3', 's3': 'h4', 's4': 'h5', 's5': 'h6'}
# tags whose text is kept as-is (inline) or that only wrap other content
INLINE = {'code','em','strong','b','i','u','tt','dfn','a','span','cite','sup','sub','small',
          'big','font','center','abbr','kbd','samp','var','html','head','body','title',
          'substdims','dl','ul','ol','table','tr','td','th'}
BLOCK = set(HEADINGS) | {'p','pre','dt','dd','li','br','figure','infigure','include',
                         'xtable','grid','cell','toc','warn','blockquote','abstract','mytoc'}

def read_source(path):
    b = open(path, 'rb').read()
    try: return b.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError: return b.decode('latin-1'), 'latin-1'

INC_RE = re.compile(r"""(?m)^#include\s+(['"])([^'"]*)\1.*$""")

def expand_includes(raw, base, expanded, depth=0):
    """Replace #include lines that bring in document content (after <body>, or not under wmlinc/)
    with the file's text when it can be found relative to the including file; leave the line
    in place otherwise so it is reported as missing. Setup includes (macro files) are never expanded."""
    body_pos = raw.lower().find('<body')
    def rep(m):
        name = m.group(2)
        if (body_pos >= 0 and m.start() < body_pos) or (body_pos < 0 and 'wmlinc/' in name): return m.group(0)
        path = os.path.normpath(os.path.join(base, name))
        if depth > 5 or not os.path.isfile(path): return m.group(0)
        sub, _ = read_source(path)
        expanded.append(os.path.basename(path))
        return '\n' + expand_includes(sub, os.path.dirname(path), expanded, depth + 1) + '\n'
    return INC_RE.sub(rep, raw)

def preprocess(raw, notes, catart=False):
    numbers = []
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    raw = re.sub(r'<!DOCTYPE[^>]*>', '', raw, flags=re.S)
    # WML/Perl filter blocks:  {: [[s/.../.../g]] ... :}   -> keep the body only
    raw = re.sub(r'\{:\s*\[\[.*?\]\]', '', raw, flags=re.S)
    raw = re.sub(r'(?m)^\s*:\}\s*$', '', raw)
    raw = re.sub(r'\{\\em ([^{}]*)\}', r'\1', raw)          # stray TeX in the source
    if catart:
        # catart.wml numbers <s1>..<s5> / <section level label> as 1.  1.1.  1.1.1. ...
        counters, labels = [0] * 5, {}
        for m in re.finditer(r'<(?:s([1-5])|section)\b([^>]*)>', raw, re.I):
            toks = m.group(2).split()
            if m.group(1): level, label = int(m.group(1)) - 1, (toks[0] if toks else '')
            else:
                level = int(toks[0]) if toks and toks[0].isdigit() else 0
                label = toks[1] if len(toks) > 1 else ''
            counters[level] += 1
            for k in range(level + 1, 5): counters[k] = 0
            num = ''.join('%d.' % counters[k] for k in range(level + 1))
            numbers.append(num)
            if label: labels[label] = num
        raw = re.sub(r'<ref\s+(\w+)\s*>', lambda m: labels.get(m.group(1), '?'), raw, flags=re.I)
        raw = raw.replace('{#MYTOC#}', '<mytoc>')   # generated list of numbered sections goes here
    # {#NAME#} are WML location markers (e.g. where a generated TOC is inserted)
    locs = sorted(set(re.findall(r'\{#(\w+)#\}', raw)))
    raw = re.sub(r'\{#\w+#\}', '', raw)
    if locs: notes.append('WML location markers removed: ' + ', '.join(locs) + '.')
    # includes before <body> are macro/setup files; includes inside the body bring in content
    body_pos = raw.lower().find('<body')
    def inc(m):
        name = m.group(2)
        if (body_pos >= 0 and m.start() < body_pos) or (body_pos < 0 and 'wmlinc/' in name):
            return ''
        return '<include name="%s">' % name.split('/')[-1]
    raw = re.sub(r"""(?m)^#include\s+(['"])([^'"]*)\1.*$""", inc, raw)
    raw = re.sub(r'(?m)^#(use|include|define|undef)\b.*$', '', raw)
    m = re.search(r'<title>(.*?)</title>', raw, re.S)
    title = m.group(1).strip() if m else ''
    raw = re.sub(r'<head>.*?</head>', '', raw, flags=re.S)
    return raw, title, numbers

class Extractor(HTMLParser):
    def __init__(self, aliases=None, numbers=None):
        super().__init__(convert_charrefs=True)
        self.aliases = aliases or {}; self.numbers = list(numbers or []); self.sec_stack = []; self.seen = set()
        self.blocks = []; self.kind = 'p'; self.buf = []; self.extra = {}
        self.grid = None; self.cell = None
        self.dl = None; self.swapped = False
        self.quote = 0; self.unknown = set(); self.aliased = set()
    def flush(self):
        t = ''.join(self.buf)
        if self.kind == 'pre':
            if t.strip(): self.blocks.append(('pre', t.strip('\n'), self.extra))
        else:
            t = re.sub(r'[ \t\r\f]+', ' ', t.replace('\n', ' ').replace('\x03', '\n'))
            t = '\n'.join(x.strip() for x in t.split('\n')).strip()
            if t: self.blocks.append((self.kind, t, self.extra))
        self.buf = []; self.extra = {}
    def start(self, kind, **extra):
        self.flush(); self.kind = kind; self.extra = extra
    def close_cell(self):
        if self.cell is None: return
        t = re.sub(r'[ \t\r\f\n]+', ' ', ''.join(self.cell['text']))
        t = '\n'.join(x.strip() for x in t.split('\x03')).strip()
        self.grid['cells'].append((self.cell['span'], t))
        self.grid.setdefault('hdr', []).append(bool(self.cell.get('hdr'))); self.cell = None
    def back_to_text(self):
        self.flush(); self.kind = 'quote' if self.quote else 'p'
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        num = None
        if self.aliases:
            if tag == 'section':
                toks = [k for k, v in attrs]
                lvl = int(toks[0]) if toks and toks[0].isdigit() else 0
                self.aliased.add(tag); self.sec_stack.append('h%d' % (lvl + 2)); tag = self.sec_stack[-1]
                num = self.numbers.pop(0) if self.numbers else ''
            elif tag in self.aliases:
                self.aliased.add(tag)
                if re.fullmatch(r's[1-5]', tag): num = self.numbers.pop(0) if self.numbers else ''
                tag = self.aliases[tag]
        if tag not in INLINE and tag not in BLOCK: self.unknown.add(tag)
        if tag in ('toc', 'warn'): self.seen.add(tag)
        if tag in HEADINGS: self.start(tag, **({'num': num} if num else {}))
        elif tag == 'mytoc':
            self.start('toc'); self.buf.append('x'); self.flush(); self.kind = 'p'
        elif tag == 'p': self.start('quote' if self.quote else 'p')
        elif tag == 'pre': self.start('pre')
        elif tag in ('dt', 'dd'):
            if self.dl is None:                     # source sometimes swaps dt/dd
                self.dl = 'swap' if tag == 'dd' else 'normal'
                self.swapped |= self.dl == 'swap'
            if self.dl == 'swap': tag = 'dt' if tag == 'dd' else 'dd'
            self.start(tag)
        elif tag == 'li': self.start('li')
        elif tag in ('dl', 'ul', 'ol'): self.back_to_text(); self.dl = None
        elif tag == 'br':
            (self.cell['text'] if self.cell is not None else self.buf).append('\x03')
        elif tag == 'blockquote': self.quote += 1; self.start('quote')
        elif tag == 'figure': self.start('figure', img=a.get('img', ''))
        elif tag == 'infigure':
            self.start('infigure', img=a.get('img', '')); self.buf.append('x'); self.back_to_text()
        elif tag == 'include':
            self.start('include', name=a.get('name', '')); self.buf.append('x'); self.back_to_text()
        elif tag == 'xtable': self.start('xtable')
        elif tag == 'grid':
            self.flush()
            self.grid = {'cols': int(re.match(r'\d+', a.get('layout', '1x1')).group()), 'cells': []}
        elif tag == 'abstract':
            self.flush(); self.blocks.append(('h2', 'Abstract', {})); self.kind = 'p'
        elif tag == 'cell':
            self.close_cell()
            self.cell = {'span': int((a.get('colspan') or '1').strip()), 'text': []}
        elif tag == 'b' and self.cell is not None and not ''.join(self.cell['text']).strip():
            self.cell['hdr'] = True
        elif tag in ('toc', 'warn', 'body'): self.flush()
    def handle_endtag(self, tag):
        if tag == 'section' and self.aliases and self.sec_stack: tag = self.sec_stack.pop()
        else: tag = self.aliases.get(tag, tag)
        if tag in HEADINGS or tag in ('figure', 'pre', 'xtable'):
            self.back_to_text()
        elif tag == 'blockquote':
            self.flush(); self.quote = max(0, self.quote - 1); self.kind = 'quote' if self.quote else 'p'
        elif tag == 'abstract': self.back_to_text()
        elif tag == 'cell': self.close_cell()
        elif tag == 'grid':
            self.close_cell()                       # tolerate a missing </cell>
            self.blocks.append(('grid', self.grid, {})); self.grid = None; self.kind = 'p'
        elif tag in ('dl', 'ul', 'ol'): self.back_to_text()
    def handle_data(self, d):
        if self.cell is not None: self.cell['text'].append(d); return
        if self.grid is not None: return
        self.buf.append(d)

def wrap(t, ind='', sub=None):
    res = []
    for ln in t.split('\n'):
        res += textwrap.wrap(ln, W, initial_indent=ind,
                             subsequent_indent=ind if sub is None else sub) or ['']
    return res

def render_grid(g, out):
    cols, cells = g['cols'], g['cells']
    filled = [c for c in cells if c[1]]
    if len(filled) <= 1:                                    # layout-only grid (e.g. author block)
        out += ['  ' + l for l in (filled[0][1].split('\n') if filled else [])] + ['']; return
    hdr = g.get('hdr') or [False] * len(cells)
    rows, row, used = [], [], 0
    for (span, txt), h in zip(cells, hdr):
        row.append((span, txt, h)); used += span
        if used >= cols: rows.append(row); row, used = [], 0
    if row: rows.append(row)
    w = [0] * cols
    for r in rows:
        if len(r) == cols:
            for i, (_, x, _h) in enumerate(r): w[i] = max(w[i], max((len(l) for l in x.split('\n')), default=0))
    avail = W - 2 - 3 * (cols - 1)                      # keep the table inside the page width
    if sum(w) > avail:
        k = w.index(max(w)); w[k] = max(15, avail - (sum(w) - w[k]))
    def table_row(texts):
        wrapped = [textwrap.wrap(' '.join(x.split()), w[i]) or [''] for i, x in enumerate(texts)]
        return ['  ' + ' | '.join((wrapped[i][n] if n < len(wrapped[i]) else '').ljust(w[i])
                                  for i in range(len(texts))).rstrip()
                for n in range(max(len(c) for c in wrapped))]
    for k, r in enumerate(rows):
        if len(r) == 1 and r[0][0] == cols:
            out += ['  ' + l for l in textwrap.wrap(r[0][1], W - 2)] + ['  ' + '-' * min(sum(w) + 3 * (cols - 1), W - 2)]
        else:
            out += table_row([x for _, x, _h in r])
            if k == 0 and len(rows) > 1 and all(h for _, _, h in r):      # header row (all cells bold)
                out.append('  ' + '-+-'.join('-' * x for x in w))
    out.append('')

XCELL = re.compile(r'\(\(?\s*([=+\-]|\d+)\s*,\s*([=+\-]|\d+)\s*\)\)?\s*((?:[A-Za-z]+=\d+\s+)*)')

def parse_xtable(t):
    """wml::fmt::xtable cells: (row,col) with absolute numbers or = (same) / + (next) / - (previous),
    then optional attributes (colspan=N rowspan=N) and the cell text up to the next (row,col)."""
    t = t.replace('\n', ' ')
    ms = list(XCELL.finditer(t))
    cells = []; r = c = 0
    for k, m in enumerate(ms):
        def step(v, cur):
            return cur if v == '=' else cur + 1 if v == '+' else cur - 1 if v == '-' else int(v)
        r, c = step(m.group(1), r), step(m.group(2), c)
        end = ms[k + 1].start() if k + 1 < len(ms) else len(t)
        attrs = dict((a.lower(), int(v)) for a, v in re.findall(r'([A-Za-z]+)=(\d+)', m.group(3)))
        cells.append({'r': r, 'c': c, 'span': attrs.get('colspan', 1), 'text': t[m.end():end].strip()})
    return cells

def render_xtable(t, out):
    cells = parse_xtable(t)
    if not cells:                                     # unparseable: keep the text rather than fail
        out += wrap(t, '  ') + ['']; return
    if len(cells) > 3 and all(x['r'] == 1 or x['c'] == 1 for x in cells) and all(x['span'] == 1 for x in cells):
        # matrix whose row and column headings list the same topics, body cells empty
        R = max(x['r'] for x in cells)
        by = {(x['r'], x['c']): x['text'] for x in cells}
        names = [by.get((r, 1), '') for r in range(2, R + 1)]
        out.append('  (table: same topics as rows and columns; body cells empty)')
        lw = max(len(n) for n in names) + 4
        out.append('  ' + ' ' * lw + ' '.join(str(i + 1).rjust(2) for i in range(len(names))))
        for i, n in enumerate(names): out.append('  ' + f'{i+1}. {n}'.ljust(lw))
        out.append(''); return
    ncol = max(x['c'] + x['span'] - 1 for x in cells)
    w = [0] * (ncol + 1)
    for x in cells:
        if x['span'] == 1: w[x['c']] = max(w[x['c']], len(x['text']))
    rows = {}
    for x in cells: rows.setdefault(x['r'], []).append(x)
    total = sum(w[1:]) + 3 * (ncol - 1)
    for r in sorted(rows):
        row = sorted(rows[r], key=lambda x: x['c'])
        if len(row) == 1 and row[0]['span'] == ncol and ncol > 1:
            out += ['  ' + row[0]['text'], '  ' + '-' * max(total, len(row[0]['text']))]
            continue
        parts, c = [], 1
        for x in row:
            while c < x['c']: parts.append(' ' * w[c]); c += 1
            width = sum(w[x['c']:x['c'] + x['span']]) + 3 * (x['span'] - 1)
            parts.append(x['text'].ljust(width)); c = x['c'] + x['span']
        out.append('  ' + ' | '.join(parts).rstrip())
    out.append('')

def render(blocks):
    out = []
    def blank():
        if out and out[-1] != '': out.append('')
    for kind, t, ex in blocks:
        if kind in HEADINGS:
            if ex.get('num'): t = ex['num'] + ' ' + t
            blank(); out += [t, HEADINGS[kind] * len(t), '']
        elif kind == 'toc':
            entries = [b[2]['num'] + ' ' + b[1] for b in blocks if b[0] in HEADINGS and b[2].get('num')]
            out += entries + [''] if entries else []
        elif kind == 'p': out += wrap(t) + ['']
        elif kind == 'quote': out += wrap(t, '    ') + ['']
        elif kind == 'pre': out += ['    ' + l.expandtabs(4) for l in t.split('\n')] + ['']
        elif kind == 'dt': out += wrap(t)
        elif kind == 'dd': out += wrap(t, '    ') + ['']
        elif kind == 'li': out += wrap(t, '  - ', '    ') + ['']
        elif kind == 'figure':
            out += wrap(f'[Figure ({ex["img"]}): {t or "(no caption)"}]', '', '  ') + ['']
        elif kind == 'infigure': out += [f'[Figure ({ex["img"]})]', '']
        elif kind == 'include':
            out += wrap(f'[The build includes the file {ex["name"]} here; that file was not '
                        'provided, so its content is not part of this extraction.]') + ['']
        elif kind == 'xtable': render_xtable(t, out)
        elif kind == 'grid': render_grid(t, out)
    txt = '\n'.join(l.rstrip() for l in out)
    txt = txt.replace(' --- ', ' \u2014 ').replace('.~', '. ')
    return re.sub(r'\n{3,}', '\n\n', txt).strip() + '\n'

def main(argv):
    src = argv[1]; dst = argv[2] if len(argv) > 2 else re.sub(r'\.wml$', '', src) + '.txt'
    raw, enc = read_source(src)
    notes = []
    catart = bool(re.search(r"""(?m)^#include\s+['"][^'"]*catart\.wml""", raw))
    expanded = []
    raw = expand_includes(raw, os.path.dirname(os.path.abspath(src)), expanded)
    if expanded: notes.append('Included content expanded in place: ' + ', '.join(expanded) + '.')
    raw, title, numbers = preprocess(raw, notes, catart)
    p = Extractor(CATART if catart else {}, numbers)
    p.feed(raw); p.close(); p.close_cell() if p.grid is not None else None; p.flush()
    txt = render(p.blocks)
    name = src.split('/')[-1]
    src_words = len(re.sub(r'<[^>]*>', ' ', re.sub(r'<pre>.*?</pre>', lambda m: m.group(0), raw, flags=re.S)).split())
    out_words = len(txt.split())
    ratio = out_words / max(src_words, 1)
    print(f'coverage: {out_words} words out / {src_words} words in ({ratio:.0%})', file=sys.stderr)
    if ratio < 0.85:
        print('WARNING: much less text extracted than the source contains; '
              'check for unclosed tags or unhandled constructs', file=sys.stderr)
    notes_txt = [f'Plain-text extraction of {name} (Website META Language source).',
        'WML directives and HTML tags were removed; headings, lists, tables and figures',
        'were re-laid out as text. Figures appear as [Figure (file): caption].']
    if p.seen: notes_txt.append('The ' + ' and '.join('<%s>' % t for t in sorted(p.seen)) +
        ' tag(s), which the WML build expands into generated text, are omitted.')
    if catart: notes_txt.append('Headings follow catart.wml: <doctitle> is the title and <s1>..<s5> are numbered sections; the generated contents list is reproduced where the document places it.')
    if any(b[0] == 'include' for b in p.blocks):
        notes_txt.append('Files pulled in with #include (other than macro libraries) were not provided.')
    notes_txt.extend(notes)
    if p.swapped:
        notes_txt.append('A definition list had its dt/dd tags swapped in the source; shown as intended.')
    if enc == 'latin-1':
        notes_txt.append('Source was ISO-8859-1; output is UTF-8.')
    if p.unknown:
        notes_txt.append('Unrecognized tags (text kept, markup ignored): ' + ', '.join(sorted(p.unknown)))
        print('unrecognized tags:', sorted(p.unknown), file=sys.stderr)
    header = '[' + textwrap.fill(' '.join(notes_txt), W - 1) + ']\n\n'
    open(dst, 'w', encoding='utf-8').write(header + txt)
    print(f'{src} -> {dst}: {len(p.blocks)} blocks', file=sys.stderr)

if __name__ == '__main__':
    main(sys.argv)
