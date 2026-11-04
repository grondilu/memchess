#!/usr/bin/env python3
"""Build js/openings.js: classify memchess training lines with lichess-org/chess-openings.

Inputs (all in the repo):
  chess-openings/[a-e].tsv  git submodule (columns: eco, name, pgn)
  js/lines.js               training lines (whiteLines / blackLines, spaced SAN)

Output:
  js/openings.js            opening_book, opening_book_moves, opening_positions,
                            opening_roots, whiteLines, blackLines

Classification
  * Every lichess entry is replayed with python-chess (illegal entries abort the
    build) and indexed by position (placement, side to move, castling), so a line
    reaching a named position by transposition still gets the name.
  * A training line belongs to every lichess opening whose position it passes
    through, plus each name-ancestor of those openings
    ("Family: Variation, Sub" -> "Family: Variation" -> "Family"), plus the
    root for its first move ("1. e4", ...).
  * Its own name (the one shown under the board) is the deepest position matched.

Tree: root "1. <move>" -> Family -> "Family: Variation" -> "Family: Variation, Sub"...
A family hangs under the root of the first move most of its lines start with.

Usage: python3 tools/build_openings.py [--check]   (--check: fail if output differs)
"""
import collections, json, re, sys
from pathlib import Path
import chess

ROOT = Path(__file__).resolve().parent.parent
TSV_DIR = ROOT / "chess-openings"
LINES_JS = ROOT / "js" / "lines.js"
OUT = ROOT / "js" / "openings.js"
MIN_CHILD_LINES = 5   # must match OPENING_MIN_LINES in memchess.js (leaf flags)


def poskey(board):
    return " ".join(board.fen().split(" ")[:3])


def pgn_to_san(pgn):
    return [t for t in pgn.split() if not re.fullmatch(r"\d+\.(\.\.)?", t)]


def ancestors(name):
    """'F: V, S1, S2' -> ['F', 'F: V', 'F: V, S1'] (strict ancestors)."""
    if ": " not in name:
        # a few lichess names have no colon: "King's Indian Attack, with Bf5"
        parts = name.split(", ")
        return [", ".join(parts[:i]) for i in range(1, len(parts))]
    fam, rest = name.split(": ", 1)
    parts = rest.split(", ")
    return [fam] + [fam + ": " + ", ".join(parts[:i]) for i in range(1, len(parts))]


def node_id(name):
    return re.sub(r"[^a-zA-Z0-9]", "", name)


def load_lichess():
    entries = []  # (name, san list, poskey, fen)
    by_pos = {}
    for f in sorted(TSV_DIR.glob("[a-e].tsv")):
        rows = f.read_text(encoding="utf-8").splitlines()
        assert rows[0].split("\t")[:3] == ["eco", "name", "pgn"], f
        for row in rows[1:]:
            eco, name, pgn = row.split("\t")[:3]
            b = chess.Board()
            sans = pgn_to_san(pgn)
            for s in sans:
                b.push_san(s)  # raises on illegal move
            k = poskey(b)
            entries.append((name, sans, k, b.fen()))
            by_pos.setdefault(k, name)  # first entry wins for duplicate positions
    return entries, by_pos


def load_lines():
    import subprocess
    js = ("const vm=require('vm'),fs=require('fs');const c={};vm.createContext(c);"
          "vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+"
          "';this.r=JSON.stringify({whiteLines,blackLines})',c);process.stdout.write(c.r)")
    data = json.loads(subprocess.check_output(["node", "-e", js, str(LINES_JS)]))
    out = {}
    for colour in ("whiteLines", "blackLines"):
        d = data[colour]
        seen, lines = set(), []
        for v in d.values():
            for l in v:
                if l not in seen:
                    seen.add(l); lines.append(l)
        out[colour] = lines
    return out


