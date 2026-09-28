"""Pair evaluation videos with damage photos + estimates into synthetic claims.

The 597 videos and 581 damage photos come from different accidents, so each
synthetic claim joins one video of the reviewed fault-eval set (the filming car
is the claimant) with one SOCAR accident from VL_damage (photos + estimate with
the loss adjuster's approved amounts). Only clips whose label was confirmed on
video are used (data/interim/eval_fault_reviewed.csv, scripts/build_eval_reviewed.py);
there the claimant is table vehicle B, or A where the review found the roles
swapped. The video labels' damage_location is empty, so the claimant's plausible
impact directions come from data/reference/collision_areas.csv and photo parts
are mapped with aihub.parts.

Case types (fixed seed):
    normal         photos consistent with the claimant's impact directions
    inflated       normal + 1~2 replacement items injected from another
                   estimate of the same car (parts facing no photographed
                   direction but plausible for the collision)
    contradiction  photos facing none of the claimant's impact directions (prefers
                   high/medium confidence accident types)

Expected route: contradiction -> siu; inflated, or a real adjustment in the
estimate -> adjust; otherwise approve.

Outputs:
    data/manifests/synth_cases.csv   ids only (tracked in git)
    data/interim/synth_cases.jsonl   full cases with ground truth

Usage:
    python scripts/build_synth_cases.py [--normal 56 --inflated 18 --contradiction 18] [--seed 42]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aihub.common import INTERIM_DIR  # noqa: E402
from aihub.parts import en_part_directions, fits, ko_item_directions  # noqa: E402

SEED = 42
CONFIDENCE_RANK = {"high": 0, "medium": 1, "low": 2}
INJECT_WORK = "교환"
INJECT_MIN_AMOUNT = 30_000     # sc- estimates put part prices on separate rows, so 교환 rows are mostly labour
REPAIR_WORK = {"교환", "판금", "수리"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def to_int(v: str) -> int:
    return int(v) if v not in ("", None) else 0


def load_collision_areas() -> dict[str, dict]:
    rows = read_csv(ROOT / "data" / "reference" / "collision_areas.csv")
    return {r["code"]: {"a": set(r["a_areas"].split(";")), "b": set(r["b_areas"].split(";")),
                        "confidence": r["confidence"]} for r in rows}


def clean_estimate(h: dict) -> bool:
    """Estimate whose item-level claimed/approved amounts explain its header totals.

    Drops sc- estimates with blank pre-adjustment amounts, and ones where the
    header 청구액 > 지급액 gap is not visible item by item (rate-level cuts),
    or vice versa, so the ground truth is unambiguous.
    """
    header_gap = to_int(h["claimed_total"]) > to_int(h["total"])
    return h["pre_amounts_complete"] == "True" and (h["has_adjustment"] == "True") == header_gap


def load_accidents() -> dict[str, dict]:
    """SOCAR accidents in VL_damage with a clean estimate: photos, parts, directions."""
    estimates = {r["estimate_id"]: r for r in read_csv(INTERIM_DIR / "estimates.csv")
                 if r["source"] == "sc" and clean_estimate(r)}
    acc: dict[str, dict] = {}
    with (INTERIM_DIR / "damage_images.jsonl").open(encoding="utf-8") as f:
        for line in f:
            img = json.loads(line)
            aid = img["accident_id"]
            if aid not in estimates:
                continue
            a = acc.setdefault(aid, {"accident_id": aid, "images": [], "parts": set(), "car_size": img["car_size"],
                                     "estimate": estimates[aid]})
            a["images"].append(img["image_file"])
            a["parts"].update(img["repair"])
    for a in acc.values():
        a["parts"] = sorted(a["parts"])
        a["part_dirs"] = [en_part_directions(p) for p in a["parts"]]
        a["photo_dirs"] = set().union(*a["part_dirs"]) if a["part_dirs"] else set()
    return {k: v for k, v in acc.items() if v["photo_dirs"] and to_int(v["estimate"]["n_items"]) > 0}


def estimate_directions(items: list[dict]) -> set[str]:
    """Directions of the parts an estimate repairs (removal/refit and paint rows excluded)."""
    dirs: set[str] = set()
    for i in items:
        if i["work"] in REPAIR_WORK:
            dirs |= ko_item_directions(i["name"])
    return dirs


def load_items(ids: set[str]) -> dict[str, list[dict]]:
    items: dict[str, list[dict]] = defaultdict(list)
    for r in read_csv(INTERIM_DIR / "estimate_items.csv"):
        if r["estimate_id"] in ids:
            items[r["estimate_id"]].append(r)
    return items


def item_amounts(items: list[dict]) -> tuple[int, int]:
    claimed = sum(to_int(i["claimed_part"]) + to_int(i["claimed_labor"]) for i in items)
    approved = sum(to_int(i["approved_part"]) + to_int(i["approved_labor"]) for i in items)
    return claimed, approved


def assign_types(videos: list[dict], areas: dict, counts: dict[str, int], rng: random.Random) -> dict[str, str]:
    order = videos[:]
    rng.shuffle(order)
    order.sort(key=lambda v: CONFIDENCE_RANK[areas[v["accident_type"]]["confidence"]])  # stable: shuffled within rank
    types = {v["eval_id"]: "contradiction" for v in order[:counts["contradiction"]]}
    rest = order[counts["contradiction"]:]
    rng.shuffle(rest)
    for i, v in enumerate(rest):
        types[v["eval_id"]] = "inflated" if i < counts["inflated"] else "normal"
    return types


def pick_injection(case_items: list[dict], acc: dict, allowed: set[str], donors: list[dict],
                   rng: random.Random) -> list[dict]:
    """1~2 replacement items from other estimates of the same car, facing no photographed direction."""
    claimed_names = {i["name"] for i in case_items}
    candidates = []
    for d in donors:
        dirs = ko_item_directions(d["name"])
        amount = to_int(d["claimed_part"]) + to_int(d["claimed_labor"])
        if (d["work"] == INJECT_WORK and amount >= INJECT_MIN_AMOUNT and dirs and dirs & allowed
                and not dirs <= acc["photo_dirs"] and d["name"] not in claimed_names):
            candidates.append(d)
    if not candidates:
        return []
    rng.shuffle(candidates)
    k = rng.choice((1, 2))
    picked, names = [], set()
    for c in candidates:
        if c["name"] not in names:
            picked.append(c)
            names.add(c["name"])
        if len(picked) == k:
            break
    return picked


def main() -> None:
    ap = argparse.ArgumentParser()
    # 92 reviewed clips, split about 60/20/20 as before
    ap.add_argument("--normal", type=int, default=56)
    ap.add_argument("--inflated", type=int, default=18)
    ap.add_argument("--contradiction", type=int, default=18)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()
    counts = {"normal": args.normal, "inflated": args.inflated, "contradiction": args.contradiction}
    rng = random.Random(args.seed)

    areas = load_collision_areas()
    reviewed = INTERIM_DIR / "eval_fault_reviewed.csv"
    if not reviewed.exists():
        raise SystemExit(f"{reviewed} missing; run scripts/build_eval_reviewed.py")
    videos = [v for v in read_csv(reviewed) if v["accident_type"] in areas]
    if len(videos) < sum(counts.values()):
        raise SystemExit(f"only {len(videos)} eval videos with collision areas; need {sum(counts.values())}")
    videos = sorted(videos, key=lambda v: v["eval_id"])[:sum(counts.values())]
    accidents = load_accidents()
    items = load_items(set(accidents))
    n_clean = len(accidents)
    # photos in the dataset do not always show every repaired part; keep accidents whose
    # repaired parts all face a photographed direction so "not in photos" means injected
    accidents = {aid: a for aid, a in accidents.items()
                 if estimate_directions(items[aid]) <= a["photo_dirs"]}
    print(f"pool: {len(videos)} videos; SOCAR accidents with photos + clean estimate {n_clean}, "
          f"estimate covered by photos {len(accidents)}")

    types = assign_types(videos, areas, counts, rng)
    by_car: dict[str, list[str]] = defaultdict(list)
    for aid, a in accidents.items():
        by_car[a["estimate"]["car_name"]].append(aid)

    acc_ids = sorted(accidents)
    used: set[str] = set()
    plan = []
    for v in videos:
        allowed = areas[v["accident_type"]][v["ego_role"].lower()]
        want = "contradiction" if types[v["eval_id"]] == "contradiction" else "consistent"
        pool = [aid for aid in acc_ids if aid not in used and fits(accidents[aid]["part_dirs"], allowed) == want]
        if not pool:
            raise SystemExit(f"{v['eval_id']}: no {want} accident left for directions {allowed}")
        aid = rng.choice(pool)
        used.add(aid)
        plan.append((v, aid, allowed))

    generic_donors = [i for eid in acc_ids for i in items[eid]]

    cases, manifest = [], []
    for n, (v, aid, allowed) in enumerate(plan, 1):
        acc = accidents[aid]
        case_type = types[v["eval_id"]]
        case_items = items[aid]
        claimed, approved = item_amounts(case_items)
        real_adjusted = acc["estimate"]["has_adjustment"] == "True"
        injected = []
        if case_type == "inflated":
            same_car = [i for eid in by_car[acc["estimate"]["car_name"]] if eid != aid for i in items.get(eid, [])]
            injected = pick_injection(case_items, acc, allowed, same_car, rng) or \
                pick_injection(case_items, acc, allowed, generic_donors, rng)
            if not injected:
                raise SystemExit(f"{v['eval_id']}: no injectable item for {aid}")
        route = "siu" if case_type == "contradiction" else "adjust" if injected or real_adjusted else "approve"
        case = {
            "case_id": f"C{n:03d}",
            "case_type": case_type,
            "expected_route": route,
            "video": {k: v[k] for k in ("eval_id", "video_name", "zip_place", "accident_type", "fault_a", "fault_b",
                                        "a_progress", "b_progress", "point_of_view", "ego_fault", "other_fault")},
            "claimant": v["ego_role"],
            "claimant_impact_directions": sorted(allowed),
            "collision_confidence": areas[v["accident_type"]]["confidence"],
            "accident_id": aid,
            "car_name": acc["estimate"]["car_name"],
            "car_size": acc["car_size"],
            "images": acc["images"],
            "photo_parts": acc["parts"],
            "photo_directions": sorted(acc["photo_dirs"]),
            "pairing_fit": fits(acc["part_dirs"], allowed),
            "estimate_items": [{k: i[k] for k in ("no", "name", "work", "claimed_part", "claimed_labor",
                                                  "approved_part", "approved_labor")} for i in case_items],
            "injected_items": [{"name": i["name"], "work": i["work"], "claimed_part": i["claimed_part"],
                                "claimed_labor": i["claimed_labor"], "donor_estimate": i["estimate_id"]}
                               for i in injected],
            "claimed_total": claimed + sum(to_int(i["claimed_part"]) + to_int(i["claimed_labor"]) for i in injected),
            "approved_total": approved,
            "real_adjusted": real_adjusted,
            "header_claimed_with_vat": to_int(acc["estimate"]["claimed_total"]),
            "header_paid_with_vat": to_int(acc["estimate"]["total"]),
        }
        cases.append(case)
        manifest.append([case["case_id"], case_type, route, v["eval_id"], v["video_name"], aid,
                         ";".join(i["donor_estimate"] for i in case["injected_items"])])

    with (INTERIM_DIR / "synth_cases.jsonl").open("w", encoding="utf-8") as f:
        for c in cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with (ROOT / "data" / "manifests" / "synth_cases.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["case_id", "case_type", "expected_route", "eval_id", "video_name", "accident_id", "donor_estimates"])
        w.writerows(manifest)

    from collections import Counter
    print("case types", Counter(c["case_type"] for c in cases))
    print("routes", Counter(c["expected_route"] for c in cases))
    print("contradiction confidence", Counter(c["collision_confidence"] for c in cases if c["case_type"] == "contradiction"))
    print("images", sum(len(c["images"]) for c in cases), "injected items", sum(len(c["injected_items"]) for c in cases))


if __name__ == "__main__":
    main()
