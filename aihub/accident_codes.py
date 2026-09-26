"""Accident type code table (0~433) from the 597 dataset manual.

The manual's "1. 대표도면" table lists, per accident type code: accident
object, place, place feature, progress of vehicle A and B, and the base fault
ratio A:B. It is extracted with xpdf's `pdftotext -table` (bundled with Git
for Windows), whose output keeps one "main" line per row holding every column
plus the three numbers; cell text that wraps spills onto the lines above and
below the main line (vertically centred). Column positions are stable within
a page, so fragments are assigned to columns by character offset. Rows are
separated by choosing one boundary line per gap between main lines (a table
row border cuts every column at once), picked by dynamic programming so that
each cell is centred on its main line and has balanced parentheses.

The VL labels' fault ratio equals this table's base fault for 1,235/1,236
files (see docs/HANDOFF.md 7.3), so the table doubles as the ground truth
mapping type -> fault ratio.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .common import find_file

COLUMNS = ("place", "place_feature", "a_progress", "b_progress")
N_CODES = 434

_MAIN_RE = re.compile(r"^(?P<body>.*?\S)\s{2,}(?P<a>\d{1,3})\s+(?P<b>\d{1,3})\s+(?P<code>\d{1,3})\s*$")
_SEGMENT_RE = re.compile(r"\S+(?: \S+)*")
_SKIP_RE = re.compile(r"^\s*-\s*\d+\s*-\s*$|사고장소특징|^\s*A\s+B\s+형\s*$|대표도면")
_OBJECT_RE = re.compile(r"^차대\s*(차|보행자|자전거|이륜차)$")
_UNBALANCED_PENALTY = 3


@dataclass
class AccidentCode:
    code: int
    accident_object: str
    place: str
    place_feature: str
    a_progress: str
    b_progress: str
    fault_a: int
    fault_b: int

    @property
    def place_key(self) -> str:
        """Place without spaces; PDF wraps split words ("사거리교차로(신 호등 없음)")."""
        return re.sub(r"\s", "", self.place)


@dataclass
class _Row:
    line_no: int
    code: int
    fault_a: int
    fault_b: int
    obj: str
    cells: dict[str, list[tuple[int, str]]] = field(default_factory=lambda: {c: [] for c in COLUMNS})


def manual_text(pdf: Path | None = None) -> str:
    pdf = pdf or find_file("597", "*manual*.pdf")
    exe = shutil.which("pdftotext")
    if not exe:
        raise RuntimeError("pdftotext not found (it ships with Git for Windows under mingw64/bin)")
    out = subprocess.run([exe, "-table", "-enc", "UTF-8", str(pdf), "-"], capture_output=True, check=True)
    return out.stdout.decode("utf-8")


def _segments(text: str) -> list[tuple[int, str]]:
    return [(m.start(), m.group()) for m in _SEGMENT_RE.finditer(text.replace("　", " "))]


def _column_starts(main_bodies: list[str]) -> list[int]:
    """The four most common segment start offsets on a page = column starts."""
    counts: dict[int, int] = {}
    for body in main_bodies:
        for start, _ in _segments(body):
            counts[start] = counts.get(start, 0) + 1
    top = sorted(counts, key=lambda s: -counts[s])[:len(COLUMNS)]
    return sorted(top)


def _column_of(start: int, col_starts: list[int]) -> str | None:
    """Column whose start is the greatest one <= start (1 char slack); None = object column."""
    idx = None
    for i, s in enumerate(col_starts):
        if start + 1 >= s:
            idx = i
    return None if idx is None else COLUMNS[idx]


def _well_formed(text: str) -> bool:
    depth = 0
    for ch in text:
        depth += (ch == "(") - (ch == ")")
        if depth < 0:
            return False
    return depth == 0


def _row_cost(main: int, frags: dict[str, list[tuple[int, str]]], lo: int, hi: int) -> float:
    """How badly the fragments on lines [lo, hi) fit a row whose main line is `main`.

    Cells are centred on the main line, except that a two-line cell puts its
    second line below: one line of asymmetry costs little (more if it points up).
    """
    cost = 0.0
    for col_frags in frags.values():
        lines = [ln for ln, _ in col_frags if lo <= ln < hi]
        if not lines:
            continue
        up, down = max(main - min(lines), 0), max(max(lines) - main, 0)
        d = abs(up - down)
        cost += 0.5 * min(d, 1) + 2 * max(d - 1, 0) + (up > down)
        if not _well_formed(" ".join(t for ln, t in col_frags if lo <= ln < hi)):
            cost += _UNBALANCED_PENALTY
    return cost


def _scan_page(lines: list[str], offset: int, mains: dict, frags: dict, objects: dict) -> int:
    """Collect main lines and column fragments of one page.

    Keys are logical line numbers that count only table text lines (no blank
    lines, page footers or headers), so a row cut by a page break stays
    contiguous. Returns the next free logical line number.
    """
    page_mains = {i: m for i, l in enumerate(lines)
                  if (m := _MAIN_RE.match(l)) and int(m["a"]) + int(m["b"]) == 100}
    if not page_mains:
        return offset
    col_starts = _column_starts([m["body"] for m in page_mains.values()])
    ln = offset
    for i, line in enumerate(lines):
        body = page_mains[i]["body"] if i in page_mains else line
        if i not in page_mains and (not line.strip() or _SKIP_RE.search(line)):
            continue
        for start, text in _segments(body):
            col = _column_of(start, col_starts)
            if col is not None:
                frags[col].append((ln, text))
            elif _OBJECT_RE.match(text):
                objects[ln] = text
        if i in page_mains:
            mains[ln] = page_mains[i]
        ln += 1
    return ln


def _split_rows(mains: dict, frags: dict, objects: dict, n_lines: int) -> list[_Row]:
    # DP over row boundaries across all pages: bounds[r] is the first line of row r.
    main_idx = sorted(mains)
    n = len(main_idx)
    first, last = 0, n_lines
    # candidate boundaries between row r-1 and r: any line in (main[r-1], main[r]]
    cands = [[first]] + [list(range(main_idx[r - 1] + 1, main_idx[r] + 1)) for r in range(1, n)] + [[last]]
    best: dict[int, tuple[float, list[int]]] = {first: (0.0, [first])}
    for r in range(n):
        nxt: dict[int, tuple[float, list[int]]] = {}
        for hi in cands[r + 1]:
            for lo, (cost, path) in best.items():
                c = cost + _row_cost(main_idx[r], frags, lo, hi)
                if hi not in nxt or c < nxt[hi][0]:
                    nxt[hi] = (c, path + [hi])
        best = nxt
    bounds = best[last][1]

    rows = []
    for r, i in enumerate(main_idx):
        lo, hi = bounds[r], bounds[r + 1]
        m = mains[i]
        row = _Row(i, int(m["code"]), int(m["a"]), int(m["b"]),
                   next((o for ln, o in objects.items() if lo <= ln < hi), ""))
        for col in COLUMNS:
            row.cells[col] = [(ln, t) for ln, t in frags[col] if lo <= ln < hi]
        rows.append(row)
    return rows


def _repair_page_breaks(codes: list[AccidentCode]) -> None:
    """A row cut by a page break leaves `...(신호등` on one code and `없음) ...` on the next."""
    for prev, cur in zip(codes, codes[1:]):
        for col in COLUMNS:
            a, b = getattr(prev, col), getattr(cur, col)
            if _well_formed(a) or _well_formed(b):
                continue
            words = b.split(" ")
            for k in range(1, len(words)):
                head, tail = " ".join(words[:k]), " ".join(words[k:])
                if _well_formed(f"{a} {head}") and _well_formed(tail):
                    setattr(prev, col, f"{a} {head}")
                    setattr(cur, col, tail)
                    break


def parse(text: str | None = None) -> list[AccidentCode]:
    text = text if text is not None else manual_text()
    begin = re.search(r"대표도면", text)
    end = re.search(r"라벨링데이터\s+구성", text)
    if not begin or not end:
        raise ValueError("code table markers not found in manual text")
    table = text[text.rfind("\n", 0, begin.start()) + 1:end.start()]

    mains: dict = {}
    frags: dict[str, list[tuple[int, str]]] = {c: [] for c in COLUMNS}
    objects: dict[int, str] = {}
    offset = 0
    for page in table.split("\f"):
        offset = _scan_page(page.splitlines(), offset, mains, frags, objects)

    codes: list[AccidentCode] = []
    current_object = ""
    for row in _split_rows(mains, frags, objects, offset):
        current_object = row.obj or current_object
        cells = {c: " ".join(t for _, t in sorted(row.cells[c])) for c in COLUMNS}
        codes.append(AccidentCode(row.code, current_object, **cells, fault_a=row.fault_a, fault_b=row.fault_b))

    found = sorted(c.code for c in codes)
    if found != list(range(N_CODES)):
        missing = sorted(set(range(N_CODES)) - set(found))
        dupes = sorted({c for c in found if found.count(c) > 1})
        raise ValueError(f"code table incomplete: missing {missing[:20]}, duplicated {dupes[:20]}")
    codes.sort(key=lambda c: c.code)
    _repair_page_breaks(codes)
    return codes
