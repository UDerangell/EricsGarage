#!/usr/bin/env python3
"""wml2txt.py - extract readable plain text from Website META Language (.wml) sources.

usage: wml2txt.py INPUT.wml [OUTPUT.txt]

Handles the HTML subset and the custom tags seen in the GZigZag documents
(<figure>, <infigure>, <grid>/<cell>, <xtable>, <toc>, <warn>, <substdims>, ...).
Unknown tags are reported on stderr and in the output header.
"""
import re, sys, textwrap
from html.parser import HTMLParser

W = 78
HEADINGS = {'h1': '=', 'h2': '-', 'h3': '~', 'h4': '.'}
# tags whose text is kept as-is (inline) or that only wrap other content
INLINE = {'code','em','strong','b','i','u','tt','dfn','a','span','cite','sup','sub','small',
          'big','font','center','abbr','kbd','samp','var','html','head','body','title',
          'substdims','dl','ul','ol','table','tr','td','th'}
BLOCK = set(HEADINGS) | {'p','pre','dt','dd','li','br','figure','infigure','include',
                         'xtable','grid','cell','toc','warn','blockquote','abstract'}

def read_source(path):
    b = open(path, 'rb').read()
    try: return b.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError: return b.decode('latin-1'), 'latin-1'

def preprocess(raw, notes):
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    raw = re.sub(r'<!DOCTYPE[^>]*>', '', raw, flags=re.S)
    # WML/Perl filter blocks:  {: [[s/.../.../g]] ... :}   -> keep the body only
    raw = re.sub(r'\{:\s*\[\[.*?\]\]', '', raw, flags=re.S)
    raw = re.sub(r'(?m)^\s*:\}\s*$', '', raw)
    raw = re.sub(r'\{\\em ([^{}]*)\}', r'\1', raw)          # stray TeX in the source
    def inc(m):
        name = m.group(1)
        if 'wmlinc/' in name: return ''                      # macro library: no content
        return '<include name="%s">' % name.split('/')[-1]
    raw = re.sub(r"(?m)^#include\s+'([^']*)'.*$", inc, raw)
    raw = re.sub(r'(?m)^#(use|include|define|undef)\b.*$', '', raw)
    m = re.search(r'<title>(.*?)</title>', raw, re.S)
    title = m.group(1).strip() if m else ''
    raw = re.sub(r'<head>.*?</head>', '', raw, flags=re.S)
    return raw, title

class Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []; self.kind = 'p'; self.buf = []; self.extra = {}
        self.grid = None; self.cell = None
        self.dl = None; self.swapped = False
        self.quote = 0; self.unknown = set()
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
        self.grid['cells'].append((self.cell['span'], t)); self.cell = None
    def back_to_text(self):
        self.flush(); self.kind = 'quote' if self.quote else 'p'
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag not in INLINE and tag not in BLOCK: self.unknown.add(tag)
        if tag in HEADINGS: self.start(tag)
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
        elif tag in ('toc', 'warn', 'body'): self.flush()
    def handle_endtag(self, tag):
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
    rows, row, used = [], [], 0
    for span, txt in cells:
        row.append((span, txt)); used += span
        if used >= cols: rows.append(row); row, used = [], 0
    if row: rows.append(row)
    w = [0] * cols
    for r in rows:
        if len(r) == cols:
            for i, (_, x) in enumerate(r): w[i] = max(w[i], len(x))
    for r in rows:
        if len(r) == 1 and r[0][0] == cols:
            out += ['  ' + r[0][1], '  ' + '-' * (sum(w) + 3 * (cols - 1))]
        else:
            out.append('  ' + ' | '.join(x.ljust(w[i]) for i, (_, x) in enumerate(r)).rstrip())
    out.append('')

def render_xtable(t, out):
    cells = {}
    for m in re.finditer(r'\(\((\d+),\s*(\d+)\)\)\s*(.*?)(?=\(\(|\Z)', t.replace('\n', ' '), re.S):
        cells[(int(m.group(1)), int(m.group(2)))] = m.group(3).strip()
    R = max(r for r, c in cells)
    names = [cells.get((r, 1), '') for r in range(2, R + 1)]
    out.append('  (table: the same topics are the row and column headings; body cells are empty)')
    lw = max(len(n) for n in names) + 4
    out.append('  ' + ' ' * lw + ' '.join(str(i + 1).rjust(2) for i in range(len(names))))
    for i, n in enumerate(names): out.append('  ' + f'{i+1}. {n}'.ljust(lw))
    out.append('')

def render(blocks):
    out = []
    def blank():
        if out and out[-1] != '': out.append('')
    for kind, t, ex in blocks:
        if kind in HEADINGS:
            blank(); out += [t, HEADINGS[kind] * len(t), '']
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
    raw, title = preprocess(raw, notes)
    p = Extractor(); p.feed(raw); p.close(); p.close_cell() if p.grid is not None else None; p.flush()
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
        'were re-laid out as text. Figures appear as [Figure (file): caption]. The <toc>',
        'and <warn> tags, which the WML build expands into generated text, are omitted.']
    if any(b[0] == 'include' for b in p.blocks):
        notes_txt.append('Files pulled in with #include (other than macro libraries) were not provided.')
    if p.swapped:
        notes_txt.append('A definition list had its dt/dd tags swapped in the source; shown as intended.')
    if enc == 'latin-1':
        notes_txt.append('Source was ISO-8859-1; output is UTF-8.')
    if p.unknown:
        notes_txt.append('Unrecognized tags (text kept, markup ignored): ' + ', '.join(sorted(p.unknown)))
        print('unrecognized tags:', sorted(p.unknown), file=sys.stderr)
    header = '[' + '\n'.join(textwrap.fill(' '.join(notes_txt), W).split('\n')) + ']\n\n'
    open(dst, 'w', encoding='utf-8').write(header + txt)
    print(f'{src} -> {dst}: {len(p.blocks)} blocks', file=sys.stderr)

if __name__ == '__main__':
    main(sys.argv)
