"""Reviewed fault eval set: keep only clips whose label was confirmed on video.

The 150 clips of data/interim/eval_fault.csv were reviewed one by one against
their frames (docs/LABEL_REVIEW.md). The verdicts live in
data/manifests/label_review.csv (tracked in git, no scene descriptions):

    verdict   일치      label fits with ego = B (the dataset manual's first-person rule)
              역할반전  the accident type fits only if ego = A (labeler kept the table's A/B order)
              불일치    no role assignment of the labeled type fits the video
              애매      cannot be confirmed from the video
    ego_role  B for 일치, A for 역할반전, blank otherwise
    use       1 = in the reviewed set (일치/역할반전 and not a duplicate)

Output data/interim/eval_fault_reviewed.csv = eval_fault.csv rows with use=1 plus
ego_role, ego_fault (claimant's base fault) and other_fault.

Usage:
    python scripts/build_eval_reviewed.py                  # build from the manifest
    python scripts/build_eval_reviewed.py --export-review  # (re)write the manifest from
                                                           # data/interim/label_review/review.csv first
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERIM = ROOT / "data" / "interim"
MANIFEST = ROOT / "data" / "manifests" / "label_review.csv"
REVIEW = INTERIM / "label_review" / "review.csv"
OUT = INTERIM / "eval_fault_reviewed.csv"

ROLE = {"일치": "B", "역할반전": "A"}
# same accident twice in the eval set (docs/LABEL_REVIEW.md 2.3); keep one of each,
# drop both of F102/F114 because their labels contradict each other
DUPLICATES = {"F041": "duplicate of F034", "F097": "duplicate of F077", "F132": "duplicate of F128",
              "F102": "same accident as F114 with the opposite label", "F114": "same accident as F102 with the opposite label"}
FIELDS = ["eval_id", "video_name", "verdict", "confidence", "ego_role", "use", "exclude_reason"]


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def export_review() -> None:
    names = {r["eval_id"]: r["video_name"] for r in read_csv(INTERIM / "eval_fault.csv")}
    rows = []
    for r in sorted(read_csv(REVIEW), key=lambda r: r["eval_id"]):
        role = ROLE.get(r["verdict"], "")
        reason = DUPLICATES.get(r["eval_id"], "") or ("" if role else f"verdict {r['verdict']}")
        rows.append({"eval_id": r["eval_id"], "video_name": names[r["eval_id"]], "verdict": r["verdict"],
                     "confidence": r["confidence"], "ego_role": role,
                     "use": "1" if role and not reason else "0", "exclude_reason": reason})
    with MANIFEST.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {MANIFEST.relative_to(ROOT)} ({len(rows)} rows)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export-review", action="store_true")
    args = ap.parse_args()
    if args.export_review:
        export_review()

    review = {r["eval_id"]: r for r in read_csv(MANIFEST)}
    rows = read_csv(INTERIM / "eval_fault.csv")
    if set(review) != {r["eval_id"] for r in rows}:
        raise SystemExit("label_review.csv and eval_fault.csv cover different clips")
    out = []
    for r in rows:
        v = review[r["eval_id"]]
        if v["video_name"] != r["video_name"]:
            raise SystemExit(f"{r['eval_id']}: video name differs between label_review.csv and eval_fault.csv")
        if v["use"] != "1":
            continue
        role = v["ego_role"]
        ego, other = (r["fault_b"], r["fault_a"]) if role == "B" else (r["fault_a"], r["fault_b"])
        out.append({**r, "ego_role": role, "ego_fault": ego, "other_fault": other,
                    "review_verdict": v["verdict"], "review_confidence": v["confidence"]})
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(f"wrote {OUT.relative_to(ROOT)}: {len(out)} clips")
    print("  by place", dict(Counter(r["zip_place"] for r in out)))
    print("  ego role", dict(Counter(r["ego_role"] for r in out)))
    print("  excluded", dict(Counter(v["exclude_reason"].split(" of ")[0] for v in review.values() if v["use"] != "1")))


if __name__ == "__main__":
    main()
