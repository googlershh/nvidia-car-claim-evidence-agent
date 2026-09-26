"""Sample the fault-judgement evaluation set from the 597 validation labels.

Pool: validation labels of the three in-scope places, blackbox first-person
video (the filming car is vehicle B, the claimant), excluding label noise
(fault ratio != code table base fault, code place != zip place, or a code
whose accident object is not car-to-car).
Per place, draw N cases cycling over fault ratio values so ratios are spread
evenly, and within a ratio prefer the accident type drawn least so far.

Outputs:
    data/manifests/eval_fault.csv   video names + place (tracked in git)
    data/interim/eval_fault.csv     same rows with labels (regenerable)

Usage:
    python scripts/build_eval_fault.py [--per-place 50] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aihub.common import INTERIM_DIR  # noqa: E402

PLACES = ("직선도로", "사거리교차로(신호등있음)", "T자형교차로")
SEED = 42


def load_pool() -> list[dict]:
    path = INTERIM_DIR / "video_labels.csv"
    if not path.exists():
        raise FileNotFoundError("run scripts/build_interim.py first")
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with (INTERIM_DIR / "accident_codes.csv").open(encoding="utf-8-sig", newline="") as f:
        car_to_car = {r["code"] for r in csv.DictReader(f) if r["accident_object"] == "차대차"}
    return [
        r for r in rows
        if r["split"] == "val" and r["zip_object"] == "차대차" and r["accident_type"] in car_to_car
        and r["zip_place"] in PLACES
        and r["filming_way"] == "bb" and r["point_of_view"] == "1"
        and r["fault_matches_code"] == "True" and r["place_matches_zip"] == "True"
    ]


def sample_place(rows: list[dict], n: int, rng: random.Random) -> list[dict]:
    by_fault: dict[str, list[dict]] = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["video_name"]):
        by_fault[r["fault_a"]].append(r)
    for bucket in by_fault.values():
        rng.shuffle(bucket)
    order = sorted(by_fault, key=int)
    rng.shuffle(order)

    picked: list[dict] = []
    type_count: Counter = Counter()
    while len(picked) < n and any(by_fault.values()):
        for fault in order:
            bucket = by_fault[fault]
            if not bucket or len(picked) >= n:
                continue
            least = min(type_count[r["accident_type"]] for r in bucket)
            choice = next(r for r in bucket if type_count[r["accident_type"]] == least)
            bucket.remove(choice)
            type_count[choice["accident_type"]] += 1
            picked.append(choice)
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-place", type=int, default=50)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

    pool = load_pool()
    rng = random.Random(args.seed)
    eval_rows = []
    for place in PLACES:
        rows = [r for r in pool if r["zip_place"] == place]
        picked = sample_place(rows, args.per_place, rng)
        eval_rows.extend(picked)
        print(f"{place}: pool {len(rows)}, picked {len(picked)}, "
              f"types {len({r['accident_type'] for r in picked})}, "
              f"fault_a {dict(sorted(Counter(int(r['fault_a']) for r in picked).items()))}")

    for i, r in enumerate(eval_rows, 1):
        r["eval_id"] = f"F{i:03d}"
    manifest = ROOT / "data" / "manifests" / "eval_fault.csv"
    with manifest.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["eval_id", "video_name", "zip_place"])
        w.writerows([r["eval_id"], r["video_name"], r["zip_place"]] for r in eval_rows)
    full = INTERIM_DIR / "eval_fault.csv"
    with full.open("w", encoding="utf-8-sig", newline="") as f:
        cols = ["eval_id"] + [k for k in eval_rows[0] if k != "eval_id"]
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(eval_rows)
    print(f"wrote {len(eval_rows)} rows -> {manifest.relative_to(ROOT)}, {full.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
