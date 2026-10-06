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
