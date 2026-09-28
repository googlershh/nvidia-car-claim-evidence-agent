"""Load synthetic claims (scripts/build_synth_cases.py) as pipeline inputs + separate ground truth."""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .schemas import ClaimBundle, EstimateLine, Modifier, Statement

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "interim" / "synth_cases.jsonl"
STATEMENTS = ROOT / "data" / "interim" / "statements.jsonl"   # scripts/build_statements.py
MEDIA = ROOT / "data" / "interim" / "media"
SEED = 42


@dataclass
class GroundTruth:
    case_id: str
    case_type: str                   # normal | inflated | contradiction
    expected_route: str              # approve | adjust | siu
    accident_type: int
    fault_a: int                     # current fault standard (10th edition) base fault
    fault_b: int
    photo_parts: list[str]           # damage-label repair parts (what the photos show)
    injected: list[str]              # names of injected estimate lines
    approved_total: int              # loss adjuster's approved amount (items, before VAT)
    real_adjusted: bool
    claimant_role: str = "B"         # table vehicle of the filming car, from the label review
    fault_scored: bool = True        # False when no fault standard chart clearly matches the code
    insured_statement: str = ""      # consistent | self_serving
    counterparty_claim: str = ""     # accept | modifier | alt_type

    @property
    def claimant_fault(self) -> int:
        return self.fault_b if self.claimant_role == "B" else self.fault_a


def _int(v) -> int:
    return int(v) if v not in ("", None) else 0


def _line(item: dict) -> EstimateLine:
    no = item.get("no")
    return EstimateLine(no=int(no) if str(no).isdigit() else None, name=item["name"], work=item["work"],
                        claimed_part=_int(item["claimed_part"]), claimed_labor=_int(item["claimed_labor"]))


def _statement(s: dict) -> Statement:
    return Statement(source=s["source"], text=s["text"], claimed_chart=s["claimed_chart"],
                     claimed_insured_fault=int(s["claimed_insured_fault"]),
                     modifiers=[Modifier(m["party"], m["name"], int(m["value"])) for m in s["modifiers"]])


def to_bundle(case: dict, statements: dict | None = None) -> tuple[ClaimBundle, GroundTruth]:
    lines = [_line(i) for i in case["estimate_items"]]
    rng = random.Random(f"{SEED}:{case['case_id']}")
    for inj in case["injected_items"]:           # hide injected lines at a fixed pseudo-random position
        lines.insert(rng.randint(0, len(lines)), _line({**inj, "no": None}))
    for i, line in enumerate(lines, 1):
        line.no = i
    video = case["video"]
    bundle = ClaimBundle(
        case_id=case["case_id"],
        video=MEDIA / "videos" / f"{video['video_name']}.mp4",
        photos=[MEDIA / "images" / name for name in case["images"]],
        estimate=lines,
        car_name=case.get("car_name", ""),
        statements=[_statement(s) for s in statements["statements"]] if statements else [],
    )
    truth_of = {s["source"]: s["truth"] for s in statements["statements"]} if statements else {}
    truth = GroundTruth(
        case_id=case["case_id"], case_type=case["case_type"], expected_route=case["expected_route"],
        accident_type=int(video["accident_type"]), fault_a=int(video["fault_a"]), fault_b=int(video["fault_b"]),
        photo_parts=list(case["photo_parts"]), injected=[i["name"] for i in case["injected_items"]],
        approved_total=int(case["approved_total"]), real_adjusted=bool(case["real_adjusted"]),
        claimant_role=case.get("claimant", "B"), fault_scored=bool(int(video.get("fault_scored", 1))),
        insured_statement=truth_of.get("insured", ""), counterparty_claim=truth_of.get("counterparty", ""),
    )
    return bundle, truth


def iter_cases(path: Path = CASES) -> Iterator[tuple[ClaimBundle, GroundTruth]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run scripts/build_synth_cases.py")
    statements = {}
    if STATEMENTS.exists():
        statements = {s["case_id"]: s for s in map(json.loads, STATEMENTS.open(encoding="utf-8"))}
    with path.open(encoding="utf-8") as f:
        for line in f:
            case = json.loads(line)
            yield to_bundle(case, statements.get(case["case_id"]))
