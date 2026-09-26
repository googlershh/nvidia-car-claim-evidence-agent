"""Print field fill rates and distributions of the stage-1 AI Hub files.

Reads directly from the zips under data/raw (no extraction). The numbers
recorded in docs/HANDOFF.md section 7.3 come from this script.

Usage:
    python scripts/inspect_raw.py [video|damage|estimate ...]
"""

from __future__ import annotations

import collections
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EMPTY = ("", None, [])


def iter_zip_json(pattern: str, dataset_key: str):
    for path in sorted((RAW_DIR / dataset_key).rglob(pattern)):
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith(".json"):
                    yield path, name, json.loads(z.read(name).decode("utf-8-sig"))


def fill_rates(records: list[dict], title: str) -> None:
    print(f"\n-- fill rate: {title} (n={len(records)})")
    for field in sorted({k for r in records for k in r}):
        filled = sum(r.get(field) not in EMPTY for r in records)
        print(f"  {field:28s} {filled:7d}  {filled / len(records):6.1%}")


def inspect_video() -> None:
    print("=" * 20, "597 video labels (VL)")
    rows = []
    for path, name, d in iter_zip_json("VL_*.zip", "597"):
        v = d["video"]
        v["_place_zip"] = path.stem.split("_")[-1]
        v["_type"] = v.get("traffic_accident_type", v.get("accident_type"))
        v["_schema"] = ("rateAB" if "accident_negligence_rateA" in v else "rate1") + "/" + (
            "traffic_accident_type" if "traffic_accident_type" in v else "accident_type")
        rows.append(v)
    print("schema variants", collections.Counter(v["_schema"] for v in rows))
    fill_rates([{k: x for k, x in v.items() if not k.startswith("_")} for v in rows], "video")
    ab = [v for v in rows if "accident_negligence_rateA" in v]
    print("\nA+B == 100:", sum(v["accident_negligence_rateA"] + v["accident_negligence_rateB"] == 100 for v in ab), "/", len(ab))
    print("A:B", sorted(collections.Counter((v["accident_negligence_rateA"], v["accident_negligence_rateB"]) for v in ab).items()))
    print("filming_way x point_of_view", collections.Counter((v["filming_way"], v["video_point_of_view"]) for v in rows))
    for place in sorted({v["_place_zip"] for v in rows}):
        sub = [v for v in rows if v["_place_zip"] == place]
        print(f"\n== {place}: n={len(sub)}")
        for f in ("accident_place", "accident_place_feature", "_type"):
            c = collections.Counter(v[f] for v in sub)
            print(f"  {f}: {len(c)} distinct, top {c.most_common(10)}")


def inspect_damage() -> None:
    print("=" * 20, "581 damage labels (VL_damage)")
    images, anns = [], []
    for _, _, d in iter_zip_json("VL_damage.zip", "581"):
        images.append(d)
        anns.extend(d["annotations"])
    print("images", len(images), "annotations", len(anns))
    print("info.name", collections.Counter(d["info"]["name"] for d in images))
    print("supercategory", collections.Counter(d["categories"]["supercategory_name"] for d in images))
    fill_rates([{k: v for k, v in a.items() if k not in ("segmentation",)} for a in anns], "annotation")
    items = [x for a in anns for x in a["repair"]]
    print("\nrepair parts", collections.Counter(x.split(":")[0] for x in items).most_common(15))
    print("repair methods", collections.Counter(m for x in items for m in x.split(":", 1)[1].split(",")))
    print("images whose annotations share one repair list:",
          sum(len({tuple(a["repair"]) for a in d["annotations"]}) <= 1 for d in images), "/", len(images))


def inspect_estimate() -> None:
    print("=" * 20, "581 estimates (TS_99. 붙임_견적서) and link to VL_damage")
    images_per_id = collections.Counter(d["categories"]["id"] for _, _, d in iter_zip_json("VL_damage.zip", "581"))
    estimates = {name[:-5]: e for _, name, e in iter_zip_json("TS_99*.zip", "581")}
    print("estimates", len(estimates), collections.Counter(k.split("-")[0] for k in estimates))
    for prefix in ("as", "sc"):
        ids = {i for i in images_per_id if i.startswith(prefix)}
        hit = ids & estimates.keys()
        print(f"link {prefix}-: {len(hit)}/{len(ids)} ids have an estimate; images "
              f"{sum(images_per_id[i] for i in hit)}/{sum(images_per_id[i] for i in ids)}")
    items = [r for e in estimates.values() for r in e["수리내역"]]
    fill_rates([e["차량정보"] for e in estimates.values()], "차량정보")
    fill_rates(items, "수리내역 item")
    print("\n작업", collections.Counter(r.get("작업") for r in items).most_common(15))
    adjusted = [e for e in estimates.values() if any("손해사정전" in r for r in e["수리내역"])]
    changed = [e for e in adjusted if any(r["손해사정전"] != r["손해사정후"] for r in e["수리내역"] if "손해사정전" in r)]
    print(f"estimates with 손해사정전/후: {len(adjusted)}; with any adjusted item: {len(changed)}")


SECTIONS = {"video": inspect_video, "damage": inspect_damage, "estimate": inspect_estimate}

if __name__ == "__main__":
    for key in sys.argv[1:] or SECTIONS:
        SECTIONS[key]()
