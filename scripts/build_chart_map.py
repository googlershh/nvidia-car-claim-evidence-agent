"""Map the in-scope AI Hub accident type codes to the KNIA fault standard charts (차XX-X).

Inputs:
    data/raw/knia/knia_fault_standard_10th_2023.pdf   (scripts/download_knia.py)
    data/interim/accident_codes.csv                   (scripts/build_interim.py)
Outputs:
    data/interim/knia/charts.json          every car-vs-car chart: title, parties, base fault per
                                           variant, modifiers, old (9th edition) numbers. Not in git.
    data/reference/code_to_chart.csv       code -> chart, variant, A/B orientation, applied modifier,
                                           and whether the chart reproduces the AI Hub base fault.
                                           mapping: same (reproduced) | revised (10th edition changed the
                                           value; the chart value is the current one) | uncertain.
                                           chart_fault_a/b is the current (10th edition) base fault and is
                                           the fault ground truth of the reviewed eval set.

The mapping itself (MAP below) was made by reading each chart. The script re-derives the
expected fault from the chart text so every row is checked, not asserted.

Usage:
    python scripts/build_chart_map.py
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.tools.fault import codes_ko, in_scope_codes  # noqa: E402

PDF = ROOT / "data" / "raw" / "knia" / "knia_fault_standard_10th_2023.pdf"
RAW = ROOT / "data" / "interim" / "knia" / "standard_raw.txt"
CHARTS = ROOT / "data" / "interim" / "knia" / "charts.json"
OUT = ROOT / "data" / "reference" / "code_to_chart.csv"

UNCERTAIN = {89}   # no chart clearly matches; kept for reference, fault not scored
T = "삼거리"  # T-junction modifier ("삼거리(T자) 회전/좌회전 +10"): the 10th edition merged the
              # separate T-junction charts of the 9th edition into the cross-road charts

# code: (chart, variant, swap, modifiers, note)
#   swap      True when the code's vehicle A is the chart's vehicle B
#   modifiers substrings of chart modifier names applied on top of the base fault
MAP: dict[int, tuple[str, str, bool, list[str], str]] = {
    0: ("차42-1", "", False, [], "1차 사고로 정차한 앞차를 재추돌"),
    1: ("차41-1", "", False, [], ""),
    2: ("차42-2", "", False, [], "도로 가장자리 주정차 추돌"),
    3: ("차43-1", "", False, [], ""),
    4: ("차52-1", "", False, [], ""),
    5: ("차31-1", "", False, [], ""),
    6: ("차32-1", "", False, [], ""),
    7: ("차45-3", "", False, [], "실선 중앙선 = 앞지르기 금지 장소"),
    8: ("차45-5", "", False, [], ""),
    9: ("차45-4", "", False, [], ""),
    10: ("차45-6", "", False, [], ""),
    11: ("차43-2", "", False, [], ""),
    12: ("차43-3", "", False, [], ""),
    13: ("차43-4", "", False, [], ""),
    14: ("차43-7", "가", False, [], ""),
    15: ("차43-7", "나", False, [], ""),
    16: ("차47-1", "", False, [], ""),
    17: ("차55-2", "", False, [], ""),
    18: ("차55-6", "", False, [], ""),
    19: ("차55-5", "", False, [], ""),
    20: ("차55-7", "", False, [], ""),
    60: ("차1-1", "", False, [], ""),
    61: ("차1-2", "가", False, [], ""),
    62: ("차1-2", "나", False, [], ""),
    63: ("차1-3", "", False, [], ""),
    64: ("차3-3", "", False, [], ""),
    65: ("차1-4", "", False, [], ""),
    66: ("차3-1", "", False, [], ""),
    67: ("차3-2", "", False, [], ""),
    68: ("차3-4", "", False, [], ""),
    69: ("차3-5", "가", False, [], ""),
    70: ("차3-5", "나", False, [], ""),
    71: ("차2-1", "", False, [], ""),
    72: ("차2-4", "", False, [], "적색 동일신호"),
    73: ("차2-2", "", False, [], ""),
    74: ("차2-3", "", False, [], ""),
    75: ("차2-4", "", False, [], "황색 동일신호"),
    76: ("차2-5", "가", False, [], ""),
    77: ("차2-5", "나", False, [], ""),
    78: ("차4-1", "", False, [], ""),
    79: ("차2-6", "", False, [], "10차 기본과실 90:10, AI Hub 80:20"),
    80: ("차6-1", "다", False, [], ""),
    81: ("차6-1", "가", False, [], ""),
    82: ("차6-1", "나", False, [], ""),
    83: ("차5-1", "다", False, [], ""),
    84: ("차5-1", "가", False, [], ""),
    85: ("차5-1", "나", False, [], ""),
    86: ("차6-1", "다", False, [], "차6-1은 직진·좌회전 공통. AI Hub는 좌회전에 10 더 줌"),
    87: ("차6-1", "가", False, [], "차6-1은 직진·좌회전 공통. AI Hub는 좌회전에 10 더 줌"),
    88: ("차6-1", "나", False, [], "차6-1은 직진·좌회전 공통. AI Hub는 좌회전에 10 더 줌"),
    89: ("차13-2", "", False, [], "대응 불확실: 차13-2는 신호 없는 교차로, 기본과실 반대"),
    90: ("차45-1", "", False, [], ""),
    91: ("차33-1", "가", False, [], ""),
    92: ("차33-1", "나", False, [], ""),
    93: ("차33-2", "가", False, [], ""),
    94: ("차33-2", "나", False, [], ""),
    95: ("차46-1", "가", False, [], ""),
    96: ("차46-1", "나", False, [], ""),
    97: ("차47-1", "", False, [], ""),
    98: ("차11-1", "가", False, [], ""),
    99: ("차11-1", "나", False, [], ""),
    100: ("차11-2", "", False, [], ""),
    101: ("차11-4", "", False, [], ""),
    102: ("차11-5", "", False, [], ""),
    103: ("차55-1", "", False, [], ""),
    104: ("차55-3", "", False, [], ""),
    105: ("차55-3", "", False, [], ""),
    106: ("차13-1", "", True, [T], ""),
    107: ("차16-1", "", False, [T], ""),
    108: ("차16-2", "", False, [T], ""),
    109: ("차17-1", "", False, [], ""),
    110: ("차16-3", "", False, [T], ""),
    111: ("차13-3", "", True, [T], ""),
    112: ("차16-4", "", False, [T], ""),
    113: ("차16-5", "", False, [T], ""),
    114: ("차17-2", "", False, [], ""),
    115: ("차13-4", "", True, [T], ""),
    116: ("차17-2", "", True, [], ""),
    117: ("차8-1", "", False, [T], ""),
    118: ("차9-1", "", True, [T], ""),
    119: ("차8-2", "", False, [T], "B는 오른쪽 도로에서 좌회전"),
    120: ("차8-3", "", False, [T], "B는 왼쪽 도로에서 좌회전"),
    121: ("차9-2", "", False, [T], ""),
    122: ("차10-1", "", False, [], ""),
}

VAL = re.compile(r"(\(?[+\-]\)?\s?\d+(?:\s?~\s?\d+)?|비적용)$")
LABELS = set("과실비율조정예시")


def extract_text() -> list[str]:
    if not RAW.exists():
        if not PDF.exists():
            raise SystemExit(f"{PDF} missing; run scripts/download_knia.py")
        RAW.parent.mkdir(parents=True, exist_ok=True)
        # -enc UTF-8 is required: without it the Korean text is dropped
        subprocess.run(["pdftotext", "-enc", "UTF-8", "-raw", str(PDF), str(RAW)], check=True)
    return RAW.read_text(encoding="utf-8").splitlines()


def parse_charts(lines: list[str]) -> dict[str, dict]:
    heads = [i for i, line in enumerate(lines) if re.fullmatch(r"차\d{1,2}-\d{1,2}", line.strip())]
    charts = {}
    for n, i in enumerate(heads):
        no = lines[i].strip()
        blk = [x.strip() for x in lines[i:heads[n + 1] if n + 1 < len(heads) else len(lines)]]
        k = next(x for x, line in enumerate(blk) if line.startswith("기본 과실비율"))
        e = next(x for x, line in enumerate(blk) if line.startswith("※사고발생"))
        body = [x for x in blk[k + 1:e] if x and x not in LABELS]
        text = " ".join([blk[k][len("기본 과실비율"):]] + body)
        head = re.split(r"[①-⑳]|[AB](?=[가-힣(])", text, maxsplit=1)[0]
        variants = re.findall(r"\(([가-하])\)", head) or [""]
        a, b = [int(x) for x in re.findall(r"A\s?(\d{1,3})", head)], [int(x) for x in re.findall(r"B\s?(\d{1,3})", head)]
        if not (len(a) == len(b) == len(variants)):
            raise ValueError(f"{no}: cannot read base fault from {head!r}")
        mods, buf = [], ""
        for line in body:
            buf = f"{buf} {line}".strip()
            m = VAL.search(buf)
            if m:
                name = re.sub(r"^.*?(?=[AB]\s?[가-힣(])", "", buf[:m.start()].strip(), count=1)
                mods.append({"party": name[:1], "name": name[1:].strip(), "value": m.group(1).replace(" ", "")})
                buf = ""
        old = next((x for x in blk if "舊" in x), "")
        charts[no] = {"title": blk[1], "parties": blk[2:k], "fault": {v: [fa, fb] for v, fa, fb in zip(variants, a, b)},
                      "modifiers": mods, "old": re.sub(r"^※\s*舊\s*|\s*기준$", "", old)}
    return charts


def main() -> None:
    charts = parse_charts(extract_text())
    CHARTS.write_text(json.dumps(charts, ensure_ascii=False, indent=1), encoding="utf-8")
    ko = codes_ko()
    scope = in_scope_codes()
    if sorted(MAP) != scope:
        raise SystemExit(f"MAP does not cover the in-scope codes: missing {sorted(set(scope) - set(MAP))}")
    rows = []
    for code in scope:
        chart, variant, swap, mod_keys, note = MAP[code]
        c = charts[chart]
        fa, fb = c["fault"][variant]
        applied = []
        for key in mod_keys:
            m = next(m for m in c["modifiers"] if key in m["name"])
            v = int(re.sub(r"[()+]", "", m["value"]))
            fa, fb = (fa + v, fb - v) if m["party"] == "A" else (fa - v, fb + v)
            applied.append(f"{m['party']} {m['name']} {m['value']}")
        exp_a, exp_b = (fb, fa) if swap else (fa, fb)
        r = ko[code]
        match = (exp_a, exp_b) == (int(r["fault_a"]), int(r["fault_b"]))
        mapping = "uncertain" if code in UNCERTAIN else "same" if match else "revised"
        rows.append({"code": code, "place": r["place_key"], "chart": chart, "variant": variant, "mapping": mapping,
                     "swap_ab": int(swap), "applied_modifiers": "; ".join(applied),
                     "chart_fault_a": exp_a, "chart_fault_b": exp_b,
                     "aihub_fault_a": r["fault_a"], "aihub_fault_b": r["fault_b"], "fault_match": int(match),
                     "chart_title": c["title"], "old_charts": c["old"], "note": note})
    with OUT.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    ok = sum(r["fault_match"] for r in rows)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} codes, {len({r['chart'] for r in rows})} charts, "
          f"base fault reproduced {ok}/{len(rows)} (T-junction modifier applied to {sum(bool(r['applied_modifiers']) for r in rows)})")
    for r in rows:
        if not r["fault_match"]:
            print(f"  mismatch {r['code']:>3} {r['chart']}{'(' + r['variant'] + ')' if r['variant'] else ''}: "
                  f"chart {r['chart_fault_a']}:{r['chart_fault_b']} vs AI Hub {r['aihub_fault_a']}:{r['aihub_fault_b']}  {r['note']}")


if __name__ == "__main__":
    main()
