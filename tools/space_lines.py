#!/usr/bin/env python3
"""One-off converter: rewrite concatenated SAN lines ("e4c5Nf3") as space-separated
("e4 c5 Nf3"). Each line is tokenized by replaying it with python-chess (legal moves
only, with backtracking), so tokenization is exact. Usage: tools/space_lines.py FILE...
Strings that are not a legal concatenated SAN sequence are left untouched and reported."""
import re, sys, chess

STR = re.compile(r'"((?:[^"\\\n]|\\.)*)"')            # every JS/JSON string literal
LOOKS = re.compile(r'^(?:O-O(?:-O)?|[KQBNR]?[a-h1-8x=QBNR+#]+)+$')
cache = {}

def strip(s): return s.rstrip('+#')

def tokenize(text, board=None):
    """Return list of SAN tokens (spelled exactly as in text) or None."""
    if text in cache: return cache[text]
    board = board or chess.Board()
    def rec(rest):
        if not rest: return []
        cands = []
        for mv in board.legal_moves:
            san = strip(board.san(mv))
            if rest.startswith(san):
                n = len(san)
                while n < len(rest) and rest[n] in '+#': n += 1
                cands.append((mv, rest[:n]))
        for mv, tok in sorted(cands, key=lambda c: -len(c[1])):
            board.push(mv); r = rec(rest[len(tok):]); board.pop()
            if r is not None: return [tok] + r
        return None
    res = rec(text)
    cache[text] = res
    return res

def convert(src, fails):
    count = [0]
    def sub(m):
        s = m.group(1)
        if not s or not LOOKS.match(s) or not re.search(r'[a-h][1-8]|O-O', s):
            return m.group(0)
        toks = tokenize(s)
        if toks is None or ''.join(toks) != s:
            fails.append(s); return m.group(0)
        count[0] += 1
        return '"' + ' '.join(toks) + '"'
    return STR.sub(sub, src), count[0]

if __name__ == '__main__':
    sys.setrecursionlimit(10000)
    for path in sys.argv[1:]:
        src = open(path, encoding='utf-8').read(); fails = []
        if path.endswith('white-lines'):     # plain text, one line per row
            out, n = [], 0
            for row in src.split('\n'):
                t = tokenize(row) if row else []
                if row and (t is None or ''.join(t) != row): fails.append(row); out.append(row)
                else: out.append(' '.join(t)); n += bool(row)
            dst = '\n'.join(out)
        else:
            dst, n = convert(src, fails)
        open(path, 'w', encoding='utf-8').write(dst)
        print(f'{path}: {n} strings converted, {len(fails)} failed')
        for f in fails: print('  FAILED:', f)
