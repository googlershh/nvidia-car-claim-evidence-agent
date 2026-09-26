"""Parse the downloaded AI Hub files into flat tables under data/interim.

Outputs (all regenerable, gitignored):
    accident_codes.csv        597 code table (type -> place, progress, base fault)
    video_labels.csv          597 labels + code-table cross check
    damage_images.jsonl       581 VL_damage, one image per line
    damage_part_images.jsonl  581 VL_damage_part
    estimates.csv             581 estimate headers
    estimate_items.csv        581 estimate line items (claimed / approved)
    sim_meta.csv              71958 simulation metadata

Usage:
    python scripts/build_interim.py [codes videos damage estimates sim ...]
"""

from __future__ import annotations

import csv
import dataclasses
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aihub import accident_codes, damage_labels, estimates, sim_meta, video_labels  # noqa: E402
from aihub.common import INTERIM_DIR  # noqa: E402

# accident_place code in the labels -> place in the code table (car-to-car scope)
PLACE_BY_ZIP = {"직선도로": "직선도로", "사거리교차로(신호등있음)": "사거리교차로(신호등있음)", "T자형교차로": "T자형교차로"}


def write_csv(name: str, rows: list[dict]) -> Path:
    path = INTERIM_DIR / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return path


def build_codes() -> dict[int, accident_codes.AccidentCode]:
    codes = accident_codes.parse()
    write_csv("accident_codes.csv", [{**dataclasses.asdict(c), "place_key": c.place_key} for c in codes])
    car = [c for c in codes if c.accident_object == "차대차"]
    print(f"[codes] {len(codes)} codes; car-to-car {len(car)} by place {Counter(c.place_key for c in car)}")
    return {c.code: c for c in codes}


def build_videos(codes: dict[int, accident_codes.AccidentCode]) -> None:
    rows, mismatch = [], []
    for lab in video_labels.iter_labels():
        code = codes.get(lab.accident_type)
        fault_ok = code is not None and code.fault_a == lab.fault_a
        place_ok = code is not None and code.place_key == PLACE_BY_ZIP.get(lab.zip_place, lab.zip_place)
        rows.append({**dataclasses.asdict(lab),
                     "code_place": code.place_key if code else "",
                     "code_fault_a": code.fault_a if code else "",
                     "fault_matches_code": fault_ok,
                     "place_matches_zip": place_ok})
        if not fault_ok:
            mismatch.append((lab.video_name, lab.accident_type, lab.fault_a, code.fault_a if code else None))
    write_csv("video_labels.csv", rows)
    print(f"[videos] {len(rows)} labels; schema {Counter(r['schema'] for r in rows)}")
    print(f"         fault == code base fault: {sum(r['fault_matches_code'] for r in rows)}/{len(rows)}; mismatches {mismatch[:5]}")
    bad_place = [(r["video_name"], r["zip_place"], r["code_place"]) for r in rows if not r["place_matches_zip"]]
    print(f"         code place == zip place: {len(rows) - len(bad_place)}/{len(rows)}; e.g. {bad_place[:5]}")


def build_damage(estimate_ids: set[str] | None) -> None:
    for label_set, out in (("damage", "damage_images.jsonl"), ("damage_part", "damage_part_images.jsonl")):
        path = INTERIM_DIR / out
        n, linked, levels = 0, 0, Counter()
        with path.open("w", encoding="utf-8") as f:
            for img in damage_labels.iter_images(label_set):
                f.write(json.dumps(dataclasses.asdict(img), ensure_ascii=False) + "\n")
                n += 1
                linked += estimate_ids is not None and img.accident_id in estimate_ids
                levels.update(a.level for a in img.annotations if a.level is not None)
        link = f"; with estimate {linked}" if estimate_ids is not None else ""
        print(f"[damage] {label_set}: {n} images{link}; levels {dict(sorted(levels.items()))}")


def build_estimates() -> set[str]:
    headers, items = [], []
    for est in estimates.iter_estimates():
        d = dataclasses.asdict(est)
        its = d.pop("items")
        headers.append({**d, "n_items": len(its), "has_adjustment": est.has_adjustment})
        items.extend({"estimate_id": est.estimate_id, **it} for it in its)
    write_csv("estimates.csv", headers)
    write_csv("estimate_items.csv", items)
    sc = [h for h in headers if h["source"] == "sc"]
    print(f"[estimates] {len(headers)} estimates, {len(items)} items; source {Counter(h['source'] for h in headers)}")
    print(f"            sc with adjustment {sum(h['has_adjustment'] for h in sc)}/{len(sc)}; "
          f"sc claimed-paid gap total {sum((h['claimed_total'] or 0) - (h['total'] or 0) for h in sc):,} won")
    return {h["estimate_id"] for h in headers}


def build_sim() -> None:
    if not any(sim_meta.META_DIR.glob("*.xml")):
        print(f"[sim] {sim_meta.extract()} XML extracted from Other.zip")
    recs = list(sim_meta.iter_meta())
    keys = list(dict.fromkeys(k for r in recs for k in r))
    write_csv("sim_meta.csv", [{k: r.get(k, "") for k in keys} for r in recs])
    table = sim_meta.collision_area_table(recs)
    print(f"[sim] {len(recs)} records; car-to-car {sum(table.values())}; top {table.most_common(4)}")


def main(targets: list[str]) -> None:
    targets = targets or ["codes", "videos", "estimates", "damage", "sim"]
    codes = build_codes() if {"codes", "videos"} & set(targets) else {}
    if "videos" in targets:
        build_videos(codes)
    estimate_ids = build_estimates() if "estimates" in targets else None
    if "damage" in targets:
        build_damage(estimate_ids)
    if "sim" in targets:
        build_sim()


if __name__ == "__main__":
    main(sys.argv[1:])
