"""Synthesise the two statements a handler receives for each synthetic claim.

The AI Hub data has no statements, so for every case of data/interim/synth_cases.jsonl
(scripts/build_synth_cases.py) this builds, from the fault standard charts:

    insured       our policyholder (the other car in the claim) describes the accident
                  consistent     the movements of the reviewed accident type
                  self_serving   the movements of another chart of the same situation, or the
                                 same chart with the roles swapped, that gives the insured a
                                 lower fault (only when one exists)
    counterparty  the claimant's insurer states its fault claim
                  accept         the base fault of the reviewed chart
                  modifier       the reviewed chart plus 1~2 of its modifiers that favour the
                                 claimant (truth unknown: the video must be checked)
                  alt_type       likewise for the claimant (contradicts the video)
                  A claimant with no base fault always accepts.

Ground truth is the type; the agent sees only the text and the claimed chart/ratio
(agent/schemas.py Statement). Fault values are the current (10th edition) standard.

Outputs:
    data/manifests/statements.csv    types and claimed charts per case (tracked in git)
    data/interim/statements.jsonl    full statements with ground truth

Usage:
    python scripts/build_statements.py [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent.tools.fault import chart_label, chart_map, code_modifiers, codes_ko, in_scope_codes  # noqa: E402

SEED = 42
INTERIM = ROOT / "data" / "interim"
CASES = INTERIM / "synth_cases.jsonl"
OUT = INTERIM / "statements.jsonl"
MANIFEST = ROOT / "data" / "manifests" / "statements.csv"
P_SELF_SERVING = 0.3
P_COUNTERPARTY = {"accept": 0.35, "modifier": 0.40, "alt_type": 0.25}
GENERIC = {"현저한과실", "중대한과실"}   # driver-level faults (inattention, drunk driving ...), hard to show on video


def other(role: str) -> str:
    return "B" if role == "A" else "A"


def fault_of(code: int, role: str) -> int:
    ch = chart_map()[code]
    return int(ch["chart_fault_a" if role == "A" else "chart_fault_b"])


def progress(code: int, role: str) -> str:
    r = codes_ko()[code]
    return (r["a_progress"] if role == "A" else r["b_progress"]).strip()


def alternatives(code: int, speaker_role: str) -> list[tuple[int, str]]:
    """(code, speaker role) of the same place and situation (e.g. lane change) that gives the
    speaker a lower fault: another chart, or the same chart with the roles swapped."""
    ko, cm = codes_ko(), chart_map()
    true_fault = fault_of(code, speaker_role)
    return [(k, r) for k in in_scope_codes() for r in "AB"
            if ko[k]["place_key"] == ko[code]["place_key"] and ko[k]["place_feature"] == ko[code]["place_feature"]
            and cm[k]["mapping"] != "uncertain" and fault_of(k, r) < true_fault]


def describe(code: int, me: str) -> str:
    r = codes_ko()[code]
    return (f"{r['place_key']}, {r['place_feature']} 상황입니다. "
            f"제 차는 「{progress(code, me)}」, 상대 차는 「{progress(code, other(me))}」였고 그러다 충돌했습니다.")


def build(case: dict, rng: random.Random) -> dict:
    code, claimant = int(case["video"]["accident_type"]), case["claimant"]
    insured = other(claimant)
    base_insured = fault_of(code, insured)

    # insured statement
    alts = alternatives(code, insured)
    if alts and rng.random() < P_SELF_SERVING:
        k, r = rng.choice(alts)
        ins = {"type": "self_serving", "code": k, "role": r}
    else:
        ins = {"type": "consistent", "code": code, "role": insured}
    ins_stmt = {"source": "insured", "text": "(당사 피보험자) " + describe(ins["code"], ins["role"]),
                "claimed_chart": chart_label(ins["code"]), "claimed_insured_fault": fault_of(ins["code"], ins["role"]),
                "modifiers": [], "truth": ins["type"], "claimed_code": ins["code"]}

    # counterparty claim (speaks for the claimant)
    kind = rng.choices(list(P_COUNTERPARTY), weights=list(P_COUNTERPARTY.values()))[0]
    favour = [(role, name, v) for role, name, v in code_modifiers(code)
              if (role == insured and v > 0) or (role == claimant and v < 0)]
    # prefer modifiers a video can show; fall back to 현저한과실 (inattention etc.), never 중대한과실
    specific = [m for m in favour if m[1] not in GENERIC] or [m for m in favour if m[1] == "현저한과실"]
    alts_c = alternatives(code, claimant)
    if fault_of(code, claimant) == 0:   # the claimant already bears no fault: nothing to dispute
        kind = "accept"
    if kind == "alt_type" and not alts_c:
        kind = "modifier"
    if kind == "modifier" and not specific:
        kind = "accept"
    mods: list[dict] = []
    claim_code, claim_role = code, claimant
    if kind == "alt_type":
        claim_code, claim_role = rng.choice(alts_c)
    elif kind == "modifier":
        picked = rng.sample(specific, k=min(len(specific), rng.choice([1, 2])))
        mods = [{"party": "insured" if role == insured else "claimant", "name": name, "value": v}
                for role, name, v in picked]
    claim_insured = 100 - fault_of(claim_code, claim_role)
    ratio = claim_insured
    for m in mods:
        ratio += m["value"] if m["party"] == "insured" else -m["value"]
    ratio = max(0, min(100, ratio))
    text = "(상대 보험사) 당사 고객 진술: " + describe(claim_code, claim_role)
    if mods:
        text += " 또한 " + ", ".join(f"{'귀사 고객' if m['party'] == 'insured' else '당사 고객'}의 "
                                    f"'{m['name']}'({m['value']:+d})" for m in mods) + "을(를) 주장합니다."
    text += f" 과실비율 귀사:당사 = {ratio}:{100 - ratio}을 요청합니다."
    cp_stmt = {"source": "counterparty", "text": text, "claimed_chart": chart_label(claim_code),
               "claimed_insured_fault": claim_insured, "modifiers": mods, "truth": kind, "claimed_code": claim_code}
    return {"case_id": case["case_id"], "video_code": code, "claimant": claimant, "video_chart": chart_label(code),
            "base_insured_fault": base_insured, "statements": [ins_stmt, cp_stmt]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    if not CASES.exists():
        raise SystemExit(f"{CASES} missing; run scripts/build_synth_cases.py")
    cases = [json.loads(line) for line in CASES.open(encoding="utf-8")]
    rows = []
    with OUT.open("w", encoding="utf-8") as f:
        for case in cases:
            rng = random.Random(f"{args.seed}:{case['case_id']}:statements")
            s = build(case, rng)
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
            ins, cp = s["statements"]
            rows.append({"case_id": s["case_id"], "video_chart": s["video_chart"],
                         "insured_type": ins["truth"], "insured_claimed_chart": ins["claimed_chart"],
                         "counterparty_type": cp["truth"], "counterparty_claimed_chart": cp["claimed_chart"],
                         "counterparty_modifiers": "; ".join(f"{m['party']} {m['name']} {m['value']:+d}" for m in cp["modifiers"])})
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} and {MANIFEST.relative_to(ROOT)}: {len(rows)} cases")
    print("  insured", dict(Counter(r["insured_type"] for r in rows)))
    print("  counterparty", dict(Counter(r["counterparty_type"] for r in rows)))


if __name__ == "__main__":
    main()