def main():
    entries, by_pos = load_lichess()
    first_fen = {}
    for name, sans, k, fen in entries:   # representative position per name: shortest pgn
        if name not in first_fen or len(sans) < first_fen[name][0]:
            first_fen[name] = (len(sans), fen)
    lines = load_lines()

    members = {"whiteLines": collections.defaultdict(list), "blackLines": collections.defaultdict(list)}
    family_first = collections.defaultdict(collections.Counter)
    stats = {}
    for colour, ls in lines.items():
        depth = collections.Counter(); unclassified = []
        for idx, line in enumerate(ls):
            b = chess.Board(); names = []; deepest = None
            for ply, s in enumerate(line.split(" ")):
                b.push_san(s)   # raises on illegal training line
                n = by_pos.get(poskey(b))
                if n:
                    names.append(n); deepest = (ply + 1, n)
            first = line.split(" ")[0]
            root = "1. " + first
            nodes = {root}
            for n in names:
                nodes.add(n); nodes.update(ancestors(n))
                family_first[(ancestors(n) or [n])[0]][root] += 1
            for n in nodes:
                members[colour][n].append(idx)
            if deepest:
                depth[deepest[0]] += 1
            else:
                unclassified.append(line)
        stats[colour] = (len(ls), depth, unclassified)

    all_names = set(members["whiteLines"]) | set(members["blackLines"])
    parent = {}
    for n in all_names:
        if n.startswith("1. "):
            parent[n] = "0"
        elif ancestors(n):
            parent[n] = ancestors(n)[-1]
        else:
            parent[n] = family_first[n].most_common(1)[0][0]
    ids = collections.defaultdict(list)
    for n in all_names:
        ids[node_id(n)].append(n)
    clash = {k: v for k, v in ids.items() if len(v) > 1}
    assert not clash, clash

    def count(n, c):
        return len(members[c].get(n, []))
    children = collections.defaultdict(list)
    for n, p in parent.items():
        children[p].append(n)

    def fen_for(n):
        if n in first_fen:
            return first_fen[n][1]
        if n.startswith("1. "):
            b = chess.Board(); b.push_san(n[3:]); return b.fen()
        cands = [first_fen[c] for c in all_names if c in first_fen and (n in ancestors(c))]
        return min(cands)[1] if cands else chess.STARTING_FEN

    book = {}
    for n in sorted(all_names):
        w, bl = count(n, "whiteLines"), count(n, "blackLines")
        leaf_w = int(not any(count(c, "whiteLines") >= MIN_CHILD_LINES for c in children[n]))
        leaf_b = int(not any(count(c, "blackLines") >= MIN_CHILD_LINES for c in children[n]))
        book[n] = [n, w, bl, 0, 0, parent[n], 0, 0, leaf_w, leaf_b, fen_for(n)]
    roots = sorted([n for n in all_names if parent[n] == "0"],
                   key=lambda n: -(count(n, "whiteLines") + count(n, "blackLines")))

    rev = subprocess_rev()
    out = []
    out.append("// GENERATED by tools/build_openings.py from chess-openings (lichess-org/chess-openings %s)\n" % rev)
    out.append("// and js/lines.js. Do not edit by hand; rerun the script instead.\n")
    out.append("// opening_book[name] = [name, whiteCount, blackCount, whiteLearnt, blackLearnt, parent ('0' = root),\n")
    out.append("//                       whiteDue, blackDue, whiteLeaf, blackLeaf, fen]\n")
    out.append("var OPENING_MIN_LINES = %d;\n" % MIN_CHILD_LINES)
    out.append("var opening_roots = %s;\n" % json.dumps(roots, ensure_ascii=False))
    out.append("var opening_book = {\n" + ",\n".join(
        json.dumps(k, ensure_ascii=False) + ":" + json.dumps(v, ensure_ascii=False) for k, v in book.items()) + "\n};\n")
    out.append("var opening_book_moves = {};\nfor (var _n in opening_book) opening_book_moves[_n] = _n;\n")
    out.append("var opening_positions = {\n" + ",\n".join(
        json.dumps(k) + ":" + json.dumps(v, ensure_ascii=False) for k, v in sorted(by_pos.items())) + "\n};\n")
    for colour in ("whiteLines", "blackLines"):
        out.append("var %s_all = [\n" % colour + ",\n".join(json.dumps(l) for l in lines[colour]) + "\n];\n")
        out.append("var %s_index = {\n" % colour + ",\n".join(
            json.dumps(n, ensure_ascii=False) + ":" + json.dumps(sorted(v), separators=(",", ":"))
            for n, v in sorted(members[colour].items())) + "\n};\n")
        out.append("var %s = {};\nfor (var _n in %s_index) %s[_n] = %s_index[_n].map(function(i) { return %s_all[i]; });\n"
                   % (colour, colour, colour, colour, colour))
    text = "".join(out)

    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != text:
            sys.exit("js/openings.js is out of date; rerun tools/build_openings.py")
    else:
        OUT.write_text(text, encoding="utf-8")

    print("lichess entries: %d, distinct positions: %d" % (len(entries), len(by_pos)))
    print("chooser nodes: %d (roots: %s)" % (len(book), ", ".join(roots)))
    for colour, (total, depth, unc) in stats.items():
        print("%s: %d lines, classified %d, unclassified %d" % (colour, total, total - len(unc), len(unc)))
        print("  deepest named ply: " + ", ".join("%d:%d" % kv for kv in sorted(depth.items())))
        for l in unc[:10]:
            print("  UNCLASSIFIED: " + l)


def subprocess_rev():
    import subprocess
    try:
        return subprocess.check_output(["git", "-C", str(TSV_DIR), "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


if __name__ == "__main__":
    main()
