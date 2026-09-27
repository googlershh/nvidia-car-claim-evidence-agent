"""Load synthetic claims (scripts/build_synth_cases.py) as pipeline inputs + separate ground truth."""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .schemas import ClaimBundle, EstimateLine

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "data" / "interim" / "synth_cases.jsonl"
MEDIA = ROOT / "data" / "interim" / "media"
SEED = 42


@dataclass
class GroundTruth:
    case_id: str
    case_type: str                   # normal | inflated | contradiction
    expected_route: str              # approve | adjust | siu
    accident_type: int
    fault_a: int
    fault_b: int
    photo_parts: list[str]           # damage-label repair parts (what the photos show)
    injected: list[str]              # names of injected estimate lines
    approved_total: int              # loss adjuster's approved amount (items, before VAT)
    real_adjusted: bool


def _int(v) -> int:
    return int(v) if v not in ("", None) else 0


def _line(item: dict) -> EstimateLine:
    no = item.get("no")
    return EstimateLine(no=int(no) if str(no).isdigit() else None, name=item["name"], work=item["work"],
                        claimed_part=_int(item["claimed_part"]), claimed_labor=_int(item["claimed_labor"]))


def to_bundle(case: dict) -> tuple[ClaimBundle, GroundTruth]:
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
    )
    truth = GroundTruth(
        case_id=case["case_id"], case_type=case["case_type"], expected_route=case["expected_route"],
        accident_type=int(video["accident_type"]), fault_a=int(video["fault_a"]), fault_b=int(video["fault_b"]),
        photo_parts=list(case["photo_parts"]), injected=[i["name"] for i in case["injected_items"]],
        approved_total=int(case["approved_total"]), real_adjusted=bool(case["real_adjusted"]),
    )
    return bundle, truth


def iter_cases(path: Path = CASES) -> Iterator[tuple[ClaimBundle, GroundTruth]]:
    if not path.exists():
        raise FileNotFoundError(f"{path} missing; run scripts/build_synth_cases.py")
    with path.open(encoding="utf-8") as f:
        for line in f:
            yield to_bundle(json.loads(line))
